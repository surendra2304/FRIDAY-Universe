"""Cross-sectional short-term reversal, volume-climax conditioned —
signal + execution harness, PRE-DECLARED.

TASK-STR-RD-019 (discovery census slate #3). RESEARCH-ONLY /
DEMO-ONLY.

The frozen declaration governs this family:
``xsrev_declaration.json`` (SHA-256
ffc3c573071ee8014d99d125cbc08551b39f47fb756696e603124b81e86f31f1) +
``XSREV_DECLARATION.md`` (repo home: Stratex/rigorous_backtest/rd19/).
If this code and the declaration disagree, the declaration wins and
the code is wrong. This module was staged in
~/workspace/str-xsrev/harness/ BEFORE the declared run; the run is a
separate, later, gated step (see ../RUNBOOK.md). Nothing here has
been run against the real panel.

Lineage (declared, not hidden): the ranking core is RD-002 batch-3
family xs_reversal variant rev5_r5, byte-for-byte in construction —
trailing 5-bar return rank, long the 3 lowest / short the 3 highest,
rebalance every 5 bars, ATR(14) bracket exits (SL 2.0x, TP 4.0x,
max_bars 5), next-bar-open entries, programme costs. RD-002 judged
that unconditional construction on crypto30 and it lost in every
cell (1d rev5_r5: expectancy -0.169%/trade, PF 0.957). The SINGLE
difference here is the entry gate: a pick is entered only if the
pick's own ranking-window volume is a climax (>= 1.5x the median of
its 12 preceding non-overlapping 5-bar window volume sums). See the
declaration's differentiation section.

The declared rules, implemented exactly:

1. Daily bars — aggregated from the declared 15m panel by UTC
   calendar day (open first / high max / low min / close last /
   volume sum), complete 96-bar days only. All symbols must share
   the identical daily index; the harness aborts otherwise.
2. Signal bars — j >= 64 and (j - 64) mod 5 == 0 on the common
   daily index, completed bars only.
3. Ranking — score_s = close_s[j] / close_s[j-5] - 1; ascending by
   (score, symbol); LONG the first 3, SHORT the last 3. A symbol is
   eligible iff closes j-5..j, volumes j-64..j and a positive
   ATR(14) at j are all valid; fewer than 6 eligible -> no trades
   at that rebalance.
4. Gate — V_win = sum of volume over bars j-4..j; V_base = median
   (statistics.median) of the 12 preceding non-overlapping 5-bar
   window volume sums (bars j-64..j-5). Enter iff V_base > 0 and
   V_win >= 1.5 * V_base. NO substitution.
5. Entry — at the OPEN of bar j+1; entry time = bar j+1's time.
6. Exits — ATR(14) Wilder (rd/common.py atr recursion) at bar j;
   LONG stop = entry - 2.0*ATR_j, target = entry + 4.0*ATR_j
   (SHORT mirrored). Programme simulator order from the entry bar
   onward: gap through a level fills at the bar open; stop checked
   before target within a bar. No barrier within bars j+1..j+5 ->
   TIME exit at the close of bar j+5. Data ends first ->
   END_OF_DATA at the final close.
7. Frequency — one position at a time per symbol; a pick arriving
   while a position is open on that symbol is skipped and counted.
8. Costs — the programme model (simulator.Costs): Binance USDT-M
   taker fee 5 bps + spread/slippage 3 bps per side, applied
   adversely in price space; round trip 16 bps. The 2x shadow is
   Costs(10, 6) = 32 bps round trip. Both must pass at the run.

Bars are plain dicts {"time", "open", "high", "low", "close",
"volume"}; "time" is a datetime/Timestamp or ISO-8601 string.
Stdlib only, Python 3.10-compatible, fully deterministic.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Sequence

LOOKBACK = 5            # frozen by the declaration (RD-002 rev5)
REBALANCE = 5           # frozen by the declaration
K = 3                   # frozen by the declaration (per side)
CLIMAX_MULTIPLE = 1.5   # frozen by the declaration
BASELINE_WINDOWS = 12   # frozen by the declaration (12 windows of 5 bars)
WINDOW = 5              # bars per volume window (== LOOKBACK)
WARMUP = BASELINE_WINDOWS * WINDOW + LOOKBACK - 1  # 64: first signal bar
SL_ATR = 2.0            # frozen by the declaration
TP_ATR = 4.0            # frozen by the declaration
MAX_BARS = 5            # frozen by the declaration
ATR_PERIOD = 14         # frozen by the declaration


# ------------------------------------------------------------------ costs
@dataclass(frozen=True)
class Costs:
    """Mirror of rigorous_backtest.simulator.Costs (same semantics:
    per-side fee + slippage applied adversely in price space)."""
    fee_bps_per_side: float = 5.0
    slip_bps_per_side: float = 3.0

    @property
    def per_side_rate(self) -> float:
        return (self.fee_bps_per_side + self.slip_bps_per_side) / 10000.0

    def describe(self) -> dict:
        return {
            "venue_model": "Binance USDT-M futures, taker",
            "fee_bps_per_side": self.fee_bps_per_side,
            "spread_slippage_bps_per_side": self.slip_bps_per_side,
            "round_trip_bps": 2 * (self.fee_bps_per_side + self.slip_bps_per_side),
        }


COSTS = Costs()                 # programme model: 16 bps round trip
COSTS_2X = Costs(10.0, 6.0)     # 2x shadow: 32 bps round trip


def net_return(side: str, entry: float, exit_: float, costs: Costs) -> float:
    """Identical formula to rigorous_backtest.simulator._net_return."""
    r = costs.per_side_rate
    if side == "LONG":
        entry_adj = entry * (1 + r)
        exit_adj = exit_ * (1 - r)
        return (exit_adj - entry_adj) / entry_adj
    entry_adj = entry * (1 - r)
    exit_adj = exit_ * (1 + r)
    return (entry_adj - exit_adj) / entry_adj


# ------------------------------------------------------------- aggregation
def _as_datetime(t: Any) -> datetime:
    if isinstance(t, datetime):
        return t
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def aggregate_daily(bars: Sequence[dict]) -> list[dict]:
    """Aggregate 15m bars to UTC daily bars (declaration rule):
    complete 96-bar days only; OHLC first/max/min/last; volume sum.
    Input must be time-ordered. Daily bar time = 00:00 UTC that day."""
    out: list[dict] = []
    cur_key = None
    cur: dict | None = None
    count = 0
    for b in bars:
        t = _as_datetime(b["time"])
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        key = t.date()
        if key != cur_key:
            if cur is not None and count == 96:
                out.append(cur)
            cur_key = key
            cur = {"time": datetime(key.year, key.month, key.day,
                                    tzinfo=timezone.utc),
                   "open": float(b["open"]), "high": float(b["high"]),
                   "low": float(b["low"]), "close": float(b["close"]),
                   "volume": float(b["volume"])}
            count = 1
        else:
            cur["high"] = max(cur["high"], float(b["high"]))
            cur["low"] = min(cur["low"], float(b["low"]))
            cur["close"] = float(b["close"])
            cur["volume"] += float(b["volume"])
            count += 1
    if cur is not None and count == 96:
        out.append(cur)
    return out


# ------------------------------------------------------------------- ATR
def atr_series(bars: Sequence[dict], period: int = ATR_PERIOD) -> list[float]:
    """Wilder ATR, identical recursion to rd/common.py atr():
    TR[0] = high - low; TR[i] = max(range, |high - prev close|,
    |low - prev close|); ATR = EWM alpha = 1/period, adjust=False."""
    n = len(bars)
    out = [0.0] * n
    if n == 0:
        return out
    alpha = 1.0 / period
    prev_close = float(bars[0]["close"])
    tr0 = float(bars[0]["high"]) - float(bars[0]["low"])
    out[0] = tr0
    for i in range(1, n):
        h, l, pc = float(bars[i]["high"]), float(bars[i]["low"]), prev_close
        tr = max(h - l, abs(h - pc), abs(l - pc))
        out[i] = out[i - 1] + alpha * (tr - out[i - 1])
        prev_close = float(bars[i]["close"])
    return out


# ------------------------------------------------------------------ picks
def _valid(x: Any) -> bool:
    return x is not None and isinstance(x, (int, float)) and x == x \
        and x not in (float("inf"), float("-inf"))


@dataclass(frozen=True)
class Pick:
    symbol: str
    signal_index: int   # j on the common daily index
    time: Any           # signal bar time
    side: str           # "LONG" | "SHORT"
    score: float        # trailing 5-bar return at j
    atr: float          # ATR(14) at j
    v_win: float        # ranking-window volume sum (bars j-4..j)
    v_base: float       # median of the 12 baseline window sums
    climax: bool        # gate outcome

    def as_dict(self) -> dict[str, Any]:
        return {"symbol": self.symbol, "signal_index": self.signal_index,
                "time": str(self.time), "side": self.side,
                "score": self.score, "atr": self.atr, "v_win": self.v_win,
                "v_base": self.v_base, "climax": self.climax}


def is_signal_bar(j: int, n: int) -> bool:
    """Declared grid: j >= 64, (j - 64) mod 5 == 0, and the entry bar
    j+1 must exist."""
    return j >= WARMUP and (j - WARMUP) % REBALANCE == 0 and j + 1 < n


def generate_picks(panel: dict[str, list[dict]]) -> tuple[list[Pick], dict]:
    """All ranked picks on the declared grid, each with its gate
    outcome (climax). Picks with climax=False are recorded but never
    entered (no substitution). Aborts (ValueError) if the symbols do
    not share an identical daily index."""
    symbols = sorted(panel.keys())
    ref_sym = symbols[0]
    ref_times = [b["time"] for b in panel[ref_sym]]
    n = len(ref_times)
    for s in symbols:
        if [b["time"] for b in panel[s]] != ref_times:
            raise ValueError(f"daily index mismatch for {s}")
    closes = {s: [float(b["close"]) for b in panel[s]] for s in symbols}
    volumes = {s: [float(b["volume"]) for b in panel[s]] for s in symbols}
    atrs = {s: atr_series(panel[s]) for s in symbols}
    picks: list[Pick] = []
    stats = {"signal_bars": 0, "rebalances_thin": 0, "picks_ranked": 0,
             "picks_climax": 0, "picks_gated_out": 0}
    for j in range(n):
        if not is_signal_bar(j, n):
            continue
        stats["signal_bars"] += 1
        scored: list[tuple[float, str]] = []
        for s in symbols:
            c = closes[s]
            v = volumes[s]
            if not all(_valid(c[m]) for m in range(j - LOOKBACK, j + 1)):
                continue
            if not all(_valid(v[m]) for m in range(j - WARMUP, j + 1)):
                continue
            if not (_valid(atrs[s][j]) and atrs[s][j] > 0.0):
                continue
            scored.append((c[j] / c[j - LOOKBACK] - 1.0, s))
        if len(scored) < 2 * K:
            stats["rebalances_thin"] += 1
            continue
        scored.sort()  # (score, symbol) — RD-002 tie-break
        chosen = [(s, "LONG") for _, s in scored[:K]] + \
                 [(s, "SHORT") for _, s in scored[-K:]]
        score_of = {s: sc for sc, s in scored}
        for s, side in chosen:
            v = volumes[s]
            v_win = sum(v[j - WINDOW + 1: j + 1])
            windows = [sum(v[j - WARMUP + WINDOW * w:
                              j - WARMUP + WINDOW * (w + 1)])
                       for w in range(BASELINE_WINDOWS)]
            v_base = statistics.median(windows)
            climax = v_base > 0.0 and v_win >= CLIMAX_MULTIPLE * v_base
            picks.append(Pick(s, j, ref_times[j], side, score_of[s],
                              atrs[s][j], v_win, v_base, climax))
            stats["picks_ranked"] += 1
            if climax:
                stats["picks_climax"] += 1
            else:
                stats["picks_gated_out"] += 1
    return picks, stats


# ----------------------------------------------------------------- trades
@dataclass
class Trade:
    """Field-compatible with rigorous_backtest.simulator.Trade, plus
    the bracket levels for auditability."""
    symbol: str
    entry_time: Any
    exit_time: Any
    side: str           # "LONG" | "SHORT"
    entry_price: float  # raw (pre-cost) fill reference
    exit_price: float   # raw (pre-cost) fill reference
    net_return: float   # fraction of entry price, net of all costs
    exit_reason: str    # "TP" | "SL" | "TIME" | "END_OF_DATA"
    stop: float = 0.0
    target: float = 0.0


def _check_exit(side: str, stop: float, target: float,
                bar: dict) -> tuple[float | None, str | None]:
    """Programme simulator order: gap through a level fills at the
    bar open; the stop is checked before the target (worst case)."""
    o, h, l = float(bar["open"]), float(bar["high"]), float(bar["low"])
    if side == "LONG":
        if o <= stop:
            return o, "SL"
        if l <= stop:
            return stop, "SL"
        if o >= target:
            return o, "TP"
        if h >= target:
            return target, "TP"
    else:
        if o >= stop:
            return o, "SL"
        if h >= stop:
            return stop, "SL"
        if o <= target:
            return o, "TP"
        if l <= target:
            return target, "TP"
    return None, None


def simulate_symbol(bars: Sequence[dict], symbol: str,
                    picks: Sequence[Pick],
                    costs: Costs = COSTS) -> tuple[list[Trade], dict]:
    """Declared execution for one symbol over its gate-passing picks
    (in signal order). One position at a time; a pick whose entry
    bar falls inside an open position's managed window is skipped
    and counted."""
    n = len(bars)
    trades: list[Trade] = []
    stats = {"entered": 0, "skipped_open": 0}
    busy_until = -1  # last managed bar index of the open/last position
    for p in picks:
        if not p.climax:
            continue
        j = p.signal_index
        entry_bar = j + 1
        if entry_bar <= busy_until:
            stats["skipped_open"] += 1
            continue
        entry = float(bars[entry_bar]["open"])
        sign = 1.0 if p.side == "LONG" else -1.0
        stop = entry - sign * SL_ATR * p.atr
        target = entry + sign * TP_ATR * p.atr
        last = min(j + MAX_BARS, n - 1)
        exit_price = None
        reason = None
        exit_bar = last
        for m in range(entry_bar, last + 1):
            ep, rs = _check_exit(p.side, stop, target, bars[m])
            if ep is not None:
                exit_price, reason, exit_bar = ep, rs, m
                break
        if exit_price is None:
            exit_bar = last
            exit_price = float(bars[last]["close"])
            reason = "TIME" if j + MAX_BARS <= n - 1 else "END_OF_DATA"
        trades.append(Trade(symbol, bars[entry_bar]["time"],
                            bars[exit_bar]["time"], p.side, entry,
                            exit_price,
                            net_return(p.side, entry, exit_price, costs),
                            reason, stop, target))
        stats["entered"] += 1
        busy_until = exit_bar
    return trades, stats


def simulate(panel: dict[str, list[dict]],
             costs: Costs = COSTS) -> tuple[list[Trade], dict]:
    """Declared execution over the whole panel. Returns (trades,
    stats) with the pick/gate census included."""
    picks, stats = generate_picks(panel)
    by_symbol: dict[str, list[Pick]] = {s: [] for s in panel}
    for p in picks:
        by_symbol[p.symbol].append(p)
    trades: list[Trade] = []
    stats = {**stats, "entered": 0, "skipped_open": 0}
    for s in sorted(panel.keys()):
        ts, st = simulate_symbol(panel[s], s, by_symbol[s], costs)
        trades.extend(ts)
        stats["entered"] += st["entered"]
        stats["skipped_open"] += st["skipped_open"]
    return trades, stats
