# FRIDAY Universe — Handoff

Shared coordination and continuity document for Claude and ChatGPT.
Older handoff: docs/FRIDAY_Universe_Engineering_Handoff.md (superseded by this file; kept for history).

## A. Active task registry
| TASK-ID | Task | Owner | Branch | Files claimed | Status |
|---|---|---|---|---|---|
| TASK-DOC-001 | Create the three central documents | Claude | claude/TASK-DOC-001 | docs/MASTER_PLAN.md, docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md | DONE (PR #21 merged 2026-11-08) |
| PHASE-0 | Phase 0 — owner actions executed by Claude (owner instructed: implement Phase 0 without asking ChatGPT) | Claude | main / claude/TASK-DOC-001 | docs/handoff.md, docs/MASTER_PLAN.md | IN_PROGRESS |
| TASK-OPS-002 | Verify OCI sniper authenticates (run 42497059156) | Claude | main (workflow dispatch) | .github/workflows/oracle-capacity-sniper.yml | IN_PROGRESS |
| TASK-CI-002 | Get main fully green | Claude | claude/TASK-CI-002 | CI workflows, tests, tests/test_real_deep_layer11.py | IN_PROGRESS (PR #22 merged; post-merge CI still failing) |
| TASK-INF-001 | Audit Oracle infrastructure on both VMs | Claude | pending | docs/ARCHITECTURE_AS_BUILT.md, infrastructure evidence | NOT_STARTED (reserved for Claude in next-task plan) |
| TASK-INF-002 | Set FRIDAY-Voice MemoryMax after configuration review | Claude | pending | FRIDAY-Voice systemd unit/configuration | NOT_STARTED (reserved for Claude in next-task plan) |
| TASK-SEC-003 | Add shared-secret authentication to bridge ingress and MCP routes | ChatGPT | chatgpt/TASK-SEC-003 | bridge/auth.py, bridge/server_auth.patch, tests/test_bridge_auth.py, docs/BRIDGE_AUTHENTICATION.md, docs/MASTER_PLAN.md, docs/ARCHITECTURE_AS_BUILT.md, docs/handoff.md | IN_REVIEW (PR #24 open; 19 targeted tests pass; monorepo validators red on unrelated tests) |

## B. Completed tasks
(none verified yet under the DONE definition)

Recent work on main (not yet claimed under a TASK-ID, recorded for history):
- 28bd5e6 docs: master plan v2 — Claude. Verified infrastructure, routing, safety. Coverage stated.
- dd1ff29 ci: move Oracle sniper workflows to repo root — Claude. Needed because GitHub runs only root workflows.
- cf92fa9, a971e2c, d501148, 369995e — CI fixes (mock Oracle DB URL, isolate VyralX tests, Memora tmp_path, fastapi in validate-monorepo) — ChatGPT. Merge c097312 completes PR #19. Tests executed: not recorded here; ChatGPT to record.

## C. Current work
- PHASE 0 STARTED (Claude, 2026-11-08 ~16:05 UTC), per owner instruction. Steps:
  1. OCI secrets present in repo (names verified via API). Values unverified.
  2. Sniper check: run 42497059156 on main (c097312) dispatched 15:53 UTC; step "Run Infinite 24/7 Sniper" still running at 16:05. No failure. Authentication not yet confirmed; logs not readable until the job ends. Live log: https://github.com/surendra2304/FRIDAY-Universe/actions/runs/42497059156
  3. History rewrite (leaked keys from commit 46034a4): DEFERRED until PRs #20 and #21 are resolved, because a rewrite changes every commit ID on main and would invalidate both PR bases. Owner approved the rewrite. Note: ChatGPT's own rules say "never force-push main"; the owner's explicit approval is the exception and is recorded here.
- Main CI remains RED. On main commit `b2b13791d5de2c91b3b1b38a57230f501f09021a`, runs 42501251700 and 42501251688 (Monorepo Structure and Safety CI) and 42501251683 (FRIDAY Universe CI/CD) all failed. The Docker failure in 42501251683 is `ModuleNotFoundError: No module named 'friday_core'` when the container starts `uvicorn friday_core.real_api_server:app`, despite image build and Compose startup succeeding. Claude owns TASK-CI-002; PR #23 is open with further fleet CI dependency and deploy-policy test changes.
- PR #20 merged at 2026-11-08 16:21 UTC. PR #21 merged at 16:17 UTC. PR #22 (initial CI dependency installation) merged at 16:22 UTC. PR #23 (Claude CI follow-up) and PR #24 (ChatGPT bridge authentication) remain open. Do not infer CI is green from merge or deployment success; latest main runs remain failing.
- Claude: PHASE-0 / TASK-OPS-002 remains in progress; TASK-INF-001 and TASK-INF-002 are reserved to Claude as shown in the active registry. Claude also owns TASK-CI-002; PR #22 is merged, but main CI remains failing.
- ChatGPT: I did NOT start TASK-CI-002, did not edit CI workflows or tests for that task, and do not claim its work. I claim TASK-SEC-003 on `chatgpt/TASK-SEC-003`.
- TASK-SEC-003 implementation checkpoint: PR #24 is open at https://github.com/surendra2304/FRIDAY-Universe/pull/24, branch `chatgpt/TASK-SEC-003`, head before this handoff checkpoint `021cf65dc761c22a36b473a8f583cd9d8143ddf2`. It adds `bridge/auth.py`, `bridge/server_auth.patch`, `tests/test_bridge_auth.py`, and `docs/BRIDGE_AUTHENTICATION.md`, plus updates the three central documents. Middleware accepts standard `Authorization: Bearer <secret>` or `X-FRIDAY-BRIDGE-KEY: <secret>`, backed only by runtime `FRIDAY_BRIDGE_SHARED_SECRET`; missing configuration returns 503 and invalid credentials 401. Auth is registered inside CORS so rejection responses retain CORS headers. The patch for the currently ignored/untracked live `bridge/server.py` has NOT been applied; the production bridge was NOT restarted and the shared secret is NOT provisioned.

## D. Blocked tasks
| Blocker | Cause | Required action | Responsible |
|---|---|---|---|
| Main CI required checks | Latest runs 42499559130 and 42499559121 on main 0a2eeb4 | Read job logs, fix remaining failures and rerun all required checks; do not merge feature PRs while red | Claude (TASK-CI-002) |
| TASK-CI-002 completion | Main CI remains failing after PR #22 | Continue root-cause investigation until all required checks pass | Claude |
| Sniper secrets might be wrong | OCI_KEY_CONTENT PEM is not in CREDENTIALS.md (only user OCID, tenancy OCID and fingerprint are) | Confirm the PEM was pasted into OCI_KEY_CONTENT, and that OCI_KEY_CONTENT_2 has the second key's PEM | Owner |
| History rewrite | Destructive; invalidates open branch bases | Coordinate timing with ChatGPT; run after open PRs merge | Claude (owner approved) |
| FRIDAY-Voice no memory limit | Not yet changed | Set MemoryMax | Claude (TASK-INF-002) |

## E. Next tasks (in roadmap order)
1. TASK-OPS-002 — confirm the sniper authenticates. Claude to read the run log when complete, or owner checks the live page.
2. TASK-INF-001 — infrastructure audit (Claude).
3. TASK-INF-002 — FRIDAY-Voice memory limit (Claude).
4. TASK-CI-002 — main green (Claude owns; PR #22 merged but latest main checks still fail).
5. TASK-SEC-003 — bridge authentication (ChatGPT; PR #24 in review).
6. TASK-CORE-001 — per-agent audit, starting with FRIDAY (Claude), after dependencies and ownership are reconciled.

## F. Shared decisions
- 2026-11-08: Both AIs work top to bottom through MASTER_PLAN.md. No bottom-up ownership split. (Owner decision.)
- 2026-11-08: Sniper workflows live at repo root only. Subfolder copies are not run by GitHub.
- 2026-11-08: Stratex trades on Binance testnet only. Owner confirmed. Code defaults to testnet (BINANCE_TESTNET default "true"); the effective value on the running units is UNVERIFIED.
- 2026-11-08: The UniverseOrchestrator live path returns a fixed success message without calling peers. Treated as a defect (TASK-CORE-002).
- 2026-11-08: Keyword routing in dispatch_directive misroutes common words. Treated as a defect (TASK-ORCH-001).
- 2026-11-08: Stratex and other agents stay on their current servers. Owner decision.
- 2026-11-08: Sniper retry loop speed-up (15 s cycle, 45 s backoff) is a trade-off: fewer waits, possibly more 429 throttles. Review after several hours of logs.

## G. Latest handoff checkpoint
- Last completed TASK-ID: none verified under DONE.
- Current IN_PROGRESS TASK-IDs: PHASE-0 and TASK-OPS-002 (Claude), TASK-CI-002 (Claude; PR #22 merged, main CI still failing), TASK-SEC-003 (ChatGPT; PR #24 in review).
- Last modified files (this branch): bridge/auth.py, bridge/server_auth.patch, tests/test_bridge_auth.py, docs/BRIDGE_AUTHENTICATION.md, docs/MASTER_PLAN.md, docs/ARCHITECTURE_AS_BUILT.md, docs/handoff.md.
- Latest merged documentation PR: #21 (claude/TASK-DOC-001). ChatGPT TASK-SEC-003 PR: #24, open and awaiting required checks.
- Tests and results: targeted pytest of the exact `bridge/auth.py` and `tests/test_bridge_auth.py` contents passed 19/19 in 0.07s in an isolated scratch package; a separate local ASGI/CORS check confirmed an unauthenticated 401 retains configured CORS headers. For latest PR #24 head `021cf65`, `FRIDAY Universe CI/CD` run 42502800884 passed. `Validate fleet layout and mirror safety` run 42502800827 failed with 3,286 passed, 74 skipped, 38 failed and 43 errors in 437.92s; `Validate monorepo-only policy and workflow syntax` run 42502800825 also failed. Neither failure summary reported an error or failure in `tests/test_bridge_auth.py`. Broader failures include missing agent/test dependencies and import roots, `sys` NameError in `tests/test_real_deep_layer11.py`, dispatch host DNS/circuit-open errors, CPU-worker subprocess failures and stale tests/workflow expectations. Findings were sent to Claude on PR #23. Main CI on `b2b1379` failed on runs 42501251700, 42501251688 and 42501251683.
- Outstanding issues: sniper authentication unconfirmed; FRIDAY-Voice memory limit; bridge remains unauthenticated in production pending runtime secret provisioning, Claude/ChatGPT client compatibility, patch activation and owner-approved restart; PR #24 monorepo validators remain red on unrelated repository tests; main CI red; owner-approved history rewrite deferred until PRs #23 and #24 settle.
- Coordination risk: the Oracle workspace `/opt/friday_universe` is a single shared checkout and its active branch can be switched by either engineer. ChatGPT's work is therefore isolated through GitHub branch/content operations; do not switch the shared checkout for ChatGPT tasks without coordinating.
- Task-ID consistency note: PR #23 is titled TASK-CI-003, but MASTER_PLAN.md currently defines TASK-CI-003 as fixing `run_workspace_test` (pytest missing in the Server 2 venv). The PR scope is different; Claude was notified to reconcile the task ID or roadmap definition before merge.
- Exact next actions: (1) Claude continues Phase 0, TASK-CI-002 and its follow-up CI work; (2) ChatGPT keeps PR #24 isolated and unmerged until required checks are green; (3) once required CI passes, review the PR and its deployment impact before any merge; (4) only after both MCP clients support the selected auth header, the runtime secret is provisioned and the owner authorizes the change, activate the bridge patch/restart; (5) defer the owner-approved history rewrite until PRs #23 and #24 settle. ChatGPT will not perform the history rewrite.
