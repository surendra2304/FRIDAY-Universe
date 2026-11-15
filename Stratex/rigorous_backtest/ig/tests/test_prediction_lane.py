"""Tests for TASK-IG-STR-11 prediction_lane (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.prediction_lane import (LANE_REGISTRATION, PredictionLaneCollector,
                                implied_probabilities, parse_market)

RAW_STR = {"id": 123, "question": "Will X happen?",
           "outcomes": '["Yes", "No"]',
           "outcomePrices": '["0.62", "0.38"]',
           "volume": "1000.5", "liquidity": "250",
           "endDate": "2027-01-01T00:00:00Z", "active": True,
           "closed": False}
RAW_LIST = {"id": "abc", "question": "Multi?",
            "outcomes": ["A", "B", "C"],
            "outcomePrices": [0.5, 0.3, 0.2],
            "volume": 10, "active": True}


def test_parse_gamma_string_shape():
    m = parse_market(RAW_STR)
    assert m["id"] == "123"
    assert m["outcomes"] == [{"name": "Yes", "price": 0.62},
                             {"name": "No", "price": 0.38}]
    probs = implied_probabilities(m)
    assert abs(sum(probs.values()) - 1.0) < 1e-9


def test_parse_list_shape_and_multi_outcome():
    m = parse_market(RAW_LIST)
    assert len(m["outcomes"]) == 3
    assert abs(sum(implied_probabilities(m).values()) - 1.0) < 1e-9


def test_malformed_records_skipped():
    assert parse_market({"id": 1}) is None
    assert parse_market({"id": 1, "question": "q", "outcomes": ["Yes"],
                         "outcomePrices": []}) is None
    assert parse_market({"id": 1, "question": "q", "outcomes": ["Yes"],
                         "outcomePrices": ["not-a-number"]}) is None
    assert parse_market("nonsense") is None


def test_collector_with_injected_fetcher():
    seen = {}

    def fake_fetcher(url):
        seen["url"] = url
        return [RAW_STR, {"id": 9}, RAW_LIST]

    c = PredictionLaneCollector(fake_fetcher)
    markets, skipped = c.fetch_markets(limit=5)
    assert len(markets) == 2 and skipped == 1
    assert "limit=5" in seen["url"] and "active=true" in seen["url"]


def test_lane_registration_states_the_bar():
    assert LANE_REGISTRATION["status"] == "research_only"
    assert "PF >= 1.2" in LANE_REGISTRATION["evidence_bar"]
    assert "no wallet" in LANE_REGISTRATION["trading"]
