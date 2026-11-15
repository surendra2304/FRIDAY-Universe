"""Tests for TASK-IG-INT-03 — live tracking data layer.

Hermetic: transports are injected. Fixtures are shaped from the REAL public
responses captured 2026-11-15 (OpenSky state vectors, wheretheiss.at ISS
JSON, Digitraffic AIS GeoJSON, USGS GeoJSON).
"""

from __future__ import annotations

import json

import pytest

from intelx.tracking.models import BoundingBox
from intelx.tracking.service import TrackingService
from intelx.tracking.sources import (
    DigitrafficShipsSource,
    LayerUnavailable,
    OpenSkyFlightsSource,
    SatelliteSource,
    UsgsEventsSource,
)

OPENSKY = json.dumps(
    {
        "time": 1794763854,
        "states": [
            ["801686", "AXB1235 ", "India", 1794763766, 1794763792, 72.9095, 19.0893, 167.64, False, 79.75, 269.26, -3.9, None, 129.54, "2321", False, 0],
            ["80175a", "IGO31HM ", "India", 1794763853, 1794763853, 72.6957, 19.2349, 3009.9, False, 154.04, 356.94, 14.96, None, 3116.58, "0272", False, 0],
            ["deadbe", "NOLOC   ", "Nowhere", 1794763853, 1794763853, None, None, None, False, None, None, None, None, None, None, False, 0],
        ],
    }
).encode()

ISS = json.dumps(
    {
        "name": "iss",
        "id": 25544,
        "latitude": 31.6132,
        "longitude": -18.3095,
        "altitude": 415.37,
        "velocity": 27608.03,
        "visibility": "daylight",
        "footprint": 4483.83,
        "timestamp": 1794763835,
    }
).encode()

AIS = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "mmsi": 374891000,
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [28.8367, 60.00092]},
                "properties": {
                    "mmsi": 374891000,
                    "sog": 3.7,
                    "cog": 334.0,
                    "navStat": 0,
                    "heading": 320,
                    "timestampExternal": 1794763832269,
                },
            },
            {
                "mmsi": 230061400,
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [20.08849, 60.375063]},
                "properties": {
                    "mmsi": 230061400,
                    "sog": 0.0,
                    "cog": 0.0,
                    "navStat": 1,
                    "heading": 511,
                    "timestampExternal": 1794763832269,
                },
            },
        ],
    }
).encode()

USGS = json.dumps(
    {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": "ak2026wqrlbd",
                "properties": {
                    "mag": 3.4,
                    "place": "19 km ENE of Susitna North, Alaska",
                    "time": 1794762829502,
                    "type": "earthquake",
                    "title": "M 3.4 - 19 km ENE of Susitna North, Alaska",
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/aka2026wqrlbd",
                },
                "geometry": {"type": "Point", "coordinates": [-150.1, 62.3, 12.5]},
            }
        ],
    }
).encode()


def make_get(routes: dict[str, tuple[int, bytes]]):
    async def get(url: str, headers: dict) -> tuple[int, dict, bytes]:
        for key, (status, body) in routes.items():
            if key in url:
                return status, {}, body
        return 404, {}, b""

    return get


async def test_opensky_parses_state_vectors() -> None:
    src = OpenSkyFlightsSource(get=make_get({"opensky": (200, OPENSKY)}))
    objects = await src.fetch()
    assert len(objects) == 2  # the position-less vector is skipped
    first = objects[0]
    assert first.kind == "flight"
    assert first.name == "AXB1235"
    assert first.lat == pytest.approx(19.0893)
    assert first.speed_mps == pytest.approx(79.75)
    assert first.properties["origin_country"] == "India"


async def test_opensky_429_is_an_honest_layer_error() -> None:
    src = OpenSkyFlightsSource(get=make_get({"opensky": (429, b"")}))
    with pytest.raises(LayerUnavailable) as exc:
        await src.fetch()
    assert "429" in str(exc.value)


async def test_satellite_normalises_units() -> None:
    src = SatelliteSource(get=make_get({"wheretheiss": (200, ISS)}))
    objects = await src.fetch()
    assert len(objects) == 1
    iss = objects[0]
    assert iss.name == "iss"
    assert iss.altitude_m == pytest.approx(415370.0)
    assert iss.speed_mps == pytest.approx(27608.03 / 3.6)
    assert iss.properties["altitude_km_native"] == 415.37


async def test_satellite_bbox_filter() -> None:
    src = SatelliteSource(get=make_get({"wheretheiss": (200, ISS)}))
    india = BoundingBox(lamin=5, lomin=68, lamax=37, lomax=97)
    assert await src.fetch(bbox=india) == []  # ISS fixture sits over the Atlantic


async def test_ships_parse_and_scope_is_labelled_regional() -> None:
    src = DigitrafficShipsSource(get=make_get({"digitraffic": (200, AIS)}))
    objects = await src.fetch()
    assert len(objects) == 2
    assert objects[0].speed_mps == pytest.approx(3.7 * 0.514444)
    assert objects[0].heading_deg == 320
    assert objects[1].heading_deg == 0.0  # heading 511 = unavailable -> cog fallback
    assert "Baltic" in src.scope_note and "not global" in src.scope_note


async def test_events_parse() -> None:
    src = UsgsEventsSource(get=make_get({"earthquake": (200, USGS)}))
    objects = await src.fetch()
    assert len(objects) == 1
    quake = objects[0]
    assert quake.kind == "event"
    assert quake.properties["magnitude"] == 3.4
    assert quake.altitude_m == pytest.approx(-12500.0)  # depth below surface


async def test_snapshot_isolates_layer_failures() -> None:
    good = SatelliteSource(get=make_get({"wheretheiss": (200, ISS)}))
    bad = OpenSkyFlightsSource(get=make_get({"opensky": (503, b"")}))
    service = TrackingService(sources=[good, bad])
    snap = await service.snapshot()
    assert len(snap.objects) == 1
    by_source = {layer.source: layer for layer in snap.layers}
    assert by_source["wheretheiss"].count == 1
    assert by_source["opensky"].count == 0
    assert "503" in by_source["opensky"].error
    payload = snap.to_dict()
    assert payload["total_objects"] == 1


async def test_snapshot_kind_filter() -> None:
    service = TrackingService(
        sources=[
            SatelliteSource(get=make_get({"wheretheiss": (200, ISS)})),
            UsgsEventsSource(get=make_get({"earthquake": (200, USGS)})),
        ]
    )
    snap = await service.snapshot(kinds={"event"})
    assert [o.kind for o in snap.objects] == ["event"]
    assert len(snap.layers) == 1
