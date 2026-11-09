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
- MERGED IMPLEMENTATION (PR #25, commit 79c1f75; deployment not verified): integrations/universe_orchestrator.py execute_universe_goal, with no simulation API set, previously returned status `dispatched`, real_agents 8, and a fixed synthesis without calling any peer. Grok's merged fix calls FleetClient.get_fleet_summary and returns status `not_executed` with probed online/total counts, or the probe error. It does not execute the goal on this path. Test evidence recorded in the commit: 5 passed (2 new plus 3 existing) on Server 2, 2026-11-08. This is test evidence, not production deployment evidence.
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
16. DEFECT FIXED IN REVIEW (PR #39, not on main): Stratex exchanges/exchange_implementations.py fabricated FILLED order results and unconditional cancel success (Binance/Bybit/OKX), built a live-endpoint python-binance client without testnet routing or authorization, and allowed unguarded Coinbase live orders. The production daemon does not route orders through these adapters (dashboard uses them read-only), so no fabricated order reached a venue; the code defect existed on main until PR #39. Follow-ups: Bybit/OKX real execution or removal, read-path data honesty in those adapters, Stratex tests in CI.
