# TASK-STR-067 — Pattern-comparison step on the multi-agent research desk

— Muse 15, 2026-11-25

## Claim

- Board record verified first-hand on main `8bfcbc4f`: `TASK-STR-067`
  AVAILABLE, owner null, P3, no hub claim, no branch, no open PR.
- Hub claim comment `7146973743` on issue #1483 (completion post of
  TASK-STR-066, 2026-11-25 ~04:33 IST); branch
  `muse15/task-str-067-pattern-comparison` from main `8aea4275`,
  rebased onto `8bfcbc4f` for this PR.
- Board flip AVAILABLE → IN_REVIEW rides in this PR (one work PR, live
  evidence, per owner order 7143628341). The claim sat ~1.5 h with no
  work run behind it (work-request cron cancels on claim; the hourly
  self-check is the only run that picks a held task up) — the 05:56 IST
  self-check repaired the stall by doing the work in that run.

## Implementation

`Stratex/rigorous_backtest/ig/research_desk.py` — new `pattern_match()`
(TASK-STR-067), wired into `run_desk()` as a `pattern_matches` section
per kept setup; `scan()`, `analyse()`, `plan()`, `risk_checklist()`
untouched:

- Current price action = the last `window` candles (default 10).
  Similarity is the mean absolute gap between the normalised
  cumulative log-return shapes (0..1, 1 = identical path), so two
  windows at different price levels but the same path compare equal.
- Candidates are windows inside the last `lookback_days` (default 180)
  of history. A candidate only counts if its window AND its
  `forward`-candle (default 10) outcome window both end before the
  current window starts — no outcome leaks into the pattern compared.
  Matches are picked greedily by similarity and never overlap each
  other. The `lookback_days` window is applied only when candles carry
  `time`/`timestamp` (seconds or ms); otherwise the whole history is
  searched and `lookback_applied` says so.
- Each match reports start/end index + time, similarity,
  pattern net return, forward return over the next 10 candles,
  forward direction (up/down/flat at a 0.5% threshold) and `success`:
  the forward move agrees with the setup direction (flat never
  succeeds). `success_rate` = successes / matches, `None` when there
  are no matches.
- With fewer than `2 * window + forward` candles there is not even one
  full candidate plus its outcome plus the current window, so the
  result says `insufficient_history` with a reason instead of guessing.
- Stdlib only, no new dependencies. Research surface only — the section
  describes what happened after similar patterns; it is not a signal,
  not an entry, not an order, and nothing in production consumes this
  module (same as IG-STR-05 by design).

## Tests

`Stratex/rigorous_backtest/ig/tests/test_research_desk.py` — 5 new
tests, suite **10/10 passed** locally (pytest 9.2.0, this VM):

- Planted patterns: 200 daily candles, flat at 100 except three windows
  copying the current window's shape at other levels (90/110/95), with
  known 10-bar forward moves (+3% / -3% / +3%) → 3 matches found, the
  planted start indices, similarity > 0.99, forward returns ±3%,
  success rate 2/3 for long.
- Short direction flips success (1/3 on the same series).
- Lookback: with `lookback_days=60` the 20- and 80-index plants are
  excluded and only the recent one survives.
- Insufficient history (25 candles) → `insufficient_history`, no
  matches, `success_rate` null, reason carried.
- `run_desk()` memo carries the `pattern_matches` section and the
  summary `pattern_matches_found` count (3 on the planted series).
- CI: `test_research_desk.py` added to the Stratex tier-1 pytest
  invocation in `.github/workflows/friday-universe-ci.yml`. The file
  was collected by NO CI job on main before this change (same gap
  TASK-STR-066 fixed for `test_levels.py`).

## Live evidence (real market data, 2026-11-25 ~06:05 IST)

`run_desk()` run on live Deribit public candles (BTC-PERPETUAL,
`get_tradingview_chart_data`, no auth — this VM is geo-blocked from
Binance; the module is stdlib-only and runs offline on any OHLC feed,
so no server leg is needed for this research surface):

- Series: **201 x 1d bars**, 2026-05-08 → 2026-11-24, last close
  **59,511.5**. Setup: short (last close below the 30-day-ago close),
  entry 59,511.5, invalidation 30-day high, target 2R; checklist passed.
- Current 10-day window 2026-11-15 → 2026-11-24, net **-8.34%**
  (analysis trend: down).
- **3 matches** in the last 6 months:
  1. 2026-06-13 → 2026-06-22, similarity **0.880**, pattern net -2.48%,
     forward **-1.72% (down) — success** for the short direction.
  2. 2026-05-29 → 2026-06-07, similarity **0.869**, pattern net
     -13.94%, forward **+1.96% (up) — fail**.
  3. 2026-09-06 → 2026-09-15, similarity **0.845**, pattern net -4.59%,
     forward **+11.02% (up) — fail**.
- **Historical success rate: 1/3 (33.3%)** for the short direction.
  Honest read: after the three most similar 10-day slides in the last
  6 months, BTC bounced twice and kept falling once — the section
  reports that plainly; it is not a short signal.
- Full memo saved in the run log (this VM, `/tmp/live_str067_out.json`).

## Board flips carried in this PR

- TASK-STR-067 AVAILABLE → IN_REVIEW (owner muse_15, this PR).
- TASK-STR-066 IN_REVIEW → MERGED (work PR #1740, merge `07c72f72`).
- TASK-STR-075 CLAIMED/muse_6 → AVAILABLE/null (void per watch062
  re-scope ruling; owed since watch065).
- TASK-REL-097 IN_REVIEW → MERGED (work PR #1674, merged
  2026-11-24T14:18:06Z).
- TASK-VOI-033 owner muse_15 → null (released in the TASK-STR-066
  claim post 7146070918; board still carried the owner).

## Five states

- Implemented: YES (this PR) / Tested: YES (10/10 local; CI — see PR) /
  Merged: NO / Deployed: NO (no production consumer by design —
  research surface only) / Production-verified: YES for the acceptance
  as written (live-data run above proves the memo carries the
  pattern-match section — 3 similar patterns in 6 months, what
  happened after each, and the historical success rate — on real
  market candles).

— Muse 15
