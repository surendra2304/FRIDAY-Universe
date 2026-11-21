# Stratex AWS U1 move — cutover checklist (TASK-STR-U1-001)

**Task:** TASK-STR-U1-001 — inventory everything the Stratex move from S1
(Oracle Server 1, production) to FRIDAY-Universe-1 (AWS U1) needs, and file
the cutover checklist. **Preparation only — no cutover without Muse's hub
clearance.**

**Author:** Muse 7 (worker Muse, roster `muse_7`).
**Assignment:** issue #35 comment 7065396261 (Muse, coordinator ~21:35 IST).
**Claim:** issue #35 comment 7065615787; claim board PR #1231.
**Date:** 2026-11-21.

## Bases (verified)

- **Declared side:** main `9ef366a0` (board blob `c9fd231d`, verified against the
  git blobs API before editing). All repo paths below are at this base.
- **Live side:** Oracle Server 1 (`10.0.0.121`, host `friday-universe-vnic`),
  probed read-only via the bridge 2026-11-21 ~21:58–22:05 IST
  (`oracle_check_service`, `run_shell`, `read_text`; nothing written, no
  service restarted, no secret read). S1 git checkout at the time: branch
  `main` @ `03378ba4` — four merges behind main `9ef366a0` (PRs #1226, #1227,
  #1228, #1229); the U1 host must start from current main, not from S1's
  checkout.
- **No secret values in this file.** Credential *names* and *files* only.
  Values live in `Stratex/.env` on S1 (mode 600) and in the credentials file;
  they are copied as a file, never transcribed.

## 1. Scope — what moves, what does not

**Moves to U1 (the Stratex lane):**

| Piece | Entry point | Live port |
|---|---|---|
| Stratex API (`Stratex/dashboard.py`, Flask) | systemd `Stratex.service` | 8003 (`PORT=8003`) |
| Stratex Daemon (`Stratex/autonomy/run_daemon.py`) | systemd `Stratex-Daemon.service` | none (outbound only) |
| Forward scorecard generator (`Stratex/measurement/forward_scorecard.py`) | systemd `stratex-forward-scorecard.service` + `.timer` (every 15 min) | none |

**Does NOT move in this task:** FRIDAY (10000), Inference (8001), Memora
(8002), Futuris (8004), IntelX (8005), Forge (8006) stay on S1. Caddy stays
on S1 (see §7). `Stratex-Testnet.service` (Binance testnet `bot.py`) stays
**masked** on S1 and is not revived on U1 without a separate clearance.
`deploy/deploy_fleet.sh` (docker-compose fleet deploy) and
`Stratex/deploy.sh` / `Stratex/deploy_production.py` (Binance-testnet-era
scripts) are legacy and are **not** the deploy path for U1.

## 2. Source state on S1 (live, 2026-11-21 ~22:00 IST)

- `Stratex.service`: active (running) since 21:26:59 IST, Main PID 1683784,
  `MemoryMax=180M`, ~16.8M RSS. Exec (live):
  `/opt/friday_universe/venv/bin/python dashboard.py` — **venv (Python
  3.10.12), not venv312**. (Muse 3 holds clearance since 21:53 IST to repoint
  the API to venv312 live; not yet done at probe time.)
- `Stratex-Daemon.service`: active (running) since 21:27:40 IST, Main PID
  1684339, `MemoryMax=300M`, ~39M RSS, `MemorySwapMax=192M` drop-in
  (`swapmax.conf`). Exec (live):
  `/opt/friday_universe/venv/bin/python -u
  /opt/friday_universe/Stratex/autonomy/run_daemon.py` — **venv (3.10), not
  venv312**; unit env `TRADING_MODE=FUTURES`, `CTRADER_FIX_ENABLED=true`.
  The daemon is CPU-hot (12m57s CPU in 31 min) running strategy scans.
- `stratex-forward-scorecard.timer`: enabled + active (oneshot service;
  `inactive (dead)` between runs is normal — judge by the timer and by
  `generated_at` in `state/forward_scorecard.json`).
- `caddy.service`: enabled + active on S1. `Stratex-Testnet.service`:
  **masked**, inactive (unit file on disk is a 9-byte symlink to /dev/null).
- Disk: `/` 97G, 29% used, 69G free. `Stratex/` tree 111M; `venv312/` 1.7G.
- S1 UFW: active; **22/80/443 only** (v4+v6). Port 8003 is localhost-only
  behind Caddy; nothing Stratex listens on a public interface.
- S1 listeners at probe time: 22, 80, 443, 10000, 8001, 8002, 8003, 8006,
  8008, 8081, 8765, 2019 (localhost). **Observed, out of scope for this
  task:** 8004 (Futuris) and 8005 (IntelX) were not listening, and 8008
  (Sentinel's port — Sentinel lives on S2) was listening on S1. Flagged for
  the coordinator; not investigated here.

### 2a. Live unit files ≠ repo unit files (must be reconciled before cutover)

| Unit | Live on S1 | Repo at main `9ef366a0` | Difference |
|---|---|---|---|
| `Stratex.service` | venv `python dashboard.py`, 180M | `deploy/setup_fleet.sh` writes venv312 `python dashboard.py`, 180M | interpreter only (batch-B flip pending) |
| `Stratex-Daemon.service` | venv `python -u …/autonomy/run_daemon.py`, 300M, env `TRADING_MODE=FUTURES` + `CTRADER_FIX_ENABLED=true` | `deploy/Stratex-Daemon.service`: venv312 `python -u -m autonomy.run_daemon`, 180M, no such env lines | interpreter, entry form, memory cap, env lines |
| `stratex-forward-scorecard.service` | (on disk, 1031 B — content not re-read; timer active) | `deploy/stratex-forward-scorecard.service`: venv `python -m measurement.forward_scorecard`, 256M | presumed same; re-read live file at cutover |
| `Stratex-Testnet.service` | masked | `deploy/Stratex-Testnet.service`: venv `python -u bot.py`, 250M | masked live; stays masked |

`deploy/setup_fleet.sh` (role `1`) is the canonical provisioner for the S1
fleet: it builds `venv312` (Python 3.12) from
`deploy/requirements-server1.lock` (union lock — fails if missing; live
venv312 matches the lock + `sse-starlette==3.4.8`, per TASK-REL-063 audit
`docs/collaboration/S1_VENV_DRIFT_AUDIT.md`), installs the swap-cap
drop-ins (`MemorySwapMax=192M` for FRIDAY, Stratex-Daemon, IntelX), and
writes the seven S1 service units. **It does not write
`Stratex-Daemon.service`** (only its drop-in) and has no Stratex-only mode:
for U1, run only the venv-build step, then install the three Stratex units
from `deploy/` by hand (or add a Stratex-only mode — coordinator decision).
The retired 3.10 `venv` is kept for rollback; U1 starts on venv312 only.
`Stratex/deployment/friday-stratex.service` is a stale duplicate (references
the purged `/etc/default/friday_universe.env`, venv, 180M) — **do not use**.

## 3. Environment inventory (names only — values stay in `Stratex/.env`)

Source of truth for names: `Stratex/config.py`, `Stratex/dashboard.py`,
`Stratex/autonomy/run_daemon.py`, `Stratex/exchanges/*.py`,
`Stratex/notifications/telegram_bot.py`,
`Stratex/security_hardening.py` (all read at main `9ef366a0`).
The live file is `/opt/friday_universe/Stratex/.env` — 7,366 bytes, mode
600, per-agent isolation (no global env file; `/etc/default/friday_universe.env`
was purged per `deploy/setup_fleet.sh`).

### 3a. Venue — cTrader (execution; demo only)

- **Spotware Open API (the order path):** `PEPPERSTONE_CTRADER_CLIENT_ID`,
  `PEPPERSTONE_CTRADER_CLIENT_SECRET`, `PEPPERSTONE_CTRADER_ACCESS_TOKEN`,
  `PEPPERSTONE_CTRADER_REFRESH_TOKEN` (optional),
  `PEPPERSTONE_CTRADER_ACCOUNT_ID`, `PEPPERSTONE_CTRADER_ACCOUNT_NUMBER`,
  `PEPPERSTONE_CTRADER_HOST` / `_PORT` — **allowlist-pinned to
  `demo.ctraderapi.com:5035`; any other value is refused at construction**
  (`exchanges/pepperstone_ctrader_adapter.py`, TASK-STR-PEP-002). Demo
  account of record: Pepperstone DEMO (cTrader, USD, $10,000 virtual,
  1:200) — see the adapter header for the account number. Hard fail-closed:
  SL/TP attached at placement, broker read-back verification, broker
  balance on every read, halt on mismatch, unknown-not-flat on disconnect.
- **cTrader FIX (read-only price/session reference; NOT the order path):**
  `CTRADER_FIX_ENABLED`, `CTRADER_FIX_HOST` (default `demo.cfixapi.com`),
  `CTRADER_FIX_PORT` (default `5212`), `CTRADER_FIX_ACCOUNT_ID`,
  `CTRADER_FIX_PASSWORD`, `CTRADER_FIX_SENDER_COMP_ID`,
  `CTRADER_FIX_TARGET_COMP_ID`. `Stratex/scripts/update_cloud_demo_env.py`
  writes the demo FIX set into `Stratex/.env` (script path cited; values
  not reproduced here).
- **Gate (still open):** the owner's Spotware Open API authorization
  (cTrader ID sign-in + approve tap) + the demo shakedown
  (`Stratex/scripts/pepperstone_shakedown.py`) passing end-to-end. No
  strategy trades this venue before that gate. The Pepperstone app was
  retargeted coordinator-side to the new 'Stratex Demo' (ID 49885, 2026-11-21
  ~19:50 IST, per issue #35 comment 7065396261).
- **Safety:** `ALLOW_LIVE_TRADING` must stay unset/False; `TRADING_MODE`
  stays `FUTURES` (daemon unit env) with the demo venue. Live trading needs
  Surendra's explicit authorization with a proven forward record — never
  implied by this move.

### 3b. Market data (no key; public demo endpoints)

- Binance demo: `https://demo-api.binance.com`,
  `https://demo-fapi.binance.com` (from `Stratex/config.py`).
- Binance keys (`BINANCE_API_KEY`, `BINANCE_API_SECRET`, plus legacy
  `BINANCE_SECRET` / `BINANCE_SECRET_KEY` / `API_KEY` / `SECRET_KEY` names
  read by older code) belong to the masked testnet engine only; they move
  with the file but must not be reactivated with the testnet service.

### 3c. Database — Oracle Autonomous Database (host-independent)

- `STRATEX_DATABASE_URL` (preferred) or `DATABASE_URL` — the dedicated
  `STRATEX` schema login (one unprivileged login per agent; no ADMIN DSNs).
  The ADB is reached over the public internet from the host, so U1 uses the
  **same DSN value**; no database migration. Verify U1 egress to the ADB
  before cutover (§8). The daemon itself holds no DB handle (file state
  only — see §4); the API reads the DSN (`Stratex/dashboard.py:1354`).

### 3d. Messaging / notifications

- Telegram (daemon summaries, alerts): `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `TELEGRAM_WEBHOOK_URL`, `TELEGRAM_WEBHOOK_SECRET`.
  (`Stratex/scripts/telegram_webhook_watchdog.py` exists untracked on S1 —
  see §4; it is not a unit and its status on U1 is an open item.)

### 3e. API auth (dashboard control endpoints)

- `BOT_API_KEY` (admin, all scopes), `API_KEY_CONTROL`, `API_KEY_READONLY`,
  `API_KEY_FRIDAY`, `STRATEX_API_KEY` (FRIDAY scope)
  (`Stratex/security_hardening.py:212-245`). FRIDAY's side carries the
  matching value as `FRIDAY_STRATEX_API_KEY` / `STRATEX_API_KEY` in FRIDAY's
  env (verified same-value 2026-11-14, per the code comment). **Copy the
  values unchanged** — FRIDAY stays on S1 and must keep authenticating
  after the move. An unconfigured key set returns 503, not 401.

### 3f. Daemon tuning / risk / strategy (env-overridable; defaults in code)

- `STRATEX_STATE_DIR` (default `Stratex/state/`),
  `STRATEX_STRATEGY_ALLOWLIST` (comma list; empty = all),
  `STRATEX_TIMEFRAMES` (venue labels — `1w`, not `1wk`; TASK-STR-FWD-035),
  `STRATEX_MIN_CONFIDENCE`, `STRATEX_MIN_RR`, `STRATEX_MIN_STOP_PCT`,
  `STRATEX_MAX_STOP_PCT`, `STRATEX_RISK_PER_TRADE_PCT`,
  `STRATEX_MAX_POSITIONS_PER_VENUE`, `STRATEX_MAX_TOTAL_POSITIONS`,
  `STRATEX_MAX_POSITION_PCT`, `STRATEX_MAX_DAILY_LOSS_PCT`,
  `STRATEX_MAX_HEAT_PCT_PER_STRATEGY`, `STRATEX_MIN_EXPECTANCY_R`,
  `STRATEX_ENTRY_CONFLUENCE`, `STRATEX_FEE_ROUNDTRIP`,
  `STRATEX_FRICTION_ROUNDTRIP`, `STRATEX_HEARTBEAT_PULSE_SECONDS`,
  `STRATEX_INITIAL_BALANCE`, `STRATEX_SELF_EXPERIMENTS`,
  `STRATEX_ADX_THRESHOLD`, `STRATEX_CRYPTO_SYMBOLS`,
  `SCAN_INTERVAL_SECONDS`, `STRATEX_AUTOSTART_SERVICES`,
  `DAILY_LOSS_LIMIT_PCT`, `MAX_DAILY_LOSS_PCT`, `LOSS_STREAK_LIMIT`,
  `FUTURES_LEVERAGE`, `FUTURES_MARGIN_TYPE`, plus the advisory/paper/testnet
  families (`ADVISORY_*`, `TESTNET_*`, `PAPER_*`, `MAX_*`, `SQ_*`,
  `TRAIL_*`, `GEMINI_*`, `AI_UNIVERSE_*`, `INFERENCE_URL`,
  `INFERENCE_API_KEY`, `INTELX_INTELLIGENCE_ENABLED`,
  `FUTURIS_FORECAST_ENABLED`, `MT5_BRIDGE_ENABLED`, `ALLOWED_ORIGINS`,
  `APP_ENV` / `ENVIRONMENT`, `PORT`). Full name list was extracted from the
  files cited above; any name present in the live `.env` but absent from
  code is dead config — record it at cutover, do not invent a use for it.

## 4. State to transfer (local JSON; the daemon is file-state only)

All paths relative to `/opt/friday_universe/Stratex` on S1. Sizes/dates as
probed 2026-11-21 ~22:03 IST; re-snapshot at cutover — these files move
every minute while the daemon runs.

**Must move (live forward record — the move is not a reset):**

| File | Size / mtime at probe | Notes |
|---|---|---|
| `state/forward_scorecard.json` | 250,499 B, 21:59 IST, mode 600 | regenerated every 15 min by the timer; `generated_at` is the freshness proof |
| `state/fill_ledger.jsonl` | 35,349 B, 19:22 IST | every fill; scorecard source |
| `state/equity_snapshots.jsonl` | 297,814 B, 21:32 IST | equity curve; scorecard source |
| `state/position_tags.jsonl` (+ `.bak-fwdbookkeeping-20261117`) | 60,808 B, 21:33 IST | open/closed position tags; scorecard source |
| `state/daemon_heartbeat.json` | 699 B, 22:03 IST | heartbeat age < 60 s is the daemon-liveness proof |
| `state/realized_pnl.json` | 216 B, 19:22 IST | realized P&L |
| `state/account_balance.json` | 71 B, Nov 3 | last broker balance snapshot |
| `state/fix_symbol_map.json` | 6,743 B, Oct 23 | FIX symbol map |
| `state/strategy_priors.json` (+ `.bak-1794540071`) | 278 B, Nov 14 | strategy priors |
| `state/strategy_denylist.json` | 23 B, Nov 14 | denylisted strategies |
| `state/scorecard.json` | 6,640 B, Nov 14, mode 600 | legacy scorecard |
| `state/measurement_alerts.json` | 797 B, Nov 18, mode 600 | measurement alerts |
| `state/legacy_close_records.json` | 1,647 B, Nov 14 | legacy closes |
| `state/cloud_portfolio_state.json` | 90 B, Nov 8 | cloud portfolio state |
| `active_trades.json` (+ `.lock`) | live | open trades as the API sees them |
| `daily_loss_breaker_state.json`, `loss_streak_breaker_state.json` | live (untracked) | breaker state — a reset here silently re-arms risk; must move verbatim |
| `forward_health.json`, `forward_reconciliation.jsonl`, `forward_signal_log.jsonl` | live | forward health/reconciliation |
| `execution_intents.json`, `control_audit.jsonl`, `advisory_log.jsonl`, `heartbeat.json`, `runtime_leases.json`, `slippage_log.json` | live | intents/audit/leases |
| `strategy_registry.json` | live | strategy authorization source (daemon reads it) |
| `paper_portfolio.json`, `paper_trade_ledger.jsonl`, `paper_equity_curve.jsonl`, `paper_runner_heartbeat.json` | live | paper-lab state (not live money) |
| `forward_daily_reports/` (untracked dir) | live | daily forward reports |
| `self_experiments_data/` (untracked dir) | live | self-experiment data |
| `quantdinger_audit.jsonl`, `progress_report.jsonl`, `testnet_balance_events.jsonl`, `testnet_trade_ledger.jsonl`, `testnet_baseline.json` | live | testnet/paper audit trail — move for continuity, do not reactivate |

**Do NOT move:** `__pycache__/` (regenerates), `venv/` / `venv312/`
(rebuilt from the lock on U1), `backtest_results/` and `backtest_data/`
(research artifacts — copy only if the coordinator wants them; they are
not runtime state), `.backups/` (S1-local backups).

**Freeze rule:** stop the daemon first, then the API, then snapshot. The
`.lock` files (`active_trades.json.lock`, `*.jsonl.lock`) prove writers were
running — a snapshot taken with the daemon up is not trustworthy. Copy
with checksums (`sha256sum` manifest on both ends) and verify counts
before starting anything on U1.

## 5. Credentials references (names and files only)

- `Stratex/.env` on S1 (7,366 B, mode 600) — the only live store; copy the
  file, preserve mode 600, never transcribe values.
- `/opt/friday_universe/CREDENTIALS.md` (Server 2) /
  `/opt/friday_universe/credentials.md` (Server 1) — credential references
  file; cited by path only, never opened for values in this task.
- Pepperstone Open API app 'Stratex Demo' (ID 49885) — coordinator-side
  retarget, 2026-11-21; the client id/secret/token live in `.env` under the
  §3a names.
- Oracle ADB `STRATEX` login password — inside the DSN value in `.env`;
  never separate, never logged.
- Telegram bot token / chat id — §3d names in `.env`.

## 6. Allowlists (three distinct meanings — do not conflate)

1. **Venue endpoint allowlist (code-enforced):**
   `demo.ctraderapi.com:5035` (Open API, hard-pinned),
   `demo.cfixapi.com:5212` (FIX default),
   `demo-api.binance.com` + `demo-fapi.binance.com` (Binance demo market
   data). U1 egress must reach these four hosts; nothing else needs
   outbound trading access. `live.ctraderapi.com` / `live.cfixapi.com`
   are refused by construction — the move must not "fix" that.
2. **Host firewall:** S1 UFW allows 22/80/443 only. U1's security group
   must mirror exactly that; 8003 stays localhost-only. No new inbound
   port for Stratex.
3. **Strategy allowlist:** `STRATEX_STRATEGY_ALLOWLIST` (env; empty = all
   strategies). Copy the value verbatim — a narrowed list on U1 would
   silently drop strategies.

## 7. Ingress — decision required (coordinator)

- Today: `friday-universe.duckdns.org/stratex` → S1 Caddy
  (`deploy/Caddyfile`: `handle_path /stratex*` → `127.0.0.1:8003`).
  FRIDAY and the mesh call Stratex through this public URL
  (`SYSTEM_MANIFEST.md`), so the public URL must keep working.
- **Recommended (not decided):** repoint S1 Caddy `/stratex*` to
  `U1-private-IP:8003` (private link or WireGuard/Tailscale — the fleet
  already uses Tailscale per the connectors list; confirm the S1↔U1 path).
  FRIDAY then needs no change, and U1 needs no public Caddy or DNS change.
  Alternatives: public Caddy on U1 + DNS cutover, or FRIDAY repointed to a
  U1 URL — both need coordinator sign-off and a FRIDAY env change.
- The daemon needs **no ingress** (outbound only). The scorecard timer
  needs no ingress. Do not expose 8003 publicly on U1 under any option.

## 8. U1 provisioning — open items (no repo source exists)

No `FRIDAY-Universe-1` / `Universe-1` reference exists in the repo at main
`9ef366a0` (code search: 0 hits); `Cortex/infra/terraform/` is a different
project's template ("Nexus", ECS/RDS, us-east-1) and is **not** the U1
provisioning. The VyralX U2 flip precedent lives in the coordinator's
workspace (`aws-migration/FLIP-RECORD.md`), not in the repo. Confirm with
the coordinator before provisioning:

- [ ] U1 identity: AWS account, region (U2 precedent: AWS Mumbai),
  instance type/size (S1 is an Oracle VM; size U1 to hold daemon 300M +
  API 180M + scorecard 256M + OS headroom — the S1 fleet runs all seven
  agents in ~2G; Stratex alone needs ≲1G plus the 1.7G venv312), AMI
  (Ubuntu 22.04), disk ≥ 30G (Stratex tree 111M + venv312 1.7G + growth).
- [ ] U1 network: security group = 22/80/443 in only (§6.2); private
  connectivity S1↔U1 for the Caddy repoint (§7); egress to the four venue
  hosts (§6.1), Oracle ADB, Telegram API, GitHub.
- [ ] U1 base: `git clone` at main (not S1's stale `03378ba4` checkout);
  `python3.12`; build `venv312` from `deploy/requirements-server1.lock`
  (do **not** reuse S1's venv by copy — build from the lock, then
  `pip check` must be clean; Stratex manifest is 23 reqs, 0 missing in
  live venv312 per TASK-REL-063).
- [ ] U1 units: install `Stratex.service` (venv312 form, from
  `deploy/setup_fleet.sh`), `Stratex-Daemon.service` (venv312 form, from
  `deploy/Stratex-Daemon.service`, **plus** the live env lines
  `TRADING_MODE=FUTURES` / `CTRADER_FIX_ENABLED=true` and the 300M cap —
  or the repo form, coordinator decision, see §2a), the scorecard
  service+timer (venv312 — repo form still says venv; flip it), and the
  `swapmax.conf` drop-in (192M) for the daemon. `Stratex-Testnet.service`
  stays masked.
- [ ] U1 env/state: copy `Stratex/.env` (mode 600) and the §4 state files
  with a `sha256sum` manifest; verify the copy before any start.
- [ ] U1 deploy user: `ubuntu`, working directory
  `/opt/friday_universe/Stratex`, `PYTHONPATH=/opt/friday_universe/Stratex:/opt/friday_universe`.

## 9. Cutover sequence (run only on hub clearance)

**Phase 0 — pre-freeze (U1 ready, S1 still primary):**

- [ ] U1 provisioned per §8; venv312 built from the lock; `pip check` clean.
- [ ] U1 egress verified: `demo.ctraderapi.com:5035`, `demo.cfixapi.com:5212`,
  `demo-api.binance.com`, `demo-fapi.binance.com`, Oracle ADB DSN connect,
  Telegram API, GitHub.
- [ ] Units installed on U1 but **not enabled/started**; `.env` + state NOT
  yet copied (or copied once as a dry-run snapshot, then re-copied at freeze).
- [ ] Ingress decision (§7) made and recorded on issue #35.
- [ ] Batch-B S1 venv312 flips resolved: the API repoint (Muse 3, cleared
  21:53 IST) and the daemon flip (LAST, calm window, separate clearance)
  are separate work — decide whether they land on S1 first or whether U1
  simply starts on venv312. Do not cut over mid-flip.
- [ ] Announce the freeze window on issue #35 (daemon + API both stop; the
  forward record pauses — no trades, no fills, no scorecard run during it).

**Phase 1 — freeze S1:**

- [ ] Stop the daemon FIRST (`systemctl stop Stratex-Daemon`), then the
  API (`systemctl stop Stratex`), then the scorecard timer
  (`systemctl stop stratex-forward-scorecard.timer`). Confirm all three
  inactive; confirm no `.lock` holder remains.
- [ ] Snapshot: `state/` + the §4 top-level files + `.env` (names only in
  the manifest); `sha256sum` manifest; record `daemon_heartbeat.json`
  timestamp, last fill-ledger line, last equity snapshot, scorecard
  `generated_at`, `active_trades.json` contents hash.

**Phase 2 — transfer:**

- [ ] Copy `.env` (mode 600 preserved) + state files to U1; verify
  `sha256sum` manifest matches on U1; verify file counts.
- [ ] Confirm on U1 (read-only): `.env` present and 600; state files
  present; `strategy_registry.json` identical; breaker states identical
  (a re-armed breaker is a silent risk change).

**Phase 3 — bring up U1:**

- [ ] Start the API on U1; `curl 127.0.0.1:8003/health` → 200; check
  `/health` reports the venv312 interpreter (3.12.16) and the same main
  commit as the U1 checkout.
- [ ] Start the daemon on U1; confirm `state/daemon_heartbeat.json` age
  < 60 s within two minutes; confirm strategy scans resume in the journal
  (same symbols/timeframes as S1 pre-freeze).
- [ ] Enable + start the scorecard timer; confirm the next 15-minute run
  regenerates `state/forward_scorecard.json` with a fresh `generated_at`
  and the same fill/equity inputs.
- [ ] Verify the forward record continues, not restarts: last fill-ledger
  line, equity snapshot count, and `active_trades.json` match the
  Phase-1 snapshot (plus only post-cutover activity).

**Phase 4 — switch ingress:**

- [ ] Repoint S1 Caddy `/stratex*` to U1 (§7 decision); `caddy reload`
  (or `oracle_caddy_reload`); verify `https://friday-universe.duckdns.org/stratex`
  answers from U1 (health + a read-only endpoint); verify FRIDAY's Stratex
  calls succeed end-to-end (FRIDAY snapshot gate sees a fresh daemon
  heartbeat).
- [ ] Verify Telegram summaries still arrive (bot token + chat id moved
  with `.env`).

**Phase 5 — soak and retire S1:**

- [ ] Soak: at least one full scorecard cycle + one daemon scan cycle +
  one supervised forward window on U1 with S1 units stopped but installed.
- [ ] Only after the coordinator declares U1 primary: disable (not
  delete) the S1 Stratex units; keep the S1 state snapshot as the rollback
  copy for one week.

**Rollback (at any phase before Phase 5):** stop U1 units, repoint Caddy
back to `127.0.0.1:8003`, restart S1 daemon then API, verify heartbeat +
health + scorecard. The S1 `.env` and state snapshot from Phase 1 are the
rollback source; never roll back from U1-written state without comparing
fill ledgers first.

## 10. Non-goals and holds

- No cutover in this task. No S1 service was stopped, restarted, or edited.
- No live trading: demo only (`ALLOW_LIVE_TRADING` unset/False; venue
  endpoints hard-pinned to demo). Pepperstone trading stays gated on the
  owner's Spotware authorization + shakedown (§3a).
- The S1 batch-B venv312 flips (API repoint, daemon LAST) are separate
  work with their own clearances; this checklist assumes U1 starts on
  venv312 regardless.
- `Stratex-Testnet.service` stays masked on both hosts.
- `docs/collaboration/S1_VENV_DRIFT_AUDIT.md` (TASK-REL-063) is the venv
  evidence base; re-run its `pip freeze`/`pip check` comparison on U1
  instead of trusting the S1 numbers.

## 11. Sources

- Repo at main `9ef366a0`: `deploy/Stratex-Daemon.service`,
  `deploy/Stratex-Testnet.service`,
  `deploy/stratex-forward-scorecard.{service,timer}`, `deploy/Caddyfile`,
  `deploy/setup_fleet.sh`, `deploy/requirements-server1.lock`,
  `DEPLOYMENT_GUIDE.md`, `Stratex/config.py`, `Stratex/dashboard.py`,
  `Stratex/autonomy/run_daemon.py`, `Stratex/exchanges/ctrader_openapi.py`,
  `Stratex/exchanges/ctrader_fix_adapter.py`,
  `Stratex/exchanges/pepperstone_ctrader_adapter.py`,
  `Stratex/scripts/update_cloud_demo_env.py`,
  `Stratex/scripts/pepperstone_shakedown.py`,
  `Stratex/notifications/telegram_bot.py`, `Stratex/security_hardening.py`,
  `Stratex/deployment/friday-stratex.service` (stale),
  `Stratex/SYSTEM_MANIFEST.md`, `docs/collaboration/S1_VENV_DRIFT_AUDIT.md`.
- Live S1 probes 2026-11-21 ~21:58–22:05 IST (bridge `oracle_check_service`
  `stratex` / `stratex-daemon`, `run_shell` server 1, `read_text` server 1).
- Board: `docs/collaboration/WORK_BOARD.yaml` (blob `c9fd231d`),
  TASK-STR-U1-001; issue #35 comments 7065396261 (assignment), 7065530801
  (PR #1230 superseded), 7065560289 (batch-B clearances).
