"""Tests for TASK-STR-064 mispricing_scan (stdlib-only, offline).

The scan is verified on synthetic instruments whose market prices are
generated from the BSM pricer itself, so the expected deviations are
known exactly. Live-chain behaviour is checkpoint 2.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.options_pricing import bs_price
from ig.mispricing_scan import ranked_report, render_markdown, scan_mispricing

R = 0.05
SIGMA = 0.20


def _chain():
    """Synthetic 4-instrument chain, market prices = model at SIGMA."""
    specs = [
        ("BTC-30D-60000-C", "call", 60000.0, 60000.0, 30 / 365),
        ("BTC-30D-60000-P", "put", 60000.0, 60000.0, 30 / 365),
        ("BTC-30D-65000-C", "call", 60000.0, 65000.0, 30 / 365),
        ("BTC-90D-55000-P", "put", 60000.0, 55000.0, 90 / 365),
    ]
    out = []
    for name, kind, S, K, T in specs:
        out.append({
            "instrument": name, "option_type": kind, "S": S, "K": K,
            "T": T, "market_price": bs_price(S, K, T, R, SIGMA, kind),
        })
    return out


def test_zero_deviation_when_market_equals_model():
    rows = scan_mispricing(_chain(), R, SIGMA)
    assert len(rows) == 4
    for row in rows:
        assert row["status"] == "OK"
        assert abs(row["rel_dev"]) < 1e-9
        assert abs(row["abs_dev"]) < 1e-6
        assert abs(row["implied_vol"] - SIGMA) < 1e-6
        assert abs(row["iv_dev"]) < 1e-6


def test_flagged_and_ranked_first():
    chain = _chain()
    chain[2]["market_price"] *= 1.20  # 65000 call +20% over model
    rows = scan_mispricing(chain, R, SIGMA)
    ranked = ranked_report(rows)
    assert ranked[0]["instrument"] == "BTC-30D-65000-C"
    assert ranked[0]["status"] == "FLAGGED"
    assert abs(ranked[0]["rel_dev"] - 0.20) < 1e-9
    assert ranked[0]["implied_vol"] > SIGMA  # richer price -> higher IV
    assert all(row["status"] == "OK" for row in ranked[1:])


def test_invalid_price_recorded_not_crash():
    chain = _chain()
    # Deep-ITM put priced far below its intrinsic floor: no implied vol
    # exists (intrinsic ~ K*e^{-rT} - S = ~4754, market 100).
    chain.append({"instrument": "BTC-30D-60000-P-ITM", "option_type": "put",
                  "S": 55000.0, "K": 60000.0, "T": 30 / 365,
                  "market_price": 100.0})
    rows = scan_mispricing(chain, R, SIGMA)
    bad = [row for row in rows if row["instrument"] == "BTC-30D-60000-P-ITM"][0]
    assert bad["status"] == "INVALID_PRICE"
    assert bad["implied_vol"] is None
    assert bad["rel_dev"] < -0.9  # market ~100 vs model ~4800
    assert len(rows) == 5  # scan continued past the bad row


def test_put_call_parity_consistent_ivs():
    rows = scan_mispricing(_chain(), R, SIGMA)
    call = [r for r in rows if r["instrument"] == "BTC-30D-60000-C"][0]
    put = [r for r in rows if r["instrument"] == "BTC-30D-60000-P"][0]
    assert abs(call["implied_vol"] - put["implied_vol"]) < 1e-6


def test_ranking_order():
    chain = _chain()
    chain[0]["market_price"] *= 1.10   # +10%
    chain[1]["market_price"] *= 0.97   # -3%: below 5% threshold, stays OK
    chain[3]["market_price"] *= 1.30   # +30%
    ranked = ranked_report(scan_mispricing(chain, R, SIGMA))
    names = [row["instrument"] for row in ranked]
    assert names[0] == "BTC-90D-55000-P"   # largest |rel dev|
    assert names[1] == "BTC-30D-60000-C"   # +10%
    assert names[2] == "BTC-30D-60000-P"   # -3%
    assert ranked[0]["status"] == "FLAGGED"
    assert ranked[1]["status"] == "FLAGGED"
    assert ranked[2]["status"] == "OK"


def test_malformed_instrument_recorded_as_error():
    chain = _chain()
    chain.append({"instrument": "BROKEN-1", "option_type": "call",
                  "S": 60000.0, "K": 60000.0, "T": 30 / 365})
    chain.append({"instrument": "BROKEN-2", "option_type": "call",
                  "S": -5.0, "K": 60000.0, "T": 30 / 365,
                  "market_price": 100.0})
    rows = scan_mispricing(chain, R, SIGMA)
    assert len(rows) == 6
    errs = [row for row in rows if row["status"] == "ERROR"]
    assert len(errs) == 2
    assert "missing field 'market_price'" in errs[0]["error"]
    assert "spot S must be > 0" in errs[1]["error"]
    ranked = ranked_report(rows)
    assert ranked[-1]["status"] == "ERROR"  # error rows rank last


def test_render_markdown_contains_rows():
    chain = _chain()
    chain[0]["market_price"] *= 1.10
    text = render_markdown(scan_mispricing(chain, R, SIGMA),
                           title="TEST scan")
    assert "# TEST scan" in text
    assert "Scanned 4 instruments: 3 OK, 1 FLAGGED, 0 INVALID_PRICE, 0 ERROR." in text
    assert "BTC-30D-60000-C" in text
    assert "FLAGGED" in text


def test_flag_threshold_is_configurable():
    chain = _chain()
    chain[0]["market_price"] *= 1.10
    rows = scan_mispricing(chain, R, SIGMA, flag_threshold=0.15)
    assert rows[0]["status"] == "OK"  # +10% below the 15% threshold
    rows = scan_mispricing(chain, R, SIGMA, flag_threshold=0.05)
    assert rows[0]["status"] == "FLAGGED"
