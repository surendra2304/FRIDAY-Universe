"""Backfill tests: lane inference, plan derivation reusing the autopilot's
own tag/category logic, verbatim title/description round-trip on apply,
honest thumbnail reporting, and a dry-run that performs zero writes."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "backfill_public_metadata.py"
_spec = importlib.util.spec_from_file_location("backfill_public_metadata", _SCRIPT)
backfill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(backfill)


def _current(**overrides):
    base = dict(
        id="dQw4w9WgXcQ",
        title="The $9,999,999 Michelin Restaurant 💀🧼 #Shorts",
        description="He dressed up for a 5-star dinner...\n\n#Shorts #Comedy",
        tags=[
            "comedy", "expensive restaurant", "fine dining", "funny",
            "luxury dinner", "michelin star", "parody", "relatable",
            "shorts", "soap bubbles", "trending shorts", "viral comedy",
            "viral shorts",
        ],
        categoryId="24",
        defaultLanguage="en",
        defaultAudioLanguage="",
        privacy="public",
    )
    base.update(overrides)
    return base


def test_infer_lane_comedy_from_own_tags():
    lane, signals = backfill.infer_lane(
        "The $9,999,999 Michelin Restaurant 💀🧼 #Shorts",
        ["comedy", "funny", "parody", "michelin star"],
    )
    assert lane == "COMEDY"
    assert "comedy" in signals and "parody" in signals


def test_infer_lane_sports_for_stunt():
    lane, signals = backfill.infer_lane(
        "Millimeter-Perfect Extreme Stunt That Shocked Millions 😱🔥 #Shorts",
        ["extreme", "insane", "one in a million", "precision", "shorts", "stunt", "viral"],
    )
    assert lane == "SPORTS"
    assert "stunt" in signals


def test_infer_lane_viral_fallback():
    lane, signals = backfill.infer_lane(
        "Wait For The Most Unexpected Plot Twist 😱🤯 #Shorts",
        ["plot twist", "shorts", "trending", "unexpected", "viral", "wait for it"],
    )
    assert lane == "VIRAL"
    assert signals == []


def test_plan_category_and_tags_reuse_autopilot_logic():
    plan = backfill.build_plan(_current())
    assert plan["lane"] == "COMEDY"
    assert plan["category"] == {"before": "24", "after": "23"}
    tags = plan["tags"]["after"]
    lowered = [t.casefold() for t in tags]
    # Channel anchors + lane base set from viral_remix._derive_tags.
    assert "shorts" in lowered and "vyralx" in lowered and "humor" in lowered
    # The video's own proven tags survive the re-derivation.
    assert "michelin star" in lowered and "soap bubbles" in lowered
    # YouTube headroom caps, same as the autopilot path.
    assert len(tags) <= 15
    assert sum(len(t) for t in tags) <= 450
    assert plan["metadata_changed"] is True


def test_plan_sports_gets_no_comedy_base_tags():
    plan = backfill.build_plan(_current(
        title="Millimeter-Perfect Extreme Stunt That Shocked Millions 😱🔥 #Shorts",
        tags=["extreme", "insane", "precision", "shorts", "stunt", "viral"],
        description="One inch to the left and this was a catastrophe.",
    ))
    assert plan["lane"] == "SPORTS"
    assert plan["category"]["after"] == "17"
    lowered = [t.casefold() for t in plan["tags"]["after"]]
    assert "comedy" not in lowered and "funny" not in lowered
    assert "skills" in lowered  # SPORTS base set


def test_plan_ignores_description_boilerplate_for_lane():
    # The subscribe boilerplate claims "comedy" on every manual-era
    # upload; a plot-twist clip must stay VIRAL (category 24).
    plan = backfill.build_plan(_current(
        title="Wait For The Most Unexpected Plot Twist 😱🤯 #Shorts",
        tags=["plot twist", "shorts", "trending", "unexpected", "viral", "wait for it"],
        description="Watch closely.\n\n🔔 SUBSCRIBE for daily unhinged comedy & viral moments!\n\n#Shorts #Comedy #Viral",
    ))
    assert plan["lane"] == "VIRAL"
    assert plan["category"] == {"before": "24", "after": "24"}


def test_plan_language_and_override():
    plan = backfill.build_plan(_current(), lane="VIRAL")
    assert plan["lane"] == "VIRAL" and plan["lane_source"] == "override"
    assert plan["category"]["after"] == "24"
    assert plan["defaultLanguage"] == {"before": "en", "after": "en"}
    assert plan["defaultAudioLanguage"] == {"before": "", "after": "en"}


def test_plan_thumbnail_honesty(tmp_path: Path):
    missing = backfill.build_plan(_current(), thumbnail_path=str(tmp_path / "nope.jpg"))
    assert missing["thumbnail"]["status"] == "missing_file"
    real = tmp_path / "thumb.jpg"
    real.write_bytes(b"\xff\xd8\xff" + b"x" * 10)
    ready = backfill.build_plan(_current(), thumbnail_path=str(real))
    assert ready["thumbnail"]["status"] == "ready"
    none = backfill.build_plan(_current())
    assert none["thumbnail"]["status"] == "none_provided"


def test_apply_roundtrips_title_and_description_verbatim():
    service = MagicMock()
    plan = backfill.build_plan(_current())
    result = backfill.apply_plan(service, plan)
    assert result["updated"] is True
    body = service.videos().update.call_args.kwargs["body"]
    assert body["id"] == "dQw4w9WgXcQ"
    assert body["snippet"]["title"] == plan["title"]
    assert body["snippet"]["description"] == plan["description"]
    assert body["snippet"]["categoryId"] == "23"
    assert body["snippet"]["tags"] == plan["tags"]["after"]


def test_apply_skips_update_when_nothing_changed():
    service = MagicMock()
    current = _current(
        categoryId="23", defaultAudioLanguage="en",
        tags=backfill.build_plan(_current())["tags"]["after"],
    )
    plan = backfill.build_plan(current)
    assert plan["metadata_changed"] is False
    result = backfill.apply_plan(service, plan)
    assert result["updated"] is False
    service.videos().update.assert_not_called()


def test_apply_thumbnail_only_when_file_ready(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    calls = []
    monkeypatch.setattr(backfill, "set_thumbnail", lambda vid, path: calls.append((vid, path)) or True)
    service = MagicMock()
    missing = backfill.build_plan(_current(), thumbnail_path=str(tmp_path / "nope.jpg"))
    backfill.apply_plan(service, missing)
    assert calls == []  # a missing file is reported, never fabricated
    real = tmp_path / "thumb.jpg"
    real.write_bytes(b"\xff\xd8\xff" + b"x" * 10)
    ready = backfill.build_plan(_current(), thumbnail_path=str(real))
    result = backfill.apply_plan(service, ready)
    assert calls == [("dQw4w9WgXcQ", str(real))]
    assert result["thumbnail_set"] is True


def test_dry_run_performs_zero_writes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    service = MagicMock()
    service.videos().list().execute.return_value = {"items": [{
        "id": "dQw4w9WgXcQ",
        "snippet": {
            "title": _current()["title"], "description": _current()["description"],
            "tags": _current()["tags"], "categoryId": "24",
            "defaultLanguage": "en", "defaultAudioLanguage": "",
        },
        "status": {"privacyStatus": "public"},
    }]}
    service.videos().update.side_effect = AssertionError("write attempted in dry-run")
    monkeypatch.setattr(backfill, "youtube_service", lambda: service)
    monkeypatch.setattr(backfill, "set_thumbnail",
                        lambda *a: (_ for _ in ()).throw(AssertionError("thumbnail write in dry-run")))
    rc = backfill.main(["--video-id", "dQw4w9WgXcQ"])
    assert rc == 0
    plan = json.loads(capsys.readouterr().out.strip().splitlines()[0])
    assert plan["mode"] == "dry-run"
    assert plan["category"]["after"] == "23"
