# TASK-FRG-025 — CHECKPOINT 1 (scoping) — Muse 20 — 2026-11-25 ~17:35 IST

## Claim of record
- Hub comment 7160470331 (~16:31 IST). Queue at claim: FRG-025 → STR-065 → SEN-033.
- **Stall found by the 17:28 IST hourly self-check and repaired in the same run:** ~57 min after the claim there was no branch and no checkpoint (claim post only). Branch `muse20/task-frg-025` created this run from main `e0373ced`; this checkpoint filed on it. Same mechanism as the FRD-050 / STR-078 / API-007 stalls: the work-request cycle stays cancelled while a task is held, so no work run fires — the self-check is the repair leg.

## Board verified first-hand this run (main `e0373ced`, WORK_BOARD.yaml 22,876 lines)
- TASK-FRG-025: AVAILABLE / owner muse_20 / branch null / pr null. P2. No competing hub claim.
- Acceptance (verbatim shape): live extreme-condition verification of the six items below. Per item: a real build task for another agent executed end-to-end through Forge, output actually used by that agent in production, with live evidence (what ran, on which server, with what result, incl. the failure case). A code-only report is rejected — the task closes only on live evidence per item. Any item that fails live gets a named fix task; do not mark a failing item verified.

## Corpus items — all six MERGED on main (board records read first-hand)
| Item | Title | Status / PR | Deliverable on main |
|---|---|---|---|
| IG-FRG-07 | Forge build-template pack (SaaS stack, solo-founder launch, one-prompt agent, portfolio website) | MERGED, landing 4737479f | `Forge/app/templates/ig_templates.py` — verified present, 11,522 bytes, sha f0b10274; test `Forge/tests/test_ig_frg07_ig_templates.py` — 2,594 bytes, sha 00e7662e |
| IG-FRG-08 | Evaluation notes for reference-only Forge items (JCode, OpenMausBot, Paperclip, Codex, agentic IDEs, claude-mem) | MERGED, landing 4f748cd0 | `Forge/docs/IG_EVALUATION_NOTES.md` (deliverable per board; presence re-check owed in the next leg) |
| IG2-FRG-01 | Adopt Karpathy coding principles into Forge guidance | MERGED, PR #674, merge ee16ef05 | Files not yet located — next leg |
| IG2-FRG-02 | Graphify code-graph step for Forge | MERGED, PR #676, merge d1dc1df1 | Files not yet located — next leg |
| IG2-FRG-03 | Open-code-review supplement for Forge PR review | MERGED, PR #681, merge 62f7df13 | Files not yet located — next leg |
| IG2-FRG-04 | Parallel range-chunk downloader (Plexo pattern) | MERGED, PR #687, merge aee4d432 | Files not yet located — next leg |

Board next_actions: IG-FRG-07 — expose templates at Forge intake (template name + project name → render_goal → build) and run one saas-stack build as the acceptance shape. IG-FRG-08 — coordinator decision owed on the two follow-ups named in the notes (preview endpoint bound to verification manifest; budget/heartbeat board fields). IG2-FRG-01..04 — post-merge: fleet CD deploy → production probe.

## Live legs — HELD, ruling owed from Muse
No live step taken in this run; no fleet move; no Forge dispatch attempted.
- The owner stop order still holds live probe/deploy legs fleet-wide (no lift seen in hub watches through WATCH097).
- Owed before any live leg: (a) Muse's ruling naming the live Forge host for this task, (b) clearance/grant under the stop order, (c) one real build task + consuming agent per item.
- Note: IG-FRG-08 is a notes-only item — its live leg cannot be shaped until the coordinator decision on its two follow-ups lands.

## Next legs
1. Read-only: locate each IG2-FRG-01..04 deliverable file on main; confirm IG-FRG-08 notes file present; confirm the new test files are collected in CI; read the Forge intake/delegate entry points to shape one real build task per item.
2. Request the live-leg ruling from Muse (host + clearance) on the hub.
3. Live legs per item once ruled; evidence doc + board flip AVAILABLE → IN_REVIEW ride in the single work PR when DONE or genuinely BLOCKED (owner rule 1).

## Five states
Implemented NO (scoping only) / tested NO / merged NO / deployed NO / production-verified NO.

## Queue / schedules / usage
- Queue: FRG-025 (head) → STR-065 → SEN-033.
- Work-request task stays cancelled while FRG-025 is claimed (guard). Hourly self-check + weekly reset armed.
- Usage: 14% of free weekly limit (verified this run via subscription-status; reset Dec 1, 11:00 AM IST). Additional tokens 0% used. Free usage remains — no wrap-up.
- Carried: Muse's ruling on TASK-STR-085 still owed (duplicate of TASK-IG-STR-06, checkpoint 1 filed 7155854013; no ruling in watches 095/096/097 as read this run).
