"""TASK-VYR-082: the layered marketing architecture on channel_operator.

Behaviour pinned here (board record, vyralx package V-03 item
DeihbtONYtH, frame-verbatim):

* Layer 01 SIGNALS collects the six kinds; kinds with no VyralX source
  (website visitors, lead forms, sales calls) are reported unavailable
  with the reason, never synthesised; invalid ad records are listed
  with the reason, never silently dropped or repaired.
* Layer 02 SYSTEM OF RECORD assembles the stores the caller supplies;
  customers & deals and ad accounts have no VyralX store and are
  always unavailable; the ads/leads/sales domains carry row counts.
* Layer 03 THE BRAIN decides from measured views only: no metrics
  means no winner is named; next topics are capped at the weekly slot
  count and ordered by lane priority; bad candidates are skipped with
  the reason, never fatal.
* Layer 05 DEPARTMENTS runs the four that map to VyralX (content
  studio, publishing, market intelligence, reputation); the other four
  (paid ads, lead capture, sales response, nurture & retargeting) are
  listed as unmapped with the reason. Studio proposals and schedule
  entries are pending_review / approval-gated, publish=False,
  unlisted; distribution is planned, never executed.
* Layer 06 DATA & OBSERVABILITY reports the four funnel KPIs
  unavailable with the reason, never estimated; the agent activity log
  is the one measurable source KPI, one entry per layer step.
* Layer 07 HUMAN HANDOFF is the owner's unlisted review-first gate,
  unchanged: the plan is pending_review and enqueues into the VYR-004
  review queue as pending_review; nothing in it publishes.
* The board record names six layers and skips number 04 — Layer 04 is
  unnamed in the source record, so no fourth layer is invented; the
  registry carries the six named layers under their source numbers and
  the plan says so on its face.

On clean main every test fails: app.services.layered_marketing does
not exist.
"""
from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

from app.services import layered_marketing as lm
from app.services import channel_operator as co
from app.services import remix_flow as rf

START = datetime(2026, 11, 16, 9, 0, tzinfo=co.IST)  # a Monday


def _video(title, fmt, lane="space_science", views=None):
    v = {"title": title, "lane": lane, "format_name": fmt}
    if views is not None:
        v["metrics"] = {"views": views, "likes": views // 20,
                        "comments": views // 100}
    return v


def _ad(advertiser, hook, **extra):
    rec = {"advertiser": advertiser, "hook_text": hook,
           "platform": "instagram"}
    rec.update(extra)
    return rec


def _comments():
    return [
        {"comment_id": "1", "author": "a",
         "text": "How did you get this footage?"},
        {"comment_id": "2", "author": "b",
         "text": "sub4sub — check my channel, free money!"},
        {"comment_id": "3", "author": "c", "text": "Loved this one."},
    ]


def _week_input():
    return {
        "videos": [
            _video("A", "remix", "space_science", views=1000),
            _video("B", "remix", "space_science", views=3000),
            _video("C", "explainer", "history", views=500),
            _video("D", "explainer", "history"),
        ],
        "topics": [
            {"topic": "quantum computing", "lane": "tech_ai"},
            {"topic": "the Voyager probes", "lane": "space_science"},
            {"topic": "the Silk Road", "lane": "history"},
            {"topic": "the Apollo 11 landing", "lane": "space_science"},
            {"topic": "neural nets", "lane": "tech_ai"},
        ],
        "comments": _comments(),
        "signals": {
            "competitor_ads": [
                _ad("Acme", "What if you could see 3 new worlds "
                            "this week?",
                    engagement={"likes": 100, "shares": 20, "comments": 5},
                    days_running=30),
                _ad("Beta", "How did you miss these 5 space facts?",
                    engagement={"likes": 50},
                    first_seen="2026-11-01", last_seen="2026-11-10"),
                {"advertiser": "Gamma", "platform": "instagram"},
            ],
            "comments_dms": _comments(),
            "reviews_mentions": [
                {"title": "Voyager probe update", "channel_title": "Space",
                 "view_count": 5000, "like_count": 200,
                 "comment_count": 30,
                 "published_at": "2026-11-15T10:00:00+00:00"},
            ],
        },
        "record": {
            "content_calendar": [{"calendar_id": "c1", "name": "weekly"}],
            "asset_library": [{"file_id": "m1", "kind": "video"}],
        },
        "trend_candidates": [
            {"title": "Voyager probe update", "channel_title": "Space",
             "view_count": 5000, "like_count": 200, "comment_count": 30,
             "published_at": "2026-11-15T10:00:00+00:00"},
            {"title": "Old clip, no date", "channel_title": "Archive",
             "view_count": 900, "like_count": 10, "comment_count": 0},
        ],
    }


# --------------------------------------------------------------------------- #
# Layer 01 — SIGNALS
# --------------------------------------------------------------------------- #
def test_signals_collects_supplied_kinds():
    out = lm.collect_signals(_week_input()["signals"])
    assert out["layer"] == "01"
    ads = out["kinds"]["competitor_ads"]
    assert ads["available"] is True
    assert ads["count"] == 2  # the third record has no hook_text
    assert len(ads["invalid"]) == 1
    assert "hook_text" in ads["invalid"][0]["reason"]
    assert out["kinds"]["comments_dms"]["count"] == 3
    assert out["kinds"]["reviews_mentions"]["count"] == 1
    assert set(out["available_kinds"]) == {
        "competitor_ads", "comments_dms", "reviews_mentions"}


def test_signals_missing_kinds_reported_not_synthesised():
    out = lm.collect_signals({})
    for kind in ("website_visitors", "lead_forms", "sales_calls"):
        entry = out["kinds"][kind]
        assert entry["available"] is False
        assert entry["count"] == 0
        assert entry["items"] == []
        assert entry["note"]
    assert out["kinds"]["competitor_ads"]["available"] is False
    # Empty input: every kind is missing, in SIGNAL_KINDS order.
    assert out["missing_kinds"] == [
        "competitor_ads", "comments_dms", "website_visitors", "lead_forms",
        "reviews_mentions", "sales_calls"]


def test_signals_invalid_ad_record_listed_not_dropped():
    out = lm.collect_signals({"competitor_ads": [
        _ad("Acme", "A real hook", days_running=5),
        {"advertiser": "", "hook_text": "no advertiser"},
        {"advertiser": "Beta", "hook_text": "  "},
    ]})
    ads = out["kinds"]["competitor_ads"]
    assert ads["count"] == 1
    assert [i["index"] for i in ads["invalid"]] == [1, 2]
    assert all(i["reason"] for i in ads["invalid"])


# --------------------------------------------------------------------------- #
# Layer 02 — SYSTEM OF RECORD
# --------------------------------------------------------------------------- #
def test_record_assembles_supplied_stores():
    signals = lm.collect_signals(_week_input()["signals"])
    out = lm.build_system_of_record(_week_input()["record"], signals)
    assert out["layer"] == "02"
    assert out["stores"]["content_calendar"]["available"] is True
    assert out["stores"]["content_calendar"]["rows"] == 1
    assert out["stores"]["asset_library"]["available"] is True
    assert out["stores"]["customers_deals"]["available"] is False
    assert out["stores"]["ad_accounts"]["available"] is False
    assert set(out["available_stores"]) == {
        "content_calendar", "asset_library"}


def test_record_domains_ads_leads_sales():
    signals = lm.collect_signals(_week_input()["signals"])
    out = lm.build_system_of_record(_week_input()["record"], signals)
    assert out["domains"]["ads"]["available"] is True
    assert out["domains"]["ads"]["rows"] == 2
    assert out["domains"]["leads"]["available"] is False
    assert out["domains"]["sales"]["available"] is False
    empty = lm.build_system_of_record({}, lm.collect_signals({}))
    assert empty["domains"]["ads"]["available"] is False
    assert empty["domains"]["ads"]["rows"] == 0


# --------------------------------------------------------------------------- #
# Layer 03 — THE BRAIN / Growth Director
# --------------------------------------------------------------------------- #
def _decision():
    week = _week_input()
    signals = lm.collect_signals(week["signals"])
    record = lm.build_system_of_record(week["record"], signals)
    return lm.growth_director_decide(
        signals, record, week["videos"], week["topics"], now=START)


def test_brain_picks_winners_from_measured_views():
    out = _decision()
    assert out["layer"] == "03"
    assert out["winning_formats"] == ["remix", "explainer"]
    lanes = [p["lane"] for p in out["lane_priorities"]]
    assert lanes[0] == "space_science"  # mean 2000
    assert lanes[1] == "history"  # mean 500
    assert out["lane_priorities"][0]["views_mean"] == 2000.0


def test_brain_no_metrics_names_no_winner():
    week = _week_input()
    signals = lm.collect_signals(week["signals"])
    record = lm.build_system_of_record(week["record"], signals)
    out = lm.growth_director_decide(
        signals, record,
        [_video("A", "remix"), _video("B", "explainer")],
        week["topics"], now=START)
    assert out["winning_formats"] == []
    assert any("no winning format" in g for g in out["gaps"])
    assert out["analysis"]["metrics_available"] is False


def test_brain_next_topics_capped_to_slots_and_ordered():
    out = _decision()
    assert len(out["next_topics"]) == 3  # one per weekly slot
    assert [t["topic"] for t in out["next_topics"]] == [
        "the Voyager probes", "the Apollo 11 landing", "the Silk Road"]
    assert out["skipped_topics"] == []


def test_brain_skips_bad_topics_with_reasons():
    week = _week_input()
    signals = lm.collect_signals(week["signals"])
    record = lm.build_system_of_record(week["record"], signals)
    out = lm.growth_director_decide(
        signals, record, week["videos"],
        [{"topic": "good one", "lane": "history"},
         {"topic": "bad lane", "lane": "movies"},
         {"topic": "   ", "lane": "history"}],
        now=START)
    assert out["next_topics"] == [{"topic": "good one",
                                   "lane": "history"}]
    assert len(out["skipped_topics"]) == 2
    assert any("unknown lane" in s["reason"]
               for s in out["skipped_topics"])
    assert any("empty topic" in s["reason"]
               for s in out["skipped_topics"])


def test_brain_recommendations_continue_review_explore():
    out = _decision()
    by_action = {}
    for rec in out["recommendations"]:
        by_action.setdefault(rec["action"], []).append(rec["subject"])
    assert by_action["continue"] == ["remix"]
    assert "explainer" in by_action["review"]
    assert "tech_ai" in by_action["explore"]  # untried lane
    assert all(rec.get("evidence") for rec in out["recommendations"])


# --------------------------------------------------------------------------- #
# Layer 05 — DEPARTMENTS
# --------------------------------------------------------------------------- #
def _departments():
    week = _week_input()
    signals = lm.collect_signals(week["signals"])
    record = lm.build_system_of_record(week["record"], signals)
    decision = lm.growth_director_decide(
        signals, record, week["videos"], week["topics"], now=START)
    return lm.run_departments(decision, week, signals,
                              start=START, now=START)


def test_studio_proposals_gated():
    deps = _departments()
    studio = deps["mapped"]["content_studio"]
    assert len(studio["proposals"]) == 3  # one per chosen topic
    for p in studio["proposals"]:
        assert p["status"] == "pending_review"
        assert p["requires_approval"] is True
        assert p["publish"] is False


def test_publishing_schedule_is_plan_only():
    deps = _departments()
    pub = deps["mapped"]["publishing"]
    assert len(pub["schedule"]) == 3
    times = [e["planned_for"] for e in pub["schedule"]]
    assert times == sorted(times)
    assert times[0] == "2026-11-16T18:00:00+05:30"
    for entry in pub["schedule"]:
        assert entry["publish"] is False
        assert entry["privacy"] == "unlisted"
        assert entry["status"] == "pending_review"
    for dist in pub["distribution"]:
        assert dist["distribution_planned"] is True
        assert dist["distribution_executed"] is False
        assert set(dist["platforms"]) == {
            "youtube_shorts", "instagram_reels", "tiktok",
            "facebook_reels"}


def test_market_intelligence_brief_from_records():
    deps = _departments()
    intel = deps["mapped"]["market_intelligence"]
    assert intel["available"] is True
    brief = intel["brief"]
    assert brief["status"] == "draft_only"
    assert brief["publish"] is False
    assert len(brief["ranked"]) == 2
    assert brief["variant_guidance"]
    assert len(intel["trend_watch"]) == 2
    assert intel["trend_watch"][0]["trend_score"] >= \
        intel["trend_watch"][1]["trend_score"]


def test_market_intelligence_no_records_no_brief():
    out = lm.market_intelligence([], [], now=START)
    assert out["brief"] is None
    assert out["trend_watch"] == []
    assert out["note"]


def test_reputation_drafts_post_nothing():
    deps = _departments()
    rep = deps["mapped"]["reputation"]
    assert len(rep["drafts"]) == 3
    assert rep["drafts"][0]["action"] == "reply"
    assert rep["drafts"][1]["action"] == "hide"
    assert rep["drafts"][1]["reply"] is None
    assert rep["flagged_hide_suggested"] == 1
    for d in rep["drafts"]:
        assert d["posted"] is False
        assert d["requires_approval"] is True


def test_unmapped_departments_listed_with_reasons():
    deps = _departments()
    assert set(deps["unmapped"]) == {
        "paid_ads", "lead_capture", "sales_response",
        "nurture_retargeting"}
    assert all(deps["unmapped"].values())
    assert "content_studio" in deps["mapped"]
    assert "publishing" in deps["mapped"]


# --------------------------------------------------------------------------- #
# Layer 06 — DATA & OBSERVABILITY
# --------------------------------------------------------------------------- #
def _cycle():
    return lm.run_weekly_cycle(_week_input(), START)


def test_source_kpis_unmeasured_never_estimated():
    plan = _cycle()
    source = plan["layers"]["06"]["source_kpis"]
    for name in ("cost_per_lead", "speed_to_lead", "booked_and_paid",
                 "ad_to_customer"):
        assert source[name]["available"] is False
        assert source[name]["value"] is None
        assert source[name]["reason"]
    log = source["agent_activity_log"]
    assert log["available"] is True
    assert log["value"] == 6
    assert set(log["by_layer"]) == {"01", "02", "03", "05", "06", "07"}


def test_activity_log_one_entry_per_layer_step():
    plan = _cycle()
    log = plan["activity_log"]
    assert [e["layer"] for e in log] == ["01", "02", "03", "05", "06", "07"]
    assert all(e["at"] == START.isoformat() for e in log)
    assert all(e["action"] and e["detail"] for e in log)


def test_channel_kpis_match_cycle_counts():
    plan = _cycle()
    kpis = plan["layers"]["06"]["channel_kpis"]
    assert kpis["signals_available_kinds"] == 3
    assert kpis["record_available_stores"] == 2
    assert kpis["winning_formats"] == 2
    assert kpis["next_topics"] == 3
    assert kpis["proposals"] == 3
    assert kpis["schedule_entries"] == 3
    assert kpis["comment_drafts"] == 3
    assert kpis["flagged_hide_suggested"] == 1
    assert kpis["brief_available"] is True
    per_layer = plan["layers"]["06"]["per_layer"]
    assert set(per_layer) == {"01", "02", "03", "05", "06", "07"}


# --------------------------------------------------------------------------- #
# Layer 07 — HUMAN HANDOFF
# --------------------------------------------------------------------------- #
def test_handoff_gate_record():
    plan = _cycle()
    hand = plan["layers"]["07"]
    assert hand["gate"] == "owner_unlisted_review_first"
    assert hand["status"] == "pending_review"
    assert hand["requires_approval"] is True
    assert hand["publishes_anything"] is False
    assert hand["plan_kind"] == "layered_marketing_plan"


def test_enqueue_growth_plan_pending_review(tmp_path):
    plan = _cycle()
    queue = tmp_path / "queue.jsonl"
    lm.enqueue_growth_plan(plan, queue)
    entries = rf.list_review_queue(queue)
    assert len(entries) == 1
    assert entries[0]["kind"] == "layered_marketing_plan"
    assert entries[0]["status"] == "pending_review"
    assert entries[0]["publishes_anything"] is False
    assert entries[0]["plan"]["kind"] == "layered_marketing_plan"


# --------------------------------------------------------------------------- #
# Weekly cycle
# --------------------------------------------------------------------------- #
def test_weekly_cycle_end_to_end():
    plan = _cycle()
    assert plan["kind"] == "layered_marketing_plan"
    assert plan["version"] == lm.LAYERED_VERSION
    assert plan["week_start"] == START.isoformat()
    assert set(plan["layers"]) == {"01", "02", "03", "05", "06", "07"}
    assert plan["status"] == "pending_review"
    assert plan["requires_approval"] is True
    assert plan["publishes_anything"] is False
    growth = plan["growth_plan"]
    assert len(growth["topics"]) == 3
    assert len(growth["schedule"]) == 3
    assert len(growth["comment_drafts"]) == 3
    assert growth["recommendations"]
    assert growth["gaps"]  # missing signal kinds + stores are listed


def test_weekly_cycle_deterministic():
    first = lm.run_weekly_cycle(_week_input(), START)
    second = lm.run_weekly_cycle(_week_input(), START)
    assert first == second


def test_weekly_cycle_no_metrics_still_plans():
    week = _week_input()
    week["videos"] = [_video("A", "remix"), _video("B", "explainer")]
    plan = lm.run_weekly_cycle(week, START)
    assert plan["layers"]["03"]["winning_formats"] == []
    assert len(plan["growth_plan"]["schedule"]) == 3
    assert any("no winning format" in g
               for g in plan["growth_plan"]["gaps"])


def test_weekly_cycle_empty_input_honest():
    plan = lm.run_weekly_cycle({}, START)
    assert plan["layers"]["01"]["available_kinds"] == []
    assert plan["layers"]["02"]["available_stores"] == []
    assert plan["layers"]["03"]["winning_formats"] == []
    assert plan["layers"]["03"]["next_topics"] == []
    assert plan["growth_plan"]["proposals"] == []
    assert plan["growth_plan"]["schedule"] == []
    assert plan["status"] == "pending_review"
    assert plan["publishes_anything"] is False


def test_layer_registry_six_named_layers_layer04_absent():
    assert lm.LAYER_NUMBERS == ("01", "02", "03", "05", "06", "07")
    assert set(lm.LAYERS) == set(lm.LAYER_NUMBERS)
    assert lm.LAYERS["03"]["name"] == "THE BRAIN / GROWTH DIRECTOR"
    assert lm.LAYERS["07"]["name"] == "HUMAN HANDOFF"
    plan = _cycle()
    assert plan["layer_numbers"] == list(lm.LAYER_NUMBERS)
    assert plan["layer_04"]["status"] == "unnamed_in_source_record"
    assert plan["layer_04"]["name"] is None
    assert "04" not in plan["layers"]


def test_module_imports_no_publish_paths():
    path = (Path(__file__).resolve().parent.parent
            / "app" / "services" / "layered_marketing.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    banned_modules = ("youtube", "ytdlp", "multiplatform_publisher",
                      "edge_tts", "googleapiclient")
    banned_attrs = ("upload", "publish", "post_comment", "hide_comment")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            target = (node.module or "") + " " + " ".join(
                a.name for a in node.names)
            assert not any(b in target for b in banned_modules), target
        if isinstance(node, ast.Import):
            for a in node.names:
                assert not any(b in a.name for b in banned_modules), a.name
        if isinstance(node, ast.Attribute):
            assert node.attr not in banned_attrs, node.attr


def test_start_must_be_aware():
    try:
        lm.run_weekly_cycle(_week_input(), datetime(2026, 11, 16, 9, 0))
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for naive start")
