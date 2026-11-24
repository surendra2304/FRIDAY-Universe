"""TASK-REL-098 — Fleet CD failed-deploy recovery guard.

Failure mode (PR #1642 body): a failed Server 1 deploy on 2026-11-24 left
Memora stopped. Under `set -e`, a failing `systemctl restart` — or any later
step — aborts the deploy script before the health gate runs, and nothing ever
starts the agent again. The same hole exists in the Server 2 job and in the
rollback script's restart loop (`scripts/rollback_deploy.sh`), the recovery
path the deploy's own error message points to.

The guard (one EXIT trap per job, installed right after the job's agent map,
plus the same pattern in the rollback script):

- on failure AFTER this run attempted a restart, make ONE bounded recovery
  attempt per attempted agent found inactive (`reset-failed` + `start`);
- exit with the ORIGINAL failure code — recovery never masks the failure;
- only agents/services this run attempted are touched, so moved/sleeping
  units (FRIDAY, Inference, Stratex on Server 1; VyralX on Server 2) are
  never revived by the guard, even though their LoadState is still
  `loaded` (disabled is not masked).

These tests EXECUTE the real job scripts and the real rollback script under
bash with fake `sudo` / `systemctl` / `curl` / `sleep` on PATH, so what is
tested is what deploys. The only line redirected is the deploy-host
`cd /opt/friday_universe` (this VM has no such checkout; the fixture repo
IS the checkout for the test).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-monorepo.yml"
ROLLBACK = ROOT / "scripts" / "rollback_deploy.sh"

GUARD_BEGIN = "# BEGIN REL-098 RECOVERY GUARD (TASK-REL-098)"
GUARD_END = "# END REL-098 RECOVERY GUARD (TASK-REL-098)"

FAKE_SUDO = """#!/usr/bin/env bash
# Fake sudo: pass through to the real command (fake systemctl / cp).
exec "$@"
"""

FAKE_SYSTEMCTL = """#!/usr/bin/env bash
# Stateful fake systemctl for the REL-098 guard tests.
# $FAKE_LOAD_TABLE: lines "UNIT=LoadState"; missing unit -> not-found.
# $FAKE_ACTIVE_FILE: units currently active (one per line).
# $FAKE_FAIL_RESTART / $FAKE_FAIL_START: space-separated unit names whose
# restart/start fails (and leaves the unit inactive).
# $FAKE_LOG: every invocation appended.
printf '%s\\n' "$*" >> "${FAKE_LOG:-/dev/null}"
table="$FAKE_LOAD_TABLE"
active="$FAKE_ACTIVE_FILE"
cmd="$1"; shift || true
case "$cmd" in
  show)
    unit="${1%.service}"; shift
    prop=""
    for a in "$@"; do case "$a" in --property=*) prop="${a#--property=}";; esac; done
    if [ "$prop" = "LoadState" ]; then
      state=$(grep -E "^${unit}=" "$table" 2>/dev/null | cut -d= -f2)
      echo "${state:-not-found}"
    elif [ "$prop" = "NRestarts" ]; then
      echo "0"
    else
      echo ""
    fi
    exit 0
    ;;
  is-active)
    quiet=0; unit=""
    for a in "$@"; do case "$a" in --quiet) quiet=1;; *) unit="${a%.service}";; esac; done
    if grep -qx "$unit" "$active" 2>/dev/null; then
      [ "$quiet" -eq 0 ] && echo "active"
      exit 0
    else
      [ "$quiet" -eq 0 ] && echo "inactive"
      exit 1
    fi
    ;;
  restart|start)
    unit="${1%.service}"
    fail_list="${FAKE_FAIL_RESTART:-}"
    [ "$cmd" = "start" ] && fail_list="${FAKE_FAIL_START:-}"
    if echo " $fail_list " | grep -qw "$unit"; then
      grep -vx "$unit" "$active" > "$active.tmp" 2>/dev/null || true
      mv "$active.tmp" "$active" 2>/dev/null || true
      exit 1
    fi
    grep -qx "$unit" "$active" 2>/dev/null || echo "$unit" >> "$active"
    exit 0
    ;;
  reset-failed|daemon-reload|enable|list-timers)
    exit 0
    ;;
  cat)
    exit 0
    ;;
  *)
    echo "fake systemctl: unsupported: $cmd $*" >&2
    exit 1
    ;;
esac
"""

FAKE_CURL = """#!/usr/bin/env bash
# Fail when the probed port is in $FAKE_CURL_FAIL_PORTS (space-separated).
for p in ${FAKE_CURL_FAIL_PORTS:-}; do
  case "$*" in *":${p}/"*) exit 1;; esac
done
exit 0
"""

FAKE_SLEEP = """#!/usr/bin/env bash
# No-op sleep: the health gate's settle windows must not cost real time.
exit 0
"""


def _git(cwd, *args):
    return subprocess.check_output(
        ["git", "-C", str(cwd), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def _job_script(job):
    """The exact bash of one deploy job, dedented from the workflow YAML."""
    text = WORKFLOW.read_text(encoding="utf-8")
    if job == "server1":
        chunk = text[text.index("deploy-server1:"):text.index("deploy-server2:")]
    else:
        chunk = text[text.index("deploy-server2:"):]
    lines = chunk[chunk.index("script: |") + len("script: |"):].splitlines()
    out = []
    for ln in lines:
        if ln.strip() == "":
            out.append("")
        else:
            assert ln.startswith(" " * 12), ln
            out.append(ln[12:])
    return "\n".join(out)


def _guard_blocks():
    text = WORKFLOW.read_text(encoding="utf-8")
    parts = text.split(GUARD_BEGIN)[1:]
    assert len(parts) == 2, f"expected 2 guard blocks, found {len(parts)}"
    return [GUARD_BEGIN + p.split(GUARD_END)[0] + GUARD_END for p in parts]


def _fake_bin(tmp_path, *, loads, active, fail_restart="", fail_start="",
              fail_ports=""):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "sudo").write_text(FAKE_SUDO)
    (bindir / "systemctl").write_text(FAKE_SYSTEMCTL)
    (bindir / "curl").write_text(FAKE_CURL)
    (bindir / "sleep").write_text(FAKE_SLEEP)
    for name in ("sudo", "systemctl", "curl", "sleep"):
        (bindir / name).chmod(0o755)
    (tmp_path / "loads.txt").write_text(
        "".join(f"{u}={s}\n" for u, s in loads.items()))
    (tmp_path / "active.txt").write_text("".join(f"{u}\n" for u in active))
    (tmp_path / "systemctl.log").write_text("")
    return bindir, {
        "FAKE_LOAD_TABLE": str(tmp_path / "loads.txt"),
        "FAKE_ACTIVE_FILE": str(tmp_path / "active.txt"),
        "FAKE_LOG": str(tmp_path / "systemctl.log"),
        "FAKE_FAIL_RESTART": fail_restart,
        "FAKE_FAIL_START": fail_start,
        "FAKE_CURL_FAIL_PORTS": fail_ports,
    }


def _base_env(tmp_path, **fake_kwargs):
    bindir, fenv = _fake_bin(tmp_path, **fake_kwargs)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:/usr/bin:/bin"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.update(fenv)
    return env


def _calls(tmp_path):
    log = tmp_path / "systemctl.log"
    if not log.exists():
        return []
    return [line for line in log.read_text().splitlines() if line.strip()]


def _starts(calls):
    return [c for c in calls if c.startswith("start ")]


@pytest.fixture
def fleet(tmp_path):
    """Origin + local clone on main; advance() lands a folder change."""
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-b", "main")
    _git(origin, "config", "user.email", "fixture@example.org")
    _git(origin, "config", "user.name", "Fixture")
    for folder in ("Forge", "IntelX", "VyralX", "Memora", "Sentinel",
                   "Cortex", "Futuris"):
        (origin / folder).mkdir()
        (origin / folder / "app.py").write_text("version=1\n")
    _git(origin, "add", ".")
    _git(origin, "commit", "-m", "initial")
    local = tmp_path / "local"
    subprocess.check_output(["git", "clone", "-q", str(origin), str(local)],
                            text=True)
    _git(local, "config", "user.email", "fixture@example.org")
    _git(local, "config", "user.name", "Fixture")

    def advance(folder):
        (origin / folder / "app.py").write_text("version=2\n")
        _git(origin, "commit", "-am", f"change {folder}")
        return _git(origin, "rev-parse", "HEAD")

    return origin, local, advance


def _run_job(tmp_path, local, target, job, **fake_kwargs):
    script = _job_script(job)
    script = script.replace("${{ github.sha }}", target)
    script = script.replace("${{ github.event_name }}", "push")
    script = script.replace("cd /opt/friday_universe", f"cd {local}", 1)
    env = _base_env(tmp_path, **fake_kwargs)
    return subprocess.run(["bash", "-c", script], capture_output=True,
                          text=True, timeout=120, env=env, cwd=local)


# Post-move (2026-11-24) Server 1: FRIDAY / Inference / Stratex are
# installed (LoadState=loaded — disabled is NOT masked) but STOPPED
# sleeping backups. The guard must never start them.
S1_LOADS = {"Memora": "loaded", "Forge": "loaded", "Sentinel": "loaded",
            "FRIDAY": "loaded", "Inference": "loaded", "Stratex": "loaded",
            "FRIDAY-Voice": "loaded", "Stratex-Daemon": "loaded"}
S1_ACTIVE = ["Memora", "Forge", "Sentinel"]

# Server 2: VyralX is masked (moved to AWS U2); daemon unit still loaded.
S2_LOADS = {"VyralX": "masked", "Cortex": "loaded", "IntelX": "loaded",
            "Futuris": "loaded", "VyralX-Daemon": "loaded"}
S2_ACTIVE = ["Cortex", "IntelX", "Futuris", "VyralX-Daemon"]


# -- structural pins: the merged CD map (PR #1642) + the guard ------------


def test_guard_blocks_identical_and_placed():
    blocks = _guard_blocks()
    assert blocks[0] == blocks[1], "S1/S2 guard blocks must stay in sync"
    text = WORKFLOW.read_text(encoding="utf-8")
    s1 = text.split("deploy-server2:")[0]
    s2 = text.split("deploy-server2:")[1]
    for job_text, agents in (
            (s1, 'SERVER1_AGENTS=("Memora" "Forge" "Sentinel")'),
            (s2, 'SERVER2_AGENTS=("VyralX" "Cortex" "IntelX" "Futuris")')):
        assert agents in job_text
        assert job_text.index(agents) < job_text.index(GUARD_BEGIN)
        assert job_text.index(GUARD_BEGIN) < job_text.index(
            'for AGENT in "${SERVER' + ('1' if job_text is s1 else '2') +
            '_AGENTS[@]}"; do')
    # The guard's scope is the attempted set, never the whole agent map.
    assert "for AGENT in $RESTART_ATTEMPTED" in blocks[0]
    assert "trap rel098_recover EXIT" in blocks[0]
    assert "reset-failed" in blocks[0]


def test_cd_map_verification_pr1642():
    text = WORKFLOW.read_text(encoding="utf-8")
    s1 = text.split("deploy-server2:")[0]
    # Paths filter: moved agents no longer trigger the Server 1 deploy.
    filters = text.split("filters: |")[1].split("deploy-server1:")[0]
    server1_filter = filters.split("server2:")[0]
    assert "- 'FRIDAY/**'" not in server1_filter
    assert "- 'Inference/**'" not in server1_filter
    assert "- 'Stratex/**'" not in server1_filter
    assert "- 'Memora/**'" in server1_filter
    # No moved-agent restart survives in the Server 1 job.
    assert "sudo systemctl restart FRIDAY-Voice.service" not in s1
    assert "sudo systemctl restart Stratex-Daemon.service" not in s1
    assert "sudo systemctl restart FRIDAY.service" not in s1
    assert "sudo systemctl restart Inference.service" not in s1
    assert "sudo systemctl restart Stratex.service" not in s1
    # Every restart in both jobs is recorded for the guard, daemon included.
    assert text.count('RESTART_ATTEMPTED="$RESTART_ATTEMPTED') == 3
    # Rollback script mirrors the same map (PR #1642 follow-up 2).
    rb = ROLLBACK.read_text(encoding="utf-8")
    assert "SERVER1_SERVICES=(Memora Forge Sentinel)" in rb
    assert "SERVER2_SERVICES=(VyralX Cortex IntelX Futuris VyralX-Daemon)" in rb


# -- behavioural proof: Server 1 -------------------------------------------


def test_s1_restart_failure_recovers_agent_and_preserves_failure(
        fleet, tmp_path):
    _, local, advance = fleet
    target = advance("Forge")
    result = _run_job(tmp_path, local, target, "server1",
                      loads=S1_LOADS, active=S1_ACTIVE,
                      fail_restart="Forge")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "TASK-REL-098 recovery" in result.stdout
    calls = _calls(tmp_path)
    assert "reset-failed Forge.service" in calls, calls
    assert "start Forge.service" in calls, calls
    # The guard never revives a moved/sleeping unit, even though its
    # LoadState is loaded and it is stopped right now.
    for unit in ("FRIDAY", "Inference", "Stratex", "FRIDAY-Voice",
                 "Stratex-Daemon"):
        assert f"start {unit}.service" not in calls, calls
        assert f"reset-failed {unit}.service" not in calls, calls


def test_s1_later_step_failure_does_not_restart_healthy_agents(
        fleet, tmp_path):
    # Restart succeeds; the health gate then fails Forge. The trap runs
    # (header printed) but finds Forge active and starts nothing.
    _, local, advance = fleet
    target = advance("Forge")
    result = _run_job(tmp_path, local, target, "server1",
                      loads=S1_LOADS, active=S1_ACTIVE,
                      fail_ports="8006")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "TASK-REL-098 recovery" in result.stdout
    assert _starts(_calls(tmp_path)) == [], _calls(tmp_path)


def test_s1_failure_before_any_restart_recovers_nothing(fleet, tmp_path):
    # Dirty checkout: safe checkout refuses before the guard is even
    # installed and before any restart — nothing to recover.
    _, local, advance = fleet
    target = advance("Forge")
    (local / "Forge" / "app.py").write_text("collaborator edit\n")
    result = _run_job(tmp_path, local, target, "server1",
                      loads=S1_LOADS, active=S1_ACTIVE)
    assert result.returncode != 0, result.stdout + result.stderr
    assert "TASK-REL-098 recovery" not in result.stdout
    assert _starts(_calls(tmp_path)) == [], _calls(tmp_path)


def test_s1_success_path_recovers_nothing(fleet, tmp_path):
    _, local, advance = fleet
    target = advance("Forge")
    result = _run_job(tmp_path, local, target, "server1",
                      loads=S1_LOADS, active=S1_ACTIVE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "TASK-REL-098 recovery" not in result.stdout
    assert _starts(_calls(tmp_path)) == [], _calls(tmp_path)


def test_recovery_start_failure_still_fails(fleet, tmp_path):
    # Even when the recovery start itself fails, the script exits with the
    # original failure (a warning is logged, the failure is not masked).
    _, local, advance = fleet
    target = advance("Forge")
    result = _run_job(tmp_path, local, target, "server1",
                      loads=S1_LOADS, active=S1_ACTIVE,
                      fail_restart="Forge", fail_start="Forge")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "recovery start failed" in result.stdout


# -- behavioural proof: Server 2 -------------------------------------------


def test_s2_restart_failure_recovers_intelx(fleet, tmp_path):
    _, local, advance = fleet
    target = advance("IntelX")
    result = _run_job(tmp_path, local, target, "server2",
                      loads=S2_LOADS, active=S2_ACTIVE,
                      fail_restart="IntelX")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "TASK-REL-098 recovery" in result.stdout
    calls = _calls(tmp_path)
    assert "reset-failed IntelX.service" in calls, calls
    assert "start IntelX.service" in calls, calls
    assert "start VyralX.service" not in calls, calls


def test_s2_daemon_restart_failure_recovers_daemon(fleet, tmp_path):
    _, local, advance = fleet
    target = advance("VyralX")
    result = _run_job(tmp_path, local, target, "server2",
                      loads=S2_LOADS, active=S2_ACTIVE,
                      fail_restart="VyralX-Daemon")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "TASK-REL-098 recovery" in result.stdout
    calls = _calls(tmp_path)
    assert "start VyralX-Daemon.service" in calls, calls
    assert "start VyralX.service" not in calls, calls


# -- behavioural proof: rollback script ------------------------------------


def _rollback_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "fixture@example.org")
    _git(repo, "config", "user.name", "Fixture")
    (repo / "Memora").mkdir()
    (repo / "Memora" / "app.py").write_text("v1\n")
    (repo / "scripts").mkdir()
    (repo / "scripts" / "x.py").write_text("v1\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "A")
    _git(repo, "commit", "--allow-empty", "-m", "B")
    (repo / "Memora" / "app.py").write_text("v2\n")
    (repo / "scripts" / "x.py").write_text("v2\n")
    _git(repo, "commit", "-am", "C touches Memora + scripts")
    return repo


def _run_rollback(tmp_path, repo, *args, **fake_kwargs):
    rundir = tmp_path / "systemd-run"
    rundir.mkdir(exist_ok=True)
    env = _base_env(tmp_path, **fake_kwargs)
    env["ROLLBACK_REPO_DIR"] = str(repo)
    env["ROLLBACK_SYSTEMD_RUN_DIR"] = str(rundir)
    return subprocess.run(["bash", str(ROLLBACK), *args],
                          capture_output=True, text=True, timeout=120,
                          env=env)


def test_rollback_restart_failure_recovers_service(tmp_path):
    repo = _rollback_repo(tmp_path)
    result = _run_rollback(tmp_path, repo, "HEAD~1", "--yes",
                           loads=S1_LOADS, active=S1_ACTIVE,
                           fail_restart="Memora")
    assert result.returncode != 0, result.stdout + result.stderr
    assert "TASK-REL-098 recovery" in result.stdout
    assert "ROLLBACK DONE" not in result.stdout
    calls = _calls(tmp_path)
    assert "reset-failed Memora.service" in calls, calls
    assert "start Memora.service" in calls, calls


def test_rollback_success_path_recovers_nothing(tmp_path):
    repo = _rollback_repo(tmp_path)
    result = _run_rollback(tmp_path, repo, "HEAD~1", "--yes",
                           loads=S1_LOADS, active=S1_ACTIVE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ROLLBACK DONE" in result.stdout
    assert _starts(_calls(tmp_path)) == [], _calls(tmp_path)


def test_rollback_map_excludes_moved_agents_even_when_loaded(tmp_path):
    # Dry-run: Memora + scripts changed, FRIDAY loaded on Server 1 — the
    # old map would restart FRIDAY; the fixed map restarts only the live
    # Server 1 agents.
    repo = _rollback_repo(tmp_path)
    result = _run_rollback(tmp_path, repo, "HEAD~1", "--dry-run",
                           loads=S1_LOADS, active=S1_ACTIVE)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "would restart: Memora Forge Sentinel" in result.stdout
