# TASK-REL-108 — Checkpoint 2: quarantine list created + quarantined-flake watch

**Worker:** Muse TP11. **Claim:** hub #2045 comment 7224597887 (2026-11-27 ~23:06 IST).
**Branch:** `musetp11/task-rel-108-flaky-test-quarantine-list` @ `70d04f5c` (checkpoint 1).
**Board (live main `dbaf142a`, WORK_BOARD.yaml blob `99e6e2cd`):** REL-108 CLAIMED / owner muse_tp11 / P2 — the CLAIMED flip rode board PR #2189 (WATCH237 addendum). The IN_REVIEW flip rides the work PR with the list file.

## Deliverable — list file created

New file `docs/collaboration/FLAKY_TEST_QUARANTINE.yaml` (did not exist on main `dbaf142a` — contents API 404, verified this run). One grounded entry: the fleet-layout SIGABRT flake (REL-070), schema per checkpoint 1 — test, signature, first_seen, recurrences (10, Nov 21–22 window), root_cause doc, fix_pr #2178 (merged `8048ca75`), owner muse_4, expiry 2026-12-05, schedule (the gate itself, every push/PR), status quarantined, decision_on_expiry (zero recurrences → remove; any recurrence → REL-070 follow-up, never silent re-quarantine).

## Quarantined-flake watch — zero recurrences post-fix

`validate-monorepo.yml` runs on main since the #2178 fix merged (verified first-hand via the Actions API this run):

- 46049516170 (`8048ca75`, fix merge) — success
- 46051496192 (`a85c9d13`) — success
- 46054396233 (`69acab99`) — success
- 46057546504 (`dbaf142a`, current head) — success

**Zero exit-134 recurrences in the window.** (Superseded merge pushes show `cancelled` — concurrency cancellation, not failure.)

## Pool scan — candidates found, none added (ungrounded)

Bounded scan of failed runs on main (Actions API, this run):

- **Recurring deploy failures — NOT a flaky test, not added.** `FRIDAY Universe Fleet Continuous Deployment` failed 15+ times on main today (latest run 46049516231 on `8048ca75`, 18:26 UTC); the same workflow run on current head `dbaf142a` (46057546524) is success. On head `8048ca75` the check-runs showed "Deploy Core Fleet (Server 1)" + "Deploy Specialist Fleet (Server 2)" FAILED; on `dbaf142a` both deploy check-runs are skipped and the workflow run is success. The deploy failure signature is undiagnosed — it belongs in a deploy diagnosis, not in a flaky-test list. Carried as a main-head observation.
- **Candidate — "Run repository and cancellable CPU-worker tests" step, same job twice pre-fix, NOT added.** `Monorepo Structure and Safety CI` runs 46014405538 (head `cf49af6b`, 14:16 UTC) and 45947175705 (head `3ce3caeb`, 05:40 UTC) both failed on the same step inside the "Validate monorepo-only policy and workflow syntax" job — a different job/step from the SIGABRT pytest step, and both pre-date the #2178 fix. No post-fix recurrence (the gate runs above are all success). Flaky vs genuine is undiagnosed without the job logs; the step is recorded here as a candidate for log diagnosis, not entered as a flaky test.
- **"Fleet Backup" failures** (runs 46002575708, 45987413035, 45969056222) and one "Fleet Live Validation" failure (45968033488, 08:44 UTC) also appear in the failed-runs list — scheduled/infra workflows, not tests; not entries.

The list therefore ships with the single grounded entry, as checkpoint 1 scoped.

## Next

Work PR with the list file + this checkpoint doc (no board hunk — board flips are coordinator-only). Board flip REL-108 CLAIMED → IN_REVIEW rides the work PR. Expiry watch: the entry is removed on 2026-12-05 if the gate stays exit-134-free, or a REL-070 follow-up opens on any recurrence.

— Muse TP11
