"""Collection canary (TASK-REL-068).

This file exists to prove the contracts workflow actually collects a newly
shipped test file. It is listed in .github/workflows/owner-workflows.yml
(contracts job) and is also collected by validate-monorepo.yml's directory
run (`pytest -q tests`).

The first test is self-checking: if this file is ever dropped from the
workflow's pytest invocation, the test itself fails loudly wherever it is
collected, and scripts/ci_test_collection_audit.py fails the PR that
ships an uncollected test file. Delete this file only together with its
workflow listing.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "owner-workflows.yml"


def test_canary_is_listed_in_contracts_workflow():
    text = CONTRACTS_WORKFLOW.read_text(encoding="utf-8")
    assert Path(__file__).name in text, (
        "REL-068 canary %s is not listed in %s — the contracts workflow "
        "would never collect it" % (Path(__file__).name, CONTRACTS_WORKFLOW)
    )


def test_canary_runs():
    assert re.compile(r"rel068").search(Path(__file__).name)
