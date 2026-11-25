"""TASK-FRG-022 live proof driver — run the adopted workflow passes for real.

Reproducible: PYTHONPATH=Forge python3 Forge/scripts/frg022_live_proof.py
(run from the repo root). Stdlib only, plus pytest for the real test run.

What it proves, live:
  1. DIRTY ship: a candidate whose change set plants a hardcoded key in
     client code, wires request input into a system prompt on a
     tool-enabled call, and claims more than it evidences. The
     orchestrator must BLOCK at the audit gate (and never reach the
     reality gate).
  2. CLEAN ship: the same shape with env-based secrets, the documented-safe
     user-role pattern, and a REAL passing test run (this script executes
     pytest on Forge/tests/test_frg022_workflow_passes.py and feeds the
     real counts into the Reality Checker). The orchestrator must certify
     READY_TO_SHIP.
  3. RESCAN: fix the dirty file (key removed, secret moved to env) and
     re-audit — the finding must show as RESOLVED, nothing new.

Secret hygiene: every planted value is built at runtime from short
fragments, so no key-shaped literal is committed anywhere. The values
are synthetic fixtures, never real credentials. The auditor's own output
never prints a raw value (previews are names only); this driver asserts
that on the dirty run.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from workflow_passes.orchestrator import AgentsOrchestrator  # noqa: E402
from workflow_passes.reality_checker import EvidenceItem, ShipCandidate  # noqa: E402

TEST_FILE = "Forge/tests/test_frg022_workflow_passes.py"


def _k(*parts: str) -> str:
    """Build a synthetic secret-shaped value from fragments at runtime."""
    return "".join(parts)


def _run_real_tests() -> tuple[bool, int, int, str]:
    """Execute the real test suite and return (passed, n_passed, n_total, tail).

    No explicit -q: Forge/pyproject.toml already sets addopts "-ra -q",
    and a second -q would make pytest -qq, which suppresses the summary
    line this parser reads.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = "Forge"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", TEST_FILE],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[2],
        env=env,
    )
    tail = (result.stdout.strip().splitlines() or ["<no pytest output>"])[-1]
    match = re.search(r"(\d+) passed", tail)
    passed = result.returncode == 0 and match is not None
    total = int(match.group(1)) if match else 0
    return passed, total, total, tail


def _dirty_files() -> dict[str, str]:
    key = _k("sk-", "live-", "a1b2c3d4e5f6a7b8")
    return {
        "app/page.tsx": (
            '"use client";\n'
            f"const openai = new OpenAI({{ apiKey: \"{key}\" }});\n"
        ),
        "app/api/agent/route.ts": (
            "export async function POST(req) {\n"
            "  const { instruction } = await req.json();\n"
            "  await openai.chat.completions.create({\n"
            '    model: "gpt-4o",\n'
            '    messages: [{ role: "system", content: `You are support. ${instruction}` }],\n'
            '    tools: [{ type: "function", function: { name: "issueRefund" } }],\n'
            "  });\n"
            "}\n"
        ),
    }


def _clean_files() -> dict[str, str]:
    return {
        "app/page.tsx": (
            '"use client";\n'
            "const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });\n"
        ),
        "app/api/agent/route.ts": (
            "export async function POST(req) {\n"
            "  const { userMessage } = await req.json();\n"
            "  await openai.chat.completions.create({\n"
            '    model: "gpt-4o",\n'
            '    messages: [\n'
            '      { role: "system", content: "You are support." },\n'
            '      { role: "user", content: userMessage },\n'
            "    ],\n"
            "  });\n"
            "}\n"
        ),
    }


def main() -> int:
    orchestrator = AgentsOrchestrator()
    spec = [
        "Two named passes exist (Reality Checker, AI Code Auditor)",
        "Coordinated by an agents-orchestrator pattern",
    ]
    passed, n_passed, n_total, tail = _run_real_tests()
    print(f"REAL TEST RUN: {tail} (returncode {'0' if passed else 'non-zero'})")

    # --- 1. DIRTY ship: must BLOCK at the audit gate. ---
    dirty = ShipCandidate(
        name="frg022-dirty-ship",
        claim="Implemented the two workflow passes. Zero issues found, 98/100, production ready!",
        spec=spec,
        evidence=[],
        files=_dirty_files(),
        claimed_files=["app/page.tsx"],
        claimed_tests_passed=n_passed,
        claimed_tests_total=n_total,
    )
    dirty_verdict = orchestrator.run(
        dirty, dirty.files, client_reachable={"app/page.tsx"}
    )
    print("\n=== DIRTY SHIP ===")
    print(dirty_verdict.status_report())
    assert dirty_verdict.status == "BLOCKED", "dirty ship must be blocked"
    assert dirty_verdict.phase == "audit", "dirty ship must block at the audit gate"
    assert dirty_verdict.reality is None, "no advancement past a failed gate"
    # No raw planted value may appear in any output.
    planted = _k("sk-", "live-", "a1b2c3d4e5f6a7b8")
    assert planted not in dirty_verdict.status_report(), "secret value leaked into output"

    # --- 3. RESCAN: fix the dirty file, re-audit, finding must resolve. ---
    fixed = {
        "app/page.tsx": (
            '"use client";\n'
            "const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });\n"
        ),
        "app/api/agent/route.ts": _dirty_files()["app/api/agent/route.ts"],
    }
    before = orchestrator.auditor.audit(_dirty_files(), {"app/page.tsx"})
    after = orchestrator.auditor.audit(fixed, {"app/page.tsx"})
    diff = after.rescan_diff(before)
    print("\n=== RESCAN (key removed, secret moved to env) ===")
    print(f"resolved: {len(diff.resolved)} | still present: {len(diff.still_present)} "
          f"| newly introduced: {len(diff.newly_introduced)}")
    for finding in diff.still_present:
        print(f"  STILL PRESENT: {finding.render().splitlines()[0]}")
    assert len(diff.resolved) == 1, "the planted key finding must resolve"
    assert diff.newly_introduced == [], "the fix must introduce nothing new"

    # --- 2. CLEAN ship: must certify READY on the real test run. ---
    clean = ShipCandidate(
        name="frg022-clean-ship",
        claim="Implemented the two workflow passes with tests.",
        spec=spec,
        evidence=[
            EvidenceItem(
                kind="test_run",
                reference=f"pytest {TEST_FILE}",
                detail=tail,
                passed=passed,
                tests_passed=n_passed,
                tests_total=n_total,
                spec_refs=(0, 1),
            ),
            EvidenceItem(
                kind="file",
                reference="Forge/workflow_passes/reality_checker.py",
                detail="Reality Checker pass",
                spec_refs=(0,),
            ),
            EvidenceItem(
                kind="file",
                reference="Forge/workflow_passes/orchestrator.py",
                detail="Agents Orchestrator coordination",
                spec_refs=(1,),
            ),
        ],
        files=_clean_files(),
        claimed_files=["app/page.tsx"],
        claimed_tests_passed=n_passed,
        claimed_tests_total=n_total,
        revision_cycles=0,
    )
    clean_verdict = orchestrator.run(clean, clean.files, client_reachable={"app/page.tsx"})
    print("\n=== CLEAN SHIP ===")
    print(clean_verdict.status_report())
    assert clean_verdict.status == "READY_TO_SHIP", "clean ship must certify"
    assert clean_verdict.reality is not None and clean_verdict.reality.verdict == "READY"

    print("\nLIVE PROOF: DIRTY blocked at audit, RESCAN resolved 1/1, CLEAN certified READY.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
