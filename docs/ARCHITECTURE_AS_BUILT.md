# FRIDAY Universe — Architecture As Built

Describes what is implemented and running, not what is intended.
Labels: VERIFIED (independently checked), PARTIALLY VERIFIED, UNVERIFIED, GAP (missing or wrong), CONFLICT (sources disagree).
Evidence cited by file path or command. Secrets are named, never printed.

## 1. Repository structure (VERIFIED)
- 5,288 tracked files; about 1.1 million lines of Python.
- Agent folders: FRIDAY (1,122 files, about 202k lines), Stratex (840 files, about 155k), Sentinel, Cortex, Inference, Forge, IntelX, Futuris, VyralX, Memora.
- Shared: tests/ (89 files), scripts/ (30), mesh/ (21 files, the health checker), docs/, deploy/, docker/, tools/.
- Only root-level .github/workflows/ runs on GitHub. Agent-level .github folders are inert (VERIFIED: sniper workflows were inert under FRIDAY/.github until moved).

## 2. Ten-agent implementation (VERIFIED in AGENTS.yaml; PARTIALLY VERIFIED in code)
| Agent | Entry point (observed) | Server | Port | Status |
|---|---|---|---|---|
| FRIDAY | src/friday/api/server.py (3,089 lines) | 1 | 10000 | Running (systemd FRIDAY.service) |
| Inference | Inference/app/main.py (per deploy guide) | 1 | 8001 | Running |
| Memora | Memora/apps/api | 1 | 8002 | Running |
| Stratex | Stratex/dashboard.py and autonomy/run_daemon.py | 1 | 8003 | Running (+ Stratex-Daemon) |
| Futuris | Futuris app | 1 | 8004 | Running |
| IntelX | IntelX/intelx/app/main.py | 1 | 8005 | Running |
| Forge | Forge app | 1 | 8006 | Running |
| Cortex | Cortex/apps/api (cortex_api.main:app) | 2 | 8009 | Running |
| Sentinel | Sentinel app | 2 | 8008 | Running |
| VyralX | VyralX/app/main.py | 2 | 8010 | Running (+ daemon, autopilot) |
- VERIFIED at point-in-time check 2026-11-09: all ten canonical agent systemd services (FRIDAY, Inference, Memora, Stratex, Futuris, IntelX, Forge, Cortex, Sentinel, VyralX) were active across the two VMs. This is service liveness only; it does not prove each function or integration is healthy.
- CONFLICT: docs/DEPLOYMENT_GUIDE.md described the port map as 8000–8010 container ports before PR #20; that PR changed it to production host ports. Confirm the current file.
- VERIFIED: `friday-oci-a1-allocator.service` is referenced in docs but not registered on Server 1 (not-found).

## 3. Internal APIs and communication (VERIFIED in fleet_client.py)
- FRIDAY's fleet client (src/friday/ecosystem/fleet_client.py) calls each peer over HTTP: probe_* for health, ask_* for queries, dispatch_task for typed envelopes.
- Typed dispatch posts to /v1/task/execute. VERIFIED present in: Inference, Memora, Stratex (1 definition each), Futuris (4), VyralX (5), IntelX (1), Cortex (1). VERIFIED absent in: Forge, Sentinel.
- CONFLICT: dispatch_task sends typed tasks to Forge and Sentinel, which do not implement that endpoint.
- The Caddy public routes (VERIFIED, /etc/caddy/Caddyfile on Server 1): /friday, /inference, /memora, /stratex, /futuris, /intelx, /forge, /bridge, /mcp, /messages, /vyralx, /sentinel, /cortex.

## 4. FRIDAY orchestration and task dispatch (VERIFIED by reading; behaviour PARTIALLY VERIFIED)
- Command router: _dispatch_command in src/friday/api/server.py. Checks prompt injection, refuses destructive intents, then routes to ask_* calls. Routing table is substring matching.
- Directive router: fleet_client.dispatch_directive, substring keyword matching. Misroutes observed by test: "decode this base64"→Forge, "I want to trader-proof my plan"→Stratex, "cashback offers"→Stratex, "the weather in the webpage"→Cortex.
- MERGED IMPLEMENTATION AND DEPLOYED (live goal invocation unverified): integrations/universe_orchestrator.py execute_universe_goal, with no simulation API set, previously returned status `dispatched`, real_agents 8, and a fixed synthesis without calling any peer. Grok's merged fix (PR #25, commit 79c1f75) calls FleetClient.get_fleet_summary and returns status `not_executed` with probed online/total counts, or the probe error; it does not execute the goal on this path. Test evidence recorded in the commit: 5 passed (2 new plus 3 existing) on Server 2, 2026-11-08. Deployment workflow #42507954757 succeeded; FRIDAY.service restarted 2026-11-08 18:03 UTC and /friday/health returned HTTP 200 at 18:07 UTC. The exact goal path remains unverified in production.
- Task records: none found. No table or store tracks assignment, status or result across agents. (PARTIALLY VERIFIED: searched for dispatch/task store; not exhaustive.)
- Autonomy: src/friday/autonomous/ exists (controller.py, daemon.py, enhanced_controller.py). UNVERIFIED: whether it can assign work to agents.
- Dispatch bus: FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py exists and is mounted at `/api/v1` (source-level route evidence). PR #28 (`claude/TASK-DISPATCH-001`) is IN_REVIEW and not merged. Independent review on 2026-11-09 found payload priority type mismatch, missing Cortex/Memora auth headers, generic/wrong routes for Forge/Futuris/Sentinel, DEGRADED/ERROR receipt misclassification and possible Stratex false success. Dispatch functionality must not be called integrated until those contract findings are fixed and tests pass.

## 5. Inference routing and providers (PARTIALLY VERIFIED)
- Inference exposes health and a routing gateway; key pools exist for Gemini, Groq, OpenRouter and NVIDIA NIM in the (untracked) credentials file. Names and counts only are recorded here.
- Keys were committed in public history (commit 46034a4). Owner rotated them.
- UNVERIFIED: fallback order and failover behaviour.

## 6. Memora databases and memory sharing (PARTIALLY VERIFIED)
- Memora manifest: Oracle Autonomous Database, schema MEMORA, Oracle 23ai vector store. (Memora/SYSTEM_MANIFEST.md, changed in PR #20.)
- CONFLICT: an older manifest said SQLite WAL. Current code and manifest should be checked against each other (UNVERIFIED).
- Memory namespaces: memora://<agent>/private (documented). UNVERIFIED: enforcement.
- Stratex: Oracle schema STRATEX (manifest); code uses SQLite in places (e.g. sqlite+aiosqlite path in old manifest). CONFLICT, UNVERIFIED.

## 7. Oracle Cloud infrastructure and placement (VERIFIED)
- Server 1: 140.245.208.100 (private 10.0.0.121). 956 MB RAM. Disk 97 GB, 26% used.
- Server 2: 140.245.243.168 (private 10.0.0.120). 956 MB RAM. Disk 49 GB, 37% used.
- Memory use at time of check: Server 1 454 MB used, 346 MB available, 1.5 GB swap used. Server 2 466 MB used, 337 MB available.
- Region ap-hyderabad-1. Always Free A1 capacity: none available (sniper log, 287 attempts, "Capacity full").
- VERIFIED 2026-11-09: FRIDAY-Voice.service is active and loads `/etc/systemd/system/FRIDAY-Voice.service.d/memory.conf` with MemoryHigh=250M and MemoryMax=300M. This resolves the previous missing-limit gap. Separate LiveKit logs contain event-loop-blocked warnings (158–679ms; threshold 100ms) at 2026-11-08 19:35–20:10 UTC; current frequency and user-facing effect are not yet verified.

## 8. Service ports, health and deployment configuration (VERIFIED)
- Health: systemd/mesh checks reported GET /health 200 for all ten agents at the point-in-time check; direct exhaustive endpoint and capability tests for every agent remain outstanding.
- Restart policy: all units Restart=always (VERIFIED). A crash loop restarts silently; no alerting found.
- Deploy: deploy-monorepo.yml on push to main; SSH to each server; `git fetch origin main; git reset --hard origin/main`; restarts changed agents. VERIFIED by reading the workflow; deployment execution is not evidenced by this GitHub-only review.
- Mirror: current main workflow still requires inspection against open PR #27. PR #27 proposes manual-only mirroring and removes force-push; it is not merged.

## 9. Authentication and authorization (PARTIALLY VERIFIED)
- Agents require bearer keys named in their manifests (MEMORA_API_KEY, STRATEX_API_KEY, FRIDAY_API_KEY and so on). Values are secrets; not recorded.
- Bridge (friday-bridge, :8011, exposed via Caddy /bridge, /mcp, /messages): run_shell, github_api, github_write_file, read_text, github_run_logs. Production bridge auth remains unverified/not enabled in the observed production source. PR #24 (`chatgpt/TASK-SEC-003`) adds fail-closed ASGI middleware and tests on a branch only; its integration patch, runtime secret provisioning, both MCP clients' header compatibility, and owner-approved restart remain outstanding. Do not claim protection is active.
- CI secrets: DATABASE_URL in CI is a test-only placeholder (VERIFIED in monorepo-validation.yml from PR #20).

## 10. Secret management (VERIFIED)
- GitHub Actions secrets in FRIDAY-Universe: GH_PAT_MIRROR, ORACLE_SSH_KEY, SERVER1_HOST, SERVER2_HOST, OCI_USER_OCID, OCI_KEY_CONTENT, OCI_FINGERPRINT, OCI_TENANCY_OCID, OCI_REGION, OCI_USER_OCID_2, OCI_KEY_CONTENT_2, OCI_FINGERPRINT_2 (names verified via API).
- CREDENTIALS.md on Server 2 (/opt/friday_universe/CREDENTIALS.md): untracked by git (VERIFIED, 0 history commits in earlier host check). Holds identifiers and provider keys in plaintext. Keep it out of git.
- `.gitignore` excludes credential files, `.env` files, private-key files, token JSON and service-account JSON; `.env.example` remains explicitly allowed. A recursive Git-tree filename inventory on main (5,291 blobs) found the nine expected `.env.example` templates and no tracked credential/private-key filename matches. This is filename evidence only, not content proof.
- IN_REVIEW, not on main: PR #31 adds a Gitleaks GitHub Actions workflow for PR/push change ranges. Run 42525462164 passed after fixing an initial shallow-fetch range failure. It does not scan the legacy full history; TASK-SEC-002 is still required.
- IN_REVIEW, not on main: PR #32 addresses an IntelX database runtime error. Live IntelX.service logs recorded `AttributeError: OracleDialectAsync_oracledb has no attribute _json_deserializer` during a SQLAlchemy result processor at 2026-11-08 20:22:08 UTC. IntelX model declarations use generic SQLAlchemy JSON columns, while its engine customized only Oracle JSON DDL compilation and did not set generic JSON serializer/deserializer defaults. PR #32 adds these missing base-dialect defaults in a standalone `IntelX/intelx/oracle_dialect_compat.py` imported before engine construction, plus `tests/test_intelx_oracle_json_compat.py` that exercises JSON bind/result round-trip on `OracleDialect`. Latest CI on PR head is queued/in progress; earlier collection attempts failed because `intelx.db` package initialization imported SQLAlchemy asyncio and greenlet was absent. The helper has since been moved outside that package. No service restart or production DB validation performed.
- Leaked keys in public history commit 46034a4: owner rotated. History not yet rewritten.
- Binance keys are present in the credentials file and in Stratex/.env (BINANCE_API_KEY/BINANCE_API_SECRET names observed; values not read). Effective venue mode is demo (BINANCE_ENV=demo) with ed25519 keys; the earlier blanket "testnet only" claim is superseded by the 2026-11-09 flag verification above.

## 11. External integrations (PARTIALLY VERIFIED)
- Binance (Stratex). VERIFIED 2026-11-09 (read-only, non-secret flags): production .env on Server 1 has BINANCE_TESTNET=false, TRADING_MODE=FUTURES, TESTNET_ENABLED=true, PAPER_SAFE_MODE=FALSE, BINANCE_ENV=demo, BINANCE_KEY_TYPE=ed25519; BINANCE_API_KEY/BINANCE_API_SECRET names present (values not read). The daemon's venue is BinanceFuturesAdapter in demo mode (demo.binance.com), not the classic testnet. Code default BINANCE_TESTNET true does not match the effective value — recorded as an owner decision point. IN_REVIEW, not on main: PR #39 adds the fail-closed live-trading guard across exchanges/exchange_implementations.py (permanent LIVE block, explicit ALLOW_LIVE_TRADING opt-in defaulting to false, testnet-routed client, fabricated FILLED orders removed).
- Telegram (Stratex notifications). UNVERIFIED.
- LiveKit (FRIDAY-Voice). UNVERIFIED.
- Gemini, Groq, OpenRouter, NVIDIA NIM (Inference). UNVERIFIED.
- AWS Mumbai libSQL (Memora, IntelX per old credentials file). CONFLICT with Oracle manifest; UNVERIFIED.

## 12. Background workers and scheduled jobs (VERIFIED)
- Oracle sniper: hourly cron (workflows at repo root) plus 6-hour relay (workflow_dispatch). VERIFIED in workflow files.
- Stratex-Daemon and VyralX-Daemon / VyralX-Autopilot: long-running services. VERIFIED units exist.
- friday-oci-a1-allocator.service: referenced, not installed (VERIFIED).

## 13. Failure handling and recovery (PARTIALLY VERIFIED)
- Circuit breakers exist in fleet_client (get_circuit_breaker). UNVERIFIED thresholds.
- Restart=always on all services. No alerting found (GAP).
- Backups: UNVERIFIED. No backup job found in this review.
- Rollback: none documented (GAP).

## 14. CI/CD (VERIFIED)
- Workflows at root on main include deploy-monorepo, mirror-subrepos, monorepo-validation, validate-monorepo, friday-universe-ci, heavy-task-image-build, oracle-capacity-sniper, oracle-capacity-sniper-worker2. PR #31 proposes a new secret-scan.yml workflow; it is not merged.
- Earlier CI blockers included VyralX/Futuris `app` collision, missing test dependencies and a `sys` import error. PR #22 and commits f24ff91/680c04e landed fixes for dependency installation and `mesh/memory_fabric.py`. Historical run 42502800827 still showed 3,286 passed, 74 skipped, 38 failed and 43 errors on a PR head. Current main full-suite status not verified in this review.
- Workflows run on Node 20 with actions/checkout@v4 (deprecation warning in logs; not blocking).

## 15. Known gaps and inconsistencies (summary)
1. CONFLICT: Stratex database (Oracle manifest vs SQLite code).
2. CONFLICT: Memora database (Oracle manifest vs SQLite in older docs).
3. CONFLICT: Stratex venues (Binance Futures vs MT5 vs cTrader). Owner says Binance testnet.
4. MERGED (PR #25): universe_orchestrator no longer fabricates a live dispatch; when no Universe API is configured, the goal remains `not_executed` and is not actually executed.
5. GAP: keyword routing misroutes; TASK-ORCH-001 remains outstanding.
6. GAP: Forge and Sentinel typed task route capability is not yet complete; PR #29 covers Sentinel only and PR #28's generic defaults have unresolved contract review findings.
7. RESOLVED CONFIGURATION GAP: FRIDAY-Voice now has MemoryHigh=250M and MemoryMax=300M in a systemd drop-in (read-only verification 2026-11-09); LiveKit event-loop blocking warnings remain separately under investigation.
8. GAP: production bridge authentication not yet activated; PR #24 is source/tests only pending operational requirements.
9. GAP: no runtime FRIDAY task database/store for cross-agent assignment. A documentation-level contributor/task registry is proposed in PR #30 under docs/collaboration; it is not yet merged and does not replace a runtime task execution record.
10. GAP: no alerting on crash loops; no documented rollback.
11. GAP: sniper secrets authentication unconfirmed (TASK-OPS-002).
12. UNVERIFIED: most per-agent internals (not yet read in full).
13. IntelX Oracle JSON processor error observed; PR #32 fix is in review and not deployed.
14. FRIDAY-Voice memory limit is now configured (MemoryMax=300M); LiveKit event-loop blocked warnings need further diagnosis.
15. Stratex received 401 responses for some `/api/v1/status` and `/api/v1/positions` probes and 404 responses for several alternate positions/trades URLs in service logs. Futuris also logged 404s against Stratex positions endpoints. Caller/endpoint contract and effect on service functionality remain under TASK-STR-001/TASK-STR-002 investigation; Stratex.service itself was active.
13. CI: full monorepo validation is not green. On PR #30 head 7ec4cdda, run 42564999230 reported 37 failed, 3272 passed, 73 skipped and 40 errors; run 42564999188 failed during monorepo-policy validation. This is branch test evidence, not main verification.
14. Cortex role policy: PR #26 has an unresolved finding because method-only POST=>operator blocks read-only forecast analysis for viewer users.
15. Secret scan: PR #31 is open, and its change-range Gitleaks CI passed on its latest head; broader monorepo validation remains red. Do not treat TASK-SEC-004 as complete until PR review, required checks and merge.
16. Futuris/Stratex data truth: PR #33 removes simulated BTC/ETH/SOL positions and placeholder credentials from the Futuris telemetry connector. It is not merged or deployed; read-key configuration and live data verification remain outstanding.
17. CI: PR #34 changes validation dependencies/fixtures, the dispatch bus and Forge optimizers. Its FRIDAY CI and heavy-task image checks passed, but both monorepo validator jobs failed. PR #34 overlaps PR #23 and #28 on changed files.
18. AI collaboration: PR #30 proposes a shared collaboration centre at docs/collaboration and GitHub issue #35 for claims/handoffs. The directory is not on main until PR #30 is reviewed and merged. It is a contributor coordination layer, not a runtime FRIDAY task store.


## 16. Multi-AI collaboration and task ownership (PROPOSED IN PR #30; NOT ON MAIN)

- The proposed coordination directory is `docs/collaboration/`. PR #30 (ChatGPT) and PR #36 (Vercel v0) independently created overlapping versions. PR #30 currently contains a universal contributor guide, roster, operational task board, file-ownership/conflict register, append-only activity log, decisions, handoffs, reusable templates and validator. The two PRs must be consolidated before merging.
- GitHub issue #35 is the shared, timestamped claim/release/handoff thread for Claude, ChatGPT, Grok, ZAI, Vercel v0 and future contributors. Every collaborator remains an equal engineering contributor; the project owner retains final approval.
- `docs/MASTER_PLAN.md` remains authoritative for task scope and acceptance criteria. The collaboration board mirrors ownership and work state; it does not replace the Master Plan.
- Initial file-overlap audit found PR #23/#34 overlap on `.github/workflows/validate-monorepo.yml`, PR #28/#34 overlap on `universe_dispatch_bus.py`, and PR #24/#26/#30 overlap on the three central documents. These conflicts require explicit reconciliation before merge.
- Vercel v0 is now an active contributor with branch `v0/coordination-bootstrap` and PR #36; its branch/PR existence is verified, while its reported local shell/Vercel sync capabilities are not independently verified in this session. ZAI remains planned/not onboarded. Verify tools and permissions before expanding either contributor's scope.
- The collaboration directory is documentation/Git coordination only. FRIDAY's runtime assignment/result store under TASK-CORE-003 remains a separate engineering requirement.
- A dedicated validator `scripts/validate_collaboration.py` and workflow `.github/workflows/collaboration-registry.yml` are included in PR #30. They structurally validate contributor/task IDs, states, ownership references, conflict references, required docs and the canonical ten-agent list. Collaboration Registry Validation run 42596903311 passed on PR #30 head 5920161f. Broad monorepo validators 42596903328 and 42596903017 were in progress at the latest status check. The collaboration check validates registry structure only, not implementation or production health.


## 17. Memora Oracle vector adapter remediation (PR #37 — IN_REVIEW; not on main)

- The Memora Oracle vector adapter's former MERGE matched only memory ID, and its SQLite fallback could update the tenant label for an existing ID. PR #37 changes the Oracle match key to (ID, tenant) and rejects cross-tenant ID reuse in the fallback.
- The canonical write pipeline passes its active SQLAlchemy session to vector upsert before the final event/audit commit. The adapter previously committed that caller-owned session; PR #37 now encloses caller-owned upsert/delete in a nested savepoint and leaves the parent transaction to the memory pipeline. Schema bootstrap uses its own managed session.
- Readiness now reports `not_initialized` until schema bootstrap succeeds and reports the actual backend instead of assuming a SQLite emulation.
- Adapter inputs now reject invalid identifiers, vector dimensions and non-finite values, invalid payload types, invalid thresholds and unbounded result limits.
- The stale `VECTOR_DIMENSION=1536` knob was unused; actual embedding generation and Oracle table are 384-dimensional. PR #37 removes the ineffective override and documents the 384-dimensional contract. External Qdrant collection provisioning is not verified.
- Verification: PR #37 focused Memora Vector Regression run 42596147391 PASS (8 passed, 1 warning); full FRIDAY Universe CI/CD run 42596147378 PASS, including the Memora step and HTTP/API suite. Oracle MERGE is checked by SQL contract tests; SQLite tests verify fallback and transaction boundaries. No live Oracle Autonomous Database or Qdrant service was contacted. Broad monorepo validation remains separately in progress.


## 18. Memora vector audit (PR #37 — IN_REVIEW, not merged)

- PR #37 adds tenant-safe vector upsert semantics for Oracle and the SQLite fallback, caller-owned transaction savepoints for vector mutations, schema bootstrap isolation, truthful readiness, and input validation.
- The unused 1536-dimensional configuration was removed; current embedding generation/Oracle vector schema is fixed at 384. A deployed Qdrant collection's actual dimension remains unverified.
- Verification: focused Memora vector regression run 42596147391 passed (8 passed, 1 warning); FRIDAY CI run 42596147378 passed, including all FRIDAY test suites, Memora vector tests, and HTTP/API tests.
- No live Oracle database/Qdrant service was contacted. PR #37 remains open and is not production-verified.


## 19. Memora maintenance tenant isolation (PR #38 — IN_PROGRESS; stacked on PR #37)

- The API-triggered /v1/memories/sweep-horizon previously forwarded a request-body tenant ID directly to the consolidator. The consolidator can create permanent milestone records and delete expiring raw records within the selected tenant.
- PR #38 binds the API route to the authenticated Memora service identity in the API-bound default tenant. A foreign tenant selector returns HTTP 403 before the sweeper is called; omitted or matching selectors still run only for the bound tenant.
- The trusted internal background worker's separate all-tenant sweep mode remains unchanged; the restriction applies to the authenticated API endpoint.
- Verification on PR #38 head 0b8252529f36d37c51907cfbd1dc3fd6149b6bfb: FRIDAY Universe CI/CD run 42598678632 passed, including Memora group (17 passed, 1 warning) and HTTP/API suite (45 passed); focused Memora Vector Regression run 42598678508 passed (8 passed, 1 warning).
- PR #38 is stacked on PR #37 and must not merge before #37. The full TASK-DATA-002 isolation audit remains in progress; Oracle/Qdrant production state remains unverified.

- Additional mounted-surface finding on PR #38: `main.py` also mounts the legacy `/api/v1/memora/access/*` compatibility router. Its handlers previously lacked authentication and exposed process-local grant/revoke/approve operations and global audit/report metadata. PR #38 now authenticates all seven routes, restricts administrative operations and global inspection to the `memora` service identity, binds self-service request/check subjects to the authenticated caller, and labels the engine as process-local compatibility state. Focused regression run 42658441949 passed (12 passed, 1 warning); Memora step in FRIDAY CI run 42658441937 passed. This branch is unmerged and not deployed; the controller is not the canonical persistent PolicyEngine.

- Additional canonical write-path boundary verified on PR #38: caller-supplied `shared_with` values previously added per-memory allow-list entries after a namespace `write` decision only. The pipeline now requires record ownership and an explicit PolicyEngine `share` decision; rejects wildcard, self, unknown and foreign-tenant recipients; and provisions tenant-scoped read/query namespace grants plus per-memory membership in the same transaction. Audit and `memory.shared` event are recorded. The canonical team-shared namespace's implicit semantics remain unchanged. Focused Memora regression run 42663206883 passed (16 tests, 1 warning); full FRIDAY CI run 42663207108 passed all Python and HTTP/API suites; Docker job skipped on the PR event. Monorepo checks were still in progress at the time of this update. Unmerged/un-deployed on PR #38.

- Additional task-action receipt correction on PR #38: `Memora/apps/api/routers/v1_task.py` previously reported `backend=oracle` and `durable_write=true` for any successful store. It now derives backend/durability from `storage_receipt()`; the verification evidence reports the actual backend and only claims durable_write when the storage layer marks it durable. A route-level test verifies the SQLite/non-durable contract. CI for this last change is pending; this is not evidence of production Oracle persistence.

16. DEFECT FIXED IN REVIEW (PR #39, not on main): Stratex exchanges/exchange_implementations.py fabricated FILLED order results and unconditional cancel success (Binance/Bybit/OKX), built a live-endpoint python-binance client without testnet routing or authorization, and allowed unguarded Coinbase live orders. The production daemon does not route orders through these adapters (dashboard uses them read-only), so no fabricated order reached a venue; the code defect existed on main until PR #39. Follow-ups: Bybit/OKX real execution or removal, read-path data honesty in those adapters, Stratex tests in CI.

## 20. Database architecture per agent (TASK-DATA-001 audit, 2026-11-09; owner-authorized remediation 2026-11-10; ZAI — IN_REVIEW)

Method: repository config-code scan plus read-only production verification through the bridge MCP on both servers. Only environment-variable NAMES, schema-user NAMES, dialect schemes and listener presence were recorded; no secret values were read, printed or stored. Command-level evidence is listed in docs/collaboration/ACTIVITY_LOG.md.

### 20.1 Shared infrastructure (VERIFIED)
- One Oracle Autonomous Database instance — host verified in every production DSN: `adb.ap-hyderabad-1.oraclecloud.com` (TCPS 1521, `oracle+oracledb` dialect) — is the sole durable store for all ten agents, reached from both servers. Infrastructure-level blast radius is therefore shared; schema-level separation is the only isolation. Relevant to TASK-INF-003 (backup/restore) and capacity planning.
- Per-agent Oracle schema users verified by name: FRIDAY, INFERENCE, MEMORA, STRATEX, FUTURIS, INTELX, FORGE, SENTINEL, CORTEX, VYRALX, plus a second VyralX media schema VYRALX_MEDIA.
- Redis exists only on Server 2 (127.0.0.1:6379, loopback-bound; used by Cortex event streaming and the friday-bridge). No Redis listener exists on Server 1 (`ss -ltn`, 2026-11-09).
- Qdrant is not listening on either server (no 6333 anywhere).
- SQLite is a dev/test fallback only. Production paths are fail-closed: FRIDAY `resolve_database_url` hard-errors on a missing/non-Oracle URL (`FRIDAY/src/friday/core/oracle.py`), and Sentinel `get_database_url` raises on any sqlite URL (`Sentinel/sentinel/storage/persistence/durable_store.py`). CI uses a mock DSN placeholder only.

### 20.2 Per-agent DSN env-var names, code consumers and schema ownership (VERIFIED)
"Code-read" = the variable name appears in the agent's Python config path. "Provisioned" = the name is set in the agent's production .env. Table ownership evidence comes from repository code/migrations.

| Agent | Schema user | Code-read DSN vars | Provisioned but unused in code | Migrations | Owned tables (evidence) |
|---|---|---|---|---|---|
| FRIDAY | FRIDAY | DATABASE_URL > FRIDAY_DATABASE_URL > FRIDAY_UNIVERSE_DB_URL (alias chain, `friday/core/oracle.py`); ASYNC_DATABASE_URL (`friday/core/config.py`) | FRIDAY_UNIVERSE_DB_ASYNC_URL (ADMIN; `*_DB_ASYNC_URL` has no Python consumer anywhere) | idempotent create_all `ensure_schema` | ~60 tables incl. agent_tasks, api_keys, access_grants, audit_events, artifacts, execution_traces, documents, embeddings |
| Inference | INFERENCE | DATABASE_URL; ORACLE_CORE_URL / ORACLE_CORE_ASYNC_URL (`app/memory/oracle.py`) | — | none found | memories, deliberations, evaluations, experiments, messages, runs, strategies, tasks, agents |
| Memora | MEMORA | DATABASE_URL (alternates: SQLITE_FALLBACK_URL, TURSO_DATABASE_URL, MEMORA_TEST_POSTGRES_URL); REDIS_URL; QDRANT_URL | FRIDAY_UNIVERSE_DB_URL (ADMIN copy) + FRIDAY_UNIVERSE_DB_ASYNC_URL (ADMIN) | Alembic (22 files) | namespaces, event_log, event_consumer_cursors, operations, alembic_version + memory tables |
| Stratex | STRATEX | DATABASE_URL; STRATEX_DATABASE_URL; MT5_BRIDGE_DATABASE_URL / MT5_BRIDGE_IDEMPOTENCY_DB (unset in production) | — | selection tests (`test_oracle_persistence_selection.py`) | order_intents, order_audit_events, bridge_orders, trading_journal, journal, portfolio_equity_state |
| Futuris | FUTURIS | DATABASE_URL (+ TEST_DATABASE_URL) | FRIDAY_UNIVERSE_DB_URL (ADMIN copy) + FRIDAY_UNIVERSE_DB_ASYNC_URL (ADMIN) | Alembic (0001/0002) | checkpoints, idempotency, jobs, outbox |
| IntelX | INTELX | DATABASE_URL; INTELX_DB_URL (`intelx/core/settings.py`, real_investigation_pipeline.py) | FRIDAY_UNIVERSE_DB_URL (ADMIN copy) + FRIDAY_UNIVERSE_DB_ASYNC_URL (ADMIN) | Alembic (6 files) | cases, investigation_cases, research_state, outbox, runs |
| Forge | FORGE | FORGE_DATABASE_URL; ASYNC_DATABASE_URL; FORGE_UNIVERSE_DB_URL | DATABASE_PATH / MEMORA_DB_PATH (present in production env) | none found | projects, tasks, task_graphs, artifacts, memora_outbox, memory_records, audit_events, checkpoints |
| Sentinel | SENTINEL | DATABASE_URL > SENTINEL_DATABASE_URL / SENTINEL_ORACLE_URL chain (`get_settings().db.sync_url`) | — | Alembic (0001 core models, 0002 task contracts) | users + core task-approval models; sqlite refused |
| Cortex | CORTEX | ORACLE_CORE_URL / ORACLE_CORE_ASYNC_URL; REDIS_URL (S2, present); dev fallbacks SQLITE_DSN / POSTGRES_DSN | — (CORTEX_URL etc. are HTTP peers, not DSNs) | Alembic (12 files) | jobs, outbox, idempotency + Friday-router schema |
| VyralX | VYRALX + VYRALX_MEDIA | DATABASE_URL; MEDIA_DATABASE_URL (`app/database.py`, `app/media_store.py`) | VYRALX_DB_URL + VYRALX_DB_ASYNC_URL (ADMIN; no Python consumer) | custom `app/migrations.py` | PROVISIONED_TABLES: agent_tasks, assets, content_packs, publish_jobs, render_jobs, sources, video_metrics, video_projects |

### 20.3 Findings (2026-11-09; remediation executed 2026-11-10 under owner authorization — see §20.4)
1. ADMIN-privileged DSNs in production agent env files. Correction issued 2026-11-10 during remediation: in FRIDAY/.env the sync variable FRIDAY_UNIVERSE_DB_URL authenticates as the FRIDAY schema user (a redundant duplicate of DATABASE_URL, not a privilege violation — kept in place); only FRIDAY's FRIDAY_UNIVERSE_DB_ASYNC_URL was ADMIN. On Memora/Futuris/IntelX both FRIDAY_UNIVERSE_DB_URL and FRIDAY_UNIVERSE_DB_ASYNC_URL authenticated as ADMIN; on VyralX both VYRALX_DB_URL and VYRALX_DB_ASYNC_URL did. This contradicted the root .env.example policy "One unprivileged login per agent". REMEDIATED 2026-11-10: all ADMIN-bearing lines removed from six env files across both servers; services restarted and verified healthy; dead ADMIN construction removed from deploy/setup_fleet.sh (§20.4). Residual exposure now matches the policy. Still feeds TASK-SEC-004 for the historical-exposure review.
2. Provisioned-but-unused DSN variables: `*_DB_ASYNC_URL` appears in zero Python files (repo-wide), and VYRALX_DB_URL is unconsumed on VyralX. Dead configuration invites drift and silently widens credential exposure. REMEDIATED 2026-11-10: the variables were removed together with the ADMIN DSNs (§20.4).
3. Memora Redis/Qdrant wiring is dead on Server 1: REDIS_URL and QDRANT_URL point at localhost:6379/6333 where nothing listens (neither Redis nor Qdrant is installed on Server 1, and Memora's emitter deliberately refuses localhost Redis when MEMORA_ENV=production). Memora runs Oracle-only and the cross-agent event bus works via HTTP polling of Memora's own /v1/events + /v1/events/cursor endpoints (journal evidence: consumers `friday-cloud` and `futuris-cloud-v1`). RESOLVED 2026-11-10 as intentional configuration: REDIS_URL=disabled (the emitter's designed off-switch) and the dead QDRANT_URL/QDRANT_COLLECTION removed, so the deployed config is truthful and the startup log says "Redis not configured" instead of the misleading "Render cloud environment detected". Feeds TASK-DATA-003 and TASK-OBS-001 for the decision on whether a real Redis is ever wanted.
4. DSN naming inconsistency across agents: DATABASE_URL, AGENT_DATABASE_URL, *_DB_URL, *_DB_ASYNC_URL, ORACLE_CORE_URL/ASYNC, INTELX_DB_URL conventions coexist; Cortex is the only agent without a DATABASE_URL variable. Candidate standardization alongside TASK-API-002 (AGENTS.yaml as the source of truth could cover DSN variable names too).
5. Single shared ADB instance: one Autonomous Database serves all ten agents plus the ADMIN connections. A single instance outage or quota event affects every agent's durability. Relevant to TASK-INF-003 backup/recovery and to the resource budget in AGENTS.yaml.
6. Non-DB observation found during the same read-only walk: vyralx-autopilot.service on Server 2 was failed (systemd start-operation timeout, SIGTERM at 2026-11-09T16:05:40Z after 1h4m CPU in whisper/source analysis; static unit triggered by vyralx-autopilot.timer). VyralX-Daemon and VyralX services themselves were running. REMEDIATED 2026-11-10: TimeoutStartSec raised 3600→7200 (root cause: the script's --timeout 2400 caps only the publish-drain phase, so a full run can exceed 1h; 2h stays well inside the 5h timer interval), failure state cleared, timer re-armed for the next 00/5:05 UTC slot (§20.4). Remaining follow-up for TASK-VYR-001: make the autopilot script enforce a total wall-clock budget.

### 20.4 Remediation executed 2026-11-10 (owner-authorized via chat: "Fix them and continue working"; ZAI)

Authorization and safety method: the owner authorized remediation of the audit findings in the collaboration chat. Every production change below was preceded by a backup, applied through the bridge MCP, and followed by an explicit verification; only variable NAMES, schema-user NAMES and unit/log facts were handled — no secret values were read, printed or stored.

1. **ADMIN DSN removal (finding 1 + 2).** Pre-flight: confirmed zero live-code consumers of `FRIDAY_UNIVERSE_DB_URL`/`_ASYNC_URL`/`VYRALX_DB_URL`/`_ASYNC_URL` on both servers (the only references are FRIDAY's last-priority alias chain, where DATABASE_URL wins, doc strings and error messages; `/etc/friday/dispatch.env` is clean). Removed 9 ADMIN-bearing lines from six env files — Server 1: FRIDAY/.env (FRIDAY_UNIVERSE_DB_ASYNC_URL), Memora/.env, Futuris/.env, IntelX/.env (FRIDAY_UNIVERSE_DB_URL + _ASYNC_URL each), VyralX/.env repo copy (VYRALX_DB_URL + _ASYNC_URL); Server 2: VyralX/.env live copy (VYRALX_DB_URL + _ASYNC_URL). FRIDAY's own-user FRIDAY_UNIVERSE_DB_URL duplicate was kept (non-privileged fallback). Backups: `~/env-backups/*.pre-taskdata001` (mode 600) on each server. Restarted and verified active with clean startup logs and working Oracle connections: FRIDAY, FRIDAY-Voice, Memora, Futuris, IntelX (Server 1); VyralX, VyralX-Daemon (Server 2). Post-change fleet check: zero failed units on both servers; primary DSNs unchanged (FRIDAY, MEMORA, FUTURIS, INTELX, VYRALX, VYRALX_MEDIA schema users).
2. **Regression-source removal.** `deploy/setup_fleet.sh` section [2/4] constructed the four ADMIN-privileged DSN variables (plus ADMIN username/password scaffolding) that nothing consumed; the deployed ADMIN entries predate the current script, which never wrote .env files. The dead construction was removed so fleet re-setup cannot re-seed ADMIN DSNs and no longer demands ADMIN passwords (bash -n verified).
3. **Memora event-bus config made truthful (finding 3).** Redis and Qdrant are not installed on Server 1, and `Memora/core/events/emitter.py` deliberately refuses localhost Redis when MEMORA_ENV=production. Chosen fix: `REDIS_URL=disabled` (the emitter's designed off-switch — "none"/"disabled"/"false"/"" are accepted) and removal of the dead QDRANT_URL/QDRANT_COLLECTION (no production consumer; the Qdrant adapter is never instantiated and vectors live in Oracle per the PR #37 audit). VECTOR_DIMENSION was left in place (harmless, matches the code default; PR #37 removes the setting on the code side). Backup: `~/env-backups/Memora.env.pre-redis-fix`. Post-restart log: "Redis not configured. Event Bus running in local in-memory mode." and "Application startup complete"; Futuris event polling (`/v1/events/cursor`, `/v1/events?after_id=…`) returned 200 OK after the restart, proving the durable Oracle event path intact.
4. **vyralx-autopilot unit repair (finding 6).** `/etc/systemd/system/vyralx-autopilot.service` on Server 2: TimeoutStartSec 3600→7200 (Type=oneshot; the timer fires every 5h, so no run overlap is possible), `systemctl daemon-reload`, `reset-failed`. Verified: TimeoutStartUSec=2h, Result=success, ActiveState=inactive (idle), timer next fire 2026-11-10T05:05:00Z. Backup: `~/systemd-backups/vyralx-autopilot.service.pre-taskdata001`. No manual batch run was started; the next timer-triggered run validates the new cap end-to-end (expected completion under 2h; the run killed on 2026-11-09 had already consumed 1h wall / 59min CPU and was still mid-work).
5. **What was intentionally NOT done:** no new software installed on either server (Redis/Qdrant stay absent by explicit choice, not oversight — provisioning them is an owner decision tracked via TASK-DATA-003/TASK-OBS-001); no merge of any PR; no change to any agent's primary DATABASE_URL; no credentials rotated (the ADMIN password itself is unchanged — rotation is TASK-SEC-004 scope if the owner wants it, since the removed DSNs existed in files for an unknown period).

## 21. 2026-11-12 — Arena.ai TASK-VAL-003 (branch only; not merged/deployed)

- Collaborator: `arena_engineering_01`; branch `arena/TASK-VAL-003-runtime-audit`; shared claim on issue #35 comment 6824912950.
- Added `scripts/audit_fleet_runtime.py` and `tests/test_audit_fleet_runtime.py`: read-only, bounded, secret-minimizing on-host checkout/systemd/health evidence. No env/log reads; no worktree/service modifications; no cached-ref-as-live-GitHub claim; no functional-readiness inference from health.
- Tests: 98 passed across the new 30-test suite and five adjacent fleet/backup suites. Registry validator run separately. These are targeted results, not a full-suite claim.
- Both VMs checked at 13:28 UTC / 18:58 IST: all ten canonical units active, NRestarts=0, local and public health HTTP 200 with healthy/ok payloads. Both checkouts and cached origin/main are 7ab94d39; freshly queried GitHub main is e26aeff3 (later docs-only commit). Protected untracked entry counts: S1=9, S2=6. No fetch/reset/cleanup/restart performed. A worktree revision is NOT an attestation of loaded process code.
- Current GitHub discovery: PRs #45–#54, all Dependabot; no review comments/reviews at inspection. Main e26aeff3 CI/registry/secrets/fleet-deploy checks report success. A successful docs-only deploy need not sync the VMs. Respect ZAI Agent 2's active Stratex profitability claim posted 13:09Z.
- Configuration-file evidence only: selected database DSN schemes on both hosts are oracle+oracledb, including all ten agents' primary configured variables. No DSN credentials/hosts/paths printed. This contradicts an older handoff note claiming several production DATABASE_URLs were HTTP; effective runtime storage and live DB integrity still need separate verification.
- Review findings posted to the owner of `scripts/validate_fleet_live.py`, NOT silently edited: missing socket import in TLS probe; success exit based only on agent health count; HTTP 200 treated as healthy without semantic validation. Await shared ownership agreement for that separate correction.
- Security: anonymous MCP access reconfirmed. D-014 records prior owner risk acceptance; it is not proof of safety. Owner notified; no auth activation/config change performed. Chat-exposed PAT not used/stored, revocation recommended.
- Not completed: exhaustive manual review of every source line; provider outage/failover drill; live DB restore/tenant-isolation proof; owner voice session; external trading/publishing operations. Do not equate these health probes or targeted tests with production readiness.
- Next: publish PR, obtain independent review and CI; owner alone authorizes merge/deploy. No production action is requested by this evidence-only task.
