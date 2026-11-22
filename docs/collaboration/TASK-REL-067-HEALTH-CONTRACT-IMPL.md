# TASK-REL-067 — Health-Capability Contract Implementation (WORK IN PROGRESS)

**Task:** Implement the health-capability contract per REL-004 section 8
(design: `docs/collaboration/TASK-REL-004-HEALTH-CONTRACT.md`, Muse 9).
**Branch:** `muse8/task-rel-067`. **Status:** Stratex + FRIDAY classifier +
FRIDAY /health + Memora /health + Futuris /health + IntelX /health slices
implemented on the branch; 5 agents' `/health` remain. **Work PR not opened yet** — this
document grows with the work and is filed with the work PR.

## Done this run (2026-11-22 ~15:00 IST, hourly self-check)

Stratex is the reference implementation (design §5: every contract field
already exists in its `/health` body; the work is a derivation, not a probe).

- `Stratex/dashboard.py` — `_stratex_capability_report()` derives the
  §2.2 report: `capabilities.trading_engine` (required; heartbeat ≤ 90 s +
  worker RUNNING + PID alive, including the PAPER-mode and FUTURES-daemon
  alternate witnesses), `capabilities.trading_capable` (required; engine
  healthy + ≥ 1 executable strategy + evaluation fresh ≤ 900 s + no panic /
  kill-switch), `capabilities.market_data` (required; `binance_connected` +
  `websocket_connected` — **default fixed: omitted flags now report
  `unknown` with detail `MARKET_DATA_NOT_REPORTED`, never default True**),
  `dependencies.database` (required; live Oracle `SELECT 1 FROM DUAL`, the
  same probe `/ready` already ran). Top-level `status` is derived (`ok`
  iff every required capability/dependency is `ok`, else `degraded`);
  HTTP is 200 iff `ok`, else 503. `evidence_class` on `/health` is now
  `capability_report`. All pre-existing fields are kept. No secret or raw
  exception text is placed in any detail: `READ_ERROR: <exc>` is mapped to
  the stable code `ENGINE_PROBE_FAILED`; other reason codes are
  `HEARTBEAT_FILE_MISSING`, `ENGINE_OFFLINE`, `PANIC_ACTIVE`,
  `KILL_SWITCH_LOCKED`, `MARKET_DATA_DISCONNECTED`,
  `DATABASE_UNCONFIGURED`, `DATABASE_UNREACHABLE`, plus the existing
  `STALE_STRATEGY_EVALUATION` / `NO_EXECUTABLE_STRATEGY` /
  `NO_STRATEGY_EVALUATION` codes.
- `/ready` unchanged in behaviour: it now consumes the probe
  `_health_payload` already ran (design §2.5) instead of re-probing; the
  ready gate, production gate, payload fields and HTTP codes are identical.
  `/ready`'s payload additionally carries the capabilities block (additive).
- `Stratex/Dockerfile` — HEALTHCHECK moved from `/health` to `/ready`
  (design §2.5/§7: `/health` 503 means "degraded", not "dead").
- `Stratex/tests/test_engine_capability_truthfulness.py` — the old test
  asserting `/health` stays 200 for an inert engine is updated to the
  contract (503, `degraded`, `trading_capable` unavailable,
  `NO_EXECUTABLE_STRATEGY`); two tests added: the TASK-REL-003 condition
  (engine offline + stale evaluation → 503, `trading_engine` /
  `trading_capable` unavailable, `STALE_STRATEGY_EVALUATION`) and the
  capable-engine ok path (200, all capabilities `ok`, DB probe stubbed).

## Probe-routing verification (§7 prerequisite, Stratex)

- `deploy/Caddyfile`: the Stratex `reverse_proxy` block sets no
  `health_uri` — Caddy does not actively probe Stratex health. No Caddy
  change needed for Stratex.
- No `render.yaml` exists in the repo (root or `Stratex/`); the "Render
  must not kill-loop" comment in the old test is historical (service
  measured on Render 2026-10-03). The live service is the Oracle Server 1
  systemd unit; its liveness gate is `/ready` via the unit, not `/health`.
- Docker HEALTHCHECK moved to `/ready` (above).

## Verification status — read this before merging

- **Not verified locally in this run.** The hourly self-check run hit an
  execution-risk notice on the local clone, so no local pytest, import or
  build of repo code was run; the edits were verified by re-reading the
  changed regions only. **CI on the work PR is the gate**: the updated and
  new Stratex tests must pass there, plus the existing
  `test_daemon_heartbeat_health.py` (untouched; its `_health_payload`
  assertions on engine fields are unaffected) and the `/ready` tests.
- **Live-probe criteria 2–3 are NOT yet verified.** They cannot be until
  this code merges and deploys: a live probe can only observe the new
  503/degraded behaviour on a running service with the new code. Baseline
  (pre-contract, VAL-004 Fleet Live Validation run 44995483145, 2026-11-22
  12:19 IST): Stratex `/health` answered 200 with the engine offline.
  Post-merge, the verification is: deploy → probe Stratex `/health`
  (expect degraded/503 with `trading_capable` unavailable +
  `STALE_STRATEGY_EVALUATION` while the engine is offline) → probe
  FRIDAY fleet-status (expect Stratex named DEGRADED with the failing
  capability + reason; pre-contract peers labelled capability unknown).
- Note: `test_engine_capability_truthfulness.py` and
  `test_daemon_heartbeat_health.py` are not in any workflow's explicit
  file list today (checked 2026-11-22) — the same gap REL-001 closed for
  other files. The FRIDAY test files are unlisted too (see the FRIDAY
  classifier section above); the work PR wires all three into the
  contracts job lists in the same PR, on top of the rebase.

## Done this run (2026-11-22 ~15:35 IST hourly self-check) — FRIDAY classifier (§4)

- `FRIDAY/src/friday/ecosystem/fleet_client.py` — `_classify_health_response`
  now returns `(status, contract_note)` and reads the §2.2 contract fields
  first. Contract body (a `capabilities` dict of dicts with closed-vocabulary
  states): all capabilities `ok` → ONLINE ("capabilities ok"); a capability
  `degraded`/`unavailable` → DEGRADED with every non-ok capability named
  ("trading_engine unavailable (STALE_STRATEGY_EVALUATION)"); a capability
  `unknown` and none worse → REACHABLE ("capability unknown — <cap> unknown
  (CONFIG_ONLY)") — never silently reported ok, never called degraded. A
  degraded top-level `status` with no non-ok capability → DEGRADED naming
  the verdict ("peer reports status=degraded (no failing capability
  named)"). HTTP 503 with a contract body is DEGRADED, not UNREACHABLE.
  Malformed capabilities blocks fall back to legacy string matching, never a
  crash. Pre-contract peers (no `capabilities` block) keep today's string
  matching but are REACHABLE ("capability unknown — pre-contract /health"),
  never ONLINE. All nine `probe_*` methods use the new tuple via
  `_ok_details` / `_degraded_details` helpers; the per-probe caveats (what
  was NOT checked) are kept. `get_fleet_summary` no longer reads ONLINE as
  "answered": it counts answered = ONLINE + REACHABLE + DEGRADED, so a fleet
  of pre-contract peers no longer reports "No peer microservice answered".
- `FRIDAY/src/friday/tools/builtin/fleet_status.py` — summary scope is now
  "capability report from each agent's /health, not task-level verification";
  a contract DEGRADED is named with its failing capability in the summary
  ("Stratex DEGRADED: trading_capable unavailable
  (STALE_STRATEGY_EVALUATION)") without doubling the agent name; when the
  rest are all ONLINE the summary adds "The rest report all required
  capabilities ok."; REACHABLE peers are labelled "reachable, capability
  unknown (pre-contract /health)". Metadata scope tag is now
  `health_capability_report`.
- `FRIDAY/src/friday/autonomous/controller.py` (§4.5) — the diagnostic
  `peer_health_endpoints` evidence keeps `responded` and adds the split:
  `online`, `degraded`, `reachable_capability_unknown`, plus the updated
  scope sentence.
- `FRIDAY/src/friday/api/server.py` (§4.5) — `/api/agents/status` and
  `/api/agents/supervision` share the one classifier through `FleetClient`
  (no divergent classification introduced); both scope tags are now
  `health_capability_report` and the notes say capability reports. The
  public-status checklist (`get_public_status`) is intentionally unchanged:
  it is a reachability checklist (H7), not a capability verdict.
- Tests: `FRIDAY/tests/test_fleet_probe_labelling.py` — the two tests that
  pinned the old behaviour are updated to the contract (pre-contract ok body
  is REACHABLE, never ONLINE; degraded-body details name the peer verdict),
  and 8 new tests pin the classifier (contract ok → ONLINE, 503 contract
  body → DEGRADED with reason, degraded body over 200, unknown capability →
  REACHABLE, malformed capabilities → legacy fallback) plus the Stratex probe
  end-to-end (503 contract body → "Stratex DEGRADED: ..." details;
  contract ok → ONLINE "capabilities ok").
  `FRIDAY/tests/test_fleet_status_truth.py` — scope assertion updated to
  `health_capability_report`; 2 new tests pin the summary wording (no
  doubling of contract DEGRADED details; all-ONLINE summary has no
  Attention and no capability-unknown note).
- Verification status (same limits as the Stratex slice): no local pytest /
  import / build was run (execution-risk notice on the local clone stands);
  edits verified by re-reading + AST parse of all six files. **CI on the
  work PR is the gate.**
- CI wiring owed at rebase/work-PR time (new standing orders, 2026-11-22
  ~15:12 IST): neither FRIDAY test file is in any workflow's explicit file
  list today (checked: owner-workflows.yml contracts list +
  friday-universe-ci.yml), and neither is
  `Stratex/tests/test_engine_capability_truthfulness.py`. The work PR must
  add them to the contracts job lists in the same PR (standing order 5) —
  deferred now because main's `owner-workflows.yml` moved since the
  branch base (main 92f84677 vs branch d023c095); the wiring goes on top
  of the rebase, per standing order 3. (Update 16:30 IST: the FRIDAY
  /health slice adds a fourth unlisted file,
  `FRIDAY/tests/test_friday_health_contract.py` — see the §3 section
  below; all four ride in the work PR.)

## Done this run (2026-11-22 ~16:30 IST hourly self-check) — FRIDAY's own /health (§3)

- `FRIDAY/src/friday/api/server.py` — `health_check()` now returns the §2.2
  capability report (JSONResponse, HTTP 200 iff `ok` else 503):
  `capabilities.orchestration` (required; from the `friday_deep.health`
  import-check report — HEALTHY → `ok`, DEGRADED → `degraded` /
  `IMPORT_CHECK_FAILED`, FAILED → `unavailable`; evidence says
  import/liveness only), `capabilities.memory_backend` (required; the live
  DB round-trip `/ready` performs — SQLite `SELECT 1` / Oracle
  `SELECT 1 FROM DUAL`), `capabilities.peer_mesh` (optional; from
  `_peers_mesh_state()` — `connected` → `ok`, `configured_unverified` →
  `unknown` / `CONFIG_UNVERIFIED`, `unavailable` → `unknown` /
  `MESH_UNAVAILABLE`), `dependencies.database` (required; same DB probe),
  `dependencies.disk` (required; ≥ 50 MB free as `/ready` enforces,
  `LOW_DISK_SPACE` / `DISK_PROBE_FAILED`), `dependencies.environment`
  (required; `validate_runtime_environment` — added so `/health` never
  contradicts `/ready` per §2.5, which fails readiness on an invalid
  environment). Top-level `status` is derived (`ok` iff every required
  capability/dependency is `ok`, else `degraded`); `evidence_class` is now
  `capability_report` on the /health response (the `friday_deep` Report
  itself is unchanged — it genuinely proves liveness only and keeps
  `process_liveness`). All pre-existing fields are kept (`overall`,
  `checks`, `observed_at`, `service`, `agent`, `canonical_name`,
  `version`, `peers_mesh`). No secret or raw exception text in any
  payload: failure classes are exception type names only.
- `readiness_check()` refactored to share the probes: `_probe_memory_database()`
  (the exact /ready DB logic — sqlite `connect_sqlite` seam preserved, so
  the existing patch-based regressions still apply) and `_probe_disk()`
  (the exact /ready disk logic). /ready's returned fields, values and HTTP
  codes are unchanged; its env validation and production-Oracle gate stay
  inline as today. The production-Oracle gate is a /ready-only routing
  policy (production runs Oracle; the sqlite case cannot occur in
  production), so it is not duplicated into /health.
- Tests: `FRIDAY/tests/test_obs003_health_honesty.py` — the two tests that
  pinned `status: "healthy"` now pin the contract vocabulary (`ok` +
  HTTP 200 when the report is healthy; `degraded` + HTTP 503 with
  `IMPORT_CHECK_FAILED` when it is degraded).
  `FRIDAY/tests/test_tier1_resilience_and_contracts.py` —
  `test_health_endpoint_contract` now pins `status: "ok"`,
  `evidence_class: "capability_report"`, the full capability/dependency
  key sets, and every required entry `ok` in the hermetic test env.
  `FRIDAY/tests/e2e/test_tier1_features.py` — F7.1 now pins `status: "ok"`.
  `FRIDAY/tests/test_container_compatibility.py` — now pins
  `evidence_class: "capability_report"` on /health.
  New: `FRIDAY/tests/test_friday_health_contract.py` — 8 tests pin the §3
  contract (ok path + legacy fields kept; degraded orchestration → 503;
  DB down → 503 + `DATABASE_UNREACHABLE` with only the exception type
  name in evidence; DB unconfigured → `DATABASE_UNCONFIGURED`; disk low
  → `LOW_DISK_SPACE`; env invalid → both /ready and /health 503, §2.5;
  peer_mesh unknown does not degrade; /ready fields unchanged).
- Verification status (same limits as the earlier slices): no local pytest /
  import / build was run (execution-risk notice on the local clone stands);
  edits verified by re-reading the changed regions + `py_compile` + AST
  parse of all six files, and by diffing `readiness_check` against the
  branch base to confirm /ready's behaviour is identical. **CI on the work
  PR is the gate.**
- CI wiring owed at rebase/work-PR time (new standing orders): now FOUR
  test files are in no workflow's explicit file list —
  `Stratex/tests/test_engine_capability_truthfulness.py`,
  `FRIDAY/tests/test_fleet_probe_labelling.py`,
  `FRIDAY/tests/test_fleet_status_truth.py` and the new
  `FRIDAY/tests/test_friday_health_contract.py`. The work PR must add all
  four to the contracts job lists in the same PR (standing order 5).

## §6 open questions resolved from source this run

- **Q1 — FRIDAY `peers_mesh` provenance: RESOLVED.** `_peers_mesh_state()`
  (`FRIDAY/src/friday/api/server.py`) inspects the LIVE in-process mesh
  (`get_mesh().status()` state_counts of observed outcomes) — a live
  observation of this process's recorded mesh outcomes, not config and
  not a probe of peers. The `peer_mesh` capability evidence says so
  ("mesh observed COMPLETED/SUCCESS peer outcomes in-process" /
  "no completed peer outcome observed in-process").
- **Q4 — FRIDAY `/health/deep` mount: RESOLVED (not mounted in live FRIDAY).**
  The constant `{"status": "healthy", "engines": 7}` lives on the separate
  FastAPI app in `FRIDAY/apps/core/src/friday_core/real_deep_api_server.py`
  (own app, "FRIDAY Universe Deep API" v3.0.0, docs put it on port 8011).
  The live FRIDAY process is `friday.api.server:app` on port 10000
  (AGENTS.md, DEPLOYMENT_GUIDE, README agree); `server.py` never
  references `real_deep_api_server`, mounts only `/static` and `/` (UI),
  and no test or code references `/health/deep` except its definition.
  The deep app's models are imported by `real_engines_router.py` (typing
  only), never its app. So `/health/deep` is NOT reachable on the live
  FRIDAY process and needs no contract change; if the deep app is ever
  deployed as a fleet service it needs its own contract pass. Live
  confirmation is folded into the post-merge probe (a 404 on port 10000
  is expected).

## Done this run (2026-11-22 ~17:30 IST hourly self-check) — Memora /health (§5)

Memora was the smallest change in the fleet (design §5): every contract
field was already probed; the work is a mapping, a relabel, and one new
dependency surface.

- `Memora/apps/api/routers/health.py` (commit `b4657f13`) — `health_check()`
  now returns the §2.2 report alongside every pre-existing field (kept
  byte-identical in meaning): `capabilities.memory_store` (required; live
  `SELECT 1`, `unavailable` + `DATABASE_UNREACHABLE` on failure),
  `capabilities.event_store` (required; oracle backend, `unavailable` +
  `EVENT_STORE_UNAVAILABLE` otherwise), `capabilities.vector_search`
  (required; the active vector adapter's readiness — Oracle 23ai adapter on
  the Oracle backend — `unavailable` + `VECTOR_STORE_NOT_INITIALIZED` /
  `VECTOR_STORE_UNAVAILABLE`), `dependencies.database` (same live `SELECT 1`),
  `dependencies.vector_store` (same readiness), `dependencies.circuit_breakers`
  (required; surfaced from `/ready`'s `circuit_registry.healthy()` — `ok`
  when no breaker is open, `degraded` + `CIRCUIT_BREAKER_OPEN` naming the
  open breakers otherwise). Top-level `status` is derived (`ok` iff all six
  required entries are `ok`, else `degraded`) and the value moves from
  `"healthy"` to `"ok"` — the contract's closed vocabulary (§2.2); HTTP is
  unchanged (200 iff ok, else 503, as this handler already did).
  `evidence_class` is now `capability_report` (was `process_liveness`).
  Only the exception class name is recorded on DB failure, never message
  text (§2.2 rule 8). `/ready` is untouched in behaviour (its
  `evidence_class` stays `readiness_probe`: it reports readiness, not a
  capability verdict).
- Behaviour change to record: an open circuit breaker now degrades
  `/health` (503) where it previously did not — `/health` did not look at
  breakers at all. That is the contract (§2.2 rule 1: every required
  dependency must be `ok`), and `/ready` already reported the same state.
- `Memora/Dockerfile` (commit `ce87b373`) — HEALTHCHECK moved from `/health`
  to `/ready` (design §2.5/§7, mirroring the Stratex slice). `deploy/Caddyfile`
  sets no `health_uri` on the Memora block, so Caddy does not actively probe
  Memora health; no Caddy change needed.
- Tests (commits `f63b7f34`, `ac901fab`) —
  `Memora/tests/test_health_readiness_truth.py`: the vector-availability test
  now expects `"ok"` (was `"healthy"`) and pins the circuit registry healthy
  so it measures the vector leg only; 4 new tests pin the capability report
  (all-ok shape, no `detail` on ok entries, legacy fields kept), the
  `not_initialized` detail code, DB failure as `unavailable` with no raw
  exception text in the payload, and an open breaker degrading with the
  breaker named. `Memora/tests/test_health_observation_metadata.py`: the
  evidence-class assertion is now exactly `"capability_report"`.
- **§6 Q5 resolved from source:** `Memora/storage/relational/session.py`
  `get_db()` (line 650) raises `HTTPException(status_code=503, ...)` when
  `storage_ready()` is false, so a failed DB-session dependency answers an
  honest 503 and the `/health` handler body never runs — not a 500, not a
  200 with a stale body. Pinned by `test_get_db_rejects_unready_storage_with_503`
  (commit `f63b7f34`).
- Verification status (same limits as the earlier slices): no local pytest /
  import / build was run (execution-risk notice on the local clone stands);
  edits verified by re-reading the changed regions + `py_compile` + AST
  parse of all three Python files + byte-verified upload (returned blob shas
  equal the local git blob hashes). **CI on the work PR is the gate.**
- CI wiring owed at work-PR time: neither Memora test file is in any
  workflow's explicit file list today (checked 2026-11-22 on current main:
  the friday-universe-ci.yml Memora vector job lists 11 files + the viking
  suite; the health tests are not among them). They join the work-PR wiring
  list, now 6 files: `Stratex/tests/test_engine_capability_truthfulness.py`,
  `FRIDAY/tests/test_fleet_probe_labelling.py`,
  `FRIDAY/tests/test_fleet_status_truth.py`,
  `FRIDAY/tests/test_friday_health_contract.py`,
  `Memora/tests/test_health_readiness_truth.py`,
  `Memora/tests/test_health_observation_metadata.py`.

## Done this run (2026-11-22 ~18:30 IST, hourly self-check)

Futuris `/health` slice (design §5).

- `Futuris/futuris/api/app.py` — new `_health_payload()` builder + the
  `/health` route now returns `JSONResponse` (200 iff `ok`, else 503):
  `capabilities.storage` (required; live `verify_schema()` — see §6 Q6
  below), `capabilities.forecasting` (required; **no model probe exists
  anywhere in the surveyed code, so `unknown` with detail
  `NO_MODEL_PROBE`** — storage readiness is not forecasting ability and
  is never presented as such), `dependencies.database` (required; the same
  live schema-inspection round-trip). Top-level `status` is derived (`ok`
  iff every required capability/dependency is `ok`, else `degraded`);
  `evidence_class` is now `capability_report`; `agent: futuris` added;
  all pre-existing fields kept, including the legacy `storage` block.
  **Honest consequence, stated plainly: Futuris `/health` is now
  `degraded` / 503 even with storage ready, because `forecasting` is
  required and unknown.** That is the contract's outcome (§2.4 forbids
  reclassifying a required capability as optional to get a green status);
  it clears only when a forecasting-model probe is built. `/ready` is
  unchanged in behaviour (same 200/503 gates and fields).
- `Futuris/futuris/api/app.py` `execute_task` (`/v1/task/execute`
  status/health action) now calls `_health_payload()` instead of the old
  dict-returning `health_check()` — it keeps its dict access and its
  `SUCCESS`/`DEGRADED` verdict mapping, which now honestly reports
  `DEGRADED` while `forecasting` is unknown.
- Criterion 5 scrub (design §2.2 rule 8): `verify_schema()` returned raw
  exception text in its `error` field, which `/health`, `/ready` and
  `/status` all echoed — the message can carry a DSN fragment. The payload
  now carries only the exception type name; the full message is logged
  server-side (`schema_verify_failed`). `/ready`'s own except branch is
  scrubbed the same way. `/ready` codes/fields are otherwise identical.
- `Futuris/Dockerfile` — HEALTHCHECK moved from `/health` to `/ready`
  (design §2.5; the pre-existing port 8000 vs production 8004 gap is left
  as-is, out of scope). `deploy/Caddyfile` sets no `health_uri` on the
  Futuris `reverse_proxy` block — Caddy does not actively probe it, so no
  Caddy change is needed.
- Tests: `Futuris/tests/api/test_health.py` updated (storage-ready is now
  503/`degraded` with `storage` ok + `forecasting` unknown; evidence class
  `capability_report`; HEAD carries the same 503; not-ready is 503 with
  `storage`/`database` unavailable + `SCHEMA_INCOMPLETE`);
  `Futuris/tests/api/test_hostile_inputs.py` health test updated the same
  way; `Futuris/scripts/e2e_system_test.py` health assertions updated
  (503/`degraded`, storage still ready). New
  `Futuris/tests/test_futuris_health_contract.py` (4 tests): contract shape
  with storage ready; schema-incomplete → 503 + `SCHEMA_INCOMPLETE`;
  connect failure → `DATABASE_UNREACHABLE` with no DSN/URL/password text
  anywhere in the payload; `/ready` codes unchanged (200 ready / 503
  not_ready). `Futuris/tests/api/test_round2_hardening.py` needs no change
  (its two `/health` calls assert headers only, not the status code).
- **§6 Q6 resolved from source:** `Futuris/futuris/storage/db.py`
  `verify_schema()` (lines 108–145) IS a live check — it opens a real
  connection (`engine.connect()`, `pool_pre_ping: True`) and runs the
  SQLAlchemy inspector against the live Oracle schema on every call; there
  is no caching. `storage` may therefore report `ok` on its basis.
- Verification status (same limits as the earlier slices): no local pytest /
  import / build was run (execution-risk notice on the local clone stands);
  edits verified by re-reading the changed regions + `py_compile` + AST
  parse of all six Python files + byte-verified upload (returned blob shas
  equal the local git blob hashes). **CI on the work PR is the gate.**
- CI wiring owed at work-PR time: no Futuris test file is in any workflow's
  explicit file list today (checked 2026-11-22 on current main
  `c3736155`). The new contract file joins the work-PR wiring list, now 7
  files: `Stratex/tests/test_engine_capability_truthfulness.py`,
  `FRIDAY/tests/test_fleet_probe_labelling.py`,
  `FRIDAY/tests/test_fleet_status_truth.py`,
  `FRIDAY/tests/test_friday_health_contract.py`,
  `Memora/tests/test_health_readiness_truth.py`,
  `Memora/tests/test_health_observation_metadata.py`,
  `Futuris/tests/test_futuris_health_contract.py`.

## Done this run (2026-11-22 ~21:30 IST, hourly self-check — stall repair) — IntelX /health (§5)

IntelX was the first agent where the contract could NOT be applied to
the existing `/health` handler: `/health` was an alias of the
process-only liveness handler `/healthz`, and TASK-INT-012 pins that
handler (with tests) to no database work, always 200/`"ok"`, and the
exact key set with `database: "not_checked"` — FRIDAY's `ask_intelx`
reads that field for display. Applying the §2.2 report to the shared
handler would have broken INT-012 and destroyed the liveness surface
(the Docker HEALTHCHECK hits `/healthz`). So the routes are split
instead — the shape §2.2 rule 3 anticipates: the liveness-only endpoint
keeps `process_liveness`, and `/health` becomes its own handler
carrying the contract. Both paths are mounted twice (root + `/api/v1`,
via `root_api_router` and `v1_router`), so the split applies to
`/healthz` + `/api/v1/healthz` (liveness) and `/health` +
`/api/v1/health` (contract) together.

- `IntelX/intelx/api/v1/health.py` (commit `617e571d`) — new
  `_capability_report()` builder + a separate `/health` route returning
  `JSONResponse` (200 iff `ok`, else 503):
  `capabilities.research` (required; no live probe exists anywhere in
  the surveyed code, so `unknown` with detail `NO_LIVE_PROBE` — and
  `degraded` / `MOCK_MODE` in mock mode, because synthetic findings
  must never present as `ok`), `capabilities.model_provider`
  (required when not `MOCK_MODE`; config-only today → `unknown` /
  `CONFIG_ONLY` per §2.2 rule 7, never `ok` on config alone — in
  `MOCK_MODE` `unknown` / `MOCK_MODE`, since there is no live provider
  to report), `dependencies.database` (required; live
  `check_database_health()` round-trip, `unavailable` +
  `DATABASE_UNREACHABLE` on failure),
  `dependencies.storage` (required; the writable data-dir probe,
  `unavailable` + `STORAGE_UNWRITABLE` on failure). Top-level `status`
  is derived (`ok` iff every required entry is `ok`, else `degraded`);
  `evidence_class` is now `capability_report`; all pre-existing fields
  kept. The legacy `database` field now reports the probed value
  (`connected`/`unavailable`, as `/readyz` does) instead of
  `"not_checked"` — `/health` does check the database. No secret or
  raw exception text in any payload: `check_database_health()` never
  raises (returns False, logs server-side), and the provider evidence
  names only whether config is present, never key material.
  **Honest consequence, stated plainly: IntelX `/health` is now
  `degraded` / 503 even with the database and storage ready, because
  `research` is required and unknown.** That is the contract's outcome
  (§2.4 forbids reclassifying a required capability as optional to get
  a green status); it clears only when a research probe is built.
  Shared probes: `_probe_database()`, `_probe_storage()` and
  `_provider_configured()` (the `/readyz` logic, verbatim) are used by
  both `/health` and `/readyz`, so the two endpoints can never disagree
  about database/storage/provider state (§2.5).
- `/healthz` is unchanged in behaviour (same payload, same key set,
  always 200, no database work) — only the `/health` alias decorators
  and a docstring note were removed/added. `/readyz` is unchanged in
  behaviour (same 200/503 gates, fields and values); it now consumes
  the shared probe helpers instead of inline code, with the production
  Oracle gate and the `database_backend` resolution verbatim.
- Probe-routing verification (§7 prerequisite, IntelX):
  `deploy/Caddyfile` sets no `health_uri` on any block (the file
  contains no `health` string at all), so Caddy does not actively probe
  IntelX health; no Caddy change needed. `IntelX/Dockerfile`
  HEALTHCHECK and `IntelX/docker-compose.yml` healthcheck both hit
  `/healthz`, which stays liveness-only and never 503s — no kill-loop
  risk from the new `/health` 503, so the HEALTHCHECK is deliberately
  NOT moved to `/readyz` (moving it would change the container health
  gate from liveness to readiness: a DB outage would mark the
  container unhealthy). `docker-compose.production.yml` has no IntelX
  healthcheck (its line-12 healthcheck is Redis's).
- FRIDAY fleet reads the contract now (commits `45d257ef`,
  `881fba2d`): `FRIDAY/src/friday/ecosystem/fleet_client.py`
  `probe_intelx` and `FRIDAY/src/friday/core/service_registry.py`
  both default `FRIDAY_INTELX_HEALTH_PATH` to `/api/v1/health`
  (was `/api/v1/healthz`; every other agent already defaults to
  `/health`). Safe pre-deploy: the old `/health` alias returned the
  same liveness body, which the §4 classifier reads as pre-contract
  REACHABLE — identical to probing `/healthz`. Post-deploy, fleet-status
  reads the contract: IntelX DEGRADED with its failing capability
  named. `ask_intelx` still reads `/api/v1/healthz` (liveness + display
  fields) — it requires HTTP 200, so it must not move to `/health`.
  No FRIDAY test pins the old default path (checked:
  `test_fleet_probe_labelling.py`, `test_peer_evidence_inversion.py`,
  `test_prompt1_central_os.py` — the last only pins a Memora override).
- Tests (commits `0afc2ee0`, `dd7df687`, `bd84b644`) —
  `IntelX/tests/test_healthz_liveness.py`: the `/health` alias test is
  removed (the alias no longer exists) and the module docstring records
  the split; the four `/healthz`/`/readyz` tests are untouched.
  `IntelX/tests/test_health.py`: `test_healthz_endpoint` and the
  `/readyz` tests are untouched; `test_health_head_and_alias_endpoints`
  now pins `/health` GET + HEAD at 503/`degraded`/`capability_report`
  in mock mode. New `IntelX/tests/test_intelx_health_contract.py`
  (7 tests): contract shape (capability/dependency key sets, closed
  vocabulary, no `detail` on ok entries, legacy fields kept); mock
  mode 503 with research degraded/`MOCK_MODE` and DB/storage ok;
  live mode research unknown/`NO_LIVE_PROBE` + provider
  unknown/`CONFIG_ONLY` with no key material in the payload; provider
  key missing → unknown/`CONFIG_ONLY` naming the missing config; DB
  down → database unavailable/`DATABASE_UNREACHABLE` + `/readyz`
  503 (no §2.5 contradiction); storage failure →
  unavailable/`STORAGE_UNWRITABLE` + `/readyz` storage error; the
  split pinned (`/healthz` never calls the DB check, `/health` calls
  it exactly once); `/readyz` fields unchanged in mock mode.
- Verification status (same limits as the earlier slices): no local pytest /
  import / build was run (execution-risk notice on the local clone stands);
  edits verified by re-reading the changed regions + diffing the new
  files against the branch base (the `/readyz` payload and return are
  byte-identical; the only `/readyz` change is helper calls for the
  three probes) + byte-verified upload (returned blob shas equal the
  locally computed git blob hashes for all six files). **CI on the work
  PR is the gate.**
- CI wiring owed at work-PR time: no IntelX test file is in any
  workflow's explicit file list today (checked 2026-11-22 on current
  main: `friday-universe-ci.yml` pytest invocations list no IntelX
  file; `owner-workflows.yml` contracts list has no IntelX file). The
  new contract file and the two modified test files join the work-PR
  wiring list, now 10 files: `Stratex/tests/test_engine_capability_truthfulness.py`,
  `FRIDAY/tests/test_fleet_probe_labelling.py`,
  `FRIDAY/tests/test_fleet_status_truth.py`,
  `FRIDAY/tests/test_friday_health_contract.py`,
  `Memora/tests/test_health_readiness_truth.py`,
  `Memora/tests/test_health_observation_metadata.py`,
  `Futuris/tests/test_futuris_health_contract.py`,
  `IntelX/tests/test_intelx_health_contract.py`,
  `IntelX/tests/test_health.py`,
  `IntelX/tests/test_healthz_liveness.py`.
- Stall repair: the 20:16 IST self-check reported this task stalled
  (branch head `1e078f9c`, no checkpoint ~2h). This run resumed with
  the IntelX slice: 6 code/test commits on `muse8/task-rel-067`
  (`617e571d`, `45d257ef`, `881fba2d`, `0afc2ee0`, `dd7df687`,
  `bd84b644`) plus this evidence-doc update; branch head is the doc
  commit. Work PR still pending (5 agents remain + §6 Q2/Q3 +
  criterion 5/6 sweeps + CI wiring).

## Remaining (next runs)

1. The other five agents' `/health` mappings per design §5 (Forge,
   Sentinel, Cortex, VyralX, Inference).
2. §6 open questions still to resolve from source/live probe while implementing:
   Forge's three `/health`s (confirm by live probe which handler answers each path); Stratex master-control
   `/health` mount. (Memora `/health` dependency-failure mode resolved
   17:16 IST: 503 via `get_db()`; Futuris `verify_schema()` liveness
   resolved this run: live, see above.)
3. Criterion 5 sweep: no secret in any health payload (Cortex raw
   exception text is still named in the design §2.2 rule 8; Futuris
   `/ready` + `verify_schema()` scrubbed this run).
4. Criterion 6: all ten `/ready` behaviours unchanged; Caddy/Docker
   probes confirmed on `/ready` per agent before its `/health` flips.
5. Note for the work PR / deploy: Stratex cut over to FRIDAY-Universe-1
   ("Stratex Server", AWS U1) on 2026-11-22 ~17:36–18:00 IST (owner order,
   issue #35 comments 7078890756 / 7079118898) — the Stratex live-probe
   baseline for criterion 2 was taken on Oracle S1, so the post-merge
   live probe must target the new host.

— Muse 8, TASK-REL-067, 2026-11-22 ~21:30 IST

## Contracts fix — four-workflow step green (2026-11-23 ~01:44 IST)

CI on head `119e006e` (run 45057771720) failed only the `contracts` job:
the four-workflow step went red while the REL-068 guard passed. Local
reproduction of the step's exact 38-file pytest invocation (same dep list
as the workflow) gave 15 failed / 851 passed, in 3 clusters — all fixed
in one commit on `muse8/task-rel-067`:

1. Proxy-env crash (7 tests: TestRenderTool ×2, tier1 f1_01–f1_04 +
   f11_05): `httpx.AsyncClient()` with default `trust_env=True` reads
   proxy env vars; bracketed-IPv6 NO_PROXY entries break httpx URL
   parsing (`InvalidURL: Invalid port: ':1]'`). Fix: `trust_env=False`
   in `FleetClient.get_shared_client()` and `AIUniverseClient.get_client()`
   — both talk to internal peers/services only, never via an egress proxy.
2. Stale fleet answers (7 tests, `test_fleet_status_truth.py`):
   `FleetStatusTool.execute` called `get_all_statuses()` without
   `force_refresh`, so the real client could return cached statuses —
   against the tool's own real-probe contract (the test fake enforces
   "fleet answers must be fresh, not cached"). Fix: `force_refresh=True`
   on both call sites.
3. FastAPI 0.165 route shape (1 test, `test_server_app_health_routes`):
   `app.routes` now contains `_IncludedRouter` entries with no `.path`.
   Fix: filter routes by `hasattr(route, "path")` in the test.

After the fix, the same local invocation is 866 passed, 0 failed
(22.15s). CI re-run pending on the pushed head.
Note: the coordinator's watch 7084680004 names 4 CI failures including a
livekit ModuleNotFoundError and a /health 503 fleet-supervision loop —
neither reproduced locally (livekit imports fine; the health-contract
tests pass); the CI log itself is sign-in-gated, so which tests failed
on CI stays unverified until the new CI run lands.

— Muse 8, TASK-REL-067, 2026-11-23 ~01:44 IST
