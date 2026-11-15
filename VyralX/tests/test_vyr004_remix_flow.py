"""TASK-VYR-004: provenance-gated CC/PD remix flow.

The behaviour these tests pin (owner direction 2026-11-15: build videos
from other people's videos, with less editing — but only material the
channel may lawfully and safely reuse):

* discovery is restricted to Creative Commons / public-domain / owner
  material, from keyless sources (Wikimedia Commons, Internet Archive,
  NASA) — licences that forbid derivatives (ND) or commercial use (NC)
  are rejected, as is anything unrecognised;
* every evaluated source gets a provenance record (URL, author, licence,
  retrieval date); no provenance — or a rejected licence — is not a
  candidate, and the produce step refuses it before touching the network;
* the compliance checklist mirrors docs/REMIX_POLICY.md, including the
  excluded lanes (anime/gameplay compilations);
* upload metadata carries the attribution block (author, licence, source).

On clean main every test here fails: app.services.remix_flow does not exist.
"""
from __future__ import annotations

import json

import pytest

from app.services import remix_flow as rf


# --------------------------------------------------------------------------- #
# licence gate
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "name,url,platform,expected_class,expected_allowed",
    [
        ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/", "", "cc_by", True),
        ("CC BY-SA 4.0", "https://creativecommons.org/licenses/by-sa/4.0/", "", "cc_by_sa", True),
        ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/", "", "public_domain", True),
        ("Public Domain Mark 1.0", "https://creativecommons.org/publicdomain/mark/1.0/", "", "public_domain", True),
        ("CC BY-NC 4.0", "https://creativecommons.org/licenses/by-nc/4.0/", "", "cc_noncommercial", False),
        ("CC BY-ND 4.0", "https://creativecommons.org/licenses/by-nd/4.0/", "", "cc_noderivatives", False),
        ("CC BY-NC-SA 4.0", "https://creativecommons.org/licenses/by-nc-sa/4.0/", "", "cc_noncommercial", False),
        ("", "https://archive.org/details/x", "nasa", "public_domain", True),
        ("", "", "owner_upload", "owner", True),
        ("All rights reserved", "", "", "unknown", False),
        ("", "", "", "unknown", False),
        ("Creative Commons", "", "", "unknown", False),
    ],
)
def test_classify_license(name, url, platform, expected_class, expected_allowed):
    license_class, allowed, reason = rf.classify_license(name, url, platform)
    assert license_class == expected_class
    assert allowed is expected_allowed
    assert reason  # every decision carries its reason


# --------------------------------------------------------------------------- #
# adapter parsers (canned payloads — no network)
# --------------------------------------------------------------------------- #
COMMONS_PAYLOAD = {
    "query": {
        "pages": [
            {
                "title": "File:Stock market board.webm",
                "canonicalurl": "https://commons.wikimedia.org/wiki/File:Stock_market_board.webm",
                "videoinfo": [
                    {
                        "url": "https://upload.wikimedia.org/stock_market_board.webm",
                        "width": 1920,
                        "height": 1080,
                        "duration": 62.5,
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC BY 4.0"},
                            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by/4.0/"},
                            "Artist": {"value": '<a href="#">Jane Trader</a>'},
                        },
                    }
                ],
            },
            {
                "title": "File:No derivatives.webm",
                "canonicalurl": "https://commons.wikimedia.org/wiki/File:No_derivatives.webm",
                "videoinfo": [
                    {
                        "url": "https://upload.wikimedia.org/no_derivatives.webm",
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC BY-ND 4.0"},
                            "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-nd/4.0/"},
                            "Artist": {"value": "Someone"},
                        },
                    }
                ],
            },
        ]
    }
}


def test_parse_commons_extracts_provenance_and_classifies():
    records = rf.parse_commons(COMMONS_PAYLOAD)
    assert len(records) == 2
    good = records[0]
    assert good.platform == "wikimedia_commons"
    assert good.author == "Jane Trader"  # HTML stripped
    assert good.license_class == "cc_by" and good.allowed is True
    assert good.duration_seconds == 62.5
    assert good.media_url.endswith("stock_market_board.webm")
    rejected = records[1]
    assert rejected.allowed is False
    assert rejected.license_class == "cc_noderivatives"


def test_parse_archive_search_and_pick_file():
    payload = {
        "response": {
            "docs": [
                {
                    "identifier": "stock-footage-1930",
                    "title": "Stock ticker footage",
                    "creator": ["Prelinger, Rick"],
                    "licenseurl": "https://creativecommons.org/licenses/by/4.0/",
                }
            ]
        }
    }
    hits = rf.parse_archive_search(payload)
    assert hits == [
        {
            "identifier": "stock-footage-1930",
            "title": "Stock ticker footage",
            "author": "Prelinger, Rick",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
        }
    ]
    files = [
        {"name": "clip.mp4", "format": "h.264", "size": 5_000_000},
        {"name": "clip.webm", "format": "WebM", "size": 9_000_000},
        {"name": "notes.txt", "format": "Text", "size": 100},
    ]
    assert rf.pick_archive_file(files) == "clip.mp4"  # mp4 preferred over larger webm
    assert rf.pick_archive_file([{"name": "notes.txt"}]) is None


def test_parse_nasa_search_and_pick_file():
    payload = {
        "collection": {
            "items": [
                {
                    "href": "https://images-assets.nasa.gov/video/ABC/collection.json",
                    "data": [{"nasa_id": "ABC", "title": "Earth from orbit"}],
                }
            ]
        }
    }
    hits = rf.parse_nasa_search(payload)
    assert hits[0]["nasa_id"] == "ABC"
    urls = [
        "https://images-assets.nasa.gov/video/ABC/ABC~orig.mp4",
        "https://images-assets.nasa.gov/video/ABC/ABC~small.mp4",
        "https://images-assets.nasa.gov/video/ABC/poster.jpg",
    ]
    assert rf.pick_nasa_file(urls).endswith("~small.mp4")  # lightest rendition
    assert rf.pick_nasa_file(["https://x/y.jpg"]) is None


# --------------------------------------------------------------------------- #
# provenance gate + registry
# --------------------------------------------------------------------------- #
def _record(**overrides):
    base = dict(
        platform="wikimedia_commons",
        title="Market board",
        author="Jane Trader",
        source_page_url="https://commons.wikimedia.org/wiki/File:Market_board.webm",
        media_url="https://upload.wikimedia.org/market_board.webm",
        license_name="CC BY 4.0",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        retrieved_at="2026-11-15T00:00:00+00:00",
        license_class="cc_by",
        allowed=True,
        decision_reason="CC BY — reuse allowed with attribution",
    )
    base.update(overrides)
    return rf.ProvenanceRecord(**base)


def test_registry_round_trip_and_stable_record_id(tmp_path):
    registry = tmp_path / "prov.jsonl"
    record = _record()
    rf.record_provenance([record], registry)
    loaded = rf.load_provenance(registry)
    assert len(loaded) == 1
    assert loaded[0].record_id == record.record_id
    assert loaded[0].to_dict() == record.to_dict()


def test_require_candidate_rejects_unlicensed_and_incomplete():
    _record().require_candidate()  # complete + allowed: no raise
    with pytest.raises(ValueError):
        _record(allowed=False, license_class="cc_noderivatives").require_candidate()
    with pytest.raises(ValueError):
        _record(retrieved_at="").require_candidate()  # no provenance timestamp
    with pytest.raises(ValueError):
        _record(author="").require_candidate()


def test_discover_candidates_records_everything_returns_only_allowed(tmp_path, monkeypatch):
    good = _record()
    bad = _record(
        source_page_url="https://commons.wikimedia.org/wiki/File:Nc.webm",
        allowed=False,
        license_class="cc_noncommercial",
        decision_reason="NonCommercial licence forbids use on a monetised channel",
    )
    monkeypatch.setitem(rf._ADAPTERS, "fake", lambda q, n: [good, bad])
    registry = tmp_path / "prov.jsonl"
    candidates = rf.discover_candidates(
        "markets", sources=("fake",), registry_path=registry
    )
    assert candidates == [good]
    recorded = rf.load_provenance(registry)
    assert {r.record_id for r in recorded} == {good.record_id, bad.record_id}
    assert all(r.retrieved_at for r in recorded)  # stamped at discovery


# --------------------------------------------------------------------------- #
# metadata + compliance checklist
# --------------------------------------------------------------------------- #
def test_metadata_carries_attribution_block():
    meta = rf.build_remix_metadata(_record(), title="Money in 40 Seconds: Leverage")
    assert "Jane Trader" in meta["description"]
    assert "CC BY 4.0" in meta["description"]
    assert "https://commons.wikimedia.org/wiki/File:Market_board.webm" in meta["description"]
    assert "Jane Trader" in meta["attribution"]


def test_compliance_checklist_pass_and_exclusions():
    checklist = rf.compliance_checklist(
        _record(),
        lane="space_science",
        source_has_speech=False,
        render_seconds=45.0,
        format_name="one_fact_escalation",
    )
    assert rf.checklist_passed(checklist)
    anime = rf.compliance_checklist(
        _record(), lane="anime_compilation", source_has_speech=False
    )
    assert not rf.checklist_passed(anime)
    assert any(
        item["status"] == "FAIL" and "excluded lane" in item["item"]
        for item in anime
    )
    narrated = rf.compliance_checklist(
        _record(),
        lane="space_science",
        source_has_speech=True,
        render_seconds=45.0,
        format_name="one_fact_escalation",
    )
    assert not rf.checklist_passed(narrated)


def test_compliance_checklist_hard_rules():
    base = dict(
        lane="space_science",
        source_has_speech=False,
        format_name="one_fact_escalation",
    )
    # claimed Shorts over 1 minute are BLOCKED, not just claimed
    long_render = rf.compliance_checklist(_record(), render_seconds=75.0, **base)
    assert not rf.checklist_passed(long_render)
    assert any(
        item["status"] == "FAIL" and "60 seconds" in item["item"]
        for item in long_render
    )
    # unmeasured runtime cannot pass either
    unmeasured = rf.compliance_checklist(_record(), render_seconds=None, **base)
    assert not rf.checklist_passed(unmeasured)
    # finance advice and sports compilations are excluded lanes
    for lane in ("finance_advice", "sports_compilation", "bollywood_compilation"):
        items = rf.compliance_checklist(
            _record(), render_seconds=45.0, **{**base, "lane": lane}
        )
        assert not rf.checklist_passed(items), lane
    # money STORIES are a lawful lane; no declared format is not
    story = rf.compliance_checklist(
        _record(), render_seconds=45.0, **{**base, "lane": "money_story"}
    )
    assert rf.checklist_passed(story)
    no_format = rf.compliance_checklist(_record(), render_seconds=45.0,
                                        **{**base, "format_name": ""})
    assert not rf.checklist_passed(no_format)


def test_produce_refuses_rejected_record_and_excluded_lane():
    rejected = _record(allowed=False, license_class="unknown", decision_reason="no licence")
    with pytest.raises(ValueError):
        rf.produce_remix_short(rejected, "Some script.", title="T")
    with pytest.raises(ValueError):
        rf.produce_remix_short(_record(), "Some script.", title="T", lane="gameplay_reupload")


def test_review_queue_round_trip(tmp_path):
    queue = tmp_path / "queue.jsonl"
    entry = {"queue_id": "remix-x", "status": "pending_review"}
    rf.enqueue_review(entry, queue)
    assert rf.list_review_queue(queue) == [entry]
    assert json.loads(queue.read_text(encoding="utf-8").strip()) == entry
