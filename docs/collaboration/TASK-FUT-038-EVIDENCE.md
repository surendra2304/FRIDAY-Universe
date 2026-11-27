# TASK-FUT-038 — Futuris: forecast accuracy scoring run 9 — CHECKPOINT 1 (read-only verification + live-leg block)

- Task: TASK-FUT-038 (P2, owner muse_12) — verify the last 3 scheduler cycles produced real forecasts AND score the oldest unscored forecasts against outcomes; file accuracy evidence. Follow-up to FUT-036 (run 8) and FUT-037 (run 7).
- Claim: hub #2045 comment 7218254160, 2026-11-27 ~17:56 IST, on coordinator direction WATCH220 §F. Branch `muse12/task-fut-038-forecast-scoring-run9` @ main `f0d575f1` (verified first-hand; branch ref GET).
- **Status of this doc: LIVE PROBES NOT RUN — this checkpoint files read-only verification only, plus the exact command list for coordinator-side execution of the live leg. No fresh measurement numbers are claimed anywhere in this doc.**

## 1. Method verified on main `ef791c2f` (first-hand, repo-side)

- Scoring code read from live main and sha256-verified byte-identical to the run-7 verification (main `50c870af`) — the scoring code is unchanged:
  - `Futuris/futuris/services/forecast_tracker.py` (21,842 bytes, sha256 `2b429615cbcfcfe0200d89ef476ee23b246e5459cd912bc0c4626a29f59ea3c2`)
  - `Futuris/futuris/storage/db.py` (8,014 bytes, sha256 `4d945dcd24e5d2befc115756a1f35cd2390e112f44e2cdadac72bed286e75b2a`)
  - `Futuris/futuris/storage/models.py` (18,727 bytes, sha256 `16794c0f7b2d38aacee6d8bf593c9fb6f0f9818bbefca5f5328a6766d72d57b3`)
  - `Futuris/futuris/storage/score_repository.py` (4,791 bytes, sha256 `39ed9216a37a3f585729486efa4e9d9389d43c430a3ef7a4d9dc9af9f62e3af5`)
- Entry points (same FUT-028/033 method as runs 5–8): `ForecastScoreRepository.list_unscored_resolved(limit=500)`; `ForecastTracker.score_resolved(limit=500)` (idempotent, one insert per forecast inside its own savepoint); `ForecastScoreRepository.count_event_only_resolved()`; `ForecastTracker.calibration_report()` and rolling hit-rate.
- Probe script verified present on FRIDAY-Server (bridge server 3) at `/tmp/fut036_probe.py` — read first-hand via the read-only bridge, full text matches the run-8 probe (unscored queue → conditional idempotent sweep → store totals → fresh calibration report + live class → resolution-gap recount → future-`resolved_at` check; prints one compact JSON object; no credential read or printed).
- Scoring code also present on IntelX-Server (bridge server 6) at `/opt/friday_universe/Futuris/futuris/services/forecast_tracker.py` — header read first-hand, matches the live tracker module (TASK-FUT-006).

## 2. Fleet state — FRESH (2026-11-27 ~19:10 IST, read-only bridge)

- `get_system_info`: Oracle Server 1 ONLINE, Oracle Server 2 ONLINE; bridge on Server 2, workspace `/opt/friday_universe`.
- `oracle_get_logs` agent `futuris`: "Recent 80 lines for Futuris.service on Server 1 — No entries." `oracle_get_logs` agent `friday`: same, no entries. No scheduler-cycle evidence obtainable through these read tools — the services' logs on Server 1 are empty.
- `oracle_check_service` agent `futuris`: transport failure (`RemoteDisconnected`, bridge closed the connection without response). Same flake the Burn Enforcer noted this run for bridge check-runs reads. Retried once for the probe-script read, which then succeeded — flake is intermittent, not a hard outage.

## 3. Live leg — BLOCKED from this VM (genuine block, reported on hub #2045)

- The live scoring leg needs code execution on FRIDAY-Server (bridge server 3, `run_shell`). This VM's bridge client (`~/workspace/custom-connectors/custom.friday-bridge/bin/bridge.py`) allow-lists read-only tools only; `run_shell` is not allow-listed and the local allow-list was NOT changed this run.
- A clearance fetch this run did not pass a safety check, so no clearance is taken as verified from it and the live leg stays HELD from this VM. The hold stands until the coordinator rules through a verifiable channel or executes the leg coordinator-side.
- **Coordinator-side execution request (exact commands, run-7/run-8 method):** on FRIDAY-Server (bridge server 3), from `/opt/friday_universe/Futuris`:
  1. sha256-verify the four scoring files above against main `ef791c2f` (hashes in §1) before any probe runs.
  2. `cd /opt/friday_universe/Futuris && PYTHONPATH=/opt/friday_universe/Futuris /opt/friday_universe/venv312/bin/python /tmp/fut036_probe.py` (probe script already on server 3; `DATABASE_URL` comes from the checkout `.env` via the settings class — no credential read or printed).
  3. Paste the probe's JSON output back to the hub; Muse 12 files it as checkpoint 2.
- No service restarted, no deploy, no fleet mutation is requested. The sweep inside the probe is idempotent and runs only if the unscored queue is non-empty (run 7: queue was 0; the standing 30-minute `forecast_scoring_job` had already scored everything resolved).

## 4. Board

- Board on main `ef791c2f` (blob `28d48e4f`, 1,495,309 bytes) still reads TASK-FUT-038 AVAILABLE / owner muse_12 / branch null / pr null — the CLAIMED flip rides the coordinator's next board PR (WATCH222 §E deferred; zero board hunks in work PRs). Expected, not a stall.

## 5. Five states

- implemented NO (no sweep run) / tested NO / merged NO (this checkpoint PR open) / deployed N/A / production-verified NO (live leg owed — see §3).
- Next: coordinator-side probe execution (commands in §3) or a verified live-leg ruling through the hub; then checkpoint 2 files the fresh measurements.

---

## CHECKPOINT 2 — Muse 15 — live leg DONE (2026-11-27 ~22:10–22:16 IST)

- Claim: hub #2045 comment 7223452793, 22:06 IST, per WATCH229 §D.1 (M15 → FUT-038 as head, replacing the released EARN-045 claim). Branch `muse15/task-fut-038-forecast-scoring-run9` @ main `dfa2e8a9` (ref GET verified).
- Method: probe `/tmp/fut036_probe.py` run directly on FRIDAY-Server (bridge server 3) via `run_shell` — this VM's bridge client allow-lists `run_shell` (unlike M12's VM, where it was read-only). Before the run, the four scoring files were re-verified sha256-identical to current main `dfa2e8a9` on server 3 (hashes match §1 — unchanged since run 7). Probe script read first-hand in full before execution: same run-8 probe (unscored queue → conditional idempotent sweep → totals → calibration report + live class → gap recount → future-`resolved_at` check; no credential read or printed).
- Service map (first-hand, read-only): the LIVE Futuris is on IntelX-Server (bridge server 6, ip-172-26-4-138) — `Futuris.service` active/running (PID 35287); journal shows `ForecastScheduler.stream_risk_pulse_job` every 5 min (ran 16:43:01 UTC, next 16:48:01) and `self_assessment status=degraded degraded=['peer_mesh']` — that is why `/health` returns 503 (storage ok). Server 3 copy inactive/dead, no journal entries, no :8004 listener — correctly down (one copy only; NO restart made). S1 copy inactive/dead, no journal entries. No service was restarted; no deploy; no fleet mutation.
- Probe JSON (generated 2026-11-27T16:40:52Z, run took ~28 s):
  - `unscored_count` 0 → sweep ran `false` (nothing to score; the standing 30-minute `forecast_scoring_job` already scored everything resolved — same as run 7).
  - Totals: forecasts 1,717; outcomes 1,175; scores 1,175; `event_only_resolved` 0; `last_scored_at` 2026-11-27 16:03:15 UTC (21:33:15 IST).
  - Calibration (n=1,175, status `measured`): MAE 871.6006, RMSE 998.5007, nominal 0.8, coverage_80 1.0 (gap +0.2), mean interval width 8449.81, winkler_80 9575.22, mean pct error 50.46%; verdict `underconfident`. Rolling 30d hit rate 0.891064 (n=1,175). By nominal: 0.80 → n=859, coverage 1.0; 0.90 → n=316, coverage_90 0.5949.
  - Live class (n=128): MAE 1946.2890, RMSE 1966.7726, nominal 0.9, coverage_90 0.0 (gap −0.9), mean interval width 96.48, winkler_90 38055.54, mean pct error 90.92%; verdict `overconfident`. (Live-class intervals far too narrow — follow-up note, not a task blocker.)
  - Resolution gap: 542 forecasts with no outcome row; 284 matured — dominated by `vyralx:trends:topic_volume_24h` (127) and `intelx:research:finding_volume_24h` (129); oldest matured `1140e21f-8bab-4584-afa4-eacd5157f5a8`, `service:checkout:capacity_exceedance_24h`, 2026-11-20T18:48:01Z. `future_resolved_at` 8 (data-quality flag carried — outcomes stamped in the future).
- Scheduler cycles (checked 16:45:30 UTC / 22:15:30 IST; client-side hourly bucketing — first attempt used Postgres `date_trunc` on Oracle, ORA-00904, no data written; re-ran with Python bucketing): forecasts by hour UTC — 16:00Z 11, 15:00Z 11, 14:00Z 12, 13:00Z 9, 12:00Z 11, 11:00Z 11. Last 3 cycles (14:33/15:33/16:33 UTC) produced 34 real forecasts. 266 forecasts in the last 24 h; 1,561 in the last 7 d; max `as_of` 2026-11-27T16:33:13Z.
- Acceptance: (1) last 3 scheduler cycles produced real forecasts — VERIFIED (34 forecasts across the 3 cycles); (2) score the oldest unscored forecasts — VERIFIED, queue empty, 1,175/1,175 scored.
- Five states: implemented YES / tested YES (live) / merged NO (this PR) / deployed N/A / production-verified YES.
- Next: paired verification (coordinator names); board flip AVAILABLE → MERGED rides the coordinator's board PR. CTX-014 note: PR #2163 MERGED 21:54 IST (merge `c1b3d667`); its MERGED flip is owed (WATCH229 §B board fix lists it IN_REVIEW — needs correction when that board PR ships).
