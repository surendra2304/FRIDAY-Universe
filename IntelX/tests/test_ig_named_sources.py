"""Tests for TASK-IG-INT-05 — named research/archive source utilities.

Hermetic. Fixtures mirror the real archive.org responses captured live
2026-11-15 (advancedsearch docs; metadata with files; {} for unknown ids).
"""

from __future__ import annotations

import json

import pytest

from intelx.connectors.named_sources import (
    NAMED_SOURCES,
    ArchiveOrgClient,
    NamedSourceUnavailable,
    WolframAlphaClient,
    seed_search_url,
)

ARCHIVE_SEARCH = json.dumps(
    {
        "response": {
            "numFound": 2,
            "docs": [
                {
                    "identifier": "27-03-2020_202005",
                    "title": "Friday Message (27-03-2020)",
                    "creator": "Geoji T Samuel",
                    "date": "2020-05-18T00:00:00Z",
                    "mediatype": "audio",
                },
                {"identifier": "no-title-item", "creator": "Anon", "mediatype": "texts"},
            ],
        }
    }
).encode()

ARCHIVE_METADATA = json.dumps(
    {
        "metadata": {
            "identifier": "27-03-2020_202005",
            "title": "Friday Message (27-03-2020)",
            "description": "A recorded message.",
            "creator": "Geoji T Samuel",
        },
        "files": [
            {"name": "27-03-2020 Edited.mp3", "format": "VBR MP3", "size": "310832"},
            {"name": "__ia_thumb.jpg", "format": "Item Tile", "size": "5661"},
        ],
    }
).encode()

WOLFRAM = json.dumps(
    {
        "queryresult": {
            "success": True,
            "pods": [
                {"title": "Input", "subpods": [{"plaintext": "2 + 2"}]},
                {"title": "Result", "subpods": [{"plaintext": "4"}]},
                {"title": "Empty pod", "subpods": [{"plaintext": ""}]},
            ],
        }
    }
).encode()


class FakeFetch:
    def __init__(self, routes: dict[str, tuple[int, bytes]]) -> None:
        self.routes = routes

    async def __call__(self, url: str) -> tuple[int, str, bytes]:
        for key, (status, body) in self.routes.items():
            if key in url:
                return status, url, body
        return 404, url, b""


def test_registry_covers_the_five_named_sources_honestly() -> None:
    by_name = {s.name: s for s in NAMED_SOURCES}
    assert set(by_name) == {"Internet Archive", "WolframAlpha", "OpenCulture", "AlternativeTo", "JustWatch"}
    assert by_name["Internet Archive"].kind == "api_keyless"
    assert by_name["WolframAlpha"].kind == "api_keyed"
    for seed in ("OpenCulture", "AlternativeTo", "JustWatch"):
        assert by_name[seed].kind == "seed_site"
        assert "No public API" in by_name[seed].access_note


def test_seed_search_urls() -> None:
    assert seed_search_url("AlternativeTo", "notion") == "https://alternativeto.net/browse/search/?q=notion"
    assert "wolframalpha.com/input?i=" in seed_search_url("WolframAlpha", "integrate x")
    with pytest.raises(NamedSourceUnavailable):
        seed_search_url("NoSuchSite", "x")


async def test_archive_search_parses_docs() -> None:
    client = ArchiveOrgClient(fetch=FakeFetch({"advancedsearch": (200, ARCHIVE_SEARCH)}))
    items = await client.search("friday")
    assert len(items) == 2
    assert items[0].identifier == "27-03-2020_202005"
    assert items[0].item_url == "https://archive.org/details/27-03-2020_202005"
    assert items[0].mediatype == "audio"


async def test_archive_metadata_and_unknown_identifier() -> None:
    client = ArchiveOrgClient(fetch=FakeFetch({"metadata/27-03": (200, ARCHIVE_METADATA), "metadata": (200, b"{}")}))
    meta = await client.metadata("27-03-2020_202005")
    assert meta is not None
    assert meta.title == "Friday Message (27-03-2020)"
    assert meta.files[0]["format"] == "VBR MP3"
    # archive.org answers {} for unknown ids: reported as not-found, not dressed up
    assert await client.metadata("definitely-not-an-item") is None


async def test_archive_http_error_is_explicit() -> None:
    client = ArchiveOrgClient(fetch=FakeFetch({"advancedsearch": (503, b"")}))
    with pytest.raises(NamedSourceUnavailable) as exc:
        await client.search("x")
    assert "503" in str(exc.value)


async def test_wolfram_fails_closed_without_appid() -> None:
    client = WolframAlphaClient(appid="", fetch=FakeFetch({}))
    assert not client.configured
    with pytest.raises(NamedSourceUnavailable) as exc:
        await client.query("2+2")
    assert "WOLFRAMALPHA_APPID" in str(exc.value)
    assert "fabricated" in str(exc.value)


async def test_wolfram_parses_pods_when_configured() -> None:
    client = WolframAlphaClient(appid="TEST-APPID", fetch=FakeFetch({"wolframalpha": (200, WOLFRAM)}))
    pods = await client.query("2+2")
    assert pods == [
        {"title": "Input", "plaintext": "2 + 2"},
        {"title": "Result", "plaintext": "4"},
    ]
