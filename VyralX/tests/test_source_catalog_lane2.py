"""Schema/provenance validation for the lane-2 history source catalogue (TASK-VYR-011).

The catalogue is only useful if every record can pass VyralX's rights
gate and feed the remix editor real measurements, so these tests pin:
- every clip carries a gate-passing licence (public domain / CC0 /
  CC BY / CC BY-SA — never NC/ND/unknown) plus provenance,
- durations/resolutions are measured values in sane ranges, each
  labelled with its measurement source,
- ids and media URLs are unique,
- the loader maps records onto Source-model fields without loss.
"""
import json
import re
from pathlib import Path

from app.services.source_catalog_lane2 import (
    CATALOG_PATH,
    as_source_rows,
    catalogue_stats,
    load_catalogue,
    load_clips,
)

_PLACEHOLDERS = {"-", "n/a", "na", "none", "unknown", "tbd", "todo", "pending", "not provided"}
_MEASUREMENT_SOURCES = {"archive_metadata", "commons_metadata", "loc_metadata", "ffprobe"}


def _meaningful(value: str) -> bool:
    v = " ".join(str(value or "").split()).strip().casefold()
    return len(v) >= 5 and v not in _PLACEHOLDERS


def _gate_passing(license_name: str) -> bool:
    low = (license_name or "").lower()
    if "noncommercial" in low or "no derivatives" in low or "-nc" in low or "-nd" in low:
        return False
    return (
        "public domain" in low
        or low.startswith("cc0")
        or re.match(r"cc by-sa( |$)", low) is not None
        or re.match(r"cc by( |$)", low) is not None
    )


def test_catalogue_file_present_and_counted():
    assert Path(CATALOG_PATH).is_file()
    doc = load_catalogue()
    assert doc["lane"] == "lane2_history"
    assert doc["clip_count"] == len(doc["clips"])
    assert doc["clip_count"] >= 45


def test_every_clip_has_rights_and_provenance():
    for clip in load_catalogue()["clips"]:
        assert clip["rights_verified"] is True, clip["catalog_id"]
        assert _meaningful(clip["license_name"]), clip["catalog_id"]
        assert _gate_passing(clip["license_name"]), clip["catalog_id"]
        assert _meaningful(clip["permission_reference"]), clip["catalog_id"]
        assert _meaningful(clip["rights_basis"]), clip["catalog_id"]
        assert clip["source_url"].startswith("https://"), clip["catalog_id"]
        assert clip["page_url"].startswith("https://"), clip["catalog_id"]


def test_measurements_are_real_sane_and_labelled():
    for clip in load_catalogue()["clips"]:
        assert 20 <= clip["duration_seconds"] <= 1200, clip["catalog_id"]
        assert clip["width"] >= 640 and clip["height"] >= 240, clip["catalog_id"]
        assert clip["resolution"] == f"{clip['width']}x{clip['height']}"
        assert clip["measurement_source"] in _MEASUREMENT_SOURCES, clip["catalog_id"]
        assert clip["topic_tags"], clip["catalog_id"]


def test_ids_and_urls_unique():
    clips = load_catalogue()["clips"]
    assert len({c["catalog_id"] for c in clips}) == len(clips)
    assert len({c["source_url"] for c in clips}) == len(clips)
    assert len({c["external_id"] for c in clips}) == len(clips)


def test_loader_filters_and_source_row_mapping():
    clips = load_clips()
    first_tag = clips[0]["topic_tags"][0]
    assert load_clips(tag=first_tag)
    assert load_clips(platform=clips[0]["platform"])
    assert load_clips(min_width=640) == clips
    rows = as_source_rows()
    assert len(rows) == len(clips)
    for row in rows:
        assert _meaningful(row["license_name"])
        assert _gate_passing(row["license_name"])
        assert _meaningful(row["permission_reference"])
        assert row["rights_verified"] is True
        assert row["source_url"].startswith("https://")


def test_stats_shape():
    stats = catalogue_stats()
    assert stats["lane"] == "lane2_history"
    assert stats["clip_count"] == len(load_clips())
    assert stats["total_seconds"] > 0
    assert stats["by_platform"]


def test_raw_json_is_valid_and_self_describing():
    doc = json.loads(Path(CATALOG_PATH).read_text(encoding="utf-8"))
    assert doc["catalogue"] == "vyralx_lane2_history_sources"
    assert doc["built_by"] == "TASK-VYR-011"
