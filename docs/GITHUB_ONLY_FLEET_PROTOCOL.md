# GitHub-only fleet engineering protocol

## Repository scope

The FRIDAY Universe architecture and active repository inventory define ten agents: FRIDAY, Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris, and VyralX. The root monorepo coordinates these agents; each standalone repository retains its own Git history and CI pipeline.

## Non-destructive synchronization

- Never force-push a subtree split to a standalone repository's `main`.
- A monorepo change must be copied into a branch based on the standalone repository's current `main`, committed normally, and submitted as a pull request.
- The sync workflow must require `GH_PAT_MIRROR` with contents-write and pull-request-write access to all ten standalone repositories. It must fail clearly instead of silently using the root repository's `GITHUB_TOKEN`.
- A sync PR must trigger the target standalone repository's own CI. A green monorepo deployment workflow is not a substitute for agent tests.
- If a sync PR conflicts with independent standalone work, stop and reconcile the file-level change. Never use branch rewriting as conflict resolution.
- Generated sync branches must be unique to a source revision and workflow run. A retry must not overwrite an existing branch that may be under review.
- Mirroring creates PRs only. Merge the PR after reviewing its diff and required CI checks.

## Verification rules

1. Verify the complete ten-agent inventory and YAML syntax in monorepo CI.
2. Require each standalone agent CI to run on pull requests.
3. Keep agent behavior tests, type checks, security scans, and image builds in each agent's existing CI; do not report unrun checks as passing.
4. Treat closed, unmerged task PRs as unmerged. Reconstruct their patches against current `main` and submit new branches/PRs only after deduplicating changes already present.
5. Keep Stratex execution disabled by default; consensus or a code merge is not authorization for live trading.
6. Make claims only to the level of evidence actually observed: repository state, CI on the exact SHA, or PR review status.

## GitHub-only execution boundary

This protocol covers source, tests, branch/PR management, and GitHub Actions in the monorepo and the ten standalone repositories. It does not require laptop or cloud-infrastructure access.
