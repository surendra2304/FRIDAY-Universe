"""TASK-OBS-019 — Fleet CD S2 post-deploy health-gate tests.

Fleet CD (`.github/workflows/deploy-monorepo.yml`) failed run 45122467146
on Server 2 at "Update Changed Agents on Server 2": the S2 post-deploy
health gate curls every S2 agent's /health and fails the job on any
non-2xx — including Futuris :8004 / IntelX :8005, which were ALREADY 503
before the deploy (pre-existing, not deploy-caused). The fix, S2 job
only, is two marked blocks in the workflow:

(a) a pre-deploy health baseline, captured BEFORE any restart, recording
    which agents were healthy (HEALTHY_BEFORE) and that the baseline ran
    (BASELINE_TAKEN); and
(b) a pre-existing-degradation filter after the second-chance sweep:
    a FAILED_HEALTH agent that was already unhealthy pre-deploy is a
    loud ::warning::, not a job failure; only a healthy->unhealthy
    REGRESSION still fails the job. Fail-closed: if the baseline never
    ran, nothing is downgraded.

These tests extract those exact blocks from the workflow file and EXECUTE
them under bash with fake `curl` / `systemctl` / `sleep` on PATH, so what
is tested is what deploys:

- baseline records healthy agents, skips masked units, retries a blip;
- filter downgrades pre-existing 503s (job passes), keeps regressions
  (job fails), handles a mixed set, and fails closed with no baseline;
- the combined sequence (baseline -> simulated gate failure -> filter)
  reproduces run 45122467146's shape and passes it.

Plus structural pins: exactly one baseline and one filter block, both
confined to the S2 job, baseline before the restart loop, filter after
the second-chance sweep and before the final failure block, and the S2
job script still parses under `bash -n`.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-monorepo.yml"

BASELINE_BEGIN = "# BEGIN PRE-DEPLOY HEALTH BASELINE (TASK-OBS-019)"
BASELINE_END = "# END PRE-DEPLOY HEALTH BASELINE (TASK-OBS-019)"
FILTER_BEGIN = "# BEGIN PRE-EXISTING DEGRADATION FILTER (TASK-OBS-019)"
FILTER_END = "# END PRE-EXISTING DEGRADATION FILTER (TASK-OBS-019)"
S2_JOB = "deploy-server2:"

FAKE_CURL = """#!/usr/bin/env bash
# Fake curl: last arg is the URL; ports in $CURL_FAIL_PORTS answer like
# `curl -f` on a 503 (exit 22), everything else answers 200 (exit 0).
# Each probe is logged to $CURL_LOG so tests can count retries.
url="${@: -1}"
port="$(printf '%s' "$url" | sed -E 's/.*:([0-9]+)\\/health.*/\\1/')"
printf '%s\\n' "$port" >> "${CURL_LOG:-/dev/null}"
case " ${CURL_FAIL_PORTS:-} " in *" $port "*) exit 22;; *) exit 0;; esac
"""

FAKE_SYSTEMCTL = """#!/usr/bin/env bash
# Fake systemctl: agents in $SYSTEMCTL_MASKED report LoadState=masked,
# everything else loaded; NRestarts 0; is-active always active.
if [ "$1" = "show" ]; then
  unit="$2"
  agent="${unit%.service}"
  if [ "$3" = "--property=LoadState" ]; then
    case " ${SYSTEMCTL_MASKED:-} " in *" $agent "*) echo "masked";; *) echo "loaded";; esac
    exit 0
  fi
  if [ "$3" = "--property=NRestarts" ]; then echo "0"; exit 0; fi
  echo "loaded"; exit 0
fi
if [ "$1" = "is-active" ]; then echo "active"; exit 0; fi
exit 0
"""

FAKE_SLEEP = """#!/usr/bin/env bash
# No-op sleep: the baseline retry delays are real time in production;
# tests must not wait them out.
exit 0
"""


def _marked_blocks(begin: str, end: str) -> list[str]:
    """Extract the executable bash of each marked block, dedented."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    blocks: list[str] = []
    current: list[str] | None = None
    indent = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(begin):
            indent = line[: len(line) - len(line.lstrip())]
            current = [line]
            continue
        if current is not None:
            current.append(line)
            if stripped.startswith(end):
                blocks.append(
                    "\n".join(
                        ln[len(indent):] if ln.startswith(indent) else ln
                        for ln in current
                    )
                )
                current = None
    return blocks


def _fake_bin(tmp_path: Path, *, fail_ports: str = "8004 8005",
              masked: str = "") -> tuple[Path, dict[str, str]]:
    """Fake curl/systemctl/sleep on PATH; returns (bin dir, env additions)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "curl").write_text(FAKE_CURL)
    (bindir / "systemctl").write_text(FAKE_SYSTEMCTL)
    (bindir / "sleep").write_text(FAKE_SLEEP)
    for name in ("curl", "systemctl", "sleep"):
        (bindir / name).chmod(0o755)
    env = {
        "CURL_FAIL_PORTS": fail_ports,
        "SYSTEMCTL_MASKED": masked,
        "CURL_LOG": str(tmp_path / "curl.log"),
    }
    return bindir, env


def _run_bash(script: str, tmp_path: Path, bindir: Path,
              env: dict[str, str]) -> subprocess.CompletedProcess:
    import os

    full_env = dict(os.environ)
    full_env["PATH"] = f"{bindir}:{full_env['PATH']}"
    full_env.update(env)
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True, text=True, timeout=120, env=full_env,
        cwd=tmp_path,
    )


def _baseline_script() -> str:
    blocks = _marked_blocks(BASELINE_BEGIN, BASELINE_END)
    assert len(blocks) == 1, f"expected 1 baseline block, found {len(blocks)}"
    prelude = 'SERVER2_AGENTS=("VyralX" "Cortex" "IntelX" "Futuris")\n'
    tail = '\necho "RESULT:HEALTHY_BEFORE=[$HEALTHY_BEFORE] BASELINE_TAKEN=[$BASELINE_TAKEN]"\n'
    return prelude + blocks[0] + tail


def _filter_script(failed: str, healthy_before: str,
                   baseline_taken: str | None) -> str:
    blocks = _marked_blocks(FILTER_BEGIN, FILTER_END)
    assert len(blocks) == 1, f"expected 1 filter block, found {len(blocks)}"
    taken = f'BASELINE_TAKEN="{baseline_taken}"' if baseline_taken is not None else "unset BASELINE_TAKEN"
    prelude = (
        f'FAILED_HEALTH="{failed}"\n'
        f'HEALTHY_BEFORE="{healthy_before}"\n'
        f"{taken}\n"
    )
    tail = '\necho "RESULT:FAILED_HEALTH=[$FAILED_HEALTH]"\n'
    return prelude + blocks[0] + tail


# -- structural pins -------------------------------------------------------


def test_exactly_one_baseline_and_one_filter_block() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count(BASELINE_BEGIN) == 1
    assert text.count(BASELINE_END) == 1
    assert text.count(FILTER_BEGIN) == 1
    assert text.count(FILTER_END) == 1


def test_obs019_confined_to_server2_job() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    s2_at = text.index(S2_JOB)
    # Nothing OBS-019 before the S2 job: Server 1's gate is untouched.
    assert "TASK-OBS-019" not in text[:s2_at]
    assert text.index(BASELINE_BEGIN) > s2_at
    assert text.index(FILTER_BEGIN) > text.index(BASELINE_END)


def test_baseline_before_restart_loop_filter_after_second_chance() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    s2 = text[text.index(S2_JOB):]
    restart_at = s2.index('for AGENT in "${SERVER2_AGENTS[@]}"; do')
    assert s2.index(BASELINE_BEGIN) < restart_at, (
        "baseline must run before any restart"
    )
    # Second occurrence of the sweep marker is the S2 one.
    sweeps = [m.start() for m in re.finditer(
        "second-chance sweep after 60s settle \\(TASK-OBS-005\\)", s2)]
    assert len(sweeps) == 1, f"expected 1 sweep marker in S2 job, found {len(sweeps)}"
    assert s2.index(FILTER_BEGIN) > sweeps[0]
    assert s2.index(FILTER_END) < s2.index(
        'echo "=== Health gate passed on Server 2 ==="'), (
        "filter must run before the final failure block"
    )


def test_s2_job_script_is_valid_bash() -> None:
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    scripts: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].rstrip().endswith("script: |"):
            indent = len(lines[i]) - len(lines[i].lstrip())
            body: list[str] = []
            i += 1
            while i < len(lines):
                if lines[i].strip() and (
                    len(lines[i]) - len(lines[i].lstrip())
                ) <= indent:
                    break
                body.append(lines[i])
                i += 1
            nonblank = [b for b in body if b.strip()]
            dedent = min(len(b) - len(b.lstrip()) for b in nonblank)
            scripts.append(
                "\n".join(b[dedent:] if b.strip() else "" for b in body)
            )
            continue
        i += 1
    assert len(scripts) == 2, f"expected 2 deploy scripts, found {len(scripts)}"
    s2_script = scripts[1]
    assert BASELINE_BEGIN in s2_script and FILTER_BEGIN in s2_script
    neutralised = re.sub(r"\$\{\{[^}]*\}\}", "0" * 40, s2_script)
    result = subprocess.run(
        ["bash", "-n"], input=neutralised, capture_output=True,
        text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr


# -- baseline behaviour ----------------------------------------------------


def test_baseline_records_healthy_agents_only(tmp_path: Path) -> None:
    bindir, env = _fake_bin(tmp_path)  # Futuris 8004 / IntelX 8005 fail
    result = _run_bash(_baseline_script(), tmp_path, bindir, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT:HEALTHY_BEFORE=[ VyralX Cortex] BASELINE_TAKEN=[yes]" in result.stdout, result.stdout
    assert "Futuris: NOT healthy before deploy" in result.stdout
    assert "IntelX: NOT healthy before deploy" in result.stdout
    # A failing agent is retried 3x before being called degraded.
    log = (tmp_path / "curl.log").read_text().splitlines()
    assert log.count("8004") == 3, log
    assert log.count("8005") == 3, log
    assert log.count("8009") == 1 and log.count("8010") == 1, log


def test_baseline_skips_masked_units(tmp_path: Path) -> None:
    bindir, env = _fake_bin(tmp_path, masked="VyralX")  # VyralX masked on S2
    result = _run_bash(_baseline_script(), tmp_path, bindir, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT:HEALTHY_BEFORE=[ Cortex] BASELINE_TAKEN=[yes]" in result.stdout, result.stdout
    assert "VyralX: skipped" in result.stdout
    assert "8010" not in (tmp_path / "curl.log").read_text(), (
        "masked units must not be probed"
    )


# -- filter behaviour ------------------------------------------------------


def test_filter_downgrades_preexisting_503s_to_warning(tmp_path: Path) -> None:
    bindir, env = _fake_bin(tmp_path)
    script = _filter_script("Futuris IntelX", " VyralX Cortex", "yes")
    result = _run_bash(script, tmp_path, bindir, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT:FAILED_HEALTH=[]" in result.stdout, result.stdout
    assert "::warning::Futuris UNHEALTHY" in result.stdout
    assert "::warning::IntelX UNHEALTHY" in result.stdout
    assert "pre-existing degradation" in result.stdout


def test_filter_keeps_healthy_to_unhealthy_regression(tmp_path: Path) -> None:
    bindir, env = _fake_bin(tmp_path)
    script = _filter_script("IntelX", " VyralX Cortex IntelX", "yes")
    result = _run_bash(script, tmp_path, bindir, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT:FAILED_HEALTH=[ IntelX]" in result.stdout, result.stdout
    assert "REGRESSION" in result.stdout
    assert "::warning::IntelX" not in result.stdout


def test_filter_mixed_set_warns_one_keeps_one(tmp_path: Path) -> None:
    bindir, env = _fake_bin(tmp_path)
    script = _filter_script("Futuris Cortex", " VyralX Cortex", "yes")
    result = _run_bash(script, tmp_path, bindir, env)
    assert "RESULT:FAILED_HEALTH=[ Cortex]" in result.stdout, result.stdout
    assert "::warning::Futuris UNHEALTHY" in result.stdout
    assert "Cortex: REGRESSION" in result.stdout


def test_filter_fails_closed_when_baseline_never_ran(tmp_path: Path) -> None:
    bindir, env = _fake_bin(tmp_path)
    # BASELINE_TAKEN unset entirely: nothing may be downgraded.
    script = _filter_script("Futuris IntelX", " VyralX Cortex", None)
    result = _run_bash(script, tmp_path, bindir, env)
    assert "RESULT:FAILED_HEALTH=[ Futuris IntelX]" in result.stdout, result.stdout
    assert "::warning::" not in result.stdout


def test_filter_empty_failed_health_is_noop(tmp_path: Path) -> None:
    bindir, env = _fake_bin(tmp_path)
    script = _filter_script("", " VyralX Cortex IntelX Futuris", "yes")
    result = _run_bash(script, tmp_path, bindir, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT:FAILED_HEALTH=[]" in result.stdout


# -- combined sequence (run 45122467146's shape) ---------------------------


def test_combined_baseline_gate_filter_passes_preexisting_503s(tmp_path: Path) -> None:
    """Baseline (Futuris/IntelX 503) -> gate fails both -> filter empties
    the failure list: the job would PASS, as it should have on run
    45122467146. The regression twin fails, as it should."""
    bindir, env = _fake_bin(tmp_path)
    baseline = _baseline_script()
    blocks = _marked_blocks(FILTER_BEGIN, FILTER_END)
    assert len(blocks) == 1
    combined = (
        baseline
        + '\nFAILED_HEALTH="Futuris IntelX"\n'
        + blocks[0]
        + '\necho "RESULT:FAILED_HEALTH=[$FAILED_HEALTH]"\n'
        + 'if [ -n "$FAILED_HEALTH" ]; then exit 1; fi\n'
    )
    result = _run_bash(combined, tmp_path, bindir, env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT:FAILED_HEALTH=[]" in result.stdout, result.stdout

    # Regression twin: IntelX was healthy before, 503 after -> exit 1.
    bindir2, env2 = _fake_bin(tmp_path, fail_ports="")
    combined2 = (
        baseline
        + '\nFAILED_HEALTH="IntelX"\n'
        + blocks[0]
        + '\necho "RESULT:FAILED_HEALTH=[$FAILED_HEALTH]"\n'
        + 'if [ -n "$FAILED_HEALTH" ]; then exit 1; fi\n'
    )
    result2 = _run_bash(combined2, tmp_path, bindir2, env2)
    assert result2.returncode == 1, result2.stdout + result2.stderr
    assert "RESULT:FAILED_HEALTH=[ IntelX]" in result2.stdout, result2.stdout
