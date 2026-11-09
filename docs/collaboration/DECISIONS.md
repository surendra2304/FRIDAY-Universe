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
