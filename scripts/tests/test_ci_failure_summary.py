#!/usr/bin/env python3
"""Tests for scripts/ci_failure_summary.py (TASK-REL-085).

Standalone runner -- no pytest dependency. Run from the repository root:

    python3 scripts/tests/test_ci_failure_summary.py

Cases:
  A. Passing command -> exit 0, no summary written, pass line printed.
  B. Failing command -> exit code preserved, summary names the failing
     check + step + exit code, offending lines (the command's failure
     output) are in the summary file, and the same summary is printed.
  C. Unstartable command -> exit 127, summary still names the check.
  D. Real validator, pristine registry -> the roster validator passes
     through the wrapper, exit 0 (proves the workflow wiring is safe).
  E. Real validator, broken registry -> duplicate evidence key in the
     board makes the roster validator fail through the wrapper; the
     summary names roster-validator and carries the validator's
     INVALID line as an offending line.
  F. Real fleet validator, broken layout -> a missing agent CI workflow
     makes validate_fleet.py fail through the wrapper; the summary
     names fleet-layout and carries the missing-workflow line.

Cases D-F build scratch trees from the live repo files, like
test_validate_collaboration.py does, so the fixtures are the real
validators plus one deliberate break.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / "scripts" / "ci_failure_summary.py"

REGISTRY_FILES = (
    "docs/MASTER_PLAN.md",
    "docs/handoff.md",
    "docs/ARCHITECTURE_AS_BUILT.md",
    "docs/collaboration/README.md",
    "docs/collaboration/TEAM_ROSTER.yaml",
    "docs/collaboration/WORK_BOARD.yaml",
    "docs/collaboration/FILE_OWNERSHIP.yaml",
    "docs/collaboration/ACTIVITY_LOG.md",
    "docs/collaboration/DECISIONS.md",
    "docs/collaboration/HANDOFFS.md",
    "docs/collaboration/TASK_TEMPLATE.yaml",
    "docs/collaboration/HANDOFF_TEMPLATE.md",
)

AGENTS = (
    "FRIDAY", "Inference", "Memora", "Stratex", "Forge",
    "Cortex", "Sentinel", "IntelX", "Futuris", "VyralX",
)

FAILURES = []


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print("[%s] %s%s" % (status, name, (" -- " + detail) if detail and not condition else ""))
    if not condition:
        FAILURES.append(name)


def run_wrapper(tmp, check_name, step, workflow, job, command, extra_env=None):
    """Run the wrapper with a temp summary file; return (proc, summary)."""
    tmp.mkdir(parents=True, exist_ok=True)
    summary_path = tmp / "step-summary.md"
    env = dict(os.environ)
    env["GITHUB_STEP_SUMMARY"] = str(summary_path)
    env["GITHUB_RUN_ID"] = "99999999999"
    env["GITHUB_REPOSITORY"] = "surendra2304/FRIDAY-Universe"
    env["GITHUB_WORKFLOW"] = "Test workflow"
    env["GITHUB_REF"] = "refs/pull/9999/merge"
    env["GITHUB_SHA"] = "deadbeef" * 5
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, str(WRAPPER),
         "--check", check_name, "--step", step,
         "--workflow", workflow, "--job", job,
         "--log", str(tmp / "wrapper.log"),
         "--"] + [str(c) for c in command],
        capture_output=True, text=True, env=env,
    )
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    return proc, summary


def build_registry_tree(tmp):
    """Copy the live registry files + roster validator into a scratch tree."""
    for rel in REGISTRY_FILES:
        src = ROOT / rel
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    validator_dst = tmp / "scripts" / "validate_collaboration.py"
    validator_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "scripts" / "validate_collaboration.py", validator_dst)
    return tmp


def build_fleet_tree(tmp):
    """Build a minimal valid monorepo layout + fleet validator in tmp."""
    for agent in AGENTS:
        ci = tmp / agent / ".github" / "workflows" / "ci.yml"
        ci.parent.mkdir(parents=True, exist_ok=True)
        ci.write_text("name: CI\non:\n  pull_request:\n  push:\n", encoding="utf-8")
        (tmp / agent / "tests").mkdir(parents=True, exist_ok=True)
    mirror = tmp / ".github" / "workflows" / "mirror-subrepos.yml"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text("name: Mirror\non:\n  workflow_dispatch:\n", encoding="utf-8")
    validator_dst = tmp / "scripts" / "validate_fleet.py"
    validator_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "scripts" / "validate_fleet.py", validator_dst)
    return tmp


def main():
    tmp = Path(tempfile.mkdtemp(prefix="rel085-"))

    # A. Passing command.
    proc, summary = run_wrapper(
        tmp / "a", "roster-validator", "Validate collaboration registry",
        ".github/workflows/collaboration-registry.yml",
        "Validate roster, task IDs and file ownership",
        [sys.executable, "-c", "print('all good')"])
    check("A exit 0 on pass", proc.returncode == 0, "exit=%s" % proc.returncode)
    check("A no summary on pass", summary == "", "summary=%r" % summary[:80])
    check("A pass line printed", "step passed (exit 0)" in proc.stdout)

    # B. Failing command.
    proc, summary = run_wrapper(
        tmp / "b", "fleet-layout", "Validate all ten agent roots",
        ".github/workflows/validate-monorepo.yml",
        "Validate fleet layout and mirror safety",
        [sys.executable, "-c",
         "import sys; print('offending line one'); print('Fleet validation failed with 1 problem(s):'); print('- missing agent directory: Nope'); sys.exit(3)"])
    check("B exit code preserved", proc.returncode == 3, "exit=%s" % proc.returncode)
    check("B summary names check", "## fleet-layout — step FAILED (exit 3)" in summary)
    check("B summary names step", "Failing step: Validate all ten agent roots" in summary)
    check("B summary names workflow", "validate-monorepo.yml" in summary)
    check("B offending lines in summary",
          "offending line one" in summary and "missing agent directory: Nope" in summary)
    check("B run id in summary", "99999999999" in summary)
    check("B banner printed", "fleet-layout step FAILED (exit 3)" in proc.stdout)

    # C. Unstartable command.
    proc, summary = run_wrapper(
        tmp / "c", "monorepo-policy", "Validate repository and workflow safety",
        ".github/workflows/monorepo-validation.yml",
        "Validate monorepo-only policy and workflow syntax",
        ["/nonexistent/binary-xyz"])
    check("C exit 127 on unstartable", proc.returncode == 127, "exit=%s" % proc.returncode)
    check("C summary names check", "## monorepo-policy — step FAILED (exit 127)" in summary)

    # D. Real roster validator, pristine registry -> pass-through exit 0.
    tree_d = build_registry_tree(tmp / "d")
    proc, summary = run_wrapper(
        tmp / "d-log", "roster-validator", "Validate collaboration registry",
        ".github/workflows/collaboration-registry.yml",
        "Validate roster, task IDs and file ownership",
        [sys.executable, str(tree_d / "scripts" / "validate_collaboration.py")])
    check("D pristine registry passes", proc.returncode == 0,
          "exit=%s stdout=%s" % (proc.returncode, proc.stdout[-300:]))
    check("D no summary on pass", summary == "")

    # E. Real roster validator, duplicate evidence key -> fail with INVALID line.
    tree_e = build_registry_tree(tmp / "e")
    board = tree_e / "docs" / "collaboration" / "WORK_BOARD.yaml"
    text = board.read_text(encoding="utf-8")
    marker = "    evidence:\n"
    idx = text.find(marker)
    assert idx != -1, "board has no evidence block to duplicate"
    broken = text[:idx] + marker + text[idx:]
    board.write_text(broken, encoding="utf-8")
    proc, summary = run_wrapper(
        tmp / "e-log", "roster-validator", "Validate collaboration registry",
        ".github/workflows/collaboration-registry.yml",
        "Validate roster, task IDs and file ownership",
        [sys.executable, str(tree_e / "scripts" / "validate_collaboration.py")])
    check("E broken registry fails", proc.returncode == 1, "exit=%s" % proc.returncode)
    check("E summary names check", "## roster-validator — step FAILED (exit 1)" in summary)
    check("E INVALID line is an offending line",
          "COLLABORATION REGISTRY INVALID" in summary, summary[-500:])

    # F. Real fleet validator, missing agent CI workflow -> fail with the line.
    tree_f = build_fleet_tree(tmp / "f")
    (tree_f / "Forge" / ".github" / "workflows" / "ci.yml").unlink()
    proc, summary = run_wrapper(
        tmp / "f-log", "fleet-layout", "Validate all ten agent roots and workflow syntax",
        ".github/workflows/validate-monorepo.yml",
        "Validate fleet layout and mirror safety",
        [sys.executable, str(tree_f / "scripts" / "validate_fleet.py")])
    check("F broken layout fails", proc.returncode == 1, "exit=%s" % proc.returncode)
    check("F summary names check", "## fleet-layout — step FAILED (exit 1)" in summary)
    check("F missing-workflow line is an offending line",
          "Forge: missing standalone CI workflow" in summary, summary[-500:])

    print()
    if FAILURES:
        print("REL-085 TESTS FAILED: %d case(s): %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("REL-085 TESTS PASSED: all cases green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
