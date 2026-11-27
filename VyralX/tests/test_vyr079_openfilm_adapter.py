"""TASK-VYR-079 checkpoint 2: OpenFilm adapt leg (1 of 4).

Pins: a VyralX film built on the OpenFilm HTML-as-video pattern
validates end to end (frame(t) descriptors, footage assets, content,
durations); the failure cases — missing footage, bad frame(t),
content-less shot, unknown shot kind — FAIL the film with the culprit
named and issue no render command; rendering stays gated off-fleet.
On clean main this fails: app.services.openfilm_adapter does not exist.
"""
from __future__ import annotations

import pytest

from app.services import film_pipeline as fp
from app.services import openfilm_adapter as oa

SHOTS = [{"text": "a crater forms", "duration": 5.0,
          "kind": "page", "frame_fn": "fadeIn(t)"},
         {"text": "the floor drops", "duration": 6.0,
          "kind": "footage", "frame_fn": "zoomIn(t)",
          "asset": "footage/crater.mp4"},
         {"text": "the valley changes", "duration": 4.0,
          "kind": "stills", "frame_fn": "hold(t)",
          "asset": "stills/valley.jpg"}]

EXISTING = {"footage/crater.mp4", "stills/valley.jpg"}


def _adapt(shots=None, **kw):
    kw.setdefault("asset_exists", EXISTING.__contains__)
    return oa.adapt_openfilm_film(title="Crater", lane="space_science",
                                  shots=shots if shots is not None else SHOTS,
                                  **kw)


def test_openfilm_leg_adapts_end_to_end():
    r = _adapt(voice_track="voice.mp3")
    assert r["status"] == "adapted"
    assert r["openfilm_repo"] == "openfilm/openfilm" and r["license"] == "MIT"
    assert r["validation"]["ok"] is True
    assert r["validation"]["shots_checked"] == 3
    assert sorted(r["validation"]["assets_checked"]) == sorted(EXISTING)
    assert r["film"]["duration"] == 15.0
    assert r["film_html"].count('class="shot"') == 3
    assert "function frame(t)" in r["film_html"]
    # Rendering is gated off the fleet even for a valid film.
    assert r["render"]["available"] is False
    assert r["render"]["renders_in_service"] is False
    cmd = oa.adapt_openfilm_film(
        title="Crater", lane="space_science", shots=SHOTS,
        asset_exists=EXISTING.__contains__, host_role="owner_machine")
    assert cmd["status"] == "adapted"
    assert cmd["render"]["available"] is True
    assert cmd["render"]["argv"][-1] == "film.mp4"


def test_missing_footage_fails_and_issues_no_render():
    shots = [dict(SHOTS[0]),
             dict(SHOTS[1], asset="footage/gone.mp4"),
             dict(SHOTS[2])]
    r = _adapt(shots)
    assert r["status"] == "failed" and r["render"] is None
    assert r["validation"]["assets_missing"] == ["footage/gone.mp4"]
    assert any("gone.mp4" in e and "shot-02" in e
               for e in r["validation"]["errors"])


def test_bad_frame_fn_fails_with_shot_named():
    bad_name = [dict(SHOTS[0], frame_fn="spin(t)")]
    r = _adapt(bad_name)
    assert r["status"] == "failed"
    assert any("unknown frame(t)" in e and "shot-01" in e
               for e in r["validation"]["errors"])
    bad_syntax = [dict(SHOTS[0], frame_fn="fadeIn(t"),
                  dict(SHOTS[1]), dict(SHOTS[2])]
    r2 = _adapt(bad_syntax)
    assert r2["status"] == "failed"
    assert any("malformed frame(t)" in e for e in r2["validation"]["errors"])
    empty = [dict(SHOTS[0], frame_fn="")]
    assert _adapt(empty)["status"] == "failed"


def test_contentless_shot_and_unknown_kind_fail():
    no_content = [dict(SHOTS[0], text="", html="")]
    assert _adapt(no_content)["status"] == "failed"
    assert any("no content" in e
               for e in _adapt(no_content)["validation"]["errors"])
    bad_kind = [dict(SHOTS[0], kind="hologram")]
    r = _adapt(bad_kind)
    assert r["status"] == "failed"
    assert any("hologram" in e for e in r["validation"]["errors"])


def test_unchecked_assets_warn_but_do_not_claim_present():
    r = oa.adapt_openfilm_film(title="Crater", lane="space_science",
                               shots=SHOTS)
    assert r["status"] == "adapted"
    assert r["validation"]["assets_checked"] == []
    assert any("unchecked" in w for w in r["validation"]["warnings"])


def test_short_cap_still_enforced_by_the_pipeline():
    with pytest.raises(ValueError):
        oa.adapt_openfilm_film(title="x", lane="history",
                               shots=[{"text": "a", "duration": 70.0}],
                               asset_exists=EXISTING.__contains__)
    assert fp.MAX_SHORT_SECONDS == 59.0
