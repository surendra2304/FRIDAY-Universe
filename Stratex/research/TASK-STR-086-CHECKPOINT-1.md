# TASK-STR-086 — Checkpoint 1: scoping (Muse TP6, 2026-11-25 ~14:05 IST)

## Task

Stratex: staged chart-analysis checklist in the research desk — the 7-stage screenshot
pipeline. Source: stratex package S-26 (item Def5xMKtvmC). ONLY the staged checklist is
adopted: (1) market structure, (2) data quality, (3) timeframe context, (4) fundamentals,
(5) news sentiment, (6) risk levels, (7) final report with entry, stop, target and R:R.
The reel's own income claim ("a doctor's salary in under 2 minutes") is an unverified
promo claim and is excluded — it is not part of this task.

Done = one real chart analysed end to end through all seven stages with the staged
report persisted.

## Code paths located first-hand (main a0a9f1ba)

- Research-desk home: `Stratex/research/` — flat module set, no existing staged-chart
  pipeline (code search for "staged chart" returns only incidental mentions, no
  implementation).
- `Stratex/research/regime_classifier.py` — `RegimeClassifier.classify_regime(df)`:
  EMA50/EMA200, ADX, Bollinger width, ATR% → TREND_UP / TREND_DOWN / RANGE /
  LOW_VOLATILITY / HIGH_VOLATILITY / UNKNOWN. Directly reusable for stage 1
  (market structure) and stage 3 (timeframe context).
- `Stratex/research/economic_calendar.py` — calendar data, feeds stage 5 (news
  sentiment) context.
- `Stratex/research/trend_daily_study_2026_11.md` — study-doc template: scope/data
  table, findings, live configuration, caveats. The staged report (stage 7) follows
  this shape.
- `Stratex/research/validation/` — holdout harness (`run_regime_holdout.py`,
  `walk_forward_engine.py`) and filed regime reports; the pattern for persisting a
  staged report with provenance.
- `Stratex/research/provenance/EXPERIMENT_MANIFEST.json` — provenance pattern for
  recorded runs.
- `Stratex/render_market_scanner.py` — `MarketScanner` fetches real Binance klines
  (demo-fapi endpoint; the trend study verified demo-fapi matches live fapi within
  ~0.1%) and holds an in-memory OHLCV cache. The "one real chart" leg renders from
  these real klines — no third-party footage, no paid service, no credential.
- No chart images exist under `Stratex/` today (no .png/.jpg found); the chart for
  the done-run is rendered from real klines, not taken from a file.

## Design (to build)

New module `Stratex/research/staged_chart_checklist.py` (stdlib + pandas only, same
as the desk's existing modules):

1. **Market structure** — trend/regime from `RegimeClassifier`, swing highs/lows,
   EMA50/EMA200 alignment; recorded section, explicit UNKNOWN when data is thin.
2. **Data quality** — kline completeness (expected vs received bars), gaps, stale-feed
   check, venue (demo-fapi) noted; fail-closed on missing bars.
3. **Timeframe context** — same symbol on 1d + 4h + 1h: regime agreement/disagreement
   recorded; a higher-timeframe trend against the trading timeframe is flagged, not
   hidden.
4. **Fundamentals** — from the chart alone this stage has no direct feed: record the
   funding/venue facts available (symbol, venue, contract type) and mark the
   on-chain/fundamental inputs as NOT AVAILABLE from a chart, with the gap named.
   No invented fundamentals.
5. **News sentiment** — economic-calendar items overlapping the chart window from
   `economic_calendar.py`; no calendar item → recorded as none, not as neutral.
6. **Risk levels** — ATR(14)-based stop distance, R:R for the proposed setup,
   position-size math at the desk's 0.5% risk/trade standard; min R:R 1.2 gate
   (same gate as the deployed daily-trend config).
7. **Final report** — entry, stop, target, R:R, plus per-stage sections persisted
   as one JSON + one Markdown report under `Stratex/research/`, each stage
   producing its recorded section before the next runs.

Each stage writes its section before the next stage runs, so a failure mid-pipeline
leaves a partial, attributable report — never a silent skip.

## Honest limits (written into the record now)

- Stages 4–5 are feed-limited by design: a chart image carries no fundamentals feed
  and no news feed. The pipeline records the gap explicitly instead of synthesising
  a verdict. A "PASS" on those stages means "no contradicting evidence found in the
  available feed", never "fundamentals confirm".
- The done-run chart is a rendered chart from real demo-fapi klines, not a
  screenshot of a broker terminal. The 7-stage logic is identical; the input is a
  data-rendered chart, and the report says so.
- The reel's income claim is excluded (see Task above).

## Open item — execution gate (decision owed, coordinator)

This run's environment flagged the cloned tree with an execution-risk check:
running, building, testing, importing or loading the repo content on this VM is
gated, and I was instructed to ask before proceeding. Scoping above is read-only
and unaffected. The build + test + one-real-chart run leg therefore waits on a
ruling: either clearance to execute the (new, stdlib+pandas-only) pipeline code
on this VM, or direction to run it on the fleet (Oracle Server 2) instead. No
execution of repo code has been attempted this run. The design above is complete
so the build can start the moment execution is cleared.

## Status

Muse TP6 — TASK-STR-086 — scoping done, build pending the execution ruling above.
Claim hub 7157064327, branch `musetp6/task-str-086-staged-chart-checklist` @ a0a9f1ba.
Usage 9% of free weekly limit (reset Mon Nov 30, 1:48 PM IST).
