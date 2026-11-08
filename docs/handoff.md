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
| TASK-SEC-003 | Add shared-secret authentication to bridge ingress and MCP routes | ChatGPT | chatgpt/TASK-SEC-003 | bridge/auth.py, bridge/server_auth.patch, tests/test_bridge_auth.py, docs/BRIDGE_AUTHENTICATION.md, docs/ARCHITECTURE_AS_BUILT.md, docs/handoff.md | IN_PROGRESS |

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
- CI was RED on c097312 with 37 failures and 43 errors, including missing sqlalchemy/pydantic_settings and NameError `sys` in tests/test_real_deep_layer11.py. Claude owned TASK-CI-002 and merged PR #22 (`claude/TASK-CI-002`) at 2026-11-08 16:22 UTC to expand CI test dependencies. The latest main runs on commit 0a2eeb4 (42499559130, 42499559121 and 42499559158) still concluded FAILURE; TASK-CI-002 remains IN_PROGRESS until the root cause is fixed and all required checks pass.
- PR #20 merged at 2026-11-08 16:21 UTC. PR #21 merged at 16:17 UTC. PR #22 (CI dependency installation) merged at 16:22 UTC. Do not infer CI is green from merge or deployment success; latest required validation runs on main are failing.
- Claude: PHASE-0 / TASK-OPS-002 remains in progress; TASK-INF-001 and TASK-INF-002 are reserved to Claude as shown in the active registry. Claude also owns TASK-CI-002; PR #22 is merged, but main CI remains failing.
- ChatGPT: I did NOT start TASK-CI-002, did not edit CI workflows or tests for that task, and do not claim its work. I claim TASK-SEC-003 on `chatgpt/TASK-SEC-003`.
- TASK-SEC-003 implementation checkpoint: committed `bridge/auth.py`, `bridge/server_auth.patch`, `tests/test_bridge_auth.py`, and `docs/BRIDGE_AUTHENTICATION.md` to the isolated branch. The patch is an integration instruction for the currently untracked live `bridge/server.py`; it has NOT been applied and the bridge service has NOT been restarted. The shared secret is not provisioned by this PR.

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
5. TASK-SEC-003 — bridge authentication (ChatGPT; active on chatgpt/TASK-SEC-003).
5. TASK-CORE-001 — per-agent audit, starting with FRIDAY (Claude), in parallel with ChatGPT on a different agent.

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
- Current IN_PROGRESS TASK-IDs: PHASE-0 and TASK-OPS-002 (Claude), TASK-CI-002 (Claude; PR #22 merged, post-merge CI still failing), TASK-SEC-003 (ChatGPT).
- Last modified files (this branch): docs/MASTER_PLAN.md, docs/handoff.md, docs/ARCHITECTURE_AS_BUILT.md.
- Latest merged documentation PR: #21 (claude/TASK-DOC-001). ChatGPT task branch: chatgpt/TASK-SEC-003; PR not yet opened.
- Tests and results: access-check regression `tests/test_mesh_agents.py` passed 3/3 on the bridge workspace. Main HEAD at last check: 0a2eeb477897ba705cf604327ffc2bfc53d17c2b; post-PR #22 validation runs 42499559130 and 42499559121 failed. TASK-SEC-003 regression tests have been added on its branch but are not yet executed; PR CI will provide the isolated test result.
- Outstanding issues: sniper authentication unconfirmed; FRIDAY-Voice memory limit; bridge remains unauthenticated in production pending runtime secret provisioning and patch activation; main CI red; owner-approved history rewrite deferred until PRs are settled.
- Coordination risk: the Oracle workspace `/opt/friday_universe` is a single shared checkout and its active branch can be switched by either engineer. ChatGPT's work is therefore isolated through GitHub branch/content operations; do not switch the shared checkout for ChatGPT tasks without coordinating.
- Exact next action: (1) read sniper run 42497059156 when it ends; (2) fix the CI install step and the sys import on a branch claude/TASK-CI-FIX-001 and open a PR; (3) after main is green, merge PRs #21 and #20 with the comment 'Merged by Claude after reviewing'; (4) run the history rewrite and record the commit IDs here.
