# TASK-VAL-009 — router↔bus TaskRecord correlation, live probe trace

Filed: 2026-11-23 ~14:20 IST by Muse 8 (branch `muse8/task-val-009`).
Probe design: `~/workspace/muse8/val-009/PROBE_DESIGN.md` (local working copy).
Clearance: coordinator watch comment 7095390023 (2026-11-23 ~13:37–14:15 IST) —
live dispatch leg granted (read-only recall dispatch to Memora, no writes on
Memora). Sequencing answer in the same watch: (a) finish VAL-009 first, then
claim OBS-014; the OBS-014 nudge from watch 7094281062 is withdrawn.

## Verdict — ACCEPTANCE NOT MET (reported plainly)

The router→bus chain is proven end to end in ONE shared store, and the
completion callback is shown. But the dispatched recall did NOT complete:
Memora's `/v1/task/execute` rejected the bus's call with HTTP 401
"Invalid agent credentials". The TaskRecord therefore ends **failed**, not
completed, and the acceptance ("one real dispatched task shows the full
chain: router id, bus dispatch id, completion callback") is not met as
written. A second finding: the completion callback's receipt claims
`completed` while the shared store still records the dispatch as `failed`
— receipt and store disagree (see step 5).

No retry was taken: the 401 is deterministic ("Invalid agent credentials",
full 3.1 s round trip), and it is the same shared 401 gate the coordinator
is already investigating (watch 7095390023: FRIDAY web-chat 401 blocks
Muse 11 MEM-017, Muse 10 FRD-037, Muse 7 confirms the regression;
coordinator investigation owed; "do not work around it silently"). The
probe was not re-targeted at another agent — that would change what the
probe proves. Next step: hold VAL-009 open, re-probe after the 401 fix
lands, or Muse re-scopes the acceptance. The async
accepted→callback→completed transition still needs separate clearance, as
noted in the design.

## Environment (verified this run, before the probe)

- Public ingress `https://friday-universe.duckdns.org`, base path `/friday`.
- Bridge `get_system_info` (~14:17 IST): Oracle Server 2 (10.0.0.120),
  workspace `/opt/friday_universe`, checkout branch
  `muse10/task-mem-023-three-section-proof-run2` @ `6e2b3ffd`, both Oracle
  servers ONLINE. (Checkout moved since the 13:16 baseline, which was
  `ca2c586f`; the three wiring files below are byte-identical, so the live
  wiring is the same code.)
- Wiring files on the deployed checkout (bridge `list_directory`,
  `FRIDAY/apps/core/src/friday_core/`): `task_records.py` 13,528 bytes,
  `universe_task_router.py` 8,844 bytes, `universe_dispatch_bus.py`
  29,658 bytes — exact match with the repo and with the 13:16 verification.
- Live read-only baseline re-verified 14:16 IST:
  `GET /friday/api/v1/dispatch/records/report` → 200,
  `{"enabled":true,"total":0,...}` — store empty, so every record below is
  unambiguously the probe's.
- The store is IN-MEMORY: all steps ran in one session, 14:18–14:19 IST.
  A FRIDAY restart between steps would have wiped it; none occurred
  (total went 0 → 2 monotonically across the read-back).

## Step 1 — submit (14:18:24 IST)

`POST /friday/api/v1/taskrouter/tasks?description=VAL-009%20probe%3A%20Memora%20read-only%20recall`
body `["layered_recall"]` → HTTP 200

```json
{"task_id":"task_b9f56ce22f6c","priority":5}
```

Note: the first attempt sent description + capabilities as a JSON body and
got HTTP 422 — the endpoint takes `description` as a query parameter and
the body as the capabilities list. Retried in that shape; the 422 created
no record (baseline total stayed 0 until step 1 succeeded).

## Step 2 — route (14:18:29 IST)

`POST /friday/api/v1/taskrouter/route/task_b9f56ce22f6c` → HTTP 200

```json
{"task_id":"task_b9f56ce22f6c","assigned_agent":"MEMORA","confidence":0.94,"alternatives":["FRIDAY","INFERENCE"]}
```

Routed to MEMORA at 0.94, exactly as the design predicted
(`layered_recall` is Memora-only).

## Step 3 — dispatch, live leg (14:18:35 IST)

`POST /friday/api/v1/dispatch/send?agent=Memora&action=query`
body `{"query": "VAL-009-probe-1795423697-bd2baa36", "limit": 1}` → HTTP 200
(receipt; the dispatch itself failed)

```json
{"task_id":"disp_2ed5e1717a66","agent":"Memora","status":"failed","latency_ms":3153.7396907806396,"result":"","error":"HTTP 401: {\"detail\":\"Invalid agent credentials\",\"error\":\"http_401\",\"message\":\"Invalid agent credentials\",\"success\":false}"}
```

A real HTTP call was made to Memora's `/v1/task/execute` (3,154 ms round
trip) and Memora's auth layer rejected the bus's credentials. The recall
never ran. The sentinel phrase is unique to this probe, so no other
record can be confused with it.

## Step 4 — completion callback (14:19:00 IST)

`POST /friday/api/v1/dispatch/completions?task_id=disp_2ed5e1717a66&status=completed&result=VAL-009%20probe%20callback`
→ HTTP 200

```json
{"task_id":"disp_2ed5e1717a66","agent":"Memora","status":"completed","result":"VAL-009 probe callback","error":"","recorded_via":"agent_completion_callback"}
```

The callback was accepted. Note it reports `completed` for a dispatch
whose underlying call failed — the callback is trusted, not verified
against the dispatch outcome (see the divergence in step 5).

## Step 5 — read-back (~14:19:30 IST)

`GET /friday/api/v1/dispatch/records/report` → 200

```json
{"enabled":true,"total":2,"by_status":{"submitted":0,"assigned":1,"dispatched":0,"completed":0,"failed":1,"routing_failed":0},"by_agent":{"MEMORA":1,"Memora":1},"unassigned":0}
```

Both records are in the ONE shared store: `task_b9f56ce22f6c` assigned
(owner MEMORA) and `disp_2ed5e1717a66` failed (agent Memora). Note the
case difference is real: router records owner `MEMORA` (registry name),
bus records agent `Memora` (config key) — same agent, as the design
predicted.

`GET /friday/api/v1/dispatch/receipts/disp_2ed5e1717a66` → 200

```json
{"task_id":"disp_2ed5e1717a66","agent":"Memora","status":"completed","result":"VAL-009 probe callback","latency_ms":25068.806648254395,"completed_at":1795423742.6477268,"error":""}
```

**DIVERGENCE (finding):** the receipts endpoint says `completed` (the
callback's view) while the records report, the timeline, and agents/live
all say the same dispatch is `failed`. The completion callback did not
update the TaskRecord in the shared store — it wrote a receipt that
disagrees with the store. (Also noted, not interpreted: the receipt's
`latency_ms` grew from 3,153.7 at dispatch time to 25,068.8 at read-back.)

`GET /friday/api/tasks/timeline` → 200, `total_records: 2`:

- `disp_2ed5e1717a66` — "Dispatch query to Memora", owner Memora,
  status `failed`, chip `failed`, `history_len: 3`, error = the HTTP 401
  above, created 2026-11-23T08:48:37Z, updated 08:48:40Z.
- `task_b9f56ce22f6c` — "VAL-009 probe: Memora read-only recall", owner
  MEMORA, status `assigned`, chip `queued`, `history_len: 2`, created
  2026-11-23T08:48:26Z, updated 08:48:30Z.

`GET /friday/api/agents/live` → 200, `ledger_total: 2`,
`in_flight_count: 0`. Memora `ONLINE` (latency 24 ms) with
`last_outcome: {task_id: disp_2ed5e1717a66, status: failed,
at: 2026-11-23T08:48:40Z}`. Memora is up; only the dispatch credentials
are rejected.

`GET /friday/api/v1/taskrouter/report` → 200:
`{"total_agents":10,"total_tasks":1,"total_routes":1,"routed_tasks":1,"engine_status":"operational"}`.

## What the probe proves, and what it does not

Proven:

- Router and bus share ONE TaskRecord store live: both records appear in
  the same records report, timeline, and agents/live ledger.
- `layered_recall` routes to Memora at 0.94 as designed.
- The bus performs a real HTTP dispatch to Memora and records the receipt
  (success or failure) in the shared store.
- The completion callback endpoint accepts a callback and records it
  (`recorded_via: agent_completion_callback`).

Not proven:

- No completed recall: the dispatch failed on the shared 401 gate, so no
  successful end-to-end chain exists yet.
- The callback's `completed` receipt does not move the store record — the
  two views diverge on a failed dispatch. Whether the callback is meant
  to update the store record is a code question for the re-probe (read
  `universe_dispatch_bus.py` around the completions handler).
- The accepted→callback→completed transition on a synchronously
  completing dispatch was not observable (design limitation, unchanged);
  it needs an async target and separate clearance.

## Chain semantics (unchanged from the design)

The router record (`task_b9f56ce22f6c`) and the bus record
(`disp_2ed5e1717a66`) are TWO records in ONE store; there is no foreign
key between them in code. The "chain" is procedural: one probe, one agent,
one time window, both ids in the same store report — plus this trace
tying them together. Nothing here claims a code-level link that does not
exist.

— Muse 8, 2026-11-23 ~14:20 IST
