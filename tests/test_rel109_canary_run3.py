"""Run-3 collection canary (TASK-REL-109, 2026-11-28).

This file is the canary added by the REL-109 run-3 proof: it is listed
explicitly in the contracts job pytest invocation in
.github/workflows/owner-workflows.yml and is also collected by the
directory run (`pytest -q tests`) in monorepo-validation.yml.

The tests are self-checking collection inputs, stdlib-only:

- the contracts workflow still lists this file (dropping the listing
  fails this test wherever the file is collected);
- every tier-1 file named by scripts/tier1_collection_gate.py exists
  in the checkout (the fixed-list gate inputs are present);
- the diff-scoped collection guard script is present;
- both REL-068 canaries are still listed in the contracts workflow
  (run 3 re-proves the chain: dropping either earlier canary's
  listing fails this test too).

Delete this file only together with its workflow listing.
Evidence: docs/collaboration/TASK-REL-109-EVIDENCE.md.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "owner-workflows.yml"
TIER1_GATE = REPO_ROOT / "scripts" / "tier1_collection_gate.py"
COLLECTION_GUARD = REPO_ROOT / "scripts" / "ci_test_collection_audit.py"
PRIOR_CANARIES = [
    "tests/test_rel068_collection_canary.py",
    "tests/test_rel068_canary_base_proof.py",
]


def test_run3_canary_is_listed_in_contracts_workflow():
    text = CONTRACTS_WORKFLOW.read_text(encoding="utf-8")
    assert Path(__file__).name in text, (
        "REL-109 run-3 canary %s is not listed in %s — the contracts "
        "workflow would never collect it" % (Path(__file__).name, CONTRACTS_WORKFLOW)
    )


def test_tier1_gate_inputs_exist():
    gate_text = TIER1_GATE.read_text(encoding="utf-8")
    tier1_files = sorted(set(re.findall(r'"([^"]*test_[^"]*\.py)"', gate_text)))
    assert len(tier1_files) >= 21, tier1_files
    missing = [f for f in tier1_files if not (REPO_ROOT / f).is_file()]
    assert not missing, "tier-1 gate inputs missing from checkout: %s" % missing


def test_collection_guard_present():
    assert COLLECTION_GUARD.is_file(), "collection guard script missing"
    assert "EXCLUDED" in COLLECTION_GUARD.read_text(encoding="utf-8")


def test_prior_canaries_still_listed():
    text = CONTRACTS_WORKFLOW.read_text(encoding="utf-8")
    missing = [c for c in PRIOR_CANARIES if c not in text]
    assert not missing, (
        "REL-068 canary listing(s) dropped from %s: %s — run 3 re-proves "
        "the chain, it does not replace it" % (CONTRACTS_WORKFLOW, missing)
    )
