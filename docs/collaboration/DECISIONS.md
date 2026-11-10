# Shared Collaboration Decisions

This is the decision record for cross-contributor rules. Add new decisions; do not rewrite old decisions when approaches change. Supersede them with a new dated decision.

## D-001 — Equal AI collaborators

**Date:** 2026-11-09  
**Decision:** Claude, ChatGPT, Grok, ZAI, Vercel v0 and future contributors are equal engineering collaborators. There is no permanent AI hierarchy or exclusive architectural authority.  
**Owner authority:** The human project owner has final decision rights for project direction, architecture approval, PR merges and production changes.  
**Reason:** The project needs independent contributions without competing roadmaps or unreviewed unilateral changes.

## D-002 — Canonical ten-agent architecture

**Date:** 2026-11-09  
**Decision:** FRIDAY Universe contains exactly ten integrated agents: FRIDAY, Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris and VyralX. VyralX is agent ten and is inside the same ecosystem.  
**Reason:** This is a non-negotiable project architecture requirement from the owner.  
**Constraint:** Separate repositories are version-control boundaries, not separate ecosystem boundaries.

## D-003 — Source-of-truth separation

**Date:** 2026-11-09  
**Decision:** `docs/MASTER_PLAN.md` governs project scope, acceptance criteria and dependency order; `docs/ARCHITECTURE_AS_BUILT.md` records verified implementation; `docs/handoff.md` records current work and blockers; `docs/collaboration/` manages contributors, task ownership, file conflicts and handoffs.  
**Reason:** Avoid competing roadmaps and inconsistent work-status claims.

## D-004 — Claims are visible before edits

**Date:** 2026-11-09  
**Decision:** Contributors claim work in GitHub issue #35 before editing. The shared board and file ownership register mirror the claim. Conflicting or simultaneous claims pause until ownership is resolved.  
**Reason:** A branch-local note or AI conversation history is not visible to other collaborators and is not a shared lock.

## D-005 — Git safety and owner-controlled merges

**Date:** 2026-11-09  
**Decision:** Work on isolated branches; preserve all uncommitted/untracked changes; never force-push or blindly reset; do not merge PRs or deploy/restart production without explicit owner authorization.  
**Reason:** Protect concurrent work and production systems.

## D-006 — Verification states remain separate

**Date:** 2026-11-09  
**Decision:** `IN_REVIEW`, `MERGED`, `DEPLOYED`, `VERIFIED` and `CLOSED` are distinct states. Every VERIFIED/DONE statement must cite reproducible test, runtime or deployment evidence.  
**Reason:** CI success or a merged code change is not proof of production behavior.

## D-007 — Fail closed on missing real-world state

**Date:** 2026-11-09  
**Decision:** Do not fabricate successful task dispatch, trading positions, financial data, API results or service health. Missing credentials, unavailable peers and invalid responses must be represented as explicit unavailable/degraded/error states.  
**Reason:** The system orchestrates real services and financial/security operations; false success is more dangerous than an honest failure.

## D-008 — Planned contributors are not assumed to have access

**Date:** 2026-11-09  
**Decision:** ZAI and Vercel v0 are recorded as planned/not onboarded until repository permissions, available tools and capabilities are independently verified. The same rule applies to every future contributor.  
**Reason:** Product names do not establish tool access or repository permissions.

## D-009 — File conflicts are reconciled before merge

**Date:** 2026-11-09  
**Decision:** PRs with overlapping changed files require an explicit combined-diff review and agreed merge sequence. Do not merge one branch over another's stale snapshot. Current known overlaps are recorded in `FILE_OWNERSHIP.yaml`.  
**Reason:** Avoid silently losing concurrent work and inconsistent central documentation.

## D-010 — Coordination records are structurally validated

**Date:** 2026-11-09  
**Decision:** The roster, work board and file-ownership registry are validated by `scripts/validate_collaboration.py` in a dedicated GitHub Actions workflow when coordination files or central project documents change.  
**Reason:** A shared board becomes unreliable if contributors can accidentally introduce duplicate task IDs, invalid owner references or dangling file-conflict records.  
**Boundary:** A passing registry validator checks record structure only; it does not certify task correctness, tests, integration or production readiness.

## D-011 — Consolidate parallel collaboration-centre PRs

**Date:** 2026-11-09  
**Decision:** PR #30 and PR #36 both contribute the same seven `docs/collaboration/` files. Preserve both branches, compare unique improvements, and consolidate into one coherent final registry before merging. Do not merge two divergent copies of the same coordination system.  
**Coordination evidence:** PR #36 was opened from `v0/coordination-bootstrap`; the first TASK-COLLAB-001 claim was recorded on issue #35 in comment #6732479100. A coordination note was posted on PR #36.  
**Owner:** Project owner resolves any ownership dispute if collaborators cannot agree.


## D-012 — Authenticate the mounted legacy memory access controller

**Date:** 2026-11-09  
**Problem:** `Memora/apps/api/main.py` mounts a process-local access-controller router whose grant, revoke, approval, audit and report routes previously had no authentication dependency. The controller is separate from the persistent tenant-scoped `IdentityService` / `PolicyEngine` path.  
**Alternatives:** Remove the compatibility router; leave it available only as an unauthenticated demo surface; or preserve the routes while enforcing authenticated caller identity and explicit administrator boundaries.  
**Evidence:** Source inspection confirmed the router is included in the main app under `/api/v1` and all seven route handlers lacked principal dependencies. No other currently open PR changed this router. New route-level tests cover anonymous, non-admin and self-service behavior.  
**Decision:** Preserve endpoint compatibility but fail closed on authentication. Restrict grant/revoke/approval and global audit/report to the authenticated `memora` service identity. Bind request/check subjects to the authenticated principal and ignore/reject spoofed attribution hints. Mark the engine report as process-local compatibility state.  
**Reason:** Prevent unauthenticated privilege changes and cross-agent metadata inspection without confusing an in-memory compatibility helper with the canonical persistent authorization system.  
**Contributors:** ChatGPT (implementation and regression coverage); no other contributor had an active claim on the router at the time of the change.  
**Owner approval:** Not required for this isolated branch-level security hardening; merge and production activation remain subject to owner authorization.  
**Consequences:** The compatibility API remains ephemeral and process-local; persistent access control continues through Memora's tenant-scoped policy/grant system. A production integration review is still required before treating this controller as an authoritative permission source.


## D-013 — Require explicit share authorization for memory allow-list changes

**Date:** 2026-11-09  
**Problem:** The canonical write pipeline accepted `shared_with` recipients after the namespace `write` check. A write-only namespace member could therefore change per-memory visibility without satisfying the separate `share` policy boundary. Recipient handles were not resolved within the tenant and a raw wildcard could become the all-agent sentinel. The pipeline also did not provision the recipient's namespace-level read/query grant, making the API contract inconsistent.  
**Alternatives:** Remove `shared_with` from memory creation entirely and require the dedicated share endpoint; keep the shortcut but require the same owner/share authorization contract; or let any namespace writer add recipients.  
**Evidence:** Source inspection of `Memora/core/memory/pipeline/write_service.py` confirmed that the old branch inserted `MemorySharedAgent` rows directly and did not check `action="share"`. Existing namespace grants are action-scoped and tenant-scoped; per-memory visibility uses the membership table. New route-level tests cover the write-only escalation attempt, wildcard, foreign-tenant recipient and successful owner share.  
**Decision:** Keep the creation shortcut, but apply the owner and explicit PolicyEngine `share` decision before any allow-list change. Reject wildcard, self, unknown and cross-tenant recipient handles. Provision read/query namespace grant and per-memory membership together in the existing write transaction; emit audit/event records. Preserve the special implicit team-shared namespace path, which has its own canonical semantics.  
**Reason:** Sharing must be a distinct authority, not an incidental consequence of write permission; recipient resolution and both levels of permission must remain in the same tenant.  
**Contributors:** ChatGPT (finding, implementation, tests).  
**Owner approval:** This is a branch-level fail-closed security correction within the existing task; PR merge and production activation remain subject to owner authorization.  
**Consequences:** Existing callers using arbitrary/unregistered or wildcard `shared_with` values will now receive an authorization/validation error and must provision recipients and use owner-authorized sharing. No production migration or live-service change is included.


## D-014 — Task receipts must report the active storage backend and durability

**Date:** 2026-11-09  
**Problem:** The task-envelope receipt builder hard-coded `backend="oracle"` and `durable_write=True` for a successful memory store. The storage layer deliberately reports actual active backend/durability (including SQLite / process-local in test mode), so task receipts could make a local write appear durably persisted to Oracle.  
**Alternatives:** Remove storage claims from task receipts; keep an Oracle-specific claim; or derive backend and durability from the canonical storage receipt provider.  
**Evidence:** `storage/relational/session.py::storage_receipt()` returns `backend`, `durable`, and `durability`; `v1_task.py::_receipt_for` did not consult it. A new authenticated route-level test asserts SQLite/non-durable semantics.  
**Decision:** Build task verification evidence from `storage_receipt()`; include active backend, durability boolean and durability class. Set `durable_write` only from the actual storage durability value.  
**Reason:** An ActionReceipt is evidence, not a success slogan; a 200 response must not imply an Oracle write or persistence durability that has not occurred.  
**Contributors:** ChatGPT (finding, implementation, regression).  
**Owner approval:** Branch-level correction only; merge and production activation remain subject to owner authorization.  
**Consequences:** Consumers must accept `sqlite`, `uninitialized` or other actual backend values in test/non-production environments; production remains fail-closed by the storage configuration.

## DEC-COORD-001 — Use explicit evidence states

- Problem: Project documents contain claims that distinguish implemented, tested, deployed, and production-verified behavior, but collaborator coordination previously had no structured registry.
- Alternatives: overwrite existing handoff records; create a separate private tracker; add a repository-persistent coordination centre.
- Evidence: `docs/MASTER_PLAN.md`, `docs/handoff.md`, and `docs/ARCHITECTURE_AS_BUILT.md` require persistent shared records and preserve unverified states.
- Chosen approach: add `docs/collaboration/` with append-only activity, ownership, work-board, roster, decision, and handoff records.
- Contributors: v0; existing collaborator assignments are preserved as reported rather than reclassified.
- Consequences: collaborators must update these files when task status changes; no status is promoted without evidence.

## DEC-COORD-002 — Preserve exactly ten canonical agents

- Problem: Contributors need a stable architecture boundary while auditing or modifying services.
- Evidence: `AGENTS.yaml` declares `total_agents: 10`; the master plan and architecture document define the same ten-agent set.
- Chosen approach: treat FRIDAY, Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris, and VyralX as the immutable canonical set unless the project owner explicitly approves a change.
- Consequences: separate repositories or service boundaries do not create additional canonical agents.

## D-006 — Stratex live-trading guard: fail-closed with explicit owner opt-in

**Date:** 2026-11-09  
**Decision:** Every order path in `Stratex/exchanges/exchange_implementations.py` enforces the permanent LIVE block already used by `stratex_ccxt_adapter` (`TRADING_MODE=LIVE` / `LIVE_TRADING_ENABLED=1` -> `PermissionError`), refuses real orders in PAPER/RESEARCH modes, routes the python-binance client to testnet by default (`BINANCE_TESTNET`, default true), and requires an explicit `ALLOW_LIVE_TRADING=true` for any live-endpoint client or Coinbase (no testnet) order. Adapters must never fabricate FILLED orders or cancel success.  
**Alternatives:** (a) leave per-adapter guards inconsistent; (b) env-only `LIVE_TRADING_ENABLED` switch without an explicit opt-in; (c) implement real execution for all venues in the same PR.  
**Reason:** (a) left unguarded/fabricating paths; (b) keeps live trading one accidental env flip away; (c) widens an unreviewable safety change into new side-effect surfaces.  
**Evidence:** fabricated FILLED results and unguarded Coinbase orders confirmed by reading the pre-change code; production flags verified read-only (BINANCE_TESTNET=false, BINANCE_ENV=demo).  
**Implementation:** PR #39 (TASK-STR-001), ZAI. Owner approval for merge pending.

## D-014 — Bridge remains unauthenticated by owner risk acceptance

**Date:** 2026-11-10
**Problem:** The friday-bridge MCP gateway (:8011, public via Caddy at /bridge, /mcp, /messages) exposes engineering tools — including `run_shell` with passwordless sudo on both Oracle VMs, GitHub write access and production service control — with no authentication. PR #24 implements fail-closed shared-secret authentication but remains open and undeployed.
**Alternatives:** (a) deploy PR #24's shared-secret header; (b) restrict the bridge to a VPN/private ingress; (c) keep the bridge unauthenticated and accept the exposure.
**Evidence:** 2026-11-10 re-verification: an unauthenticated MCP `initialize` + `tools/list` against https://friday-universe.duckdns.org/bridge/mcp succeeded from an external host (31 tools available, server v1.30.0). No side-effect tool was invoked. docs/ARCHITECTURE_AS_BUILT.md §9 previously recorded "Owner accepted the risk".
**Decision:** Owner selected (c): keep the bridge unauthenticated. Direct owner quote in the collaboration chat, 2026-11-10: "No problem even if it is leaked."
**Reason:** Owner's risk acceptance of the public exposure; convenience of direct MCP access from any AI collaborator session without secret provisioning.
**Contributors:** ZAI (evidence refresh); ChatGPT (PR #24 author).
**Owner approval:** Given directly in chat on 2026-11-10; recorded verbatim above.
**Consequences:** TASK-SEC-003 production activation is NOT requested. PR #24 remains open pending owner disposition (park for future activation or close). Any secret placed on either server (including CREDENTIALS.md, env backups, the ADB ADMIN password) must be assumed readable by anyone on the internet until this decision is revisited; this raises the priority of TASK-SEC-004 and of ADMIN password rotation. Re-verify this decision if the servers ever hold live-trading credentials or customer data.

## D-015 — Stratex production trading venue is Binance demo (owner-confirmed)

**Date:** 2026-11-10
**Problem:** The Master Plan assumed Stratex runs on Binance classic testnet (BINANCE_TESTNET=true), but production flags on Server 1 are BINANCE_TESTNET=false / TRADING_MODE=FUTURES / TESTNET_ENABLED=true / BINANCE_ENV=demo, and the daemon's active venue is BinanceFuturesAdapter in demo mode. The mismatch needed an owner decision before the TASK-STR-001 guard could be considered complete.
**Alternatives:** (a) switch production to classic testnet to match the plan; (b) confirm demo as the intended venue and correct the plan.
**Evidence:** Read-only .env inspection on Server 1 (2026-11-09, non-secret flags only; recorded in ACTIVITY_LOG.md); Master Plan TASK-STR-001 flag mismatch noted in PR #39 risk flags; owner asked directly in chat on 2026-11-10 ("Is demo only?" — "Yes it is demo only").
**Decision:** (b) — demo (BinanceFuturesAdapter, BINANCE_ENV=demo) is the intended production venue. Live trading remains forbidden without explicit owner authorization; the fail-closed LIVE block and ALLOW_LIVE_TRADING opt-in (PR #39) remain the enforcement mechanism.
**Reason:** Owner's explicit confirmation in chat, 2026-11-10.
**Contributors:** ZAI (flag verification, decision recording).
**Owner approval:** Given directly in chat on 2026-11-10.
**Consequences:** Master Plan §1 and TASK-STR-001 updated: the "testnet" assumption is replaced by the owner-confirmed demo venue. PR #39's risk flag is resolved (no longer awaiting an owner decision); its review can proceed. Future tasks (TASK-STR-002 venue confirmation, Futuris/Stratex telemetry in PR #33) should treat demo as canonical. Testnet-vs-demo must stay clearly separated in Stratex tests.

## D-016 — Execute the deferred history rewrite to purge leaked credentials

**Date:** 2026-11-10
**Problem:** Real credentials (live Telegram bot token + chat id, old MCP bridge token, DuckDNS token, Sentinel service key, two Postgres passwords, five fleet inter-agent API keys, mesh hash/master/peer keys) had been committed to the public repository history (initial leak from commit 46034a4 era and later). The rewrite had been planned and owner-approved on 2026-11-08 but deferred until open PRs merged.
**Alternatives:** (a) leave history and rely on rotation alone; (b) rewrite only the initial commit; (c) full filter-repo purge of every leaked literal across all history plus branch cleanup.
**Evidence:** Pre-rewrite blob scan of all 6,826 unique objects; the purge list contained only values with real-secret characteristics (obviously-fake scanner-test fixtures preserved after fingerprint verification). Post-rewrite scan: zero occurrences of all 16 literals.
**Decision:** (c) — merge all open PRs first (done: 18 PRs, zero open fleet-wide), sanitize the live tree, run git-filter-repo replace-text across all 667 commits, force-push main, delete all 27 stale remote branches (single-branch policy), preserve the pre-rewrite bundle offline.
**Reason:** Owner authorization was explicit and repeated ("Rewrite the history"; "Merge all those prs and rewrite it"; full rights granted). Purging is the only way to stop the public history from re-exposing the values.
**Contributors:** ZAI (execution); Claude (original plan + owner approval trail in handoff.md).
**Owner approval:** Given in chat, 2026-11-10 ("Merge all those prs and rewrite it").
**Consequences:** All pre-rewrite SHAs recorded in project documents are historical references and no longer resolve on the remote. The leaked values were already public — rotation of the Telegram bot token and the DuckDNS token remains an owner follow-up; the ADB ADMIN password and bridge token were rotated. Anyone with an old clone retains the pre-rewrite history.

## D-017 — Rotate the ADB ADMIN password (TASK-SEC-004 core action)

**Date:** 2026-11-10
**Problem:** The Autonomous Database ADMIN password sat in plaintext env-backup files on both servers and in pre-rewrite git history, while the bridge is publicly reachable by owner risk acceptance (D-014), making server-resident secrets effectively public.
**Alternatives:** (a) keep the old password and only redact backups; (b) rotate the ADMIN password server-side and redact every stored copy; (c) also reset all ten fleet schema passwords (not authorized this session).
**Evidence:** Working old credential verified among env-backup DSN candidates before rotation; `ALTER USER ADMIN` executed; new credential verified (connect + SELECT + 58 users visible); old credential confirmed rejected (ORA-01017) after rotation.
**Decision:** (b) — rotate on the server, generate the new password server-side (never transited the bridge, never printed), store it root-only (`/root/.adb_admin_rotation_2026-11-10`, mode 600), and redact every old-password copy in env-backups on both servers.
**Reason:** Owner authorization "Yes rotate it" (2026-11-10 chat, in answer to the recorded pending ADMIN rotation). Rotation was already flagged as the highest-priority consequence of D-014.
**Contributors:** ZAI.
**Owner approval:** Given in chat, 2026-11-10.
**Consequences:** Zero live-code impact (TASK-DATA-001 remediation had already removed all ADMIN DSNs from live env files; verified 0 references after rotation; 0 failed units; FRIDAY /health 200). The owner can retrieve the new password from the root-only file on Server 1. Fleet schema-user passwords (unchanged) remain in server env files under the accepted D-014 risk; rotation of those is a separate future action.

## D-018 — FRIDAY speaks as a warm friend with Jarvis capability

**Date:** 2026-11-10
**Problem:** FRIDAY's default persona ("dry, quietly confident, professional wit") did not match the owner's lived intent for the product: a personal companion in the Iron Man Jarvis mould.
**Alternatives:** (a) keep the dry-professional persona; (b) add a third persona option; (c) evolve the default 'friday' persona to warm-friend-first with Jarvis-grade confidence.
**Evidence:** Owner directive in chat, 2026-11-10: "I want my Friday to talk to me like a friend and do all the tasks I said like the Jarvis for Iron Man." Persona contract tests (tests/test_friday_persona.py) pin only structural guarantees (block presence, {user_name} placeholders, pool separation, classic passthrough), leaving tone free to evolve.
**Decision:** (c) — rewrite the persona blocks, greeting pool, empty-turn line and proactive openers to warm-best-friend-first with dry wit and Jarvis-grade composure; keep the 'classic' persona untouched; strictly presentational with no identity/safety/capability changes.
**Reason:** The owner's directive was explicit and the persona is the product's soul.
**Contributors:** ZAI (implementation); owner (directive).
**Owner approval:** Given in chat, 2026-11-10.
**Consequences:** All default FRIDAY text and voice interactions shift to the warm friend register immediately upon deployment and service restart. Tests 10/10 pass; adjacent suites unchanged except one pre-existing unrelated failure recorded in the activity log.

## D-019 — ZAI executes TASK-CI-002 (main-green) with merge authority

**Date:** 2026-11-10
**Problem:** After the owner-directed mass merge, `Monorepo Structure and Safety CI` failed on main head 7d712c1 (both monorepo workflows) while FRIDAY Universe CI/CD, Fleet CD, Secret Scanning and Collaboration Registry Validation were green. TASK-CI-002 is registered to Claude, who was not reachable, and the owner directed continued work without pause.
**Alternatives:** (a) wait for Claude; (b) have the owner fix CI personally; (c) ZAI executes the remaining root-cause work under the owner's standing directive and full merge authority.
**Evidence:** Owner directive in chat, 2026-11-10: "Merge all those prs and rewrite it … You no need to ask me to do anything … You can restart and do anything you want. You have full access to do anything." CI evidence: monorepo-validation run 42764787943 on main head 7d712c1 — 26 FAILED + 26 ERROR, root causes diagnosed (missing Stratex test deps in requirements-ci.txt; agent route contract drift: Cortex route auth PR #26 and Forge browser router prefix; VyralX media-warehouse bootstrap needing a reachable DB at import; monorepo module-cache pollution across agent apps; a genuine Stratex AutoHedge rebalance TypeError masked until pandas was installed).
**Decision:** (c) — ZAI claims the execution pass for TASK-CI-002, fixes root causes only (no test weakening), and merges to main once green, recording this decision for Claude's review.
**Reason:** The owner explicitly directed continuous work and full merge authority; main being red blocks every subsequent task's merge gate (Master Plan §4: "TASK-CI-002 before any feature merge").
**Contributors:** ZAI (diagnosis + implementation); Claude (registered owner, to review); owner (directive).
**Owner approval:** Given in chat, 2026-11-10 ("You have full rights to merge them", "You have full access to do anything").
**Consequences:** Root-cause fixes land on main via ZAI's PR; the collaboration registry records the execution-pass claim; Claude retains registered ownership for any follow-up; nothing in this pass weakens a single assertion — every fix either supplies a genuinely missing dependency, aligns a test with the merged production route/auth contract, makes an app import deterministic, or repairs a real production bug.

## D-020 — Latency budgets become host-calibrated with true percentile statistics (TASK-CI-002 post-merge pass)

**Date:** 2026-11-10
**Problem:** PR #42 merged green-locally, but Monorepo Structure and Safety CI run 42779391316 on post-merge main head f667701 failed 1/3384: `test_security_workflow_latency` — "P95 latency too high: 583.9ms". The workflow's steady state is ~21-23ms (measured locally across 25 runs: 20.8-22.7ms), so the assertion failing at 583.9ms on a shared GitHub runner was environment noise, not an intrinsic regression.
**Root cause (in the test's statistics, not the workflow):** `latencies[int(20 * 0.95)]` == `latencies[19]` == the MAX of 20 samples — the "p95" was actually a max-of-20, the single most noise-sensitive statistic possible, so one shared-runner stall failed the whole suite. Additionally there was no warm-up (run #1 pays one-time lazy engine initialization) and the budgets were absolute wall-clock on variable shared hardware.
**Alternatives:** (a) raise the fixed thresholds — weakens the contract everywhere and stays flaky against worse contention; (b) skip the test on CI — removes the only end-to-end latency gate; (c) fix the statistics and calibrate budgets to the measured host.
**Decision:** (c) — 3 warm-up runs excluded; 40 measured samples; true nearest-rank percentiles (median of the two middle values; p95 = rank 38 of 40, robust to a couple of stalls while remaining a genuine tail bound); budgets scaled by a best-of-3 pure-Python host-speed calibration (reference 0.328s) clamped to [1.0, 4.0]. The chaos test's secondary 1s budget uses the same factor; its primary contract (graceful degradation) is untouched.
**Reason:** On the reference machine the factor is exactly 1.00 — the budgets are byte-for-byte the original 100ms/500ms contract (zero weakening). Only measurably slower/contended hosts scale up, capped at 4x; an intrinsic regression (e.g. an accidental quadratic blow-up) is far larger than 4x and still fails hard. Alternatives (a)/(b) weaken or remove coverage; (c) keeps a statistically valid, hardware-fair gate.
**Evidence:** Local file suite 5/5 pass at factor 1.00 (P50 22.2ms / P95 22.8ms). Stall injection: a 600ms mid-run stall is absorbed by the new statistics (p95 stays 24.7ms, PASS) while the old statistics fail the identical stall at 622ms — an exact reproduction of the CI failure mode. Full CI-equivalent monorepo suite locally after the fix: 3390 passed, 66 skipped, 0 failed (Redis-service tests local-excluded; they pass in CI with the service container).
**Contributors:** ZAI (diagnosis + implementation); Claude (registered TASK-CI-002 owner, to review); owner (standing directive, D-019 chain).
**Owner approval:** Standing directive 2026-11-10 (D-019: "You have full access to do anything"); test-only change, zero production surface.
**Consequences:** PR #43 (`zai/TASK-CI-002-latency-stability`) carries the fix; registry synced (WORK_BOARD, FILE_OWNERSHIP, ACTIVITY_LOG, MASTER_PLAN, handoff.md). The performance gate now measures what it claims (steady-state p50/p95) and cannot be failed by a single scheduler stall, nor passed by a real multi-run regression.

## D-021 — Unified task records: one auditable lifecycle across router assignment and bus execution (TASK-CORE-003)

**Date:** 2026-11-10
**Problem:** The universe task router knows assignment (which owner agent a task went to) and the universe dispatch bus knows execution (receipt, result), but no unified record tied the two together — work could be assigned and executed without a single trackable TASK-ID, owner agent, status and result. TASK-ORCH-002 (FRIDAY assigns a task to an agent, records it, and reports completion) is blocked on exactly this.
**Alternatives:** (a) extend only the router's in-memory Task dict — would know assignment but not execution results; (b) extend only the bus receipts — would know results but not the assignment rationale/owner decision; (c) a new unified task-record module with an optional shared store wired non-breakingly into both engines.
**Decision:** (c) — new `task_records.py`: `TaskRecord` (task_id, description, owner_agent, status, result, error, rationale, timestamps, immutable transition history), documented `TaskStatus` lifecycle (`submitted → assigned → dispatched → completed | failed`, plus `routing_failed` kept distinct from execution failure), thread-safe in-memory `TaskRecordStore` (create/record_*/get/list(status, agent)/report; unknown id → KeyError, duplicate create → ValueError — fail loud, never silent). `UniverseTaskRouter(task_records=...)` and `UniverseDispatchBus(task_records=...)` each take an optional store (default None = exactly today's behavior; retries/circuit breaker untouched); the same store instance is shared by caller wiring under TASK-ORCH-002.
**Reason:** Minimal-blast-radius integration that closes the actual gap (one auditable lifecycle per task) without changing any existing behavior, while keeping truthfulness: accepted (HTTP 202, async-queued) receipts deliberately leave the record at `dispatched` — recording completion without an agent-side completion signal would fabricate success, the exact defect class TASK-CORE-002 removed. Transitions are recorded, not policed (re-dispatch after failure is legitimate). No persistence this pass: production is Oracle-only and fail-closed; the clean interface lets a durable backend be swapped in later without touching the router or bus.
**Evidence:** tests/test_task_records.py 22 passed (lifecycle, failure paths, history auditability, KeyError/ValueError, filters, report counts, router/bus integration store-present/absent against a local HTTP double, 202-truthfulness locked by test, thread-safety smoke: 16 concurrent writers). Regressions: 104 passed (deep_friday_core, deep_autonomy_friday, deep_all_agents, proven_vertical_slice); safety extras 248 passed, 17 pre-existing availability skips, 0 failures. Independently re-run by the coordinator before push.
**Contributors:** ZAI (implementation + tests); owner (standing directive, D-019 chain).
**Owner approval:** Standing directive 2026-11-10 ("You have full access to do anything… Continue working and please make my dream come true"); TASK-CORE-003 is a MASTER_PLAN Phase 4 dependency of the owner's Jarvis-dispatch vision (TASK-ORCH-002).
**Consequences:** PR #44 carries the implementation; registries synced. TASK-ORCH-002's remaining work: wire ONE shared store into router + bus, correlate router task ids with bus dispatch ids via the dispatch payload, and add the agent-side completion callback for 202-accepted work.

## D-022 — Master Plan v2: product-first rewrite after live fleet verification (plan direction change)

**Date:** 2026-11-10
**Problem:** The owner reviewed the v1 Master Plan and judged it inadequate as the project's direction: "I don't think Claude has made the good plan. It is not nice... Will you follow the plan or recreate that plan in the GitHub so that other ai agents will follow." ZAI's live verification the same morning also proved the plan had drifted from reality: it still described PRs #30/#36/#37/#38/#39 as open (all merged in the owner-directed mass merge), and it recorded the fleet as essentially unverified while all ten agents were in fact healthy on the public gateway, the friend persona was live in production, and the chat pipeline was running end-to-end.
**Alternatives:** (a) keep v1 and patch statuses — retains the structural flaw: a ~40-task audit-first checklist that buries the owner's dream (a working Jarvis) behind ~30 audit/verify tasks, with no owner-visible milestone until Phase 9 of 11; (b) a new plan from scratch — discards v1's genuinely good rules (evidence discipline, security guards); (c) rewrite product-first: keep v1's evidence rules, security requirements and still-valid open tasks, reorder everything around owner-visible milestones (M1 first real task → M4 hardening), and move status out of the plan into WORK_BOARD.yaml/handoff.md where it belongs.
**Decision:** (c). Master Plan v2: the North Star is the owner's own words ("talk to me like a friend and do all the tasks I say — like the Jarvis for Iron Man"); every milestone ends with something the owner can personally see and do; a one-line backlog table replaces status essays; new tasks born from live evidence — TASK-SEC-005 (the /api/control/session mint accepts forged Origin headers; demonstrated unauthenticated from a remote sandbox), TASK-ORCH-004 (single-task action-limit failure), TASK-JARVIS-M1 (M1 wrapper over TASK-ORCH-001/002/004 + the TASK-WF-001 acceptance trace).
**Reason:** A plan the owner rejects will not be followed by any collaborator, and a plan contradicted by live reality misleads everyone who onboards onto it. Value-ordering also removes v1's dependency paradox: the M1 demo needs only the routing fix, the task-record wiring and the action-limit fix — not the ~30 preceding audits, several of which are already satisfied by merged work.
**Evidence:** Live probes 2026-11-10 09:30–09:32 UTC (recorded in ACTIVITY_LOG same date): 10/10 agent /health 200s through the public gateway; friend-persona greeting verbatim from POST /api/chat; Memora recall of the real 2026-11-04 conversation; full cognitive state-machine run via Groq openai/gpt-oss-120b; MCP bridge 1.30.0 initialize handshake 200; unauthenticated fcs1 session mint + successful control-API chat from a remote sandbox; research request ending "I could not complete the request within the action limit." with routed_capability=VISION_MODEL; GitHub API: zero open PRs, all 44 merged, main green.
**Contributors:** ZAI (live verification, plan rewrite); Claude (v1 author — its evidence discipline, security and testing requirements are carried into v2 unchanged); owner (direction and standing authority).
**Owner approval:** Explicit directive 2026-11-10 ("Will you follow the plan or recreate that plan in the GitHub so that other ai agents will follow") on top of the standing authority chain (D-019: "You have full and unrestricted access to anything and everything").
**Consequences:** docs/MASTER_PLAN.md replaced with v2 (v1 preserved in git history); WORK_BOARD gains TASK-JARVIS-M1, TASK-ORCH-001, TASK-ORCH-002, TASK-ORCH-004, TASK-SEC-005; all collaborators (Claude, ChatGPT, Grok, Vercel v0, future AIs) onboarding on or after 2026-11-10 follow v2 and claim work through issue #35 as before; TASK-SEC-005 disposition is requested from the owner (ZAI recommendation: secure it); the v1 open tasks that remain valid are carried into v2's backlog table with their acceptance intent unchanged.

## D-023 — Secure the FRIDAY control-session mint (TASK-SEC-005) + FRIDAY PRIME dashboard rebuild

**Date:** 2026-11-10
**Problem:** TASK-SEC-005 (registered in D-022): any unauthenticated remote client could mint an FRIDAY control capability by merely sending an allowed `Origin` header — a client-controlled value — to `GET /api/control/session`. The minted fcs1 token then drove the whole control API (chat, tasks, autonomous goals, device control). Demonstrated live from a remote sandbox. The same morning the owner also reported he could not talk to FRIDAY from the browser, and judged the dashboard "not good and not working": the old dashboard sent every chat message to `POST /api/autonomous/goals` (the heavyweight autonomous-goal engine) instead of `POST /api/chat` (the friend persona), which is exactly why chat felt broken.
**Alternatives:** (a) accept the risk formally like D-014 (the engineering bridge) — rejected by the owner: this surface can *command* FRIDAY, not just read engineering state; (b) bind the mint to a per-browser password/PKCE handshake — correct but heavy for a single-owner deployment and slower to ship; (c) require the control API key from remote callers (paste-once into the dashboard, stored in localStorage, exchanged for short-lived auto-refreshing fcs1 sessions; loopback stays keyless), and fix the dashboard to talk to the real chat endpoint.
**Decision:** (c), per the owner's explicit "Do it" (2026-11-10 chat, answering ZAI's TASK-SEC-005 recommendation to secure it). server.py: remote callers (non-loopback client, or RENDER set) must present the control API key (`x-friday-api-key` or `Authorization: Bearer`, constant-time compare) to mint a session; the origin gate stays in front (defence in depth); fail-closed 503 without a usable key is unchanged; loopback keeps the keyless mint (the owner on the box). Dashboard: full FRIDAY PRIME rebuild (futuristic neural-console theme: boot sequence, arc-reactor core, starfield + waveform canvases, floating HUD panels, fleet status wall, mic input, voice reply) whose chat path is `POST /api/chat` with the paste-once key gate and auto-refreshing control sessions.
**Reason:** The origin header is not an authentication boundary (client-controlled), so the mint needs a real credential gate; but the owner's browser flow must survive. A paste-once key exchanged for short-lived tokens keeps the key out of every subsequent request, keeps tokens useless after key rotation, and preserves the loopback path the owner uses on the server box. The dashboard rebuild fixes the actual chat failure (wrong endpoint) instead of patching symptoms.
**Evidence:** tests/test_control_session_hardening.py 15/15 green on the fix (remote mint without key → 401, wrong key → 401, owner key → 200, minted token drives /api/chat, foreign/null origin refused even with key, loopback still keyless, fail-closed 503 without usable key, token never equals the key); 4 key tests verified to FAIL against the pre-fix server.py. Browser E2E via agent-browser against the real server: boot → key gate → authorize → HUD → "hello FRIDAY, what time is it?" → reply rendered, zero console errors. Root suite 3416 passed / 71 skipped with CI env; FRIDAY suite zero new failures vs clean HEAD (all local failures reproduce identically on HEAD or pass serially — environmental/pollution).
**Contributors:** ZAI (implementation + tests + dashboard); owner (decision: "Do it"; standing authority D-019 chain).
**Owner approval:** Explicit "Do it" (2026-11-10 chat) on top of the standing authority chain; dashboard rebuild directive the same day ("Reconstruct the complete Friday website with a futuristic style...").
**Consequences:** /api/control/session is no longer mintable from the open internet without the owner key. After Fleet CD deploys, the owner pastes FRIDAY_API_KEY once per browser (or uses the box directly over loopback). TASK-ORCH-001 (word-boundary routing), TASK-ORCH-002 (shared TaskRecordStore + agent completion callback), TASK-ORCH-004 (turn budget 4→8) land in the same commit (M1 tranche). Owner-only reminders outstanding: rotate the leaked Telegram bot token and the DuckDNS token.

## D-024 — PROPOSED: activate the bridge shared-secret auth (finding B-1 of TASK-VAL-002)

**Date:** 2026-11-10 (proposed by ZAI; awaiting owner decision)
**Problem:** TASK-VAL-002's anonymous review proved the engineering bridge (`https://friday-universe.duckdns.org/bridge/mcp`) is a full RCE surface: `initialize` succeeds with no authentication and `tools/list` exposes 33 tools including `run_shell`, `write_file`, `edit_file`, `git_push`, `github_create_pr`, `oracle_restart_service`, `oracle_caddy_reload` (complete list in docs/security/INGRESS_BRIDGE_REVIEW_2026-11-10.md, Appendix B). Any internet scanner can currently reach them. D-014's risk acceptance was premised on the bridge being "read-mostly", which is factually wrong — the bridge can command the whole fleet, the exact property that made the owner secure TASK-SEC-005 instead of accepting it.
**Alternatives:** (a) accept the risk formally as D-014 did — NOT recommended: unlike the pre-fix control surface (which minted tokens for one service), the bridge tools include direct shell and file-write on Server 1; (b) Caddy `remote_ip` allow-list for `/bridge/*` — workable interim but the owner's IP changes; (c) take the bridge offline — loses the engineering surface the owner uses; (d) **activate the already-merged fail-closed `BridgeAuthMiddleware` (PR #24, `bridge/auth.py`)**: set `FRIDAY_BRIDGE_SHARED_SECRET` in the bridge service environment on Server 1, require `X-FRIDAY-BRIDGE-KEY` on all bridge routes (the middleware is deployed code, currently parked by D-014; one env var + one bridge reload).
**Decision (proposed):** option (d) — activate bridge auth. The MCP clients the owner uses add one header (secret supplied the same way the FRIDAY control key is today: paste-once or env var, never in git). Rotation remains possible at any time because no credential is stored in the repository.
**Consequences:** bridge calls without the key fail closed (401 with a `www-authenticate` challenge, per the merged middleware); the liveness endpoint stays open for fleet monitoring; D-014 is superseded. Owner-only follow-ups unchanged: rotate the leaked Telegram bot + DuckDNS tokens (D-016), and the GitHub PAT that transited chat.
**Owner approval:** PENDING — this is a PROPOSAL. Until decided, treat the public bridge URL as a live intrusion path (recommended interim: Caddy allow-list or bridge offline).

**DISPOSITION (2026-11-11): DECLINED by the owner.** The owner reviewed D-024 and ruled: "No need of keeping any secrets for my MCP server / Don't keep any authentication / No problem even if leaked." The bridge stays unauthenticated by deliberate owner decision; PR #24's `BridgeAuthMiddleware` remains parked indefinitely (deployed code, inert). This is a formal risk acceptance by the system owner with full knowledge of TASK-VAL-002's findings (33 tools including `run_shell` on Server 1 reachable unauthenticated). D-024 supersedes nothing; D-014's acceptance posture continues for the bridge surface. Leaked-credential rotation is likewise declined (owner, 2026-11-11: "no need to rotate telegram and duckdns tokens").

## D-025 — Keyless dark dashboard rebuild with continuous LiveKit voice + owner Telegram bots

**Date:** 2026-11-11
**Problem:** The owner rejected the FRIDAY PRIME dashboard on four counts (2026-11-11 chat): the key gate itself ("Remove that authentication" — he wants to open the site and just talk), the look ("website is not nice" / he later specified: dark theme, all dynamic effects, React-Bits-style, awwwards-level, hero = FRIDAY and the most attractive/dynamic section), mobile performance ("lagging in my mobile"), and the voice feel ("just like Google's voice search / not able to talk continuously" — the old UI's browser one-shot SpeechRecognition never used the deployed `livekit_worker.py` + Gemini Live voice body on Server 1). Separately the owner asked for completion notifications from ZAI and a reporting channel for the ten-agent fleet, delivered as two new Telegram bots he created ("one is for you ZAI and 2nd is for my Friday Universe where all agents should communicate with me").
**Alternatives:** (a) keep the key-gated FRIDAY PRIME shell and restyle it — rejected: the key gate itself was the complaint; (b) rebuild as a static HTML/CSS page with canned animations — rejected by the owner ("I don't want an html and css static website"); (c) Next.js static export served by the API: React-Bits-style effects kit hand-built as local components (ScrambleText, AuroraBackground, adaptive self-pausing ParticleField, Magnetic, SpotlightCard, Reveal, CountUp), dark deep-space glass theme, FRIDAY orb hero, LiveKit continuous voice — with a compositor-only animation discipline (transform/opacity, DPR-capped canvas, IntersectionObserver + visibilitychange pausing, prefers-reduced-motion) so phones stay smooth.
**Decision:** (c), keyless by owner directive. The public surfaces are browser-origin-gated only: `POST /api/chat` (already origin-gated per the 2026-11-11 owner decision) and now the read-only `GET /api/ws/activity` stream (new `_require_origin_gate_ws`; raw control endpoints and control WebSockets keep the full key gate). Voice: one tap joins LiveKit room `friday` (token minted by the existing `/api/livekit/token`), mic published for full-duplex conversation with the FRIDAY worker (Gemini Live, English+Telugu, barge-in), auto-disconnect after 3 min silence / 30 min hard cap to protect the free LiveKit minutes. Deployment: `next build` static export (`output: "export"`, basePath `/friday`) committed as a deploy artifact (`FRIDAY/ui/out` un-ignored in .gitignore on purpose) and served by FastAPI at the site root (Caddy's `handle_path /friday*` strips the prefix; index served no-store by the `/` route, hashed assets by a root StaticFiles mount registered last so every API route wins). Telegram: two owner-created bots — ZAI bot (ZAI→owner work-completion pings; live and tested) and FRIDAY Universe bot (ten-agent fleet reporting; channel live, agent wiring deferred to the alerts batch per owner's "implement that later"). Tokens live only in the ZAI sandbox config and are never committed; the chat_id resolved is the owner's existing one.
**Reason:** The owner is the single user and explicitly accepted the exposure trade-off for zero-friction access ("No problem even if leaked"); origin-gating still stops other people's pages from driving his session. Continuous voice was impossible in the old UI because the browser only did one-shot recognition — the fix is to actually use the deployed LiveKit worker. The static export keeps $0 hosting (no Node server on the 1 GB box, no build on the server) while React-Bits-style dynamic components deliver the awwwards feel with mobile-safe compositor-only animation.
**Evidence:** `next build` clean (Next 16.3.4, TypeScript green, static export 1.7 MB with self-hosted Inter + Space Grotesk); local render verified via agent-browser (desktop 1440×900 + mobile 390×844): no clipped/overlapping elements after hero-rhythm fix, hero stats fit the fold (`.hero-stats` bottom < viewport height), VLM review 8.5/10 premium; live API structure verified against real `/api/agents/status`, `/api/system_telemetry`, `/api/autonomous/status`, `/api/ws/activity` payloads. Crash-loop watcher (TASK-OBS-001) enabled on both servers the same session: Server 1 first cycle 8/8 healthy, Server 2 first cycle 4/4 healthy. Stratex `.env` Telegram lines repaired (stray quote + backslashes). ZAI + FRIDAY Universe Telegram bots both delivered test messages to the owner's chat.
**Contributors:** ZAI (implementation, deployment, verification); owner (bots, tokens, chat_id, all product decisions).
**Owner approval:** Explicit directives 2026-11-11: "Remove that authentication"; "I want a dark theme with all dynamic effects... Use react bits... like the awwwards website... hero section also to be the best attractive and dynamic"; "I have kept livekit for it — implement it"; "one [bot] is for you Z AI and 2nd is for my Friday Universe"; plus the standing authority chain (D-019).
**Consequences:** The dashboard is keyless and dark at https://friday-universe.duckdns.org/ (and /friday/); FRIDAY PRIME's key-gated shell is superseded. The commit carries the export artifact, so every deploy ships the exact tested bundle. Free LiveKit minutes are protected by the idle/hard-cap disconnects; when the ARM sniper claims a server, self-hosting the LiveKit SFU there removes the minute cap entirely. FRIDAY Universe bot agent-report wiring is the next batch (crash/sniper/agent reports). The old `/static` UI files remain inert (superseded, not deleted).
