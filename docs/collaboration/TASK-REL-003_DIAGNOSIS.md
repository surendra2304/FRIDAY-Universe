# TASK-REL-003 — Stratex engine offline: diagnosis

**Owner:** Muse 7 · **Status:** diagnosis only (read-only) · **Date:** 2026-11-22 ~09:30 IST
**Assignment:** coordinator watch comment 7072956811 (~08:00 IST, pool 4 item 8) ·
**Claim:** issue #35 comment 7073237609 · **Claim PR:** #1300 (merged 08:46 IST, 1c3e7962)
**Scope:** read-only diagnosis. No service restarted, no file edited on any server,
no trade placed, no config changed. Demo-only fail-closed guard (D-015 /
`ALLOW_LIVE_TRADING`) untouched.

## Verdict in one paragraph

The November-14 defect reading was real but it measured the **wrong engine**.
The legacy spot-testnet worker (`bb_reversion` + factory winners, 16 symbols)
had not evaluated a strategy since ~2 Nov, was restarted 14 Nov 13:04 UTC, ran
8.5 h, and stopped 14 Nov 21:31 UTC — it has been dead ever since
(`testnet_heartbeat.json` frozen, pid 2503927 gone). The engine that actually
trades in the current FUTURES configuration is the **multi-venue daemon**
(`Stratex/autonomy/run_daemon.py`, Binance Futures testnet + OANDA practice,
30 symbols). It is alive now: last strategy evaluation 33 s before the final
read, ~2,310 strategy evaluations per ~60–80 s scan cycle, 30 open positions.
`/stratex/health` reports `engine_healthy: true` today because, in FUTURES
mode, the dashboard takes the daemon heartbeat as the only engine witness and
clears the stale-testnet reasons. So: **the defect as filed is TRUE of the
legacy testnet worker (dead) and FALSE of the live FUTURES engine (healthy).**
No engine repair was needed or made; the repair still owed is retirement of
the dead worker's heartbeat from the health path (see §5), which is a Muse
decision, not part of this read-only task.

## 1. The defect as filed (2026-11-14 07:07 UTC probe)

From the board record and MASTER_PLAN §3:

- `/stratex/health`: `engine: "offline"`, `engine_healthy: false`
- `STALE_STRATEGY_EVALUATION: last evaluation 1039907s ago` (≈12.0 days,
  so last evaluation ≈ 2 Nov ~07:00 UTC), threshold 900 s
- `daemon_balance: null`, `open_positions: null`
- The process still answered `/health` 200 (process liveness only)

## 2. Live evidence, this run (2026-11-22 ~09:27–09:32 IST / 03:57–04:02 UTC)

### 2.1 Public probe — engine healthy now

`GET https://friday-universe.duckdns.org/stratex/health` → 200,
observed `2026-11-22T03:57:36Z`:

```json
{"status": "ok", "service": "stratex", "version": "2.2.0",
 "engine": "online", "engine_healthy": true,
 "engine_source": "multi_venue_daemon", "engine_trading_capable": true,
 "capability_reasons": [],
 "capability_warnings": ["DEMO_ENVIRONMENT: execution venues are Binance Futures testnet and OANDA practice"],
 "daemon_balance": 10559.78499871, "open_positions": 30,
 "unrealized_pnl": 102.19, "mode": "FUTURES",
 "environment": "multi_venue_testnet_practice",
 "evidence_class": "process_liveness"}
```

(`GET /stratex/ready` timed out from the bridge probe; not retried — the
diagnosis does not depend on it. Limitation, not a finding.)

### 2.2 Daemon heartbeat — fresh, evaluating, every cycle

`Stratex/state/daemon_heartbeat.json` on Server 1, read 04:02:06Z
(daemon pid 1977654, alive, elapsed 1:47:12):

```json
{"status": "RUNNING", "pid": 1977654, "timestamp": "2026-11-22T04:02:06Z",
 "scan_count": 82, "scan_interval_seconds": 15.0,
 "last_strategy_evaluation": "2026-11-22T04:01:36Z",
 "last_cycle": {"scanned": 2310, "signals": 22, "executed": 0, "errors": 0,
                "symbols": 30, "symbols_1d": 30},
 "total_balance": 10560.10, "total_equity": 10661.59,
 "unrealized_pnl": 101.49, "realized_pnl": 151.62, "open_positions": 30,
 "venues": ["binance_futures"]}
```

- Last evaluation 33 s old at read time (threshold 900 s). Previous read
  03:58:23Z: `scan_count` 78, last evaluation 03:57:41Z (42 s old) — the
  heartbeat advances every cycle, ~56–80 s per cycle, 2,310 evaluations each.
- Daemon journal (`Stratex-Daemon.service`) shows live strategy evaluation
  lines seconds before each read (e.g. 09:27:11 IST: `strategy_ha_trend_*`
  on `binance_futures:NEARUSDT 4h: SIGNAL - BUY`).

### 2.3 Services — both running, clean deploy restart 07:44 IST today

| Unit | State | Since | PID |
|---|---|---|---|
| `Stratex.service` (dashboard.py) | active (running), enabled | 07:44:41 IST | 1977513 |
| `Stratex-Daemon.service` (run_daemon.py) | active (running), enabled | 07:44:57 IST | 1977654 |

- `NRestarts=0`, `Result=success` for both; VM up 38 d 22 h (no reboot).
- Both units were actively evaluating seconds before the stop (daemon pid
  1933051 logging evaluations 07:43:42; dashboard pid 1932912 logging
  07:43:31) and resumed cleanly after. Trigger was the automated deploy:
  GitHub push webhooks hit `/api/deploy/github` 07:40–07:44 IST and Server 1
  is on `ef42312f` (merge PR #1303). No crash signature.
- `heartbeat.json` (paper runner) fresh 09:26 IST; `paper_runner_heartbeat.json`
  `RUNNING`, pid 1977513, started `2026-11-22T02:15:20Z`.

### 2.4 Legacy testnet worker — dead since 14 Nov 21:31 UTC

`Stratex/testnet_heartbeat.json` on Server 1, mtime 2026-11-15 03:01 IST,
contents frozen:

```json
{"worker_alive": false, "status": "STOPPED", "pid": 2503927,
 "timestamp": "2026-11-14T21:31:34.747351Z", "mode": "TESTNET",
 "binance_connected": true, "websocket_connected": true,
 "strategy": "bb_reversion",
 "strategies": ["bb_reversion", "factory_winner_1", "factory_winner_2",
                "factory_winner_3", "factory_winner_4", "factory_winner_5"],
 "timeframes": ["15m", "1h", "5m"],
 "symbols": ["BTCUSDT", "ETHUSDT", ... 16 symbols],
 "last_market_update": "2026-11-14T21:31:34Z",
 "last_candle_close": "2026-11-14T21:31:03Z",
 "last_strategy_evaluation": "2026-11-14T21:31:03Z",
 "service_start_time": "2026-11-14T13:04:10Z",
 "current_equity": 4978.19, "open_positions": 0}
```

- `ps -p 2503927`: no such process. Dead 7 d 12 h at diagnosis time.
- Timeline: last evaluation ≈ 2 Nov (per the 14 Nov probe's 1,039,907 s) →
  restarted 14 Nov 13:04 UTC (after the defect was filed; ~8.5 h of life) →
  stopped 14 Nov 21:31 UTC, never wrote again.

### 2.5 Daemon activity before today — on-disk record starts 14 Nov

- `state/equity_snapshots.jsonl` (749 lines): first entry
  `2026-11-14T12:36:52Z`, `engine: "daemon"`, hourly; entries present every
  day 14–22 Nov. No daemon snapshot in this file before 14 Nov.
- `state/fill_ledger.jsonl`: daemon fills 14 Nov (9), 16 Nov (3),
  17 Nov (3), 19 Nov (32), 20 Nov (12), 21 Nov (18).
- `state/forward_scorecard.json`: `global_forward_start`
  `2026-11-15T11:29:49+05:30`.
- So the daemon is evidenced as active from 14 Nov 12:36 UTC — about
  5.5 h **after** the defect probe. At probe time it either was not running
  or was not yet producing snapshots; the retained evidence cannot
  distinguish those two.

## 3. Code path — why the endpoint says healthy now

`Stratex/dashboard.py`, `get_engine_health_data()` (main, 6,838 lines):

1. Reads `testnet_heartbeat.json` (or `TESTNET_HEARTBEAT_FILE`). With the
   frozen file: `worker_alive` false, heartbeat age huge,
   `capability_reasons = ["STALE_STRATEGY_EVALUATION: last evaluation …s ago (>900s)"]`
   — the exact Nov-14 signature, still computed today.
2. In FUTURES mode (`config.TRADING_MODE == "FUTURES"`), if not
   trading-capable, it consults `_multi_venue_daemon_snapshot()`:
   `state/daemon_heartbeat.json` via `daemon_book.read_daemon_heartbeat`
   (600 s max age **plus** a live-pid check — "a daemon killed moments ago
   is not resurrected by a merely-recent file"). A fresh snapshot sets
   `is_healthy = True`, `engine_status = "ONLINE"`,
   `trading_capable = True`, and **clears `capability_reasons` to `[]`**.
3. `/stratex/health` returns `_health_payload("process_liveness")`, which
   exposes `engine_healthy`, `daemon_balance`, `open_positions` — but **not**
   `last_strategy_evaluation`, `heartbeat_age_seconds`, or
   `daemon_last_evaluation`. Freshness is only implied (non-null daemon
   balance/positions prove a <600 s daemon heartbeat); it is not shown.

The Nov-14 probe response (`daemon_balance: null`, `open_positions: null`)
shows no daemon snapshot was returned then. The current code's FUTURES-mode
override is what makes the same endpoint read healthy today.

## 4. Root cause

1. **Proximate cause of the Nov-14 reading:** the health endpoint's engine
   witness was the legacy spot-testnet worker, which had stopped evaluating
   ~2 Nov and was never healthy again. The endpoint correctly reported what
   it measured; it measured the wrong (superseded) engine.
2. **Why the legacy worker died ~2 Nov, and why it died again 14 Nov
   21:31 UTC after being restarted 13:04 UTC: UNDETERMINED from retained
   evidence.** The systemd journal on Server 1 only retains back to
   22 Nov 07:30 IST; no error lines survive for the 14 Nov 21:00–22:00
   window, and no daemon journal survives from 2–14 Nov. The restart-then-
   die-within-8.5 h pattern suggests it was already failing, but that is an
   inference, not evidence.
3. **Why the defect persisted as a board item after the daemon took over:**
   the defect was filed against the endpoint output, and nobody re-probed
   after the FUTURES-mode daemon became the live engine; the frozen
   `testnet_heartbeat.json` kept the stale reading computable by the same
   code path, so the item looked open.

## 5. Residual risk and recommended repair (Muse decision — NOT done here)

1. **Retire the legacy testnet worker explicitly.** Remove
   `testnet_heartbeat.json` from the health path (delete the frozen file and
   stop whatever would rewrite it) and record the multi-venue daemon as the
   sole engine witness. Until then, any consumer reading
   `testnet_heartbeat.json` directly sees a dead worker, and the health
   function still computes — then silently clears — a stale-evaluation reason.
2. **Surface freshness in `/stratex/health`.** Add `daemon_last_evaluation`
   age (or `heartbeat_age_seconds`) to `_health_payload`, so readiness is
   shown, not implied by non-null balance/positions.
3. **Do NOT restart the legacy worker.** It trades different venues and
   strategies (spot testnet, `bb_reversion`) from the live engine (Binance
   Futures testnet + OANDA practice) and died twice; reviving it would run
   two engines. If spot-testnet coverage is ever wanted again, that is a new
   task with its own cause found first.
4. **Journal retention** (observation, not a repair): the 8-day hole that
   makes §4.2 undeterminable is a retention setting, not a mystery — if
   future diagnoses need >8 days of service logs, retention must be raised
   before the evidence ages out.

## 6. Acceptance mapping

- *Root cause identified and recorded with evidence before any change* —
  this document (§§2–4). No change has been made.
- *Repair restores strategy evaluation freshness (<900 s) on the demo
  configuration, verified by live probe* — **already true for the live
  engine**: last daemon evaluation 33 s old at the final read; `/stratex/health`
  `engine_healthy: true` (probe §2.1). What remains is the retirement/cleanup
  in §5.1–5.2, which changes the health path and therefore needs Muse's call.
- *No trading-behaviour changes; D-015 / ALLOW_LIVE_TRADING untouched* —
  none made. All probes were reads (`get_system_info`, service checks,
  journal reads, file reads, public GETs).

## 7. Evidence index (all read-only)

- Bridge v1.30.0, `get_system_info`: both Oracle servers ONLINE.
- `/stratex/health` probe 2026-11-22T03:57:36Z (full body §2.1).
- `Stratex/state/daemon_heartbeat.json` reads 03:58:23Z and 04:02:06Z (§2.2).
- `oracle_check_service` stratex / stratex-daemon, 09:25–09:27 IST.
- `Stratex/testnet_heartbeat.json`, `heartbeat.json`,
  `paper_runner_heartbeat.json` (Server 1, §2.3–2.4).
- `Stratex/state/{equity_snapshots.jsonl, fill_ledger.jsonl,
  forward_scorecard.json}` date histograms (§2.5).
- `Stratex/dashboard.py` (main, 6,838 lines): `get_engine_health_data()`,
  `_multi_venue_daemon_snapshot()`, `_health_payload()` (§3).
- Board record: TASK-REL-003 CLAIMED, owner muse_7, on main 436fb43a
  (blob 3bca8d7c, 13,597 lines) before this work; main has since moved to
  db754a4b (PR #1306).
- Limitations: journal retained only from 22 Nov 07:30 IST (no Nov 2–14
  service logs); `/stratex/ready` probe timed out from the bridge; no
  Telegram message-id style confirmation applies (no alert sent).
