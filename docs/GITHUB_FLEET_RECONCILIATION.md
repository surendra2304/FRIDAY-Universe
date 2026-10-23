# GitHub-only fleet reconciliation

## Scope

The canonical fleet contains ten independent repositories: FRIDAY, Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris, and VyralX. The standalone repositories and their histories must remain independent; this monorepo is a coordination and source mirror, not a reason to recreate or replace repository history.

## Safe synchronization rules

- Never force-push generated subtree histories to a standalone repository's default branch.
- Publish source updates to a unique automation branch and open a pull request against the standalone `main`.
- Do not automatically delete files from standalone repositories. Review removals explicitly.
- Require a cross-repository token with only the contents-write and pull-request-write permissions needed for the ten repositories. Do not silently fall back to the monorepo's `GITHUB_TOKEN`.
- Never overwrite an existing sync branch. If a branch exists without its expected PR, stop and investigate.
- Merge only after reviewing the diff and passing the standalone repository's required CI.

## Recovery of closed Task PRs

A closed PR that was not merged is not evidence that its change landed. For every Task 1/2/3 PR:

1. Retrieve the exact PR patch and associated commits.
2. Compare each change against the current standalone `main` by file content and behavior, not ancestry alone.
3. Reapply only missing, still-correct changes on a fresh branch based on current `main`.
4. Resolve conflicts intentionally and add regression tests.
5. Open a new PR with a traceable reference to the original task PR.
6. Do not merge a PR whose required checks are failing or missing.

## Verification standard

A deployment workflow passing does not prove unit tests pass. A green unit-test job does not prove production health. Report repository state, CI state, and runtime state separately. For GitHub-only implementation, mark runtime verification as unverified.

## Safety boundaries

- Keep Stratex execution disabled and live-money trading unauthorized.
- Never commit credentials or expose tokens in logs, PR bodies, artifacts, or source files.
- Never disable security scans or use blanket `|| true` to conceal failures.
- Make changes in feature branches and reviewable pull requests; preserve existing default-branch history.
