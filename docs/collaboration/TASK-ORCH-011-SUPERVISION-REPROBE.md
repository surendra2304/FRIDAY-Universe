# TASK-ORCH-011 — Fleet Supervision Re-probe (TASK-ORCH-003 follow-up)

**Date:** 2026-11-22 · **Worker:** Muse 9 · **Task:** re-verify TASK-ORCH-003
(autonomous controller + fleet supervision), MASTER_PLAN §6 STALE-UNVERIFIED
follow-up · **Scope:** read-only — no autonomy enable, no controller change,
no supervision-flag flip. Nothing was changed on any server.

## 1. Verdict

**The supervision loop is alive and honest. The fleet picture it reports is
stale in four places. And autonomy is ON in production — the ORCH-003 posture
("OFF by default, untested in the on state") no longer describes the live
system.**

- Supervision loop: running, snapshot 29 s old at probe time, `last_error`
  null, 5-minute interval. It reports failure honestly (see §4).
- Code default for autonomy is still OFF (`config.py:213`, `default=False`),
  verified — but the live FRIDAY process has `autonomous_mode=true` AND
  `full_access_mode=true` (confirmed twice, 11:43 and 11:52 IST). The daemon
  is armed and heartbeating, idle (0 queued, 0 running). Cause: the standing
  production env flag `FRIDAY_AUTONOMOUS_MODE=true` + the TASK-FRD-023
  boot-arm (`server.py:637-641`), which starts the daemon at boot whenever
  the flag is set. The 11:15 IST restart re-armed it. See gap G3 — this
  needs a coordinator decision, not a worker toggle.
- Guard tests: **8/8 pass** on Server 1, 27.32 s, 2026-11-22 ~11:55 IST
  (`/tmp/orch011_pytest.log` on Server 1).
- Deployed code byte-identical to main for all four supervision-relevant
  files (sha256, §5).

## 2. Controller + autonomy default (source, main)

| Check | File:line | Result |
|---|---|---|
| `autonomous_mode` default OFF | `FRIDAY/src/friday/core/config.py:213-216` | `Field(default=False, "Enable owner-requested actions without confirmation prompts; disabled by default.")` |
| `full_access_mode` default OFF | `FRIDAY/src/friday/core/config.py:218-222` | `Field(default=False, ...)` |
| Toggle is runtime-only | `FRIDAY/src/friday/autonomous/controller.py:275-289` | `enabled` property reads/writes the shared runtime setting; `get_status()` reports `"autonomous_mode_persistence": "runtime_only"` (`:305`) |
| Env flag arms the daemon at boot (TASK-FRD-023) | `FRIDAY/src/friday/api/server.py:637-641` | `if get_settings().autonomous_mode: await autonomous_daemon.start()` — "Until this block existed … `FRIDAY_AUTONOMOUS_MODE=true` in the environment armed nothing" |
| Settings read the flag from env | `FRIDAY/src/friday/core/config.py:76-79` | `env_prefix="FRIDAY_"` — so `FRIDAY_AUTONOMOUS_MODE=true` in the service environment sets the mode at every boot |
| Audit doc unchanged since 2026-11-10 | `docs/autonomy/AUTONOMY_AUDIT_2026-11-10.md` | Still the 2026-11-10 audit; no edit since. Its §5 condition ("before flipping it on … OBS-001 alerting should be live") is now overtaken by events — see G3 |

Caveat on the runtime-only guard test: `test_enabling_autonomy_does_not_survive_a_settings_rebuild`
passes because the test env sets `FRIDAY_AUTONOMOUS_MODE=false`
(`FRIDAY/tests/conftest.py:98`). In production the flag is set (documented
in `FRIDAY/tests/test_autonomous_daemon_arm.py:7-13`: "The owner's standing
flag `FRIDAY_AUTONOMOUS_MODE=true` was set in production"), so a restart
restores ON, not OFF. The test pins the no-env-flag case only.

## 3. Guard tests re-run (live, Server 1 venv)

- Command (Server 1, `/opt/friday_universe/FRIDAY`):
  `/opt/friday_universe/venv/bin/python -m pytest tests/test_fleet_supervision_loop_contracts.py -q -p no:cacheprovider`
- Result: **8 passed in 27.32 s** (log `/tmp/orch011_pytest.log` on Server 1).
  The 8 are the ORCH-003 contracts: failed poll keeps last snapshot +
  `last_error`; successful poll refreshes + clears error; loop survives a
  failed cycle; `running` flag lifecycle; toggle runtime-only; status reports
  `runtime_only` and no auto-approval while off; toggle flips truthfully;
  disk-backed action history survives re-instantiation.
- Note: an earlier bridge `run_workspace_test` attempt ran the whole-repo
  suite and failed collection on an unrelated Futuris test
  (`DATABASE_URL is not configured` on the bridge host) — environmental,
  not a test failure. The targeted re-run above is the evidence.

## 4. Live state (2026-11-22, 11:43–11:55 IST)

### 4.1 FRIDAY process

- `FRIDAY.service` (Server 1): active (running) since 11:15:20 IST;
  systemd "Scheduled restart job, restart counter is at 1" — previous
  process (PID 2008492, handling live chat turns until ~10:28 IST) exited
  11:15:11 IST. Restart cause unverified from the journal window read.
- `GET /friday/health`: 200, `overall: healthy`, process liveness only,
  observed 11:42 IST.
- `GET /friday/api/autonomous/status` (11:43 and 11:52 IST, identical):
  `{"autonomous_mode": true, "full_access_mode": true,
  "sensitive_actions_auto_approved": true,
  "autonomous_mode_persistence": "runtime_only", "active_agent": null,
  "active_directive": null, "history_count": 50, ...}`.
  No `Autonomous Mode changed to:` toggle line appears in the 400-line
  journal window — consistent with env-driven (not toggle-driven) mode.
  Daemon heartbeats every ~5 min: "Autonomous daemon alive: 0 queued,
  0 running" (11:15:54, 11:20:56, 11:26:02, 11:31:07, 11:41:13 IST);
  "Autonomous daemon started" 11:15:53 IST, immediately after the restart.
  The 50-entry action-history ring is full; newest sampled entries are
  old (Memora 2026-11-08, Stratex 2026-11-18, self-repair 2026-11-14) —
  no autonomous goal work is executing.

### 4.2 Supervision loop

- `GET /friday/api/agents/supervision` 11:52 IST (`06:22:33Z`):
  `status: degraded`, `checked_at: 2026-11-22T06:22:33.706669+00:00`,
  `snapshot_age_seconds: 29`, `interval_seconds: 300`,
  `last_error: null`, `agent_count: 9`.
  The loop is running and its snapshot is fresh; "degraded" is because not
  all 9 peers report ONLINE, not because the loop is down.
- `GET /friday/api/agents/status` 06:13:20Z: `degraded`, 5 ONLINE
  (Inference, Memora, Stratex, Cortex, Forge) / 4 UNREACHABLE (IntelX,
  Futuris, Sentinel, VyralX). 06:22:33Z sweep: 3 ONLINE / 2 DEGRADED
  (Stratex, Forge — probe `ReadTimeout` at ~10–11.7 s) / 4 UNREACHABLE.
  Stratex and Forge flap ONLINE↔DEGRADED sweep to sweep — the known
  TASK-REL-023 pattern (FRIDAY event-loop stall on the swap-loaded 956 MB
  host, not peer death). Both directly verified alive (§4.3).

### 4.3 The 4 "UNREACHABLE" agents are alive — probe targets are stale

| Agent | FRIDAY probes | Running copy actually at | Direct evidence (this session) |
|---|---|---|---|
| IntelX | `127.0.0.1:8005` (Server 1, masked copy) | Server 2 `10.0.0.120:8005` | Unit active since Nov 20 23:56 IST; `:8005` listening; `/health` 200 `mock_mode: false`; watch cycles logged 11:33 IST |
| Futuris | `127.0.0.1:8004` (Server 1, masked copy) | Server 2 `10.0.0.120:8004` | Unit active since Nov 21 20:12 IST; `:8004` listening; `/health` 200, storage 13/13 present |
| Sentinel | `10.0.0.120:8008` (Server 2, masked copy) | Server 1 `10.0.0.121:8008` | `/health` 200, `kill_switch_active: false`, `audit_chain_valid: true`; `/ready` READY, database connected (oracle), 13 modules active |
| VyralX | `10.0.0.120:8010` (Server 2, masked copy, stopped Nov 19 16:21 IST) | AWS Sydney (per fleet 6/4 layout) | **Not verified in this re-probe** — no AWS endpoint was probed; supervision has a blind spot for the AWS leg |

The masked Server 1 copies of IntelX (failed Nov 20 23:56 IST, timeout,
signal KILL) and Futuris (inactive/dead), and the masked Server 2 copies of
Sentinel (graceful shutdown Nov 20 23:45 IST) and VyralX (stopped Nov 19
16:21 IST) are the sleeping copies of the 6/4 layout — their masked state
is expected. What is wrong is that FRIDAY probes the sleeping copies
instead of the running ones.

- Cross-checks: Inference/Memora/Cortex ONLINE in both sweeps; Forge
  `/health` 200, uptime 47238 s, `database_connected: true` (11:53 IST);
  Stratex `/health` 200, engine online, `DEMO_ENVIRONMENT` (Binance
  Futures testnet + OANDA practice), daemon balance 10555.64 (11:53 IST).
- Inconsistency between supervision surfaces: the FRIDAY agent-watch log
  line 11:26:25 IST reports `checked: 10, healthy: 10, delivered: False`
  (`below_bar`, gate held) while `/agents/status` at the same period
  reports degraded. Which surface is authoritative is undocumented.

### 4.4 Memora event consumer

- `memora_event_consumer`: `running: true`, `last_completed_at:
  2026-11-22T06:22:52Z` (fresh) — but `last_result: {"status": "error",
  "stage": "cursor", "error": "HTTPError"}`. Journal shows the same
  failure repeating (11:31, 11:39, 11:40, 11:41 IST): "Memora cursor read
  failed (HTTPError/URLError)" / "Memora event consumption did not
  complete". The loop is alive; every observed cycle fails at the cursor
  read. Memora itself is ONLINE (`/health` 200).

## 5. Deployed code vs main (sha256, Server 1 `/opt/friday_universe`)

| File | sha256 (Server 1 == local main checkout) |
|---|---|
| `FRIDAY/src/friday/api/server.py` | `74fc07d20e78119f9769a14bd9ec20b3d3c39644e3c8f5d8be355972f9764c45` |
| `FRIDAY/src/friday/autonomous/controller.py` | `0907d381b432dac27bcb8fb9dc18324afd540f224d2bc5fd905b415b8c304da9` |
| `FRIDAY/src/friday/core/config.py` | `27f890576f7fd3f933edbd66a5b2860097c7ad55bfe21b9a77a3460498bfb22f` |
| `FRIDAY/tests/test_fleet_supervision_loop_contracts.py` | `be64b5a2ee1b82a701f2bfc8ab69c50e4f4ccd820b36b595b5d8c2caad024b60` |

No changes to these four files between the claim base (`c212cfe`) and
current main (`a5ca76a`). Local clone history is grafted at `2943852`
(2026-11-21), so no tree diff against the 2026-11-10 audit tree was
possible from git history; verification is against current main + live
state, not a historical diff.

## 6. Gaps filed (file/line; no controller change in this task)

- **G1 — Supervision probe targets encode the old layout, not the live
  6/4 split.** `FRIDAY/src/friday/ecosystem/fleet_client.py:117-125`
  (`CANONICAL_INTERNAL_MESH_URLS`: IntelX/Futuris → `10.0.0.121`,
  Sentinel → `10.0.0.120`) plus the env override in `configured_url()`
  (`:237-255`, `FRIDAY_<AGENT>_URL`); live probes use `127.0.0.1` for
  Server-1 agents. Result: 4 agents permanently UNREACHABLE in
  `/api/agents/status` while alive elsewhere. Follow-up: re-point the
  probe targets at the running copies (IntelX/Futuris → Server 2,
  Sentinel → Server 1, VyralX → AWS endpoint or an explicit
  not-probed-here marker) or make them layout-aware.
- **G2 — Memora event consumer fails at the cursor on every observed
  cycle.** `FRIDAY/src/friday/api/server.py:222-239` loop /
  `memora_event_state` (exposed at `/api/agents/supervision`); consumer
  `friday-cloud`. Live `last_result` error/cursor/HTTPError; journal
  11:31–11:41 IST. Follow-up: diagnose the Memora cursor endpoint
  (`/health` 200 does not cover it).
- **G3 — Autonomy is ON in production via the standing env flag; the
  ORCH-003 "NOT permitted" posture needs a coordinator decision.**
  `FRIDAY/src/friday/core/config.py:213` (default OFF — intact) vs the
  standing `FRIDAY_AUTONOMOUS_MODE=true` in the service environment and
  the FRD-023 boot-arm (`FRIDAY/src/friday/api/server.py:637-641`).
  `full_access_mode` is also true live, so
  `sensitive_actions_auto_approved` is true. The audit's §5 precondition
  (OBS-001 alerting live before flipping on) is arguably now met —
  TASK-OBS-008 (Muse 7, today 11:33 IST) confirmed timer enablement on
  both servers and one alert proven end-to-end via drill — but the flip
  itself was never recorded as a decision. No action taken here (read-only
  task): either the flag is intentional and the audit posture should be
  updated, or the flag should be removed. Needs Muse's call.
- **G4 — Stratex/Forge probe flapping on timeouts (known REL-023
  pattern, still present).** `FRIDAY/src/friday/ecosystem/fleet_client.py:126-141`
  (probe budgets; per-probe up to 8–10 s, sweep deadline 20 s). Sweeps
  flip ONLINE↔DEGRADED on `ReadTimeout`; direct curls answer in ≤0.25 s.
  Follow-up already tracked under REL-023; no new action proposed.
- **G5 — VyralX AWS leg is a supervision blind spot.**
  `FRIDAY/src/friday/ecosystem/fleet_client.py:125`
  (`vyralx: http://10.0.0.120:8010` — the masked Server 2 copy). The
  running copy is on AWS Sydney; nothing probes it and this re-probe
  could not verify it. Follow-up: probe the AWS endpoint or record
  VyralX as explicitly out of scope for this supervision loop.
- **G6 (minor) — Two supervision surfaces disagree.**
  Agent-watch log 11:26:25 IST: 10/10 healthy; `/api/agents/status`:
  degraded. `FRIDAY/src/friday/api/server.py:1802-1869`
  (`/api/agents/status`, `/api/agents/supervision`). Follow-up: document
  which surface is authoritative, or reconcile them.

## 7. Acceptance

- [x] Supervision state re-probed (controller + guard tests + live state)
  with a recorded verdict — this document.
- [~] "Autonomy still OFF by default, verified, not assumed" — **code
  default verified OFF; live process is ON via the standing env flag
  (G3). Reported plainly, not as a pass.**
- [x] Supervision gaps filed with file/line (G1–G6 above).
- [x] No controller change in this task — no setting, flag, or service
  was modified; all probes were read-only GETs / status reads / test runs.

## 8. Evidence log (this session, 2026-11-22 IST)

- 10:59 — Claim PR #1321 merged (merge `e66b6fcd`); board CLAIMED on main.
- 11:38 — Hourly self-check found the stall: no work commits ~40 min
  after claim merge; repaired in this run (this re-probe).
- 11:41 — `oracle_fleet_health`: Server 1 up 39 d 23 h, load 4.65;
  Server 2 up 30 d 17 h, load 0.00. (Server 1 is the swap-loaded host
  behind the REL-023 probe stalls.)
- 11:42 — FRIDAY `/health` 200, healthy.
- 11:43 / 11:52 — `/api/autonomous/status`: mode true, full-access true
  (twice).
- 11:43 — `/api/agents/status` 06:13:20Z: 5 ONLINE / 4 UNREACHABLE.
- 11:44–11:50 — Service states: IntelX/Futuris masked on Server 1,
  active on Server 2; Sentinel/VyralX masked on Server 2; Sentinel alive
  on Server 1 (`/health` 200, `/ready` READY); IntelX/Futuris `/health`
  200 on Server 2.
- 11:52 — `/api/agents/supervision` 06:22:33Z: age 29 s, `last_error`
  null; Memora consumer error/cursor/HTTPError.
- 11:53 — Forge `/health` 200 (uptime 47238 s, DB connected); Stratex
  `/health` 200 (engine online, demo env).
- ~11:55 — Guard tests 8/8 pass, 27.32 s, Server 1 venv.
- Bridge limits hit: `run_workspace_test` ignores its path arg (runs the
  whole repo; collection fails on Futuris `DATABASE_URL` on the bridge
  host); bridge `run_shell` client read-timeout is 60 s — long commands
  must be launched detached (`setsid … &`) and their logs read back.

— Muse 9
