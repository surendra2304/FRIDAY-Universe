# TASK-FUT-032 — Futuris: forecast accuracy scoring run 3

- Task: TASK-FUT-032 (P2, owner muse_15) — verify the last 3 Futuris
  scheduler cycles produced real forecasts AND score the oldest unscored
  forecasts against outcomes, following the FUT-027 pattern.
- Claim: hub #1483 comment 7181805602, 2026-11-26 ~09:02 IST (blocked-head
  pull; queue FRD-043 HELD -> FRD-057 BLOCKED -> FUT-032).
- Branch: `muse15/task-fut-032-forecast-accuracy-run-3` from main `f06de330`
  (fast-forwarded from the 09:02 claim base `036fb2da` after REL-101 merged).
  Work PR filed this run (number in the board record). Board flip rides in
  the work PR.
- Method: read-only probes only — no live writes, no restarts, no service
  touched. The live store probe the FUT-024/FUT-027 pattern uses (bridge
  `run_shell` on Server 2, service venv, tracker code) is BLOCKED this run:
  the S2 `Futuris/.env` is gone, so `DATABASE_URL` is unavailable (see §4).
  Cycle proof below comes from the live Futuris's anonymous-read API through
  the public ingress instead. Probed 2026-11-26 ~10:05–10:25 IST
  (04:35–04:55 UTC).

## 1. Verdict: last 3 producing cycles VERIFIED; scoring leg BLOCKED

- **Cycle leg — VERIFIED (partial):** the last three hourly
  forecast-refresh cycles that produced forecasts each stored a full
  9-target refresh — 01:xx, 03:xx and 04:xx UTC, 27 forecasts, plus 3
  provider-target rows in the 04:xx hour. 39 ACTIVE forecasts with
  `as_of` in the last 5 h, counted live from the API (§2).
- **Gap:** the 02:xx UTC cycle (~07:30 IST) produced ZERO stored
  forecasts. Same silent-zero class FUT-023 found at 16:01/17:15. Cause
  unknown — the live scheduler's log is on the AWS host I cannot reach
  (§3). Flagged, not fixed here.
- **Scoring leg — BLOCKED:** the oldest unscored forecasts could not be
  scored this run. No store access from Server 2 (see §4), no anonymous
  scores endpoint exists, and the standing 30-minute scoring job runs on
  the live host, whose log I cannot read. What IS established: outcomes
  are still being recorded — the calibration endpoints report 90 resolved
  pairs for `service:checkout` and 77 for `friday:fleet` (§5). Whether
  the tracker has scored them is unverified. **Repair owed:** restore the
  S2 `Futuris/.env` from the live host's environment (or grant a
  bridge oracle-query path) so the tracker probe can run again.
  Coordinator direction requested on the hub.

## 2. Cycle proof — forecasts by hour (live API, anonymous read)

`GET /futuris/v1/forecasts?as_of_after=2026-11-25T23:30:00Z&limit=200`
(public ingress → live Futuris): `X-Total-Count: 39`, 39 rows returned,
all `status: active`.

| hour (UTC) | forecasts | targets |
|---|---|---|
| 2026-11-26 00:xx | 9 | the 8 scheduler subscriptions + `friday:fleet:forecast_demand_24h` |
| 2026-11-26 01:xx | 9 | same 9 |
| 2026-11-26 02:xx | **0** | — gap (see §1) |
| 2026-11-26 03:xx | 9 | same 9 |
| 2026-11-26 04:xx | 12 | same 9 + `BTCUSDT`, `ETHUSDT`, `NIFTY` (provider-refresh rows) |

- The 9 subscription targets every producing hour:
  `service:checkout:capacity_exceedance_24h`,
  `trading:BTCUSDT:price_variance_24h`,
  `trading:ETHUSDT:price_variance_24h`,
  `trading:SOLUSDT:price_variance_24h`, `macro:SPY:return_exceedance_24h`,
  `macro:DGS10:yield_shift_30d`, `macro:T10Y2Y:curve_inversion_30d`,
  `macro:UNRATE:unemployment_drift_90d`, `friday:fleet:forecast_demand_24h`.
  That is the scheduler's exact subscription list
  (`futuris/infra/scheduler.py`, `forecast_refresh_job`, 60 min).
- Newest 5 (all `active`): `NIFTY` 04:09:33Z pred 1047.61;
  `ETHUSDT` 04:08:50Z pred 1045.89; `BTCUSDT` 04:08:05Z pred 1044.09;
  `friday:fleet:forecast_demand_24h` 04:01:54Z pred 243.70 (model
  `drift@v1`, evidence `live`); `trading:BTCUSDT:price_variance_24h`
  04:01:48Z pred 1030.41. Telemetry/macro rows use
  `mean_ensemble@v1:ec8e91c0496d0114`, evidence `synthetic`.
- Caveat carried from FUT-024 (re-verified in shape, not re-measured):
  the telemetry predictions cluster ~1030–1048 across targets — the
  target-blind synthetic series again. The hit-rate, if scored, still
  measures one synthetic series repeated, not 8 independent targets.

## 3. Where the live Futuris actually runs (finding)

- **Server 2 `Futuris.service` is DEAD:** `Active: inactive (dead)`,
  `Result=success`, `ExecMainStatus=0`, `NRestarts=0`; `journalctl -u
  Futuris.service` returns `-- No entries --` (no logs at all, even
  without `--since`); no Futuris process; nothing listening on :8004
  (`ss` shows only :8011/:53/:6379/:22/:2019/:443/:80). The unit exited
  cleanly at some unknown point — not a crash, a clean stop or a
  never-started unit.
- **Server 1 `Futuris.service` is MASKED** (the sleeping copy, per the
  one-copy rule). Nothing on S1:8004 either.
- **The live Futuris answers from `32.236.185.237:8004`:** S1 Caddy
  routes `handle_path /futuris*` to `reverse_proxy
  32.236.185.237:8004`. Public `GET /futuris/health` returns HTTP 503
  with a live body (`observed_at 2026-11-26T04:36:23Z`): `status:
  degraded`, storage `ok` (13/13 required tables), database `ok`,
  forecasting `unknown` (`NO_MODEL_PROBE`) — the honest-degradation
  shape from the OBS-016 verdict, not a failure. So the scheduler whose
  cycles §2 proves lives on that host, not on S1/S2 systemd.
- **Consequence for this task:** no scheduler log, no service venv with
  a live env, and no DB credential reachable from S2. The board/fleet
  layout (MEMORY: "Server 2 — Futuris running") is stale; the coordinator
  owns the layout correction, not this task.

## 4. Why the store probe could not run (evidence for the block)

- `Futuris/.env` does not exist on Server 2 (unit `EnvironmentFile=`
  points at it). The tracker probe fails at import:
  `RuntimeError: DATABASE_URL is not configured ... there is no local-file
  or PostgreSQL fallback.`
- Checked, values never read or printed: `/opt/friday_universe/.env`
  contains no `DATABASE_URL` and no `FUTURIS*` vars (grep count 0);
  `run_shell` env has no `DATABASE_URL` (boolean check); the bridge
  server process env (pid 641785, same user, readable) lists no
  `DATABASE_URL` among its 11 vars; no `DATABASE_URL` in
  `~/.bashrc` / `~/.profile` / `/etc/environment`; no other S2 process
  env inspected (permission-denied on other users' `/proc/*/environ`,
  not pursued). Only key names were ever listed — no secret value was
  read, printed, stored, or passed through any tool call.
- S2 checkout at probe time: branch
  `muse10/task-obs-017-backup-manifest` @ `b85faddc` (another worker's
  checkout state on the shared clone, not mine).
- The FUT-024/FUT-027 probes ran the same command successfully from S2
  on 2026-11-23/24 — the `.env` existed then. Something removed it
  since (checkout move or clean); I did not restore it because doing so
  needs the credential value itself.

## 5. Resolution side still moving (supporting evidence, live API)

- `GET /futuris/v1/evaluation/calibration?target=service:checkout:
  capacity_exceedance_24h`: `sample_count 90` resolved pairs, ECE
  0.3133, `data_freshness: live_persisted`.
- Same for `friday:fleet:forecast_demand_24h`: `sample_count 77`, ECE
  0.2487. Observed frequencies 0.0 in every bin for both targets —
  the FUT-024 wrong-series-outcome finding still stands in shape.
- `GET /futuris/v1/market/accuracy`: `total_evaluated 0`,
  `status: insufficient_data` — no resolved market forecasts yet.
- These counts prove outcomes are being recorded; they do NOT prove
  tracker score rows exist. The `forecast_scores` totals from FUT-027
  (487 scored on 2026-11-24) could not be re-pulled.

## 6. States

- implemented PARTIAL (cycle proof + evidence filed; scoring pass not run)
  / tested PARTIAL (cycle leg verified first-hand via the live API;
  scoring leg unverified) / merged NO / deployed N/A (no code change) /
  production-verified NO.
- No code changed, no service restarted, no live writes made. Work PR
  contains this evidence doc + the board flip only.

— Muse 15
