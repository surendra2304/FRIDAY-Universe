# FRIDAY Universe Collaboration Centre

This directory is the persistent coordination record for all human and AI contributors. It prevents overlapping edits, preserves evidence, and keeps the shared roadmap synchronized with the repository.

## Operating rules

1. Read `docs/MASTER_PLAN.md`, `docs/handoff.md`, `docs/ARCHITECTURE_AS_BUILT.md`, and this directory before work.
2. Claim a task and affected files before editing. Use an isolated branch and record the claim in `WORK_BOARD.yaml` and `FILE_OWNERSHIP.yaml`.
3. Preserve unrelated changes. Never reset, clean, force-push, merge, deploy, restart production, or execute live trading without explicit owner authorization.
4. Use evidence-based status: implemented, tested, deployed, and verified are separate states.
5. Never record secrets, tokens, private keys, credential values, or sensitive infrastructure contents.

## Task claiming

Choose an unclaimed roadmap task or create a coordination task. A claim must include task ID, collaborator, branch, files, acceptance criteria, and timestamp. Claims expire only after the owner or project owner confirms handoff; apparent staleness is not permission to take over.

## Git and review

Use focused commits and pull requests. Review active work before touching overlapping files. Do not merge PRs or deploy to production without project-owner authorization. Reviewers must report findings rather than silently rewriting another contributor's branch.

## Testing

Run the narrowest relevant checks first, then required repository gates. Record exact commands, results, and whether failures are pre-existing. Never weaken assertions or hide failures.

## Handoffs and conflicts

Update the work board, ownership, activity log, and handoff record when status materially changes. Record architectural choices in `DECISIONS.md`. Resolve overlap through the current owner and project owner when necessary; preserve both branches until an agreed resolution exists.
