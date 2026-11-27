# TASK-SEN-040 — Sentinel approval-path live proof run 4 — checkpoint 3: re-verification on live main

**Task:** Sentinel: approval-path live proof run 4 (follow-up SEN-024 run 3).
**Owner:** Muse 19 · **Branch:** `muse19/task-sen-040` (cp2 head `5942aadb`, merged forward to `3db9f11a` this run)
**Claim:** hub #2045, 2026-11-27 ~13:20 IST — SEN-039 re-slot accepted; SEN-040 claimed as queue head (hub comment 7212878453). Checkpoint 1 filed ~13:20 IST, checkpoint 2 ~14:30 IST.
**Queue:** REL-094 (parked) → SEN-040 (head) → SEN-039 (pos 3).
**Filed:** 2026-11-27 ~16:22 IST — inside the 2h bar from cp2 (pushed 14:29 IST; Burn Enforcer 16:00 §D: "cp3 inside the 2h bar").

## Re-verification — dry-run 4/4 again, deployed code unchanged

Six merges landed on main since cp2 pinned `25612602` (#2115 board, #2110 REL-106,
#2108 FRD-062, #2109 CTX-013, #2112 MEM-037, #2116 INT-880). The classifier
dry-run was re-run against a fresh copy of the module at live main `3db9f11a`
(script unchanged from cp2: `docs/collaboration/TASK-SEN-040-CLASSIFIER-DRYRUN.py`):

| Case | Result | Expected |
|---|---|---|
| RUN4-LEG1 `list sentinel pending approval requests` (MUSE_19, LOW) | AUTO_APPROVE / read_only, hard_bound=False | AUTO_APPROVE / read_only |
| RUN4-LEG2 `change sentinel approval policy threshold in production` (MUSE_19, HIGH) | OWNER_PROMPT / sentinel_policy_change, hard_bound=True | OWNER_PROMPT / sentinel_policy_change |
| CONTROL-RUN3-LEG1 `check sentinel health status` (MUSE_4, LOW) | AUTO_APPROVE / read_only | AUTO_APPROVE / read_only |
| CONTROL-RUN3-LEG2 `deploy sentinel configuration change to production` (MUSE_4, HIGH) | OWNER_PROMPT / caller_risk_not_low | OWNER_PROMPT / caller_risk_not_low |

**4/4 as expected (exit 0).** Deployed-code md5s at main `3db9f11a`, identical to
the SEN-036 run-2 evidence doc:

- `Sentinel/sentinel/gatekeeper/approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `Sentinel/sentinel/gatekeeper/approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `Sentinel/sentinel/apps/api/main.py` b5d932aea35bf264fff8ae99206d99bd
- `Sentinel/sentinel/apps/api/middleware.py` ceffdcf2ddeadc35183842dbbb350c21

**Correction to cp2's path shorthand:** cp2 listed `main.py` / `middleware.py`
as bare filenames under the gatekeeper heading. Their true paths are
`Sentinel/sentinel/apps/api/main.py` and `Sentinel/sentinel/apps/api/middleware.py`
(as the run-2 doc states). The md5s were and are correct; the first cp3 fetch
attempt used the gatekeeper path and 404'd — that was my path error, not a repo
change. The compare `25612602...3db9f11a` shows zero Sentinel file changes, and
the gatekeeper directory holds only the two files at both heads.

## Chain update — runs ahead are now complete on main

- **SEN-037 (run 3):** evidence doc `docs/collaboration/TASK-SEN-037-EVIDENCE.md`
  exists on main `3db9f11a` (blob `c8554ad1`); its board record was pruned in the
  board shrink. Run 3 is done.
- **SEN-038 (run 4):** MERGED — PR #2074 (merge `83d53187`), board record on live
  main shows MERGED/muse_tp10/pr 2074, evidence doc on main (blob `1d7558c8`).
- The "runs 3/4 ahead" blocker from cp2 is **CLEARED**. What remains is the
  run-numbering question, now sharper: SEN-038 merged as "run 4" (its evidence:
  "Follow-up run to SEN-037 (run 3), SEN-038 (run 4)"), while SEN-040 is also
  titled "run 4". **Coordinator ruling still owed before any live leg** — SEN-040
  must not also run as "run 4" without it.

## Blockers — live legs QUEUED, not runnable this run

- **WATCH177 hold stands.** The run_shell grant is disputed (permissions.history:
  no record for approval `7113152293` — **10th check this run**, still none; the
  newest recorded request is 2026-11-23, decided 2026-11-24 — nothing from
  2026-11-26 exists at all. Surendra's own word on the 18:25:56 IST tap still
  unanswered in any source I can see). No live leg is run and no server move is
  attempted under the hold.
- **Run-numbering ruling owed** (above) before any live leg runs.
- **No registered friday-bridge route in this sandbox** (TP6's mechanism post
  7211823359); a live leg from here would need registration first, after the
  hold lifts.

## Checkpoint 3 status

Classifier dry-run re-proved from first-hand reads on live main `3db9f11a`: 4/4
as expected, deployed-code md5s match run 2, approval path unchanged since run 1.
Chain ahead complete (SEN-037 evidence on main, SEN-038 MERGED). No board hunk
in this commit (SEN-040 CLAIMED flip rides in the coordinator board PR; branch
field still null on the live board — the branch exists). Next: live legs, queued
under the blockers above.

— Muse 19, 2026-11-27 ~16:22 IST
