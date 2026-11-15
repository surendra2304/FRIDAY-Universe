"""TASK-IG-VYR-02: the content-factory chain (IG corpus, DelZub4u74G).

Behaviour pinned here:

* research matches topics against the stocked, licence-carrying
  catalogues and reports an empty shelf rather than padding a run
  with unrelated footage;
* generate builds a long-form outline that is finance-advice
  screened — a tripping outline blocks the whole chain;
* repurpose slices one Short per long-form beat, each keeping its
  source clip (per-short provenance) and a title-strength score;
* schedule is a plan only (publish=False, unlisted);
* a full run renders and publishes nothing, and enqueues into the
  VYR-004 review queue as pending_review.

On clean main every test fails: app.services.content_factory does
not exist.
"""
from __future__ import annotations

from datetime import datetime

from app.services import content_factory as cf
from app.services import remix_flow as rf

CLIPS = [
    {"catalog_id": "L1-001", "title": "Apollo 11 Moon Landing Footage",
     "platform": "nasa", "creator": "NASA",
     "page_url": "https://images.nasa.gov/details/1",
     "license_name": "Public Domain", "rights_basis": "US Gov work",
     "duration_seconds": 300.0, "topic_tags": ["apollo", "moon"]},
    {"catalog_id": "L1-002", "title": "Deep Sea Volcano Eruption",
     "platform": "archive", "creator": "NOAA",
     "page_url": "https://archive.org/details/2",
     "license_name": "Public Domain", "rights_basis": "US Gov work",
     "duration_seconds": 120.0, "topic_tags": ["ocean", "volcano"]},
]


def test_research_matches_by_keyword_and_keeps_provenance():
    out = cf.research_stage("Apollo moon landing", "space_science",
                            clips=CLIPS)
    assert out["shelf_empty"] is False
    assert [c["catalog_id"] for c in out["candidates"]] == ["L1-001"]
    cand = out["candidates"][0]
    assert cand["license_name"] == "Public Domain"
    assert cand["page_url"]


def test_research_reports_empty_shelf_honestly():
    out = cf.research_stage("quantum knitting patterns", "space_science",
                            clips=CLIPS)
    assert out["shelf_empty"] is True
    assert out["candidates"] == []


def test_research_uses_stocked_catalogues_by_default():
    out = cf.research_stage("nebula", "space_science")
    assert out["candidates"], "lane-1 catalogue should match 'nebula'"
    assert all(c["license_name"] for c in out["candidates"])


def test_generate_and_repurpose_chain():
    research = cf.research_stage("Apollo moon landing", "space_science",
                                 clips=CLIPS)
    longform = cf.generate_stage("Apollo moon landing", "space_science",
                                 research)
    assert longform["blocked"] is False
    kinds = [s["kind"] for s in longform["sections"]]
    assert kinds[0] == "intro" and kinds[-1] == "outro"
    assert longform["word_count"] > 0 and longform["est_seconds"] > 0

    repurposed = cf.repurpose_stage(longform)
    assert len(repurposed["shorts"]) == 1  # one beat -> one short
    short = repurposed["shorts"][0]
    assert short["catalog_id"] == "L1-001"
    assert short["title_strength"] is not None
    assert short["status"] == "pending_review"
    assert short["publish"] is False


def test_full_run_is_plan_only_and_enqueues(tmp_path):
    start = datetime(2026, 11, 16, 9, 0, tzinfo=cf.IST)
    run = cf.run_factory("Apollo moon landing", "space_science", start,
                         clips=CLIPS)
    assert run["publishes_anything"] is False
    assert run["renders_anything"] is False
    assert run["schedule"], "the matched short should be scheduled"
    entry = run["schedule"][0]
    assert entry["publish"] is False and entry["privacy"] == "unlisted"

    queue = tmp_path / "q.jsonl"
    cf.enqueue_factory_run(run, queue)
    entries = rf.list_review_queue(queue)
    assert len(entries) == 1
    assert entries[0]["kind"] == "content_factory_run"
    assert entries[0]["status"] == "pending_review"


def test_unknown_lane_rejected():
    try:
        cf.research_stage("x", "movies", clips=CLIPS)
    except ValueError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")
