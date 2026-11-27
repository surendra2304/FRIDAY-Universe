# TASK-FRG-026 — CHECKPOINT 1 (scoping) — Muse TP7 — 2026-11-27 ~18:01 IST

## Claim of record
- Hub comment 7217215769 (~17:01 IST). Queue at claim: FRG-026 → FRD-059 (live-gated).
- Branch `musetp7/task-frg-026-forge-verify-wave3` @ main `caa597bc` (ref create 201, verified first-hand this run via refs API + `git ls-remote`). Board flip rides the work PR per WATCH136.

## Board (TASK-FRG-026, P2; verified first-hand on live main `f0d575f1`)
- Board moved: now `docs/collaboration/WORK_BOARD.yaml` (blob `409850b4`, 11,494 lines). Row L8457–L8476: status AVAILABLE / owner muse_tp7 / branch null / pr null / P2 / created 2026-11-24.
- Acceptance: live extreme-condition verification of TASK-IG2-FRG-05..10. Per item: a real build task for another agent executed end-to-end through Forge, output actually used by that agent in production, with live evidence (what ran, on which server, with what result, incl. the failure case). A code-only report is rejected — the task closes only on live evidence per item. Any item that fails live gets a named fix task; do not mark a failing item verified.
- FRD-059 (L8854): IN_REVIEW / muse_tp7 / pr 1848, live-gated — queue next after FRG-026.

## Corpus items — all six MERGED (archive + pulls API, verified first-hand)
Archive `docs/collaboration/WORK_BOARD_ARCHIVE.yaml` on the branch (blob `e3de4ebd`, 15,284 lines); PR states verified via the pulls API this run.

| Item | Title | Status / PR | Deliverable on the branch (verified present, ref `caa597bc`) |
|---|---|---|---|
| IG2-FRG-05 | ECC harness patterns for Forge (ADAPT, OSS core only) | MERGED, PR #734, merge `cc890b75` | `Forge/app/harness/ecc_patterns.py` (11,108 bytes); test `Forge/tests/test_ig2_frg05_ecc_harness.py` (3,857 bytes) |
| IG2-FRG-06 | Forge local-business prospecting + auto-website pipeline | MERGED, PR #719, merge `0f866128` | `Forge/forge_upgrade/local_business_pipeline.py` (8,631 bytes); test `Forge/tests/test_ig2_frg06_local_business.py` (3,005 bytes) |
| IG2-FRG-07 | Real one-prompt agent-creation flow: prompt -> working, tested, registered agent | MERGED, PR #762, merge `0f861910`, landing `417c5a3e` | `Forge/app/templates/agent_creation.py` (28,697 bytes) |
| IG2-FRG-08 | Claudex Loop: build/audit role-swap loop until cross-model agreement | MERGED, PR #788, merge `ecb07dd9`, landing `a51495e2` | `Forge/app/verification/claudex_loop.py` (11,393 bytes) |
| IG2-FRG-09 | G-08..G-12 agent-infra evaluation with self-verification against the actual repos | MERGED, PR #790, merge `708f632b`, landing `7fddae21` | `Forge/docs/IG2_EVALUATION_NOTES.md` (9,399 bytes) — docs-only, no production behaviour to probe |
| IG2-FRG-10 | C-2 wiring: independent review passes inside the verification battery (production caller) | MERGED, PR #789, merge `2b076252`, landing `14f704f2` | `Forge/app/verification/engine.py` (25,484 bytes); production caller `Forge/app/api/delegate.py` -> `verification_engine.verify_task` |

Shared deliverables also present on the branch: `Forge/forge_upgrade/coding_principles.py` (FRG-01), `code_graph.py` (FRG-02), `ocr_review.py` (FRG-03); tests `Forge/tests/test_ig2_frg01`–`test_ig2_frg04` present (verified on the local tree; re-check on the branch at filing — done above for the six item paths).
Board next_actions: all six — post-merge: fleet CD deploy -> production probe. FRG-10 adds: coordinator decision owed on setting `FORGE_REVIEW_AUTHOR_MODEL` + `FORGE_REVIEW_REVIEWER_MODEL` in Forge's production env to activate the cross-model review leg; until then the deterministic review runs and gates with the audit absence disclosed.

## Hub read this run (through 7218287618, TP4 ~17:58 IST)
- WATCH219 (7217532865) + WATCH219-CORR (7217604943), Burn Enforcer 17:47 (7217811734), WATCH220 (7217912157) + WATCH220-CORR (7218048324) read in full. No TP7 demand, no competing claim on FRG-026, no ruling on the FRG-026 live leg.
- BE 17:47 §H: "TP7 (FRG-026 claimed)" — producing, no action.
- Main moved `caa597bc` → `f0d575f1` during the hour (#2120 VYR-093 merged 17:45 IST, merge `f0d575f1`; #2124 REL-107 merged 17:43 IST, merge `e013e581`). No TP7 work affected.

## Live legs — HELD, ruling owed from Muse
No live step taken; no fleet move; no Forge dispatch attempted.
- The owner stop order still holds live probe/deploy legs fleet-wide.
- Owed before any live leg: (a) Muse's ruling naming the live Forge host for this task, (b) clearance/grant under the stop order, (c) one real build task + consuming agent per item.
- Note: IG2-FRG-09 is a notes-only item — its live leg cannot be shaped as a build task; flag to Muse whether it closes on the evaluation record or needs a named follow-up.
- Carried: FRD-049 live leg still HELD (merged PR #2104, not production-verified).

## Next legs
1. Read-only: read the Forge intake/delegate entry points to shape one real build task per item; confirm the new test files are collected in CI.
2. Request the live-leg ruling from Muse (host + clearance) on hub #2045.
3. Live legs per item once ruled; evidence doc + board flip AVAILABLE → IN_REVIEW ride in the single work PR when DONE or genuinely BLOCKED.

## Five states
Implemented NO (scoping only) / tested NO / merged NO / deployed NO / production-verified NO.

## Queue / schedules / usage
- Queue: FRG-026 (head) → FRD-059 (IN_REVIEW, pr 1848, live-gated).
- Work-request task stays cancelled while FRG-026 is claimed (guard). Hourly self-check + weekly reset armed.
- Usage: 14% of free weekly limit (verified this run), reset Wed Dec 2, 17:01 IST. Additional tokens 0%.
