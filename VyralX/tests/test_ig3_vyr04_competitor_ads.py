"""TASK-IG3-VYR-04: competitor-ad pattern intelligence (B116+B126).

Behaviour pinned here:

* ranking rests on evidence the record itself carries —
  longevity x engagement, with the formula and the inputs
  printed on every ranked entry;
* an ad with no measured longevity or engagement ranks last
  with its missing evidence flagged — never a fabricated score;
* the pattern layer is the fleet's own hook heuristic
  (format_clone.score_hook) aggregated over the winners, and
  variant guidance is issued only for components the winners
  actually share;
* the module makes no platform calls and spends nothing —
  records are operator-supplied, the brief is draft-only;
* the router answers through the app pattern and app.main
  mounts it (AUDIT-2 production-caller standard).

On clean main every test fails: the module does not exist.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services import competitor_ads as ca

_MAIN = (Path(__file__).resolve().parent.parent / "app" / "main.py")


def _ad(advertiser, hook, **kw):
    base = {"advertiser": advertiser, "platform": "meta",
            "hook_text": hook}
    base.update(kw)
    return base


def test_record_validation_names_what_is_missing():
    with pytest.raises(ValueError, match="advertiser"):
        ca.normalise_ad({"hook_text": "Hello?"})
    with pytest.raises(ValueError, match="hook_text"):
        ca.normalise_ad({"advertiser": "Acme"})


def test_longevity_from_dates_days_running_or_none():
    ad = ca.normalise_ad(_ad("A", "Hook?",
                             first_seen="2026-01-01",
                             last_seen="2026-03-02"))
    assert ca.longevity_days(ad) == 60
    ad = ca.normalise_ad(_ad("A", "Hook?", days_running=12,
                             first_seen="2026-01-01",
                             last_seen="2026-03-02"))
    assert ca.longevity_days(ad) == 12  # explicit value wins
    ad = ca.normalise_ad(_ad("A", "Hook?"))
    assert ca.longevity_days(ad) is None
    with pytest.raises(ValueError, match="bad ISO date"):
        ca.longevity_days(ca.normalise_ad(
            _ad("A", "Hook?", first_seen="Jan 1", last_seen="Mar 2")))


def test_engagement_weights_and_missing_means_none():
    ad = ca.normalise_ad(_ad("A", "Hook?", engagement={
        "likes": 100, "shares": 10, "comments": 5}))
    assert ca.engagement_score(ad) == 100 + 2 * 10 + 3 * 5
    # Flat fields are accepted as the same evidence.
    ad = ca.normalise_ad(_ad("A", "Hook?", likes=7))
    assert ca.engagement_score(ad) == 7
    ad = ca.normalise_ad(_ad("A", "Hook?"))
    assert ca.engagement_score(ad) is None


def test_ranking_orders_by_evidence_and_flags_the_unmeasured():
    ranked = ca.rank_ads([
        _ad("Viral", "Why do 9 out of 10 dentists hide this?",
            days_running=200, engagement={"likes": 5000,
                                           "comments": 300,
                                           "shares": 800}),
        _ad("Steady", "Nobody tells you this about saving money",
            days_running=120, engagement={"likes": 900,
                                           "comments": 40,
                                           "shares": 60}),
        _ad("Ghost", "A hook with no numbers behind it"),
    ])
    assert [r["advertiser"] for r in ranked] == \
        ["Viral", "Steady", "Ghost"]
    assert [r["rank"] for r in ranked] == [1, 2, 3]
    viral = ranked[0]["evidence"]
    assert viral["longevity_days"] == 200
    assert viral["engagement_score"] == 5000 + 3 * 300 + 2 * 800
    assert viral["rank_score"] is not None
    ghost = ranked[-1]["evidence"]
    assert ghost["rank_score"] is None
    assert "unrankable" in ghost["basis"]


def test_pattern_extraction_aggregates_the_winners_hooks():
    brief = ca.pattern_brief([
        _ad("Viral", "Why do dentists hide this secret from you?",
            days_running=90, engagement={"likes": 5000}),
        _ad("Steady", "What nobody tells you about your 2 kidneys?",
            days_running=60, engagement={"likes": 3000}),
        _ad("Quiet", "A plain statement about toothpaste",
            days_running=10, engagement={"likes": 5}),
    ], top_n=2)
    patterns = brief["patterns"]
    assert patterns["ads_considered"] == 2
    assert patterns["component_rates"]["question_form"] == 1.0
    assert patterns["component_rates"]["curiosity_marker"] == 1.0
    assert patterns["mean_hook_score"] is not None
    assert "not a virality predictor" in patterns["basis"]
    guidance = " ".join(brief["variant_guidance"])
    assert "question" in guidance
    # The brief is honest about its own boundaries.
    assert brief["status"] == "draft_only"
    assert brief["publish"] is False
    assert brief["spend"] == "none"
    assert "no platform was queried" in brief["platform_calls"]
    assert brief["ig_sources"] == ["DeihbtONYtH", "DdbljkbH5b2"]


def test_brief_refuses_empty_input():
    with pytest.raises(ValueError):
        ca.pattern_brief([])


def test_router_answers_and_main_mounts_it():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(ca.router, prefix="/api/v1")
    client = TestClient(app)

    res = client.get("/api/v1/competitor-ads/policy")
    assert res.status_code == 200
    assert res.json()["platform_calls"] == "none"

    res = client.post("/api/v1/competitor-ads/brief", json={
        "ads": [_ad("Viral", "Why do 9 out of 10 dentists hide this?",
                    days_running=30, engagement={"likes": 100})]})
    assert res.status_code == 200
    assert res.json()["ranked"][0]["advertiser"] == "Viral"

    res = client.post("/api/v1/competitor-ads/brief",
                      json={"ads": [{"hook_text": "no advertiser"}]})
    assert res.status_code == 422

    main_src = _MAIN.read_text(encoding="utf-8")
    assert "from app.services.competitor_ads import router as " \
        "competitor_ads_router" in main_src
    assert "app.include_router(competitor_ads_router" in main_src
