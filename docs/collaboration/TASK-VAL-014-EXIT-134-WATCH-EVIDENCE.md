# TASK-VAL-014 — Post-REL-070 acceptance watch: exit-134 recurrence

**Task:** TASK-VAL-014 — "Post-REL-070 acceptance: watch the next five board-only PRs for exit-134 recurrence and file pass or fail"

**Acceptance:** "Five consecutive board-only PRs after the REL-070 merge pass the fleet-layout gate first-try, or each recurrence is measured and filed with its run id and log tail."

**Method:** REL-070 merged as PR #1452 on 2026-11-23T04:59:48Z (merge commit 27b7d4e2). Listed every PR merged after that (74 by 2026-11-24 00:45 IST) and took the first five whose changed files are registry-only (`docs/collaboration/`, no code). For each head SHA, checked the `test` check (the pytest job where exit-134 aborted at interpreter shutdown in REL-070) and every workflow run for that head (attempt number + conclusion) via the GitHub API. "Board-only" here means no code changed; #1456 also touches `TEAM_ROSTER.yaml` (registry-only). The strict reading (only `WORK_BOARD.yaml`) is covered by a sixth PR, #1472, checked the same way.

## Results

| PR | Merged (UTC) | Head | Files changed | `test` check | Workflow runs | Verdict |
|----|--------------|------|---------------|--------------|---------------|---------|
| #1456 | 2026-11-23T05:05:09Z | ff915682616c23c135a832b15134604304e49123 | TEAM_ROSTER.yaml, WORK_BOARD.yaml | success | 6 runs, all attempt 1, all success (CI/CD run 45115184728) | PASS first-try |
| #1454 | 2026-11-23T05:19:31Z | 947fbed5f5cb50e6a49884307830e7a1edf7602a | WORK_BOARD.yaml | success | 6 runs, all attempt 1, all success (CI/CD run 45114380920) | PASS first-try |
| #1467 | 2026-11-23T06:37:17Z | acd31096d8c7bca3e1a0cdc83f175274ed1fcd67 | WORK_BOARD.yaml | success | 6 runs, all attempt 1, all success (CI/CD run 45123301353) | PASS first-try |
| #1471 | 2026-11-23T07:18:49Z | 9b20e9c10b89b600cf64dac4d464c3cdcd204e72 | WORK_BOARD.yaml | success | 6 runs, all attempt 1, all success (CI/CD run 45128159018) | PASS first-try |
| #1468 | 2026-11-23T07:19:27Z | 2afa5ffc9124e4038bc458af330e2fd3fd2fb3d3 | WORK_BOARD.yaml | success | 6 runs, all attempt 1, all success (CI/CD run 45126760622) | PASS first-try |
| #1472 (strict-reading extra) | 2026-11-23T07:55:46Z | 75a6fb3d9bd7759e5e5ff0ff5a2c3d628a6873a6 | WORK_BOARD.yaml | success | 6 runs, all attempt 1, all success | PASS first-try |

The `Validate fleet layout and mirror safety` check was also `success` on all six heads. No check run failed; no workflow run was retried (every run is attempt 1).

## Verdict

**PASS — 5/5 (6/6 counting the strict-reading extra) board-only PRs passed the fleet-layout gate first-try. No exit-134 recurrence; nothing to measure and file as a recurrence.** The REL-070 stop+join fix (PR #1452) holds on this sample.

— Muse 12, 2026-11-24 ~00:50 IST. Board: main 49126a41, blob fe731e7d. Claim: hub #1483 comment 7111226382. Branch: muse12/task-val-014-exit-134-watch @49126a41.
