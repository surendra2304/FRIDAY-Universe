"""TASK-STR-RD-020 — Cross-asset momentum rotation with a pre-declared
drawdown brake (research only). NO RUN is performed by this module's
author; it is the frozen harness for a future declared run.

Lineage (full disclosure in declaration.json): the signal is
TASK-STR-RD-013's cross-asset momentum rotation rule verbatim, on
RD-013's exact 7-asset universe and hash-verified panel. RD-013 judged
48 configurations 0/48 — the drawdown gate (<= 20%) failed universally.
This family is the revisit RD-013's own board note mandates: the same
rotation plus ONE new mechanism, a portfolio-level drawdown brake, as
a NEW pre-declared family — not a retune of RD-013's grid. It is also
distinct from TASK-STR-RD-014 (per-symbol trend + volatility targeting
+ per-symbol shadow-driven brake on crypto30, 0/96): no volatility
targeting anywhere here, the brake is portfolio-level and driven by
the braked book's own equity, and the release rules follow RD-014's
recorded post-mortem (own-recovery release from HALVED; fresh-signal
re-entry from FLAT — never shadow-equity recovery).

Frozen mechanics (declaration.json is the governing text):
  selection  at each Monday rebalance t: score = trailing L-calendar-
             day return (last close <= t vs last close <= t-L; each
             endpoint within 3 calendar days of its target; asset
             needs >= L+30 days of history). Top-K at equal weight
             1/K; long_flat: a selected asset with score <= 0 is held
             as cash, weight NOT redistributed; unfilled weight cash.
  brake      portfolio-level state machine on the braked book's own
             daily close-to-close drawdown from its running peak
             (peak never reset, path runs from START, IS era included):
               NORMAL -(DD <= -10%)-> HALVED (exposure scale 0.5)
               NORMAL|HALVED -(DD <= -15%)-> FLAT (scale 0)
               HALVED -(braked DD >= -5%)-> NORMAL (scale 1.0)
               FLAT -(Monday rebalance whose fresh selection would be
                      fully invested, i.e. all top-K scores > 0)->
                      HALVED (probationary re-entry at scale 0.5)
             All decisions use closes <= d and execute at close d
             (RD-013's convention). The brake signal at close d is the
             drawdown of the pre-trade mark at d against the running
             peak of pre-trade marks. A scale change or rebalance sets
             holdings to scale x selection x equity at that close.
  costs      round-trip bps by asset (crypto 16, GOLD 10, SPX/NDX 8 —
             the RD-002/RD-013 table). Every trade (rebalance, brake
             trim, flatten, re-entry) is charged sum_i |dw_i| x RT_i/2
             as an equity fraction, deducted at the trade close. Cash
             earns 0. Initial build charged.
  accounting daily close-to-close equity curve (after-trades marks).
             Weekly period returns are measured pre-trade close to
             pre-trade close, so each Monday's trade costs fall inside
             the period starting that Monday (RD-013's convention) and
             the period returns telescope exactly onto the equity
             curve. A TRADE (episode) is one asset's continuous
             positive-weight run: opened when its weight leaves 0,
             closed when it returns to 0 (deselection, brake FLAT) or
             force-closed at END; episode net return = the asset's
             compounded daily return over the run x (1 - RT/2 drag at
             entry) x (1 - RT/2 drag at exit) - 1.
  judgement  OOS = period starts / episode entries in
             [2024-07-01, 2026-11-01); folds W1-W5 as RD-002, periods
             attributed by start date, episodes by entry date. The
             drawdown gate is measured on the DAILY curve with the
             peak carried in from the full path (stricter than
             RD-013's period-granularity, reset-at-OOS measurement —
             declared in declaration.json).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ASSETS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "GOLD", "SPX", "NDX"]
RT_BPS = {"BTCUSDT": 16.0, "ETHUSDT": 16.0, "SOLUSDT": 16.0, "BNBUSDT": 16.0,
          "GOLD": 10.0, "SPX": 8.0, "NDX": 8.0}
START = pd.Timestamp("2023-01-02")
OOS_START = pd.Timestamp("2024-07-01")
END = pd.Timestamp("2026-11-01")
FOLDS = [("W1", "2024-07-01", "2025-01-01"), ("W2", "2025-01-01", "2025-07-01"),
         ("W3", "2025-07-01", "2026-01-01"), ("W4", "2026-01-01", "2026-07-01"),
         ("W5", "2026-07-01", "2026-11-01")]
STALE_DAYS = 3

# The frozen grid: 4 cells = 4 trials. Cadence and mode are NOT axes.
LOOKBACKS = [63, 126]
KS = [2, 3]
CADENCE = "weekly"
MODE = "long_flat"

# The frozen brake: single parameter set, NOT a grid axis.
BRAKE_L1_DD = -0.10        # NORMAL -> HALVED (scale 0.5)
BRAKE_L2_DD = -0.15        # NORMAL|HALVED -> FLAT (scale 0)
BRAKE_RELEASE_DD = -0.05   # HALVED -> NORMAL on braked-book recovery
SCALE_HALVED = 0.5

# SHA-256 of the exact panel files RD-013 judged on, as recorded in
# results_rd13/synthesis.json (origin/main). The loader refuses any
# file whose hash differs from BOTH its sidecar and this record.
RD13_PANEL_SHA256 = {
    "BTCUSDT_1h_2022-01_2026-10.csv":
        "cbd726f60c714420781961a447577b43659780e66f6e94e27ee1db5a2ebc640e",
    "ETHUSDT_1h_2022-01_2026-10.csv":
        "5d861191ad4d68e922b741c33e99192d6082016b92eaf265dd76e7949d01c88c",
    "SOLUSDT_1h_2022-01_2026-10.csv":
        "281fbff59b203575c1acf24b0a15cafdb53cae6a3814df2d95c099d0de056196",
    "BNBUSDT_1h_2022-01_2026-10.csv":
        "5461c517e9a18ffdfb0ec7fdad845fd864465a377351208c934f0cb3af745549",
    "YH_GOLD_1d.csv":
        "4933b83b0672551656e0c4c7068f9087b232274ab954e64164b9360ca3560dd4",
    "YH_SPX_1d.csv":
        "ab1482ee3b03fa53fa80ffc818cd86f4c60feb8c85265b4ca808e0b60b4673bb",
    "YH_NDX_1d.csv":
        "4dd2893217154491dc5732eae71883a71d4a234ff87b46d4b32cb964ed6ea581",
}


def _verify(path: Path) -> dict:
    sidecar = path.with_suffix(path.suffix + ".json")
    meta = json.loads(sidecar.read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != meta.get("csv_sha256"):
        raise RuntimeError(f"sidecar hash mismatch for {path}; refusing unverified data")
    expected = RD13_PANEL_SHA256.get(path.name)
    if expected is not None and digest != expected:
        raise RuntimeError(
            f"{path} does not match the RD-013 judged panel hash; refusing substituted data")
    return meta


def load_closes(cache: Path) -> tuple[dict[str, pd.Series], dict]:
    """Daily close series per asset, indexed by UTC calendar date.
    Identical construction to rd13/rotation.py (complete 24-bar
    buckets only for crypto; Yahoo daily closes for GOLD/SPX/NDX)."""
    closes: dict[str, pd.Series] = {}
    provenance = {}
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]:
        f = cache / f"{sym}_1h_2022-01_2026-10.csv"
        meta = _verify(f)
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        daily = df["close"].resample("1D", origin="start_day").agg(["last", "count"])
        dropped = int((daily["count"] != 24).sum())
        s = daily.loc[daily["count"] == 24, "last"]
        s.index = s.index.tz_localize(None).normalize()
        closes[sym] = s
        provenance[sym] = {"source": meta["source"], "csv_sha256": meta["csv_sha256"],
                           "base_rows": meta["rows"], "daily_bars": int(len(s)),
                           "incomplete_days_dropped": dropped}
    for sym, yf in [("GOLD", "GOLD"), ("SPX", "SPX"), ("NDX", "NDX")]:
        f = cache / f"YH_{yf}_1d.csv"
        meta = _verify(f)
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        if df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)
        s = df["close"].copy()
        s.index = s.index.normalize()
        s = s[~s.index.duplicated(keep="last")].sort_index()
        closes[sym] = s
        provenance[sym] = {"source": meta["source"], "csv_sha256": meta["csv_sha256"],
                           "base_rows": meta["rows"], "daily_bars": int(len(s)),
                           "incomplete_days_dropped": 0}
    return closes, provenance


def close_at(series: pd.Series, target: pd.Timestamp):
    """(close, staleness_days) of the last bar <= target, or None."""
    idx = series.index.searchsorted(target, side="right") - 1
    if idx < 0:
        return None
    bar_date = series.index[idx]
    return float(series.iloc[idx]), (target - bar_date).days


def select(closes, t: pd.Timestamp, lookback: int, k: int) -> dict[str, float]:
    """RD-013's selection rule verbatim (long_flat): target weights at
    rebalance t, using only bars <= t."""
    scored = []
    for a in ASSETS:
        s = closes[a]
        if (t - s.index[0]).days < lookback + 30:
            continue
        now = close_at(s, t)
        past = close_at(s, t - pd.Timedelta(days=lookback))
        if now is None or past is None:
            continue
        if now[1] > STALE_DAYS or past[1] > STALE_DAYS:
            continue
        scored.append((a, now[0] / past[0] - 1.0))
    scored.sort(key=lambda x: (-x[1], x[0]))
    w = {a: 0.0 for a in ASSETS}
    for a, score in scored[:k]:
        w[a] = 0.0 if score <= 0 else 1.0 / k
    return w


def rebalance_dates() -> list[pd.Timestamp]:
    return list(pd.date_range(START, END, freq="W-MON"))


def run_config(closes, lookback: int, k: int, cost_mult: float = 1.0) -> dict:
    """Simulate one frozen cell day by day. Returns the daily equity
    path, weekly period returns, closed episodes, brake transition log
    and total turnover cost — all causal (decisions at close d use
    only bars <= d and execute at close d)."""
    rebs = rebalance_dates()
    reb_set = set(rebs)
    cal = set()
    for s in closes.values():
        cal.update(s.index[(s.index >= START) & (s.index <= END)])
    days = sorted(cal | reb_set | {END})
    days = [d for d in days if START <= d <= END]

    marks = {a: {} for a in ASSETS}  # per-day last-close-<= marks, filled lazily

    def mark(a, d):
        m = marks[a].get(d)
        if m is None:
            c = close_at(closes[a], d)
            m = c[0] if c is not None else float("nan")
            marks[a][d] = m
        return m

    cash = 1.0
    h = {a: 0.0 for a in ASSETS}          # dollar holdings (equity starts 1.0)
    selection = {a: 0.0 for a in ASSETS}  # current target weights w*
    state = "NORMAL"
    scale = 1.0
    peak = 1.0              # brake signal peak: max of pre-trade signal marks
    peak_post = 1.0         # gate DD peak: max of after-trades closes
    equity_path = []        # (date, equity after trades)
    dd_path = []            # (date, after-trades drawdown vs peak_post)
    pre_by_date = {}        # date -> equity pre-trade at that close
    period_pre = []         # (rebalance date, equity pre-trade at that close)
    transitions = []        # brake state changes: dict(date, from, to, dd_at_signal)
    total_cost = 0.0
    open_eps = {}           # asset -> [entry_date, factor]
    episodes = []           # closed: dict(asset, entry, exit, net)

    prev = None
    for d in days:
        # --- 1. accrue returns from prev close to this close ---
        if prev is not None:
            for a in ASSETS:
                if h[a] > 0.0:
                    m0, m1 = mark(a, prev), mark(a, d)
                    if m0 == m0 and m1 == m1 and m0 > 0:
                        r = m1 / m0 - 1.0
                        h[a] *= (1.0 + r)
                        if a in open_eps:
                            open_eps[a][1] *= (1.0 + r)
        equity_pre = cash + sum(h.values())
        # --- 2. drawdown on the pre-trade mark (the signal close) ---
        peak = max(peak, equity_pre)
        dd = equity_pre / peak - 1.0 if peak > 0 else 0.0
        # --- 3. events at this close ---
        is_reb = d in reb_set
        if is_reb:
            selection = select(closes, d, lookback, k)
            period_pre.append((d, equity_pre))
        new_state, new_scale = state, scale
        if state in ("NORMAL", "HALVED") and dd <= BRAKE_L2_DD:
            new_state, new_scale = "FLAT", 0.0
        elif state == "NORMAL" and dd <= BRAKE_L1_DD:
            new_state, new_scale = "HALVED", SCALE_HALVED
        elif state == "HALVED" and dd >= BRAKE_RELEASE_DD:
            new_state, new_scale = "NORMAL", 1.0
        elif (state == "FLAT" and is_reb
              and sum(selection.values()) >= 1.0 - 1e-9):
            new_state, new_scale = "HALVED", SCALE_HALVED
        changed = (new_state != state)
        if changed:
            transitions.append({"date": str(d.date()), "from": state,
                                "to": new_state, "dd_at_signal": dd})
            state, scale = new_state, new_scale
        # --- 4. execute trades at this close if rebalancing or braked ---
        equity = equity_pre
        if is_reb or changed:
            targets = {a: scale * selection[a] * equity_pre for a in ASSETS}
            cost = 0.0
            for a in ASSETS:
                dw = abs(targets[a] - h[a]) / equity_pre if equity_pre > 0 else 0.0
                cost += dw * (RT_BPS[a] * cost_mult / 10000.0) / 2.0
            total_cost += cost
            equity = equity_pre * (1.0 - cost)
            h = {a: scale * selection[a] * equity for a in ASSETS}
            cash = equity - sum(h.values())
            # episode open/close on the post-trade holdings
            for a in ASSETS:
                if h[a] > 0.0 and a not in open_eps:
                    open_eps[a] = [d, 1.0]
                elif h[a] == 0.0 and a in open_eps:
                    entry_date, factor = open_eps.pop(a)
                    drag = 1.0 - (RT_BPS[a] * cost_mult / 10000.0) / 2.0
                    episodes.append({"asset": a, "entry": entry_date, "exit": d,
                                     "net": factor * drag * drag - 1.0})
        pre_by_date[d] = equity_pre
        equity_path.append((d, equity))
        peak_post = max(peak_post, equity)
        dd_path.append((d, equity / peak_post - 1.0 if peak_post > 0 else 0.0))
        prev = d
    # --- force-close open episodes at END (RD-009 precedent) ---
    last = days[-1]
    for a, (entry_date, factor) in list(open_eps.items()):
        drag = 1.0 - (RT_BPS[a] * cost_mult / 10000.0) / 2.0
        episodes.append({"asset": a, "entry": entry_date, "exit": last,
                         "net": factor * drag * drag - 1.0})
    # --- weekly period returns: pre-trade close to pre-trade close ---
    periods = []
    bounds = period_pre + [(END, pre_by_date.get(END, equity_path[-1][1]))]
    for j in range(len(bounds) - 1):
        t0, e0 = bounds[j]
        t1, e1 = bounds[j + 1]
        if t1 <= t0:
            continue
        periods.append({"start": t0, "net": e1 / e0 - 1.0 if e0 > 0 else 0.0})
    return {"equity_path": equity_path, "dd_path": dd_path,
            "periods": periods, "episodes": episodes,
            "transitions": transitions, "total_cost_frac": total_cost,
            "final_equity": equity_path[-1][1] if equity_path else 1.0}


def summarise(result: dict) -> dict:
    periods = result["periods"]
    oos_p = [p for p in periods if OOS_START <= p["start"] < END]
    is_p = [p for p in periods if p["start"] < OOS_START]
    rets = np.array([p["net"] for p in oos_p], dtype=float)
    compounded = float(np.prod(1.0 + rets) - 1.0) if len(rets) else 0.0
    pos = float(rets[rets > 0].sum())
    neg = float(-rets[rets < 0].sum())
    pf = (pos / neg) if neg > 0 else (float("inf") if pos > 0 else 0.0)
    t_p = float(stats.ttest_1samp(rets, 0.0, alternative="greater").pvalue) \
        if len(rets) > 2 else 1.0
    folds = {}
    for fid, s, e in FOLDS:
        fr = np.array([p["net"] for p in oos_p
                       if pd.Timestamp(s) <= p["start"] < pd.Timestamp(e)])
        folds[fid] = {"periods": int(len(fr)),
                      "compounded": float(np.prod(1.0 + fr) - 1.0) if len(fr) else 0.0}
    folds_positive = int(sum(1 for f in folds.values() if f["compounded"] > 0))
    # daily-curve OOS max drawdown, peak carried in from the full path
    oos_dd = [dd for d, dd in result["dd_path"] if OOS_START <= d <= END]
    max_dd = float(min(oos_dd)) if oos_dd else 0.0
    # episodes entered OOS
    oos_eps = [e for e in result["episodes"] if OOS_START <= e["entry"] < END]
    ep_rets = np.array([e["net"] for e in oos_eps], dtype=float)
    epos = float(ep_rets[ep_rets > 0].sum())
    eneg = float(-ep_rets[ep_rets < 0].sum())
    ep_pf = (epos / eneg) if eneg > 0 else (float("inf") if epos > 0 else 0.0)
    # per-asset contribution: episode net returns summed per asset (the
    # family's trade unit), share of total positive contribution
    contrib = {a: 0.0 for a in ASSETS}
    for e in oos_eps:
        contrib[e["asset"]] += e["net"]
    pos_contrib = {a: c for a, c in contrib.items() if c > 0}
    tot_pos = sum(pos_contrib.values())
    max_share = (max(pos_contrib.values()) / tot_pos) if tot_pos > 0 else 1.0
    is_rets = np.array([p["net"] for p in is_p], dtype=float)
    return {
        "oos_periods": int(len(rets)),
        "oos_compounded": compounded,
        "oos_max_drawdown_daily": max_dd,
        "oos_period_pf": pf,
        "oos_mean_period_return": float(rets.mean()) if len(rets) else 0.0,
        "t_stat_one_sided_p": t_p,
        "folds": folds,
        "folds_positive": folds_positive,
        "oos_episodes": int(len(oos_eps)),
        "oos_episode_pf": ep_pf,
        "contrib_by_asset_episodes": {a: float(c) for a, c in contrib.items()},
        "max_asset_profit_share": float(max_share),
        "brake_transitions": int(len(result["transitions"])),
        "total_turnover_cost_frac": float(result["total_cost_frac"]),
        "is_compounded": float(np.prod(1.0 + is_rets) - 1.0) if len(is_rets) else 0.0,
        "is_periods": int(len(is_rets)),
    }


def evaluate_bar(row: dict, n_global: int, x2_row: dict | None = None) -> dict:
    """The frozen eight-gate bar (declaration.json governs). Returns
    per-gate booleans + the verdict class. Gate 7 (2x costs) is only
    evaluable when x2_row is supplied (the runner supplies it for
    cells passing gates 1-6 and 8, RD-013's conditional pattern)."""
    alpha = 0.05 / n_global
    p = row["t_stat_one_sided_p"]
    gates = {
        "g1_compounded_positive": row["oos_compounded"] > 0,
        "g2_period_pf_ge_1_2": row["oos_period_pf"] >= 1.2,
        "g3_folds_ge_4_of_5": row["folds_positive"] >= 4,
        "g4_max_dd_le_20pct_daily": row["oos_max_drawdown_daily"] >= -0.20,
        "g5_max_asset_share_le_50pct": row["max_asset_profit_share"] <= 0.50,
        # RD-013's fail-closed band: a p within 2x of the threshold
        # either way counts as FAILED, so passing requires p < alpha/2.
        "g6_bonferroni": bool(p * 2.0 < alpha),
        "g8_episodes_ge_200_and_episode_pf_ge_1_2":
            row["oos_episodes"] >= 200 and row["oos_episode_pf"] >= 1.2,
    }
    if x2_row is not None:
        gates["g7_x2_costs"] = bool(x2_row["oos_compounded"] > 0
                                    and x2_row["oos_period_pf"] >= 1.2)
    mech = all(v for k, v in gates.items() if k != "g7_x2_costs")
    if row["oos_episodes"] < 200:
        verdict = "INSUFFICIENT_OOS_TRADES"
    elif mech and gates.get("g7_x2_costs", False):
        verdict = "PASS"
    elif mech:
        verdict = "MECHANICAL_PASS_X2_PENDING"
    else:
        verdict = "FAIL"
    return {"gates": gates, "bonferroni_alpha": alpha, "verdict": verdict}
