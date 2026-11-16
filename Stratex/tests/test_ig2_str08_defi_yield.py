"""TASK-IG2-STR-08 — DeFi LP/yield monitor tests (no network; injected fetcher)."""

import pytest

from research.defi_yield_monitor import (
    DefiYieldMonitor,
    PoolSnapshot,
    diff_snapshots,
    parse_pools,
    select_watched,
)

NOW = 1_700_000_000.0

PAYLOAD_V1 = {"data": [
    {"pool": "p-usdc-eth", "project": "aave-v3", "symbol": "USDC", "chain": "Ethereum",
     "apy": 4.0, "apyBase": 4.0, "apyReward": None, "tvlUsd": 100_000_000},
    {"pool": "p-usdc-arb", "project": "aave-v3", "symbol": "USDC", "chain": "Arbitrum",
     "apy": 5.0, "apyBase": 5.0, "apyReward": None, "tvlUsd": 10_000_000},
    {"pool": "p-lido", "project": "lido", "symbol": "STETH", "chain": "Ethereum",
     "apy": 3.0, "apyBase": 3.0, "apyReward": None, "tvlUsd": 9_000_000_000},
]}

PAYLOAD_V2 = {"data": [
    {"pool": "p-usdc-eth", "project": "aave-v3", "symbol": "USDC", "chain": "Ethereum",
     "apy": 5.2, "apyBase": 5.2, "apyReward": None, "tvlUsd": 130_000_000},
    {"pool": "p-lido", "project": "lido", "symbol": "STETH", "chain": "Ethereum",
     "apy": 3.05, "apyBase": 3.05, "apyReward": None, "tvlUsd": 9_100_000_000},
]}

WATCH = [{"project": "aave-v3", "symbol": "USDC"}, {"pool_id": "p-lido"}]


def test_parse_pools_normalizes():
    pools = parse_pools(PAYLOAD_V1)
    assert len(pools) == 3
    assert pools[0]["apy"] == 4.0 and pools[0]["apy_reward"] is None
    assert parse_pools(None) == [] and parse_pools({}) == []


def test_select_watched_prefers_highest_tvl_for_project_symbol():
    selected = select_watched(parse_pools(PAYLOAD_V1), WATCH)
    ids = {p["pool_id"] for p in selected}
    assert ids == {"p-usdc-eth", "p-lido"}  # Ethereum USDC pool beats Arbitrum on TVL


def _snap(apy, tvl, when=NOW):
    return PoolSnapshot(pool_id="p1", project="aave-v3", symbol="USDC",
                        chain="Ethereum", apy=apy, apy_base=apy, apy_reward=None,
                        tvl_usd=tvl, observed_at=when)


def test_diff_first_snapshot_is_new_pool():
    changes = diff_snapshots(None, _snap(4.0, 100.0))
    assert [c.kind for c in changes] == ["NEW_POOL"]


def test_diff_detects_apy_and_tvl_moves():
    changes = diff_snapshots(_snap(4.0, 100_000_000), _snap(5.2, 130_000_000, NOW + 60))
    assert {c.kind for c in changes} == {"APY_MOVE", "TVL_MOVE"}


def test_diff_small_moves_are_silent():
    assert diff_snapshots(_snap(4.0, 100_000_000), _snap(4.1, 105_000_000, NOW + 60)) == []


def test_poll_once_reports_changes_across_polls(tmp_path):
    payloads = iter([PAYLOAD_V1, PAYLOAD_V2])
    monitor = DefiYieldMonitor(
        snapshots_path=str(tmp_path / "snaps.jsonl"), watchlist=WATCH,
        fetch_json=lambda url, timeout=30.0: next(payloads))
    first = monitor.poll_once(now=NOW)
    assert {c.kind for c in first} == {"NEW_POOL"}
    second = monitor.poll_once(now=NOW + 3600)
    kinds = {(c.pool_id, c.kind) for c in second}
    assert ("p-usdc-eth", "APY_MOVE") in kinds and ("p-usdc-eth", "TVL_MOVE") in kinds
    assert all(c.pool_id != "p-lido" for c in second)  # 3.00 -> 3.05 is noise
    note = monitor.research_note(second)
    assert "aave-v3 USDC" in note and "APY 5.20%" in note


def test_poll_once_dead_api_returns_empty(tmp_path):
    def dead(url, timeout=30.0):
        raise ConnectionError("down")

    monitor = DefiYieldMonitor(snapshots_path=str(tmp_path / "s.jsonl"),
                               watchlist=WATCH, fetch_json=dead)
    assert monitor.poll_once(now=NOW) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
