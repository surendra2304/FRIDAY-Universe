"""Per-asset-class cost models for TASK-STR-RD-002 (disclosed, per class).

The harness simulator applies costs adversely in price space, per side.
Crypto keeps the BT-001/RD-001 standard (Binance USDT-M taker 5 bps/side
+ 3 bps/side spread+slippage = 16 bps round trip) so RD-002 crypto rows
are directly comparable with BT-001/RD-001. Forex/commodity/index figures
model typical practice-account execution (spread + slippage, no separate
commission on the owner's OANDA practice venue):

  forex majors (EURUSD GBPUSD USDJPY USDCHF AUDUSD USDCAD NZDUSD
                EURGBP EURJPY GBPJPY AUDJPY EURCHF)   6 bps round trip
  forex minors / crosses / exotics (all other pairs) 10 bps round trip
  GOLD 10 | SILVER 14 | WTI 12 | BRENT 12 | NATGAS 20 | COPPER 12 |
  PLATINUM 14 bps round trip
  indices (CFD/futures spread model)                  8 bps round trip

Every near-bar result is re-run at 2x these costs (sensitivity).
"""
from __future__ import annotations

from ..simulator import Costs

CRYPTO = Costs(5.0, 3.0)                      # 16 bps RT (harness standard)
FX_MAJOR = Costs(0.0, 3.0)                    # 6 bps RT
FX_MINOR = Costs(0.0, 5.0)                    # 10 bps RT
INDEX = Costs(0.0, 4.0)                       # 8 bps RT

FX_MAJORS = {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
             "NZDUSD", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURCHF"}

_COMMODITY_RT = {"GOLD": 10.0, "SILVER": 14.0, "WTI": 12.0, "BRENT": 12.0,
                 "NATGAS": 20.0, "COPPER": 12.0, "PLATINUM": 14.0}


def costs_for(panel: str, symbol: str) -> Costs:
    if panel.startswith("crypto"):
        return CRYPTO
    if panel.startswith("forex"):
        return FX_MAJOR if symbol in FX_MAJORS else FX_MINOR
    if panel.startswith("comm"):
        rt = _COMMODITY_RT[symbol]
        return Costs(0.0, rt / 2.0)
    if panel.startswith("idx"):
        return INDEX
    raise ValueError(f"unknown panel {panel}")


def double(costs: Costs) -> Costs:
    """2x-cost sensitivity variant."""
    return Costs(costs.fee_bps_per_side * 2, costs.slip_bps_per_side * 2)


def describe(panel: str, symbol: str) -> dict:
    c = costs_for(panel, symbol)
    return {"round_trip_bps": 2 * (c.fee_bps_per_side + c.slip_bps_per_side),
            "fee_bps_per_side": c.fee_bps_per_side,
            "slip_bps_per_side": c.slip_bps_per_side}
