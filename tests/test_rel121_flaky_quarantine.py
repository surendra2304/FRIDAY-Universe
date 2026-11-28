"""TASK-REL-121: flaky-test quarantine enforcement.

The list (docs/collaboration/FLAKY_TEST_QUARANTINE.md + .yaml) names each
flaky test with owner + expiry; quarantined nodeids are skipped in PR CI
and run on the nightly gate. These tests pin the loader, the expiry
rule, the PR-skip matching, and the list/workflow wiring.
"""

import datetime
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_module():
    path = os.path.join(ROOT, "scripts", "flaky_quarantine.py")
    spec = importlib.util.spec_from_file_location("flaky_quarantine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fq = _load_module()


def test_list_validates_with_owner_and_expiry():
    entries = fq.load_entries()
    assert entries, "quarantine list must not be empty"
    assert fq.validate_entries(entries) == []
    for entry in entries:
        assert entry["owner"]
        assert entry["expiry"]
        assert entry["nodeids"]


def test_first_entry_is_fleet_layout_sigabrt():
    entries = fq.load_entries()
    first = entries[0]
    assert "validate-monorepo" in first["test"]
    assert "SIGABRT" in first["signature"]
    assert first["owner"] == "muse_4"
    assert first["expiry"] == "2026-12-05"
    assert first["nodeids"] == [
        "tests/test_e2e_real_repo_integration.py::TestStratexE2E"
    ]


def test_fallback_parser_matches_yaml():
    assert fq.load_entries(force_fallback=True) == fq.load_entries()


def test_expired_quarantine_fails_validation():
    entries = fq.load_entries()
    errors = fq.validate_entries(entries, today=datetime.date(2026, 12, 6))
    assert any("expired" in e for e in errors)


def test_missing_owner_fails_validation():
    entries = [dict(fq.load_entries()[0], owner="")]
    errors = fq.validate_entries(entries)
    assert any("owner" in e for e in errors)


def test_matching_covers_class_nodeids_only():
    entries = fq.load_entries()
    hit = fq.matching_entry(
        "tests/test_e2e_real_repo_integration.py::TestStratexE2E::test_vibe_alphas",
        entries,
    )
    assert hit is not None and hit["owner"] == "muse_4"
    # The REL-070 regression tests guard the fix; they are not quarantined.
    assert (
        fq.matching_entry(
            "tests/test_rel070_shutdown_threads.py::TestRel070ShutdownThreads"
            "::test_keeper_stops_and_thread_dies",
            entries,
        )
        is None
    )


def test_mode_pr_only_for_pull_request():
    assert fq.current_mode({"GITHUB_EVENT_NAME": "pull_request"}) == "pr"
    assert fq.current_mode({"GITHUB_EVENT_NAME": "schedule"}) == "nightly"
    assert fq.current_mode({"GITHUB_EVENT_NAME": "push"}) == "local"
    assert (
        fq.current_mode(
            {"GITHUB_EVENT_NAME": "push", "FRIDAY_FLAKY_QUARANTINE_MODE": "pr"}
        )
        == "pr"
    )


def test_markdown_list_first_entry_and_rules():
    path = os.path.join(ROOT, "docs", "collaboration", "FLAKY_TEST_QUARANTINE.md")
    text = open(path, encoding="utf-8").read()
    assert "Fleet-layout SIGABRT flake (REL-070) — first entry" in text
    assert "**Owner:** muse_4" in text
    assert "**Expiry:** 2026-12-05" in text
    assert "skipped in PR CI" in text
    assert "nightly" in text


def test_nightly_workflow_runs_unskipped():
    path = os.path.join(ROOT, ".github", "workflows", "flaky-quarantine-nightly.yml")
    text = open(path, encoding="utf-8").read()
    assert "schedule:" in text
    assert "FRIDAY_FLAKY_QUARANTINE_MODE: nightly" in text
    assert "ci_gate_test_runner.py" in text
    assert "flaky_quarantine.py --check" in text
