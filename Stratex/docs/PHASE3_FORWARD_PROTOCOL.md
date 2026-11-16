# Phase-3 Forward Protocol — Governed Demo Book

**Status:** decided package, TASK-STR-FWD-006 (2026-11-15). This document
is the single statement of the sizing and kill rules for every governed
forward book: the two RD-002 winners (ichimoku_trend tk_cloud,
dow_effect), the best_per_class sleeve (sleeve_shock_breakout +
sleeve_tsmom2_dual), the FORWARD_TEST lane, and the OANDA FX-MR-v4
engine (trader.py). It supersedes every earlier inline statement of
these numbers (registry reasons in `config_strategy.py` carry the same
values and point here).

**Why this document exists.** TASK-STR-RD-011 proved the originally
written pair — "1% per-trade risk cap" next to a "5% strategy-DD kill" —
is arithmetically inconsistent on pooled multi-symbol books: at 1% per
trade and measured concurrency of 11.9–21.3 simultaneous positions, a
book carries 12–21% of equity in aggregate stop-risk (heat), so ordinary
variance trips a 5% drawdown kill almost immediately (on RD-002's own
out-of-sample streams the kill fired on day 2 for ichimoku and day 4 for
dow; the survivable per-trade risk at that concurrency is 0.03–0.41%).
The kill was never the defect — the sizing was. The per-trade cap and
the heat cap are therefore stated **together, in one table, in this one
document**, so the pair cannot drift apart again.

## The decided package

| # | Rule | Decided value | Basis |
|---|------|---------------|-------|
| 1 | Per-trade risk | **0.1%** of equity per trade (pooled multi-symbol books) | **Venue equity** — the equity of the account the trade actually sits on |
| 2 | Aggregate heat cap | **2%** of equity per strategy — the sum of stop-risk over ALL simultaneously open positions of the strategy may never exceed it; a new trade is sized down to the remaining budget, and a strategy at the cap opens nothing | Venue equity |
| 3 | Strategy drawdown kill | **5%** — unchanged, never weakened. Computed **mark-to-market** (closed fills + current unrealized PnL) and evaluated **on the daemon's scan cadence** (every scan cycle, throttled to 30 s), not daily | Venue equity |
| 4 | Portfolio daily breaker | **3%** — unchanged. A **pause**, not a kill: it blocks new entries for the day; it never denylists a strategy and never closes positions | Venue equity (per engine) |
| 5 | Leverage | **3x** — reviewed and kept (daemon `BINANCE_LEVERAGE` pin) | — |
| 6 | Sleeve-level kill | **5% DD** — kept. Judged on compounded equity + max drawdown ONLY (no per-trade expectancy/PF kill for sleeve components), computed mark-to-market over **both components combined** | Combined equity of the venue accounts the sleeve trades on (Binance + OANDA) |
| 7 | Performance kill criteria | **Unchanged**: expectancy < 0 **or** profit factor < 1.0 after ≥ 50 **closed** trades auto-pauses the strategy | Closed fills only (never marked to market) |
| 8 | Vol-targeting | **Banned for dow_effect** — no volatility-scaled position sizing may be applied to it, in the daemon, in any strategy module, or in any future sizing change, without a new coordinator decision that names this ban | — |

Rules 1 and 2 are a pair: **0.1% per trade, 2% aggregate heat, stated
together or not at all.** Any future change to either number must amend
this table and re-derive the pair against rule 3 (at the heat cap, a
full correlated stop-out costs exactly the heat cap — 2% — which is
what makes the 5% kill survivable through ordinary variance rather than
a day-2 certainty).

## Rationale — measurement-phase sizing

This is **measurement-phase sizing**. The forward programme exists to
measure expectancy and profit factor, and both statistics are
**size-invariant**: a strategy's expectancy per trade and PF do not
change when positions are smaller. The package is therefore calibrated
to one goal — survive ordinary variance for the full measurement window
(≥ 50 closed trades per strategy, and the 8-week forward window) and
never produce a **spurious kill**: a kill fired by sizing arithmetic
rather than by the strategy's actual edge would destroy the measurement
the programme exists to collect. Exposure scales only **after** forward
proof, as a new coordinator decision taken on that evidence — never by
quietly editing a number in this table.

## Definitions

- **Venue equity**: the balance/equity reported by the venue account a
  position sits on (Binance demo-fapi for daemon crypto books; the
  OANDA practice account NAV for OANDA books). The composite
  cross-venue total is **never** a sizing or kill basis: before this
  package, daemon sizing used the composite (~$20.5k = demo-fapi
  ~$10.5k + OANDA ~$10k), so a "1%" crypto trade actually risked ~$205
  ≈ 2% of the account it sat on.
- **Stop-risk** of an open position: quantity × |entry − stop|. A
  position with no recorded stop is charged at the daemon's maximum
  stop distance (3% of notional) — its true risk is undefined, never
  zero.
- **Mark-to-market drawdown**: the peak-to-trough drawdown of the
  cumulative net-PnL curve of closed fills, extended by one final point
  carrying the book's current unrealized PnL. The performance criteria
  (rule 7) deliberately do **not** use this curve.
- **Scan cadence**: the daemon evaluates the guard at the top of every
  `scan_and_execute` cycle (after close reconciliation, before entry
  decisions), throttled to at most one evaluation per 30 s inside the
  continuous loop. Before this package the guard ran once per UTC day
  in the auto-prune slot and **not at all on days the daemon restarted**
  — an unrealized drawdown could grow unbounded between evaluations.

## Enforcement points

| Rule | Where enforced |
|------|----------------|
| 1, 2 (daemon books) | `autonomy/run_daemon.py` — sizing block in `_execute_signal`: venue equity via `MultiVenueEngine.get_venue_equity`, heat budget via `heat_capped_risk_amount` + `StratexTradingEngine._strategy_open_risk`. Env: `STRATEX_RISK_PER_TRADE_PCT=0.001`, `STRATEX_MAX_HEAT_PCT_PER_STRATEGY=0.02`. The per-position notional cap (`STRATEX_MAX_POSITION_PCT=0.10`) is denominated on the same venue equity; it binds before the risk cap only for very tight stops, and the venue-minimum-notional bump may not exceed the heat-capped risk budget. |
| 1, 2 (sleeve OANDA leg) | `oanda_demo/sleeve_runner.py` — `RISK_PER_TRADE_PCT=0.001`, `MAX_HEAT_PCT=0.02`; open risk tracked from committed `risk_usd` per trade (broker-stop fallback for legacy entries); remaining-budget sizing in `_position_units`. |
| 1, 2 (FX-MR-v4 engine) | `oanda_demo/trader.py` — `RISK_PER_TRADE_PCT=0.001`, `MAX_HEAT_PCT=0.02` over the engine's **own** trades only (ownership-scoped, as its trade management already is). Aligned to this package by TASK-STR-FWD-006 (the surface TASK-STR-FWD-004 is unpausing). |
| 3, 6, 7 | `measurement/forward_guard.py` (`evaluate`, `evaluate_sleeves`, `strategy_stats`) called from `run_daemon._maybe_apply_forward_guard` on the scan cadence. The sleeve's OANDA-leg unrealized PnL is published by the sleeve runner into its state file (`unrealized_pnl_usd`) every scan and consumed by the daemon guard; the daemon leg's unrealized comes from live positions. A breach denylists the strategy (entries paused; positions are never force-closed). |
| 4 | Daemon: `STRATEX_MAX_DAILY_LOSS_PCT=0.03` gate in `scan_and_execute`. Sleeve runner / trader: their own −3% daily breakers (`DAILY_LOSS_LIMIT_PCT=0.03`). |
| 5 | Server-1 environment pin `BINANCE_LEVERAGE=3` (daemon leverage at order time). |
| 8 | Verified absent from `run_daemon.py`, `multi_venue_engine.py`, `strategy_dow_effect.py`, `strategy_ichimoku_trend.py` (TASK-STR-FWD-006 grep audit); the ban is recorded in dow_effect's registry reason so any future sizing work meets it first. |

Registry entries for every governed strategy carry the machine-readable
pair `"risk_per_trade_pct": 0.001, "max_heat_pct": 0.02`
(`config_strategy.py`), so the values are checkable without reading
prose.

## Before / after (live Server-1 values)

Before-values are TASK-STR-FWD-002's verified live read of the deployed
code + `.env` (2026-11-15, nothing changed by that read). After-values
are this package as implemented; the live read-back after deployment is
recorded in the TASK-STR-FWD-006 completion comment on issue #35.

| Row | Before (live) | After (decided + implemented) |
|-----|---------------|-------------------------------|
| Per-trade risk | 1% (`STRATEX_RISK_PER_TRADE_PCT=0.01`) of **composite** ~$20.5k ≈ $205/trade ≈ 2% of the venue account | 0.1% of **venue** equity (≈ $10.50/trade at $10.5k demo-fapi equity) |
| Heat cap | **None** — only position count 30/venue + free-margin floor; theoretical worst case ~30% of composite ≈ 60% of the crypto venue at risk at once | 2% of venue equity per strategy, enforced at entry (resize-down, then block) |
| Notional cap | 10% of composite (`STRATEX_MAX_POSITION_PCT=0.10`); the wide-stop sleeve shock leg escaped it entirely | 10% of **venue** equity; min-notional bump additionally bounded by the heat-capped risk budget |
| Strategy DD kill | 5% of composite equity, **closed fills only**, once per UTC day, skipped on restart days | 5% of **venue** equity, **mark-to-market**, every scan cycle (30 s throttle) |
| Daily breaker | 3%, pause-only | 3%, pause-only — unchanged |
| Leverage | 3x | 3x — reviewed, kept |
| Sleeve kill | 5% DD, closed fills only, composite basis | 5% DD, mark-to-market both legs combined, combined venue-equity basis |
| Sleeve OANDA leg | 1% of NAV/trade, 25%-of-NAV notional cap, count 28, own −3% breaker, **no heat cap** | 0.1% of NAV/trade, 2% heat cap, caps/breaker otherwise unchanged |
| Performance kills | expectancy<0 or PF<1.0 after ≥50 closed trades | Unchanged |
| Vol-targeting (dow_effect) | Absent from code, ban nowhere written | Absent from code (grep-verified), ban written here + in the registry |

Demo only. Nothing in this package touches the live-trading guard, and
no rule here authorizes real-money trading.
