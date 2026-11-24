#!/usr/bin/env python3
"""TASK-FRG-001: prove the idle-loop cage is real before it ships.

Static checks (no service, no server, no production DB needed):

  1. the cage unit exists and parses as a systemd unit;
  2. its MemoryMax is strictly tighter than the production Forge
     unit's (forge.service: 180M) and its CPUQuota is bounded;
  3. its ExecStart runs the one-shot cycle driver — not uvicorn, not
     the production app — and that driver file exists in-repo;
  4. the loop is armed ONLY inside the cage (FORGE_IDLE_EXPERIMENTS=on
     in the cage unit; the production unit does not set it, so the
     lifespan default stays off there);
  5. the cage is a manual/transient one-shot (Type=oneshot, no
     [Install] section) with the hardening the fleet needs on a
     956 MB host (PrivateTmp, ProtectSystem=strict, NoNewPrivileges);
  6. the loop's own gates are present in idle_loop.py (kill switch,
     explicit-on lifespan gate, host-load gate, daily cap,
     run_one_cycle).

`systemd-analyze verify` runs too, when available, but only as
information: the /opt paths it checks exist on Server 1, not on the
machine that runs this script, so its complaints about missing
executables are expected here and are NOT a gate.

Exit 0 when every hard check passes, 1 otherwise. Prints one
PASS/FAIL line per check plus the informational verify output.
"""

from __future__ import annotations

import ast
import configparser
import re
import subprocess
import sys
from pathlib import Path

# Repo root = parent of Forge/ (this script is Forge/scripts/...).
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CAGE_UNIT = REPO_ROOT / "Forge/app/deployment/forge-idle-loop-cage.service"
PROD_UNIT = REPO_ROOT / "Forge/app/deployment/forge.service"
DRIVER = REPO_ROOT / "Forge/scripts/frg001_idle_cycle_once.py"
IDLE_LOOP = REPO_ROOT / "Forge/app/improvement/idle_loop.py"

_SIZE_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([KMGT]i?B?|B)?\s*$", re.IGNORECASE)
_MULT = {"": 1, "B": 1,
         "K": 1024, "KB": 1000, "KIB": 1024,
         "M": 1024 ** 2, "MB": 1000 ** 2, "MIB": 1024 ** 2,
         "G": 1024 ** 3, "GB": 1000 ** 3, "GIB": 1024 ** 3,
         "T": 1024 ** 4, "TB": 1000 ** 4, "TIB": 1024 ** 4}


def parse_size(text: str) -> int | None:
    """systemd memory size -> bytes, or None if unparseable."""
    m = _SIZE_RE.match(text or "")
    if not m:
        return None
    return int(float(m.group(1)) * _MULT[m.group(2).upper()])


def parse_unit(path: Path) -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str  # keep key case (systemd keys are case-sensitive)
    cp.read(path, encoding="utf-8")
    return cp


def main() -> int:
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'} {name}" + (f": {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    for label, path in (("cage unit", CAGE_UNIT), ("production unit", PROD_UNIT),
                        ("cycle driver", DRIVER), ("idle loop", IDLE_LOOP)):
        check(f"exists {label}", path.is_file(), str(path))

    if failures:
        return 1

    cage = parse_unit(CAGE_UNIT)
    prod = parse_unit(PROD_UNIT)

    cage_mem = parse_size(cage.get("Service", "MemoryMax", fallback=""))
    prod_mem = parse_size(prod.get("Service", "MemoryMax", fallback=""))
    check("cage MemoryMax parses", cage_mem is not None,
          f"MemoryMax={cage.get('Service', 'MemoryMax', fallback='?')}")
    check("production MemoryMax parses", prod_mem is not None,
          f"MemoryMax={prod.get('Service', 'MemoryMax', fallback='?')}")
    if cage_mem is not None and prod_mem is not None:
        check("cage MemoryMax strictly tighter than production",
              cage_mem < prod_mem, f"cage {cage_mem} B < prod {prod_mem} B")

    quota_raw = cage.get("Service", "CPUQuota", fallback="").strip().rstrip("%")
    try:
        quota = float(quota_raw)
    except ValueError:
        quota = None
    check("cage CPUQuota present and bounded (0 < q <= 50)",
          quota is not None and 0 < quota <= 50, f"CPUQuota={quota_raw}%")

    exec_start = cage.get("Service", "ExecStart", fallback="")
    check("cage ExecStart runs the one-shot cycle driver",
          "frg001_idle_cycle_once.py" in exec_start, exec_start)
    check("cage ExecStart is not the production app",
          "uvicorn" not in exec_start and "app.main" not in exec_start,
          exec_start)

    cage_env = cage.get("Service", "Environment", fallback="")
    check("cage arms the loop explicitly",
          "FORGE_IDLE_EXPERIMENTS=on" in cage_env, cage_env)
    prod_env = prod.get("Service", "Environment", fallback="")
    check("production unit does not arm the loop (default off)",
          "FORGE_IDLE_EXPERIMENTS" not in prod_env,
          "no FORGE_IDLE_EXPERIMENTS in forge.service")

    check("cage is a one-shot unit", cage.get("Service", "Type", fallback="") == "oneshot",
          f"Type={cage.get('Service', 'Type', fallback='?')}")
    check("cage is manual/transient (no [Install] section)",
          not cage.has_section("Install"),
          "no WantedBy — start on demand only")

    check("cage runs as the production user",
          cage.get("Service", "User", fallback="") == "ubuntu"
          and cage.get("Service", "Group", fallback="") == "ubuntu",
          f"User={cage.get('Service', 'User', fallback='?')}")
    check("cage works from the production Forge tree",
          cage.get("Service", "WorkingDirectory", fallback="")
          == "/opt/friday_universe/Forge",
          cage.get("Service", "WorkingDirectory", fallback="?"))

    for key in ("PrivateTmp", "ProtectSystem", "NoNewPrivileges"):
        check(f"cage hardening {key}",
              cage.get("Service", key, fallback="").lower() in ("true", "strict"),
              f"{key}={cage.get('Service', key, fallback='?')}")
    check("cage ledger path writable",
          "/opt/friday_universe/Forge/data" in
          cage.get("Service", "ReadWritePaths", fallback=""),
          f"ReadWritePaths={cage.get('Service', 'ReadWritePaths', fallback='?')}")

    tree = ast.parse(IDLE_LOOP.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
    for gate in ("LOAD_GATE_FRACTION", "DEFAULT_DAILY_CAP",
                 "experiments_enabled", "lifespan_enabled",
                 "start_if_enabled", "run_one_cycle", "host_load_refusal"):
        check(f"idle_loop.py defines {gate}", gate in names)

    # Informational only: /opt paths exist on Server 1, not here.
    verify = subprocess.run(
        ["systemd-analyze", "verify", str(CAGE_UNIT)],
        capture_output=True, text=True, timeout=60,
    )
    print("--- systemd-analyze verify (informational; /opt paths are Server 1) ---")
    print((verify.stdout or "") + (verify.stderr or "") or "(no output)")
    print(f"--- verify exit code: {verify.returncode} (not a gate here) ---")

    if failures:
        print(f"\n{len(failures)} hard check(s) failed: {', '.join(failures)}")
        return 1
    print("\nAll hard checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
