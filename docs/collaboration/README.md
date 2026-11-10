# FRIDAY Universe — Multi-AI Collaboration Centre

This directory is the shared operational coordination centre for all human and AI contributors working in FRIDAY Universe.

**GitHub coordination hub:** https://github.com/surendra2304/FRIDAY-Universe/issues/35

## What is authoritative?

These records have distinct purposes. They must stay synchronized, but they must not compete with one another.

| Record | Authority |
|---|---|
| `docs/MASTER_PLAN.md` | Project objectives, phase order, dependencies and acceptance criteria |
| `docs/ARCHITECTURE_AS_BUILT.md` | What the source code and deployed system actually implement |
| `docs/handoff.md` | Current project state, blockers and next engineering actions |
| `docs/collaboration/TEAM_ROSTER.yaml` | Contributor identities, verified capabilities and onboarding state |
| `docs/collaboration/WORK_BOARD.yaml` | Operational task registry and collaborator ownership |
| `docs/collaboration/FILE_OWNERSHIP.yaml` | Active file/component claims and overlap/conflict warnings |
| `docs/collaboration/ACTIVITY_LOG.md` | Append-only activity and evidence history |
| `docs/collaboration/DECISIONS.md` | Shared decisions and the evidence behind them |
| `docs/collaboration/HANDOFFS.md` | Cross-collaborator handoffs and exact next actions |
| GitHub issue #35 | Externally visible task claims, releases, blockers and handoffs |

The collaboration board mirrors the Master Plan. It does not silently change task acceptance criteria or redefine the architecture.

## Equal collaboration model

Claude, ChatGPT, Grok, ZAI, Vercel v0 and future contributors are equal engineering collaborators. No AI is automatically the principal architect, team leader or exclusive owner of a technical domain.

A contributor's specialization is a capability, not an authority level. Every contributor may implement, challenge, review and improve any part of the system, subject to task and file ownership.

The human project owner retains final approval for architectural direction, merges and production changes.

## Mandatory onboarding sequence

Every contributor must:

1. Read `docs/MASTER_PLAN.md`, `docs/handoff.md` and `docs/ARCHITECTURE_AS_BUILT.md`.
2. Read this directory, especially `TEAM_ROSTER.yaml`, `WORK_BOARD.yaml` and `FILE_OWNERSHIP.yaml`.
3. Refresh open PRs, branches, recent commits and CI results from GitHub. A prior snapshot is not current truth.
4. Verify what other contributors are actually changing before editing.
5. Register its actual identity, tools and verified repository/runtime access in `TEAM_ROSTER.yaml`. Never infer access from the AI product name.
6. Claim an available task using the protocol below.
7. Implement, test, review and update all affected records.
8. Hand off evidence and the exact next action.

## Task claim protocol

**The GitHub issue is the visible claim thread.** Before editing, post a top-level comment on issue #35 using this format:

```text
CLAIM TASK-ID
Collaborator: <collaborator_id from TEAM_ROSTER.yaml>
Branch: <branch name>
PR: <number or none>
Files: <exact paths/components>
Started: <UTC ISO-8601 timestamp>
Expected next update: <UTC ISO-8601 timestamp>
```

Then update `WORK_BOARD.yaml` and `FILE_OWNERSHIP.yaml` in the contributor's branch/PR.

Before claiming:
- Check whether the task already has an active owner.
- Check whether each target file is claimed or has uncommitted work.
- Check all open PRs for overlapping filenames, not just PR titles.
- Check the connected worktree status if available.
- Contact the existing owner if ownership or branch state is unclear.

A task is not available simply because its owner has not posted recently. A missing update does not authorize takeover.

### Simultaneous claims and atomicity

GitHub issue comments provide the shared, timestamped claim record; the first valid claim is the provisional owner. If claims overlap or arrive nearly simultaneously, both contributors must pause file edits and resolve ownership in issue #35.

When updating an existing YAML record through GitHub's Contents API, supply the current blob SHA. A stale-SHA conflict means another update happened: refresh the file, reconcile the change and retry. Never force an update over a newer version.

A branch-local claim alone is not a shared lock. Never treat it as one.

### Release and handoff comments

Use issue #35 and the templates in `HANDOFFS.md`:

- `RELEASE TASK-ID` — release ownership, explain why and identify remaining work.
- `BLOCKED TASK-ID` — state the exact blocker, evidence and required unblocker.
- `HANDOFF TASK-ID` — record completed work, tests, branch/PR and next action.
- `REVIEW TASK-ID PR-NUMBER` — post reproducible review findings.

Renew claims with progress updates. The board's stale-claim warning is a request to contact the owner, not permission to overwrite their work.

## Task states

Use these exact operational states:

- `PROPOSED` — work identified but not yet approved/ready to claim.
- `AVAILABLE` — acceptance criteria and dependencies are clear; no active owner.
- `CLAIMED` — owner registered; implementation not yet underway.
- `IN_PROGRESS` — implementation is underway.
- `BLOCKED` — cannot proceed until a named dependency is resolved.
- `IN_REVIEW` — implementation submitted for review.
- `MERGED` — PR merged into its target branch.
- `DEPLOYED` — implementation deployed to the intended environment.
- `VERIFIED` — acceptance criteria verified with recorded evidence in the target environment.
- `CLOSED` — task formally closed; include why if not delivered.

Do not collapse these states:
- A green targeted test does not mean the full repository suite is green.
- A merged PR does not mean it is deployed.
- A running service does not prove its API works.
- A deployed change does not mean production verification passed.
- A task is not `DONE` unless the Master Plan's acceptance criteria are satisfied. Use `VERIFIED` and the evidence first; use `CLOSED` only when the task is formally closed.

## File ownership and protected work

Before modifying a file:
- Check `FILE_OWNERSHIP.yaml` and all PR changed-file lists.
- Preserve untracked and uncommitted work.
- Do not switch, clean, reset or overwrite another contributor's worktree.
- Do not edit files owned by another contributor without an explicit handoff or agreement recorded on issue #35.
- When two PRs touch the same files, record a conflict and coordinate the merge/rebase sequence.

The current workspace observation in `FILE_OWNERSHIP.yaml` is especially important: the shared Server 2 worktree was observed on Claude's `claude/TASK-CI-004` branch with an untracked Forge contract test. Treat it as protected until its owner confirms disposition.

## Required updates

For each material change, update:
- `WORK_BOARD.yaml` — task status, owner, branch, PR, tests, evidence and next action.
- `FILE_OWNERSHIP.yaml` — files claimed/released and conflict state.
- `ACTIVITY_LOG.md` — append a dated entry; do not rewrite history.
- `HANDOFFS.md` — cross-contributor handoff when another contributor must continue.
- The three central documents whenever project state, architecture or roadmap evidence materially changes.

Do not update only the board while leaving contradictory status in the Master Plan or handoff.

## Engineering and safety rules

- Preserve exactly ten integrated agents. VyralX is agent ten.
- Inference is the canonical LLM/provider gateway, not action authority.
- Fix root causes; do not mask errors or weaken tests.
- Never fabricate success, live telemetry, positions, balances or health.
- Never commit credentials or secrets.
- Never force-push, blindly reset, or discard work.
- Never merge PRs or deploy/restart production without explicit owner authorization.
- Never place live trading orders. Stratex stays on the owner-approved testnet configuration.
- Keep unverified facts explicitly marked as unverified.

## Adding new collaborators

When ZAI, Vercel v0 or another contributor is introduced:
1. Add a roster entry with status `planned` or `onboarding`.
2. Record only capabilities and repository/runtime access actually verified.
3. Give the contributor this guide and the Universal AI Collaboration Directive.
4. Require it to inspect the latest shared records and open PRs.
5. Do not assign a task until it has registered and completed its onboarding check.

## Snapshot warning

The YAML files are an initial snapshot dated 2026-11-09. Contributors must refresh GitHub and runtime state before acting. The records are not a live dashboard and do not update themselves.


## Automated registry validation

Run locally before submitting changes:

```bash
python -m pip install "PyYAML>=6.0,<7.0"
python scripts/validate_collaboration.py
```

The dedicated GitHub Actions workflow `.github/workflows/collaboration-registry.yml` runs on pull requests and pushes that change collaboration records or the central documents. It validates contributor IDs, task IDs/states, ownership references, conflict references, required files and the canonical ten-agent record. A passing registry check validates the records' structure; it does not prove task implementation or production health.
