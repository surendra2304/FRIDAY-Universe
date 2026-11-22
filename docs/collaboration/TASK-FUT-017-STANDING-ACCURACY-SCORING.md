# TASK-FUT-017 — Futuris: standing per-cycle accuracy scoring + explicit fit-cost cap

- Task: TASK-FUT-017 (P2, owner muse_1)
- Work PR: #1368, head `003731fbb84f5e99748d414657262122e487be31`, base main `9e0d74e`
  (merge-base `9e0d74ef`; rebased from assignment base `351c2866` when main
  moved under the run — PR #1363, Muse 2 FRD-033, no overlap with these files)
- Branch: `muse1/task-fut-017-standing-accuracy-scoring`
- Claim: issue #35 comment 7078010223 (hub comment + branch push, no claim PR)
- Assignment: coordinator pool 8, issue #35 comment 7077871779 (~16:05 IST);
  assigned on Muse 1's work request, comment 7077852023 (~16:02 IST)
- Board blob verified against the true main blob before editing: `d591ef01`
  (main `9e0d74e`); board flip AVAILABLE → IN_REVIEW rides in this PR

## 1. What was missing (gap found on main)

FUT-006 already scores resolved forecasts, but the grading was not standing:

1. The lifecycle sweep and the calibration sweep resolve matured forecasts
   (horizon passed, outcome recorded) and then stop — scoring happened only
   in the separate 30-minute `forecast_scoring_job`, up to a cycle later.
   Nothing in a cycle proved its own matured forecasts were scored.
2. `/v1/self/status` had no accuracy section at all: no rolling hit-rate
   anywhere on Futuris's status surface.
3. `select_best_adapter` bounded fits only by wall-clock budget and CPU
   saturation. There was no memory estimate and no fit-cost cap anywhere:
   the backtest fits every routed candidate (AutoARIMA stepwise search
   included) and the winner is refit on the full series, with the 512M
   MemoryMax as the only guard — the OOM saga's backstop, not a control.

## 2. What this PR implements

### Fit-cost cap — `Futuris/futuris/models/fit_cost.py` (new)

- `estimate_fit_memory_mb(candidate, n_rows, n_features, n_exog=0)`:
  conservative upper-bound estimate per candidate family (float64 working
  copies): naive/drift/seasonal_naive 2x the frame, AutoETS 12x,
  MeanEnsemble 14x (AutoETS + SeasonalNaive), AutoARIMA 48x + per-exog
  term + 4MB search overhead. Unlisted adapters take the 48x bound.
  The estimate is labelled an estimate wherever it is recorded.
- `shortlist_candidates(...)`: router rank order in, the affordable
  prefix out; expensive candidates are dropped first, a cheap baseline
  later in the ranking still fits, and at least one (cheapest) candidate
  is always kept — the frame is already in memory, so a cheap baseline
  fit adds about one series copy on top of data the process already holds.
- `resolve_fit_memory_budget(...)`: explicit caller budget, else the
  configured cap, else the 256MB default.
- `final_fit_within_budget(...)`: the same estimate for the winner's
  full-data refit; cheap baselines are never refused.

### Selection + pipeline

- `models/selection.py`: candidates are shortlisted against
  `FUTURIS_FIT_MEMORY_BUDGET_MB` (new setting in `infra/config.py`,
  default 256 — half the 512M backstop) before any fit starts. Dropped
  candidates are recorded as skipped with reason `fit_cost_cap`, and the
  estimates + budget ride in `SelectionOutcome.metadata()`. All three
  callers (pipeline, engine, universe forecasting) get the cap, since
  they share `select_best_adapter`.
- `core/pipeline.py`: the winner's full-data refit is estimated before it
  starts; over budget it refits naive instead, the model version carries
  `:final_fit_cost_capped`, and the decision rides in
  `Forecast.model_metadata` (`final_fit_cost_capped`,
  `final_fit_estimate_mb`, `final_fit_fallback_adapter`).

### Standing per-cycle scoring

- `infra/scheduler.py`: `lifecycle_sweep_job` and `calibration_sweep_job`
  now call `_score_matured_forecasts(source=...)` at the end of the cycle
  that resolves matured forecasts — scoring is best-effort (a scoring
  failure is logged and recorded, never aborts the cycle) and idempotent,
  so overlaps are harmless. Each call records `last_cycle_scoring` and
  `forecast_scoring_job` records `last_scoring_summary` (scored count,
  report status, `n_scored_total`, `rolling_hit_rate_30d`, timestamp).
  The standalone 30-minute `forecast_scoring_job` remains as the backstop.
- `services/forecast_tracker.py`: `build_rolling_hit_rate(rows, ...)` —
  share of scored forecasts whose actual landed inside the interval over
  the most recent 30 days (window ends at the newest score row by
  default, so reports are reproducible); below 30 in-window scores the
  status is `insufficient_data` with a null hit-rate. `calibration_report`
  now carries `rolling_hit_rate_30d`, and `ForecastTracker.rolling_hit_rate()`
  serves it from a bounded read (newest 1000 rows). `storage/score_repository.py`
  gains `list_recent_scores(limit)` + `count_scores()`.

### Rolling hit-rate on the status surface

- `infra/self_healing.py`: new `check_accuracy()` subsystem on
  `/v1/self/status` (`forecast_accuracy`): rolling 30-day hit-rate,
  counts, and the last cycle's scoring summary when the scheduler runs
  in-process. Thin data reports `unknown` with the count attached — never
  a verdict, never `down`. Runs inside the same 3s measurement budget as
  every other check. `infra/metrics.py`: new gauge
  `futuris_forecast_rolling_hit_rate`.

## 3. Verification (local, this run)

- New suite `Futuris/tests/test_fut017_standing_accuracy_scoring.py`:
  **20/20 green** under the exact CI invocation
  (`python -m pytest -q ... --confcutdir=Futuris/tests/infra`).
  Fake adapters stand in for statsforecast, so the suite runs where
  statsforecast is not installed (CI has none on this test surface).
  Covers: estimate ordering/scaling, shortlist behaviour (full keep at
  256MB, expensive-first drop at 2MB, never-empty), selection cap
  (`fit_cost_cap`, metadata), pipeline final-refit fallback (budget
  5.30MB sits between mean_ensemble's 3744-row backtest estimate 5.11MB
  and its 4032-row refit estimate 5.47MB), rolling hit-rate window math
  (40 in-window of 90 total → 0.75; old rows excluded), tracker
  end-to-end (40 scored → hit-rate 0.75), lifecycle sweep scoring
  matured forecasts in-cycle, per-cycle summary recording, scoring
  failure never breaking a cycle, and the status check (unknown while
  thin, measured 0.75 once 40 scored).
- Neighbouring suites on the same invocation: **68 passed, 2 skipped**
  (the 2 skips are pre-existing statsforecast skips);
  `test_fut006_forecast_tracker.py` 9/9 green after the change.
- `test_scheduler_and_pipeline.py`: 2 failures — verified pre-existing
  on pristine main (same 2 fail with this PR stashed): the environment
  has no statsforecast backend, so the pipeline raises
  `StatsForecastUnavailableError` and the refresh job skips the
  subscription. Not a regression.
- Ruff F821 clean on all changed files (the CI gate for siblings). Full
  ruff on the edited files: 65 findings vs 64 on pristine main — the +1
  is an E402 on the one added import line, the repo's pre-existing
  `UTC = timezone.utc`-before-imports pattern; the new test file is
  ruff-clean and the new `fit_cost.py` is ruff-clean.
- Board: record verified AVAILABLE / owner muse_1 on main `9e0d74e`
  (blob `d591ef01`) before editing; single `evidence:` key kept (one
  item appended, no duplicate key); `scripts/validate_collaboration.py`
  run after the edit: **COLLABORATION REGISTRY VALID, 644 tasks**.
- CI on PR #1368: not yet observed at filing time — see STATUS comment.

## 4. Disclosures / open items

- **No live proof yet.** The code is not deployed: no fleet service was
  restarted by this run (no hub clearance held). The board's "prove over
  one live cycle" needs Muse's hub clearance after merge: deploy + restart
  Futuris, then one live scheduler cycle must show forecasts stored with
  horizons, matured ones scored in-cycle (`last_cycle_scoring`), and the
  rolling hit-rate on live `/v1/self/status`.
- **Estimates, not measurements.** The fit-cost coefficients are
  conservative planning bounds (float64 working copies per family), not
  measured RSS. They are labelled estimates in code, metadata, and this
  doc. If live RSS ever contradicts them, the coefficients — not the cap
  mechanism — need recalibration.
- **CI quirk found while testing:** the monorepo-validation invocation
  uses `--confcutdir=Futuris/tests/infra`, under which
  `Futuris/tests/conftest.py` does not load — the autouse throwaway-DB
  fixture is inactive there. The new status tests therefore build their
  own temp engine in-file (`status_storage` fixture) instead of relying
  on the conftest. Worth a look by whoever owns the CI collection rule;
  not fixed here (out of scope).
- The `test_scheduler_and_pipeline.py` failures above are environmental
  (no statsforecast in this VM or on the CI test surface), recorded here
  so they are not mistaken for regressions of this PR.

## 5. Files changed

- `Futuris/futuris/models/fit_cost.py` (new)
- `Futuris/futuris/models/selection.py`
- `Futuris/futuris/core/pipeline.py`
- `Futuris/futuris/services/forecast_tracker.py`
- `Futuris/futuris/storage/score_repository.py`
- `Futuris/futuris/infra/scheduler.py`
- `Futuris/futuris/infra/self_healing.py`
- `Futuris/futuris/infra/config.py`
- `Futuris/futuris/infra/metrics.py`
- `Futuris/tests/test_fut017_standing_accuracy_scoring.py` (new, 20 tests)
- `.github/workflows/monorepo-validation.yml` (new test added to the CI
  collection list)
- `docs/collaboration/WORK_BOARD.yaml` (FUT-017 flip to IN_REVIEW, pr 1368)
- `docs/collaboration/TASK-FUT-017-STANDING-ACCURACY-SCORING.md` (this file)
