# Incident 2026-11-11 — Stratex testnet losses (> $2,000 in 12 hours)

**Status:** Root causes identified · fixes landed in this batch (see
`docs/BATCH_EXECUTION_PLAN.md` Batch 1)
**Owner action:** demo account reset + all positions closed (fresh baseline from
this point — the ledger from here on measures the fixes cleanly).

## What happened

The bot lost more than $2,000 on the demo/testnet account within ~12 hours.
The owner halted it and reset the account. The local ledger copy
(`testnet_trade_ledger.jsonl`, 64 trades, 2026-09) shows the same structural
problems that produced the live bleed.

## Evidence from the ledger (64 closed trades)

| Metric | Value |
|---|---|
| Strategy diversity | **1 of 8 configured** (SUPERTREND only) |
| Win rate | 17/64 = **26.6%** |
| Average win | +4.18 |
| Average loss | −1.03 |
| Trades exited < 20 min | **64/64 (100%)** |
| Same-entry-exit exits (fee churn) | 9/64 |
| Net PnL (this old sample) | +22.71 (small-sample luck; regime dependent) |

## Root causes (in order of severity)

### RC1 — No daily-loss circuit breaker (why it bled $2,000)
Nothing in the engine halts new entries after a daily drawdown. Risk caps exist
per-trade (1%) and per-position-count (8), but 8 concurrent × repeated
re-entries × ~1% risk each compounds through a whole losing day with no stop.
**Fix:** daily-loss circuit breaker — 3% daily loss → auto-pause ALL new entries
via the existing `trading_pause` flag + Telegram alert. (Batch 1 task 6.)

### RC2 — Fabricated win-rate prior (why bad trades passed the gate)
`strategy_supertrend.py` declared `_OOS_WIN_RATE_PRIOR = 0.80` ("80% sniper
mode") with R:R 1.0. The profitability gate computes expected value from the
strategy-supplied prior, so **every signal looked like +0.6R expected** —
0.80×1 − 0.20×1 — and passed. The realized win rate is 26.6%. The repo's own
governance (`strategy_registry.json` provenance note) had already burned this
exact pattern on `adx_ema`: *"The recorded claim was unsupported and
contradicted the evidence."*
**Fix:** prior replaced with the ledger-measured 0.266, R:R raised to 2.0 to
match the realized ~4:1 winner geometry with a haircut. (Batch 1 task 4.)

### RC3 — Churn brackets (why every trade died inside one candle)
64/64 trades exited in < 20 minutes. Brackets are computed from the signal
candle's ATR (SL ≈ 1.5×ATR of a 15m candle). On liquid pairs that distance is
smaller than one volatility burst, so SL or TP is hit almost immediately —
including 9 trades that closed at the exact entry price (pure fee bleed).
**Fix:** minimum bracket distance floor — SL/TP distances must be ≥ 10× the
round-trip fee cost and ≥ 0.25% of price; otherwise the signal is rejected as
churn-risk. (Batch 1 task 5.)

### RC4 — Single-strategy concentration (why one bad regime = red day)
8 strategies are configured in `ACTIVE_STRATEGIES` but only SUPERTREND is
`VALIDATED` in `PRODUCTION_STRATEGY_REGISTRY`, so governance blocked the other
7. One strategy × one regime dependence = concentrated losses when the regime
turns.
**Fix:** promote `factory_winner_1..5` to VALIDATED — they carry real mass-backtest
evidence (2,408–11,338 trades each, net profit factor 1.36–1.48, honest priors
0.305–0.431 already wired in `strategy_factory_winners.py`). Live trading
diversifies 1 → 6 strategies. (Batch 1 tasks 7–8.)

## Why the fixes are safe

- The circuit breaker uses the existing, battle-tested `trading_pause`
  file-backed flag (fail-closed semantics, same pattern as panic_state).
- Honest priors make the profitability gate **stricter**, not looser — signals
  must now clear friction with a 26.6% prior, so marginal churn trades get
  rejected instead of waved through.
- Factory winners were selected under realistic 8 bps maker/taker futures
  friction across 204 variations — the evidence standard the registry demands.
- Everything lands with tests (Batch 1 task 9) before the commit.

## Follow-ups (tracked in `docs/BATCH_EXECUTION_PLAN.md` Batch 2)

- Walk-forward validation of 2 more dormant strategies (target: ≥30 OOS trades,
  PF ≥ 1.0 before promotion).
- Regime filter for shorts (ledger shows shorts fighting the trend).
- Trailing-stop audit (protect the 4:1 winners at break-even after 1R).
- Per-symbol cooldown (stop revenge-entries on one symbol).
