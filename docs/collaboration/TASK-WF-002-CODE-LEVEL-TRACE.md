# TASK-WF-002 — Code-level trace (interim leg): one end-to-end task across three agents

Filed: 2026-11-23 ~18:05 IST by Muse 14 (branch `muse14/task-wf-002-e2e-trace`, base main `7345f64a`).
Authority: coordinator hub watch 7100338636 (~17:28 IST, confirmed in push 7100469274 ~17:40 IST) —
"proceed with the CODE-LEVEL trace leg now (no live dispatch needed); the live leg waits for the
FRD-038 401 fix (Muse 11 claimed it, work started). File the code-level trace as the interim leg."

Scope of this leg: **code-level only. No live dispatch was attempted, no live agent endpoint was
called, no production credential was used.** Every claim below cites a file and line verified by
reading the clone at main `7345f64a`. Where the live app does not mount a module the docs
advertise, that is stated, not traced through as if it were live.

Baseline: WF-001 (2026-11-10) recorded 3 completed / 1 failed (Futuris 501); the owner browser
closure never happened. The live gate for this task is the same family of failure: VAL-009
(Muse 8, 2026-11-23 ~14:18 IST, `docs/collaboration/TASK-VAL-009-ROUTER-BUS-TRACE.md`) proved
the router→bus chain end to end in one shared store, but the Memora dispatch failed with
HTTP 401 "Invalid agent credentials", and the completion callback's receipt then disagreed
with the store. VAL-009 is on HOLD for the shared 401 fix (FRD-038, claimed by Muse 11,
branch `muse11/task-frd-038-webchat-401`, board record `TASK-FRD-038`, status CLAIMED).

## Task chosen

**"Weekly market briefing": produce one briefing for a topic (e.g. `BTCUSDT`) from three
specialist legs, aggregated in FRIDAY.**

| Leg | Agent | Action via the bus | What the leg must produce |
|-----|-------|--------------------|---------------------------|
| 1 | Memora | `query` (recall) — the exact VAL-009 call | Prior context / memories for the topic, with an `ActionReceipt` naming `memory_id`/`recalled_count` |
| 2 | Futuris | `forecast` | A calibrated forecast for the topic with a receipt |
| 3 | IntelX | `research_live` | A live-researched brief with citations, persisted as a durable run |

Why this task: leg 1 is the live gate itself (the VAL-009 failing call, so the trace re-uses a
call already proven to reach a real agent), legs 2 and 3 are the two other agents whose
`/v1/task/execute` handlers are reachable through the same bus, and the three legs together
cover memory, forecasting, and research — three distinct agents, one end-to-end purpose.
No other representative task was needed: the VAL-009 path supports all three legs through the
same intake → route → dispatch → receipt chain.

## The shared path (all three legs)

**Intake — FRIDAY live app.** `FRIDAY/src/friday/api/server.py` is the live application
(AGENTS.md: "The live application is `FRIDAY/src/friday/api/server.py`"). It mounts all three
pieces of the chain under `/api/v1`:

- `friday_core.agent_mesh_router` — `server.py:6521`, mounted `server.py:6529` (`/api/v1/mesh/*`).
- `friday_core.universe_dispatch_bus` — `server.py:6544`, mounted `server.py:6549` (`/api/v1/dispatch/*`).
- `friday_core.universe_task_router` — `server.py:6580`, mounted `server.py:6581` (`/api/v1/taskrouter/*`).

So the router→bus chain is genuinely mounted in the live app, not library-only. (Contrast
§"Not mounted" below.)

**Submit + route — UniverseTaskRouter.**
`POST /api/v1/taskrouter/tasks?description=…` with the capabilities list as the body creates
the task and a `submitted` record in the shared store
(`FRIDAY/apps/core/src/friday_core/universe_task_router.py:209-215`,
`submit_task` L108-121, store create L119-120).
`POST /api/v1/taskrouter/route/{task_id}` scores every registered agent
(`route_task` L122-172): capability match × 0.5 + load × 0.2 + success rate × 0.3
(L135-149), picks the best, records the assignment with rationale in the same shared store
(L166-169). Capabilities are loaded from the mesh registry at construction
(`_load_from_registry` L83-90, `mesh/registry.py:208-246`): Memora alone declares
`layered_recall` (`mesh/registry.py:56`), Futuris declares `probabilistic_forecasting`
(`mesh/registry.py:96`), IntelX declares `research` intent (`mesh/registry.py:85`) —
which is why VAL-009's `["layered_recall"]` routed to MEMORA at 0.94 live.
The router and the bus share ONE process-wide in-memory `TaskRecordStore`
(`FRIDAY/apps/core/src/friday_core/task_records.py:289-309`, `get_shared_task_records`;
wired into both engines at import time — router L199, bus
`FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py:631`).

**Dispatch — UniverseDispatchBus.**
`POST /api/v1/dispatch/send?agent=<Name>&action=<action>` with the payload as the body
(`universe_dispatch_bus.py:634-647`) calls `dispatch_async` (L380-408): it looks up the
agent config, creates a `disp_<hex>` envelope, records `submitted → dispatched` in the
shared store (`_record_dispatch_lifecycle` L294-302), POSTs real HTTP to
`{base_url}/v1/task/execute` (`_dispatch_http` L339-378, `_build_action_url` L210-215,
`_request_payload` L225-245 — note `priority` is stringified, L238, because Cortex
validates priority as a string), then records the receipt outcome in the store
(`_record_dispatch_outcome` L317-337). Registered bases
(`_register_default_agents` L148-194, deployed layout per VAL-006): Memora
`http://10.0.0.121:8002`, Futuris `http://10.0.0.120:8004`, IntelX `http://10.0.0.120:8005`.
Credentials come only from env (`FRIDAY_DISPATCH_<NAME>_API_KEY`, default header
`x-api-key`, L175-180); `_headers` (L218-223) sends **only** that header plus an optional
`FRIDAY_DISPATCH_<NAME>_EXTRA_HEADER` — notably, the bus never sends `X-Agent-Name`
unless the extra header is configured. Retries: 3 (max_retries, L339-378); a 404 is not
retried; anything else (including 401) is retried with backoff, then a `failed` receipt
is recorded. Circuit opens after 3 consecutive failures (`_record_failure` L288-292) and
then `dispatch`/`dispatch_async` raise 503 until manually reset (L383-386, L413-416,
`reset_circuit` L490-497).

**Receipt vs record — the two views.** `_receipt_for_response` (L247-280): HTTP 202, or a
200 whose body status is `accepted`/`queued`/`pending`/`running`, yields an `accepted`
receipt; a 200 otherwise yields `completed`; anything else yields no receipt (failure).
`_record_dispatch_outcome` (L317-337): only `completed` maps to a `completed` store record;
`accepted` **deliberately leaves the record at `dispatched`** — "recording completion would
fabricate success". The async loop is closed only by the agent (or owner) POSTing
`/api/v1/dispatch/completions` (`record_agent_completion` L499-561, route L701-719):
unknown `task_id` → 404, non-terminal status → 422, and — the VAL-009 divergence, now
explained in code — if the store record is already terminal (`completed`/`failed`/
`routing_failed`), the callback's outcome is **not** written to the store (L540-556:
`if record.status not in terminal:` guards the update), while the in-memory receipt IS
overwritten (L536-548). So a `completed` callback on an already-`failed` dispatch makes
`GET /dispatch/receipts/{id}` say `completed` while `GET /dispatch/records/report` still
says `failed`. See silent-failure risk S1.

**Aggregation — where the three legs come together.** There is no live aggregator that
combines three legs into one briefing. The bus only records per-leg receipts
(`get_receipt` L569-583, `get_task_records_report` L563-567, route
`/dispatch/records/report` L721-725). The VAL-009 probe read the same three surfaces
(`records/report`, `dispatch/receipts/{id}`, `/api/tasks/timeline`, `/api/agents/live`).
Synthesis into one answer happens in the FRIDAY chat/agent loop, not in the bus.
See §"Not mounted" — the in-process orchestrator that does aggregate multi-agent
workflows is not reachable from the live app.

## Per-leg trace

### Leg 1 — Memora recall (the VAL-009 call; the live gate)

| Step | Code |
|------|------|
| Request | `POST /friday/api/v1/dispatch/send?agent=Memora&action=query`, body `{"query": "<topic>", "limit": 1}` → bus `dispatch_async` (`universe_dispatch_bus.py:380`) → `POST http://10.0.0.121:8002/v1/task/execute` with envelope `{task_id, agent: "Memora", action: "query", payload, priority: "100", timeout_sec, source_agent: "FRIDAY"}` (`_request_payload` L225-245). |
| Routing | Task router capability scoring (`universe_task_router.py:122-172`); `layered_recall` is Memora-only in the registry (`mesh/registry.py:56`). Proven live by VAL-009: `layered_recall` → MEMORA at 0.94. |
| Agent entry | `Memora/apps/api/routers/v1_task.py:195-232` (`execute_task`, mounted via `Memora/apps/api/main.py:334` as `v1_task_router`). `action=query` is in `_QUERY_ACTIONS` (L29); `_execute_query` (L322-...) runs `SearchService.hybrid_search` with the policy gate and returns `{"count", "memories", "query"}`. On SUCCESS a receipt is attached (`_receipt_for` L113-153) with `verification_evidence` carrying `recalled_count`, `query`, backend/durability — the evidence the caller needs, not just a summary. |
| Auth (the gate) | The route depends on `get_actor_header` (`v1_task.py:199`), i.e. `authenticate_agent` (`Memora/apps/api/dependencies.py:182-196, 300-363`). It reads `X-Agent-Name` + `X-API-Key`/`Authorization: Bearer`, looks up the expected key by agent name in `AGENT_API_KEY_ENV_VARS` (L15-27: `"friday": "FRIDAY_API_KEY"`), and hmac-compares (L356). No credential at all → 401 `"Missing agent credentials"` (L345-348). Wrong credential → 401 `"Invalid agent credentials"` (L356, L363). **The VAL-009 probe got the second string**, which proves a credential *was* presented and rejected — consistent with the bus sending its configured `x-api-key` value while Memora resolves the expected key from the agent name, which the bus only sends if `FRIDAY_DISPATCH_MEMORA_EXTRA_HEADER="X-Agent-Name: FRIDAY"` is set (bus L189-194 gives exactly that example). The live leg must therefore check the deployed pair on Server 1: the extra header, and whether `FRIDAY_DISPATCH_MEMORA_API_KEY` equals Memora's `FRIDAY_API_KEY`. |
| Evidence if it ran | `TaskResultModel` with `status: "SUCCESS"`, `result.count`, `result.memories[]` (id, content, score), plus `receipt.verification_evidence` (`recalled_count`, `query`, `backend`, `durable`). The bus would record a `completed` receipt and a `completed` store record. |
| Result today (code-level) | Would fail at auth exactly as VAL-009 proved live (401, 3,154 ms round trip, retried 3×, `failed` receipt, store record `failed`). No code change in this leg alters that; the fix is FRD-038 (Muse 11). |
| Silent-failure risk | None in the failure itself — the 401 is loud (failed receipt + failed record). The silent risk is S1 (callback divergence) if anyone "completes" this dispatch by callback afterwards. |

### Leg 2 — Futuris forecast

| Step | Code |
|------|------|
| Request | `POST /friday/api/v1/dispatch/send?agent=Futuris&action=forecast`, body `{"target": "<topic>", "horizon": "24h"}` → bus → `POST http://10.0.0.120:8004/v1/task/execute`. |
| Routing | Task router scoring; `probabilistic_forecasting` is Futuris-only (`mesh/registry.py:96`). (The mesh router `agent_mesh_router.py` would also pick Futuris for `forecast` capability — `route_task` L~100-140 — but its scores are static defaults; see S5.) |
| Agent entry | `Futuris/futuris/api/app.py:356-357` — `/v1/task/execute` (and `/api/v1/task/execute`) **exists but is a documented refusal stub**: it returns the health payload only for `status`/`health`/`ping`/`report`/`supervision_status`, and for every other action — including `forecast` — raises **HTTP 501** with "The generic task endpoint has no evidence-backed handler configured. No forecast was run and no result was produced. Use the authenticated forecast API with timestamped telemetry." This is the same Futuris 501 the WF-001 baseline recorded in 2026-11-10. |
| Evidence if it ran | None through this route. A real forecast lives elsewhere: `POST /forecast` and `POST /v1/forecast` (`Futuris/futuris/api/app.py:658-659`, `quick_forecast` — statsforecast pipeline, persists a `Forecast` row, returns prediction + 90% range + `evidence_class`), and the `/api/v1/futuris/forecast/*` routers (`Futuris/predict/forecasting_engine.py:329-390`). But the bus **cannot target them**: `action_path` is fixed to `/v1/task/execute` with no `{action}` placeholder (`universe_dispatch_bus.py:181-182, 210-215`), and the action travels only inside the envelope body. |
| Result today (code-level) | Deterministic 501 → bus retries 3× → `failed` receipt, `failed` store record, and after 3 consecutive failures the Futuris circuit opens (bus L288-292) and later dispatches 503 until manually reset. Loud failure, not silent — but the leg **cannot complete through the bus at all** until a real handler is wired behind Futuris `/v1/task/execute` (or the bus gains a per-agent action path). The live leg must not claim a Futuris forecast from this route. |
| Silent-failure risk | S6 (circuit): a stale open circuit after the 501s could 503 a later, fixed Futuris dispatch and look like Futuris being down. Also S2/S7 do not apply here (no 202/accepted path). |

### Leg 3 — IntelX live research

| Step | Code |
|------|------|
| Request | `POST /friday/api/v1/dispatch/send?agent=IntelX&action=research_live`, body `{"topic": "<topic>"}` → bus → `POST http://10.0.0.120:8005/v1/task/execute`. (Timeout: the bus default is 30 s; the fleet client uses 115 s for `research_live` — `FRIDAY/src/friday/ecosystem/fleet_client.py:1797-1800` — so a live `research_live` via the bus should pass an explicit `timeout_sec` ≥ 115.) |
| Routing | Task router scoring; IntelX declares the `research` intent (`mesh/registry.py:85`) and the `web_crawling`/`document_synthesis` capabilities (`mesh/registry.py:83`). |
| Agent entry | `IntelX/intelx/api/router.py:105-106` — `/v1/task/execute`, auth `get_friday_api_key`. `action=research_live` (L~140-190) validates the query (5–1000 chars), refuses `MOCK_MODE` with 503, runs the real scout/retrieve/synthesis pipeline (`run_live_research` + `synthesize_grounded`), persists the run durably (`persist_live_research`, `research_recall` L~190-210 retrieves it verbatim later), and returns an envelope with a receipt. Unknown/other actions fall through to the legacy research path or 422/404. |
| Auth | `IntelX/intelx/core/auth.py:338-390` (`get_friday_api_key`): accepts `Authorization: Bearer <key>` **or** `X-API-Key: <key>`, enforces 50 req/hour (429), then hash-matches the key against the `ApiKey` table (env-seeded integration keys). The bus sends `X-API-Key` by default (header `x-api-key`, bus L175-180) — shape-compatible. Whether it authenticates live depends on `FRIDAY_DISPATCH_INTELX_API_KEY` matching a seeded, unrevoked IntelX key; that is a live-leg check, not decidable from code. |
| Evidence if it ran | Envelope with `status`, `result` (brief + citations), `receipt` (with `verification_evidence`, `durable_run: true`, `run_id`), persisted run retrievable via `research_recall`. The bus would record `completed`. |
| Result today (code-level) | Traces cleanly end to end through the bus; no code-level blocker found. The live outcome (200 vs 401 vs 429) is unproven until the live leg runs. |
| Silent-failure risk | S2/S7 if IntelX ever answered 202 or a 200 with a `running` status (it does not today — `research_live` awaits the pipeline inline); S3 (in-memory store) applies to the record of the result. |

## The second live route (not the traced path, named for the live leg)

The FRIDAY agent loop also has a second dispatch path that bypasses the bus:
`FRIDAY/src/friday/cognition/mesh.py` — `Mesh.dispatch` (L985-1080) with per-peer
contracts (`build_contracts` L341-476: memora L362-373, intelx L388-400, futuris L400-412;
bearer for Memora/IntelX, `x-api-key` for Futuris), strict receipt verification
(`verify_receipt` L705-792: no receipt → `UNVERIFIED`; wrong action/target → `UNVERIFIED`;
401/403 → `REFUSED` L1140-1152; 202 → `PENDING`), fallback paths on 404/405
(`_try_fallback` L1187+), and `dispatch_many` (L1323-1340) for fan-out. The fleet client
(`FRIDAY/src/friday/ecosystem/fleet_client.py:1749-1800`) posts the same
`/v1/task/execute` URLs with per-agent headers (Memora: `Bearer` + `X-Agent-Name`,
L1766; IntelX: `Bearer`, L1797; Futuris: `X-API-Key`, L1804). The trace uses the bus
path because VAL-009 proved it live; the live leg may use either, but must record
which one, since their failure semantics differ (bus: `failed` receipt + retries;
mesh: classified `PeerOutcome` + receipt verification).

## Not mounted — do not trace through these as if live

- **`friday_core.universe_orchestrator` / `DeepWorkflowEngine`** is the module that
  actually aggregates multi-agent work (`run_full_trading_workflow`:
  Stratex sentiment → order flow → patterns → **Futuris forecast** → stress test, with
  harness verification and memory commit —
  `FRIDAY/apps/core/src/friday_core/universe_orchestrator.py:280-360`). But
  `FRIDAY/src/friday/api/server.py` never imports it (verified by grep: no match), and
  it runs its engines **in-process** via `importlib` (`universe_orchestrator.py:29-56`),
  not over HTTP — so it is not the live multi-agent path and its workflows cannot be
  the "one end-to-end task" for WF-002.
- **`friday_core.agent_runtime` `/v1/agent/*`** (`agent_runtime.py:450`, routes
  L453-502: capabilities, plan, execute, context/compact, browser/run, trace) is
  mounted only in `friday_core.real_deep_api_server.py:47,56` — **not** in the live
  `server.py` (verified by grep: no match). AGENTS.md's "mounted as `/v1/agent/*`"
  does not hold for the live app at this commit. Its `FridayAgentRuntime`
  (`recall_context` L234-238, `verify` L304-306, `commit_memory` L358-361) is the
  aggregation/verification machinery the orchestrator workflows use in-process.
- **`friday_core.agent_mesh_router`** IS mounted (`server.py:6529`), but it is a
  second, separate router from the task router: its registrations are static defaults
  (`agent_mesh_router.py:199-208`), its scores use hardcoded `success_rate 0.5` /
  `current_load 0.0`, and nothing in the live path feeds dispatch outcomes back into
  it. Two routers, one of which never learns. See S5.

## Silent-failure risks found (code-level)

- **S1 — Callback/receipt vs store divergence (VAL-009 finding, mechanism now pinned).**
  `universe_dispatch_bus.py:499-561`: `record_agent_completion` overwrites the receipt
  but skips the store update when the record is already terminal (L540-556). A
  `completed` callback on a failed dispatch makes the receipts endpoint and the records
  report disagree; the callback is trusted, never verified against the dispatch
  outcome. Any live-leg read-back must check BOTH surfaces and treat disagreement as
  a finding, not a pass.
- **S2 — `accepted` is a parking lot.** An `accepted` receipt leaves the store record
  at `dispatched` forever unless the agent calls back (bus L317-337). Nothing polls,
  times out, or reaps an accepted task. A peer that queues work and then drops it is
  invisible except in the receipts list.
- **S3 — The trace store is in-memory and dies with the process.**
  `task_records.py` header + `get_shared_task_records` (L289-309): "In-memory only, by
  design". A FRIDAY restart between dispatch and read-back wipes the whole trace
  (VAL-009 noted the same). The evidence doc is the durable record.
- **S4 — Router and bus records are not linked.** Two records (`task_<hex>` and
  `disp_<hex>`) in one store, no foreign key (VAL-009 doc, "Chain semantics"). The
  "chain" is procedural (one probe, one window, both ids in one report) plus this
  trace file. Also the agent name differs by case (`MEMORA` vs `Memora`), so
  `by_agent` counts split one agent into two (VAL-009 step 5).
- **S5 — Routing never learns.** The mesh router's scores are static defaults and the
  task router's `success_rate` defaults to 0.8 and is never updated from dispatch
  outcomes (`universe_task_router.py:92-100`, `update_load` L102-106 is never called
  from the live path). A repeatedly failing agent keeps winning routes on capability
  match alone.
- **S6 — Futuris circuit breaker can outlive the fix.** Three consecutive 501s open
  the Futuris circuit (bus L288-292); afterwards every Futuris dispatch 503s until a
  manual `POST /dispatch/agents/Futuris/reset` (L687-693). A stale open circuit after
  the Futuris handler is fixed would masquerade as Futuris being down.
- **S7 — A 200 with `status: "running"` is filed as `accepted`, then forgotten.**
  `_receipt_for_response` (bus L265-275) maps any 200 with a pending-ish body status
  to `accepted`; combined with S2, a peer that reports `running` and never finishes
  leaves a permanently `dispatched` record with no alarm.
- **S8 — No timeout on the accepted leg.** The bus's per-attempt timeout covers the
  HTTP call only; there is no deadline by which an accepted task must complete or be
  declared failed.

## Verdict — code-level leg only

The code-level trace is **complete and filed**, with two of three legs traceable end to
end and one leg (Futuris) proven **uncompletable through the traced route**:

- Leg 1 (Memora): fully wired; the only blocker is the credential mismatch FRD-038
  owns. The 401 mechanism is pinned in code (§Leg 1, Auth).
- Leg 2 (Futuris): **cannot complete via the dispatch bus** — `/v1/task/execute` is a
  501 refusal stub for every real action; the real forecast API is unreachable from
  the bus's fixed action path. This is a code finding, not a live flake, and it
  reproduces the WF-001 Futuris 501.
- Leg 3 (IntelX): fully wired; no code-level blocker; live outcome unproven.

The acceptance ("one fresh end-to-end task runs across at least three agents … and no
silent failure") is **not met by this leg alone** — it cannot be, by design: no live
dispatch ran, no leg produced a result, and the Futuris leg cannot produce one through
this route at all. What this leg does meet is the coordinator's interim order: the
complete static trace, every silent-failure risk named with file/line, and the exact
live-leg remainder below.

## Live-leg remainder (what the live dispatch must still prove, once the FRD-038 401 fix lands)

1. **Memora leg (after FRD-038):** re-run the VAL-009 call
   (`POST /friday/api/v1/dispatch/send?agent=Memora&action=query`, sentinel query) and
   confirm a `completed` receipt **and** a `completed` store record with a receipt whose
   `verification_evidence.recalled_count` matches the returned memories. Check the
   deployed Server 1 env pair first: `FRIDAY_DISPATCH_MEMORA_EXTRA_HEADER` (must name
   the agent) and `FRIDAY_DISPATCH_MEMORA_API_KEY` vs Memora's `FRIDAY_API_KEY`.
   This also re-proves VAL-009's acceptance.
2. **Futuris leg:** do NOT re-run `action=forecast` through the bus and expect a
   forecast — the 501 is deterministic. Either (a) a real handler is wired behind
   Futuris `/v1/task/execute` first (a code change, then re-probe), or (b) the live
   leg dispatches the forecast through the real `POST /v1/forecast` route and records
   explicitly that it bypassed the bus. If (a), reset the Futuris circuit first
   (S6) — a stale open circuit will 503 the re-probe. Record which option was taken;
   do not silently substitute (b) for the bus path.
3. **IntelX leg:** run `action=research_live` through the bus with `timeout_sec` ≥ 115,
   confirm a `completed` receipt with `receipt.verification_evidence`, `durable_run:
   true`, and a `run_id` retrievable via `research_recall`. If it 401s, the
   `FRIDAY_DISPATCH_INTELX_API_KEY` does not match a seeded IntelX key — that is a
   second credential finding, not a reason to re-target the leg.
4. **Aggregation:** there is no live aggregator; the live leg must assemble the
   briefing from the three receipts + the shared-store report itself, and record the
   three `disp_` ids, the three receipts, and the store report in the trace. Check
   BOTH the receipts endpoint and the records report for every leg (S1) and treat any
   disagreement as a failed leg, not a pass.
5. **Silent-failure watch:** after the run, verify no leg is left at `dispatched`
   (S2/S7/S8) and no circuit is left open (S6); record the final store report
   verbatim. If FRIDAY restarts mid-run, the in-memory store is wiped (S3) — the
   run must be re-done in one session, as VAL-009 was.

— Muse 14, 2026-11-23 ~18:05 IST
