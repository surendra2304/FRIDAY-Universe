"""Tests for TASK-IG-STR-07 arb_scanner (stdlib-only, offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.arb_scanner import (find_opportunities, record_opportunities,
                            verify_journal)

Q = [
    {"venue": "A", "symbol": "BTCUSDT", "bid": 100.0, "ask": 100.1, "ts": 1},
    {"venue": "B", "symbol": "BTCUSDT", "bid": 101.0, "ask": 101.1, "ts": 1},
    {"venue": "A", "symbol": "ETHUSDT", "bid": 50.0, "ask": 50.05, "ts": 1},
    {"venue": "B", "symbol": "ETHUSDT", "bid": 50.02, "ask": 50.06, "ts": 1},
]


def test_finds_net_positive_pair_only():
    opps = find_opportunities(Q, fee_bps_per_side=10.0)
    assert len(opps) == 1
    o = opps[0]
    assert o["symbol"] == "BTCUSDT"
    assert o["buy_venue"] == "A" and o["sell_venue"] == "B"
    gross = (101.0 - 100.1) / 100.1 * 10000.0
    assert abs(o["net_bps"] - (gross - 20.0)) < 1e-9
    assert o["paper_only"] is True


def test_fees_wipe_out_thin_edge():
    # same quotes, punitive fees: nothing survives
    assert find_opportunities(Q, fee_bps_per_side=60.0) == []
    # and a buffer can kill the BTC edge too
    assert find_opportunities(Q, fee_bps_per_side=10.0,
                              buffer_bps=100.0) == []


def test_min_net_threshold_and_sorting():
    q = Q + [{"venue": "C", "symbol": "BTCUSDT", "bid": 102.0,
              "ask": 102.1, "ts": 1}]
    opps = find_opportunities(q, fee_bps_per_side=10.0, min_net_bps=50.0)
    assert opps and all(o["net_bps"] > 50.0 for o in opps)
    nets = [o["net_bps"] for o in opps]
    assert nets == sorted(nets, reverse=True)
    assert opps[0]["sell_venue"] == "C"


def test_invalid_quote_rejected():
    try:
        find_opportunities([{"venue": "A", "symbol": "X", "bid": 5.0,
                             "ask": 4.0, "ts": 1}])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for crossed quote")


def test_paper_journal_chain(tmp_path):
    p = str(tmp_path / "arb.jsonl")
    opps = find_opportunities(Q, fee_bps_per_side=10.0)
    assert record_opportunities(p, opps) == 1
    assert record_opportunities(p, opps) == 1
    assert verify_journal(p) is True
    # tampering breaks the chain
    lines = Path(p).read_text().splitlines()
    lines[0] = lines[0].replace("BTCUSDT", "ETHUSDT")
    Path(p).write_text("\n".join(lines) + "\n")
    assert verify_journal(p) is False
