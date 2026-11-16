"""TASK-IG2-VYR-10: the claude-ads-pattern creative audit.

Behaviour pinned here:

* every finding is pass/fail/unknown WITH evidence, reusing the
  packaging lints VyralX already enforces (no drift);
* measured performance is always ``unknown`` from creative copy
  alone, and NO composite score is emitted;
* paid spend is never created or audited — a spend claim surfaces
  as an unknown finding, not a score;
* revisions are drafts: the input creative is never mutated and
  nothing is applied;
* briefs state the real packaging constraints for a lane.

On clean main every test fails: app.services.creative_audit does
not exist.
"""
from __future__ import annotations

import copy

import pytest

from app.services import creative_audit as ca

GOOD = {
    "title": "Saturn V: 5 Engines, 150 Seconds",
    "thumbnail_text": "TALLEST EVER",
    "hook_line": "Nobody expected this rocket to fly?",
    "description": "The Saturn V remains the tallest rocket ever "
                   "flown successfully, and this is its story. #space",
    "tags": ["saturn v", "nasa", "space history"],
}


def test_good_creative_passes_copy_checks():
    audit = ca.audit_creative(GOOD, lane="space_science")
    by_check = {f["check"]: f for f in audit["findings"]}
    assert by_check["title_packaging"]["status"] == "pass"
    assert by_check["thumbnail_text"]["status"] == "pass"
    assert by_check["description_substance"]["status"] == "pass"
    assert by_check["tag_coverage"]["status"] == "pass"
    assert all(f["evidence"] for f in audit["findings"])


def test_bad_creative_fails_with_evidence():
    bad = {"title": "wow amazing stuff", "thumbnail_text": "",
           "hook_line": "hello there everyone today",
           "description": "short", "tags": []}
    audit = ca.audit_creative(bad, lane="space_science")
    assert audit["counts"]["fail"] >= 4
    by_check = {f["check"]: f for f in audit["findings"]}
    assert by_check["thumbnail_text"]["status"] == "fail"
    assert by_check["tag_coverage"]["status"] == "fail"


def test_performance_is_unknown_and_no_composite_score():
    audit = ca.audit_creative({**GOOD, "ctr": 0.12}, lane="space_science")
    by_check = {f["check"]: f for f in audit["findings"]}
    assert by_check["measured_performance"]["status"] == "unknown"
    assert audit["composite_score"] is None
    assert audit["counts"]["unknown"] >= 1


def test_paid_spend_is_never_created_or_scored():
    audit = ca.audit_creative({**GOOD, "paid_spend": 500},
                              lane="space_science")
    assert audit["paid_spend_created"] is False
    by_check = {f["check"]: f for f in audit["findings"]}
    assert by_check["paid_spend"]["status"] == "unknown"


def test_draft_revisions_mutate_nothing():
    creative = {"title": "wow", "thumbnail_text": "", "hook_line": "",
                "description": "", "tags": []}
    snapshot = copy.deepcopy(creative)
    draft = ca.draft_revisions(creative, lane="space_science")
    assert draft["status"] == "draft" and draft["applied"] is False
    assert draft["suggestions"]
    assert creative == snapshot
    assert ca.audit_creative(creative, lane="space_science")[
        "changes_applied"] is False


def test_brief_states_real_packaging_constraints():
    brief = ca.creative_brief("Saturn V", lane="space_science")
    assert brief["constraints"]["title_max_chars"] == 60
    assert brief["constraints"]["thumbnail_max_words"] == 4
    assert brief["constraints"]["privacy_if_published"] == "unlisted"
    assert brief["constraints"]["paid_spend"] is False
    with pytest.raises(ValueError):
        ca.creative_brief("X", lane="crypto_tips")
    with pytest.raises(ValueError):
        ca.creative_brief("  ")
