"""TASK-IG2-STR-07 — whale-flow tracker tests (no network; injected fetcher)."""

import pytest

from research.whale_flow_tracker import (
    RESEARCH_ONLY,
    WhaleFlowTracker,
    detect_dex_anomalies,
    detect_spot_volume_spike,
    detect_tvl_shifts,
    parse_coingecko_market,
    parse_defillama_chains,
    parse_dexscreener_pairs,
)

NOW = 1_700_000_000.0

DEX_PAYLOAD = {
    "pairs": [
        {"baseToken": {"symbol": "SOL"}, "volume": {"h24": 1_000_000, "h1": 300_000},
         "txns": {"h1": {"buys": 900, "sells": 300}},
         "liquidity": {"usd": 500_000}},
        {"baseToken": {"symbol": "SOL"}, "volume": {"h24": 200_000, "h1": 20_000},
         "txns": {"h1": {"buys": 100, "sells": 90}},
         "liquidity": {"usd": 50_000}},
        {"baseToken": {"symbol": "OTHER"}, "volume": {"h24": 9_999_999, "h1": 9_999_999},
         "txns": {"h1": {"buys": 9999, "sells": 1}},
         "liquidity": {"usd": 1}},
    ]
}

CG_PAYLOAD = [
    {"id": "bitcoin", "current_price": 97000.0, "total_volume": 60_000_000_000,
     "price_change_percentage_24h": 2.5},
    {"id": "solana", "current_price": 210.0, "total_volume": 5_000_000_000,
     "price_change_percentage_24h": -1.0},
]

LLAMA_PAYLOAD = [
    {"name": "Ethereum", "change_1d": -7.5},
    {"name": "Solana", "change_1d": 1.2},
    {"name": "Arbitrum", "change_1d": None},
]


def test_research_only_flag():
    assert RESEARCH_ONLY is True


def test_parse_dexscreener_aggregates_only_matching_symbol():
    stats = parse_dexscreener_pairs(DEX_PAYLOAD, "SOL")
    assert stats.pair_count == 2
    assert stats.volume_h24 == 1_200_000
    assert stats.volume_h1 == 320_000
    assert stats.buys_h1 == 1000 and stats.sells_h1 == 390
    assert stats.liquidity_usd == 550_000


def test_detect_dex_anomalies_fires_spike_and_imbalance():
    stats = parse_dexscreener_pairs(DEX_PAYLOAD, "SOL")
    kinds = {s.kind for s in detect_dex_anomalies(stats, NOW)}
    assert kinds == {"DEX_VOLUME_SPIKE", "DEX_FLOW_IMBALANCE"}


def test_detect_dex_anomalies_quiet_market_is_silent():
    payload = {"pairs": [{"baseToken": {"symbol": "SOL"},
                          "volume": {"h24": 1_000_000, "h1": 10_000},
                          "txns": {"h1": {"buys": 60, "sells": 55}},
                          "liquidity": {"usd": 10_000}}]}
    stats = parse_dexscreener_pairs(payload, "SOL")
    assert detect_dex_anomalies(stats, NOW) == []


def test_parse_coingecko_market():
    m = parse_coingecko_market(CG_PAYLOAD, "bitcoin")
    assert m["volume_24h"] == 60_000_000_000
    assert parse_coingecko_market(CG_PAYLOAD, "dogecoin") is None
    assert parse_coingecko_market({"unexpected": 1}, "bitcoin") is None


def test_spot_volume_spike_threshold():
    assert detect_spot_volume_spike("BTC", 160.0, 100.0, NOW) is not None
    assert detect_spot_volume_spike("BTC", 120.0, 100.0, NOW) is None
    assert detect_spot_volume_spike("BTC", 160.0, None, NOW) is None


def test_tvl_shifts():
    changes = parse_defillama_chains(LLAMA_PAYLOAD)
    signals = detect_tvl_shifts(changes, ["Ethereum", "Solana", "Arbitrum"], NOW)
    assert [s.symbol for s in signals] == ["ETHEREUM"]


def _fake_fetch(url, params=None, timeout=15.0):
    if "dexscreener" in url:
        return DEX_PAYLOAD
    if "coingecko" in url:
        return CG_PAYLOAD
    if "llama" in url:
        return LLAMA_PAYLOAD
    raise AssertionError(url)


def test_poll_once_end_to_end_and_dedupe(tmp_path):
    tracker = WhaleFlowTracker(
        signals_path=str(tmp_path / "signals.jsonl"),
        watchlist={"SOL": "solana"}, tvl_chains=["Ethereum"],
        fetch_json=_fake_fetch)
    first = tracker.poll_once(now=NOW)
    kinds = {s.kind for s in first}
    assert "DEX_VOLUME_SPIKE" in kinds and "TVL_SHIFT" in kinds
    # Same anomalies inside the dedupe window are not re-emitted.
    second = tracker.poll_once(now=NOW + 60)
    assert all(s.kind not in ("DEX_VOLUME_SPIKE", "TVL_SHIFT") for s in second)
    stored = tracker.recent_signals()
    assert stored and stored[0]["observed_at"] == NOW


def test_poll_once_survives_dead_endpoint(tmp_path):
    def dead_fetch(url, params=None, timeout=15.0):
        raise ConnectionError("endpoint down")

    tracker = WhaleFlowTracker(
        signals_path=str(tmp_path / "signals.jsonl"), fetch_json=dead_fetch)
    assert tracker.poll_once(now=NOW) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
