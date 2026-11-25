"""TASK-FRD-050 — FRIDAY voice place-finder flow.

A spoken place request runs the full flow:

1. parse the request (cuisine / place type, optional "near <area>",
   optional "from <start point>");
2. map search by cuisine / type around the area;
3. filter to the highest-rated result;
4. route time from the named start point;
5. read the verdict aloud (via the host-supplied ``speak`` callable).

Providers are free and keyless by default: OpenStreetMap Nominatim for
geocoding, the Overpass API for the place search, and the public OSRM demo
server for driving time. OpenStreetMap carries no star ratings, so the
default provider reports ``rating=None`` and the flow ranks unrated
candidates by listing completeness — and the verdict says so plainly
instead of inventing a rating. A provider that does carry ratings (a
future Google Places adapter, or a test fake) plugs into the same
``PlaceSearchProvider`` protocol and the highest-rated filter then uses
real ratings, ties broken by review count.

Nothing in this module invents data: every verdict is built from what
the provider actually returned, and every failure mode (unknown area,
unknown start point, no candidates, provider error) produces an honest
verdict that says what is missing. The ``speak`` step only reads the
verdict text; the map URL is returned for display, never spoken.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Protocol

import httpx

logger = logging.getLogger("voice.place_finder")

_USER_AGENT = "FRIDAY-Universe/1.0 (voice place-finder; contact: FRIDAY-Universe)"
_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
_HTTP_TIMEOUT = 10.0
_DEFAULT_RADIUS_M = 5000

# Cuisine / type words the parser recognises. Anything else the speaker
# says is kept verbatim as the free-text search query.
_CUISINES = (
    "italian", "indian", "chinese", "mexican", "thai", "japanese",
    "korean", "vietnamese", "french", "greek", "turkish", "lebanese",
    "american", "pizza", "sushi", "vegan", "vegetarian", "burger",
    "seafood", "barbecue", "bbq", "bakery", "coffee", "breakfast",
    "brunch", "fast food", "street food",
)
_PLACE_TYPES = (
    "restaurant", "cafe", "coffee shop", "bakery", "bar", "pub",
    "diner", "eatery",
)
_WAKE_WORDS = (
    "hey friday", "ok friday", "friday",
    "find me", "find", "show me", "look for", "search for",
    "what is the best", "what's the best", "whats the best",
    "the best", "best", "top", "nearest", "closest",
)


@dataclass
class Place:
    """One place candidate returned by a search provider."""

    name: str
    kinds: tuple[str, ...] = ()
    rating: float | None = None
    review_count: int = 0
    lat: float | None = None
    lon: float | None = None
    address: str = ""
    source: str = ""
    # Listing-completeness score (0-5) used only when no candidate has a
    # rating; never presented as a star rating.
    quality_score: int = 0

    @property
    def map_url(self) -> str:
        if self.lat is None or self.lon is None:
            return ""
        return (
            "https://www.openstreetmap.org/?"
            f"mlat={self.lat}&mlon={self.lon}#map=16/{self.lat}/{self.lon}"
        )


@dataclass
class PlaceRequest:
    """A parsed spoken place request."""

    query: str  # cuisine / type words, or the speaker's free text
    cuisine: str = ""
    place_type: str = ""
    near_text: str = ""  # area to search around ("near <area>")
    origin_text: str = ""  # named start point ("from <start point>")

    @property
    def search_text(self) -> str:
        parts = [p for p in (self.cuisine, self.place_type) if p]
        return " ".join(parts) if parts else self.query


@dataclass
class PlaceFinderResult:
    """Outcome of one full place-finder flow run."""

    request: PlaceRequest
    verdict: str  # speakable text; never contains a URL
    place: Place | None = None
    candidates: list[Place] = field(default_factory=list)
    route_minutes: float | None = None
    rating_basis: str = "none"  # "rated" | "unrated" | "none"
    map_url: str = ""
    error: str = ""


class PlaceSearchProvider(Protocol):
    """What the flow needs from a map backend."""

    def geocode(self, name: str) -> tuple[float, float] | None:
        """Resolve a place/area name to (lat, lon); None when unknown."""
        ...

    def search_places(
        self, query: str, near_lat: float, near_lon: float, radius_m: int
    ) -> list[Place]:
        """Places matching ``query`` near the given point."""
        ...

    def route_minutes(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
    ) -> float | None:
        """Driving time in minutes; None when no route is available."""
        ...


# ---------------------------------------------------------------------------
# Request parsing (pure)
# ---------------------------------------------------------------------------

def parse_place_request(text: str) -> PlaceRequest:
    """Parse a spoken place request into its structured parts.

    Understands "best <cuisine> restaurant near <area> from <start>",
    in any order of the "near" / "from" clauses. Unknown words are kept
    as the free-text query; nothing is dropped silently.
    """
    raw = (text or "").strip()
    lowered = re.sub(r"\s+", " ", raw.lower()).strip()

    origin_text = ""
    m = re.search(r"\bfrom\s+(.+)$", lowered)
    if m:
        origin_text = m.group(1).strip(" .")
        lowered = lowered[: m.start()].strip()

    near_text = ""
    m = re.search(r"\bnear\s+(.+)$", lowered)
    if m:
        near_text = m.group(1).strip(" .")
        lowered = lowered[: m.start()].strip()

    for wake in sorted(_WAKE_WORDS, key=len, reverse=True):
        if lowered == wake:
            lowered = ""
            break
        if lowered.startswith(wake + " "):
            lowered = lowered[len(wake):].strip()
            break
    lowered = lowered.strip(" .")

    cuisine = ""
    for word in _CUISINES:
        if re.search(rf"\b{re.escape(word)}s?\b", lowered):
            cuisine = word
            break
    place_type = ""
    for word in _PLACE_TYPES:
        if re.search(rf"\b{re.escape(word)}s?\b", lowered):
            place_type = word
            break

    query = lowered
    return PlaceRequest(
        query=query,
        cuisine=cuisine,
        place_type=place_type,
        near_text=near_text,
        origin_text=origin_text,
    )


def pick_best(places: list[Place]) -> tuple[Place | None, str]:
    """Filter candidates to the single best result.

    Returns ``(place, rating_basis)``. Rated candidates win on rating,
    ties break by review count; with no ratings at all the most complete
    listing wins and the basis is "unrated" so the verdict can say so.
    """
    if not places:
        return None, "none"
    rated = [p for p in places if p.rating is not None]
    if rated:
        best = max(rated, key=lambda p: (p.rating, p.review_count))
        return best, "rated"
    best = max(places, key=lambda p: (p.quality_score, p.name))
    return best, "unrated"


# ---------------------------------------------------------------------------
# Free providers (Nominatim + Overpass + OSRM; no key, no account)
# ---------------------------------------------------------------------------

def _quality_score(tags: dict) -> int:
    """Listing-completeness score, 0-5. Never a star rating."""
    score = 0
    if tags.get("name"):
        score += 1
    if tags.get("cuisine"):
        score += 1
    if tags.get("opening_hours"):
        score += 1
    if tags.get("phone") or tags.get("website") or tags.get("contact:website"):
        score += 1
    if tags.get("addr:street") or tags.get("addr:housenumber"):
        score += 1
    return score


class OverpassPlaceProvider:
    """Keyless OSM provider: Nominatim + Overpass + OSRM.

    Ratings are not available from OpenStreetMap, so every returned
    ``Place`` has ``rating=None``; the flow ranks by ``quality_score``
    and the verdict states the basis.
    """

    def geocode(self, name: str) -> tuple[float, float] | None:
        try:
            resp = httpx.get(
                _NOMINATIM_URL,
                params={"q": name, "format": "json", "limit": 1},
                headers={"User-Agent": _USER_AGENT},
                timeout=_HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            hits = resp.json()
        except Exception as exc:  # network / HTTP / bad JSON
            logger.warning("place-finder geocode failed for %r: %s", name, exc)
            return None
        if not hits:
            return None
        try:
            return float(hits[0]["lat"]), float(hits[0]["lon"])
        except (KeyError, TypeError, ValueError):
            return None

    def search_places(
        self, query: str, near_lat: float, near_lon: float, radius_m: int
    ) -> list[Place]:
        amenity = "restaurant|cafe|fast_food"
        cuisine_filter = ""
        lowered = query.lower()
        for word in _CUISINES:
            if word in lowered and word not in ("coffee", "breakfast", "brunch"):
                cuisine_filter = f'["cuisine"~"{word}"]'
                break
        if "cafe" in lowered or "coffee" in lowered:
            amenity = "cafe"
        ql = (
            "[out:json][timeout:25];"
            f"(node[\"amenity\"~\"{amenity}\"]{cuisine_filter}"
            f"(around:{radius_m},{near_lat},{near_lon});"
            f"way[\"amenity\"~\"{amenity}\"]{cuisine_filter}"
            f"(around:{radius_m},{near_lat},{near_lon}););"
            "out center 50;"
        )
        try:
            resp = httpx.get(
                _OVERPASS_URL,
                params={"data": ql},
                headers={"User-Agent": _USER_AGENT},
                timeout=_HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
        except Exception as exc:
            logger.warning("place-finder Overpass search failed: %s", exc)
            raise
        places: list[Place] = []
        for el in elements:
            tags = el.get("tags") or {}
            name = (tags.get("name") or "").strip()
            if not name:
                continue
            lat = el.get("lat")
            lon = el.get("lon")
            if lat is None or lon is None:
                center = el.get("center") or {}
                lat, lon = center.get("lat"), center.get("lon")
            if lat is None or lon is None:
                continue
            street = tags.get("addr:street", "")
            number = tags.get("addr:housenumber", "")
            address = " ".join(p for p in (number, street) if p)
            kinds = tuple(
                k for k in (tags.get("amenity", ""), tags.get("cuisine", "")) if k
            )
            places.append(
                Place(
                    name=name,
                    kinds=kinds,
                    rating=None,  # OSM carries no star ratings.
                    review_count=0,
                    lat=float(lat),
                    lon=float(lon),
                    address=address,
                    source="OpenStreetMap",
                    quality_score=_quality_score(tags),
                )
            )
        return places

    def route_minutes(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
    ) -> float | None:
        url = (
            f"{_OSRM_URL}/{from_lon},{from_lat};{to_lon},{to_lat}"
            "?overview=false"
        )
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": _USER_AGENT},
                timeout=_HTTP_TIMEOUT,
            )
            resp.raise_for_status()
            routes = resp.json().get("routes") or []
        except Exception as exc:
            logger.warning("place-finder OSRM route failed: %s", exc)
            return None
        if not routes or routes[0].get("duration") is None:
            return None
        try:
            return round(float(routes[0]["duration"]) / 60.0, 1)
        except (TypeError, ValueError):
            return None


# ---------------------------------------------------------------------------
# The flow
# ---------------------------------------------------------------------------

def _fmt_minutes(minutes: float) -> str:
    if minutes < 1:
        return "under a minute"
    if minutes == int(minutes):
        return f"{int(minutes)} minutes"
    return f"{minutes} minutes"


def run_place_finder_flow(
    text: str,
    provider: PlaceSearchProvider,
    speak: Callable[[str], None] | None = None,
    default_center: tuple[float, float] | None = None,
    radius_m: int = _DEFAULT_RADIUS_M,
) -> PlaceFinderResult:
    """Run the full voice place-finder flow for one spoken request.

    ``speak`` is the host's read-aloud step (e.g. FRIDAY's TTS); it is
    called with the verdict text once, after the verdict is built.
    ``default_center`` is the speaker's approximate location, used when
    the request names no area; without any centre the flow asks for one
    instead of guessing.
    """
    request = parse_place_request(text)

    if not request.search_text:
        verdict = (
            "I couldn't tell what kind of place you're looking for. "
            "Try naming a cuisine or a type of place, like Italian "
            "restaurants or coffee shops."
        )
        result = PlaceFinderResult(request=request, verdict=verdict,
                                   error="empty query")
        if speak is not None:
            speak(verdict)
        return result

    # 1. Resolve the search centre.
    centre: tuple[float, float] | None = None
    centre_name = ""
    if request.near_text:
        centre = provider.geocode(request.near_text)
        centre_name = request.near_text
        if centre is None:
            verdict = (
                f"I couldn't find the area {request.near_text}, so I "
                "couldn't search there. Try naming a nearby town, "
                "neighbourhood, or landmark."
            )
            result = PlaceFinderResult(request=request, verdict=verdict,
                                       error="near geocode failed")
            if speak is not None:
                speak(verdict)
            return result
    elif default_center is not None:
        centre = default_center
        centre_name = "your area"
    if centre is None:
        verdict = (
            "I don't know which area to search. Tell me a place to look "
            "near, for example: best Italian restaurant near Bhimavaram."
        )
        result = PlaceFinderResult(request=request, verdict=verdict,
                                   error="no search centre")
        if speak is not None:
            speak(verdict)
        return result

    # 2. Map search.
    try:
        candidates = provider.search_places(
            request.search_text, centre[0], centre[1], radius_m
        )
    except Exception as exc:
        verdict = (
            "The map search failed just now, so I have no places to "
            f"compare ({type(exc).__name__}). Please try again in a moment."
        )
        result = PlaceFinderResult(request=request, verdict=verdict,
                                   error=f"search failed: {exc}")
        if speak is not None:
            speak(verdict)
        return result
    if not candidates:
        verdict = (
            f"I couldn't find any {request.search_text} near {centre_name}."
        )
        result = PlaceFinderResult(request=request, verdict=verdict,
                                   error="no candidates")
        if speak is not None:
            speak(verdict)
        return result

    # 3. Filter to the best result.
    best, basis = pick_best(candidates)

    # 4. Route time from the named start point, when one was given.
    route_minutes: float | None = None
    origin_note = ""
    if request.origin_text:
        origin = provider.geocode(request.origin_text)
        if origin is None:
            origin_note = (
                f" I couldn't find the start point {request.origin_text}, "
                "so I don't have a drive time."
            )
        elif best is not None and best.lat is not None and best.lon is not None:
            route_minutes = provider.route_minutes(
                origin[0], origin[1], best.lat, best.lon
            )
            if route_minutes is None:
                origin_note = (
                    f" I couldn't work out a route from "
                    f"{request.origin_text}."
                )

    # 5. Verdict, built only from what the providers returned.
    assert best is not None  # candidates non-empty => pick_best returns one
    where = f" near {centre_name}" if centre_name else ""
    if basis == "rated":
        rating_text = (
            f", rated {best.rating} stars"
            + (f" from {best.review_count} reviews"
               if best.review_count else "")
        )
    else:
        rating_text = (
            ", and the map I use lists no star ratings, so I picked the "
            "best-listed one"
        )
    address_text = f" It is at {best.address}." if best.address else ""
    if route_minutes is not None:
        route_text = (
            f" From {request.origin_text}, it is about "
            f"{_fmt_minutes(route_minutes)} by car."
        )
    elif origin_note:
        route_text = origin_note
    elif request.origin_text:
        route_text = ""
    else:
        route_text = " Tell me where you are starting from if you want the drive time."
    verdict = (
        f"The best {request.search_text}{where} is {best.name}"
        f"{rating_text}.{address_text}{route_text}"
    )
    result = PlaceFinderResult(
        request=request,
        verdict=verdict,
        place=best,
        candidates=candidates,
        route_minutes=route_minutes,
        rating_basis=basis,
        map_url=best.map_url,
    )
    if speak is not None:
        speak(verdict)
    return result
