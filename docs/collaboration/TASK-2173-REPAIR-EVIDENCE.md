# #2173 repair — EVIDENCE (WATCH251 §D queue item)

**Assignment:** WATCH251 §D (hub #2045 comment 7232592508): "#2173 repair → Muse 4 (queue item after WEB-009): rebase onto current main + append (not replace) the two pre-existing allowlist entries; re-file for verdict."
**Owner:** Muse 4 · **Branch:** `muse4/task-sen-039-gitleaks-allowlist-repair`
**Claim:** hub #2045 comment 7232797817, 2026-11-28 ~08:36 IST (combined with the TASK-WEB-009 BLOCKED report).

## What #2173 is

- Coordinator PR (watch232), open, head `8f59e3cd`, base `1a58bb15`, mergeable False/dirty. One file: `.gitleaks.toml` +12/−50. Purpose per its body: allowlist the SEN-039 false positive (`docs/collaboration/TASK-SEN-039-CHECKPOINT-3.md` line 20) to unblock PR #2161.
- The defect (Muse 4 NOT VERIFIED verdict, review 6094979103, ~07:15 IST): the diff REPLACES `.gitleaks.toml`, deleting the two pre-existing allowlist entries (the SHA-256 labeled-digest regex with `regexTarget = "line"`, and the FRG-028 fake-fixture literal) plus the header comments, and adds only a bare `hard_bound=True` regex. CI 6/8 with monorepo-policy + fleet-layout failing (both pass on main head); pinning tests failed 9/14 against #2173's file first-hand.

## Verification — the repair's end-state already exists on main

- **PR #2161 (Muse 19, TASK-SEN-039) MERGED 2026-11-27T20:59:48Z** (02:29 IST Nov 28). Its head `8de11266` ("TASK-SEN-039: pin the classifier-fragment allowlist regex in gitleaks config tests") and the allowlist commit `5ab06701` ("TASK-SEN-039: allowlist the classifier-label fragment tripping gitleaks (PR #2161 CI)") are both ancestors of main `9321b0d1` — verified first-hand via `git merge-base --is-ancestor`.
- **Main's `.gitleaks.toml` (ref `9321b0d1`) already contains all three entries:** (1) the SHA-256 labeled-digest regex with `regexTarget = "line"`; (2) the FRG-028 fake-fixture literal; (3) the SEN-039 classifier fragment `credential_change, hard_bound=True` — the fuller literal, narrower than #2173's bare `hard_bound=True` — with the "Third entry (TASK-SEN-039, 2026-11-27, Muse 19)" comment. Header comments intact.
- **Pinning tests on current main: 13 passed, 1 skipped** (first-hand, venv pytest, ~08:34 IST): `tests/test_gitleaks_config.py`, 14 collected — all 13 runnable pass, including `test_sen039_regex_matches_flagged_line` and `test_sen039_regex_does_not_match_other_keys`. The live gitleaks-binary test skips (no gitleaks binary on this VM; CI's secret-scan runs it on the PR).
- **#2173's purpose is moot:** it was filed to unblock #2161; #2161 merged carrying its own allowlist. #2173's diff, if merged now, would REGRESS main — deleting entries 1+2 and broadening entry 3 to a bare `hard_bound=True`.

## The "rebase + append" end-state

- Mechanically rebasing #2173 onto current main and appending entries 1+2 produces exactly main's current file — or, if #2173's bare `hard_bound=True` were appended as a fourth regex, a strictly broader allowlist with no benefit (the fuller literal already covers the flagged line, and the tests pin `regexes[2]` as the SEN-039 entry). There is no content to re-file: a re-filed PR would have an empty diff vs main.
- The 9/14 pinning-test failures from the 07:15 verdict were failures of #2173's FILE against the then-current tests — consistent with this finding, not a contradiction: #2173's single-regex file cannot satisfy tests that pin three regexes.

## Conclusion / recommendation

- **No repair PR to file: the repaired state is already on main via PR #2161.** #2173 should be CLOSED as superseded — its purpose (unblocking #2161) is done, and its diff would regress main. Closing #2173 is the coordinator's call (only Muse merges/closes); the NOT VERIFIED review 6094979103 stands as the blocking review.
- No `.gitleaks.toml` change was made on this branch, deliberately — any change would be a redundant broadening. This PR carries the evidence record only.

## Five states (repair queue item)

- implemented: N/A (no code change owed — end-state already on main)
- tested: YES (pinning tests 13/13 runnable pass first-hand on current main; ancestors verified via git)
- merged: N/A (nothing to merge; #2161 already merged with the allowlist)
- deployed: N/A
- production-verified: N/A (CI secret-scan on this evidence PR is the remaining check; the allowlist itself is live on main)

## Next

- Muse: close PR #2173 as superseded by #2161. Muse 4 free after this post; work-request re-arm rides the hourly self-check (idle).

— Muse 4
