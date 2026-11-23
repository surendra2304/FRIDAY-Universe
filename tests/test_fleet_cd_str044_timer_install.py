"""TASK-STR-044 — Fleet CD S1 daily-reconciliation timer-install tests.

Fleet CD (`.github/workflows/deploy-monorepo.yml`, S1 job) installs the
systemd timer for the daily fill-ledger reconciliation job from the
repo units (`Stratex/deployment/friday-stratex-reconciliation.*`) and
enables it, so the schedule ships with the code. Install only: the
block never restarts the daemon and never touches trading state.

These tests extract that exact block from the workflow file and
EXECUTE it under bash with fake `sudo` / `systemctl` on PATH, so what
is tested is what deploys:

- Stratex change -> units copied to the unit dir, daemon-reload run,
  timer enabled + started;
- non-Stratex change -> nothing installed, systemctl never called;
- units absent from the checkout -> no-op, exit 0 (deploy proceeds);
- the timer fires daily and the service is a oneshot running the job
  script from the deployed checkout (unit-file pins).

Plus structural pins: exactly one timer-install block, confined to the
S1 job, placed after the Stratex-Daemon restart block.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "deploy-monorepo.yml"
SERVICE = ROOT / "Stratex" / "deployment" / "friday-stratex-reconciliation.service"
TIMER = ROOT / "Stratex" / "deployment" / "friday-stratex-reconciliation.timer"

BEGIN = "# BEGIN STR-044 TIMER INSTALL (TASK-STR-044)"
END = "# END STR-044 TIMER INSTALL (TASK-STR-044)"
S2_JOB = "deploy-server2:"

FAKE_SUDO = """#!/usr/bin/env bash
# Fake sudo: pass through to the real command (cp / systemctl fakes).
exec "$@"
"""

FAKE_SYSTEMCTL = """#!/usr/bin/env bash
# Fake systemctl: log every invocation; always succeed.
printf '%s\\n' "$*" >> "${SYSTEMCTL_LOG:-/dev/null}"
exit 0
"""


def _marked_blocks() -> list[str]:
    """Extract the executable bash of each marked timer-install block."""
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
    return blocks


def _fake_bin(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "sudo").write_text(FAKE_SUDO)
    (bindir / "systemctl").write_text(FAKE_SYSTEMCTL)
    for name in ("sudo", "systemctl"):
        (bindir / name).chmod(0o755)
    env = {"SYSTEMCTL_LOG": str(tmp_path / "systemctl.log")}
    return bindir, env


def _checkout(tmp_path: Path, *, with_units: bool = True) -> Path:
    checkout = tmp_path / "checkout"
    deploy_dir = checkout / "Stratex" / "deployment"
    deploy_dir.mkdir(parents=True)
    if with_units:
        (deploy_dir / SERVICE.name).write_text(SERVICE.read_text(encoding="utf-8"))
        (deploy_dir / TIMER.name).write_text(TIMER.read_text(encoding="utf-8"))
    return checkout


def _run_block(tmp_path: Path, checkout: Path, *, changed: str) -> subprocess.CompletedProcess:
    blocks = _marked_blocks()
    assert len(blocks) == 1, f"expected 1 timer-install block, found {len(blocks)}"
    script = blocks[0].replace("${{ github.event_name }}", "push")
    bindir, env = _fake_bin(tmp_path)
    unit_dir = tmp_path / "systemd"
    unit_dir.mkdir(exist_ok=True)
    full_env = dict(os.environ)
    full_env["PATH"] = f"{bindir}:{full_env['PATH']}"
    full_env.update(env)
    full_env["STR044_SYSTEMD_DIR"] = str(unit_dir)
    prelude = (
        "set -euo pipefail\n"
        f'CHANGED_AGENTS="{changed}"\n'
    )
    return subprocess.run(
        ["bash", "-c", prelude + script],
        capture_output=True, text=True, timeout=60, env=full_env,
        cwd=checkout,
    )


def _systemctl_calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "systemctl.log"
    if not log.exists():
        return []
    return [line for line in log.read_text().splitlines() if line.strip()]


# -- structural pins -------------------------------------------------------


def test_exactly_one_timer_install_block() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count(BEGIN) == 1
    assert text.count(END) == 1


def test_str044_confined_to_server1_job() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    s2_at = text.index(S2_JOB)
    assert "TASK-STR-044" not in text[: text.index("deploy-server1:")]
    assert text.index(BEGIN) < s2_at
    assert text.index(BEGIN) > text.index("deploy-server1:")


def test_timer_install_after_stratex_daemon_restart() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    restart_at = text.index('echo "=== Restarting Stratex-Daemon.service ==="')
    assert restart_at < text.index(BEGIN)


def test_unit_files_present_and_pinned() -> None:
    service = SERVICE.read_text(encoding="utf-8")
    assert "Type=oneshot" in service
    assert "scripts/daily_fill_ledger_reconciliation.py" in service
    assert "User=ubuntu" in service
    assert "/opt/friday_universe/Stratex/.env" in service
    assert "WantedBy=multi-user.target" in service
    timer = TIMER.read_text(encoding="utf-8")
    assert "OnCalendar=*-*-* 01:00:00" in timer
    assert "Persistent=true" in timer
    assert "Unit=friday-stratex-reconciliation.service" in timer
    assert "WantedBy=timers.target" in timer


# -- behavioural proof -------------------------------------------------------


def test_stratex_change_installs_and_enables_timer(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    result = _run_block(tmp_path, checkout, changed="Stratex")
    assert result.returncode == 0, result.stdout + result.stderr
    unit_dir = tmp_path / "systemd"
    assert (unit_dir / SERVICE.name).exists()
    assert (unit_dir / TIMER.name).exists()
    assert (unit_dir / SERVICE.name).read_text() == SERVICE.read_text()
    calls = _systemctl_calls(tmp_path)
    assert any(c == "daemon-reload" for c in calls), calls
    assert any(
        c == "enable --now friday-stratex-reconciliation.timer" for c in calls
    ), calls
    assert any(
        c.startswith("list-timers") and "friday-stratex-reconciliation.timer" in c
        for c in calls
    ), calls


def test_non_stratex_change_installs_nothing(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path)
    result = _run_block(tmp_path, checkout, changed="Memora")
    assert result.returncode == 0, result.stdout + result.stderr
    assert list((tmp_path / "systemd").iterdir()) == []
    assert _systemctl_calls(tmp_path) == []


def test_missing_units_is_a_noop(tmp_path: Path) -> None:
    checkout = _checkout(tmp_path, with_units=False)
    result = _run_block(tmp_path, checkout, changed="Stratex")
    assert result.returncode == 0, result.stdout + result.stderr
    assert list((tmp_path / "systemd").iterdir()) == []
    assert _systemctl_calls(tmp_path) == []


def test_workflow_dispatch_installs_timer(tmp_path: Path) -> None:
    blocks = _marked_blocks()
    script = blocks[0].replace("${{ github.event_name }}", "workflow_dispatch")
    bindir, env = _fake_bin(tmp_path)
    checkout = _checkout(tmp_path)
    unit_dir = tmp_path / "systemd"
    unit_dir.mkdir(exist_ok=True)
    full_env = dict(os.environ)
    full_env["PATH"] = f"{bindir}:{full_env['PATH']}"
    full_env.update(env)
    full_env["STR044_SYSTEMD_DIR"] = str(unit_dir)
    result = subprocess.run(
        ["bash", "-c", 'set -euo pipefail\nCHANGED_AGENTS="Memora"\n' + script],
        capture_output=True, text=True, timeout=60, env=full_env,
        cwd=checkout,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (unit_dir / TIMER.name).exists()
