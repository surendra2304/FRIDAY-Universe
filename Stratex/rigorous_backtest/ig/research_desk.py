"""Multi-agent research desk for Stratex — scanner/setup/plan/check.

TASK-IG-STR-05 (IG corpus item Det0-D8Oc41; skill structure adapted
from the day-trader-skill and tradermonty/claude-trading-skills repo
cards: scanner -> setup analysis -> plan -> risk checklist, with a
journal behind it — see desk_journal.py).

The "agents" here are deterministic role functions, not LLM calls:
  scan()          — filter candidate setups against market context
  analyse()       — describe a setup against its candles (trend, R:R,
                    where the entry sits in the recent range)
  pattern_match() — compare current price action with the last 3
                    similar patterns in 6 months + what happened after
                    each + the historical success rate (TASK-STR-067)
  plan()          — draft a sized plan from caller-supplied risk inputs
  risk_checklist()— fail-closed checks a plan must pass to be memo'd
                    (TASK-STR-069: six hardened, evidence-gated items —
                    clean-data re-test, >=50 trades, drawdown-vs-return
                    gate, tiny-size incubation, repainting warning, bot
                    provenance)
  run_desk()      — run the chain and produce ONE structured memo

RESEARCH ONLY. A plan produced here is a memo — it is not an order, it
is not sent anywhere, and passing the checklist promotes nothing: any
strategy behind a setup still faces the RD programme bar and the
Phase-3 forward protocol before it may trade, even on demo. Risk
parameters are caller inputs; this module imports nothing from
production and changes no governance.

Stdlib only, Python 3.10-compatible.
"""


def _ema(values, period):
    if not values:
        return None
    k = 2.0 / (period + 1)
    out = values[0]
    for v in values[1:]:
        out = v * k + out * (1 - k)
    return out


def scan(setups, contexts=None, min_adv_quote=None, max_spread_bps=None):
    """Stage 1 — scanner. Keeps setups whose market context (when
    supplied) clears the caller's liquidity/spread thresholds. A setup
    with no context is kept but flagged context_missing: the desk
    reports what it does not know instead of guessing."""
    kept, dropped = [], []
    contexts = contexts or {}
    for s in setups:
        ctx = contexts.get(s["symbol"])
        if ctx is None:
            kept.append({**s, "scan_flags": ["context_missing"]})
            continue
        flags = []
        if min_adv_quote is not None and ctx.get("adv_quote", 0) < min_adv_quote:
            flags.append("below_min_adv")
        if max_spread_bps is not None and ctx.get("spread_bps", 1e18) > max_spread_bps:
            flags.append("spread_too_wide")
        if flags:
            dropped.append({**s, "scan_flags": flags})
        else:
            kept.append({**s, "scan_flags": []})
    return {"kept": kept, "dropped": dropped}


def _norm_shape(closes):
    """Normalised cumulative log-return profile of a window (0..1 range).

    Flat windows (range ~ 0) map to all zeros. Shape, not level: two
    windows at different prices but the same path compare equal."""
    if not closes:
        return []
    base = closes[0]
    if base <= 0:
        return [0.0] * len(closes)
    import math
    prof = [math.log(c / base) if c > 0 else 0.0 for c in closes]
    lo, hi = min(prof), max(prof)
    span = hi - lo
    if span < 1e-12:
        return [0.0] * len(prof)
    return [(p - lo) / span for p in prof]


def _shape_distance(a, b):
    if len(a) != len(b) or not a:
        return 1.0
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a)


def _candle_time(candle):
    """Unix seconds for a candle, accepting 'time'/'timestamp' in s or ms."""
    for key in ("time", "timestamp"):
        v = candle.get(key)
        if v is not None:
            v = float(v)
            return v / 1000.0 if v > 1e11 else v
    return None


def pattern_match(candles, direction, window=10, forward=10,
                  lookback_days=180, max_matches=3):
    """Stage 2b — pattern comparison (TASK-STR-067).

    Compare the current price action (last `window` candles) with the
    last `max_matches` similar windows inside the last `lookback_days`
    of history, and report what happened after each plus the
    historical success rate. Research surface only — no signal, no
    entry, no order.

    Similarity is the mean absolute gap between the normalised
    cumulative-return shapes (0..1, 1 = identical path). Candidate
    windows must end, with their `forward`-candle outcome window,
    before the current window starts, so no outcome leaks into the
    pattern being compared. Matches are picked greedily by similarity
    and never overlap each other.

    `direction` ("long"/"short") is the setup direction the outcomes
    are judged against: a match succeeds when its forward move agrees
    with it (flat forward moves never succeed). With fewer than
    `2 * window + forward` candles there is not even one full candidate
    plus its outcome plus the current window, so the result says
    `insufficient_history` instead of guessing."""
    n = len(candles)
    result = {"status": "ok", "window": window, "forward": forward,
              "lookback_days": lookback_days,
              "lookback_applied": False,
              "current_window": None, "matches_found": 0,
              "matches": [], "successes": 0, "success_rate": None}
    if n < window:
        result["status"] = "insufficient_history"
        result["reason"] = "need at least %d candles for the current window, got %d" % (window, n)
        return result
    if n < 2 * window + forward:
        result["status"] = "insufficient_history"
        result["reason"] = ("need at least %d candles for one candidate + "
                            "outcome + current window, got %d"
                            % (2 * window + forward, n))
        return result
    closes = [c["close"] for c in candles]
    cur_start = n - window
    cur_shape = _norm_shape(closes[cur_start:])
    cur_net = closes[-1] / closes[cur_start] - 1.0 if closes[cur_start] else 0.0
    times = [_candle_time(c) for c in candles]
    cutoff = None
    if times[cur_start] is not None:
        cutoff = times[cur_start] - lookback_days * 86400.0
        result["lookback_applied"] = True
    result["current_window"] = {
        "start_index": cur_start, "end_index": n - 1,
        "start_time": times[cur_start], "end_time": times[-1],
        "net_return_pct": cur_net * 100.0,
    }
    candidates = []
    last_j = n - 2 * window - forward
    for j in range(0, last_j + 1):
        if cutoff is not None and times[j] is not None and times[j] < cutoff:
            continue
        shape = _norm_shape(closes[j:j + window])
        dist = _shape_distance(cur_shape, shape)
        candidates.append((dist, j))
    candidates.sort()
    picked = []
    for dist, j in candidates:
        if len(picked) >= max_matches:
            break
        if any(abs(j - pj) < window for _, pj in picked):
            continue
        end_close = closes[j + window - 1]
        fwd_closes = closes[j + window:j + window + forward]
        fwd_ret = fwd_closes[-1] / end_close - 1.0 if end_close else 0.0
        fwd_dir = ("up" if fwd_ret > 0.005 else
                   "down" if fwd_ret < -0.005 else "flat")
        success = (fwd_dir == "up" and direction == "long") or \
                  (fwd_dir == "down" and direction == "short")
        picked.append((dist, j))
        pat_net = closes[j + window - 1] / closes[j] - 1.0 if closes[j] else 0.0
        result["matches"].append({
            "start_index": j, "end_index": j + window - 1,
            "start_time": times[j], "end_time": times[j + window - 1],
            "similarity": max(0.0, 1.0 - dist),
            "pattern_net_return_pct": pat_net * 100.0,
            "forward_return_pct": fwd_ret * 100.0,
            "forward_direction": fwd_dir,
            "success": success,
        })
    result["matches_found"] = len(result["matches"])
    result["successes"] = sum(1 for m in result["matches"] if m["success"])
    if result["matches_found"]:
        result["success_rate"] = result["successes"] / result["matches_found"]
    return result


def analyse(setup, candles):
    """Stage 2 — setup analysis against recent candles (dicts with
    high/low/close). Descriptive only."""
    closes = [c["close"] for c in candles]
    if len(closes) < 30:
        return {"symbol": setup["symbol"], "trend": "unknown",
                "reason": "insufficient candles (%d < 30)" % len(closes)}
    fast = _ema(closes[-30:], 10)
    slow = _ema(closes[-30:], 30)
    slope = (fast - slow) / slow if slow else 0.0
    trend = "up" if slope > 0.001 else "down" if slope < -0.001 else "flat"
    recent = candles[-30:]
    hi = max(c["high"] for c in recent)
    lo = min(c["low"] for c in recent)
    entry = setup["entry_ref"]
    pos = None if hi == lo else (entry - lo) / (hi - lo)
    risk = abs(entry - setup["invalidation"])
    reward = abs(setup["target"] - entry)
    return {
        "symbol": setup["symbol"],
        "trend": trend,
        "ema_slope": slope,
        "entry_range_position": pos,
        "risk_per_unit": risk,
        "reward_per_unit": reward,
        "rr_ratio": (reward / risk) if risk > 0 else None,
        "aligned": (trend == "up" and setup["direction"] == "long")
                   or (trend == "down" and setup["direction"] == "short"),
    }


def plan(setup, equity, risk_per_trade_pct):
    """Stage 3 — draft a sized plan (a memo, never an order)."""
    if equity <= 0:
        raise ValueError("equity must be > 0")
    if risk_per_trade_pct <= 0:
        raise ValueError("risk_per_trade_pct must be > 0")
    risk_per_unit = abs(setup["entry_ref"] - setup["invalidation"])
    if risk_per_unit == 0:
        raise ValueError("invalidation must differ from entry_ref")
    risk_amount = equity * risk_per_trade_pct
    return {
        "symbol": setup["symbol"],
        "timeframe": setup.get("timeframe"),
        "direction": setup["direction"],
        "entry_ref": setup["entry_ref"],
        "invalidation": setup["invalidation"],
        "target": setup["target"],
        "units": risk_amount / risk_per_unit,
        "risk_amount": risk_amount,
        "equity": equity,
        "risk_per_trade_pct": risk_per_trade_pct,
        "status": "DRAFT — research memo only, not an order",
    }


def risk_checklist(plan_draft, setup, max_risk_pct, min_rr=1.5,
                   evidence=None, min_trades=50, max_dd_to_return=0.5):
    """Stage 4 — fail-closed checklist. `passed` requires every item.

    TASK-STR-069: the checklist gains six hardened items, each gated on
    caller-supplied backtest `evidence` (a dict). An item with no
    evidence is recorded unevaluated (``ok`` True, ``evaluated`` False)
    so a plan with no backtest evidence keeps the pre-STR-069 behaviour;
    the result's ``unevaluated`` list names what was never proven. When
    evidence IS supplied, the item is evaluated and can fail the
    checklist. The desk reports what it does not know instead of
    guessing (the same rule as scan()'s context_missing flag).

    Evidence keys (all optional):
      clean_data_retest (bool) — a clean-data / unseen-data re-test ran
          after the big backtest.
      trade_count (int) — trades in the backtest; must be >= min_trades.
      max_drawdown_pct, total_return_pct (floats) — drawdown-vs-return
          robustness gate: max drawdown must be <= max_dd_to_return *
          total return (default: the strategy earns at least 2x its
          worst drawdown). A non-positive return fails the gate.
      tiny_size_incubated (bool) — tiny-size incubation ran before any
          scale-up.
      repainting (bool) — True means the signal repaints: the backtest
          cannot be trusted, so the item fails (a warning, recorded).
      bot_built_by_us (bool) — True means the bot was built by us;
          False fails: never run a bot you did not build.
    """
    items = []

    def add(name, ok, detail, evaluated=True):
        items.append({"name": name, "ok": bool(ok), "detail": detail,
                      "evaluated": bool(evaluated)})

    inv, entry, tgt = setup["invalidation"], setup["entry_ref"], setup["target"]
    if setup["direction"] == "long":
        add("invalidation_below_entry", inv < entry,
            "long invalidation %s vs entry %s" % (inv, entry))
        add("target_above_entry", tgt > entry,
            "long target %s vs entry %s" % (tgt, entry))
    elif setup["direction"] == "short":
        add("invalidation_above_entry", inv > entry,
            "short invalidation %s vs entry %s" % (inv, entry))
        add("target_below_entry", tgt < entry,
            "short target %s vs entry %s" % (tgt, entry))
    else:
        add("direction_valid", False, "direction %r" % setup["direction"])
    risk = abs(entry - inv)
    rr = abs(tgt - entry) / risk if risk > 0 else 0.0
    add("rr_meets_minimum", rr >= min_rr, "R:R %.2f vs min %.2f" % (rr, min_rr))
    cap = plan_draft["equity"] * max_risk_pct
    add("risk_within_cap", 0 < plan_draft["risk_amount"] <= cap,
        "risk_amount %.2f vs cap %.2f" % (plan_draft["risk_amount"], cap))
    add("research_only", True,
        "plan is a research memo; promotion requires the RD bar + forward protocol")

    # TASK-STR-069 hardened items (evidence-gated; see docstring).
    ev = evidence or {}
    if "clean_data_retest" in ev:
        add("clean_data_retest", bool(ev["clean_data_retest"]),
            "clean-data / unseen-data re-test after the big backtest: %s"
            % ("done" if ev["clean_data_retest"] else "NOT done"))
    else:
        add("clean_data_retest", True,
            "clean-data / unseen-data re-test: not supplied — unevaluated",
            evaluated=False)
    if ev.get("trade_count") is not None:
        add("min_trades", ev["trade_count"] >= min_trades,
            "%s trades vs minimum %s" % (ev["trade_count"], min_trades))
    else:
        add("min_trades", True,
            "trade count: not supplied — unevaluated", evaluated=False)
    dd, ret = ev.get("max_drawdown_pct"), ev.get("total_return_pct")
    if dd is not None and ret is not None:
        add("drawdown_vs_return",
            ret > 0 and dd <= max_dd_to_return * ret,
            "max drawdown %.2f%% vs total return %.2f%% "
            "(gate: drawdown <= %.0f%% of return)"
            % (dd, ret, max_dd_to_return * 100))
    else:
        add("drawdown_vs_return", True,
            "drawdown/return: not supplied — unevaluated", evaluated=False)
    if "tiny_size_incubated" in ev:
        add("tiny_size_incubation", bool(ev["tiny_size_incubated"]),
            "tiny-size incubation before scale-up: %s"
            % ("done" if ev["tiny_size_incubated"] else "NOT done"))
    else:
        add("tiny_size_incubation", True,
            "tiny-size incubation: not supplied — unevaluated",
            evaluated=False)
    if "repainting" in ev:
        add("repainting_check", not ev["repainting"],
            "WARNING: signal repaints — backtest results cannot be trusted"
            if ev["repainting"] else "signal does not repaint")
    else:
        add("repainting_check", True,
            "repainting status: not supplied — unevaluated", evaluated=False)
    if "bot_built_by_us" in ev:
        add("bot_provenance", bool(ev["bot_built_by_us"]),
            "bot built by us" if ev["bot_built_by_us"]
            else "bot NOT built by us — never run a bot you did not build")
    else:
        add("bot_provenance", True,
            "bot provenance: not supplied — unevaluated", evaluated=False)

    return {"passed": all(i["ok"] for i in items), "items": items,
            "unevaluated": [i["name"] for i in items if not i["evaluated"]]}


def run_desk(setups, contexts, candles_by_symbol, equity,
             risk_per_trade_pct, max_risk_pct, min_rr=1.5,
             min_adv_quote=None, max_spread_bps=None,
             pattern_window=10, pattern_forward=10,
             pattern_lookback_days=180, backtest_evidence=None):
    """Run the full desk chain and return one structured memo dict.

    `backtest_evidence` (optional) maps a setup symbol to the backtest
    evidence dict its checklist is hardened against (TASK-STR-069); a
    symbol with no entry is checked with no evidence (hardened items
    unevaluated, named in the checklist's ``unevaluated`` list)."""
    stage1 = scan(setups, contexts, min_adv_quote, max_spread_bps)
    analyses, plans, checks, patterns = {}, [], [], {}
    for s in stage1["kept"]:
        candles = candles_by_symbol.get(s["symbol"], [])
        analyses[s["symbol"]] = analyse(s, candles)
        p = plan(s, equity, risk_per_trade_pct)
        ev = (backtest_evidence or {}).get(s["symbol"])
        chk = risk_checklist(p, s, max_risk_pct, min_rr, evidence=ev)
        plans.append(p)
        checks.append({"symbol": s["symbol"], **chk})
        # TASK-STR-067: pattern-match section per kept setup.
        patterns[s["symbol"]] = pattern_match(
            candles, s["direction"], window=pattern_window,
            forward=pattern_forward, lookback_days=pattern_lookback_days)
    return {
        "type": "memo",
        "desk": "stratex-research-desk",
        "research_only": True,
        "scan": {"kept": [s["symbol"] for s in stage1["kept"]],
                 "dropped": [{"symbol": d["symbol"], "flags": d["scan_flags"]}
                             for d in stage1["dropped"]]},
        "analyses": analyses,
        "plans": plans,
        "checklists": checks,
        "pattern_matches": patterns,
        "summary": {
            "setups_in": len(setups),
            "plans_drafted": len(plans),
            "checklists_passed": sum(1 for c in checks if c["passed"]),
            "pattern_matches_found": sum(
                p["matches_found"] for p in patterns.values()),
        },
    }
