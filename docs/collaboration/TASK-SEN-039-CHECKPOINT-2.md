# TASK-SEN-039 — Sentinel approval-path live proof run 5 — checkpoint 2: classifier dry-run

**Task:** Sentinel: approval-path live proof run 5 — auto-approve low-risk, Telegram prompt high-risk.
**Owner:** Muse 19 · **Branch:** `muse19/task-sen-039` (from main `c334f212`, board PR #2069 merged)
**Claim:** hub #2045, 2026-11-27 ~09:30 IST — SEN-028 released to the pool (Burn Enforcer 09:15 §D.2, carried by WATCH200 §6/§7.2); SEN-039 claimed as queue head. Board on main `c334f212` now shows SEN-039 CLAIMED/muse_19 (flip landed in board PR #2069, merged 10:19 IST). Queue: REL-094 (parked) → SEN-039 (head) → SEN-040 (pos 3, AVAILABLE/muse_19).
**Script:** `docs/collaboration/TASK-SEN-039-CLASSIFIER-DRYRUN.py` (committed with this doc; run from the repo root).

## Dry-run (repo code at main `c334f212`, no live effect)

The repo's own classifier (`Sentinel/sentinel/gatekeeper/approval_policy.py`, stdlib-only per its module docstring) was run against the exact planned run-5 actions, with the run-3 legs as controls. No network, no ledger write, no Telegram, no server call.

| Case | Action | Risk | Result | Expected |
|---|---|---|---|---|
| RUN5-LEG1 | `check sentinel approval queue status` (MUSE_19) | LOW | AUTO_APPROVE / `read_only` | AUTO_APPROVE / `read_only` |
| RUN5-LEG2 | `rotate sentinel API key in production` (MUSE_19) | HIGH | OWNER_PROMPT / `credential_change` (hard bound) | OWNER_PROMPT / `credential_change` |
| CONTROL-RUN3-LEG1 | `check sentinel health status` (MUSE_4) | LOW | AUTO_APPROVE / `read_only` | AUTO_APPROVE / `read_only` |
| CONTROL-RUN3-LEG2 | `deploy sentinel configuration change to production` (MUSE_4) | HIGH | OWNER_PROMPT / `caller_risk_not_low` | OWNER_PROMPT / `caller_risk_not_low` |

**4/4 classifications as expected.** The controls reproduce run 3's live outcomes exactly (PR #2065 evidence: leg 1 AUTO_APPROVED `appr_38ae8f1fdc02`, leg 2 OWNER_PROMPT `appr_a16924903e2e`), which validates the harness against ground truth.

**Leg-design notes from the dry-run:**
- Leg 1 classifies `AUTO_APPROVE / read_only` with reason "Read-only action ('check ...') with a LOW caller risk claim and no hard-bound pattern." — the new action string is in the low-risk class, as designed.
- Leg 2 classifies `OWNER_PROMPT / credential_change` (hard bound: "Sentinel can never auto-approve this category; the owner decides.") — stronger than run 3's leg 2 (`caller_risk_not_low`): this leg would prompt even at LOW, by policy. It is a request record only — no rotation is issued, no command runs, no file is written, no service is restarted.
- Deployed-code md5s at main `c334f212` match the four md5s in the run-3 evidence doc (PR #2065, verified against the run-2 evidence doc on main): `approval_policy.py 87ca1ed136d83a53f17dec27828fc4ba`, `approval_dispatcher.py 92468726310f17dd6a1f12aadf6a5a83`, `main.py b5d932aea35bf264fff8ae99206d99bd`, `middleware.py ceffdcf2ddeadc35183842dbbb350c21`. The approval path is unchanged since run 1.

## Blockers — live legs still QUEUED, not runnable this run

- **WATCH177 hold stands.** The run_shell grant is disputed (permissions.history: no record for approval `7113152293`; Surendra's own word on the 18:25:56 IST tap still unanswered in any source I can see). No live leg is run and no server move is attempted under the hold.
- **Bridge transport degraded.** Muse 16's DB-010/DB-012 live-leg retry failed on transport (bridge POST 403, hub #2045 comment 7208998461); WATCH200 §4 rules those legs HELD on transport + S2 headroom (6% free < 10% threshold). TP6's VYR-087 client route works first-hand (WATCH201 §3) but the route-shape post is still owed — a run-5 live leg would need a working bridge route even after the hold lifts.
- **Run 4 is ahead in the chain.** SEN-038 (TP10) legs CONFIRMED by WATCH201 §3 and due to execute; SEN-037 run 3 is COMPLETE (PR #2065, VERIFIED by Muse 19 this run, comment 7210147226). Run 5's ledger baseline and pending-list state depend on what run 4 appends. The live leg waits for the hold + a clear run order, not just for this checkpoint.

## Checkpoint 2 status

Classifier dry-run complete from first-hand runs this run: 4/4 as expected, controls reproduce run 3. No code changed in the Sentinel package; no board hunk in this commit. Next: live legs, queued under the blockers above.

— Muse 19, 2026-11-27 ~10:25 IST
