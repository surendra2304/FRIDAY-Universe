# TASK-REL-071 — Stratex health path: retire the legacy testnet heartbeat + surface daemon evaluation age

- **Assignment:** coordinator watch comment 7079741096 (pool 9, P1, 2026-11-22 ~18:50 IST), direct follow-on to TASK-STR-HLT-001. **Claim:** issue #35 comment 7079835965.
- **Board:** no TASK-REL-071 record on main at claim (verified this run: main 3dd7cfba, board blob 2f13afe4aac127fb2f9ca6972a07506b884e0860, 14,462 lines); the record is CREATED in this PR (IN_REVIEW, owner muse_2) — see WORK_BOARD.yaml.
- **Merge-base:** main `3dd7cfba`. **Work commit:** `f823252ffa96c7c5ad3313985e482cc998906ca3`. **PR:** #1383.

## What was stale

TASK-STR-FWD-032 excised classic-testnet from live Binance modules, but the Stratex health path still read the retired testnet engine's heartbeat first:

- `Stratex/testnet_heartbeat.json` on Server 1 is frozen since **2026-11-14T21:31:34Z** (`status: STOPPED`, `worker_alive: false`, `mode: TESTNET`, `last_strategy_evaluation: 2026-11-14T21:31:03Z`, 8 days stale at probe time). Its only writer is the retired testnet engine (`Stratex/testnet_engine/service.py::_write_heartbeat`, line 3447), gracefully stopped and never restarted.
- `Stratex/dashboard.py::get_engine_health_data` resolved that file first (`TESTNET_HEARTBEAT_FILE` / `testnet_heartbeat.json`), so `/health` derived liveness, capability (`STALE_STRATEGY_EVALUATION` from the frozen 2026-11-14 stamp) and served fields (`last_market_update`, `last_candle_close`, `strategies`) from a dead engine — rescued in FUTURES mode only by the daemon-snapshot override.
- `Stratex/api/health.py::_measure_feed_freshness` resolved the same file first, so `/api/v1/health/detailed` derived feed freshness from the frozen heartbeat.
- No health output carried the daemon evaluation **age**: the daemon heartbeat's `last_strategy_evaluation` was served as a bare timestamp (dashboard snapshot `daemon_last_evaluation`), and the supervision `market_conditions.last_analysis` likewise — staleness was invisible without parsing ISO strings.

## Live baseline (read-only probes, 2026-11-22 ~19:03–19:06 IST, before this change)

- Server 1 `/opt/friday_universe/Stratex/testnet_heartbeat.json`: frozen as above (mtime 2026-11-15 03:01 IST); `heartbeat.json` is a 84-byte runtime-lease file, not an engine heartbeat.
- Server 1 `state/daemon_heartbeat.json`: `RUNNING`, `scan_count: 1`, `last_strategy_evaluation: 2026-11-22T12:21:44Z`, balance 10566.86, 29 positions — but pid 2260105 dead on Server 1 and the file 73 min old at probe: the live daemon runs on **U1 (Stratex Server, 13.55.176.237:8003)**, reached from Server 1 via the `stratex-u1-tunnel` SSH tunnel (port 18003). Server 1 holds a repo checkout, not the live daemon.
- Live `/health` via the tunnel (U1, 19:05 IST): `engine: online`, `engine_source: multi_venue_daemon`, `open_positions: 29`, `daemon_balance: 10561.80`, `unrealized_pnl: 59.17` — the daemon is alive on U1 — but it still serves the **pre-HLT-001** text (`capability_warnings: "DEMO_ENVIRONMENT: execution venues are Binance Futures testnet and OANDA practice"`, `environment: multi_venue_testnet_practice`) because U1 has not been redeployed since HLT-001 merged 18:04 IST. No evaluation-age field is present in the served payload.
- `/api/v1/health/detailed` was **not** probed live: it requires an `X-API-Key` and this task touches no credentials by design (see honesty bounds).

## Changes (work commit)

- `Stratex/daemon_book.py:74-84` — new public `daemon_heartbeat_candidates()`: the single candidate convention (env `STRATEX_DAEMON_HEARTBEAT_FILE`, then `cwd/state`, then this module's `state/`) shared by the dashboard and the feed pillar, so writer and readers always agree. The retired file is not a candidate.
- `Stratex/dashboard.py` — `get_engine_health_data` (resolution :1133-1141, age :1159-1171, liveness :1178-1183, capability :1228-1250, return :1286): resolves `STRATEX_HEARTBEAT_FILE` → daemon candidates → generic `heartbeat.json` fallback; the frozen file is never read. Freshness is the worse of content-timestamp age and file-mtime age (a file whose content claims fresh but whose mtime is old is stale evidence). `worker_alive` is format-aware: an explicit key wins, otherwise `status == "RUNNING"` is the alive signal (the daemon heartbeat has no `worker_alive` key). `last_strategy_evaluation_age_sec` is surfaced in the return dict; an unreadable evaluation stamp now yields age `None`, never `0.0`.
- `Stratex/dashboard.py::_multi_venue_daemon_snapshot` (:1091-1106) — adds `daemon_last_evaluation_age_sec` next to `daemon_last_evaluation`.
- `Stratex/dashboard.py::_health_payload` (:1328-1329) — the served `/health` now carries `daemon_last_evaluation` + `daemon_last_evaluation_age_sec`.
- `Stratex/dashboard.py::api_strategy_metrics` (:3633-3641) and `_get_real_strategy_matrix` (:6628-6634) — the two remaining live reads of the retired file (dashboard UI panels, not health endpoints) are retired too: the strategy-metrics panel no longer gates on a heartbeat (the daemon heartbeat carries no strategies list; the frozen file's 300 s freshness check had already neutralised it, so the verdict is unchanged), and the strategy matrix now uses the governance config instead of the frozen list (which had been overriding config with a dead engine's strategies).
- `Stratex/api/health.py::_measure_feed_freshness` (:136-185) — resolves the daemon heartbeat the same way; feed evidence is now `last_strategy_evaluation` (stamped at scan-cycle boundaries, where an evaluation — and therefore a market-data fetch — just completed) alongside the legacy `last_market_update` / `last_candle_close` keys when present; reports `last_strategy_evaluation_age_sec`, `heartbeat_age_sec` and `heartbeat_source: daemon_heartbeat`.
- `Stratex/api/friday_supervision.py::_real_trading_data` (:233, :242-246) — `market_conditions` gains `last_analysis_age_sec` (seconds since the last `_ensure_market_analysis` refresh completed), `None` on a cold process.
- `Stratex/tests/test_rel_071_stratex_health_path.py` — new regression file (9 tests): source guard (no `TESTNET_HEARTBEAT_FILE` / quoted `testnet_heartbeat.json` in `dashboard.py` or `api/health.py`); daemon-format heartbeat serves ONLINE with evaluation age in engine data and `/health`; a frozen legacy file sitting in cwd is ignored; feed pillar streaming / stale / no-evidence / missing cases on daemon-format fixtures; supervision age surfaced and `None` when cold.
- Updated fixtures (env var rename only, assertions unchanged unless noted): `test_daemon_heartbeat_health.py` (frozen-testnet fixture removed — the health path no longer reads that file; `test_missing_primary_heartbeat_still_consults_the_daemon` now points the override at a missing file), `test_engine_capability_truthfulness.py`, `test_render_deployment_and_supervisor.py`, `test_critical_remediation.py` (feed tests).
- `.github/workflows/owner-workflows.yml` — the new test file is added to the Stratex contracts list (it would otherwise be collected by no workflow, the PR #936 class).

## Verification

- Edited files syntax-checked (`py_compile`) and the workflow file YAML-parsed. No local pytest run on fetched content (execution-risk check); verification rests on repo CI.
- CI on the PR head is the test evidence (the new regression file now runs in the contracts job). CI status at filing: running — see PR checks.

## Not done here (honesty bounds)

- **Live probe/deploy:** NOT done in this PR. U1 still serves the pre-HLT-001 `/health` text (and the pre-REL-071 payload shape) until Muse merges AND clears deployment; the live re-probe (expect `daemon_last_evaluation_age_sec` present, frozen file ignored) is owed after clearance. No restart, no live config change, no deploy in this task.
- **`/api/v1/health/detailed` live probe:** not probed — the endpoint requires `X-API-Key` and this task does not touch credentials. Its new behaviour is covered by the regression tests only; a keyed probe is owed after deployment.
- **Residual legacy naming (not the heartbeat):** `TESTNET_LEDGER_FILE` / `testnet_trade_ledger.jsonl`, `TESTNET_PORTFOLIO_FILE`, `TESTNET_BASELINE_FILE`, the `testnet_engine` service itself (the retired writer) and its tests, FRIDAY's `stratex_portfolio.py` fallback read, and the `bot_mode` default `"TESTNET"` in `api/health.py::fast_liveness` remain — file/ledger naming, not the heartbeat, and renaming the on-disk ledger is a separate migration. The daemon heartbeat carries no per-venue connectivity flags, so `binance_connected` / `websocket_connected` still default to `True` when the key is absent (pre-existing default, unchanged).
- The daemon heartbeat carries no strategies list: the strategy-metrics panel can no longer report a DISABLED strategy from a heartbeat (see change note above); a live loaded-strategies source is a separate task if wanted.

— Muse 2
