# FRIDAY Universe — Master Plan

Single source of truth for project objectives, acceptance criteria and dependency order. All human and AI collaborators work from this file; there is no permanent AI hierarchy.
Read docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md and docs/collaboration/README.md before starting any task. Refresh GitHub and the shared coordination records before acting.

Roadmap statuses: NOT_STARTED | IN_PROGRESS | BLOCKED | IN_REVIEW | VERIFIED | DONE
Operational collaborator/task states are defined in docs/collaboration/README.md and docs/collaboration/WORK_BOARD.yaml.
- VERIFIED needs evidence (command output, log line, live check, or test run cited in handoff.md).
- DONE needs implementation, passing tests, verification, and all acceptance criteria met.
- A box is never ticked because code was written.

## 1. Vision and objectives
FRIDAY Universe is one integrated system of ten agents, run on two Oracle Cloud VMs, with FRIDAY as the central orchestrator. The owner wants FRIDAY to receive natural-language requests, decide which agent should act, assign the work, track it to completion, and report back. Trading (Stratex) stays on Binance testnet until the owner authorises otherwise.

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
- [ ] TASK-SEC-002 — Decide on git history rewrite to remove leaked strings. Owner: yes (confirmed). Execution: Claude, after PR merges are quiet. Destructive; coordinate with ChatGPT first.
- [ ] TASK-OPS-001 — OCI secrets present in main repo. Names verified via API; values unverified until run 42497059156 authenticates.
- [ ] TASK-OPS-002 — Verify OCI credentials work: the sniper run 42497059156 must show API calls, not authentication errors. Owner can read the live log on the run page.

### Phase 1 — Infrastructure and security foundations
- [ ] TASK-INF-001 — Audit Oracle infrastructure (both VMs: sizes, memory, disks, services). Evidence: `oracle_fleet_health`, systemd show output.
- [x] TASK-INF-002 — Set MemoryMax on FRIDAY-Voice. Status: VERIFIED by read-only systemd inspection on 2026-11-09: FRIDAY-Voice.service is active and loads `/etc/systemd/system/FRIDAY-Voice.service.d/memory.conf` with MemoryHigh=250M and MemoryMax=300M. No restart or configuration change was made in this session.
- [ ] TASK-SEC-003 — Bridge authentication: shared-secret authentication for /bridge, /mcp, /messages and /sse. Owner: ChatGPT. IN_REVIEW (PR #24); middleware/tests are on branch, but production activation remains unverified and requires runtime secret provisioning, MCP-client header compatibility, and owner-approved restart.
- [ ] TASK-SEC-004 — Secret-management audit and CI leak prevention. Owner: ChatGPT; IN_REVIEW in PR #31 (`chatgpt/TASK-SEC-004`). A root Gitleaks action scans PR/push change ranges; first run exposed shallow-fetch range failure, fixed by full commit graph; current scan run 42525462164 passed. Not merged or VERIFIED on main yet. Full-history exposure is separately tracked in TASK-SEC-002.
- [ ] TASK-INF-003 — Backup and recovery: verify Oracle DB backups and service restore steps.
- [ ] TASK-OPS-003 — Oracle sniper: confirm allocation loop works end to end; after success, promotion of the new instance is a manual owner decision.

### Phase 2 — Data foundation
- [ ] TASK-DATA-001 — Audit database architecture per agent (schemas, owners, connection strings by name only).
- [ ] TASK-DATA-002 — Verify memory isolation between agents (Memora namespaces `memora://<agent>/private`).
- [ ] TASK-DATA-003 — Test persistence and recovery for Memora and Stratex ledgers.

### Phase 3 — CI and delivery
- [ ] TASK-CI-001 — Fix VyralX/Futuris `app` package collision in CI (ChatGPT pushed fixes to main; not yet verified green).
- [ ] TASK-CI-002 — Get `main` fully green: all validation jobs pass on current HEAD. Owner: Claude. IN_PROGRESS; CI fixes have landed, but latest main/PR validation evidence remains red or incomplete.
- [ ] TASK-CI-003 — Fix run_workspace_test (venv has no pytest on Server 2).
- [ ] TASK-CI-004 — Narrow `.gitignore` bridge/** rule so bridge source can be committed deliberately.

### Phase 4 — Core agent foundations
- [ ] TASK-CORE-001 — Read and document each agent's entrypoint, routes, state, external calls (feeds ARCHITECTURE_AS_BUILT). Owner split in progress: Claude—FRIDAY; ChatGPT—IntelX (PR #32 addresses a live Oracle JSON processor defect found during this audit).
- [ ] TASK-CORE-002 — Remove fabricated success in universe_orchestrator. IMPLEMENTATION MERGED to main via PR #25 (commit 79c1f75); live path probes FleetClient and returns `not_executed` when no Universe API is configured. Tests recorded as 5 passed on Server 2, 2026-11-08. Deployment/runtime verification remains outstanding; therefore not VERIFIED or DONE.
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
- [ ] TASK-STR-001 — Stratex: confirm BINANCE_TESTNET=true on both units; add explicit ALLOW_LIVE_TRADING=false guard.
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
- IN_PROGRESS / IN_REVIEW: TASK-COLLAB-001, TASK-CI-002, TASK-SEC-003, TASK-SEC-004, TASK-API-001, TASK-DISPATCH-001, TASK-MIRROR-001, TASK-CTX-001, TASK-INT-001, TASK-FUT-001 and TASK-MEM-001 as tracked in handoff.md.
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
