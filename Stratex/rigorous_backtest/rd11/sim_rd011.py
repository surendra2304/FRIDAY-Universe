#!/usr/bin/env python3
"""TASK-STR-RD-011 — position sizing & portfolio optimisation simulation
on the TASK-STR-RD-002 out-of-sample trade streams.

Construction rules (all disclosed in RESULTS_RD11.md):
 - OOS filter identical to RD-002's Stage-C loader: entry_time >= the
   row's first-fold oos_start and < 2026-11-01.
 - Daily book returns: rd2.combo.stream_daily_returns, imported
   unchanged (equal-weight book: a day's return = sum of that day's
   exiting trades' net returns / positions open that day).
 - Sizing = a causal exposure multiplier m_t on the unit book's daily
   returns. Every multiplier uses strictly past data only.
 - Kill simulation: phase-3 rule — running drawdown from peak beyond
   5% halts the strategy permanently; reported alongside the unkilled
   path.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parents[1]  # Stratex/rigorous_backtest
GIT = BASE / "results_rd2"
BAK = BASE / "results_rd11" / "streams"  # rows recovered from the RD-002
# crew's on-disk full backup (integrity proof in RESULTS_RD11.md)
OUT = BASE / "results_rd11"
sys.path.insert(0, str(BASE.parent))  # Stratex/

from rigorous_backtest.rd2.combo import stream_daily_returns  # noqa: E402
from rigorous_backtest.rd.common import trades_from_json  # noqa: E402

ERA_END = pd.Timestamp("2026-11-01", tz="UTC")
FOLDS = {"W1": ("2024-07-01", "2025-01-01"), "W2": ("2025-01-01", "2025-07-01"),
         "W3": ("2025-07-01", "2026-01-01"), "W4": ("2026-01-01", "2026-07-01"),
         "W5": ("2026-07-01", "2026-11-01")}

CONFIGS = {
    "ichimoku_tk_cloud__crypto30__4h": ("git", "grid_rows/ichimoku_trend__tk_cloud__crypto30__4h.json", "WINNER"),
    "dow_reversal__crypto30__1d": ("bak", "dow_effect__reversal__crypto30__1d.json", "WINNER"),
    "bollinger_p50sd2__crypto30__1d": ("git", "grid_rows/bollinger_trend__p50_sd2.0__crypto30__1d.json", "WATCHLIST"),
    "shock_k1.0__crypto30__1d": ("git", "grid_rows/shock_breakout__k1.0__crypto30__1d.json", "WATCHLIST"),
    "adx_ema_bare__crypto30__4h": ("git", "gov_rows/strategy_adx_ema__bare__crypto30__4h.json", "WATCHLIST"),
    "tsmom2_dual__comm7__4h": ("git", "grid_rows/tsmom2_dual__roc30_ema200__comm7__4h.json", "WATCHLIST"),
}
SLEEVE = {
    "shock_k1.0__crypto30__1wk": "shock_breakout__k1.0__crypto30__1wk.json",
    "tsmom2_roc90__forex28__1d": "tsmom2_dual__roc90_ema200__forex28__1d.json",
    "vol_adaptive_gate__comm7__4h": "vol_adaptive_trend__ema20_50_gate__comm7__4h.json",
    "keltner_m2.0__idx7__1d": "keltner_breakout__ema20_m2.0__idx7__1d.json",
}


def load_oos(src, rel):
    row = json.loads((GIT if src == "git" else BAK).joinpath(rel).read_text())
    prof = row["report"]["fold_profile"]
    start = pd.Timestamp(row["report"]["per_fold"][prof[0]]["oos_start"], tz="UTC")
    trades = trades_from_json(row["trades"])
    oos = [t for t in trades if start <= t.entry_time < ERA_END]
    return oos, row


def trade_stats(trades):
    r = np.array([t.net_return for t in trades])
    losses = r[r <= 0]
    return {"n": len(r), "expectancy": float(r.mean()),
            "pf": float(r[r > 0].sum() / abs(losses.sum())),
            "e_loss_mag": float(np.abs(losses).mean()) if len(losses) else 0.0,
            "win_rate": float((r > 0).mean())}


def book(trades):
    """Unit daily book returns + avg concurrency (their construction)."""
    s = stream_daily_returns(trades)
    return s, float(s.attrs.get("avg_concurrency", 1.0))


def metrics(daily):
    eq = (1.0 + daily).cumprod()
    total = float(eq.iloc[-1] - 1.0)
    dd_series = eq / eq.cummax() - 1.0
    maxdd = float(dd_series.min())
    sd = float(daily.std())
    sharpe = float(daily.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    # kill simulation: first close where running DD < -5%
    kill_date, kill_ret = None, None
    breached = dd_series[dd_series < -0.05]
    if len(breached):
        kill_date = breached.index[0]
        kill_ret = float(eq.loc[kill_date] - 1.0)
    return {"total_return": total, "max_dd": maxdd, "sharpe_ann": sharpe,
            "calmar": (total / abs(maxdd)) if maxdd < 0 else None,
            "killed": kill_date is not None,
            "kill_date": str(kill_date.date()) if kill_date is not None else None,
            "days_to_kill": int((kill_date - eq.index[0]).days) if kill_date is not None else None,
            "return_at_kill": kill_ret,
            "worst_day": float(daily.min()),
            "days_beyond_3pct_loss": int((daily < -0.03).sum())}


def fold_metrics(daily):
    out = {}
    for f, (a, b) in FOLDS.items():
        seg = daily.loc[a:b]
        if len(seg) == 0 or (seg == 0).all():
            out[f] = None
            continue
        eq = (1.0 + seg).cumprod()
        out[f] = {"total_return": float(eq.iloc[-1] - 1.0),
                  "max_dd": float((eq / eq.cummax() - 1.0).min())}
    return out


def m_fixed(stats, kbar):
    """Constant multiplier so the average losing trade risks 1% of equity:
    a trade's book contribution is r_i / open_count (~r_i / kbar)."""
    return 0.01 * kbar / stats["e_loss_mag"] if stats["e_loss_mag"] > 0 else 0.0


def multipliers(unit, m_fix, cap_mult=2.0):
    """Causal multiplier paths for each scheme. Returns dict name->Series."""
    out = {}
    out["unit"] = pd.Series(1.0, index=unit.index)
    out["fixed1pct"] = pd.Series(m_fix, index=unit.index)
    cap = cap_mult * m_fix
    # vol target: target = full-window daily vol of the fixed book
    sigma_star = float((unit * m_fix).std())
    trail_vol = unit.rolling(60).std().shift(1)
    mv = sigma_star / trail_vol
    mv = mv.clip(0.0, cap)
    mv[trail_vol.isna()] = m_fix
    out["voltarget"] = mv
    # fractional Kelly on trailing 252d of unit returns, min 120 obs
    mu = unit.rolling(252).mean().shift(1)
    var = unit.rolling(252).var().shift(1)
    cnt = unit.rolling(252).count().shift(1)
    fstar = (mu / var).where((var > 0) & (cnt >= 120))
    for lam, name in ((0.25, "kelly25"), (0.5, "kelly50")):
        mk = (lam * fstar).clip(0.0, cap)
        mk[fstar.isna()] = 0.0
        out[name] = mk
    return out


def dd_capped_m(unit, target_dd=0.05):
    """Diagnostic: largest constant m (grid) whose full-window max DD
    stays within target_dd. Fitted on the judged window — upper bound,
    NOT a tradable rule."""
    best = 0.0
    for m in np.arange(0.01, 8.001, 0.01):
        eq = (1.0 + unit * m).cumprod()
        if float((eq / eq.cummax() - 1.0).min()) >= -target_dd:
            best = float(m)
        else:
            break
    return best


def run_book(name, trades):
    stats = trade_stats(trades)
    unit, kbar = book(trades)
    mf = m_fixed(stats, kbar)
    mults = multipliers(unit, mf)
    res = {"n_trades": stats["n"], "expectancy_pct": stats["expectancy"] * 100,
           "pf": stats["pf"], "win_rate": stats["win_rate"],
           "avg_concurrency": kbar, "m_fixed1pct": mf, "schemes": {}}
    for sname, m in mults.items():
        sized = unit * m
        mm = metrics(sized)
        mm["avg_multiplier"] = float(m.mean())
        res["schemes"][sname] = mm
    res["folds"] = {s: fold_metrics(unit * mults[s])
                    for s in ("fixed1pct", "voltarget", "kelly25")}
    mcap = dd_capped_m(unit)
    res["dd_capped"] = {"m": mcap, **metrics(unit * mcap)}
    # W1-calibrated fixed sensitivity (first-fold trades only)
    prof_start = min(t.entry_time for t in trades)
    first_fold = None
    for f, (a, b) in FOLDS.items():
        if pd.Timestamp(a, tz="UTC") <= prof_start < pd.Timestamp(b, tz="UTC"):
            first_fold = (a, b)
            break
    w1 = [t for t in trades
          if pd.Timestamp(first_fold[0], tz="UTC") <= t.entry_time < pd.Timestamp(first_fold[1], tz="UTC")]
    _, k1 = book(w1)
    mf_w1 = m_fixed(trade_stats(w1), k1)
    res["fixed1pct_firstfold_cal"] = {"m": mf_w1, **metrics(unit * mf_w1)}
    return res, unit


def risk_parity_weights(cov):
    n = cov.shape[0]
    w = np.ones(n) / n
    C = cov.values
    for _ in range(500):
        port_var = float(w @ C @ w)
        if port_var <= 0:
            break
        target = port_var / n
        mrc = C @ w
        for i in range(n):
            if C[i, i] <= 0:
                continue
            b = mrc[i] - C[i, i] * w[i]
            disc = b * b + 4 * C[i, i] * target
            w[i] = (-b + np.sqrt(max(disc, 0.0))) / (2 * C[i, i])
            mrc = C @ w
    return w / w.sum()


def combine_books(units, weighting):
    """Daily portfolio returns from unit book series. equal = Stage-C
    mean; invvol = Stage-C method; riskparity = trailing-252d ERC,
    monthly refresh, strictly past (equal until 120 obs)."""
    R = pd.DataFrame(units)
    if weighting == "equal":
        return R.mean(axis=1)
    if weighting == "invvol":
        weights = pd.DataFrame(0.0, index=R.index, columns=R.columns)
        cur = {c: 1.0 / len(R.columns) for c in R.columns}
        last = None
        for d in R.index:
            if last is None or (d - last).days >= 30:
                hist = R.loc[:d].iloc[:-1]
                if len(hist) >= 60:
                    vol = hist.std()
                    inv = {c: (1.0 / vol[c] if vol[c] > 1e-9 else 0.0) for c in R.columns}
                    tot = sum(inv.values())
                    if tot > 0:
                        cur = {c: inv[c] / tot for c in R.columns}
                last = d
            for c in R.columns:
                weights.loc[d, c] = cur[c]
        return (weights.shift(1).fillna(1.0 / len(R.columns)) * R).sum(axis=1)
    if weighting == "riskparity":
        port = pd.Series(0.0, index=R.index)
        cur = np.ones(len(R.columns)) / len(R.columns)
        last = None
        cols = list(R.columns)
        for d in R.index:
            if last is None or (d - last).days >= 30:
                hist = R.loc[:d].iloc[:-1].tail(252)
                if len(hist) >= 120:
                    cur = risk_parity_weights(hist.cov())
                last = d
            port.loc[d] = float(R.loc[d].values @ cur)
        return port
    raise ValueError(weighting)


def run_portfolio(name, member_units, trades_by_member):
    """member_units: dict config->unit daily series; trades_by_member:
    dict config->OOS trades (pooled for the fixed-1% calibration;
    kbar = mean of member concurrencies)."""
    member_trades = [t for v in trades_by_member.values() for t in v]
    pooled_stats = trade_stats(member_trades)
    kbars = []
    for tlist in trades_by_member.values():
        _, k = book(tlist)
        kbars.append(k)
    kbar = float(np.mean(kbars))
    mf_unit = m_fixed(pooled_stats, kbar)
    res = {"members": sorted(member_units.keys()), "weightings": {}}
    for w in ("equal", "riskparity", "invvol"):
        unit = combine_books(member_units, w)
        mults = multipliers(unit, mf_unit)
        entry = {"m_fixed1pct": mf_unit, "schemes": {}}
        for sname in ("unit", "fixed1pct", "voltarget", "kelly25", "kelly50"):
            entry["schemes"][sname] = metrics(unit * mults[sname])
        mcap = dd_capped_m(unit)
        entry["dd_capped"] = {"m": mcap, **metrics(unit * mcap)}
        res["weightings"][w] = entry
    return res


def file_provenance():
    import hashlib
    prov = {}
    paths = {}
    for _n, (src, rel, _c) in CONFIGS.items():
        paths[rel] = (GIT if src == "git" else BAK) / rel
    for rel in SLEEVE.values():
        paths[rel] = BAK / rel
    for rel, p in sorted(paths.items()):
        raw = p.read_bytes()
        row = json.loads(raw)
        prov[rel] = {
            "file_sha256": hashlib.sha256(raw).hexdigest(),
            "trades_sha256": hashlib.sha256(json.dumps(
                row["trades"], sort_keys=True,
                separators=(",", ":")).encode()).hexdigest(),
            "n_trades_total": len(row["trades"]),
        }
    return prov


def main():
    results = {"configs": {}, "portfolios": {},
               "stream_provenance": file_provenance()}
    units, trades_by = {}, {}
    for name, (src, rel, cls) in CONFIGS.items():
        oos, _row = load_oos(src, rel)
        trades_by[name] = oos
        r, unit = run_book(name, oos)
        r["class"] = cls
        r["source"] = src
        results["configs"][name] = r
        units[name] = unit
        print(f"{name}: n={r['n_trades']} PF={r['pf']:.3f} kbar={r['avg_concurrency']:.1f} "
              f"m_fix={r['m_fixed1pct']:.2f} | unit DD {r['schemes']['unit']['max_dd']:.3f} "
              f"| fixed tot {r['schemes']['fixed1pct']['total_return']:+.3f} DD {r['schemes']['fixed1pct']['max_dd']:.3f} killed={r['schemes']['fixed1pct']['killed']} "
              f"| vol tot {r['schemes']['voltarget']['total_return']:+.3f} DD {r['schemes']['voltarget']['max_dd']:.3f} killed={r['schemes']['voltarget']['killed']}")
    sleeve_units, sleeve_trades_by = {}, {}
    for name, rel in SLEEVE.items():
        oos, _row = load_oos("bak", rel)
        u, _k = book(oos)
        sleeve_units[name] = u
        sleeve_trades_by[name] = oos
    sets = {
        "WIN2_winners": ({m: units[m] for m in
                          ("ichimoku_tk_cloud__crypto30__4h", "dow_reversal__crypto30__1d")},
                         {m: trades_by[m] for m in
                          ("ichimoku_tk_cloud__crypto30__4h", "dow_reversal__crypto30__1d")}),
        "ALL6_winners_plus_watchlist": (units, trades_by),
        "SLEEVE4_best_per_class": (sleeve_units, sleeve_trades_by),
    }
    for pname, (mu, mt) in sets.items():
        results["portfolios"][pname] = run_portfolio(pname, mu, mt)
        print(f"portfolio {pname} done")
    (OUT / "synthesis_rd11.json").write_text(json.dumps(results, indent=1, default=str))
    print("wrote", OUT / "synthesis_rd11.json")


if __name__ == "__main__":
    main()
