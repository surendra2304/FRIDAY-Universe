"""Tests for TASK-IG-STR-01 options_pricing (stdlib-only, offline)."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ig.options_pricing import (bs_price, greeks, implied_vol,
                                put_call_parity_residual)

# Hull's textbook example: S=100, K=100, T=1, r=5%, sigma=20%.
HULL = dict(S=100.0, K=100.0, T=1.0, r=0.05, sigma=0.20)


def test_hull_call_put_prices():
    assert abs(bs_price(**HULL, option_type="call") - 10.4506) < 1e-3
    assert abs(bs_price(**HULL, option_type="put") - 5.5735) < 1e-3


def test_put_call_parity_holds():
    for q in (0.0, 0.02):
        assert abs(put_call_parity_residual(q=q, **HULL)) < 1e-9


def test_hull_greeks():
    g = greeks(**HULL, option_type="call")
    assert abs(g["delta"] - 0.6368) < 1e-3
    assert abs(g["gamma"] - 0.01876) < 1e-4
    assert abs(g["vega"] - 37.524) < 1e-2
    assert abs(g["theta"] - (-6.414)) < 1e-2
    assert abs(g["rho"] - 53.232) < 1e-2
    gp = greeks(**HULL, option_type="put")
    assert abs(gp["delta"] - (-0.3632)) < 1e-3
    assert gp["gamma"] == g["gamma"]
    assert gp["vega"] == g["vega"]


def test_implied_vol_round_trip():
    for sigma in (0.05, 0.2, 0.6, 1.4):
        px = bs_price(100.0, 95.0, 0.5, 0.03, sigma, "call")
        iv = implied_vol(px, 100.0, 95.0, 0.5, 0.03, "call")
        assert abs(iv - sigma) < 1e-6
        px = bs_price(100.0, 105.0, 0.25, 0.01, sigma, "put", q=0.01)
        iv = implied_vol(px, 100.0, 105.0, 0.25, 0.01, "put", q=0.01)
        assert abs(iv - sigma) < 1e-6


def test_implied_vol_rejects_arbitrage_price():
    try:
        implied_vol(150.0, 100.0, 100.0, 1.0, 0.05, "call")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for impossible price")


def test_intrinsic_at_expiry_and_validation():
    assert bs_price(120.0, 100.0, 0.0, 0.05, 0.2, "call") == 20.0
    assert bs_price(80.0, 100.0, 0.0, 0.05, 0.2, "put") == 20.0
    for bad in (dict(S=0.0), dict(K=-1.0), dict(T=-0.5), dict(sigma=0.0)):
        args = dict(HULL)
        args.update(bad)
        try:
            bs_price(**args)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError for %r" % (bad,))


def test_deep_itm_otm_limits():
    itm = bs_price(200.0, 100.0, 1.0, 0.05, 0.2, "call")
    assert 104.0 < itm < 105.2  # ~ S - K*e^{-rT} = 104.88, minus small time value effects
    otm = bs_price(50.0, 100.0, 0.25, 0.05, 0.2, "call")
    assert 0.0 <= otm < 0.05
    assert math.isfinite(itm) and math.isfinite(otm)
