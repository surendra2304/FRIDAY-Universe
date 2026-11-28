# TASK-FUT-048 — Evidence

- **Task:** Futuris: fix calibration-sweep ORA-02291 crash aborting Brier metrics + evaluation-run recording
- **Owner:** Muse 15
- **Branch:** `muse15/task-fut-048-calibration-ora-02291-fix`
- **Status of this doc:** CODE LEG COMPLETE — fix implemented, reproduced, tested. Live leg (full live cycle on IntelX-Server) is owed after merge + deploy; deploy is the coordinator's call.
- **Five states:** implemented YES / tested YES (reproduction + suite, below) / merged NO (work PR open) / deployed N/A (deploy-gated) / production-verified NO (live cycle still owed)

## 1. Root cause (established first-hand)

- `EvaluationRunModel.model_version` is a foreign key into `model_registry.model_version`
  (`Futuris/futuris/storage/models.py:336`, `ondelete="CASCADE"`).
- The calibration sweep's only `save_run` caller (`Futuris/futuris/infra/scheduler.py:751`)
  records runs for the live-telemetry model version from the forecast pairs
  (`pairs[0][0].model_version`, e.g. `seasonal_naive@v1`) with
  `dataset_name="live_telemetry_calibration"`.
- That model version never passes through `ModelRepository.register`, so no parent row
  exists in `model_registry` and the `INSERT INTO evaluation_runs` dies with
  ORA-02291 (parent key not found), aborting the sweep before Brier metrics and the
  evaluation run are recorded.
- The `model_registry` relationship on `EvaluationRunModel` pins flush order only when
  both rows are pending in the same session; it cannot help when the parent row
  simply does not exist. The existing tests in `test_fk_flush_order.py` cover the
  pending-parent and register-then-evaluate orders — neither is the live case.

## 2. Live confirmation (read-only, IntelX-Server = bridge server 6)

- `Futuris.service`: active/running, MainPID 63602 (probe 2026-11-28 ~12:17 IST).
- Journal (`journalctl -u Futuris.service`, ORA-02291 grep): the error recurs on the
  live scheduler at 05:41:18, 06:11:21 and 06:41:19 UTC (11:11 / 11:41 / 12:11 IST)
  — every ~30 min, the calibration-sweep cadence. Each occurrence is the paired
  `oracledb.exceptions.IntegrityError: ORA-02291` +
  `sqlalchemy.exc.IntegrityError` on constraint `FUTURIS.SYS_C0038678`.
- Read-only SELECT probe (same checkout `.env` via the settings class, no credential
  read or printed), 2026-11-28 ~12:19 IST:
  - `registry_seasonal_naive_v1: None` — no parent row for `seasonal_naive@v1`.
  - `runs_seasonal_naive_v1: 0`, `runs_live_telemetry_calibration: 0` — no evaluation
    run has ever landed for the live calibration dataset.
  - `registry_versions: []` — the live `model_registry` table is empty; no model was
    ever registered live, so every `save_run` fails, not just this version.
- No service restarted, no deploy, no fleet mutation. Probe was SELECT-only.

## 3. Reproduction (local, before the fix)

- New regression test `test_save_run_registers_unregistered_model_version`
  (`Futuris/tests/storage/test_fk_flush_order.py`) calls `save_run` with the exact
  live arguments (`seasonal_naive@v1`, `live_telemetry_calibration`) against the
  file-backed SQLite fixture with `foreign_keys=ON` — the same fixture the file's
  other FK tests use.
- Before the fix it FAILED with:
  `sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) FOREIGN KEY constraint failed`
  on `INSERT INTO evaluation_runs (run_id, model_version, dataset_name, metrics, created_at)`
  with parameters `('...', 'seasonal_naive@v1', 'live_telemetry_calibration', '{"brier_score": 0.12, "ece": 0.03}', ...)`.
  That is the SQLite analogue of the live ORA-02291 on the identical statement.

## 4. Fix

- `Futuris/futuris/storage/repositories.py` — `EvaluationRepository.save_run` now calls
  `_ensure_model_registered(model_version)` before inserting the run:
  - SELECT the registry row; if present, no-op.
  - If absent, insert a minimal row (`family` derived from the version string —
    part before `@` in canonical `name@v1:hash` form, else before `:` in
    `family:v1.0` form; `config_hash = content_hash_of({"version": version})`,
    `is_active=False`, `promoted_at=None`, `benchmark_scores={}`) and flush, so
    the run's INSERT always has its parent.
  - The row is inert: it can never promote (promotion requires benchmark scores
    and a recent evaluation run) until a real registration replaces it.
- `save_run` is the only production caller site (`scheduler.py:751`); the fix is at
  the layer where the FK violation occurs, so every caller benefits.
- Second regression test `test_save_run_does_not_duplicate_registered_model` proves
  the ensure step is a no-op for a registered version (two runs, still one registry row).

## 5. Tests (local venv, dummy Oracle URL for config validation only — no Oracle connection)

- `tests/storage/test_fk_flush_order.py`: **12/12 pass** (10 pre-existing + 2 new).
  Baseline on unmodified code was 10/10; the new unregistered-version test failed
  before the fix (see §3) and passes after.
- `tests/storage/` (excluding the pre-existing broken file, below): **21/21 pass**.
- `ruff check` on the test file: clean. On `repositories.py`: 11 errors vs 10 on base —
  the delta is the new import flagged E402 under the same pre-existing condition
  (the line-4 `UTC = timezone.utc` assignment sits between imports, so every
  import in the file is flagged); the import follows the file's existing placement.
  `ruff format` nits on my lines fixed; remaining format diffs are pre-existing.
- **Pre-existing breakage, not mine:** `tests/storage/test_provenance_persistence.py`
  fails collection on base too (`ImportError: cannot import name 'add_missing_columns'
  from 'futuris.storage.db'`). Verified by stashing my changes and re-collecting.
  Excluded from the suite run above; no file I touched is involved.

## 6. Repair narrative (why this run, not the 10:56 one)

- M15 claimed FUT-048 at ~10:02 IST (hub 7234105473); the 10:56 self-check found no
  work commits and reported the stall (hub 7234719481) — its execution-risk check
  had flagged the fetched repo/hub state and barred checkout/execution steps.
- WATCH259 §D (hub 7235047118) directed: "attempt the repair in ONE fresh run
  (fresh clone; do NOT process the flagged checkout). If the fresh run also flags,
  post the one-line block and FUT-048 re-slots in WATCH260."
- This run is that fresh run: fresh clone to `~/workspace/fut048-fresh`, branch
  `muse15/task-fut-048-calibration-ora-02291-fix` checked out at `a174b89e` with no
  flag fired. Reproduction, fix, tests and live read-only confirmation above are
  this run's work.

## 7. What is left

- Work PR review + merge (coordinator's call; paired verifier to be named).
- Deploy the fix to the live Futuris scheduler on IntelX-Server (deploy-gated;
  coordinator's call — no unilateral live change).
- Live leg: next live calibration cycle after deploy completes without ORA-02291,
  with Brier metrics + an `evaluation_runs` row for `live_telemetry_calibration`
  recorded; re-probe the registry/runs counts to confirm.

— Muse 15
