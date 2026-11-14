"""Factory-family evaluation: re-run the 204-variant selection honestly.

The signal logic below replicates, function for function, the legacy
research/strategy_factory/mass_backtester.py (the code whose single-window
in-sample ranking promoted factory_winner_1..5). Replication fidelity is not
assumed: run_validation() compares this implementation against the legacy
backtest function itself on real data and reports any divergence.

What changes versus the legacy run — deliberately:
- Walk-forward: in each fold, variants are ranked ONLY on trades entered
  before the fold (in-sample segment); the selected top-5 are then judged
  ONLY on trades entered inside the fold (out-of-sample).
- Costs: this harness's stated cost model (16 bps round trip) instead of
  the legacy 8 bps.
- The full in-sample distribution is reported, not just the top of it.
- Trades are timestamped and attributed by entry time; a position still
  open at the end of the data is closed at the final close (the legacy code
  silently dropped it).
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from .data_feed import Dataset
from .simulator import Costs, Trade, trade_metrics
from .walkforward import FOLDS, trades_in_window


# --- Indicator replicas (identical formulas to the legacy mass_backtester) ---

def compute_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = pd.concat([
        df['high'] - df['low'],
        abs(df['high'] - df['close'].shift(1)),
        abs(df['low'] - df['close'].shift(1))
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    return 100.0 - (100.0 / (1.0 + rs))


def compute_stoch(df: pd.DataFrame, k_period: int = 14, d_period: int = 3, smooth: int = 3):
    low_min = df['low'].rolling(window=k_period).min()
    high_max = df['high'].rolling(window=k_period).max()
    fast_k = 100 * (df['close'] - low_min) / (high_max - low_min + 1e-12)
    k = fast_k.rolling(window=smooth).mean()
    d = k.rolling(window=d_period).mean()
    return k, d


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line


def variant_signals(df: pd.DataFrame, stype: str, params: dict) -> tuple[np.ndarray, np.ndarray]:
    """(long_signals, short_signals) boolean arrays — legacy logic verbatim."""
    long_signals = pd.Series(False, index=df.index)
    short_signals = pd.Series(False, index=df.index)

    if stype == "ema_crossover":
        f_ema = df['close'].ewm(span=params["fast_ema"], adjust=False).mean()
        s_ema = df['close'].ewm(span=params["slow_ema"], adjust=False).mean()
        long_signals = (f_ema > s_ema) & (f_ema.shift(1) <= s_ema.shift(1))
        short_signals = (f_ema < s_ema) & (f_ema.shift(1) >= s_ema.shift(1))
    elif stype == "rsi_mean_reversion":
        rsi = compute_rsi(df['close'], params["rsi_period"])
        long_signals = (rsi.shift(1) < params["rsi_lower"]) & (rsi >= params["rsi_lower"])
        short_signals = (rsi.shift(1) > params["rsi_upper"]) & (rsi <= params["rsi_upper"])
    elif stype == "bb_break_reenter":
        mid = df['close'].rolling(window=params["bb_period"]).mean()
        std = df['close'].rolling(window=params["bb_period"]).std()
        upper = mid + (params["bb_std"] * std)
        lower = mid - (params["bb_std"] * std)
        long_signals = (df['low'].shift(1) < lower.shift(1)) & (df['close'] > lower)
        short_signals = (df['high'].shift(1) > upper.shift(1)) & (df['close'] < upper)
    elif stype == "macd_crossover":
        macd, sig = compute_macd(df['close'], params["macd_fast"], params["macd_slow"], params["macd_signal"])
        long_signals = (macd > sig) & (macd.shift(1) <= sig.shift(1))
        short_signals = (macd < sig) & (macd.shift(1) >= sig.shift(1))
    elif stype == "stoch_crossover":
        k, d = compute_stoch(df, params["stoch_k"], params["stoch_d"], params["stoch_smooth"])
        long_signals = (k > d) & (k.shift(1) <= d.shift(1)) & (k < params["stoch_upper"])
        short_signals = (k < d) & (k.shift(1) >= d.shift(1)) & (k > params["stoch_lower"])
    elif stype == "ema_rsi_confluence":
        f_ema = df['close'].ewm(span=params["fast_ema"], adjust=False).mean()
        s_ema = df['close'].ewm(span=params["slow_ema"], adjust=False).mean()
        rsi = compute_rsi(df['close'], params["rsi_period"])
        long_signals = (f_ema > s_ema) & (f_ema.shift(1) <= s_ema.shift(1)) & (rsi < params["rsi_long_max"])
        short_signals = (f_ema < s_ema) & (f_ema.shift(1) >= s_ema.shift(1)) & (rsi > params["rsi_short_min"])
    elif stype == "macd_bb_confluence":
        macd, sig = compute_macd(df['close'], params["macd_fast"], params["macd_slow"], params["macd_signal"])
        mid = df['close'].rolling(window=params["bb_period"]).mean()
        std = df['close'].rolling(window=params["bb_period"]).std()
        long_signals = (macd > sig) & (macd.shift(1) <= sig.shift(1)) & (df['close'] < mid)
        short_signals = (macd < sig) & (macd.shift(1) >= sig.shift(1)) & (df['close'] > mid)
    elif stype == "stoch_ema_confluence":
        f_ema = df['close'].ewm(span=params["fast_ema"], adjust=False).mean()
        s_ema = df['close'].ewm(span=params["slow_ema"], adjust=False).mean()
        k, d = compute_stoch(df, params["stoch_k"], params["stoch_d"], params["stoch_smooth"])
        long_signals = (k > d) & (k.shift(1) <= d.shift(1)) & (df['close'] > s_ema)
        short_signals = (k < d) & (k.shift(1) >= d.shift(1)) & (df['close'] < s_ema)
    else:
        raise ValueError(f"unknown factory strategy type: {stype}")

    return (long_signals.fillna(False).to_numpy(dtype=bool),
            short_signals.fillna(False).to_numpy(dtype=bool))


def simulate_variant(df: pd.DataFrame, long_sig: np.ndarray, short_sig: np.ndarray,
                     atr: np.ndarray, sl_mult: float, tp_mult: float,
                     symbol: str, costs: Costs) -> list[Trade]:
    """Fast equivalent of the legacy trade loop (see simulator docstring for
    the FACTORY_ORIGINAL semantics). Exit search is vectorised per trade."""
    from .simulator import _net_return

    closes = df["close"].to_numpy()
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    index = df.index
    n = len(df)
    trades: list[Trade] = []
    # Candidate entry bars: entry at bar i (>=30, the legacy loop start) when
    # a signal fired at bar i-1 with a valid ATR. Legacy checks long first.
    sig_prev_long = np.concatenate([[False], long_sig[:-1]])
    sig_prev_short = np.concatenate([[False], short_sig[:-1]])
    atr_prev = np.concatenate([[0.0], atr[:-1]])
    cand_bars = np.nonzero((sig_prev_long | sig_prev_short) & (atr_prev > 0))[0]
    cand_bars = cand_bars[cand_bars >= 30]
    cursor = 30  # next entry must be at a bar > last exit bar
    for cand in cand_bars:
        entry_bar = int(cand)
        if entry_bar < cursor:
            continue
        side = "LONG" if sig_prev_long[entry_bar] else "SHORT"
        entry_p = closes[entry_bar]
        a = atr[entry_bar - 1]
        if side == "LONG":
            sl_p, tp_p = entry_p - sl_mult * a, entry_p + tp_mult * a
        else:
            sl_p, tp_p = entry_p + sl_mult * a, entry_p - tp_mult * a
        # Exit scan from entry_bar+1 (legacy checks exits on later iterations).
        exit_bar = None
        exit_price = None
        reason = None
        if entry_bar + 1 < n:
            if side == "LONG":
                sl_hits = np.nonzero(lows[entry_bar + 1:] <= sl_p)[0]
                tp_hits = np.nonzero(highs[entry_bar + 1:] >= tp_p)[0]
            else:
                sl_hits = np.nonzero(highs[entry_bar + 1:] >= sl_p)[0]
                tp_hits = np.nonzero(lows[entry_bar + 1:] <= tp_p)[0]
            first_sl = (entry_bar + 1 + sl_hits[0]) if len(sl_hits) else None
            first_tp = (entry_bar + 1 + tp_hits[0]) if len(tp_hits) else None
            if first_sl is not None and (first_tp is None or first_sl <= first_tp):
                exit_bar, exit_price, reason = first_sl, sl_p, "SL"
            elif first_tp is not None:
                exit_bar, exit_price, reason = first_tp, tp_p, "TP"
        if exit_bar is None:
            exit_bar, exit_price, reason = n - 1, closes[n - 1], "END_OF_DATA"
            trades.append(Trade(symbol, index[entry_bar], index[exit_bar], side,
                                entry_p, exit_price,
                                _net_return(side, entry_p, exit_price, costs), reason))
            break
        trades.append(Trade(symbol, index[entry_bar], index[exit_bar], side,
                            entry_p, exit_price,
                            _net_return(side, entry_p, exit_price, costs), reason))
        cursor = exit_bar + 1
    return trades


def evaluate_factory(variants: list[dict], datasets: dict[str, Dataset],
                     costs: Costs) -> dict:
    """Full walk-forward re-run of the factory selection.

    datasets: keyed by timeframe -> {symbol: Dataset} (all symbols pooled,
    as in the legacy run). Returns the procedure's record: per-fold IS
    ranking summary, the selected top-5 and their OOS metrics, and the full
    trade lists needed for the original-five verdict (returned separately).
    """
    symbols = sorted({ds.symbol for tf in datasets.values() for ds in tf.values()})
    # Precompute signals once per (type, params, timeframe, symbol).
    sig_cache: dict[tuple, dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]] = {}
    variant_trades: dict[int, list[Trade]] = {}

    for v in variants:
        tf = v["timeframe"]
        cache_key = (v["type"], json.dumps(v["params"], sort_keys=True), tf)
        if cache_key not in sig_cache:
            per_symbol = {}
            for sym, ds in datasets[tf].items():
                ls, ss = variant_signals(ds.df, v["type"], v["params"])
                atr = compute_atr(ds.df, 14).to_numpy()
                per_symbol[sym] = (ls, ss, atr)
            sig_cache[cache_key] = per_symbol
        trades: list[Trade] = []
        for sym, ds in datasets[tf].items():
            ls, ss, atr = sig_cache[cache_key][sym]
            trades.extend(simulate_variant(
                ds.df, ls, ss, atr, v["exits"]["sl_atr"], v["exits"]["tp_atr"],
                sym, costs))
        variant_trades[v["id"]] = trades

    folds_out = []
    procedure_oos_trades: list[Trade] = []
    for fid, start, end in FOLDS:
        is_rows = []
        for v in variants:
            is_trades = trades_in_window(variant_trades[v["id"]], None, start)
            m = trade_metrics(is_trades)
            is_rows.append({"id": v["id"], "name": v["name"], "type": v["type"],
                            "timeframe": v["timeframe"], **m})
        ranked = [r for r in is_rows if r["trades"] > 0 and r["profit_factor_net"] is not None]
        ranked.sort(key=lambda r: (r["profit_factor_net"] if r["profit_factor_net"] != float("inf") else 1e18,
                                   r["win_rate"] or 0.0), reverse=True)
        top5 = ranked[:5]
        selected = []
        for r in top5:
            oos_trades = trades_in_window(variant_trades[r["id"]], start, end)
            procedure_oos_trades.extend(oos_trades)
            selected.append({
                "id": r["id"], "name": r["name"],
                "is_metrics": {k: r[k] for k in ("trades", "win_rate", "expectancy_net", "profit_factor_net")},
                "oos_metrics": trade_metrics(oos_trades),
            })
        pf_values = [r["profit_factor_net"] for r in ranked
                     if r["profit_factor_net"] not in (None, float("inf"))]
        folds_out.append({
            "fold": fid, "oos_start": start, "oos_end": end,
            "is_variants_with_trades": len(ranked),
            "is_pf_median": float(np.median(pf_values)) if pf_values else None,
            "is_pf_max": float(np.max(pf_values)) if pf_values else None,
            "is_variants_pf_above_1": int(sum(1 for x in pf_values if x > 1.0)),
            "selected_top5": selected,
        })

    return {
        "folds": folds_out,
        "procedure_pooled_oos": trade_metrics(procedure_oos_trades),
        "variant_trades": variant_trades,
    }
