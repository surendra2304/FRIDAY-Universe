# Engineering Decisions

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
