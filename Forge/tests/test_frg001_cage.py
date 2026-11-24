"""TASK-FRG-001: the idle-loop cage is real and stays real.

Pins the cage contract so a later edit cannot silently loosen it:

  * the cage unit's MemoryMax is strictly tighter than the
    production Forge unit's (180M), and its CPUQuota is bounded;
  * the cage runs the one-shot cycle driver, never the production
    app, and arms the loop ONLY inside the cage (the production unit
    does not set FORGE_IDLE_EXPERIMENTS, so the lifespan default
    stays off there);
  * the loop's own gates (kill switch, explicit-on lifespan gate,
    host-load gate, daily cap) are present in idle_loop.py;
  * the cycle driver refuses to run unless explicitly enabled.

Hermetic: stdlib + pytest only. No DB, no network, no server.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.improvement.idle_loop import IdleExperimentLoop

FORGE_ROOT = Path(__file__).resolve().parent.parent
CAGE_UNIT = FORGE_ROOT / "app/deployment/forge-idle-loop-cage.service"
PROD_UNIT = FORGE_ROOT / "app/deployment/forge.service"
DRIVER = FORGE_ROOT / "scripts/frg001_idle_cycle_once.py"
PROOF = FORGE_ROOT / "scripts/frg001_cage_proof.py"


def _load_proof():
    spec = importlib.util.spec_from_file_location("frg001_cage_proof", PROOF)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_proof_script_parses_sizes():
    proof = _load_proof()
    assert proof.parse_size("128M") == 128 * 1024 ** 2
    assert proof.parse_size("180M") == 180 * 1024 ** 2
    assert proof.parse_size("25%") is None
    assert proof.parse_size("") is None
    assert proof.parse_size("1G") == 1024 ** 3


def test_cage_unit_is_strictly_tighter_than_production():
    proof = _load_proof()
    cage = proof.parse_unit(CAGE_UNIT)
    prod = proof.parse_unit(PROD_UNIT)
    cage_mem = proof.parse_size(cage.get("Service", "MemoryMax"))
    prod_mem = proof.parse_size(prod.get("Service", "MemoryMax"))
    assert cage_mem is not None and prod_mem is not None
    assert cage_mem < prod_mem, f"cage {cage_mem} must be < prod {prod_mem}"
    quota = float(cage.get("Service", "CPUQuota").rstrip("%"))
    assert 0 < quota <= 50


def test_cage_runs_only_the_one_shot_driver():
    proof = _load_proof()
    cage = proof.parse_unit(CAGE_UNIT)
    exec_start = cage.get("Service", "ExecStart")
    assert "frg001_idle_cycle_once.py" in exec_start
    assert "uvicorn" not in exec_start
    assert "app.main" not in exec_start
    assert DRIVER.is_file()
    assert cage.get("Service", "Type") == "oneshot"
    assert not cage.has_section("Install"), "cage must be manual/transient"
    env = cage.get("Service", "Environment")
    assert "FORGE_IDLE_EXPERIMENTS=on" in env


def test_production_unit_does_not_arm_the_loop():
    proof = _load_proof()
    prod = proof.parse_unit(PROD_UNIT)
    assert "FORGE_IDLE_EXPERIMENTS" not in prod.get("Service", "Environment", fallback="")


def test_cage_hardening_present():
    proof = _load_proof()
    cage = proof.parse_unit(CAGE_UNIT)
    assert cage.get("Service", "PrivateTmp").lower() == "true"
    assert cage.get("Service", "ProtectSystem").lower() == "strict"
    assert cage.get("Service", "NoNewPrivileges").lower() == "true"
    assert "/opt/friday_universe/Forge/data" in cage.get("Service", "ReadWritePaths")


def test_loop_gates_present(monkeypatch):
    monkeypatch.setenv("FORGE_IDLE_EXPERIMENTS", "on")
    assert IdleExperimentLoop.lifespan_enabled() is True
    assert IdleExperimentLoop.experiments_enabled() is True
    monkeypatch.setenv("FORGE_IDLE_EXPERIMENTS", "off")
    assert IdleExperimentLoop.lifespan_enabled() is False
    assert IdleExperimentLoop.experiments_enabled() is False
    monkeypatch.delenv("FORGE_IDLE_EXPERIMENTS", raising=False)
    assert IdleExperimentLoop.lifespan_enabled() is False  # default off


def test_driver_refuses_without_explicit_flag(tmp_path):
    env = dict(os.environ)
    env.pop("FORGE_IDLE_EXPERIMENTS", None)
    proc = subprocess.run(
        [sys.executable, str(DRIVER), "--sandbox", "--data-dir", str(tmp_path)],
        capture_output=True, text=True, timeout=120, env=env,
        cwd=str(FORGE_ROOT),
    )
    assert proc.returncode == 2
    assert "FORGE_IDLE_EXPERIMENTS" in proc.stderr
