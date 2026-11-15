"""TASK-IG-VYR-06: previs / storyboarding (IG corpus, MGPREVIS pattern).

Behaviour pinned here:

* a script becomes one shot per narration beat, with duration
  estimates that sum to the storyboard total;
* a beat that matches a stocked catalogue clip carries the clip's
  id and licence; a beat with no match is ``unresolved`` and the
  storyboard declares itself incomplete — gaps are surfaced before
  a render, never papered over;
* caller-declared generated/owner beats get their strategies (and
  generated footage is marked intake-only);
* the contact-sheet plan uses placeholders for non-catalogue
  shots — it never implies footage exists where it does not;
* storyboards enqueue into the VYR-004 review queue as
  pending_review.

On clean main every test fails: app.services.previs does not exist.
"""
from __future__ import annotations

from app.services import previs
from app.services import remix_flow as rf

CLIPS = [
    {"catalog_id": "L1-100", "title": "Nebula Star Formation Timelapse",
     "license_name": "Public Domain",
     "page_url": "https://images.nasa.gov/details/100",
     "topic_tags": ["nebula", "star-formation"]},
    {"catalog_id": "L1-101", "title": "Pulsar Neutron Star Animation",
     "license_name": "Public Domain",
     "page_url": "https://images.nasa.gov/details/101",
     "topic_tags": ["pulsar", "neutron-star"]},
]

SCRIPT = ("A nebula is where stars are born, in clouds of gas and dust. "
          "A pulsar spins hundreds of times every second. "
          "Nobody has ever photographed the event horizon directly.")


def test_storyboard_matches_and_marks_gaps():
    sb = previs.build_storyboard(SCRIPT, "space_science", clips=CLIPS)
    assert len(sb["shots"]) == 3
    strategies = [s["visual"]["strategy"] for s in sb["shots"]]
    assert strategies == ["catalogue", "catalogue", "unresolved"]
    assert sb["shots"][0]["visual"]["catalog_id"] == "L1-100"
    assert sb["shots"][0]["visual"]["license_name"] == "Public Domain"
    assert sb["complete"] is False
    assert sb["summary"]["unresolved_shots"] == [3]
    assert sb["status"] == "pending_review"


def test_durations_sum_and_generated_owner_strategies():
    sb = previs.build_storyboard(
        SCRIPT, "space_science", clips=CLIPS,
        generated_beats={3}, owner_beats=set())
    assert sb["shots"][2]["visual"]["strategy"] == "generated_via_intake"
    assert "intake" in sb["shots"][2]["visual"]["note"]
    assert sb["complete"] is True
    total = round(sum(s["est_seconds"] for s in sb["shots"]), 1)
    assert sb["summary"]["est_seconds_total"] == total
    assert sb["summary"]["shots"] == 3


def test_contact_sheet_never_fakes_footage():
    sb = previs.build_storyboard(SCRIPT, "space_science", clips=CLIPS)
    plan = previs.contact_sheet_plan(sb)
    assert plan[0]["frame"]["source"] == "catalogue_clip"
    assert plan[2]["frame"]["source"] == "placeholder"
    assert "unresolved" in plan[2]["frame"]["label"]


def test_enqueue_lands_pending_review(tmp_path):
    sb = previs.build_storyboard(SCRIPT, "space_science", clips=CLIPS)
    queue = tmp_path / "q.jsonl"
    previs.enqueue_storyboard(sb, queue)
    entries = rf.list_review_queue(queue)
    assert len(entries) == 1
    assert entries[0]["kind"] == "previs_storyboard"
    assert entries[0]["status"] == "pending_review"


def test_empty_script_and_unknown_lane_rejected():
    for fn in (lambda: previs.build_storyboard("  ", "space_science"),
               lambda: previs.build_storyboard(SCRIPT, "movies")):
        try:
            fn()
        except ValueError:
            pass
        else:  # pragma: no cover
            raise AssertionError("expected ValueError")
