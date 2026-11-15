#!/usr/bin/env python3
"""TASK-STR-RD-005 runner — session / time-of-day effects.

Implements declaration.json EXACTLY (frozen 2026-11-15, SHA-256
4b640f87ab6921d517503ff4e87a9e7aef0a9f03899e0b02c98aa411ad6ec658, claimed
on issue #35 comment 6891055743 before the first cell ran).

Design notes:
- Time exits only (no brackets): exits are cost-independent in price
  space, so the 2x-cost sensitivity is an exact recomputation from the
  stored entry/exit prices, not a re-simulation.
- Metrics reuse the programme harness (rigorous_backtest.simulator
  .trade_metrics) imported read-only from an existing clone.
- Trades attributed to folds by ENTRY time (harness convention).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, "/home/hatch/workspace/str-rd3/repo/Stratex")
from rigorous_backtest.simulator import trade_metrics  # noqa: E402

CACHE = Path("/home/hatch/workspace/str-rd2/cache2")
OUT = Path("/home/hatch/workspace/rd-005/results_rd5")
OUT.mkdir(parents=True, exist_ok=True)

FOLDS_STD = [("W1", "2024-07-01", "2025-01-01"), ("W2", "2025-01-01", "2025-07-01"),
             ("W3", "2025-07-01", "2026-01-01"), ("W4", "2026-01-01", "2026-07-01"),
             ("W5", "2026-07-01", "2026-11-01")]
FOLDS_LATE = FOLDS_STD[1:]

SESSIONS = {  # name -> (tz, hour, minute)
    "TOKYO": ("Asia/Tokyo", 9, 0),
    "LONDON": ("Europe/London", 8, 0),
    "NEWYORK": ("America/New_York", 9, 30),
}
HOD_HOURS = [0, 8, 13, 16, 21]

CRYPTO30 = ["AAVEUSDT", "ADAUSDT", "ALGOUSDT", "APTUSDT", "ARBUSDT", "ATOMUSDT",
            "AVAXUSDT", "BCHUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "DOTUSDT",
            "ETCUSDT", "ETHUSDT", "FILUSDT", "HBARUSDT", "INJUSDT", "LINKUSDT",
            "LTCUSDT", "MANAUSDT", "NEARUSDT", "OPUSDT", "SANDUSDT", "SOLUSDT",
            "SUIUSDT", "TRXUSDT", "UNIUSDT", "VETUSDT", "XLMUSDT", "XRPUSDT"]
CRYPTO13_15M = ["ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT",
                "DOTUSDT", "ETHUSDT", "LINKUSDT", "LTCUSDT", "NEARUSDT",
                "SOLUSDT", "TRXUSDT", "XRPUSDT"]
FOREX3 = ["EURUSD", "GBPUSD", "USDJPY"]


# ---------------------------------------------------------------- data layer
def load_series(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["ts"], index_col="ts")
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="first")]
    return df[["open", "high", "low", "close", "volume"]].astype(float)


def verify_sidecar(csv_path: Path) -> dict:
    sidecar = csv_path.with_suffix(".csv.json")
    info = {"file": csv_path.name, "sidecar": sidecar.exists()}
    if sidecar.exists():
        man = json.loads(sidecar.read_text())
        want = man.get("csv_sha256") or man.get("sha256")
        got = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        info.update({"sha256_match": want == got, "rows_manifest": man.get("rows"),
                     "source": man.get("source")})
    return info


def panel_files(panel: str) -> list[tuple[str, Path]]:
    if panel == "crypto30_1h":
        return [(s, CACHE / f"{s}_1h_2022-01_2026-10.csv") for s in CRYPTO30]
    if panel == "crypto13_15m":
        return [(s, CACHE / f"{s}_15m_2023-10_2026-10.csv") for s in CRYPTO13_15M]
    if panel == "forex3_1h":
        return [(s, CACHE / f"YH_{s}_1h.csv") for s in FOREX3]
    raise ValueError(panel)


PANEL_META = {
    "crypto30_1h": {"bar_s": 3600, "rt_bps": 16.0, "folds": FOLDS_STD, "fx": False},
    "crypto13_15m": {"bar_s": 900, "rt_bps": 16.0, "folds": FOLDS_STD, "fx": False},
    "forex3_1h": {"bar_s": 3600, "rt_bps": 6.0, "folds": FOLDS_LATE, "fx": True},
}


# ------------------------------------------------------------- anchor builds
def session_anchor_instants(df_index: pd.DatetimeIndex, tz_name: str,
                            hh: int, mm: int) -> np.ndarray:
    """UTC ns instants of the local hh:mm anchor for every local date the
    series touches."""
    local = df_index.tz_convert(tz_name)
    dates = pd.DatetimeIndex(sorted(set(local.date)))
    out = []
    for d in dates:
        ts = pd.Timestamp(d.year, d.month, d.day, hh, mm).tz_localize(
            tz_name, ambiguous=False, nonexistent="shift_forward")
        out.append(ts.tz_convert("UTC").value)
    return np.array(out, dtype=np.int64)


def hod_anchor_instants(df_index: pd.DatetimeIndex, hour: int) -> np.ndarray:
    days = pd.date_range(df_index[0].normalize(), df_index[-1].normalize(),
                         freq="D", tz="UTC")
    return (days + pd.Timedelta(hours=hour)).asi8


# -------------------------------------------------------------- trade engine
def gen_trades(df: pd.DataFrame, anchors_ns: np.ndarray, lookback_bars: int,
               hold_hours: float, direction: str, bar_s: int, fx: bool,
               symbol: str) -> list[dict]:
    """Entries at the first bar starting in [anchor, anchor+bar). Direction
    from the prior move over lookback_bars closes strictly before the entry
    bar. Clock-based time exit. One open position per symbol."""
    idx_ns = df.index.asi8
    opens = df["open"].to_numpy()
    closes = df["close"].to_numpy()
    n = len(df)
    bar_ns = bar_s * 1_000_000_000
    trades = []
    busy_until = -1
    for anchor in anchors_ns:
        ei = int(np.searchsorted(idx_ns, anchor))
        if ei >= n:
            break
        if idx_ns[ei] - anchor >= bar_ns:      # no bar near the anchor
            continue
        entry_time = idx_ns[ei]
        if entry_time < busy_until:            # one position at a time
            continue
        sig = ei - 1                            # last bar before entry
        ref = sig - lookback_bars
        if ref < 0:
            continue
        if not fx:
            # crypto: the lookback window and the signal->entry step must
            # be contiguous (an archive hole falsifies the prior move)
            if idx_ns[sig] - idx_ns[ref] != lookback_bars * bar_ns:
                continue
            if idx_ns[ei] - idx_ns[sig] != bar_ns:
                continue
        else:
            # forex: windows may span closures (declared), bounded at 96h
            if idx_ns[sig] - idx_ns[ref] > (lookback_bars * bar_s + 96 * 3600) * 1_000_000_000:
                continue
            if idx_ns[ei] - idx_ns[sig] > 96 * 3600 * 1_000_000_000:
                continue
        prior = closes[sig] / closes[ref] - 1.0
        if prior == 0.0:
            continue
        side = 1 if prior > 0 else -1
        if direction == "REV":
            side = -side
        target = entry_time + int(hold_hours * 3600 * 1_000_000_000)
        xi = int(np.searchsorted(idx_ns, target))
        if xi >= n:
            exit_price, exit_time, reason = closes[n - 1], idx_ns[n - 1], "END_OF_DATA"
        elif idx_ns[xi] - target > 96 * 3600 * 1_000_000_000:
            exit_price, exit_time, reason = closes[xi - 1], idx_ns[xi - 1], "GAP_END"
        else:
            exit_price, exit_time, reason = opens[xi], idx_ns[xi], "TIME"
        trades.append({"symbol": symbol, "entry_time": entry_time,
                       "exit_time": exit_time, "side": side,
                       "entry_price": float(opens[ei]),
                       "exit_price": float(exit_price), "reason": reason})
        busy_until = exit_time
    return trades


def net_return(side: int, entry: float, exit_: float, rt_bps: float) -> float:
    r = (rt_bps / 2.0) / 10000.0
    if side > 0:
        ea, xa = entry * (1 + r), exit_ * (1 - r)
        return (xa - ea) / ea
    ea, xa = entry * (1 - r), exit_ * (1 + r)
    return (ea - xa) / ea


def attach_returns(trades: list[dict], rt_bps: float) -> list[dict]:
    for t in trades:
        t["net"] = net_return(t["side"], t["entry_price"], t["exit_price"], rt_bps)
    return trades


# ------------------------------------------------------------------ metrics
class T:  # minimal adapter to harness trade_metrics
    __slots__ = ("entry_time", "net_return")

    def __init__(self, entry_time, net_return):
        self.entry_time = entry_time
        self.net_return = net_return


def metrics_of(trades: list[dict]) -> dict:
    return trade_metrics([T(pd.Timestamp(t["entry_time"], tz="UTC"), t["net"])
                          for t in trades])


def fold_split(trades: list[dict], folds) -> dict:
    out = {}
    for fid, s, e in folds:
        s_ns = pd.Timestamp(s, tz="UTC").value
        e_ns = pd.Timestamp(e, tz="UTC").value
        out[fid] = metrics_of([t for t in trades if s_ns <= t["entry_time"] < e_ns])
    return out


def oos_only(trades: list[dict], folds) -> list[dict]:
    s_ns = pd.Timestamp(folds[0][1], tz="UTC").value
    e_ns = pd.Timestamp(folds[-1][2], tz="UTC").value
    return [t for t in trades if s_ns <= t["entry_time"] < e_ns]


def breadth_and_holdout(trades: list[dict], holdout_syms: set) -> dict:
    by_sym: dict[str, list[float]] = {}
    for t in trades:
        by_sym.setdefault(t["symbol"], []).append(t["net"])
    exp = {s: float(np.mean(v)) for s, v in by_sym.items() if v}
    pos_profit = {s: float(sum(x for x in v if x > 0)) for s, v in by_sym.items()}
    tot_pos = sum(pos_profit.values())
    max_share = (max(pos_profit.values()) / tot_pos) if tot_pos > 0 else None
    frac_pos = (float(np.mean([1.0 if e > 0 else 0.0 for e in exp.values()]))
                if exp else None)
    ho = [t for t in trades if t["symbol"] in holdout_syms]
    ho_m = metrics_of(ho)
    return {"per_symbol_expectancy": exp,
            "symbols_positive_frac": frac_pos,
            "max_symbol_profit_share": max_share,
            "holdout_trades": ho_m["trades"],
            "holdout_expectancy": ho_m["expectancy_net"]}


def bonferroni_p(trades: list[dict]) -> float | None:
    if len(trades) < 2:
        return None
    nets = np.array([t["net"] for t in trades], dtype=float)
    if nets.std(ddof=1) == 0:
        return None
    return float(stats.ttest_1samp(nets, 0.0, alternative="greater").pvalue)


def dsr_of(trades: list[dict], n_trials: int) -> float | None:
    """Deflated Sharpe ratio (Bailey & Lopez de Prado) on per-trade
    returns, as in RD-002: reported, not a veto."""
    nets = np.array([t["net"] for t in trades], dtype=float)
    T_ = len(nets)
    if T_ < 10 or nets.std(ddof=1) == 0:
        return None
    sr = nets.mean() / nets.std(ddof=1)
    g = 0.5772156649
    z1 = stats.norm.ppf(1 - 1.0 / n_trials)
    z2 = stats.norm.ppf(1 - 1.0 / (n_trials * np.e))
    e_max = (1 - g) * z1 + g * z2
    sr0 = e_max / np.sqrt(T_ - 1)
    sk = float(stats.skew(nets))
    ku = float(stats.kurtosis(nets, fisher=False))
    denom = np.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4 * sr**2))
    return float(stats.norm.cdf(((sr - sr0) * np.sqrt(T_ - 1)) / denom))


# ------------------------------------------------------------- config space
def configs_for(panel: str):
    """Yield (config_id, subfamily, params) exactly per declaration."""
    bar_s = PANEL_META[panel]["bar_s"]
    lb_bars = {h: int(h * 3600 / bar_s) for h in (1, 4)}
    for sess in ("TOKYO", "LONDON", "NEWYORK", "ALL"):
        for d in ("MOM", "REV"):
            for L in (1, 4):
                for H in (2, 4):
                    cid = f"SOI_{sess}_{d}_L{L}h_H{H}h"
                    yield cid, "SOI", {"session": sess, "direction": d,
                                       "lookback_bars": lb_bars[L], "lookback_h": L,
                                       "hold_h": H}
    w_bars = {h: int(h * 3600 / bar_s) for h in (1, 3)}
    for h in HOD_HOURS:
        for d in ("MOM", "REV"):
            for W in (1, 3):
                cid = f"HOD_{h:02d}UTC_{d}_W{W}h"
                yield cid, "HOD", {"hour": h, "direction": d,
                                   "lookback_bars": w_bars[W], "window_h": W,
                                   "hold_h": W}


def anchors_for(panel_data: dict, panel: str, subfam: str, params: dict,
                symbol: str) -> np.ndarray:
    df = panel_data[symbol]
    if subfam == "SOI":
        if params["session"] == "ALL":
            parts = [session_anchor_instants(df.index, tz, hh, mm)
                     for tz, hh, mm in SESSIONS.values()]
            return np.unique(np.concatenate(parts))
        tz, hh, mm = SESSIONS[params["session"]]
        return session_anchor_instants(df.index, tz, hh, mm)
    return hod_anchor_instants(df.index, params["hour"])


def judge(row: dict, n_floor: int, n_stab: int) -> str:
    """Apply the standing bar. Returns verdict string."""
    m = row["pooled_oos"]
    if m["trades"] == 0:
        return "NO_TRADES"
    mech = (m["expectancy_net"] is not None and m["expectancy_net"] > 0
            and m["profit_factor_net"] is not None and m["profit_factor_net"] >= 1.2
            and m["trades"] >= 200 and row["folds_positive_frac"] is not None
            and row["folds_positive_frac"] >= 0.8
            and row["breadth"]["holdout_trades"] >= 30
            and row["breadth"]["holdout_expectancy"] is not None
            and row["breadth"]["holdout_expectancy"] > 0
            and row["breadth"]["symbols_positive_frac"] is not None
            and row["breadth"]["symbols_positive_frac"] >= 0.5
            and row["breadth"]["max_symbol_profit_share"] is not None
            and row["breadth"]["max_symbol_profit_share"] <= 0.5)
    if not mech:
        return "FAIL"
    sens = row.get("sensitivity_2x") or {}
    if not (sens.get("expectancy_net", -1) > 0 and sens.get("profit_factor_net", 0) >= 1.2):
        return "WATCHLIST"  # mechanical pass, dies at 2x costs
    p = row["bonferroni_p"]
    if p is not None and p < 0.05 / n_stab:
        return "CANDIDATE"
    if p is not None and p < 0.05 / n_floor:
        return "WATCHLIST"  # significant at the floor N only
    return "WATCHLIST"      # mechanical pass, significance fails


def run_panel(panel: str, n_floor: int, n_stab: int) -> list[dict]:
    meta = PANEL_META[panel]
    files = panel_files(panel)
    coverage = []
    data: dict[str, pd.DataFrame] = {}
    for sym, path in files:
        cov = verify_sidecar(path)
        coverage.append(cov)
        if not cov.get("sha256_match"):
            raise RuntimeError(f"provenance mismatch: {path}")
        data[sym] = load_series(path)
    (OUT / f"coverage_{panel}.json").write_text(json.dumps(coverage, indent=1))
    syms_sorted = sorted(data)
    holdout = set(syms_sorted[::3]) if panel != "forex3_1h" else {"USDJPY"}
    rows: list[dict] = []
    # cache anchors per (symbol, subfam, key)
    anchor_cache: dict[tuple, np.ndarray] = {}

    def get_anchors(sym, subfam, params):
        key = (sym, subfam, params.get("session") or params.get("hour"))
        if key not in anchor_cache:
            anchor_cache[key] = anchors_for(data, panel, subfam, params, sym)
        return anchor_cache[key]

    # raw trade streams per config (all-time; folds partition later)
    streams: dict[str, list[dict]] = {}
    cfg_list = list(configs_for(panel))
    for cid, subfam, params in cfg_list:
        all_trades: list[dict] = []
        for sym in syms_sorted:
            anch = get_anchors(sym, subfam, params)
            tr = gen_trades(data[sym], anch, params["lookback_bars"],
                            float(params["hold_h"]), params["direction"],
                            meta["bar_s"], meta["fx"], sym)
            all_trades.extend(tr)
        streams[cid] = attach_returns(all_trades, meta["rt_bps"])

    def build_row(cid, subfam, params, trades_all):
        oos = oos_only(trades_all, meta["folds"])
        per_fold = fold_split(trades_all, meta["folds"])
        folds_with = [f for f in per_fold.values() if f["trades"] > 0]
        fpf = (float(np.mean([1.0 if f["expectancy_net"] > 0 else 0.0
                              for f in folds_with])) if folds_with else None)
        row = {"config": cid, "panel": panel, "subfamily": subfam,
               "params": {k: v for k, v in params.items() if k != "lookback_bars"},
               "pooled_oos": metrics_of(oos), "per_fold": per_fold,
               "folds_positive_frac": fpf,
               "breadth": breadth_and_holdout(oos, holdout),
               "bonferroni_p": bonferroni_p(oos)}
        if row["pooled_oos"]["trades"] >= 200 and (row["pooled_oos"]["expectancy_net"] or 0) > 0 \
                and (row["pooled_oos"]["profit_factor_net"] or 0) >= 1.2:
            dbl = attach_returns([dict(t) for t in oos], meta["rt_bps"] * 2)
            row["sensitivity_2x"] = metrics_of(dbl)
            row["dsr_at_gateN"] = dsr_of(oos, n_stab)
        row["verdict"] = judge(row, n_floor, n_stab)
        return row

    for cid, subfam, params in cfg_list:
        rows.append(build_row(cid, subfam, params, streams[cid]))

    # wf-select procedures: one per subfamily
    for subfam in ("SOI", "HOD"):
        fam = [(cid, p) for cid, sf, p in cfg_list if sf == subfam]
        proc_trades: list[dict] = []
        for fid, s, e in meta["folds"]:
            s_ns = pd.Timestamp(s, tz="UTC").value
            e_ns = pd.Timestamp(e, tz="UTC").value
            best, best_exp = None, None
            for cid, _p in fam:
                is_tr = [t for t in streams[cid] if t["entry_time"] < s_ns]
                if len(is_tr) < 50:
                    continue
                exp = float(np.mean([t["net"] for t in is_tr]))
                if best_exp is None or exp > best_exp:
                    best, best_exp = cid, exp
            if best is None:
                continue
            proc_trades.extend([t for t in streams[best]
                                if s_ns <= t["entry_time"] < e_ns])
        cid = f"WFSEL_{subfam}"
        row = build_row(cid, "WFSEL", {"procedure_of": subfam}, proc_trades)
        rows.append(row)
    return rows


# -------------------------------------------------------------- sanity checks
def sanity() -> dict:
    out = {}
    # S1: zero-cost SOI trade returns vs independent recomputation (BTC 1h)
    df = load_series(CACHE / "BTCUSDT_1h_2022-01_2026-10.csv")
    anch = session_anchor_instants(df.index, "Europe/London", 8, 0)
    tr = gen_trades(df, anch, 4, 2.0, "MOM", 3600, False, "BTCUSDT")
    checked = 0
    for t in tr[:5]:
        et = pd.Timestamp(t["entry_time"], tz="UTC")
        xt = pd.Timestamp(t["exit_time"], tz="UTC")
        entry = float(df.loc[et, "open"])
        exit_ = float(df.loc[xt, "open"]) if t["reason"] == "TIME" else float(df.loc[xt, "close"])
        r0 = net_return(t["side"], t["entry_price"], t["exit_price"], 0.0)
        r_ind = (exit_ / entry - 1.0) * t["side"] if t["side"] > 0 else (entry / exit_ - 1.0)
        # exact independent form: price-space, zero costs
        r_ind = ((exit_ - entry) / entry) * (1 if t["side"] > 0 else -1) if t["side"] > 0 \
            else (entry - exit_) / entry
        assert abs(r0 - r_ind) < 1e-12, (r0, r_ind)
        checked += 1
    out["S1_zero_cost_first5_match"] = checked == 5
    # S2: cost monotonicity — doubling costs never raises a return
    tr2 = attach_returns([dict(t) for t in tr[:200]], 16.0)
    tr3 = attach_returns([dict(t) for t in tr[:200]], 32.0)
    out["S2_cost_monotone"] = all(b["net"] <= a["net"] + 1e-15
                                  for a, b in zip(tr2, tr3))
    # S3: fold partition — pooled OOS == sum of folds, entries inside era
    rows_tr = attach_returns(tr, 16.0)
    oos = oos_only(rows_tr, FOLDS_STD)
    per = fold_split(rows_tr, FOLDS_STD)
    out["S3_fold_partition"] = (sum(f["trades"] for f in per.values())
                                == len(oos) == metrics_of(oos)["trades"])
    out["sanity_trades_sampled"] = len(tr)
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    n_floor, n_stab = 1926, 3000
    if mode == "sanity":
        print(json.dumps(sanity(), indent=1))
        return
    panels = ["crypto30_1h", "crypto13_15m", "forex3_1h"] if mode == "all" else [mode]
    all_rows = []
    for panel in panels:
        rows = run_panel(panel, n_floor, n_stab)
        (OUT / f"rows_{panel}.json").write_text(json.dumps(rows, indent=1, default=str))
        all_rows.extend(rows)
        print(f"[{panel}] {len(rows)} rows")
        for r in rows:
            m = r["pooled_oos"]
            print(f"  {r['config']:28s} n={m['trades']:6d} exp={m['expectancy_net']} "
                  f"pf={m['profit_factor_net']} folds+={r['folds_positive_frac']} "
                  f"p={r['bonferroni_p']} -> {r['verdict']}")
    (OUT / "rows_all.json").write_text(json.dumps(all_rows, indent=1, default=str))
    print(f"TOTAL ROWS {len(all_rows)}")


if __name__ == "__main__":
    main()
