"""TASK-IG2-VYR-05: OpenFilm-pattern film pipeline.

Pins: one film.html with per-shot frame(t); lanes restricted; Shorts
cap enforced; studio edits (trim/move/restyle/retype) logged and
re-timed, film stays pending_review; rendering gated OFF the fleet.
On clean main this fails: app.services.film_pipeline does not exist.
"""
from __future__ import annotations

import pytest

from app.services import film_pipeline as fp

SHOTS = [{"text": "a crater forms", "duration": 5.0},
         {"text": "the floor drops", "duration": 6.0, "kind": "footage"},
         {"text": "the valley changes", "duration": 4.0}]


def _film(**kw):
    return fp.build_film(title="Crater", lane="space_science", shots=SHOTS, **kw)


def test_film_manifest_and_html():
    f = _film(voice_track="voice.mp3")
    assert f["duration"] == 15.0 and f["status"] == "pending_review"
    assert f["privacy"] == "unlisted" and f["publish"] is False
    assert [s["start"] for s in f["shots"]] == [0.0, 5.0, 11.0]
    assert {t["kind"] for t in f["tracks"]} >= {"video", "captions", "voice"}
    page = fp.render_film_html(f)
    assert page.count('class="shot"') == 3 and "function frame(t)" in page
    assert "a crater forms" in page


def test_lane_and_short_cap_enforced():
    with pytest.raises(ValueError):
        fp.build_film(title="x", lane="gaming", shots=SHOTS)
    with pytest.raises(ValueError):
        fp.build_film(title="x", lane="history",
                      shots=[{"text": "a", "duration": 70.0}])


def test_studio_edits_logged_and_retimed():
    f = _film()
    f2 = fp.apply_studio_edit(f, {"op": "trim", "shot_id": "shot-02", "duration": 3.0})
    assert f2["duration"] == 12.0 and f2["shots"][2]["start"] == 8.0
    f3 = fp.apply_studio_edit(f2, {"op": "move", "shot_id": "shot-03", "to_index": 0})
    assert f3["shots"][0]["shot_id"] == "shot-03" and f3["shots"][0]["start"] == 0.0
    f4 = fp.apply_studio_edit(f3, {"op": "retype", "shot_id": "shot-01", "text": "new line"})
    assert f4["shots"][1]["text"] == "new line"
    assert len(f4["edit_log"]) == 3 and f4["status"] == "pending_review"
    assert f["duration"] == 15.0  # original untouched
    with pytest.raises(ValueError):
        fp.apply_studio_edit(f, {"op": "explode", "shot_id": "shot-01"})


def test_render_gated_off_fleet():
    assert fp.render_gate(host_role="fleet_service")["allowed"] is False
    assert fp.render_command(_film(), host_role="fleet_service")["available"] is False
    cmd = fp.render_command(_film(), host_role="owner_machine")
    assert cmd["available"] is True and cmd["renders_in_service"] is False
