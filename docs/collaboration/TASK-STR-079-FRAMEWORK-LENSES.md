# TASK-STR-079 — Research-desk framework lenses (Chaos Theory, Game Theory, Fractals)

— Muse 15, 2026-11-25

## Claim

- Board record verified first-hand on main `d2a40a6d`: `TASK-STR-079`
  AVAILABLE, owner null, P3, no hub claim, no branch, no open PR.
- Assigned in coordinator watch `7151431137` (run scheduled 07:57
  IST): head of my fresh queue — STR-079 → INF-034 → FRG-022. Hub
  claim comment `7151646047` on issue #1483 (2026-11-25 ~08:40 IST);
  branch `muse15/task-str-079-framework-lenses` from main `d2a40a6d`
  (ref created, verified via ls-remote).
- Board flip AVAILABLE → IN_REVIEW rides in this PR (one work PR,
  live evidence, per owner order 7143628341). The work-request cron
  is cancelled on claim, per the job body; the hourly self-check
  remains armed.

## Source — where the frameworks live

- Source: stratex package S-02/S-03/S-04, IG corpus item
  `DUYHoUdD5vk` (one comment thread in three parts, filed in the
  Instagram adoption re-audit, batch 3): Chaos Theory — markets
  deterministic but unpredictable, nonlinear, small inputs = huge
  outcomes, identify conditions where probabilities shift; Game
  Theory; Fractals.
- The source video text is **not in the repo** (no GAP-LIST.md copy,
  no transcript file; the IG item is referenced only in
  `bayesian_uncertainty.py` and the board record). The framing texts
  stored in `FRAMEWORK_LENSES` are therefore **derived from the board
  acceptance** of TASK-STR-079, with provenance on each entry. If the
  coordinator's watch record carries fuller wording, the library
  entries should be corrected to match it — the module docstring
  says so (same caveat as the S-21 prompts in TASK-STR-080).

## Implementation

`Stratex/rigorous_backtest/ig/research_desk.py` — `FRAMEWORK_LENSES`
plus three new role functions, wired into `run_desk()` as a
`framework_lenses` section per kept setup; `scan()`, `analyse()`,
`pattern_match()`, `scenario_analysis()`, `plan()`,
`risk_manager_pass()`, `risk_checklist()` untouched:

- **Lens library** (`FRAMEWORK_LENSES`): all three frameworks in one
  place — id, title, framing, the three-question question set,
  source (S-02/S-03/S-04 / `DUYHoUdD5vk`), board task, and the
  implementing function name. Mirrors `PROMPT_LIBRARY`.
- **Chaos — `chaos_lens(candles, window=30)`**: sensitivity is the
  spread of forward outcomes across the most similar past windows
  (reuses `pattern_match()`, window 10, forward 10): similar starts
  that went very different ways mean the current move is highly
  sensitive to small inputs. Spread < 2pp low, < 6pp moderate, above
  high; fewer than 2 similar windows → sensitivity unknown, not
  guessed. Probability-shift conditions, each named present/absent
  with evidence: volatility expansion (mean |daily move| last 10
  bars > 1.5x the prior 20 — from a dead-flat prior, any new
  movement counts as expansion), range break (last close outside the
  prior 29-bar range), trend flip (EMA-slope sign now vs 10 bars
  ago). Tail moves: bars whose |daily move| exceeds twice the
  window's mean |daily move|. With fewer than `window` candles the
  result says `insufficient_history`.
- **Game Theory — `game_theory_lens(candles, setup=None, window=30)`**:
  crowded side from the last close's position in the window range
  (> 0.80 longs crowded near the highs, < 0.20 shorts crowded near
  the lows, else neither); stop clusters — recent high (shorts'
  stops above it) and recent low (longs' stops below it), each with
  distance from the last close; the trap — a break below the recent
  low traps crowded longs, a break above the recent high traps
  crowded shorts, and with no crowded side there is no trap to name.
  When a setup is supplied, a fourth question notes whether its
  entry chases beyond the trap level and whether its invalidation
  sits beyond a stop-cluster level.
- **Fractals — `fractals_lens(candles, scales=(5, 10, 30, 60))`**:
  net return and direction (up > +0.5%, down < −0.5%, else flat) at
  each scale; self-similar when every scale shares the majority
  direction, agreement = share of scales matching the majority;
  breaks list the disagreeing scales with their net returns;
  smallest (5-bar) vs largest (60-bar) net compared. With fewer
  than 60 candles the result says `insufficient_history`.
- `run_desk()` gains `chaos_window=30` and
  `fractal_scales=(5, 10, 30, 60)` parameters and the summary count
  `framework_lenses_issued` (setups where all three frames are ok).
- Stdlib only, no new dependencies. Research surface only — a lens
  answers questions about the chart; it changes no scan, no plan, no
  checklist, and no trading behaviour (same as IG-STR-05 by design).

## Tests

`Stratex/rigorous_backtest/ig/tests/test_research_desk.py` — 13 new
tests, suite **36/36 passed** locally (pytest 9.2.0, isolated venv
`/tmp/venv-str079` — system Python on this VM has no pytest):

- Library: all three lenses present, every entry carries id / title
  / framing / 3 questions / source (`DUYHoUdD5vk`, S-02/S-03/S-04 in
  order) / board task (`TASK-STR-079`) / implements, and every
  `implements` name resolves to a callable in the module.
- Chaos: flat series → sensitivity low (spread 0.0), 0 tail moves, no
  conditions present; planted series → sensitivity high (spread
  exactly 6.0pp across 3 similar windows, forwards +3/−3/+3%);
  calm-then-violent series → volatility expansion + range break both
  present (evidence names "broke below the low"); 10 candles →
  `insufficient_history`.
- Game theory: planted uptrend → longs crowded, trap below the
  window low; planted downtrend → shorts crowded, trap above the
  window high; flat → neither crowded, trap null; setup question
  names the entry chasing beyond the trap level and the invalidation
  beyond a stop-cluster level; 10 candles → `insufficient_history`.
- Fractals: planted uptrend at all scales → self-similar, agreement
  1.0; mixed scales (last 5 bars down, 10/30/60 up) → not
  self-similar, agreement 0.75, break at scale 5 only; 40 candles →
  `insufficient_history`.
- `run_desk()` memo carries the `framework_lenses` section with all
  three frames ok and `framework_lenses_issued` 1 — and the lenses
  change nothing else (same 1 plan drafted, 1 checklist passed).
- Two test expectations were wrong on first run (window high/low are
  from the last 30 bars, not all 40) and were corrected to the true
  values; the implementation was unchanged.
- CI: `test_research_desk.py` is already in the Stratex tier-1 pytest
  invocation (added by TASK-STR-067, `.github/workflows/
  friday-universe-ci.yml:246`) — no CI change owed.

## Live evidence (real market data, 2026-11-25 ~08:55 IST)

`run_desk()` run on live Deribit public candles (BTC-PERPETUAL,
`get_tradingview_chart_data`, no auth — this VM is geo-blocked from
Binance; the module is stdlib-only and runs offline on any OHLC feed,
so no server leg is needed for this research surface):

- Series: **211 x 1d bars**, 2026-04-28 → 2026-11-24, last close
  **59,499.0**. Setup: short (last close below the 30-day-ago close),
  entry 59,499.0, invalidation 66,111.5 (10-day high), target 2R;
  checklist passed, scenario commit bearish, risk pass 1:3.
- **Chaos:** sensitivity **high** — forward-outcome spread **12.74pp**
  across 3 similar windows (forwards −1.72% / +1.96% / +11.02%, the
  same three windows as STR-067). No probability-shift condition
  present: vol ratio 1.06 (mean |daily move| 2.22% vs 2.10%), last
  close inside the prior 29-bar range [55,000, 81,922], EMA slope
  negative now (−0.0934) and 10 bars ago (−0.0553). **4 tail moves**
  in 30 bars (threshold 4.29%).
- **Game Theory:** **shorts crowded** near the lows (range position
  0.17). Stops: short stops above 81,922.00 (+37.69%), long stops
  below 55,000.00 (−7.56%). Trap: a break above 81,922 traps the
  crowded shorts (+37.69%). Setup note: entry sits inside of the
  trap level; invalidation sits inside the range. Honest read: after
  a −26% month the trap level is 38% away — the lens names the
  crowded side and the trap, it does not call the bounce.
- **Fractals:** **self-similar, all 4 scales down** (agreement 100%,
  no break): 5-bar −3.68%, 10-bar −6.99%, 30-bar −25.58%, 60-bar
  −29.24%.
- Memo summary: `framework_lenses_issued` **1** — one real
  research-desk report issued carrying all three frames. Full memo
  saved in the run log (this VM, `/tmp/live_str079_out.json`; raw
  bars `/tmp/live_str079_candles.json`).
- **Feed note:** the last bar's close moved 59,497 → 59,499 between
  two fetches minutes apart (live feed revision); all figures above
  are from the second fetch, which also re-ran the tests (36/36) and
  the memo.

## Board flips carried in this PR

- TASK-STR-079 AVAILABLE → IN_REVIEW (owner muse_15, this PR).
- TASK-STR-080 IN_REVIEW → MERGED (work PR #1758, merge `d2a40a6d`,
  merged 2026-11-25T02:56:14Z — verified first-hand via the PR API
  this run: state closed, merged true, head `ab080986`).
- The coordinator's watch `7151431137` said the STR-080 MERGED flip
  rides in "tomorrow's consolidated board PR"; per owner order
  7143628341 rule 4 (consolidated board PR abolished, flips ride in
  your own PR) it rides here instead.

## Five states

- Implemented: YES (this PR) / Tested: YES (36/36 local; CI — see PR) /
  Merged: NO / Deployed: NO (no production consumer by design —
  research surface only) / Production-verified: YES for the acceptance
  as written (live-data run above: one real research-desk report
  issued carrying all three framework lenses — chaos sensitivity
  high, game-theory shorts crowded, fractals self-similar down).

— Muse 15
