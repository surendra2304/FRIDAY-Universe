"""
TASK-IG2-SEN-03 — Audit-finding baseline memorist tests.

PentAGI's memorist pattern, fleet-sized: baselines are small JSON
records, the diff is deterministic, and only deltas alert.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from Sentinel.app.services.audit_baseline import (  # noqa: E402
    BaselineMemorist,
    InMemoryBaselineStore,
    JsonBaselineStore,
    alerts_for,
    diff_findings,
)


def finding(fid, severity="HIGH", title=None):
    return {
        "finding_id": fid, "severity": severity,
        "title": title or fid, "detail": "",
    }


BASELINE = [
    finding("server-1/FRIDAY/health", "HIGH"),
    finding("server-1/Memora/headers", "LOW"),
    finding("server-2/Cortex/tls", "MEDIUM"),
]


def test_first_run_without_baseline_counts_everything_new():
    diff = diff_findings(None, BASELINE)
    assert diff.has_baseline is False
    assert len(diff.new) == 3 and diff.fixed == [] and diff.regressions == []


def test_identical_run_has_no_delta():
    diff = diff_findings(BASELINE, list(BASELINE))
    assert diff.new == [] and diff.fixed == [] and diff.regressions == []
    assert diff.unchanged_count == 3
    assert alerts_for(diff) == []


def test_new_fixed_and_regression_are_separated():
    current = [
        finding("server-1/FRIDAY/health", "HIGH"),          # unchanged
        finding("server-2/Cortex/tls", "CRITICAL"),          # regression
        finding("server-1/Forge/port-reachable", "HIGH"),    # new
        # Memora/headers gone → fixed
    ]
    diff = diff_findings(BASELINE, current)
    assert [r["finding_id"] for r in diff.new] == [
        "server-1/Forge/port-reachable"
    ]
    assert [r["finding_id"] for r in diff.fixed] == ["server-1/Memora/headers"]
    assert len(diff.regressions) == 1
    assert diff.regressions[0]["from_severity"] == "MEDIUM"
    assert diff.regressions[0]["severity"] == "CRITICAL"
    assert diff.unchanged_count == 1


def test_alerts_only_for_high_new_and_regressions():
    current = BASELINE + [
        finding("server-1/Forge/headers", "LOW"),            # new but LOW
        finding("server-1/Forge/port-reachable", "HIGH"),    # new HIGH
    ]
    diff = diff_findings(BASELINE, current)
    alerts = alerts_for(diff)
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "new_exposure"
    assert alerts[0]["finding_id"] == "server-1/Forge/port-reachable"


def test_severity_decrease_is_not_a_regression():
    current = [dict(BASELINE[0], severity="LOW")] + BASELINE[1:]
    diff = diff_findings(BASELINE, current)
    assert diff.regressions == []
    assert diff.unchanged_count == 3


def test_memorist_records_then_accepts_explicitly():
    memorist = BaselineMemorist(InMemoryBaselineStore())
    diff, _ = memorist.record_run(BASELINE)
    assert diff.has_baseline is False
    # Recording a run must NOT silently create a baseline.
    diff2, _ = memorist.record_run(BASELINE)
    assert diff2.has_baseline is False

    memorist.accept_baseline(BASELINE)
    diff3, alerts = memorist.record_run(BASELINE)
    assert diff3.has_baseline is True and diff3.unchanged_count == 3
    assert alerts == []

    worse = [dict(BASELINE[0], severity="CRITICAL")] + BASELINE[1:]
    diff4, alerts4 = memorist.record_run(worse)
    assert len(diff4.regressions) == 1 and len(alerts4) == 1


def test_finding_without_id_is_rejected():
    with pytest.raises(ValueError):
        diff_findings(None, [{"severity": "HIGH"}])


def test_json_store_round_trip(tmp_path):
    store = JsonBaselineStore(tmp_path / "baseline.json")
    assert store.load() is None
    memorist = BaselineMemorist(store)
    memorist.accept_baseline(BASELINE)
    reloaded = BaselineMemorist(
        JsonBaselineStore(tmp_path / "baseline.json")
    )
    diff, _ = reloaded.record_run(BASELINE)
    assert diff.has_baseline is True and diff.unchanged_count == 3
    raw = json.loads((tmp_path / "baseline.json").read_text())
    assert len(raw["findings"]) == 3 and "accepted_at" in raw


def test_diff_markdown_mentions_changes():
    current = BASELINE + [finding("server-1/Forge/port-reachable", "HIGH")]
    markdown = diff_findings(BASELINE, current).to_markdown()
    assert "NEW [HIGH] server-1/Forge/port-reachable" in markdown
    assert "Unchanged: 3" in markdown
