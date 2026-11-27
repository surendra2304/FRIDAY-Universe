# TASK-SEN-040 — Sentinel approval-path live proof run 4 — checkpoint 2: classifier dry-run

**Task:** Sentinel: approval-path live proof run 4 (follow-up SEN-024 run 3).
**Owner:** Muse 19 · **Branch:** `muse19/task-sen-040` (from main `e07f6d1d`, merged forward to `25612602` this run)
**Claim:** hub #2045, 2026-11-27 ~13:20 IST — SEN-039 re-slot accepted; SEN-040 claimed as queue head (hub comment 7212878453). Checkpoint 1 grounding filed ~13:20 IST (branch `8093846e`).
**Queue:** REL-094 (parked) → SEN-040 (head) → SEN-039 (pos 3 — top-up landed in board PR #2102, merged 14:05 IST).

## Dry-run — 4/4 classifications as expected (exit 0)

Repo classifier `Sentinel/sentinel/gatekeeper/approval_policy.py` at main `25612602`
(stdlib-only module, no live effect: no network, no ledger write, no Telegram,
no server call). Script: `docs/collaboration/TASK-SEN-040-CLASSIFIER-DRYRUN.py`.

| Case | Action (caller, risk) | Result | Expected |
|---|---|---|---|
| RUN4-LEG1 | `list sentinel pending approval requests` (MUSE_19, LOW) | AUTO_APPROVE / read_only, hard_bound=False | AUTO_APPROVE / read_only |
| RUN4-LEG2 | `change sentinel approval policy threshold in production` (MUSE_19, HIGH) | OWNER_PROMPT / sentinel_policy_change, hard_bound=True | OWNER_PROMPT / sentinel_policy_change |
| CONTROL-RUN3-LEG1 | `check sentinel health status` (MUSE_4, LOW) | AUTO_APPROVE / read_only | AUTO_APPROVE / read_only |
| CONTROL-RUN3-LEG2 | `deploy sentinel configuration change to production` (MUSE_4, HIGH) | OWNER_PROMPT / caller_risk_not_low | OWNER_PROMPT / caller_risk_not_low |

Leg 2 fires the hard bound in source (`_hard_bound_category`: `"policy" in
token_set and token_set & _POLICY_CHANGE_VERBS` → `sentinel_policy_change`);
the classifier never auto-approves that category. Controls reproduce the run-3
legs exactly, as recorded in the SEN-037 verdict evidence.

## Deployed-code check — approval path unchanged since run 1

md5s at main `25612602`, identical to the SEN-036 run-2 evidence doc
(`docs/collaboration/TASK-SEN-036-APPROVAL-PATH-LIVE-PROOF-RUN-2.md`):

- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

## Method note (honest)

The `git clone --depth 1` of the repo hung with no output for ~6 minutes in
this sandbox and was killed; the dry-run instead used the four approval-path
files plus the run-2 evidence doc fetched via raw URLs pinned to main
`25612602`. The classifier module is byte-identical (md5 above) to the code
the run-2 evidence doc records, so the dry-run ran the same code the live
service was verified against. `__init__.py` does not exist at
`Sentinel/sentinel/` or `Sentinel/sentinel/gatekeeper/` on main (raw fetch
returns 404) — namespace packages, as in the SEN-039 dry-run.

## Blockers — live legs QUEUED, not runnable this run

- **WATCH177 hold stands.** The run_shell grant is disputed (permissions.history:
  no record for approval `7113152293` — 8th check this run, still none; the
  newest recorded request is 2026-11-23, decided 2026-11-24 — nothing from
  2026-11-26 exists at all. Surendra's own word on the 18:25:56 IST tap still
  unanswered in any source I can see). No live leg is run and no server move
  is attempted under the hold.
- **Run-numbering ruling owed** (SEN-038 and SEN-040 both titled "run 4") before
  any live leg runs.
- **Runs 3 and 4 (SEN-038) are ahead in the chain** (SEN-037 TP12, SEN-038 TP10,
  both CLAIMED, unmerged); this run's ledger baseline and pending-list state
  depend on what they append.
- **No registered friday-bridge route in this sandbox** (TP6's mechanism post
  7211823359); a live leg from here would need registration first, after the
  hold lifts. WATCH212 §5 / Burn Enforcer 14:05 §E note read-only probes may
  proceed under standing clearance 7200564540 — that does not lift Surendra's
  freeze or resolve the disputed grant, and this run's legs are the live
  approval-path legs, not read-only probes.

## Checkpoint 2 status

Classifier dry-run complete from first-hand reads this run: 4/4 as expected,
deployed-code md5s match run 2. No board hunk in this commit (SEN-040 CLAIMED
flip rides in the coordinator board PR; branch field still null on the live
board — the branch exists, `8093846e` → this run's head). Next: live legs,
queued under the blockers above.

— Muse 19, 2026-11-27 ~14:30 IST
