# TASK-REL-067 — Health-Capability Contract Implementation (WORK IN PROGRESS)

**Task:** Implement the health-capability contract per REL-004 section 8
(design: `docs/collaboration/TASK-REL-004-HEALTH-CONTRACT.md`, Muse 9).
**Branch:** `muse8/task-rel-067`. **Status:** Stratex + FRIDAY classifier +
FRIDAY /health slices implemented on the branch; 8 agents' `/health`
remain. **Work PR not opened yet** — this document grows with the work
and is filed with the work PR.

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

## Remaining (next runs)

1. The other eight agents' `/health` mappings per design §5 (Memora,
   Futuris, IntelX, Forge, Sentinel, Cortex, VyralX, Inference).
2. §6 open questions still to resolve from source/live probe while implementing:
   Forge's three `/health`s (confirm by live probe which handler answers each path); Stratex master-control
   `/health` mount; Memora `/health` dependency-failure mode; Futuris `verify_schema()` liveness.
3. Criterion 5 sweep: no secret in any health payload (Futuris `/ready`
   and Cortex raw exception text are named in the design §2.2 rule 8).
4. Criterion 6: all ten `/ready` behaviours unchanged; Caddy/Docker
   probes confirmed on `/ready` per agent before its `/health` flips.

— Muse 8, TASK-REL-067, 2026-11-22 ~16:30 IST
