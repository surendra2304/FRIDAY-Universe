# FRIDAY Universe — Master Plan

Single source of truth for project objectives, acceptance criteria and dependency order. All human and AI collaborators work from this file; there is no permanent AI hierarchy.
Read docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md and docs/collaboration/README.md before starting any task. Refresh GitHub and the shared coordination records before acting.

Roadmap statuses: NOT_STARTED | IN_PROGRESS | BLOCKED | IN_REVIEW | VERIFIED | DONE
Operational collaborator/task states are defined in docs/collaboration/README.md and docs/collaboration/WORK_BOARD.yaml.
- VERIFIED needs evidence (command output, log line, live check, or test run cited in handoff.md).
- DONE needs implementation, passing tests, verification, and all acceptance criteria met.
- A box is never ticked because code was written.

## 1. Vision and objectives
FRIDAY Universe is one integrated system of ten agents, run on two Oracle Cloud VMs, with FRIDAY as the central orchestrator. The owner wants FRIDAY to receive natural-language requests, decide which agent should act, assign the work, track it to completion, and report back. Trading (Stratex) runs on Binance demo (owner-confirmed 2026-11-10); live trading requires explicit owner authorization and the ALLOW_LIVE_TRADING guard.

## 2. Canonical ten-agent architecture
1. FRIDAY — orchestrator, voice/desktop runtime, task dispatch (Server 1, :10000)
2. Inference — LLM provider gateway and routing (Server 1, :8001)
3. Memora — memory fabric, Oracle-backed (Server 1, :8002)
4. Stratex — futures strategy and execution, testnet only (Server 1, :8003)
5. Futuris — forecasting (Server 1, :8004)
6. IntelX — research and evidence (Server 1, :8005)
7. Forge — code generation and execution (Server 1, :8006)
8. Cortex — CRM and website operations (Server 2, :8009)
9. Sentinel — security operations and audit (Server 2, :8008)
10. VyralX — video intelligence and growth (Server 2, :8010)
Plus infrastructure: Caddy (Server 1), friday-bridge engineering MCP gateway (Server 2, :8011).
Source: AGENTS.yaml (declared) and docs/ARCHITECTURE_AS_BUILT.md (observed).

## 3. Phases in execution order (dependency-driven)

### Phase 0A — Multi-AI collaboration foundation
- [ ] TASK-COLLAB-001 — Establish the shared multi-AI collaboration centre at `docs/collaboration/`: roster, task board, file ownership, activity log, decisions, handoffs and templates. Use GitHub issue #35 for visible claims/releases/handoffs. Owner: ChatGPT; IN_REVIEW in PR #30 (`chatgpt/TASK-DOC-SYNC-001`), with overlapping independent bootstrap PR #36 from Vercel v0 (`v0/coordination-bootstrap`). Automated validation added via `scripts/validate_collaboration.py` and `.github/workflows/collaboration-registry.yml`; latest validator run 42596903311 passed on PR #30 head 5920161f. Consolidate both PRs' seven shared files before merge. Do not mark DONE until the directory, all three central-document links, file-conflict records, GitHub claim protocol and validator are reviewed and merged.

### Phase 0 — Owner actions (blocking external)
- [ ] TASK-SEC-001 — Rotate every provider key that appeared in public commit 46034a4. Status: owner reports DONE; re-verify in handoff.
- [x] TASK-SEC-002 — Git history rewrite to remove leaked strings. EXECUTED 2026-11-10 by ZAI after the owner-directed mass merge (18 PRs, zero open fleet-wide): git-filter-repo purge of 16 leaked credential literals across all 667 commits, live-tree sanitization first (env-var lookups), main force-pushed, all 27 stale remote branches deleted (single-branch repo), pre-rewrite bundle preserved offline by ZAI. See DECISIONS.md D-016. Owner follow-ups: revoke/rotate the leaked Telegram bot token (BotFather) and DuckDNS token.
- [ ] TASK-OPS-001 — OCI secrets present in main repo. Names verified via API; values unverified until run 42497059156 authenticates.
- [ ] TASK-OPS-002 — Verify OCI credentials work: the sniper run 42497059156 must show API calls, not authentication errors. Owner can read the live log on the run page.

### Phase 1 — Infrastructure and security foundations
- [ ] TASK-INF-001 — Audit Oracle infrastructure (both VMs: sizes, memory, disks, services). Evidence: `oracle_fleet_health`, systemd show output.
- [x] TASK-INF-002 — Set MemoryMax on FRIDAY-Voice. Status: VERIFIED by read-only systemd inspection on 2026-11-09: FRIDAY-Voice.service is active and loads `/etc/systemd/system/FRIDAY-Voice.service.d/memory.conf` with MemoryHigh=250M and MemoryMax=300M. No restart or configuration change was made in this session.
- [ ] TASK-SEC-003 — Bridge authentication: shared-secret authentication for /bridge, /mcp, /messages and /sse. Owner: ChatGPT. MERGED 2026-11-10 (PR #24, mass merge; middleware/tests now on main), but production activation remains unverified and would require runtime secret provisioning, MCP-client header compatibility, and owner-approved restart. OWNER DECISION 2026-11-10: the owner re-confirmed the unauthenticated bridge is an accepted risk ("No problem even if it is leaked") — see DECISIONS.md D-014. Production activation is therefore not requested; owner to decide PR #24 disposition (park or close).
- [ ] TASK-SEC-004 — Secret-management audit and CI leak prevention. Owner: ChatGPT; MERGED 2026-11-10 (PR #31, mass merge): a root Gitleaks action now scans PR/push change ranges (shallow-fetch range failure was fixed by full commit graph). ADB ADMIN password rotation EXECUTED 2026-11-10 by ZAI under this task (server-side rotation, new credential root-only on Server 1, all backup copies redacted on both servers) — see DECISIONS.md D-017. Historical exposure is purged per TASK-SEC-002.
- [ ] TASK-INF-003 — Backup and recovery: verify Oracle DB backups and service restore steps.
- [ ] TASK-OPS-003 — Oracle sniper: confirm allocation loop works end to end; after success, promotion of the new instance is a manual owner decision.

### Phase 2 — Data foundation
- [ ] TASK-DATA-001 — Audit database architecture per agent (schemas, owners, connection strings by name only). Owner: ZAI; IN_REVIEW (PR #41, stacked on PR #40) — audit in docs/ARCHITECTURE_AS_BUILT.md §20 + owner-authorized remediation §20.4 (2026-11-10): ADMIN-privileged DSNs removed from six env files across both servers with services restarted and verified healthy (correction: FRIDAY's FRIDAY_UNIVERSE_DB_URL was its own schema user, only the _ASYNC twin was ADMIN); dead ADMIN construction removed from deploy/setup_fleet.sh; Memora REDIS_URL=disabled and dead Qdrant vars removed (event bus verified working via Oracle event_log + HTTP polling); vyralx-autopilot TimeoutStartSec 3600→7200 with timer re-armed. MERGED 2026-11-10 (PR #41, mass merge). ADMIN password rotation: EXECUTED 2026-11-10 (see DECISIONS.md D-017). Remaining owner decisions: whether Server 1 ever gets Redis/Qdrant (TASK-DATA-003/TASK-OBS-001), autopilot total wall-clock budget (TASK-VYR-001).
- [ ] TASK-DATA-002 — Verify memory isolation between agents (Memora namespaces `memora://<agent>/private`). Owner: ChatGPT; IN_PROGRESS on chatgpt/TASK-DATA-002-memory-tenant-isolation; PR #38 is stacked on PR #37. Fixes include authenticated tenant pinning for the destructive horizon-sweep API and authentication/authorization of the mounted process-local access-controller compatibility endpoints. The latter now restricts grant/revoke/approval and global audit/report to the authenticated memora principal and binds self-service requests/checks to the caller. Focused Memora regression run 42658441949 PASS (12 passed, 1 warning); the Memora step of FRIDAY run 42658441937 PASS. Full FRIDAY API and monorepo validation were still in progress at last check. Remaining work: complete direct-read/search/share/revoke/graph/task-route private/shared/universal matrix and verify the canonical persistent policy surface; PR #38 must not merge before PR #37.
- [ ] TASK-DATA-003 — Test persistence and recovery for Memora and Stratex ledgers.

### Phase 3 — CI and delivery
- [ ] TASK-CI-001 — Fix VyralX/Futuris `app` package collision in CI (ChatGPT pushed fixes to main; not yet verified green).
- [x] TASK-PERSONA-001 — Warm friend + Jarvis persona for FRIDAY (owner directive 2026-11-10: "I want my Friday to talk to me like a friend and do all the tasks I said like the Jarvis for Iron Man"). Owner: ZAI; MERGED to main 2026-11-10 — persona blocks, greetings and proactive phrasing rewritten; strictly presentational, classic persona untouched. Evidence: tests/test_friday_persona.py 10/10; adjacent suites 35 passed / 1 pre-existing unrelated failure. Deployment + FRIDAY service restart to follow. See DECISIONS.md D-018.
- [ ] TASK-CI-002 — Get `main` fully green: all validation jobs pass on current HEAD. Owner: Claude; execution pass by ZAI 2026-11-10 under D-019 (owner granted full authority; Claude unreachable). Root causes of the 26+26 monorepo failures on head 7d712c1 fixed: requirements-ci.txt now carries the Stratex/Futuris test surface (pandas etc.); real Stratex AutoHedge rebalance TypeError repaired (symbol*price bug); monorepo module-cache hygiene added (tests/repo_isolation.py, surgical purge of ambiguous top-level packages); Memora core/apps made regular packages (namespace precedence); stub fleet accepts the documented synthetic bus actions; Cortex e2e authenticates as the FRIDAY service per merged PR #26; Forge browser routes moved under /api/v1/forge/*; VyralX media bootstrap gets its designed dev-SQLite path in tests; Futuris fail-closed stub aligned to the structlog contract; stale file contracts reconciled (db_viewer, docs/archive). Local evidence: 3390 passed / 0 failed (Redis-service tests local-excluded; they pass in CI). Remaining: post-merge green CI evidence on main for both Monorepo Structure and Safety CI runs; then the task can be closed.
- [ ] TASK-CI-003 — Fix run_workspace_test (venv has no pytest on Server 2).
- [ ] TASK-CI-004 — Narrow `.gitignore` bridge/** rule so bridge source can be committed deliberately.

### Phase 4 — Core agent foundations
- [ ] TASK-CORE-001 — Read and document each agent's entrypoint, routes, state, external calls (feeds ARCHITECTURE_AS_BUILT). Owner split: Claude—FRIDAY; ChatGPT—IntelX (PR #32 addresses a live Oracle JSON processor defect found during this audit). Cortex source audit found missing route-level auth dependencies; remediation is in PR #26 and awaiting CI.
- [ ] TASK-CORE-002 — Remove fabricated success in universe_orchestrator. IMPLEMENTATION MERGED to main via PR #25 (commit 79c1f75); live path probes FleetClient and returns `not_executed` when no Universe API is configured. Tests recorded as 5 passed on Server 2, 2026-11-08. Deployment workflow #42507954757 succeeded; FRIDAY.service restarted 2026-11-08 18:03 UTC and /friday/health returned HTTP 200 at 18:07 UTC. Live goal invocation is still unverified; not VERIFIED or DONE.
- [ ] TASK-CORE-003 — Add task records (TASK-ID, owner agent, status, result) so work can be assigned and tracked.

### Phase 5 — Agent APIs and communication
- [ ] TASK-API-001 — Implement `/v1/task/execute` on Forge and Sentinel, or stop routing typed tasks there. Owner: Claude; IN_REVIEW (PR #29 covers Sentinel; Forge still requires capability/route validation).
- [ ] TASK-API-002 — Standardise health endpoints (/health) across all ten agents and make AGENTS.yaml the source for ports.
- [ ] TASK-API-003 — Authentication matrix test: each agent accepts only its configured keys.

### Phase 6 — FRIDAY orchestration and task dispatch
- [ ] TASK-ORCH-001 — Replace keyword-substring routing (misroutes: "decode"→Forge, "trader-proof"→Stratex, "cashback"→Stratex, "webpage"→Cortex) with explicit intent classification and a tested routing table.
- [ ] TASK-ORCH-002 — Assignment and tracking: FRIDAY assigns a task to an agent, records it, and reports completion.
- [ ] TASK-ORCH-003 — Verify autonomous controller and fleet supervision code before claiming autonomy (GAP).

### Phase 7 — Inference and provider routing
- [ ] TASK-INF-LLM-001 — Audit provider key pools (names and counts only) and fallback behaviour.
- [ ] TASK-INF-LLM-002 — Verify provider failover under simulated outage.

### Phase 8 — Specialist agent capabilities
- [ ] TASK-STR-001 — Stratex: confirm BINANCE_TESTNET=true on both units; add explicit ALLOW_LIVE_TRADING=false guard. Owner: ZAI; IN_REVIEW in PR #39 (`zai/TASK-STR-001-live-trading-guard`). Guard implemented fail-closed across `exchanges/exchange_implementations.py` (permanent LIVE block, explicit ALLOW_LIVE_TRADING opt-in defaulting to false, testnet-routed client, fabricated FILLED orders removed) with 24 new + 17 updated tests passing locally. Production check (read-only, 2026-11-09): Server 1 .env has BINANCE_TESTNET=false / TRADING_MODE=FUTURES / BINANCE_ENV=demo. OWNER DECISION 2026-11-10: demo is the intended production venue (see DECISIONS.md D-015); the plan's testnet assumption is corrected accordingly. Not merged, not deployed.
- [ ] TASK-STR-002 — Stratex: confirm which venues are active (Binance Futures, MT5, cTrader).
- [ ] TASK-FOR-001 — Forge: security review of code-execution sandbox (it runs generated code).
- [ ] TASK-MEM-001 — Memora: Oracle schema and vector-store audit. Owner: ChatGPT; IN_REVIEW in PR #37 (`chatgpt/TASK-MEM-001-memora-oracle-vector-audit`). Fixes Oracle/SQLite vector tenant-ID ownership collisions, prevents adapter-owned commits of the caller's memory/event transaction, makes readiness truthful, declares SQLAlchemy's `greenlet` runtime dependency, and removes the unused 1536-dimension setting in favour of the actual 384-dimensional contract. Focused Memora regression run 42596147391 PASS (8 tests, 1 warning); full FRIDAY CI run 42596147378 PASS. Oracle live DB and external Qdrant collection/schema remain unverified; not merged/deployed.
- [ ] TASK-FUT-001 — Futuris: forecasting audit; DSN handling.
- [ ] TASK-INT-001 — IntelX: evidence pipeline audit. Owner: ChatGPT; IN_REVIEW (PR #32 `chatgpt/TASK-INT-001-intelx-json`) adds Oracle JSON bind/result compatibility defaults and a root-suite regression test. CI collection still being corrected; not merged, not deployed, and not yet VERIFIED.
- [ ] TASK-CTX-001 — Cortex: CRM and website operations audit (Server 2).
- [ ] TASK-SEN-001 — Sentinel: policy and audit-log audit.
- [ ] TASK-VYR-001 — VyralX: daemon and autopilot audit (Server 2).
- [ ] TASK-VOI-001 — FRIDAY-Voice: LiveKit worker audit and memory limit.

### Phase 9 — Cross-agent workflows and shared memory
- [ ] TASK-WF-001 — One end-to-end workflow through FRIDAY across at least three agents, with a recorded trace.

### Phase 10 — Reliability, recovery and observability
- [ ] TASK-OBS-001 — Health and restart alerting (services have Restart=always, so crash loops are silent today).
- [ ] TASK-OBS-002 — Rollback procedure for a bad deploy (deploy resets servers with git reset --hard).

### Phase 11 — Integration, security and production validation
- [ ] TASK-VAL-001 — Full fleet validation on live servers, with evidence per agent.
- [ ] TASK-VAL-002 — Security review of public ingress and bridge.

## 4. Dependencies (summary)
- TASK-CI-002 before any feature merge.
- TASK-SEC-003 before further bridge tooling is used by anything but the owner.
- TASK-CORE-001 before any agent change in Phases 5–8.
- TASK-CORE-003 before TASK-ORCH-002.
- TASK-API-001 before TASK-ORCH-001 routes typed tasks to Forge or Sentinel.

## 5. Security, reliability and production requirements
- No secrets in git, comments, logs or documents. Names only.
- Merges to main deploy to both servers. Review deployment impact in the PR.
- No production restart without owner authorisation for that restart.
- Stratex trades on testnet only until the owner authorises live trading in writing.

## 6. Testing and verification requirements
- Every code task has a passing test run cited in handoff.md.
- CI passes before merge. Fix root causes; never weaken tests to pass.
- Live checks use the public health endpoints and systemctl status, recorded with timestamps.

## 7. Current overall progress
- VERIFIED: no end-to-end production task is claimed VERIFIED from this GitHub-only review. GitHub-visible implementation merges are not deployment evidence.
- Merged implementation: TASK-DOC-001 (PR #21), TASK-CORE-002 (PR #25), and CI-related PR #22. Their production/runtime verification is separate.
- IN_PROGRESS / IN_REVIEW: TASK-COLLAB-001, TASK-CI-002, TASK-SEC-003, TASK-SEC-004, TASK-API-001, TASK-DISPATCH-001, TASK-MIRROR-001, TASK-CTX-001, TASK-INT-001, TASK-FUT-001, TASK-MEM-001 and TASK-DATA-002 as tracked in handoff.md.
- PR #34 (Claude) adds CI root-cause changes under TASK-CI-004; its FRIDAY CI and heavy-task image checks passed, but two monorepo validation jobs failed. Independent review comment #6732764298 records outstanding stub-fleet false-success, real-fleet override, dependency and overlapping PR findings. Its file overlap with PR #23 and PR #28 is recorded in docs/collaboration/FILE_OWNERSHIP.yaml.
- VERIFIED infrastructure control: TASK-INF-002 (FRIDAY-Voice MemoryMax=300M, MemoryHigh=250M) based on 2026-11-09 systemd evidence; this is not a claim that the voice agent's event-loop warnings are resolved.
- All ten agents remain canonical and integrated; VyralX remains agent ten.
- Multi-AI collaboration centre is proposed in PR #30 and independently bootstrapped in PR #36; neither is merged to main. The shared GitHub claim thread is issue #35. The dedicated registry validator passed on latest PR #30 head `5920161f` in run 42596903311. The broad monorepo validations 42596903328 and 42596903017 were in progress at the latest status check; previous-head results remain separately recorded in handoff.md. PR #30 and #36 overlap on seven registry files and must be consolidated before merge. Read docs/collaboration/README.md and refresh TEAM_ROSTER.yaml, WORK_BOARD.yaml and FILE_OWNERSHIP.yaml before claiming work.
- Task-ID reconciliation required: PR #23 uses TASK-CI-003 for a CI install/test-environment change while this plan currently defines TASK-CI-003 as the Server 2 workspace test runner. PR #34 uses TASK-CI-004 for root-cause CI fixes while this plan currently defines TASK-CI-004 as the bridge/** .gitignore change. Do not silently rewrite acceptance criteria; reconcile IDs with Claude and the owner.


## Memora audit update — 2026-11-09

- TASK-MEM-001 is IN_REVIEW in PR #37 (`chatgpt/TASK-MEM-001-memora-oracle-vector-audit`); no merge or production deployment.
- Focused vector regression run 42596147391 PASS (8 passed, 1 warning); FRIDAY Universe CI/CD run 42596147378 PASS, including all existing FRIDAY test suites, the Memora vector test step, HTTP/API tests and artifact upload.
- Broad monorepo validators 42596147434 and 42596147572 were still in progress at the latest status check. Do not infer their result from the focused/FRIDAY workflows.
- Oracle tenant-safe MERGE and transaction savepoint behavior are covered by a SQL contract test and SQLite transaction regressions respectively; live Oracle DB execution was not performed. External Qdrant collection dimension remains unverified.


## TASK-DATA-002 — cross-agent memory isolation (2026-11-09; in progress)

- PR #38 is open on chatgpt/TASK-DATA-002-memory-tenant-isolation, stacked on PR #37. It closes a confirmed cross-tenant maintenance control gap in POST /v1/memories/sweep-horizon: body-supplied tenant IDs are now rejected unless they match the authenticated Memora service identity's tenant; the API always invokes the sweeper with the resolved tenant. The trusted internal background worker's all-tenant mode is unchanged.
- Regression results on PR #38 head 0b8252529f36d37c51907cfbd1dc3fd6149b6bfb: FRIDAY Universe CI/CD run 42598678632 PASS. Memora regression group: 17 passed, 1 warning. HTTP/API suite: 45 passed. Memora Vector Regression run 42598678508 PASS (8 passed, 1 warning).
- Broad monorepo Structure/Safety checks 42598678658 and 42598678539 were still running at the latest check; no green result is claimed for those.
- This does not close the whole task. The remaining private/shared/universal namespace audit and adversarial route matrix are still in progress. PR #38 must not be merged before its dependency PR #37.


### TASK-DATA-002 incremental security finding — 2026-11-09

The main Memora app mounted `memory_access_controller.router` under `/api/v1`, while the legacy process-local grant, approval and audit handlers had no authentication dependencies. PR #38 now requires authenticated agent credentials on all seven compatibility routes; only the `memora` service identity can mutate grants or inspect global audit/report state, and request/check operations are bound to the authenticated subject. The compatibility engine remains explicitly process-local and is not the canonical tenant-aware persistent policy store. Focused Memora run 42658441949 passed (12 tests, 1 warning); the Memora step in FRIDAY CI run 42658441937 passed. This work is unmerged and not deployed.


### TASK-DATA-002 incremental finding — explicit memory-share authorization — 2026-11-09

A second authorization defect was found in the canonical write path: the `shared_with` parameter previously inserted `MemorySharedAgent` entries after a namespace write decision only. PR #38 now requires owner control and an explicit policy `share` decision, rejects wildcard/self/unregistered/cross-tenant recipient names, and provisions tenant-scoped read/query namespace grants alongside the memory membership entry. This is performed in the existing write transaction and across new, duplicate and idempotent replay paths; canonical implicit team-shared behavior is unchanged. Focused Memora run 42663206883 passed (16 tests, 1 warning); full FRIDAY run 42663207108 passed the Python and HTTP/API suites, with Docker skipped for the PR event. Monorepo checks remained pending at the last observation. Unmerged and undeployed.


### TASK-DATA-002 incremental finding — truthful task storage receipts — 2026-11-09

The task endpoint's ActionReceipt builder previously hard-coded Oracle and durable-write claims even in a SQLite/non-durable test environment. PR #38 now sources active backend, durability and durability class from Memora's canonical `storage_receipt()`; successful store evidence only reports `durable_write=true` when the active storage contract says it is durable. A route regression test was added and wired into the focused Memora and FRIDAY workflows. This change remains unverified until those new CI runs complete; PR #38 remains unmerged/undeployed.
