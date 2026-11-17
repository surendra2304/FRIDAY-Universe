"""TRUE ORDER FLOW — signal + execution harness (declaration byte-for-byte).

Family: order_flow_aggtrades (discovery census slate #1). The frozen
declaration (orderflow_declaration.json) governs; if anything here
disagrees with it, the declaration wins.

DATA MODEL. The run-day loader streams Binance Vision futures/um
aggTrades monthly archives and aggregates the prints into bars on the
SAME UTC grid as the Binance Vision klines of the declared timeframe:

  bar = {"t": open_time_ms, "o","h","l","c": kline prices,
         "delta": signed taker base qty, "qty": total base qty,
         "nprints": aggTrades count}

  signed qty of one print = +quantity if is_buyer_maker is False
  (the taker was the BUYER) else -quantity (buyer was maker, so the
  taker was the SELLER). A print belongs to bar t iff
  t <= transact_time < t + timeframe_ms.

FLOW QUANTITY (the only signal input; prices are used for ATR and
execution only):
  CI_L(t) = sum(delta, bars t-L+1..t) / sum(qty, bars t-L+1..t)
  defined only when the full window exists AND sum(qty) > 0.

CELLS (4): {flow_thrust, flow_absorption} x {15m, 1h}.
  L (flow window) = 4 hours  -> 16 bars @15m, 4 bars @1h.
  ATR = Wilder ATR(14) on klines, causal (bars <= signal bar).

flow_thrust (state form):
  at close of bar t, if flat: LONG iff CI_L(t) >= +0.25,
  SHORT iff CI_L(t) <= -0.25. Bracket: SL 2.0*ATR, TP 3.0*ATR.
  No time stop.
flow_absorption (state form):
  price extreme lookback n = 5 hours -> 20 bars @15m, 5 bars @1h.
  LONG iff low(t) < min(low, bars t-n..t-1) AND CI_L(t) > 0;
  SHORT iff high(t) > max(high, bars t-n..t-1) AND CI_L(t) < 0.
  Bracket: SL 1.5*ATR, TP 2.0*ATR, max hold 24 bars @15m / 12 @1h
  (exit at that bar's close if neither level hit first).

EXECUTION (programme harness convention, rd.fastsim): signal on the
close of bar t -> enter at the OPEN of bar t+1; the entry bar is
exit-checked; within a bar the STOP is checked before the TARGET
(worst case); a gap through a level fills at the bar open; one
position at a time per symbol; warmup 260 bars before any signal.
Costs are applied in return space: net = gross - round-trip bps
(16 bps standard, 32 bps for the 2x shadow), both recorded.
"""
from __future__ import annotations

# ---- frozen parameters (declaration: parameters_fixed) ----
THRUST_THETA = 0.25
FLOW_WINDOW_HOURS = 4
EXTREME_LOOKBACK_HOURS = 5
ATR_PERIOD = 14
WARMUP_BARS = 260
COST_RT_BPS = 16.0
COST_RT_BPS_2X = 32.0

_TF = {  # timeframe -> (bar_ms, L bars, extreme-lookback bars, absorption max-hold bars)
    "15m": (900_000, 16, 20, 24),
    "1h": (3_600_000, 4, 5, 12),
}
_THRUST_SL, _THRUST_TP = 2.0, 3.0
_ABS_SL, _ABS_TP = 1.5, 2.0


def aggregate_aggtrades(rows, timeframe):
    """Aggregate raw aggTrades rows into flow bars.

    rows: iterable of (transact_time_ms:int, quantity:float,
    is_buyer_maker:bool), in file order. Returns {bar_open_ms:
    {"delta": float, "qty": float, "nprints": int}}.
    Pure streaming aggregation; no look-ahead is possible here —
    a print lands only in its own bar.
    """
    bar_ms = _TF[timeframe][0]
    out = {}
    for ts, qty, is_buyer_maker in rows:
        b = (int(ts) // bar_ms) * bar_ms
        cell = out.get(b)
        if cell is None:
            cell = out[b] = {"delta": 0.0, "qty": 0.0, "nprints": 0}
        cell["qty"] += qty
        cell["delta"] += -qty if is_buyer_maker else qty
        cell["nprints"] += 1
    return out


def flow_imbalance(bars, t_idx, L, bar_ms):
    """CI_L at bar index t_idx (inclusive). None if the window is
    incomplete: fewer than L bars available, any bar missing its
    flow, the window's bars not time-contiguous (a window spanning
    an archive gap is incomplete by declaration), or total qty 0."""
    if t_idx - L + 1 < 0:
        return None
    d = 0.0
    q = 0.0
    prev_t = None
    for i in range(t_idx - L + 1, t_idx + 1):
        b = bars[i]
        if b.get("delta") is None or b.get("qty") is None:
            return None
        if prev_t is not None and b["t"] - prev_t != bar_ms:
            return None
        prev_t = b["t"]
        d += b["delta"]
        q += b["qty"]
    if q <= 0.0:
        return None
    return d / q


def atr_series(bars, period=ATR_PERIOD):
    """Wilder ATR over bar dicts with h/l/c. Causal: atr[i] uses bars
    <= i. None until `period` true ranges exist."""
    out = [None] * len(bars)
    trs = []
    prev_close = None
    atr = None
    for i, b in enumerate(bars):
        if prev_close is None:
            tr = b["h"] - b["l"]
        else:
            tr = max(b["h"] - b["l"], abs(b["h"] - prev_close),
                     abs(b["l"] - prev_close))
        prev_close = b["c"]
        trs.append(tr)
        if len(trs) == period:
            atr = sum(trs) / period
            out[i] = atr
        elif atr is not None:
            atr = (atr * (period - 1) + tr) / period
            out[i] = atr
    return out


def _bracket_exit(bars, entry_idx, side, entry_price, stop, target,
                  max_hold_bars):
    """Walk bars from the entry bar; stop checked before target in
    every bar; gaps fill at the open; time exit at the close of the
    max-hold-th bar (entry bar counts as bar 1) if neither level hit
    earlier in that bar. Returns (exit_idx, exit_price, reason)."""
    last = len(bars) - 1
    j = entry_idx
    held = 0
    while j <= last:
        b = bars[j]
        held += 1
        o, h, l = b["o"], b["h"], b["l"]
        if side > 0:
            if o <= stop:
                return j, o, "STOP_GAP"
            if o >= target:
                return j, o, "TARGET_GAP"
            if l <= stop:
                return j, stop, "STOP"
            if h >= target:
                return j, target, "TARGET"
        else:
            if o >= stop:
                return j, o, "STOP_GAP"
            if o <= target:
                return j, o, "TARGET_GAP"
            if h >= stop:
                return j, stop, "STOP"
            if l <= target:
                return j, target, "TARGET"
        if max_hold_bars is not None and held >= max_hold_bars:
            return j, b["c"], "TIME"
        j += 1
    return last, bars[last]["c"], "END_OF_DATA"


def simulate(bars, timeframe, mechanism):
    """Run one cell over one symbol's bars. Returns a list of trade
    dicts: entry_time (ms, open of entry bar), side (+1/-1),
    entry_price, exit_price, exit_reason, ret_net (16 bps),
    ret_net_2x (32 bps). Signal uses only completed bars."""
    bar_ms, L, n_ext, abs_max_hold = _TF[timeframe]
    atrs = atr_series(bars)
    trades = []
    i = 0
    n = len(bars)
    while i < n - 1:
        if i < WARMUP_BARS:
            i += 1
            continue
        ci = flow_imbalance(bars, i, L, bar_ms)
        atr = atrs[i]
        side = 0
        if ci is not None and atr is not None and atr > 0:
            if mechanism == "flow_thrust":
                if ci >= THRUST_THETA:
                    side = 1
                elif ci <= -THRUST_THETA:
                    side = -1
            elif mechanism == "flow_absorption":
                if i - n_ext >= 0:
                    prior_lo = min(b["l"] for b in bars[i - n_ext:i])
                    prior_hi = max(b["h"] for b in bars[i - n_ext:i])
                    if bars[i]["l"] < prior_lo and ci > 0:
                        side = 1
                    elif bars[i]["h"] > prior_hi and ci < 0:
                        side = -1
            else:
                raise ValueError(f"unknown mechanism {mechanism}")
        if side == 0:
            i += 1
            continue
        entry_idx = i + 1
        entry_price = bars[entry_idx]["o"]
        if mechanism == "flow_thrust":
            sl_d, tp_d, max_hold = _THRUST_SL * atr, _THRUST_TP * atr, None
        else:
            sl_d, tp_d, max_hold = _ABS_SL * atr, _ABS_TP * atr, abs_max_hold
        stop = entry_price - side * sl_d
        target = entry_price + side * tp_d
        exit_idx, exit_price, reason = _bracket_exit(
            bars, entry_idx, side, entry_price, stop, target, max_hold)
        gross = side * (exit_price - entry_price) / entry_price
        trades.append({
            "entry_time": bars[entry_idx]["t"],
            "exit_time": bars[exit_idx]["t"],
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_reason": reason,
            "ret_net": gross - COST_RT_BPS / 10_000.0,
            "ret_net_2x": gross - COST_RT_BPS_2X / 10_000.0,
        })
        i = exit_idx + 1  # one position at a time; resume after exit bar
    return trades
