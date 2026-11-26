"""TASK-VYR-064: pins for the public-domain source whitelist lane.

Covers the pure/offline surface of ``app.services.pd_whitelist``:
NASA + Wikimedia parsing (licence recorded per item, NASA-centre
credit only), the logo guard, NOAA/USGS catalogue entries (no invented
media URL), the music guard, and the series-pack guard record. All
network is replaced by a fake httpx client serving canned API JSON
shaped like the real NASA images API and Wikimedia Commons API
responses, so no network and no API key are needed.

These pins fail if a non-whitelist source leaks in, a licence stops
being recorded per item, a logo item reaches a pack, a catalogue
entry invents a media URL, or a non-YouTube-Audio-Library music
source passes the guard.
"""
from __future__ import annotations

import httpx
import pytest

from app.services import pd_whitelist
from app.services.discovery import discover_space_science_media
from app.services.pd_whitelist import (
    build_credit,
    build_series_pack,
    discover_pd_media,
    logo_guard,
    nasa_search,
    validate_music_source,
    wikimedia_search,
)

NASA_PAYLOAD = {
    "collection": {
        "items": [
            {
                "href": "https://images-assets.nasa.gov/image/PIA01518/collection.json",
                "data": [
                    {
                        "center": "JPL",
                        "nasa_id": "PIA01518",
                        "title": "Jupiter Plume",
                        "description": "Voyager view of Jupiter.",
                        "keywords": ["Jupiter", "Voyager"],
                        "media_type": "image",
                        "secondary_creator": "NASA/JPL",
                    }
                ],
                "links": [
                    {"href": "https://images-assets.nasa.gov/image/PIA01518/~thumb.jpg", "rel": "preview"},
                    {"href": "https://images-assets.nasa.gov/image/PIA01518/~orig.jpg", "rel": "canonical"},
                ],
            },
            {
                "href": "https://images-assets.nasa.gov/image/LOGO1/collection.json",
                "data": [
                    {
                        "center": "HQ",
                        "nasa_id": "LOGO1",
                        "title": "NASA meatball logo",
                        "description": "The official NASA insignia.",
                        "keywords": ["logo"],
                        "media_type": "image",
                    }
                ],
                "links": [
                    {"href": "https://images-assets.nasa.gov/image/LOGO1/~orig.jpg", "rel": "canonical"},
                ],
            },
            {
                "href": "https://images-assets.nasa.gov/image/PIA09231/collection.json",
                "data": [
                    {
                        "center": "",
                        "nasa_id": "PIA09231",
                        "title": "Jupiter Ahoy!",
                        "description": "New Horizons view.",
                        "keywords": ["Jupiter"],
                        "media_type": "image",
                    }
                ],
                "links": [
                    {"href": "https://images-assets.nasa.gov/image/PIA09231/~orig.jpg", "rel": "canonical"},
                ],
            },
        ]
    }
}

WIKIMEDIA_PAYLOAD = {
    "query": {
        "pages": {
            "1": {
                "title": "File:Jupiter NIRCam.jpg",
                "imageinfo": [
                    {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/2/23/Jupiter.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Jupiter_NIRCam.jpg",
                        "extmetadata": {
                            "LicenseShortName": {"value": "Public domain"},
                            "Artist": {"value": "NASA's James Webb Space Telescope."},
                        },
                    }
                ],
            },
            "2": {
                "title": "File:Jupiter Fan Art.jpg",
                "imageinfo": [
                    {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/9/99/FanArt.jpg",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Jupiter_Fan_Art.jpg",
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC BY-SA 4.0"},
                            "Artist": {"value": "A fan artist"},
                        },
                    }
                ],
            },
            "3": {
                "title": "File:Moon CC0.png",
                "imageinfo": [
                    {
                        "url": "https://upload.wikimedia.org/wikipedia/commons/3/33/Moon.png",
                        "descriptionurl": "https://commons.wikimedia.org/wiki/File:Moon_CC0.png",
                        "extmetadata": {
                            "LicenseShortName": {"value": "CC0"},
                            "Artist": {"value": "<a href=\"/wiki/User:Astro\">Astro</a>"},
                        },
                    }
                ],
            },
        }
    }
}


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("GET", "https://example.invalid/")
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=request,
                response=httpx.Response(self.status_code, request=request),
            )

    def json(self):
        return self._payload


class _FakeClient:
    """Fake httpx client: routes by URL, records calls."""

    def __init__(self, payload_by_host):
        self.payload_by_host = payload_by_host
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, params or {}))
        for host, payload in self.payload_by_host.items():
            if host in url:
                return _FakeResponse(payload)
        return _FakeResponse({}, status=404)

    def close(self):
        pass


def _client():
    return _FakeClient(
        {
            "images-api.nasa.gov": NASA_PAYLOAD,
            "commons.wikimedia.org": WIKIMEDIA_PAYLOAD,
        }
    )


# --- NASA parsing --------------------------------------------------------


def test_nasa_search_records_licence_centre_credit_and_canonical_url():
    items = nasa_search("Jupiter", client=_client())
    assert [i["source_id"] for i in items] == ["PIA01518", "PIA09231"]
    first = items[0]
    assert first["licence"] == "Public Domain (NASA)"
    assert first["credit"] == "Credit: NASA/JPL"
    assert first["media_url"] == "https://images-assets.nasa.gov/image/PIA01518/~orig.jpg"
    assert first["rights_verified"] is True
    assert first["fetch"] == "api"
    # No-centre item credits plain NASA, never secondary_creator.
    assert items[1]["credit"] == "Credit: NASA"


def test_nasa_search_excludes_logo_item():
    items = nasa_search("Jupiter", client=_client())
    assert all("logo" not in i["title"].casefold() for i in items)
    assert "LOGO1" not in {i["source_id"] for i in items}


def test_nasa_search_rejects_empty_query():
    with pytest.raises(ValueError):
        nasa_search("  ", client=_client())


def test_nasa_http_error_surfaces_as_runtime_error():
    client = _FakeClient({"images-api.nasa.gov": NASA_PAYLOAD})
    client.get = lambda url, params=None, headers=None: _FakeResponse({}, status=500)
    with pytest.raises(RuntimeError, match="HTTP 500"):
        nasa_search("Jupiter", client=client)


# --- Wikimedia parsing ---------------------------------------------------


def test_wikimedia_search_keeps_only_cc0_and_public_domain():
    items = wikimedia_search("Jupiter", client=_client())
    assert {i["source_id"] for i in items} == {
        "File:Jupiter NIRCam.jpg",
        "File:Moon CC0.png",
    }
    by_id = {i["source_id"]: i for i in items}
    assert by_id["File:Jupiter NIRCam.jpg"]["licence"] == "Public domain"
    assert by_id["File:Moon CC0.png"]["licence"] == "CC0"
    assert all(i["rights_verified"] for i in items)


def test_wikimedia_credit_strips_artist_html():
    items = wikimedia_search("Jupiter", client=_client())
    moon = next(i for i in items if i["source_id"] == "File:Moon CC0.png")
    assert moon["credit"] == "Credit: Astro via Wikimedia Commons (CC0)"
    assert "<" not in moon["credit"]


def test_wikimedia_search_rejects_empty_query():
    with pytest.raises(ValueError):
        wikimedia_search("", client=_client())


# --- Logo guard ----------------------------------------------------------


@pytest.mark.parametrize(
    "item,expected",
    [
        ({"title": "NASA meatball logo", "description": "", "keywords": []}, False),
        ({"title": "Mission patch", "description": "official insignia", "keywords": []}, False),
        ({"title": "Worm logotype sheet", "description": "", "keywords": []}, False),
        ({"title": "Earthworm in soil", "description": "a worm", "keywords": ["worm"]}, True),
        ({"title": "Jupiter Plume", "description": "Voyager view.", "keywords": ["Jupiter"]}, True),
        ({"title": "NASA seal ceremony", "description": "", "keywords": []}, False),
    ],
)
def test_logo_guard(item, expected):
    ok, reason = logo_guard(item)
    assert ok is expected
    assert (reason is None) is expected


# --- Credits -------------------------------------------------------------


def test_build_credit_per_source():
    assert build_credit("nasa", {"centre": "GSFC"}) == "Credit: NASA/GSFC"
    assert build_credit("nasa", {"centre": ""}) == "Credit: NASA"
    assert build_credit("noaa", {}) == "Credit: NOAA"
    assert build_credit("usgs", {}) == "Credit: U.S. Geological Survey"
    assert (
        build_credit("wikimedia", {"artist": "Astro", "licence": "CC0"})
        == "Credit: Astro via Wikimedia Commons (CC0)"
    )


# --- Catalogue sources ---------------------------------------------------


def test_catalogue_entries_record_licence_and_no_media_url():
    items = discover_pd_media("Jupiter", sources=("noaa", "usgs"), client=_client())
    assert len(items) == 2
    for item in items:
        assert item["media_url"] is None
        assert item["fetch"] == "catalogue"
        assert item["licence"] == "Public Domain (U.S. Government work)"
        assert item["search_url"] and "Jupiter" in item["search_url"]
        assert item["credit"].startswith("Credit: ")
    assert items[0]["source"] == "noaa"
    assert items[1]["source"] == "usgs"


def test_discover_rejects_unknown_source():
    with pytest.raises(ValueError, match="Unknown whitelist source"):
        discover_pd_media("Jupiter", sources=("pexels",), client=_client())


def test_discover_rejects_empty_query():
    with pytest.raises(ValueError):
        discover_pd_media(" ", client=_client())


# --- Music guard ---------------------------------------------------------


@pytest.mark.parametrize(
    "name,expected",
    [
        ("YouTube Audio Library", True),
        ("youtube audio library", True),
        ("Epidemic Sound", False),
        ("Artlist", False),
        ("", False),
    ],
)
def test_validate_music_source(name, expected):
    ok, reason = validate_music_source(name)
    assert ok is expected
    assert (reason is None) is expected


# --- Lane + series pack --------------------------------------------------


def test_discover_pd_media_mixes_api_and_catalogue_with_licence_per_item():
    items = discover_pd_media("Jupiter", max_results=10, client=_client())
    assert items, "lane returned nothing"
    assert {i["source"] for i in items} == {"nasa", "wikimedia", "noaa", "usgs"}
    for item in items:
        assert item["licence"], f"no licence on {item}"
        assert item["credit"].startswith("Credit: ")
        assert item["source"] in pd_whitelist.PD_SOURCES
    assert len(items) <= 10


def test_build_series_pack_guards_and_credits():
    pack = build_series_pack("Jupiter", client=_client())
    assert pack["query"] == "Jupiter"
    assert pack["music_source"] == "YouTube Audio Library"
    assert pack["guards"] == {
        "no_nasa_logos": True,
        "credit_in_description": True,
        "music_source": "YouTube Audio Library",
    }
    assert pack["credits"], "pack carries no credit lines"
    assert all(c.startswith("Credit: ") for c in pack["credits"])
    assert "Credit: NASA/JPL" in pack["credits"]
    assert set(pack["licences"]) == set(pd_whitelist.PD_SOURCES)


def test_discovery_wire_delegates_to_whitelist_lane(monkeypatch):
    seen = {}

    def fake_lane(query, max_results=10):
        seen["query"] = query
        seen["max_results"] = max_results
        return [{"source": "nasa", "licence": "Public Domain (NASA)"}]

    monkeypatch.setattr(pd_whitelist, "discover_pd_media", fake_lane)
    items = discover_space_science_media("Mars", max_results=3)
    assert items == [{"source": "nasa", "licence": "Public Domain (NASA)"}]
    assert seen == {"query": "Mars", "max_results": 3}
