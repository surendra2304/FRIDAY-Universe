# Autonomy & Fleet Supervision Audit (TASK-ORCH-003)

**Date:** 2026-11-10 · **Auditor:** ZAI · **Question answered:** is FRIDAY's autonomous controller and fleet supervision verified — with defined authority, logging, limits and stop behavior — before any autonomy claim?

## 1. Verdict

**The supervision layer is verified and honest. The autonomy layer is correctly bounded but currently OFF by default, and no autonomy claim is justified beyond "owner-triggered, single-shot agent delegation".** Every autonomy surface is behind the owner control key (verified live: unauthenticated remote callers receive HTTP 401 on all of them — see TASK-VAL-002 evidence). Nothing in the fleet runs un-owned, open-ended work loops today except the two deliberate daemon units, which are interval-bounded and now crash-loop-visible (TASK-OBS-001).

## 2. Inventory of autonomy surfaces (authority · limits · logging · stop behavior)

| Surface | Authority | Limits | Logging | Stop behavior |
|---|---|---|---|---|
| `AutonomousController.execute_agent_control` — delegate a directive to an agent via mesh routing | Owner only (`POST /api/agents/control` behind `_require_control_access`) | `attempts=1` per dispatch; typed mesh actions; honest PENDING ≠ COMPLETED | every action appended to the action log (disk-backed, atomic writes, 50-entry cap) | per-dispatch; no loop |
| Autonomous goals queue + daemon (`/api/autonomous/goals`) | Owner only (verified 401 live) | daemon only runs while autonomous mode is ON; a submitted goal starts the worker explicitly (owner asked for work) | goal objects with status lifecycle | mode toggle OFF stops acceptance; goals bounded by queue semantics |
| **Autonomous mode toggle** | Owner only (`/api/autonomous/mode` behind control access) | **runtime-only** — a process restart returns to the config default (OFF); locked by test: a settings rebuild after `enabled=True` reads `autonomous_mode=False` | settings + controller log lines | OFF by default; restart = OFF |
| Orchestrator interactive loop | FRIDAY internal | turn budget 8 (TASK-ORCH-004), configurable, bounded | cognitive state machine trace | budget exhaustion ends the loop |
| Fleet supervision loop (`_fleet_supervision_loop`) | read-only polls of all 10 agents | interval-bounded; failed poll never fabricates status | `fleet_supervision_state.last_error` visible via status API | cancels with the app; `running` flag restored in `finally` |
| Memora event consumer loop | read/archive of untrusted notices | durable cursor, batched `has_more` draining, failure does not advance the cursor | `memora_event_state` + warnings | cancels with the app |
| Reflex loop | internal cognition | disabled unless `FRIDAY_REFLEX_ENABLED` | **stops on failure rather than spinning** (deliberate: a crashing brain must be visible, not silent) | exits on first internal failure |
| Autonomy mandates (`test_autonomy_mandate.py`) | owner-signed, scope-listed, time-limited, revocable mandates | scope/path/count/test-evidence limits enforced by signature | mandate ledger | expiry + revocation labels |
| Stratex-Daemon / VyralX-Daemon units | agent-side trading/media loops | interval-bounded batches (`--interval-hours 6`, batch size 1) | daemon logs | `systemctl stop`; crash loops now ALARM (fleet health watcher NRestarts delta, TASK-OBS-001) |

## 3. Verification performed (this session)

- **New guard tests — `FRIDAY/tests/test_fleet_supervision_loop_contracts.py` (8/8 green):**
  1. a failed poll sets `last_error` and **keeps the last good snapshot** (no fabricated liveness);
  2. a successful poll refreshes the snapshot and clears the error;
  3. the loop **survives a failed cycle and polls again** (2 polls observed after a crash);
  4. `running` flag is true only while alive and restored on cancellation;
  5. autonomy toggle is **runtime-only** — `enabled=True` does not survive a settings rebuild (simulated restart);
  6. `get_status()` reports `runtime_only` persistence and never claims auto-approval while off;
  7. toggle flips and reports truthfully;
  8. the controller's action history is disk-backed and **survives controller re-instantiation** (crash-safe audit trail).
- **Existing suites re-run (105 passed / 3 environmental):** autonomy mandate (owner-signed scopes, revocation, expiry), dangerous-API gating, diagnostics truth, mode source-of-truth, repair loop, think loop, advisory supervisor, task dispatch. The 3 failures are the known sandbox-environmental class (no fleet DNS in sandbox; verified unchanged by this session — none of this session's changes touch `FRIDAY/src`).
- **Live production evidence (2026-11-10, this session):** `GET /friday/api/agents/status` → 200 with real per-agent probe data (VAL-001 run); all three autonomous API endpoints (`/api/agents/control`, `/api/autonomous/goals`, `/api/autonomous/mode`) unreachable without the owner key (HTTP 401).

## 4. Honest limitations (what this audit does NOT claim)

1. **No long-horizon autonomy exists or is claimed**: goals queue is single-shot per goal; there is no planner that chains multi-day work. That is the correct posture per the Master Plan ("Expand independent task execution only after the core assistant works").
2. The action history is a bounded 50-entry ring on local disk — an audit trail, not a compliance-grade ledger; the ORCH-002 task-records store is the trackable substrate for real task work.
3. The daemons' autonomy is agent-internal; their output is not yet wired into the unified task records (candidate follow-up: `TASK-ORCH-005 backlog`).
4. Self-repair (`execute_self_repair`) is lock-guarded against concurrent runs but its effectiveness is not asserted by tests — it logs and reports honestly, which is what the truthfulness requirement demands.

## 5. What autonomy claims are therefore permitted

- ✅ "FRIDAY supervises the fleet continuously and reports failures honestly" — verified (supervision contracts + live status surface).
- ✅ "FRIDAY executes owner-requested agent tasks with one bounded attempt, records them, and reports truthful completion" — verified (controller + ORCH-002 records + M1 acceptance trace on production).
- ❌ NOT permitted: "FRIDAY works autonomously on its own goals" — mode is off by default, runtime-only, and untested in the on state end-to-end in production. Before flipping it on for real use, the M4 exit criteria for OBS-001 (active alerting on the servers) should be live so a runaway loop is visible.
