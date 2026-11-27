# TASK-FUT-017 — Futuris fit-cost cap: live measurement + cap from measured numbers — Muse 3

- Task: TASK-FUT-017 (P2, owner muse_3) — fit-cost-cap half ONLY. The scoring
  half is covered by TASK-FUT-041 (MERGED, PR #2130). Board record filed by
  coordinator watch214 (2026-11-27, hub #2045): POOL 8 standing item (body
  2026-11-22), never filed as a board record until now.
- Claim: hub #2045 comment 7217273580, 2026-11-27 ~17:05 IST (Burn Enforcer
  17:01 §C); branch `muse3/task-fut-017-fit-cost-cap` from main `caa597bc`.
  Board flip rides the next coordinator board PR (coordinator-only flip rule).
- Acceptance (board record, main `f0d575f1`, blob `409850b4`, verified
  first-hand): "Fit-cost cap: per-forecast-cycle fit cost measured on live
  Futuris scheduler cycles; a cap is set from the measured numbers and
  enforced (cycles over cap are flagged, not silently run)." + "Fit-cost
  numbers + cap filed as docs/collaboration/TASK-FUT-017-EVIDENCE.md."
- Live-proof route (board record): live Futuris scheduler on IntelX-Server.
- This file is checkpoint 1 — scoping + live-state verification. No code
  change in this checkpoint; the cap-setting measurement leg follows.

## 1. What already exists (verified first-hand — this is a live leg, not a build)

- The fit-cost implementation is already merged: PR #1368 (Muse 1)
  "TASK-FUT-017: Futuris standing per-cycle accuracy scoring + explicit
  fit-cost cap", merged 2026-11-22 (merge `b9123028`), head `0fa53ec5`.
  The standing-accuracy-scoring spec doc
  (`docs/collaboration/TASK-FUT-017-STANDING-ACCURACY-SCORING.md`) describes
  that implementation; this task does NOT rebuild it.
- `Futuris/futuris/models/fit_cost.py` exists on main (sha `624bba1a`,
  10,149 bytes) — read in full this run. Mechanism: `estimate_fit_memory_mb`
  (conservative upper-bound estimate per candidate family: naive/drift/
  seasonal_naive 2x frame, AutoETS 12x, MeanEnsemble 14x, AutoARIMA 48x +
  per-exog term + 4MB search overhead; unlisted adapters take the 48x bound);
  `shortlist_candidates` (router rank order in, affordable prefix out, at
  least the cheapest kept, dropped names + every estimate recorded);
  `resolve_fit_memory_budget` (explicit caller budget, else configured cap,
  else 256MB default); `final_fit_within_budget` (winner full-data refit;
  cheap baselines never refused). Enforced in `select_best_adapter` and in
  the pipeline final refit; decisions ride in `Forecast.model_metadata`
  (`fit_memory_budget_mb`, `fit_memory_estimates_mb`,
  `fit_memory_kept_total_mb`, `fit_cost_capped`,
  `candidates_dropped_by_fit_cost_cap`, `final_fit_cost_capped`,
  `final_fit_estimate_mb`, `final_fit_fallback_adapter`).
- Config: `FUTURIS_FIT_MEMORY_BUDGET_MB` exists in `Futuris/futuris/infra/config.py`
  (default 256MB — half the 512M MemoryMax backstop).

## 2. Live state — IntelX-Server (server 6), probed first-hand ~18:12–18:16 IST

- Host `ip-172-26-4-138`. `Futuris.service` active / running.
- Deployed code carries the cap: `/opt/friday_universe/Futuris/futuris/models/fit_cost.py`
  present, 10,149 bytes, mtime Nov 22 22:52 — same size as main, deployed the
  evening of the #1368 merge. `FUTURIS_FIT_MEMORY_BUDGET_MB` present in the
  deployed `infra/config.py` (line 149). `selection.py` present alongside.
- Running process: uvicorn `futuris.api.app:app`, port 8004, pid 35287,
  since Nov 26 12:31. ExecStart verified via systemd.
  (`/opt/friday_universe` on S6 is not a git checkout — no `.git` — so the
  deployed sha cannot be read from git; the file-size + mtime + setting
  checks above are the deploy evidence.)
- The scheduler is producing real forecasts on schedule (FUT-041, verified
  first-hand 2026-11-27 ~16:40 IST, merged PR #2130): 1652 forecasts, 1127
  scores; last 3 cycles 08:33 / 09:33 / 10:33 UTC with real forecasts
  (+55 forecasts in ~5h19m). Live endpoint 32.236.185.237:8004: `/ready`
  ready (database connected, Oracle), `/health` degraded (storage ok 13/13;
  forecasting capability unknown — no model probe exists).
- `/v1/self/status` is NOT readable unauthenticated: curl to
  `127.0.0.1:8004/v1/self/status` returns HTTP 403
  `{"error":{"code":"forbidden","message":"Insufficient permissions:
  requires minimum role 'viewer'"}}` (probed ~18:16 IST). The
  `forecast_accuracy` section on the status surface therefore cannot be
  read by this route; no auth bypass was attempted. The fit-cost numbers
  live in `Forecast.model_metadata` in the store — that is the measurement
  route (see §3).

## 3. Measurement route + plan (checkpoint 2)

- Route: the FUT-041 store route — FRIDAY-Server (bridge server 3),
  Futuris's own session factory + tracker code against the Oracle DB the
  S6 scheduler writes to (`Futuris/.env` present there; FUT-041 verified
  the probe files hash-identical to main). Read-only: list recent forecasts
  and extract the fit-cost metadata keys (§1) across several hourly cycles;
  count capped vs uncapped cycles; report the distribution of
  `fit_memory_kept_total_mb` and `final_fit_estimate_mb` per cycle.
- Blocker found this run: the FUT-041 probe scripts are gone from server 3
  (`/tmp/fut036_probe.py` — "File not found", verified first-hand ~18:20 IST;
  scratch cleaned between runs). Checkpoint 2 rebuilds the probe: read the
  session factory + forecast model on server 3 first, write a read-only
  script, read it back before running, then sample.
- Cap decision (checkpoint 2/3): the configured default is 256MB. The cap is
  set FROM the measured numbers — if live kept-totals sit far below 256MB
  with no capped cycles, the cap stays 256MB as configured and the evidence
  is that it binds only on genuinely large frames; if live estimates
  approach or exceed it, the cap is re-set from the measured distribution
  and the enforcement (flagged, not silently run) is verified in
  `model_metadata` on over-cap cycles. No live restart, no config change,
  no server move in this task — the stop order on server moves stands, and
  any deploy/restart needs merge + hub clearance.
- Bridge transport was flaky this run: 3 failed calls (S6 probe2 ×2,
  "MCP request did not complete"; S3 read_file ×1 transport) against 4
  successful ones. Retries succeeded. No write was attempted twice without
  a read-back first.

## 4. States

- implemented NO (no code change owed — implementation merged as #1368;
  this task's deliverable is the live measurement + cap evidence) /
  tested NO (live measurement leg not yet run — checkpoint 2) /
  merged NO / deployed n/a (no code change; no live change made) /
  production-verified NO.
- Next: checkpoint 2 — rebuild the server-3 store probe, sample live
  fit-cost metadata across cycles, set the cap from the measured numbers.

— Muse 3
