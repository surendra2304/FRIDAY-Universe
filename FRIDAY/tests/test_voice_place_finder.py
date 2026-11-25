"""TASK-FRD-050 — voice place-finder flow tests.

The flow is tested against a fake provider with rated fixtures, so the
highest-rated filter is genuinely exercised; the free OSM/OSRM providers
are tested with mocked HTTP. No test here touches the network, and no
verdict in any test invents a place, a rating, or a route time.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import place_finder as pf  # noqa: E402


# ---------------------------------------------------------------------------
# Fake provider
# ---------------------------------------------------------------------------

class FakeProvider:
    """In-memory provider: canned places, geocodes, and route time."""

    def __init__(self, places=None, geocode_map=None, route=12.5,
                 fail_search=False):
        self.places = list(places or [])
        self.geocode_map = dict(geocode_map or {})
        self.route = route
        self.fail_search = fail_search
        self.searched = []
        self.routed = []

    def geocode(self, name):
        return self.geocode_map.get((name or "").lower())

    def search_places(self, query, near_lat, near_lon, radius_m):
        self.searched.append((query, near_lat, near_lon, radius_m))
        if self.fail_search:
            raise RuntimeError("overpass down")
        return list(self.places)

    def route_minutes(self, from_lat, from_lon, to_lat, to_lon):
        self.routed.append((from_lat, from_lon, to_lat, to_lon))
        return self.route


def _rated(name, rating, reviews=0, lat=16.5, lon=81.5):
    return pf.Place(name=name, kinds=("restaurant",), rating=rating,
                    review_count=reviews, lat=lat, lon=lon,
                    address="1 Main Road", source="fake")


# ---------------------------------------------------------------------------
# Request parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,cuisine,ptype,near,origin", [
    ("find the best Italian restaurant near Bhimavaram from home",
     "italian", "restaurant", "bhimavaram", "home"),
    ("best pizza near Hyderabad", "pizza", "", "hyderabad", ""),
    ("coffee shops near MG Road from office",
     "coffee", "coffee shop", "mg road", "office"),
    ("find me a sushi place", "sushi", "", "", ""),
    ("Hey Friday, best Thai restaurant near Kochi",
     "thai", "restaurant", "kochi", ""),
    ("best biryani near Bhimavaram", "", "", "bhimavaram", ""),
])
def test_parse_place_request(text, cuisine, ptype, near, origin):
    req = pf.parse_place_request(text)
    assert req.cuisine == cuisine
    assert req.place_type == ptype
    assert req.near_text == near
    assert req.origin_text == origin


def test_parse_keeps_unknown_words_as_query():
    req = pf.parse_place_request("best biryani near Bhimavaram")
    # "best" is a filler word and is stripped; the dish itself is kept.
    assert req.search_text == "biryani"


# ---------------------------------------------------------------------------
# Highest-rated filter
# ---------------------------------------------------------------------------

def test_pick_best_highest_rating_wins():
    places = [_rated("A", 4.2, 100), _rated("B", 4.8, 10), _rated("C", 4.5, 500)]
    best, basis = pf.pick_best(places)
    assert best.name == "B"
    assert basis == "rated"


def test_pick_best_tie_breaks_by_review_count():
    places = [_rated("A", 4.8, 10), _rated("B", 4.8, 250)]
    best, basis = pf.pick_best(places)
    assert best.name == "B"
    assert basis == "rated"


def test_pick_best_unrated_uses_listing_completeness():
    places = [
        pf.Place(name="Thin", quality_score=1),
        pf.Place(name="Full", quality_score=5),
    ]
    best, basis = pf.pick_best(places)
    assert best.name == "Full"
    assert basis == "unrated"


def test_pick_best_empty_is_none():
    assert pf.pick_best([]) == (None, "none")


# ---------------------------------------------------------------------------
# Full flow with the fake provider
# ---------------------------------------------------------------------------

def _provider(**kwargs):
    geo = {"bhimavaram": (16.54, 81.52), "home": (16.50, 81.50)}
    places = kwargs.pop("places", [
        _rated("Luigi's", 4.8, 132),
        _rated("Pasta Point", 4.3, 400),
    ])
    return FakeProvider(places=places, geocode_map=geo, **kwargs)


def test_flow_happy_path_rated_with_route_and_speak():
    spoken = []
    result = pf.run_place_finder_flow(
        "best Italian restaurant near Bhimavaram from home",
        _provider(), speak=spoken.append)
    assert result.place is not None and result.place.name == "Luigi's"
    assert result.rating_basis == "rated"
    assert result.route_minutes == 12.5
    assert result.map_url.startswith("https://www.openstreetmap.org/")
    assert "Luigi's" in result.verdict
    assert "4.8 stars" in result.verdict
    assert "132 reviews" in result.verdict
    assert "12.5 minutes" in result.verdict
    assert "from home" in result.verdict.lower()
    assert spoken == [result.verdict]
    assert "http" not in result.verdict  # never speak a URL


def test_flow_unrated_says_so_plainly():
    places = [pf.Place(name="Only", quality_score=3, lat=16.5, lon=81.5)]
    result = pf.run_place_finder_flow(
        "best pizza near Bhimavaram", _provider(places=places))
    assert result.place.name == "Only"
    assert result.rating_basis == "unrated"
    assert "lists no star ratings" in result.verdict


def test_flow_no_candidates_is_honest():
    result = pf.run_place_finder_flow(
        "best sushi near Bhimavaram", _provider(places=[]))
    assert result.place is None
    assert "couldn't find any" in result.verdict


def test_flow_unknown_area_is_honest():
    result = pf.run_place_finder_flow(
        "best pizza near Nowhereville", _provider())
    assert result.place is None
    assert "couldn't find the area" in result.verdict


def test_flow_no_area_and_no_centre_asks_for_one():
    result = pf.run_place_finder_flow("best pizza", _provider())
    assert result.place is None
    assert "which area to search" in result.verdict


def test_flow_default_centre_used_when_no_area_named():
    result = pf.run_place_finder_flow(
        "best pizza", _provider(), default_center=(16.54, 81.52))
    assert result.place is not None
    assert result.place.name == "Luigi's"


def test_flow_unknown_start_point_still_names_place_without_route():
    spoken = []
    result = pf.run_place_finder_flow(
        "best Italian restaurant near Bhimavaram from Atlantis",
        _provider(), speak=spoken.append)
    assert result.place is not None and result.place.name == "Luigi's"
    assert result.route_minutes is None
    assert "couldn't find the start point" in result.verdict
    assert spoken == [result.verdict]


def test_flow_provider_error_invents_nothing():
    result = pf.run_place_finder_flow(
        "best pizza near Bhimavaram", _provider(fail_search=True))
    assert result.place is None
    assert "map search failed" in result.verdict
    assert result.error.startswith("search failed")


def test_flow_empty_query_asks_what_kind():
    result = pf.run_place_finder_flow("find me", _provider())
    assert result.place is None
    assert "what kind of place" in result.verdict


def test_flow_without_origin_invites_a_start_point():
    result = pf.run_place_finder_flow(
        "best pizza near Bhimavaram", _provider())
    assert result.place is not None
    assert "starting from" in result.verdict


# ---------------------------------------------------------------------------
# Free providers with mocked HTTP
# ---------------------------------------------------------------------------

def _resp(payload):
    return SimpleNamespace(
        json=lambda: payload,
        raise_for_status=lambda: None,
    )


def test_overpass_provider_parses_nodes_and_ways_and_scores():
    provider = pf.OverpassPlaceProvider()
    payload = {"elements": [
        {"type": "node", "lat": 16.54, "lon": 81.52, "tags": {
            "name": "Luigi's", "amenity": "restaurant", "cuisine": "italian",
            "opening_hours": "Mo-Su 11:00-22:00", "phone": "+91 1",
            "addr:street": "Main Road", "addr:housenumber": "12"}},
        {"type": "way", "center": {"lat": 16.55, "lon": 81.53}, "tags": {
            "name": "Cafe Aroma", "amenity": "cafe"}},
        {"type": "node", "lat": 16.54, "lon": 81.52, "tags": {}},
    ]}
    seen = {}
    def fake_get(url, params=None, headers=None, timeout=None):
        seen["url"] = url
        seen["params"] = params
        return _resp(payload)
    with mock.patch.object(pf.httpx, "get", side_effect=fake_get):
        places = provider.search_places("italian restaurant", 16.54, 81.52, 5000)
    assert seen["url"] == pf._OVERPASS_URL
    assert "italian" in seen["params"]["data"]
    assert "around:5000,16.54,81.52" in seen["params"]["data"]
    assert [p.name for p in places] == ["Luigi's", "Cafe Aroma"]
    luigi, aroma = places
    assert luigi.rating is None  # OSM carries no ratings
    assert luigi.quality_score == 5
    assert luigi.address == "12 Main Road"
    assert luigi.lat == 16.54 and luigi.lon == 81.52
    assert aroma.quality_score == 1
    assert aroma.lat == 16.55  # way centre used


def test_nominatim_geocode_and_empty():
    provider = pf.OverpassPlaceProvider()
    with mock.patch.object(
            pf.httpx, "get",
            return_value=_resp([{"lat": "16.54", "lon": "81.52"}])):
        assert provider.geocode("Bhimavaram") == (16.54, 81.52)
    with mock.patch.object(pf.httpx, "get", return_value=_resp([])):
        assert provider.geocode("Nowhereville") is None


def test_osrm_route_minutes_rounding():
    provider = pf.OverpassPlaceProvider()
    with mock.patch.object(
            pf.httpx, "get",
            return_value=_resp({"routes": [{"duration": 780.0}]})):
        assert provider.route_minutes(16.5, 81.5, 16.54, 81.52) == 13.0
    with mock.patch.object(
            pf.httpx, "get",
            return_value=_resp({"routes": []})):
        assert provider.route_minutes(16.5, 81.5, 16.54, 81.52) is None


# ---------------------------------------------------------------------------
# Tool wiring (LocationMapsTool "find_best_place" action)
# ---------------------------------------------------------------------------

def test_location_maps_tool_find_best_place_runs_flow():
    from friday.tools.builtin.location_maps import LocationMapsTool

    tool = LocationMapsTool(place_provider=_provider())
    with mock.patch(
            "friday.tools.builtin.location_maps.get_current_approximate_location",
            return_value={"lat": 16.54, "lon": 81.52}):
        result = tool.execute(
            action="find_best_place",
            query="best Italian restaurant near Bhimavaram from home")
    assert not result.is_error
    assert "Luigi's" in result.content
    assert "4.8 stars" in result.content
    assert "Map: https://www.openstreetmap.org/" in result.content


def test_location_maps_tool_find_best_place_requires_query():
    from friday.tools.builtin.location_maps import LocationMapsTool

    tool = LocationMapsTool(place_provider=_provider())
    result = tool.execute(action="find_best_place", query="")
    assert result.is_error


def test_location_maps_tool_find_best_place_no_candidates_is_error():
    from friday.tools.builtin.location_maps import LocationMapsTool

    tool = LocationMapsTool(place_provider=_provider(places=[]))
    with mock.patch(
            "friday.tools.builtin.location_maps.get_current_approximate_location",
            return_value={"lat": 16.54, "lon": 81.52}):
        result = tool.execute(
            action="find_best_place",
            query="best sushi near Bhimavaram")
    assert result.is_error
    assert "couldn't find any" in result.content
