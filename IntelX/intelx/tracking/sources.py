"""Live tracking sources (TASK-IG-INT-03) — free/public feeds only.

Every source below was verified live from the build sandbox on 2026-11-15:

  * Flights    — OpenSky Network public API (anonymous). Global ADS-B;
                 anonymous rate limits apply and HTTP 429 is surfaced as a
                 layer error, never filled with stale or invented traffic.
  * Satellites — wheretheiss.at, which computes positions from public TLE
                 data for arbitrary NORAD ids. Default tracked set is the
                 ISS only; extend via configuration.
  * Ships      — Digitraffic AIS (Fintraffic). REAL but REGIONAL: Finnish /
                 Baltic Sea waters only. The scope note travels with every
                 report so no consumer can mistake it for global coverage.
                 The API requires an Accept header, gzip, and a
                 Digitraffic-User header (documented by the provider).
  * Events     — USGS earthquake GeoJSON feeds (public, keyless).

All sources are read-only GETs. HTTP access is injectable for hermetic
tests; the default transport is httpx with the provider-documented headers.

Python 3.10 compatible (production interpreter).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable

from intelx.tracking.models import BoundingBox, TrackedObject

logger = logging.getLogger("intelx.tracking")

UTC = timezone.utc

# (status, headers, body)
HttpGet = Callable[[str, dict], Awaitable[tuple[int, dict, bytes]]]


class LayerUnavailable(RuntimeError):
    """A tracking layer could not produce data; reason is explicit."""


async def _default_get(url: str, headers: dict) -> tuple[int, dict, bytes]:
    import httpx

    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, headers=headers)
        return resp.status_code, dict(resp.headers), resp.content


def _get_or_raise(status: int, body: bytes, source: str) -> dict:
    if status == 429:
        raise LayerUnavailable(f"{source}: HTTP 429 (public rate limit reached; no data served rather than stale data)")
    if status != 200:
        raise LayerUnavailable(f"{source}: HTTP {status}")
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise LayerUnavailable(f"{source}: invalid JSON: {exc}") from exc


class OpenSkyFlightsSource:
    """Flights from the OpenSky Network public API."""

    source_id = "opensky"
    kind = "flight"
    scope_note = "Global ADS-B via OpenSky (anonymous tier; rate limits apply)."

    def __init__(self, get: HttpGet | None = None) -> None:
        self._get = get or _default_get

    async def fetch(self, bbox: BoundingBox | None = None) -> list[TrackedObject]:
        url = "https://opensky-network.org/api/states/all"
        if bbox is not None:
            url += f"?lamin={bbox.lamin}&lomin={bbox.lomin}&lamax={bbox.lamax}&lomax={bbox.lomax}"
        status, _, body = await self._get(url, {"User-Agent": "FRIDAY-Universe-IntelX/1.0"})
        payload = _get_or_raise(status, body, self.source_id)
        objects: list[TrackedObject] = []
        for state in payload.get("states") or []:
            # OpenSky state vector layout (documented order).
            if len(state) < 11 or state[5] is None or state[6] is None:
                continue
            icao24 = str(state[0])
            callsign = str(state[1] or "").strip()
            observed = state[3] or state[4] or payload.get("time") or 0
            objects.append(
                TrackedObject(
                    kind="flight",
                    object_id=icao24,
                    name=callsign or icao24,
                    lat=float(state[6]),
                    lon=float(state[5]),
                    altitude_m=state[7] if state[7] is not None else state[13] if len(state) > 13 else None,
                    speed_mps=state[9],
                    heading_deg=state[10],
                    observed_at=datetime.fromtimestamp(int(observed), tz=UTC),
                    source=self.source_id,
                    properties={
                        "origin_country": state[2],
                        "on_ground": state[8],
                        "vertical_rate_mps": state[11] if len(state) > 11 else None,
                        "squawk": state[14] if len(state) > 14 else None,
                    },
                )
            )
        return objects


class SatelliteSource:
    """Satellite positions via wheretheiss.at (TLE-derived, public)."""

    source_id = "wheretheiss"
    kind = "satellite"
    scope_note = "Positions computed by wheretheiss.at from public TLE data for the configured NORAD ids."

    def __init__(self, norad_ids: list[int] | None = None, get: HttpGet | None = None) -> None:
        self.norad_ids = list(norad_ids) if norad_ids else [25544]  # ISS
        self._get = get or _default_get

    async def fetch(self, bbox: BoundingBox | None = None) -> list[TrackedObject]:
        objects: list[TrackedObject] = []
        for norad_id in self.norad_ids:
            url = f"https://api.wheretheiss.at/v1/satellites/{norad_id}"
            status, _, body = await self._get(url, {"User-Agent": "FRIDAY-Universe-IntelX/1.0"})
            payload = _get_or_raise(status, body, f"{self.source_id}:{norad_id}")
            lat = float(payload["latitude"])
            lon = float(payload["longitude"])
            if bbox is not None and not bbox.contains(lat, lon):
                continue
            objects.append(
                TrackedObject(
                    kind="satellite",
                    object_id=str(payload.get("id", norad_id)),
                    name=str(payload.get("name", f"NORAD {norad_id}")),
                    lat=lat,
                    lon=lon,
                    altitude_m=float(payload["altitude"]) * 1000.0,  # API reports km
                    speed_mps=float(payload["velocity"]) / 3.6,  # API reports km/h
                    heading_deg=None,
                    observed_at=datetime.fromtimestamp(int(payload["timestamp"]), tz=UTC),
                    source=self.source_id,
                    properties={
                        "visibility": payload.get("visibility"),
                        "footprint_km": payload.get("footprint"),
                        "altitude_km_native": payload.get("altitude"),
                        "velocity_kmh_native": payload.get("velocity"),
                    },
                )
            )
        return objects


class DigitrafficShipsSource:
    """Ships from Digitraffic AIS — Baltic/Finnish waters ONLY (see scope)."""

    source_id = "digitraffic_ais"
    kind = "ship"
    scope_note = (
        "REGIONAL: Digitraffic AIS covers Finnish / Baltic Sea waters only — "
        "this is not global ship coverage, and no global keyless AIS feed exists."
    )
    _HEADERS = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Digitraffic-User": "FRIDAY-Universe/IntelX",
        "User-Agent": "FRIDAY-Universe-IntelX/1.0",
    }

    def __init__(self, get: HttpGet | None = None) -> None:
        self._get = get or _default_get

    async def fetch(self, bbox: BoundingBox | None = None) -> list[TrackedObject]:
        url = "https://meri.digitraffic.fi/api/ais/v1/locations"
        status, _, body = await self._get(url, dict(self._HEADERS))
        payload = _get_or_raise(status, body, self.source_id)
        objects: list[TrackedObject] = []
        for feature in payload.get("features") or []:
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            if bbox is not None and not bbox.contains(lat, lon):
                continue
            props = feature.get("properties") or {}
            mmsi = str(props.get("mmsi") or feature.get("mmsi") or "")
            ts_ms = props.get("timestampExternal") or 0
            sog_knots = props.get("sog")
            objects.append(
                TrackedObject(
                    kind="ship",
                    object_id=mmsi,
                    name=mmsi,  # the locations feed carries no vessel names
                    lat=lat,
                    lon=lon,
                    speed_mps=(float(sog_knots) * 0.514444) if sog_knots is not None else None,
                    heading_deg=props.get("heading") if props.get("heading") != 511 else props.get("cog"),
                    observed_at=datetime.fromtimestamp(int(ts_ms) / 1000, tz=UTC) if ts_ms else datetime.now(UTC),
                    source=self.source_id,
                    properties={
                        "mmsi": mmsi,
                        "sog_knots_native": sog_knots,
                        "cog_deg": props.get("cog"),
                        "nav_stat": props.get("navStat"),
                    },
                )
            )
        return objects


class UsgsEventsSource:
    """Real-time world events: USGS earthquakes (public GeoJSON)."""

    source_id = "usgs_earthquakes"
    kind = "event"
    scope_note = "USGS earthquakes, past 24 hours, magnitude 2.5+ (feed-configurable)."

    def __init__(self, feed: str = "2.5_day", get: HttpGet | None = None) -> None:
        self.feed = feed
        self._get = get or _default_get

    async def fetch(self, bbox: BoundingBox | None = None) -> list[TrackedObject]:
        url = f"https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{self.feed}.geojson"
        status, _, body = await self._get(url, {"User-Agent": "FRIDAY-Universe-IntelX/1.0"})
        payload = _get_or_raise(status, body, self.source_id)
        objects: list[TrackedObject] = []
        for feature in payload.get("features") or []:
            coords = (feature.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            if bbox is not None and not bbox.contains(lat, lon):
                continue
            props = feature.get("properties") or {}
            ts_ms = props.get("time") or 0
            objects.append(
                TrackedObject(
                    kind="event",
                    object_id=str(feature.get("id", "")),
                    name=str(props.get("title") or props.get("place") or "earthquake"),
                    lat=lat,
                    lon=lon,
                    altitude_m=(-float(coords[2]) * 1000.0) if len(coords) > 2 and coords[2] is not None else None,
                    observed_at=datetime.fromtimestamp(int(ts_ms) / 1000, tz=UTC) if ts_ms else datetime.now(UTC),
                    source=self.source_id,
                    properties={
                        "event_type": props.get("type", "earthquake"),
                        "magnitude": props.get("mag"),
                        "place": props.get("place"),
                        "depth_km": coords[2] if len(coords) > 2 else None,
                        "url": props.get("url"),
                    },
                )
            )
        return objects


__all__ = [
    "DigitrafficShipsSource",
    "HttpGet",
    "LayerUnavailable",
    "OpenSkyFlightsSource",
    "SatelliteSource",
    "UsgsEventsSource",
]
