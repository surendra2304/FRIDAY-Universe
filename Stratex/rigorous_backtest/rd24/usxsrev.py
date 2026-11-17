"""Harness for TASK-STR-RD-024 — family `us_xs_reversal`.

Implements EXACTLY the frozen declaration in
`declaration/USXSREV_DECLARATION.md` (frozen twin
`usxsrev_declaration.json`). If this code and the declaration
disagree, the declaration wins and this code is wrong.

Construction provenance (the judged mechanism, transplanted):
- Signal/entries: `rd2/families3.py::xs_reversal_fn` +
  `xs_custom_entries` (RD-002 batch 3) — score = trailing return,
  long lowest / short highest, rebalance 5, k = 3, stale-series
  discipline (pad-locate, > 3 bars stale is dropped).
- Execution: `rd/fastsim.py::simulate_entries` bracket_time path —
  entry at the open of signal_bar+1, ATR(14) Wilder EWM taken at the
  signal bar, levels anchored to the entry price, gap-through fills
  at the open, stop before target within a bar, time exit at the
  close of entry_bar + max_bars - 1, one position at a time.
- Costs: `simulator.Costs` / `_net_return` (adverse price-space).
- Judging: `rd2/stats2.py` (BAR, fold_report, positive_folds,
  holdout2, trade_stats, deflated_sharpe) + `walkforward.FOLDS`
  entry-time attribution + SRS TEMPORAL HOLDOUT v1 H1-H4 as adopted
  by the declaration.

Declared equity conventions implemented here (NOT in the judged
mechanism): the dividend adjustment (scores and trades) and the
short-side borrow charge. Both are spelled out in the declaration's
"Declared conventions" section.

This module is self-contained (numpy/pandas/scipy only) so its
SHA-256 can be pinned in the run record.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats as _stats

# ------------------------------------------------------------------
# Frozen constants (declaration: Exact rules / Costs / The bar)
# ------------------------------------------------------------------
UNIVERSE: list[str] = [
    "AAPL", "ABBV", "ACN", "AMD", "AMZN", "AVGO", "BAC", "COST", "CRM",
    "CVX", "GOOGL", "HD", "JNJ", "JPM", "KO", "LLY", "MA", "META",
    "MCD", "MRK", "MSFT", "NFLX", "NVDA", "PEP", "PG", "TSLA", "UNH",
    "V", "WMT", "XOM",
]
CELLS: dict[str, int] = {"rev5_r5": 5, "rev10_r5": 10}  # variant -> lookback
WARMUP = 60            # sessions before the first signal session
REBALANCE = 5          # sessions between signal sessions
K = 3                  # picks per side
SL_ATR = 2.0
TP_ATR = 4.0
MAX_BARS = 5
ATR_PERIOD = 14
STALE_SESSIONS = 3     # judged stale-series discipline
BORROW_RATE_ANNUAL = 0.0025   # declared short-borrow charge, ACT/360
SPEC = {"type": "bracket_time", "sl_atr": SL_ATR, "tp_atr": TP_ATR,
        "max_bars": MAX_BARS}

FOLDS: list[tuple[str, str, str]] = [
    ("W1", "2024-07-01", "2025-01-01"),
    ("W2", "2025-01-01", "2025-07-01"),
    ("W3", "2025-07-01", "2026-01-01"),
    ("W4", "2026-01-01", "2026-07-01"),
    ("W5", "2026-07-01", "2026-11-01"),
]
BAR = {"expectancy_net_gt": 0.0, "profit_factor_net_gte": 1.2,
       "min_oos_trades": 200, "min_positive_fold_share": 0.8}


# ------------------------------------------------------------------
# Costs (port of simulator.Costs / _net_return)
# ------------------------------------------------------------------
@dataclass(frozen=True)
class Costs:
    fee_bps_per_side: float = 5.0
    slip_bps_per_side: float = 3.0

    @property
    def per_side_rate(self) -> float:
        return (self.fee_bps_per_side + self.slip_bps_per_side) / 10000.0


COSTS_1X = Costs(5.0, 3.0)     # 16 bps round trip
COSTS_2X = Costs(10.0, 6.0)    # 32 bps round trip (the shadow)


def _net_return(side: str, entry: float, exit_: float, costs: Costs) -> float:
    r = costs.per_side_rate
    if side == "LONG":
        entry_adj = entry * (1 + r)
        exit_adj = exit_ * (1 - r)
        return (exit_adj - entry_adj) / entry_adj
    entry_adj = entry * (1 - r)
    exit_adj = exit_ * (1 + r)
    return (entry_adj - exit_adj) / entry_adj


@dataclass
class Trade:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: str                    # "LONG" | "SHORT"
    entry_price: float           # raw (pre-cost) fill reference
    exit_price: float            # raw (pre-cost) fill reference
    net_return: float            # net of costs + declared adjustments
    exit_reason: str             # "TP" | "SL" | "TIME"
    borrow_charge: float = 0.0        # declared short-borrow deduction
    dividend_adjustment: float = 0.0  # declared dividend adjustment


# ------------------------------------------------------------------
# Indicators (port of rd.common.atr — Wilder EWM)
# ------------------------------------------------------------------
def atr_wilder(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    tr = pd.concat([
        df["high"] - df["low"],
        abs(df["high"] - df["close"].shift(1)),
        abs(df["low"] - df["close"].shift(1)),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ------------------------------------------------------------------
# Panel handling
#
# A panel is dict[str, pd.DataFrame]; each frame is indexed by
# tz-aware UTC session timestamps (midnight) with columns
# open/high/low/close/volume. Dividends are dict[str, list[(ex_date
# Timestamp, amount float)]].
# ------------------------------------------------------------------
def panel_calendar(panel: dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
    cal = None
    for df in panel.values():
        cal = df.index if cal is None else cal.union(df.index)
    return cal.sort_values()


def _aligned_closes(panel: dict[str, pd.DataFrame],
                    calendar: pd.DatetimeIndex):
    """(ffill-aligned closes, sessions-since-last-real-close) per symbol."""
    closes, ages = {}, {}
    for sym, df in panel.items():
        real = df["close"].reindex(calendar)
        is_real = real.notna().to_numpy()
        closes[sym] = real.ffill()
        age = np.empty(len(calendar), dtype=int)
        last = -10 ** 9
        for i, r in enumerate(is_real):
            if r:
                last = i
            age[i] = i - last
        ages[sym] = age
    return closes, ages


def score_frame(panel: dict[str, pd.DataFrame],
                dividends: dict[str, list[tuple[pd.Timestamp, float]]],
                lookback: int):
    """Dividend-adjusted trailing-return scores on the panel calendar.

    Returns (scores, valid): DataFrames indexed by the calendar with
    one column per symbol. A score is valid only if the symbol's last
    real close is within STALE_SESSIONS of both j and j-lookback
    (declared stale-series discipline).
    """
    calendar = panel_calendar(panel)
    closes, ages = _aligned_closes(panel, calendar)
    close_df = pd.DataFrame(closes, index=calendar)
    base = close_df / close_df.shift(lookback) - 1.0
    scores = base.copy()
    # Dividend add-back: for each ex-date at calendar position p with
    # amount d, it contributes d / close[p-1] to every score whose
    # window (j-lookback, j] contains p.
    cal_pos = {ts: i for i, ts in enumerate(calendar)}
    for sym, divs in (dividends or {}).items():
        if sym not in close_df.columns:
            continue
        col = np.zeros(len(calendar))
        for ex_date, amount in divs:
            ex = pd.Timestamp(ex_date)
            if ex.tzinfo is None:
                ex = ex.tz_localize("UTC")
            # first calendar session >= ex_date is the ex session
            p = cal_pos.get(ex)
            if p is None:
                p = int(calendar.searchsorted(ex))
            if p <= 0 or p >= len(calendar):
                continue
            ref_close = close_df[sym].iloc[p - 1]
            if not np.isfinite(ref_close) or ref_close <= 0:
                continue
            add = amount / float(ref_close)
            # window condition: j - lookback < p <= j  ->  j in [p, p+lookback)
            lo = p
            hi = min(p + lookback - 1, len(calendar) - 1)
            if hi >= lo:
                col[lo:hi + 1] += add
        scores[sym] = scores[sym] + col
    valid = pd.DataFrame(False, index=calendar, columns=close_df.columns)
    for sym in close_df.columns:
        age = ages[sym]
        age_lag = np.full(len(calendar), 10 ** 9)
        if lookback < len(calendar):
            age_lag[lookback:] = age[:-lookback]
        ok = (age <= STALE_SESSIONS) & (age_lag <= STALE_SESSIONS)
        ok &= np.isfinite(scores[sym].to_numpy(dtype=float))
        valid[sym] = ok
    scores = scores.where(valid)
    return scores, valid


def generate_entries(panel: dict[str, pd.DataFrame],
                     dividends: dict[str, list[tuple[pd.Timestamp, float]]],
                     lookback: int, warmup: int = WARMUP,
                     rebalance: int = REBALANCE, k: int = K):
    """Cross-sectional picks, mirroring xs_custom_entries.

    Returns dict[symbol, list[(signal_bar_in_symbol_frame, side)]].
    """
    calendar = panel_calendar(panel)
    scores, _valid = score_frame(panel, dividends, lookback)
    out: dict[str, list] = {s: [] for s in panel}
    for j in range(warmup, len(calendar) - 1, rebalance):
        ranked = sorted(
            (float(scores[s].iloc[j]), s) for s in scores.columns
            if pd.notna(scores[s].iloc[j]))
        if len(ranked) < 2 * k:
            continue
        picks = [(s, "LONG") for _, s in ranked[:k]] + \
                [(s, "SHORT") for _, s in ranked[-k:]]
        t = calendar[j]
        stale_before = calendar[max(0, j - STALE_SESSIONS)]
        for sym, side in picks:
            df = panel[sym]
            pos = df.index.get_indexer([t], method="pad")[0]
            if pos < 0 or pos >= len(df) - 1:
                continue
            if df.index[pos] < stale_before:
                continue
            out[sym].append((int(pos), side))
    return out


# ------------------------------------------------------------------
# Execution (port of rd/fastsim.py bracket_time path)
# ------------------------------------------------------------------
def _first_hit_long(lows, highs, opens, start, sl, tp):
    sl_hits = np.nonzero(lows[start:] <= sl)[0]
    first_sl = (start + sl_hits[0]) if len(sl_hits) else None
    first_tp = None
    if tp is not None:
        tp_hits = np.nonzero(highs[start:] >= tp)[0]
        first_tp = (start + tp_hits[0]) if len(tp_hits) else None
    if first_sl is not None and (first_tp is None or first_sl <= first_tp):
        b = first_sl
        return b, (opens[b] if opens[b] <= sl else sl), "SL"
    if first_tp is not None:
        b = first_tp
        return b, (opens[b] if opens[b] >= tp else tp), "TP"
    return None


def _first_hit_short(lows, highs, opens, start, sl, tp):
    sl_hits = np.nonzero(highs[start:] >= sl)[0]
    first_sl = (start + sl_hits[0]) if len(sl_hits) else None
    first_tp = None
    if tp is not None:
        tp_hits = np.nonzero(lows[start:] <= tp)[0]
        first_tp = (start + tp_hits[0]) if len(tp_hits) else None
    if first_sl is not None and (first_tp is None or first_sl <= first_tp):
        b = first_sl
        return b, (opens[b] if opens[b] >= sl else sl), "SL"
    if first_tp is not None:
        b = first_tp
        return b, (opens[b] if opens[b] <= tp else tp), "TP"
    return None


def simulate_entries(df: pd.DataFrame, entries, atr: np.ndarray,
                     spec: dict, symbol: str, costs: Costs,
                     dividends_sym=None) -> list[Trade]:
    """Simulate (signal_bar, side) entries under the bracket_time spec.

    Entry at the open of signal_bar+1; ATR taken at the signal bar;
    one position at a time (entries inside an open position are
    skipped) — the judged semantics. Declared additions: dividend
    adjustment for trades spanning an ex-date, borrow charge on
    shorts.
    """
    opens = df["open"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    index = df.index
    n = len(df)
    divs = []
    for ex_date, amount in (dividends_sym or []):
        ex = pd.Timestamp(ex_date)
        if ex.tzinfo is None:
            ex = ex.tz_localize("UTC")
        divs.append((ex, float(amount)))
    trades: list[Trade] = []
    cursor = 0
    ordered = sorted(entries, key=lambda e: e[0])
    max_bars = int(spec["max_bars"])
    for sig_bar, side in ordered:
        if sig_bar < cursor or sig_bar + 1 >= n:
            continue
        a = float(atr[sig_bar])
        if not np.isfinite(a) or a <= 0:
            continue
        entry_bar = sig_bar + 1
        entry_price = float(opens[entry_bar])
        if side == "LONG":
            sl = entry_price - float(spec["sl_atr"]) * a
            tp = entry_price + float(spec["tp_atr"]) * a
            hit = _first_hit_long(lows, highs, opens, entry_bar, sl, tp)
        else:
            sl = entry_price + float(spec["sl_atr"]) * a
            tp = entry_price - float(spec["tp_atr"]) * a
            hit = _first_hit_short(lows, highs, opens, entry_bar, sl, tp)
        if hit is not None and hit[0] - entry_bar < max_bars:
            exit_bar, exit_price, reason = hit
        else:
            # judged bracket_time path, verbatim: time exit at the
            # close of entry_bar + max_bars - 1 (or the last bar if
            # the data ends first — same TIME exit in the engine)
            exit_bar = min(entry_bar + max_bars - 1, n - 1)
            exit_price, reason = float(closes[exit_bar]), "TIME"
            if hit is not None and hit[0] <= exit_bar:
                exit_bar, exit_price, reason = hit
        net = _net_return(side, entry_price, float(exit_price), costs)
        entry_date = index[entry_bar]
        exit_date = index[exit_bar]
        div_adj = 0.0
        for ex, amount in divs:
            if entry_date < ex <= exit_date:
                div_adj += (amount / entry_price) if side == "LONG" \
                    else -(amount / entry_price)
        net += div_adj
        borrow = 0.0
        if side == "SHORT":
            days = (exit_date - entry_date).days
            borrow = BORROW_RATE_ANNUAL * days / 360.0
            net -= borrow
        trades.append(Trade(symbol, entry_date, exit_date, side,
                            entry_price, float(exit_price), float(net),
                            reason, borrow_charge=float(borrow),
                            dividend_adjustment=float(div_adj)))
        cursor = exit_bar
    return trades


# ------------------------------------------------------------------
# Metrics and judging (ports of simulator.trade_metrics,
# walkforward.trades_in_window, rd2/stats2.py)
# ------------------------------------------------------------------
def trade_metrics(trades: list[Trade]) -> dict:
    n = len(trades)
    if n == 0:
        return {"trades": 0, "wins": 0, "win_rate": None,
                "expectancy_net": None, "profit_factor_net": None,
                "avg_win_net": None, "avg_loss_net": None,
                "total_return_net": None, "max_drawdown_net": None}
    nets = np.array([t.net_return for t in trades], dtype=float)
    wins = nets[nets > 0]
    losses = nets[nets < 0]
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    if gross_loss > 0:
        pf = gross_profit / gross_loss
    elif gross_profit > 0:
        pf = float("inf")
    else:
        pf = None
    ordered = sorted(trades, key=lambda t: t.entry_time)
    equity = np.cumprod(1.0 + np.array([t.net_return for t in ordered]))
    curve = np.concatenate([[1.0], equity])
    running_max = np.maximum.accumulate(curve)
    max_dd = float((curve / running_max - 1.0).min()) if len(curve) > 1 else 0.0
    return {
        "trades": n,
        "wins": int(len(wins)),
        "win_rate": float(len(wins) / n),
        "expectancy_net": float(nets.mean()),
        "profit_factor_net": (float(pf) if pf is not None
                              and pf != float("inf") else pf),
        "avg_win_net": float(wins.mean()) if len(wins) else None,
        "avg_loss_net": float(losses.mean()) if len(losses) else None,
        "total_return_net": float(np.prod(1.0 + nets) - 1.0),
        "max_drawdown_net": max_dd,
    }


def trades_in_window(trades: list[Trade], start, end) -> list[Trade]:
    out = []
    s = pd.Timestamp(start, tz="UTC") if start else None
    e = pd.Timestamp(end, tz="UTC") if end else None
    for t in trades:
        if s is not None and t.entry_time < s:
            continue
        if e is not None and t.entry_time >= e:
            continue
        out.append(t)
    return out


FOLD_BOUNDS = {fid: (s, e) for fid, s, e in FOLDS}


def fold_report(trades: list[Trade], fold_ids: list[str],
                symbols: list[str]) -> dict:
    per_fold, pooled = {}, []
    for fid in fold_ids:
        s, e = FOLD_BOUNDS[fid]
        ft = trades_in_window(trades, s, e)
        per_fold[fid] = {"oos_start": s, "oos_end": e, **trade_metrics(ft)}
        pooled.extend(ft)
    per_symbol = {}
    for sym in symbols:
        st = [t for t in pooled if t.symbol == sym]
        per_symbol[sym] = trade_metrics(st)
    return {"per_fold": per_fold, "pooled_oos": trade_metrics(pooled),
            "per_symbol_oos": per_symbol, "fold_profile": fold_ids}


def positive_folds(report: dict) -> tuple[int, int]:
    pos = have = 0
    for fid in report["fold_profile"]:
        m = report["per_fold"][fid]
        if (m.get("trades") or 0) > 0:
            have += 1
            if (m.get("expectancy_net") or 0) > 0:
                pos += 1
    return pos, have


def holdout2(report: dict, symbols: list[str]) -> dict:
    """Panel breadth + untouched-subset holdout (stats2 port, exact)."""
    per = report["per_symbol_oos"]
    active = {s: m for s, m in per.items() if (m.get("trades") or 0) >= 20}
    pos = [s for s, m in active.items() if (m.get("expectancy_net") or 0) > 0]
    breadth = (len(pos) / len(active)) if active else 0.0
    profits = {s: (m.get("expectancy_net") or 0.0) * (m.get("trades") or 0)
               for s, m in per.items()}
    total_pos = sum(p for p in profits.values() if p > 0)
    max_share = (max(profits.values()) / total_pos) if total_pos > 0 else 1.0
    cap = 0.5 if len(symbols) >= 5 else 0.8
    subset = sorted(symbols)[2::3]
    sub_trades = [per[s] for s in subset if s in per]
    sub_n = sum(m.get("trades") or 0 for m in sub_trades)
    sub_profit = sum((m.get("expectancy_net") or 0.0) * (m.get("trades") or 0)
                     for m in sub_trades)
    sub_exp = (sub_profit / sub_n) if sub_n else None
    return {
        "symbols_active_min20": len(active),
        "symbols_positive": len(pos),
        "breadth_positive_share": breadth,
        "max_symbol_profit_share": max_share,
        "max_share_cap": cap,
        "untouched_subset": subset,
        "untouched_trades": sub_n,
        "untouched_expectancy": sub_exp,
        "passes": (len(active) >= 3 and breadth >= 0.5
                   and max_share <= cap
                   and sub_n >= 30 and (sub_exp or 0) > 0),
    }


def temporal_holdout(trades: list[Trade], report: dict) -> dict:
    """SRS TEMPORAL HOLDOUT v1 H1-H4 as adopted by the declaration.

    H = trades entered in W5; D = trades entered in W1-W4.
    (H5 is procedural — the burn clause — and is enforced by the run
    procedure, not by this function.)
    """
    hs, he = FOLD_BOUNDS["W5"]
    h_trades = trades_in_window(trades, hs, he)
    d_trades = [t for t in trades
                if pd.Timestamp(FOLD_BOUNDS["W1"][0], tz="UTC")
                <= t.entry_time < pd.Timestamp(hs, tz="UTC")]
    h_m = trade_metrics(h_trades)
    d_m = trade_metrics(d_trades)
    fold_profit = {}
    for fid in report["fold_profile"]:
        m = report["per_fold"][fid]
        fold_profit[fid] = (m.get("expectancy_net") or 0.0) * (m.get("trades") or 0)
    total_pos = sum(p for p in fold_profit.values() if p > 0)
    max_fold_share = (max(fold_profit.values()) / total_pos) \
        if total_pos > 0 else 1.0
    checks = {
        "H1_holdout_size_gte_20": len(h_trades) >= 20,
        "H2_holdout_positive": (h_m.get("expectancy_net") or 0.0) > 0
                               and len(h_trades) > 0,
        "H3_nonholdout_positive": (d_m.get("expectancy_net") or 0.0) > 0
                                  and len(d_trades) > 0,
        "H4_fold_concentration_lte_0.80": total_pos > 0
                                          and max_fold_share <= 0.80,
    }
    return {"holdout_trades": len(h_trades),
            "holdout_metrics": h_m,
            "development_trades": len(d_trades),
            "development_metrics": d_m,
            "fold_profit": fold_profit,
            "max_fold_profit_share": max_fold_share,
            "checks": checks,
            "passes": all(checks.values())}


def trade_stats(trades: list[Trade]) -> dict:
    if not trades:
        return {"n": 0, "sharpe_per_trade": None, "t_stat": None,
                "p_one_sided": None, "skew": None, "kurtosis": None}
    r = np.array([t.net_return for t in trades], dtype=float)
    n = len(r)
    sd = float(r.std(ddof=1)) if n > 1 else 0.0
    sr = float(r.mean() / sd) if sd > 0 else 0.0
    t = sr * math.sqrt(n)
    return {"n": n, "sharpe_per_trade": sr, "t_stat": t,
            "p_one_sided": float(1 - _stats.norm.cdf(t)),
            "skew": float(_stats.skew(r)) if n > 2 else 0.0,
            "kurtosis": float(_stats.kurtosis(r, fisher=False)) if n > 3 else 3.0}


def expected_max_sharpe(n_trials: int, sr_std: float) -> float:
    if n_trials <= 1 or sr_std <= 0:
        return 0.0
    gamma = 0.5772156649
    z1 = _stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = _stats.norm.ppf(1 - 1.0 / (n_trials * math.e))
    return sr_std * ((1 - gamma) * z1 + gamma * z2)


def deflated_sharpe(sr: float, n_trades: int, skew: float, kurtosis: float,
                    n_trials: int, sr_std: float) -> float:
    if n_trades < 3 or sr_std <= 0:
        return 0.0
    sr0 = expected_max_sharpe(n_trials, sr_std)
    denom = math.sqrt(max(1e-12, 1 - skew * sr + (kurtosis - 1) / 4 * sr * sr))
    z = (sr - sr0) * math.sqrt(n_trades - 1) / denom
    return float(_stats.norm.cdf(z))


def judge_cell(trades_1x: list[Trade], trades_2x: list[Trade],
               symbols: list[str], n_final: int,
               dsr_sr_std: float | None = None) -> dict:
    """Assemble the declaration's six bar elements for one cell."""
    fold_ids = [fid for fid, _, _ in FOLDS]
    report = fold_report(trades_1x, fold_ids, symbols)
    po = report["pooled_oos"]
    pos, have = positive_folds(report)
    need = math.ceil(BAR["min_positive_fold_share"] * len(fold_ids))
    ho = holdout2(report, symbols)
    th = temporal_holdout(trades_1x, report)
    shadow = trade_metrics(trades_in_window(
        trades_2x, FOLDS[0][1], FOLDS[-1][2]))
    st = trade_stats(trades_in_window(trades_1x, FOLDS[0][1], FOLDS[-1][2]))
    alpha = 0.05 / max(1, n_final)
    bonf_pass = st["p_one_sided"] is not None and st["p_one_sided"] < alpha
    dsr = None
    if dsr_sr_std is not None and st["n"] >= 3:
        dsr = deflated_sharpe(st["sharpe_per_trade"] or 0.0, st["n"],
                              st["skew"] or 0.0, st["kurtosis"] or 3.0,
                              n_final, dsr_sr_std)
    n_oos = po.get("trades") or 0
    checks = {
        "pooled_expectancy_gt_0": (po.get("expectancy_net") or 0.0) > 0,
        "pooled_pf_gte_1.2": (po.get("profit_factor_net") or 0) >= 1.2,
        "min_oos_trades_200": n_oos >= BAR["min_oos_trades"],
        "positive_folds": pos >= need and have >= len(fold_ids) - 1,
        "panel_holdout_passes": bool(ho["passes"]),
        "temporal_holdout_passes": bool(th["passes"]),
        "cost_shadow_expectancy_gt_0": (shadow.get("expectancy_net") or 0.0) > 0,
        "cost_shadow_pf_gte_1.2": (shadow.get("profit_factor_net") or 0) >= 1.2,
        "bonferroni_pass": bool(bonf_pass),
    }
    if n_oos < BAR["min_oos_trades"]:
        verdict = "insufficient OOS trades"
    elif all(checks.values()):
        verdict = "PASS"
    else:
        verdict = "FAIL"
    return {"checks": checks, "passes_bar": verdict == "PASS",
            "verdict": verdict,
            "report": report, "panel_holdout": ho,
            "temporal_holdout": th, "shadow_pooled_oos": shadow,
            "significance": {**st, "bonferroni_alpha": alpha,
                             "bonferroni_pass": bool(bonf_pass),
                             "deflated_sharpe_reported": dsr,
                             "n_final": n_final},
            "positive_folds": pos, "folds_with_trades": have,
            "positive_folds_needed": need}


def run_cell(panel: dict[str, pd.DataFrame],
             dividends: dict[str, list[tuple[pd.Timestamp, float]]],
             lookback: int, costs: Costs):
    """Entries + simulation for one cell at one cost level."""
    entries = generate_entries(panel, dividends, lookback)
    all_trades: list[Trade] = []
    for sym, df in panel.items():
        a = atr_wilder(df).to_numpy(dtype=float)
        all_trades.extend(simulate_entries(
            df, entries.get(sym, []), a, SPEC, sym, costs,
            dividends_sym=(dividends or {}).get(sym, [])))
    return all_trades, entries
