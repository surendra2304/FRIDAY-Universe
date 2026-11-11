#!/usr/bin/env python3
"""
coverage_gate.py — CI coverage gate for regression classes (checklist I5).

Problem it solves: "no untested regression classes." Plain pass/fail test runs
cannot tell you when a regression suite quietly disappears — a PR that deletes
or breaks the tests for, say, universe_orchestrator still goes green if the
other suites pass. This gate fails the build in exactly that case.

How it works:
  1. CI runs the seven non-HTTP engine suites with
     `--cov=<friday_core src> --cov-report=json:<report.json>`.
  2. This script loads that JSON plus tests/COVERAGE_MANIFEST.json.
  3. It enforces two invariants:
       a. TOTAL coverage of friday_core >= manifest total_floor_percent
          (ratchet: measured 16.67% on 2026-11-12, floor 16.0).
       b. Every module named in the manifest keeps coverage >= its per-module
          floor (baseline * 0.9, rounded down). A module at 0% or missing from
          the report is a hard fail — that means its regression tests are gone.
  4. Exit 0 = gate passed; exit 1 = gate failed with a violation list on stdout.

Usage:
    python3 scripts/coverage_gate.py [coverage.json]     (default: coverage_ci.json)

Raising the bar: re-measure with the same seven suites, then update the
manifest floors UPWARD only (never lower them without an owner-approved
incident note — that is the whole point of the gate).

Self-test: tests/test_coverage_gate.py exercises the manifest logic with
synthetic reports; keep it green.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "tests" / "COVERAGE_MANIFEST.json"
DEFAULT_REPORT = REPO_ROOT / "coverage_ci.json"


def load_manifest(path: Path = MANIFEST_PATH) -> dict:
    """Load and validate the coverage manifest. Raises on malformed input."""
    manifest = json.loads(path.read_text(encoding="utf-8"))
    for key in ("package_root", "total_floor_percent", "modules"):
        if key not in manifest:
            raise ValueError(f"coverage manifest missing key: {key}")
    if not isinstance(manifest["modules"], dict) or not manifest["modules"]:
        raise ValueError("coverage manifest 'modules' must be a non-empty object")
    return manifest


def _module_name(file_path: str, package_root: str) -> str | None:
    """Map a coverage-report file path to a manifest module name (or None)."""
    marker = package_root.strip("/") + "/"
    idx = file_path.find(marker)
    if idx == -1:
        return None
    return file_path[idx + len(marker):]


def evaluate(report: dict, manifest: dict) -> tuple[bool, list[str]]:
    """Pure gate logic: report dict + manifest dict -> (passed, violations)."""
    violations: list[str] = []
    files = report.get("files", {})
    if not files:
        return False, ["coverage report contains no files — did the test run produce data?"]

    totals = report.get("totals", {})
    total_pct = totals.get("percent_covered")
    if total_pct is None:
        return False, ["coverage report has no totals.percent_covered"]
    total_floor = float(manifest["total_floor_percent"])
    if total_pct < total_floor:
        violations.append(
            f"TOTAL coverage {total_pct:.2f}% is below the floor {total_floor:.1f}% "
            f"(regression erosion — new code without tests, or suites deleted)"
        )

    measured: dict[str, float] = {}
    for file_path, info in files.items():
        name = _module_name(file_path, manifest["package_root"])
        if name is not None:
            measured[name] = float(info["summary"]["percent_covered"])

    for module, floor in manifest["modules"].items():
        pct = measured.get(module)
        if pct is None:
            violations.append(
                f"{module}: MISSING from the coverage report entirely "
                f"(expected >= {floor:.1f}% floor) — its regression tests are gone"
            )
        elif pct < float(floor):
            violations.append(
                f"{module}: coverage {pct:.2f}% dropped below the floor "
                f"{float(floor):.1f}% — regression tests deleted, skipped or broken"
            )
    return (not violations), violations


def main(argv: list[str]) -> int:
    report_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_REPORT
    if not report_path.exists():
        print(f"[coverage-gate] FAIL: report not found: {report_path}")
        print("[coverage-gate] Run the CI suites with --cov-report=json first.")
        return 1
    try:
        manifest = load_manifest()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[coverage-gate] FAIL: bad manifest {MANIFEST_PATH}: {exc}")
        return 1
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[coverage-gate] FAIL: bad report {report_path}: {exc}")
        return 1

    passed, violations = evaluate(report, manifest)
    if passed:
        total_pct = report.get("totals", {}).get("percent_covered", 0.0)
        print(f"[coverage-gate] PASS: total {total_pct:.2f}% >= floor "
              f"{manifest['total_floor_percent']}%; all {len(manifest['modules'])} "
              f"regression modules at/above their floors")
        return 0
    print("[coverage-gate] FAIL — regression-class coverage violations:")
    for violation in violations:
        print(f"  - {violation}")
    print("[coverage-gate] Floors live in tests/COVERAGE_MANIFEST.json; raise them "
          "after re-measuring, never lower them silently.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
