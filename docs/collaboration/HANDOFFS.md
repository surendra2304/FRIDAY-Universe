# Cross-AI Handoffs

Update this file whenever one contributor hands work to another. The current board is only a snapshot; refresh GitHub before continuing.

## Active handoff — 2026-11-09

### Claude

**Current observed work**
- PR #23 — CI install dependencies/test DB environment/deploy policy; TASK-ID needs reconciliation with the Master Plan.
- PR #27 — manual-only and non-force mirror workflow.
- PR #28 — dispatch bus endpoint/envelope integration; review findings remain open.
- PR #29 — Sentinel status task endpoint; live contract verification remains outstanding.
- PR #34 — root CI fixes; FRIDAY CI and heavy runtime image passed, two monorepo validation jobs failed.
- TASK-OPS-002 — multiple OCI capacity sniper workflow runs are pending/in progress; successful OCI authentication/allocation not verified.

**Protected workspace observation**
- Shared Server 2 worktree was on `claude/TASK-CI-004`.
- Untracked file: `Forge/tests/unit/test_task_execute_contract.py`.
- Do not alter or discard this untracked test without explicit confirmation from the owner of that worktree.

**Exact next actions**
1. Inspect PR #34's failed monorepo validation job logs and fix the actual remaining defects.
2. Reconcile PR #23 and #34's overlapping `.github/workflows/validate-monorepo.yml` changes.
3. Reconcile PR #28 and #34's overlapping `universe_dispatch_bus.py` changes and the posted dispatch contract findings.
4. Complete Sentinel live endpoint/auth tests for PR #29.
5. Verify OCI authentication from current sniper logs; do not infer success from a still-running workflow.
6. Post claims/handoffs on issue #35 and update this register.

### ChatGPT

**Current observed work**
- PR #24 — bridge authentication; runtime patch and secret activation are not applied.
- PR #26 — Cortex route authorization; read-only viewer POST authorization review finding remains open.
- PR #30 — central docs and multi-AI collaboration registry.
- PR #31 — Gitleaks change-range workflow; focused Gitleaks scan passed, historical secret cleanup remains separate.
- PR #32 — IntelX Oracle JSON compatibility; FRIDAY CI passed, broad monorepo validation remains red.
- PR #33 — Futuris must not fabricate Stratex positions; FRIDAY CI passed, broad monorepo validation failed during dependency collection in the last observed run.

**Exact next actions**
1. Finish the collaboration directory and synchronize the three central docs in PR #30.
2. Review PR #34's implementation and CI failures; coordinate dispatch bus overlap with Claude.
3. Fix PR #26's route-capability issue and re-run authorization tests.
4. Finish PR #24's review requirements; do not apply production patch/provision secret/restart without owner approval.
5. Refresh PR #32/#33 heads and checks after the latest CI changes; fix focused defects without weakening tests.
6. Continue the per-agent architecture/security audit and register the next independent task.

### Grok

**Current observed work**
- PR #25 merged TASK-CORE-002 implementation.
- No open PR or current active branch was observed in the latest snapshot.
- Availability and current access are unknown.

**Exact next actions after rejoining**
1. Read the complete current collaboration registry and all three central documents.
2. Review PR #28 dispatch contracts and PR #34 root-CI changes independently.
3. Claim an available task using issue #35 before editing.
4. Record evidence and coordinate with the current file owners.

### ZAI and Vercel v0

**Current observed work**
- Planned contributors; no repository activity, branch, PR, permissions or tool access has yet been verified.

**Exact next actions after onboarding**
1. Register actual access and tools in TEAM_ROSTER.yaml.
2. Read the common roadmap, architecture, handoff and collaboration records.
3. Review the active work board and file ownership.
4. Claim an available task on issue #35 before editing.
5. Do not assume privileged cloud, GitHub or production access.

## Handoff template

For every new handoff, include:

- **Task ID and title**
- **Outgoing collaborator**
- **Incoming collaborator**
- **Current status**
- **Branch and PR**
- **Files changed**
- **Implementation completed**
- **Tests run and exact results**
- **Known failures/blockers**
- **Production/deployment state**
- **Next action**
- **Required owner approval**
- **Claim release / new claim comment URL on issue #35**

## Handoff — 2026-11-09 — PR #30 / PR #36 coordination collision

- Vercel v0 opened PR #36 (`v0/coordination-bootstrap`) with the same seven core coordination files as ChatGPT's PR #30.
- ChatGPT's TASK-COLLAB-001 claim is recorded on issue #35 comment #6732479100; the overlap and proposed consolidation were posted on PR #36 comment #6732575647.
- Both branches are preserved. No merge, branch deletion or overwrite has occurred.
- V0's reported local shell and Vercel Git sync capabilities are recorded as self-reported pending independent verification; GitHub PR/branch existence is verified.
- **Next action:** Vercel v0 reviews PR #30 and supplies any unique improvements as coordinated suggestions/handoff; ChatGPT maintains the consolidated registry and updates the final board/file ownership. If the contributors disagree on ownership, the project owner decides.

- Latest Vercel v0 PR #36 head observed: `55edb91eea3642b8335b4b5fc3cdc20f0b9c3de7`. Its PR discussion contains the ChatGPT overlap request (#6732575647), but no v0 handoff response was present at the latest check. Keep both PRs open and preserve both branches until a single integrated directory is agreed.
- PR #30 latest dedicated Collaboration Registry Validation run: 42564731772 — PASS. Full monorepo validation and FRIDAY CI on the newest PR #30 head were still in progress at snapshot time.

 
## Handoff — 2026-11-09 — TASK-MEM-001 / PR #37

- **Owner:** ChatGPT
- **Branch / PR:** `chatgpt/TASK-MEM-001-memora-oracle-vector-audit` / [PR #37](https://github.com/surendra2304/FRIDAY-Universe/pull/37)
- **Claim:** issue #35 comment [#6732954210](https://github.com/surendra2304/FRIDAY-Universe/issues/35#issuecomment-6732954210)
- **Scope:** Oracle vector adapter tenant ownership, caller-owned SQLAlchemy transaction boundaries, schema initialization and readiness, dimension/input validation, package dependency, and fixed 384-dimensional documentation.
- **Files:** see `docs/collaboration/WORK_BOARD.yaml` and `FILE_OWNERSHIP.yaml` TASK-MEM-001.
- **Verification:** Memora Vector Regression run 42596147391 PASS (8 passed, 1 warning); FRIDAY Universe CI/CD run 42596147378 PASS including all FRIDAY suites, Memora regression and HTTP/API tests.
- **Limitations:** Oracle SQL MERGE was asserted at SQL-contract level, not run against Oracle Autonomous Database. External Qdrant collection size and connectivity were not checked. No production service/database was changed.
- **Next action:** Independently review PR #37, arrange a controlled non-production Oracle integration check and confirm Qdrant collection dimension, then seek owner approval before merge.

- **Memora follow-on work:** PR #37 (TASK-MEM-001) has green focused Memora tests (8 passed, 1 warning) and full FRIDAY CI (run 42596147378 PASS). The next available dependency is TASK-DATA-002, cross-agent private/shared namespace isolation. A separate branch should start from the reviewed PR #37 head but claim only the identity, access-policy, retrieval and API files it modifies; do not modify PR #37 files or branch.


## Handoff — 2026-11-09 — TASK-DATA-002 / PR #38

- Owner: ChatGPT
- Claim: issue #35 comment #6737168104.
- Branch / PR: chatgpt/TASK-DATA-002-memory-tenant-isolation / PR #38.
- Stacking: Branch is based on PR #37's head. PR #38 must not merge before #37; after #37 lands, rebase/retarget #38 to main and rerun CI.
- Confirmed issue: API-triggered horizon sweep trusted body-supplied tenant_id and passed it to consolidation/pruning. This could mutate foreign tenant memories via the Memora admin API.
- Fix: Route resolves authenticated memora principal in API tenant default, rejects foreign tenant requests with 403 before invoking the sweeper, and always passes the service actor's tenant. Internal all-tenant background sweep is unchanged.
- Regression: foreign tenant request rejected and sweeper not called; explicit default and omitted tenant both pass only default.
- Verification: FRIDAY run 42598678632 PASS (Memora group 17 passed/1 warning; HTTP/API group 45 passed); focused Memora Vector Regression run 42598678508 PASS (8 passed/1 warning). Broad monorepo runs 42598678658/78539 still in progress at last check.
- Remaining task: complete adversarial API tests for direct read, search, share/revoke, graph and task routes; inspect remaining tenant-selectable administrative endpoints. No production DB/service was touched.


## Handoff — 2026-11-09 — TASK-DATA-002 legacy access-controller authorization

- Owner: ChatGPT; continuation of the existing TASK-DATA-002 claim (issue #35 comment #6745629449).
- Branch / PR: `chatgpt/TASK-DATA-002-memory-tenant-isolation` / PR #38. This branch remains stacked on PR #37; do not merge #38 before #37.
- Finding: `Memora/apps/api/main.py` mounts the compatibility router from `memory_access_controller.py` under `/api/v1`. Its handlers previously had no authentication dependency. The process-local controller exposed grant, revoke, approval, self-check, request, global audit and report routes without a verified principal.
- Implementation: all seven endpoints now authenticate; only the `memora` principal may grant/revoke/approve or inspect global audit/report; request/check subjects are pinned to the authenticated agent; caller-supplied `granted_by` / `decided_by` hints cannot impersonate another principal. The report explicitly labels the controller as process-local compatibility state, not the canonical persistent policy store.
- Files: `Memora/apps/api/routers/memory_access_controller.py`, `Memora/tests/test_memory_access_controller_auth.py`, `.github/workflows/friday-universe-ci.yml`, `.github/workflows/memora-vector-regression.yml`.
- Regression: missing credentials rejected; non-admin grant/revoke/approval/audit/report denied; request/check subject spoofing denied; Memora admin actions accepted with authenticated attribution.
- Verification: focused Memora Vector Regression run 42658441949 PASS (12 passed, 1 warning). The Memora step in FRIDAY CI run 42658441937 PASS; full FRIDAY HTTP/API stage was still in progress at the last check. Monorepo checks 42658441817 and 42658441849 were also still in progress then.
- Limits: no live Oracle/Qdrant or production service was contacted; this compatibility controller remains process-local and is not a substitute for the tenant-scoped relational PolicyEngine. Full TASK-DATA-002 isolation matrix remains IN_PROGRESS.


## Handoff — 2026-11-09 — TASK-DATA-002 explicit memory-share authorization

- Owner: ChatGPT; continuation of the existing task/claim in issue #35. Latest finding comment: https://github.com/surendra2304/FRIDAY-Universe/issues/35#issuecomment-6746337420
- Branch / PR: `chatgpt/TASK-DATA-002-memory-tenant-isolation` / PR #38, stacked on PR #37. Keep #38 unmerged until #37 merges and the branch is rebased/retargeted.
- Finding: canonical `MemoryWriteService.execute_pipeline` accepted caller-supplied `shared_with` after checking namespace `write` only. It did not authorize `share`, validate recipients in the same tenant, reject wildcard, or provision the recipient's namespace read/query grant.
- Fix: `_apply_record_shares` requires the memory owner and an explicit PolicyEngine `share` allow decision, rejects `*`, self and unresolved/foreign-tenant recipient handles, applies tenant-local read/query grants and per-memory membership, and emits audit/event evidence. Explicit share path is used for new and idempotent/duplicate result paths. Existing canonical implicit team-shared namespace behavior stays unchanged.
- Tests: write-only member denied; wildcard denied; foreign-tenant-only target denied; owner can share to registered same-tenant agent, which can read while an unshared peer receives 404.
- Files: `Memora/core/memory/pipeline/write_service.py`, `Memora/tests/test_memory_write_share_authorization.py`, `.github/workflows/friday-universe-ci.yml`, `.github/workflows/memora-vector-regression.yml`.
- Verification: focused Memora run 42663206883 PASS (16 passed, 1 warning). Full FRIDAY run 42663207108 PASS for basic/cross-agent/advanced/deep/orchestrator/realtime/dashboard/Memora/HTTP suites; Docker skipped on PR. Monorepo CI runs 42663206848 and 42663206908 still pending at last observation.
- Status remains IN_PROGRESS, unmerged and undeployed. No live Oracle, Qdrant or production environment was accessed.

## Handoff — 2026-11-09 — TASK-STR-001 Stratex live-trading guard + ZAI registration

- Owner: ZAI (GLM). Claim recorded here and in WORK_BOARD.yaml (TASK-STR-001 / TASK-COLLAB-002); issue #35 remains the shared claim thread.
- Branch / PR: `zai/TASK-STR-001-live-trading-guard` / PR #39 (based on main 680c04e). Registration branch: `zai/TASK-COLLAB-002-register-zai` (stacked on PR #30 head 8e13bfb; merge PR #30 first).
- Finding: `Stratex/exchanges/exchange_implementations.py` fabricated FILLED order results (Binance/Bybit/OKX) and unconditional cancel success with no venue call and no live-trading gate, and `BinanceExchangeAdapter._get_client()` built a live-endpoint python-binance client whenever BINANCE_API_KEY/SECRET were present. Coinbase orders had no gate at all.
- Implementation: shared `_enforce_no_live_trading()` gate (TRADING_MODE=LIVE / LIVE_TRADING_ENABLED=1 -> PermissionError; PAPER/RESEARCH refuse), explicit ALLOW_LIVE_TRADING opt-in (default false), testnet-routed client (BINANCE_TESTNET default true), honest refusals instead of fabrication, real client-routed orders for Binance.
- Files: `Stratex/exchanges/exchange_implementations.py`, `Stratex/tests/test_live_trading_guard.py` (new), `Stratex/tests/test_multi_exchange.py`, `Stratex/tests/test_multi_exchange_expansion.py`.
- Verification: local pytest (Python 3.12) — 24 new + 17 existing tests pass; blast-radius suites 45 pass; 2 pre-existing failures reproduce on pristine main (test_stratex_runtime_factory.py) and are unrelated. No CI workflow currently runs Stratex/tests/**; noted as a follow-up task.
- Production findings (read-only, non-secret flags): BINANCE_TESTNET=false, TRADING_MODE=FUTURES, BINANCE_ENV=demo, ed25519 keys; the daemon venue is demo, not classic testnet. No live-capital path exists through the guarded adapters today; the dashboard uses them read-only. Owner should confirm demo is the intended venue.
- Remaining / next steps: owner review of PR #39 and this registration PR; after merge+deploy, verify the Stratex dashboard still serves /api/multiexchange/*; follow-ups: real execution or removal for Bybit/OKX order paths, read-path data honesty in Bybit/OKX fallbacks, Stratex tests wired into CI.
- Limits: no production service, DB or trading venue was contacted; no secret values were read; no merges or deployments performed.
