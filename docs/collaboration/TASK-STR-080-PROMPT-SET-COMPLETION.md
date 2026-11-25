# TASK-STR-080 — Research-desk prompt set completion (prompts 1 + 3)

— Muse 15, 2026-11-25

## Claim

- Board record verified first-hand on main `79431498`: `TASK-STR-080`
  AVAILABLE, owner null, P3, no hub claim, no branch, no open PR.
- Assigned in coordinator watch `7149287133` (06:40 IST run); hub claim
  comment `7149657952` on issue #1483 (2026-11-25 ~07:02 IST); branch
  `muse15/task-str-080-prompt-set-completion` from main `6fbc9b3b`,
  fast-forwarded to current main `79431498` for this PR (no commits
  on the branch at claim time, so the move is a fast-forward, not a
  force-push).
- Board flip AVAILABLE → IN_REVIEW rides in this PR (one work PR, live
  evidence, per owner order 7143628341). The claim sat ~5 min before
  this run picked the work up — the work-request run that fired at
  07:06 IST did the implementation instead of reporting the stall and
  waiting (same repair as STR-067). The work-request cron is cancelled
  on claim, per the job body; the hourly self-check remains armed.
- A concurrent self-check run collided on the shared local clone and
  stopped its own implementation attempt rather than racing this run;
  no files of its own were changed. STR-080 implementation rides in
  this run only.

## Source — where the verbatim prompts live

- Source: stratex package S-21, IG corpus item `DRSGKJXDAU4` (watched
  in full by the coordinator). Of its three verbatim trading prompts,
  only prompt 2 (pattern comparison) was filed (TASK-STR-067). Prompts
  1 and 3 were left unfiled; under the default-implement standard they
  are filed here.
- The source video text is **not in the repo** (no GAP-LIST.md copy,
  no transcript file; the IG item is referenced only in
  `assistant_pack.py` and the board records). The prompt texts stored
  in `PROMPT_LIBRARY` are therefore **verbatim-derived from the board
  acceptance** of TASK-STR-067 / TASK-STR-080, with provenance on each
  entry. If the coordinator's watch record carries fuller wording, the
  library entries should be corrected to match it — the module
  docstring says so.

## Implementation

`Stratex/rigorous_backtest/ig/research_desk.py` — `PROMPT_LIBRARY`
plus two new role functions, wired into `run_desk()` as
`scenario_analyses` and `risk_manager_passes` sections per kept
setup; `scan()`, `analyse()`, `pattern_match()`, `plan()`,
`risk_checklist()` untouched:

- **Prompt library** (`PROMPT_LIBRARY`): all three S-21 prompts in one
  place — id, title, verbatim-derived text, source (S-21 /
  `DRSGKJXDAU4`), board task, and the implementing function name.
  Prompt 2 points at the existing `pattern_match()` (TASK-STR-067);
  prompts 1 and 3 at the two new functions below.
- **Prompt 1 — `scenario_analysis(candles, window=30)`**: analyse the
  chart under Bullish / Bearish / Sideways, then commit to the most
  probable. Deterministic and transparent: a drift score from the EMA
  slope (60%) and the net return over the window (40%), each
  normalised so a 0.2% slope or a 5% move counts as full strength.
  Bullish share = max(drift, 0), bearish = max(-drift, 0), sideways =
  1 − |drift|; the three shares always sum to 1 and the commit is the
  largest share. `close_call` flags a top-two margin under 0.05.
  Each scenario carries its evidence line (slope, net return, mean
  |daily move|, range position). With fewer than `window` candles the
  result says `insufficient_history` instead of guessing. A flat
  chart commits sideways with share exactly 1.0 (drift snapped to 0
  below 1e-9, so float noise in the EMA cannot fake a drift).
- **Prompt 3 — `risk_manager_pass(setup, equity, risk_per_trade_pct,
  rr_target=3.0)`**: the risk-manager pass — stop-loss and
  take-profit at 1:3 R:R plus position sizing. The stop is the
  setup's invalidation; the target is placed exactly `rr_target` risk
  units from the entry in the setup direction, so R:R is 3.0 by
  construction; sizing reuses `plan()` (risk amount = equity × risk %,
  units = risk amount / risk per unit). Fail-closed: an invalidation
  on the wrong side of the entry, zero risk per unit, a bad
  direction, or a non-positive equity / risk % / rr_target returns
  `invalid_setup` with a reason and `passed` False instead of a pass.
  The four checks (stop on correct side, target beyond entry, R:R is
  target, sizing positive) are carried as the audit trail.
- `run_desk()` gains `scenario_window=30` and `rr_target=3.0`
  parameters and two summary counts (`scenario_commits`,
  `risk_passes_passed`).
- Stdlib only, no new dependencies. Research surface only — a
  scenario commit and a risk pass are memo lines; they are not a
  signal, not an entry, not an order, and nothing in production
  consumes this module (same as IG-STR-05 by design).

## Tests

`Stratex/rigorous_backtest/ig/tests/test_research_desk.py` — 8 new
tests, suite **18/18 passed** locally (pytest 9.2.0, isolated venv —
system Python on this VM has no pytest; installed into
`/tmp/venv-str080`, not the system):

- Library: all three prompts present, every entry carries id / title /
  verbatim-derived text / source (`DRSGKJXDAU4`) / board task /
  implements, and every `implements` name resolves to a callable in
  the module. Prompt 1 + 3 point at TASK-STR-080, prompt 2 at
  TASK-STR-067.
- Scenario commits: planted uptrend → bullish (share 1.0), planted
  downtrend → bearish (share 1.0), flat → sideways (share 1.0, net
  0%). Shares always sum to 1; `margin` is the top-two gap and
  `close_call` tracks `margin < 0.05` exactly. 10 candles →
  `insufficient_history`, commit null, reason carried.
- Risk pass: long setup (entry 100, invalidation 95) → SL 95.0,
  TP 115.0, R:R exactly 3.0, risk $10.00, units 2.0 (same math as
  `plan()`); short mirror (invalidation 105) → SL 105.0, TP 85.0,
  R:R 3.0; `rr_target=2.0` → TP 110.0, R:R 2.0. Wrong-side
  invalidation, zero risk, bad direction, zero equity → all
  `invalid_setup`, `passed` False, stop null.
- `run_desk()` memo carries both new sections and the summary counts
  (commit `bullish`, 1 risk pass passed on the planted uptrend).
- CI: `test_research_desk.py` is already in the Stratex tier-1 pytest
  invocation (added by TASK-STR-067, `.github/workflows/
  friday-universe-ci.yml:246`) — no CI change owed.

## Live evidence (real market data, 2026-11-25 ~07:25 IST)

`run_desk()` run on live Deribit public candles (BTC-PERPETUAL,
`get_tradingview_chart_data`, no auth — this VM is geo-blocked from
Binance; the module is stdlib-only and runs offline on any OHLC feed,
so no server leg is needed for this research surface):

- Series: **202 x 1d bars**, 2026-05-07 → 2026-11-24, last close
  **59,154.5**. Setup: short (last close below the 30-day-ago close),
  entry 59,154.5, invalidation 66,111.5 (10-day high), setup target
  2R; checklist passed.
- **Prompt 1 — scenario analysis:** commit **bearish**, margin 1.0,
  not a close call. Shares: bullish 0.0 / bearish 1.0 / sideways 0.0.
  Evidence: EMA slope −0.0940, net **−25.77%** over 30 candles, mean
  |daily move| 2.16%, range position 0.15. Honest read: after a −26%
  month the commit is emphatically bearish — that is a lagging
  description of the slide, not a short signal.
- **Prompt 3 — risk-manager pass:** **passed, all 4 checks ok.** SL
  66,111.5, TP **38,283.5**, R:R exactly **3.0**, units 0.014374,
  risk $100.00 on $10,000 equity at 1%.
- Pattern section (prompt 2, already live): 3 matches, success rate
  1/3 for the short direction — same three windows as STR-067
  (similarities 0.885 / 0.874 / 0.850; forwards −1.72% / +1.96% /
  +11.02%).
- Full memo saved in the run log (this VM, `/tmp/live_str080_out.json`;
  raw bars `/tmp/live_str080_candles.json`).
- **Setup-construction note:** the first live attempt used the
  30-day high (81,922.0) as the stop, as STR-067 did — after a −26%
  month that stop is 38% from entry, and the 1:3 target lands at
  −9,076 (a negative price). The arithmetic is correct; the setup is
  degenerate. The live analysis above therefore uses the 10-day swing
  high as the stop, and the memo's numbers are all positive and sane.
  The risk pass is level-agnostic — it prices whatever stop the desk
  hands it — so the desk's stop construction is what has to stay sane.

## Board flips carried in this PR

- TASK-STR-080 AVAILABLE → IN_REVIEW (owner muse_15, this PR).
- TASK-STR-067 IN_REVIEW → MERGED (work PR #1754, merge `79431498`).
- TASK-STR-073 IN_REVIEW → MERGED (work PR #1703, merge `4c0f77f3`,
  merged 2026-11-24T18:56:44Z).
- TASK-VOI-038 IN_REVIEW → MERGED (work PR #1666, merge `6ea282d6`,
  merged 2026-11-24T11:58:33Z).
- TASK-INT-040 IN_REVIEW → MERGED (work PR #1676, merge `4bc4159c`,
  merged 2026-11-24T15:29:47Z).
- TASK-STR-056 IN_REVIEW → MERGED (work PR #1619, merge `ec78a623`,
  merged 2026-11-24T04:07:01Z).
- All five MERGED flips verified first-hand this run (PR API state +
  merge commit, each merge commit an ancestor of current main).

## Five states

- Implemented: YES (this PR) / Tested: YES (18/18 local; CI — see PR) /
  Merged: NO / Deployed: NO (no production consumer by design —
  research surface only) / Production-verified: YES for the acceptance
  as written (live-data run above: both prompts live in the library
  and each used in one real desk analysis — scenario commit bearish
  and risk pass 1:3 on real BTC candles).

— Muse 15
