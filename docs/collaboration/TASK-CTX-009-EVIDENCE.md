# TASK-CTX-009 — Checkpoint 1: forced-breach live verification (wave 3)

Claim: hub #2045 comment 7226806426. Branch `muse10/task-ctx-009-budget-gate-live-verify`
from main `dbaf142a`. Board: AVAILABLE / owner muse_10 / P1 (WATCH234 §C assignment,
queued behind EARN-040 per WATCH235; EARN-040 merged as PR #2183, merge `dbaf142a`).

Acceptance item: live extreme-condition verification of TASK-IG2-COR-01 — real dispatch
through the live Cortex path on Oracle Server 1 with the budget gate active + a forced
budget breach producing exactly one owner alert; the C-01 wiring gap (no production
caller / persistence / alert dispatch) closed or proven absent. All verified live
this run, 2026-11-28 ~01:30–02:00 IST (UTC 2026-11-27 ~19:52–20:00).

## 1. Live service (baseline)

- Cortex on Oracle Server 1: `active (running)` since Tue 2026-11-24 19:34:23 IST,
  PID 3771939, `uvicorn apps.api.src.cortex_api.main:app --host 0.0.0.0 --port 8009`,
  35.6M / 200M. `GET /health` 200 (`cortex` v2.1.0).
- Baseline `GET /api/v1/cortex/budgets` (UTC day 2026-11-27): all 10 agents
  `tokens_used 0, tasks_used 0, paused false`. Alerts: 1 (Cortex, 2026-11-17,
  the COR-010 drill). Deliveries: 1 (same date, `telegram:api.telegram.org`,
  `delivered true`, status 200). Store: `database, durable true, load_errors 0,
  save_errors 0, last_error null` — the COR-012 durable-store fix holds.
- Note: `Cortex.service` on Server 2 is masked/inactive — expected, Cortex runs
  on Server 1. (S2 shared checkout sits on branch
  `musetp13/task-frd-046-checkpoint-2`; noted, not this task's to fix.)

## 2. Real dispatch through the live Cortex path

- `POST /v1/task/execute` (Universal Task Protocol, S1 loopback `:8009`,
  FRIDAY service key loaded server-side from the running Cortex process env):
  envelope `ctx009-dispatch-1`, `recommend_intervention` on `site_storefront`,
  proposed `banner_injection`, confidence 0.92 → HTTP 200,
  `status/state WAITING_APPROVAL`, recommendation `rec_0388d56365`,
  `requires_approval true`, 1358 ms. Recommendation is not authorization —
  nothing was executed. Receipt null (correct: receipts attach only on
  COMPLETED/SUCCESS).
- Gate charge confirmed: Cortex `tasks_used 0 → 1` (`tasks_remaining 749`) in the
  ledger immediately after the dispatch. The executor (`friday_router.py`
  §2b) charges every non-exempt envelope to the Cortex line.

## 3. Forced budget breach — exactly one owner alert

- `POST /api/v1/cortex/budgets/usage {"agent":"Cortex","tokens":750001,"tasks":1}`
  → HTTP 429, `reason token_budget_exceeded`, `paused true`. The breaching usage
  was NOT recorded (`tokens_used` stays 0).
- Post-breach `GET /api/v1/cortex/budgets`: Cortex `paused true`. Alerts: exactly
  one NEW alert, date 2026-11-27, `token_budget_exceeded`, `tasks_used 1`.
  Deliveries: exactly one NEW delivery, `at 2026-11-27T19:56:18.499204+00:00`,
  `channel telegram:api.telegram.org`, `delivered true`, `detail delivered`,
  `status_code 200`. (Prior totals were 1/1 from the 2026-11-17 drill; now 2/2.)
- The owner alert fired once, through the Telegram channel fixed by TASK-COR-010.
  No duplicate, no silent drop.

## 4. Recovery — service restored

- `POST /api/v1/cortex/budgets/Cortex/reset` → HTTP 200: Cortex `paused false`,
  usage cleared (`tokens_used 0, tasks_used 0, tasks_remaining 750`).
- Alerts and deliveries persist after reset (2/2) — the breach evidence stays in
  the durable ledger. Store still `database, durable true, 0 errors`.
- Dispatch task `ctx009-dispatch-1` cancelled (`POST /v1/task/execute`, action
  `cancel`) → HTTP 200, `state CANCELLED`. No dangling WAITING_APPROVAL task left.

## 5. C-01 wiring gap — proven absent

- Production caller: `process_task_envelope` charges the Cortex line (dispatch
  above moved `tasks_used` 0 → 1).
- Persistence: `DatabaseBudgetStore` (`agent_budget_state`), durable true, 0
  errors; the 2026-11-17 alert survived the Nov 24 Cortex restart and is still
  listed.
- Alert dispatch: `WebhookBreachAlertSink` → `SELF_HEALING_ESCALATION_WEBHOOK`
  → Telegram sendMessage, `delivered true`, HTTP 200, once per agent per day.

## Five states

- implemented YES (COR-01 code, merged) / tested YES (live, this run) /
  merged YES / deployed YES (live on S1) / production-verified YES (this run).
- No item failed live; no fix task owed.

— Muse 10
