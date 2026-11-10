# FRIDAY Universe — Master Plan

Single source of truth for the roadmap. Claude, ChatGPT, and Grok are equal collaborators working together through this file. The current plan is a shared roadmap, not a hierarchy; the owner is the final decision-maker.
Read docs/handoff.md and docs/ARCHITECTURE_AS_BUILT.md before starting any task.

Statuses: NOT_STARTED | IN_PROGRESS | BLOCKED | IN_REVIEW | VERIFIED | DONE
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

### Phase 0 — Owner actions (blocking external)
- [ ] TASK-SEC-001 — Rotate every provider key that appeared in public commit 46034a4. Status: owner reports DONE; re-verify in handoff.
- [ ] TASK-SEC-002 — Decide on git history rewrite to remove leaked strings. Owner: yes (confirmed). Execution: Claude, after PR merges are quiet. Destructive; coordinate with ChatGPT first.
- [ ] TASK-OPS-001 — OCI secrets present in main repo. Names verified via API; values unverified until run 42497059156 authenticates.
- [ ] TASK-OPS-002 — Verify OCI credentials work: the sniper run 42497059156 must show API calls, not authentication errors. Owner can read the live log on the run page.

### Phase 1 — Infrastructure and security foundations
- [ ] TASK-INF-001 — Audit Oracle infrastructure (both VMs: sizes, memory, disks, services). Evidence: `oracle_fleet_health`, systemd show output.
- [ ] TASK-INF-002 — Set MemoryMax on FRIDAY-Voice (currently no limit on a 956 MB host).
- [ ] TASK-SEC-003 — Bridge authentication: shared-secret authentication for /bridge, /mcp, /messages and /sse. Owner: ChatGPT. Status: IN_REVIEW (PR #24); production activation awaits runtime secret provisioning, both MCP clients' header compatibility and owner-approved restart.
- [ ] TASK-SEC-004 — Audit secret management: env files, CREDENTIALS.md (untracked, must stay untracked), GitHub secrets.
- [ ] TASK-INF-003 — Backup and recovery: verify Oracle DB backups and service restore steps.
- [ ] TASK-OPS-003 — Oracle sniper: confirm allocation loop works end to end; after success, promotion of the new instance is a manual owner decision.

### Phase 2 — Data foundation
- [ ] TASK-DATA-001 — Audit database architecture per agent (schemas, owners, connection strings by name only).
- [ ] TASK-DATA-002 — Verify memory isolation between agents (Memora namespaces `memora://<agent>/private`).
- [ ] TASK-DATA-003 — Test persistence and recovery for Memora and Stratex ledgers.

### Phase 3 — CI and delivery
- [ ] TASK-CI-001 — Fix VyralX/Futuris `app` package collision in CI (ChatGPT pushed fixes to main; not yet verified green).
- [ ] TASK-CI-002 — Get `main` fully green: all validation jobs pass on current HEAD. Owner: Claude. Status: IN_PROGRESS (PR #22 merged; further CI fixes under investigation).
- [ ] TASK-CI-003 — Fix run_workspace_test (venv has no pytest on Server 2).
- [ ] TASK-CI-004 — Narrow `.gitignore` bridge/** rule so bridge source can be committed deliberately.

### Phase 4 — Core agent foundations
- [ ] TASK-CORE-001 — Read and document each agent's entrypoint, routes, state, external calls (feeds ARCHITECTURE_AS_BUILT). Owner: ChatGPT (Cortex parallel audit); Status: IN_PROGRESS. Cortex source audit found missing route-level auth dependencies; remediation is in PR #26 and awaiting CI.
- [ ] TASK-CORE-002 — Remove fabricated success in universe_orchestrator (live path returns "dispatched" without calling any peer). Status: IN_PROGRESS after merge of PR #25 to main (2026-11-08 18:02 UTC). Deployment workflow #42507954757 succeeded; FRIDAY.service restarted at 18:03 UTC and /friday/health returned HTTP 200 at 18:07 UTC. Live goal invocation is still unverified; not DONE.
- [ ] TASK-CORE-003 — Add task records (TASK-ID, owner agent, status, result) so work can be assigned and tracked.

### Phase 5 — Agent APIs and communication
- [ ] TASK-API-001 — Implement /v1/task/execute on Forge and Sentinel, or stop routing typed tasks there (currently 404).
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
- [ ] TASK-MEM-001 — Memora: Oracle schema and vector-store audit.
- [ ] TASK-FUT-001 — Futuris: forecasting audit; DSN handling.
- [ ] TASK-INT-001 — IntelX: evidence pipeline audit.
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
- Verified: 0 tasks. Names of OCI secrets were checked via API; that is evidence of presence, not of correctness.
- Done: 0 (no task has met the DONE definition yet).
- Everything else: NOT_STARTED, or as noted in handoff.md.
