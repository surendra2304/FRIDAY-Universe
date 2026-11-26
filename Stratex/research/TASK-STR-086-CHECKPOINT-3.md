# TASK-STR-086 — Checkpoint 3: chart leg run on the authorised alternate venue — DONE

- **Task:** TASK-STR-086 (P3, Stratex staged chart-analysis checklist, 7-stage screenshot pipeline)
- **Worker:** Muse TP6
- **Filed:** 2026-11-25 ~18:25 IST
- **Branch:** `musetp6/task-str-086-staged-chart-checklist`
- **Claim of record:** hub 7157064327 (~14:00 IST). Checkpoint 1 hub 7157143111, checkpoint 2 hub 7160391190.

## Ruling received — WATCH098 ruling 2 (hub 7161941236, ~18:15 IST)

> "TP6 STR-086 chart leg: AUTHORISED — run the chart leg against an
> alternate public venue (read-only public market-data API, no fleet
> execution, no credentials, no deploy). Binance demo-fapi HTTP 451 is
> verified. File the venue substitution + the 451 as evidence and close
> STR-086; if the alternate venue also fails, STR-086 stays held and
> TP6 moves to VYR-063."

The chart-leg block from checkpoint 2 is cleared by this ruling. No
fleet execution, no credentials, no deploy were used for this leg.

## Venue substitution (filed as evidence)

- **Blocked venue:** Binance Demo Trading demo-fapi
  (`https://demo-fapi.binance.com/fapi/v1/klines`) — HTTP 451
  (location eligibility), verified independently in checkpoint 2
  (hub 7160391190). The 451 is recorded in the checkpoint-2 report
  (`TASK-STR-086-STAGED-REPORT-BTCUSDT-20261125T105315Z.*`).
- **Alternate venue:** Kraken public OHLC (`https://api.kraken.com/0/public/OHLC`,
  no key, read-only). Chosen because it serves all three pipeline
  timeframes (1h = 60, 4h = 240, 1d = 1440 minutes); Coinbase's public
  candles lack a 4h granularity. Pair mapping is explicit and
  fail-closed: `BTCUSDT -> XBTUSD`; an unmapped symbol or unsupported
  interval raises instead of guessing.
- **Code:** `Stratex/research/staged_chart_checklist.py` gains
  `fetch_klines_kraken` (parses Kraken `[time, open, high, low, close,
  vwap, volume, count]` rows, drops the still-forming candle per the
  desk's closed-candle convention, returns the last `limit` closed
  rows), `fetch_for_venue`, a `--venue {demo-fapi,kraken}` CLI flag
  (default still demo-fapi), and venue/contract-type threading into
  stages 2 and 4 so the report names the venue actually used.
  Stage 4 for Kraken records contract type "spot (Kraken XBTUSD)" and
  no funding rate (no funding feed on spot) — nothing synthesised.
- **Tests:** 38/38 pass (`python3 -m unittest
  test_staged_chart_checklist`, run first-hand this run), up from 28/28:
  10 new tests cover Kraken parsing, forming-candle drop, limit
  slicing, error envelope, HTTP-error surfacing, fail-closed symbol /
  interval, unknown-venue rejection, and the venue label recorded in
  the pipeline report.

## Live chart leg — one real chart, end to end

Run first-hand this run, on this VM, read-only, no fleet:

```
$ python3 staged_chart_checklist.py BTCUSDT --venue kraken
Verdict: SETUP
  stage 1 market_structure: PASS
  stage 2 data_quality: PASS
  stage 3 timeframe_context: PASS
  stage 4 fundamentals: PASS
  stage 5 news_sentiment: INCONCLUSIVE
  stage 6 risk_levels: PASS
  stage 7 final_report: PASS
```

- **Report files (on branch):**
  `Stratex/research/TASK-STR-086-STAGED-REPORT-BTCUSDT-20261125T125003Z.json`
  and `.md`.
- **Verdict: SETUP SHORT BTCUSDT** — entry 58564.60, stop 59362.61,
  target 56968.58, R:R 2.00 (min-R:R gate 1.2: pass). ATR(14) 532.01.
  Reference sizing at the desk's 0.5% risk/trade on $10,000 reference
  equity: $50.00 risk, 0.0627 reference size. Reference equity is a
  sizing reference only, not an account balance.
- **Structure:** regime TREND_DOWN, EMA alignment bearish.
- **Data quality:** all three timeframes 250/250 bars, 0 gaps, feed
  fresh (1d last close 2026-11-24 23:59:59Z; 4h/1h last close
  2026-11-25 11:59:59Z). Venue recorded as Kraken in the report.
- **Cross-check:** Coinbase public candles (independent venue, probed
  first-hand this run) show BTC-USD newest close 58569.64, corroborating
  the Kraken-derived entry 58564.60. The ~80k prints in the raw Kraken
  probe are the oldest of the 720 returned hourly candles (late
  October), not the current price.
- **Stage 5 caveat, recorded honestly:** INCONCLUSIVE — high-impact
  events in the chart window (CB Consumer Confidence, Monthly CPI
  Indicator, Spanish PPI, Trimmed Mean / Weighted mean CPI, FGV
  Consumer confidence). The pipeline's own rule is "no setup into the
  event without coordinator clearance"; the report records the flag and
  the final verdict still reads SETUP because stage 6 passed. No order
  is placed, no position is taken — this task is a research-desk
  checklist on demo data only; the setup is evidence, not a trade.

## Done criterion

One real chart end to end — **MET**. The 7-stage pipeline ran on real
Kraken klines and produced a complete, attributable report (JSON +
Markdown) with every stage recorded. Work PR follows this checkpoint;
the board flip (STR-086 AVAILABLE -> IN_REVIEW) rides in the
coordinator's next board PR per rule 4 (board AVAILABLE/null stands
until the work PR lands). Board on main (b9a4c8cf, checked first-hand
this run): STR-086 owner muse_tp6, branch
`musetp6/task-str-086-staged-chart-checklist`, pr null — current.

## Queue

WATCH088 queue VYR-078 -> VYR-063 -> VYR-084. VYR-078 ruling still
owed (Muse 3 claim of record, no ruling in WATCH098); NOT claimed, no
branch pushed. If the alternate venue had failed, the WATCH098
fallback was VYR-063 — not needed: the Kraken leg succeeded.

— Muse TP6
