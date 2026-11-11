"""
test_coverage_gate.py — tests for the CI coverage gate (checklist I5).

The gate itself must be tested: if evaluate() has a bug, the "no untested
regression classes" invariant silently stops being enforced. These tests use
synthetic coverage reports only — no network, no subprocess, no real coverage
run (fast, hermetic).
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from coverage_gate import evaluate, load_manifest  # noqa: E402

import pytest  # noqa: E402

PKG_ROOT = "FRIDAY/apps/core/src/friday_core"


def _manifest():
    """Fresh copy of the real manifest (source of truth — test it as shipped)."""
    return load_manifest()


def _report(modules: dict[str, float], total: float) -> dict:
    """Synthetic coverage JSON in the schema `coverage json` produces."""
    files = {}
    for name, pct in modules.items():
        covered = max(0, min(100, pct))
        files[f"{PKG_ROOT}/{name}"] = {
            "summary": {"percent_covered": covered, "covered_lines": 1, "num_statements": 1}
        }
    # one unrelated file so the report is realistic
    files["SomeWhere/else.py"] = {
        "summary": {"percent_covered": 0.0, "covered_lines": 0, "num_statements": 10}
    }
    return {"files": files, "totals": {"percent_covered": total}}


def test_real_manifest_is_valid_and_shipped():
    manifest = _manifest()
    assert manifest["total_floor_percent"] > 0
    assert len(manifest["modules"]) >= 5, "manifest should list the regression classes"
    for module, floor in manifest["modules"].items():
        assert module.endswith(".py"), f"bad module name: {module}"
        assert 0 < floor <= 100, f"floor out of range for {module}: {floor}"


def test_passes_when_every_module_meets_floor():
    manifest = _manifest()
    modules = {name: float(floor) + 5 for name, floor in manifest["modules"].items()}
    passed, violations = evaluate(_report(modules, manifest["total_floor_percent"] + 5), manifest)
    assert passed, f"unexpected violations: {violations}"


def test_fails_when_a_regression_module_is_missing():
    manifest = _manifest()
    # keep every floor satisfied except drop one module entirely from the report
    names = list(manifest["modules"])
    modules = {n: float(f) + 5 for n, f in manifest["modules"].items() if n != names[0]}
    passed, violations = evaluate(_report(modules, 99.0), manifest)
    assert not passed
    assert any(names[0] in v and "MISSING" in v for v in violations)


def test_fails_when_a_module_drops_below_its_floor():
    manifest = _manifest()
    names = list(manifest["modules"])
    offender = names[2]
    modules = {n: float(f) + 5 for n, f in manifest["modules"].items()}
    modules[offender] = float(manifest["modules"][offender]) - 0.5  # just under floor
    passed, violations = evaluate(_report(modules, 99.0), manifest)
    assert not passed
    assert any(offender in v and "dropped below the floor" in v for v in violations)


def test_fails_when_total_coverage_below_floor():
    manifest = _manifest()
    modules = {n: float(f) + 5 for n, f in manifest["modules"].items()}
    passed, violations = evaluate(_report(modules, manifest["total_floor_percent"] - 0.1), manifest)
    assert not passed
    assert any("TOTAL coverage" in v for v in violations)


def test_fails_on_empty_report():
    manifest = _manifest()
    passed, violations = evaluate({"files": {}, "totals": {}}, manifest)
    assert not passed
    assert violations


def test_module_name_matching_is_not_fooled_by_prefix_dirs():
    # a file that merely CONTAINS the package root string earlier in its path
    report = {
        "files": {
            f"/evil/{PKG_ROOT}X/backdoor.py": {
                "summary": {"percent_covered": 100.0, "covered_lines": 1, "num_statements": 1}
            }
        },
        "totals": {"percent_covered": 100.0},
    }
    manifest = _manifest()
    passed, violations = evaluate(report, manifest)
    assert not passed  # all real modules are missing -> must fail
    assert any("MISSING" in v for v in violations)
