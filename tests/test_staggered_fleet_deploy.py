"""TASK-REL-053 — Fleet CD staggered, health-gated restart tests (Server 1).

Fleet CD (`.github/workflows/deploy-monorepo.yml`) used to restart every
Server 1 unit ~10s apart and probe health only afterwards. On the 956MB
host all the cold starts then paged in concurrently, and on 2026-11-17
FRIDAY — the website's only upstream — took ~23 minutes to bind :10000
while the public site returned 502.

The fix is a marked STAGGERED RESTART block in the deploy-server1 job:
units restart one at a time, in a fixed order (FRIDAY last, FRIDAY-Voice
after her, exactly once), each gated on its own health — HTTP /health
for the API agents, the daemon heartbeat file for Stratex-Daemon, the
worker's registration status file for FRIDAY-Voice. A gate timeout
aborts the deploy with later units unrestarted.

These tests extract that exact block from the workflow file and EXECUTE
it under bash against stub `systemctl` / `curl` / `sudo` / `sleep`
binaries, so what is tested is what deploys:

(a) full dispatch: restarts happen in the pinned order, each restart is
    preceded by a successful gate probe of the previous unit, and
    FRIDAY-Voice restarts exactly once;
(b) a gate that never succeeds aborts the deploy — exit 1, the output
    names the unit and the workflow_dispatch recovery, and no later
    unit is restarted;
(c) a single-agent change restarts only that agent;
(d) a FRIDAY change restarts FRIDAY and FRIDAY-Voice (her trigger),
    not Stratex-Daemon.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-monorepo.yml"

BEGIN = "# BEGIN STAGGERED RESTART (TASK-REL-053)"
END = "# END STAGGERED RESTART (TASK-REL-053)"

EXPECTED_ORDER = [
    "Inference.service",
    "Memora.service",
    "Stratex.service",
    "Stratex-Daemon.service",
    "IntelX.service",
    "Futuris.service",
    "Forge.service",
    "FRIDAY.service",
    "FRIDAY-Voice.service",
]

SYSTEMCTL_STUB = r"""#!/bin/bash
# Stub systemctl: logs every call, emulates restart side effects.
echo "systemctl $*" >> "$STUB_LOG"
cmd="$1"; shift || true
case "$cmd" in
  show)
    unit="$1"
    case "$*" in
      *LoadState*) echo "loaded" ;;
      *MainPID*) cat "$STUB_STATE/$unit.mainpid" ;;
      *) echo "0" ;;
    esac
    ;;
  cat)
    echo "ExecStart=/bin/true" ;;
  restart)
    unit="$1"
    old="$(cat "$STUB_STATE/$unit.mainpid")"
    new=$((old + 500))
    echo "$new" > "$STUB_STATE/$unit.mainpid"
    echo "restarted $unit" >> "$STUB_LOG"
    if [ "$unit" != "${STUB_FAIL_UNIT:-}" ]; then
      case "$unit" in
        Stratex-Daemon.service)
          mkdir -p Stratex/state
          printf '{\n  "pid": %s,\n  "updated_at": 2000.5\n}\n' "$new" \
            > Stratex/state/daemon_heartbeat.json
          ;;
        FRIDAY-Voice.service)
          mkdir -p FRIDAY/data
          printf '{\n  "state": "registered",\n  "pid": %s\n}\n' "$new" \
            > FRIDAY/data/voice_worker_status.json
          ;;
        *)
          port="$(cat "$STUB_STATE/$unit.port")"
          echo "$port" >> "$STUB_STATE/healthy_ports"
          ;;
      esac
    fi
    ;;
  is-active)
    exit 0
    ;;
esac
exit 0
"""

CURL_STUB = r"""#!/bin/bash
# Stub curl: succeeds only for ports the systemctl stub marked healthy.
url="${@: -1}"
port="$(echo "$url" | sed 's|.*127.0.0.1:||; s|/.*||')"
echo "curl $port" >> "$STUB_LOG"
if grep -qx "$port" "$STUB_STATE/healthy_ports" 2>/dev/null; then
  exit 0
fi
exit 7
"""

SUDO_STUB = "#!/bin/bash\nexec \"$@\"\n"
SLEEP_STUB = "#!/bin/bash\nexit 0\n"

PORTS = {
    "Inference.service": 8001,
    "Memora.service": 8002,
    "Stratex.service": 8003,
    "IntelX.service": 8005,
    "Futuris.service": 8004,
    "Forge.service": 8006,
    "FRIDAY.service": 10000,
}
INITIAL_PIDS = {"Stratex-Daemon.service": 4242, "FRIDAY-Voice.service": 777}


def _staggered_block() -> str:
    """Extract the marked STAGGERED RESTART block, dedented (repo convention)."""
    lines = WORKFLOW.read_text(encoding="utf-8").splitlines()
    blocks: list[str] = []
    current: list[str] | None = None
    indent = ""
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(BEGIN):
            indent = line[: len(line) - len(line.lstrip())]
            current = [line]
            continue
        if current is not None:
            current.append(line)
            if stripped.startswith(END):
                blocks.append(
                    "\n".join(
                        ln[len(indent):] if ln.startswith(indent) else ln
                        for ln in current
                    )
                )
                current = None
    assert len(blocks) == 1, (
        f"expected exactly one STAGGERED RESTART block (Server 1), found {len(blocks)}"
    )
    return blocks[0]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def _run_block(
    tmp_path: Path,
    *,
    changed_agents: str,
    force_all: str,
    fail_unit: str = "",
) -> tuple[subprocess.CompletedProcess, list[str]]:
    """Execute the extracted block against the stubs in a fixture checkout."""
    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    _write_executable(stub_bin / "systemctl", SYSTEMCTL_STUB)
    _write_executable(stub_bin / "curl", CURL_STUB)
    _write_executable(stub_bin / "sudo", SUDO_STUB)
    _write_executable(stub_bin / "sleep", SLEEP_STUB)

    state = tmp_path / "state"
    state.mkdir()
    (state / "healthy_ports").write_text("", encoding="utf-8")
    for unit in EXPECTED_ORDER:
        pid = INITIAL_PIDS.get(unit, 1000)
        (state / f"{unit}.mainpid").write_text(f"{pid}\n", encoding="utf-8")
    for unit, port in PORTS.items():
        (state / f"{unit}.port").write_text(f"{port}\n", encoding="utf-8")

    checkout = tmp_path / "checkout"
    (checkout / "Stratex" / "state").mkdir(parents=True)
    (checkout / "Stratex" / "state" / "daemon_heartbeat.json").write_text(
        '{\n  "pid": 4242,\n  "updated_at": 1000.5\n}\n', encoding="utf-8"
    )
    (checkout / "FRIDAY" / "data").mkdir(parents=True)
    (checkout / "FRIDAY" / "data" / "voice_worker_status.json").write_text(
        '{\n  "state": "registered",\n  "pid": 777\n}\n', encoding="utf-8"
    )

    log = tmp_path / "stub.log"
    log.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "PATH": f"{stub_bin}:{os.environ['PATH']}",
        "STUB_LOG": str(log),
        "STUB_STATE": str(state),
        "STUB_FAIL_UNIT": fail_unit,
        "CHANGED_AGENTS": changed_agents,
        "DEPLOY_FORCE_ALL": force_all,
    }
    program = "set -euo pipefail\n" + _staggered_block()
    result = subprocess.run(
        ["bash", "-c", program],
        cwd=checkout,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result, log.read_text(encoding="utf-8").splitlines()


def _restarts(log_lines: list[str]) -> list[str]:
    return [
        line.split(" ", 1)[1]
        for line in log_lines
        if line.startswith("restarted ")
    ]


# -- structural pins -------------------------------------------------------


def test_block_is_extraction_clean() -> None:
    block = _staggered_block()
    assert "restart_and_gate" in block
    assert "${{" not in block, "the block must stay free of GitHub expressions"
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("sudo systemctl restart FRIDAY-Voice.service") == 1, (
        "FRIDAY-Voice must be restarted by exactly one explicit line"
    )


def test_order_table_pins_friday_last_voice_after_her() -> None:
    block = _staggered_block()
    positions = [block.index(f'"{name} ') for name in (
        "Inference", "Memora", "Stratex", "Stratex-Daemon", "IntelX",
        "Futuris", "Forge", "FRIDAY", "FRIDAY-Voice",
    )]
    assert positions == sorted(positions), "the S1 unit table is out of order"


# -- behavioural proof -----------------------------------------------------


def test_full_dispatch_restarts_in_order_each_gated(tmp_path: Path) -> None:
    result, log = _run_block(tmp_path, changed_agents="", force_all="1")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _restarts(log) == EXPECTED_ORDER
    # Every restart after the first is preceded by a gate probe of the
    # previous unit (curl for HTTP units, is-active for the file gates).
    restart_idx = [i for i, ln in enumerate(log) if ln.startswith("restarted ")]
    for prev, cur in zip(restart_idx, restart_idx[1:]):
        between = log[prev + 1:cur]
        assert any(
            ln.startswith("curl ") or "is-active" in ln for ln in between
        ), f"no gate probe between restarts at log lines {prev} and {cur}"
    healthy_lines = [
        ln for ln in result.stdout.splitlines() if ln.startswith("healthy: ")
    ]
    assert len(healthy_lines) == len(EXPECTED_ORDER), result.stdout


def test_gate_timeout_aborts_and_later_units_never_restart(
    tmp_path: Path,
) -> None:
    result, log = _run_block(
        tmp_path,
        changed_agents="",
        force_all="1",
        fail_unit="Memora.service",
    )
    output = result.stdout + result.stderr
    assert result.returncode == 1
    assert "ABORTED at Memora.service" in output
    assert "workflow_dispatch" in output, (
        "the abort message must mandate the workflow_dispatch recovery"
    )
    assert _restarts(log) == ["Inference.service", "Memora.service"], (
        "units after the failed gate must never be restarted"
    )


def test_single_agent_change_restarts_only_that_agent(tmp_path: Path) -> None:
    result, log = _run_block(tmp_path, changed_agents="Futuris", force_all="0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _restarts(log) == ["Futuris.service"]


def test_friday_change_restarts_friday_and_voice_once(tmp_path: Path) -> None:
    result, log = _run_block(tmp_path, changed_agents="FRIDAY", force_all="0")
    assert result.returncode == 0, result.stdout + result.stderr
    assert _restarts(log) == ["FRIDAY.service", "FRIDAY-Voice.service"]
