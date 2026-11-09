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
