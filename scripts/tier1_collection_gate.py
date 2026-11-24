#!/usr/bin/env python3
"""Tier-1 collection gate (TASK-REL-088).

Checks that the CI test job in .github/workflows/friday-universe-ci.yml
collects the tier-1 test files of EVERY agent (10 agents, 21 files).

Unlike scripts/ci_test_collection_audit.py (REL-068), which is diff-scoped
and only checks test files the PR itself touches, this gate checks a FIXED
list: a PR that unwires a suite without touching a test file must fail.

Exit 0: all 21 tier-1 files are collected by a pytest invocation in the
test job. Exit 1: prints each missing file and exits 1.

Usage: python3 scripts/tier1_collection_gate.py [workflow.yml]
Defaults to .github/workflows/friday-universe-ci.yml from the repo root.
No third-party dependencies (line-based parse; PyYAML is not installed
in the CI step's environment).
"""
import re
import sys
from pathlib import Path

WORKFLOW = ".github/workflows/friday-universe-ci.yml"

# Fixed tier-1 list (repo-relative). Named suites where they exist; for the
# five agents with no tier-1-named suite, the health-contract /
# importability / resilience core files (see docs/collaboration evidence
# doc for TASK-REL-088; the 5 candidate sets were confirmed by local
# runs on current main).
TIER1_FILES = [
    # FRIDAY
    "FRIDAY/tests/test_tier1_resilience_and_contracts.py",
    "FRIDAY/tests/e2e/test_tier1_features.py",
    # Memora
    "Memora/tests/test_tier1_resilience_contracts.py",
    # Stratex
    "Stratex/tests/test_tier1_resilience_and_contracts.py",
    # Forge
    "Forge/tests/unit/test_tier1_resilience.py",
    "Forge/tests/unit/test_deep_upgrade_tier1.py",
    # Cortex (wired by REL-080)
    "Cortex/tests/unit/test_e2e_tier1.py",
    "Cortex/tests/e2e/test_e2e_tier1.py",
    # Inference (confirmed by local run)
    "Inference/tests/test_health_security.py",
    "Inference/tests/test_module_importability.py",
    "Inference/tests/test_monitoring_health_evidence.py",
    # Sentinel (confirmed by local run)
    "Sentinel/tests/security/test_health_readiness.py",
    "Sentinel/tests/security/test_health_durability_truthfulness.py",
    "Sentinel/tests/unit/test_foundation.py",
    # IntelX (confirmed by local run)
    "IntelX/tests/test_intelx_health_contract.py",
    "IntelX/tests/test_health.py",
    "IntelX/tests/test_healthz_liveness.py",
    # Futuris (confirmed by local run)
    "Futuris/tests/test_futuris_health_contract.py",
    "Futuris/tests/api/test_health.py",
    # VyralX (confirmed by local run)
    "VyralX/tests/test_recovery_and_readiness.py",
    "VyralX/tests/test_obs003_health_labelling.py",
]

JOB_RE = re.compile(r"^  test:\s*$")
NEXT_JOB_RE = re.compile(r"^  [A-Za-z0-9][A-Za-z0-9_-]*:\s*$")
STEP_RE = re.compile(r"^      - ")
WD_RE = re.compile(r"^\s+working-directory:\s*(\S+)\s*$")
PY_TOKEN_RE = re.compile(r"[^\s'\"\\]+\.py")


def test_job_lines(text):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if JOB_RE.match(line):
            start = i
            break
    if start is None:
        raise SystemExit("tier1_collection_gate: job 'test' not found")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if NEXT_JOB_RE.match(lines[j]):
            end = j
            break
    return lines[start:end]


def collected_files(job_lines):
    found = set()
    wd = None
    for line in job_lines:
        if STEP_RE.match(line):
            wd = None
        m = WD_RE.match(line)
        if m:
            wd = m.group(1)
            continue
        for tok in PY_TOKEN_RE.findall(line):
            tok = tok.split("::", 1)[0]
            if wd:
                tok = wd.rstrip("/") + "/" + tok
            found.add(tok)
    return found


def main(argv):
    path = Path(argv[1] if len(argv) > 1 else WORKFLOW)
    text = path.read_text()
    collected = collected_files(test_job_lines(text))
    missing = [f for f in TIER1_FILES if f not in collected]
    print(f"tier-1 files: {len(TIER1_FILES) - len(missing)}/{len(TIER1_FILES)} collected")
    if missing:
        for f in missing:
            print(f"MISSING: {f}")
        return 1
    print("OK: all tier-1 suites collected in the test job")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
