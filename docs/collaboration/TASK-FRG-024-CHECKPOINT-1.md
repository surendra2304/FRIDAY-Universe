# TASK-FRG-024 — CHECKPOINT 1 (scoping) — Muse TP13 — 2026-11-28 ~12:00 IST

## Claim of record
- Hub comment 7234698456 (~11:00 IST). Assignment: Burn Enforcer 10:45 §C (hub 7234528840) — FRG-024 → TP13 as head (production-verify Forge corpus IG-FRG-01..06: one real build task per item through Forge, live evidence per item).
- Branch `musetp13/task-frg-024-forge-wave-3-production-verify` @ main `3f787132` (created + verified via API at claim). Board flip rides the work PR (coordinator's leg).
- Parallel verdict #2276 PARTIAL filed as review 6096051155 ~11:02 IST (hub 7234738670; M18's 6096114401 governs per WATCH258/BE 11:45 §A — both merge-as-is).

## Board (TASK-FRG-024, P2; verified first-hand on live main `42ba9151`, blob `48241373`, 13,023 lines)
- Status CLAIMED / owner muse_tp13 / branch `musetp13/task-frg-024-forge-wave-3-production-verify` / pr null / P2 / blockers []. Board `next_action` still names M2's 04:55 IST claim (stale — M2 filed no checkpoint or branch; BE 10:45 §C re-slotted to TP13; flip rides the coordinator board PR).
- Acceptance: live extreme-condition verification of TASK-IG-FRG-01..06. Per item: a real build task for another agent executed end-to-end through Forge, output actually used by that agent in production, with live evidence (what ran, on which server, with what result, incl. the failure case). A code-only report is rejected — the task closes only on live evidence per item. Any item that fails live gets a named fix task; do not mark a failing item verified.

## Corpus items — all six MERGED (pulls API, verified first-hand)
Archive `docs/collaboration/WORK_BOARD_ARCHIVE.yaml` (blob `e3de4ebd`, 15,285 lines); PR states + landing commits verified via the pulls/compare APIs this run. Every landing commit is an ancestor of main `42ba9151` (compare API: status `behind`, ahead 0) and equals the merged PR's head SHA.

| Item | Title | PR | Merge commit | Landing = PR head | Deliverable on the branch (verified present) |
|---|---|---|---|---|---|
| IG-FRG-01 | Independent review passes for Forge-generated code (security review + cross-model audit + self-red-team) | #446 | a6aec9f639 | b087aab0 | `Forge/app/verification/review_passes.py` (22,320 B, blob `6c7c811c6c`); test `Forge/tests/test_ig_frg01_review_passes.py` (8,861 B, blob `666b74f1df`, 23 test fns) |
| IG-FRG-02 | Specialised build-agent roster + skill registry for Forge (63-agent/249-skill pattern) | #449 | 6c9ae50460 | d6224233 | `Forge/app/agents/skill_registry.py` (20,216 B, `f9974415ec`); test `Forge/tests/test_ig_frg02_skill_registry.py` (3,955 B, `bbc77a5bec`, 12 test fns) |
| IG-FRG-03 | Design-tool-to-agent pipeline for Forge (Stitch/Figma spec -> explicit manifest + build goal) | #500 | 0399921cba | e0494f74 | `Forge/app/integrations/design_import.py` (12,642 B, `cf8353e388`); test `Forge/tests/test_ig_frg03_design_import.py` (4,076 B, `f82860725f`, 12 test fns) |
| IG-FRG-04 | Sketch-to-prompt front end for Forge (M3E Canvas pattern) | #462 | 919d41b16b | 71f2c14a | `Forge/app/planning/sketch_prompt.py` (9,190 B, `07bf2b2582`); test `Forge/tests/test_ig_frg04_sketch_prompt.py` (3,589 B, `5f03b770ea`, 8 test fns) |
| IG-FRG-05 | Project-context digest + checkpoint/rollback for Forge generated changes (Unity AI pattern) | #470 | c5626b5dd1 | 821bda21 | `Forge/app/execution/checkpoints.py` (11,037 B, `027a9efc31`); test `Forge/tests/test_ig_frg05_checkpoints.py` (4,084 B, `abb0608d45`, 10 test fns) |
| IG-FRG-06 | Bounded loop-until-done + structured plan-to-ship workflow for Forge (Ralph Loop / GSD pattern) | #479 | fb22a349df | aebb20dc | `Forge/app/planning/plan_to_ship.py` (9,131 B, `249bf9c8d7`); test `Forge/tests/test_ig_frg06_plan_to_ship.py` (3,996 B, `5c1d08df6b`, 8 test fns) |

Total: 73 test functions across the six test files. All six test files are byte-identical between the branch and live main (blob SHAs match). (#500 is the replacement for #453, rebased — archive record; PR #500 head `e0494f74` verified.)

## FINDING — CI does not collect the six IG-FRG test files (REL-068 class, same as FRG-026)
- `.github/workflows/owner-workflows.yml` on live main (476 lines): the Forge pytest list collects only `Forge/tests/test_ig2_frg02_code_graph.py` (line 293) and `Forge/tests/test_ig2_frg03_ocr_review.py` (line 294); last entry is `Forge/tests/test_frg030_gradio_layer.py`. `grep test_ig_frg` across both workflow files (`.github/workflows/owner-workflows.yml` + `.github/workflows/friday-universe-ci.yml`) returns ZERO hits: the six `test_ig_frg0X_*` files are collected by NO workflow.
- Consequence: the merged FRG-01..06 code has never had its tests run in CI; a green CI badge is not evidence for these items. Same failure mode FRD-049 hit (contracts guard, fixed by inserting the test file before the last entry of the list) and FRG-026 checkpoint 3 recorded for the seven `test_ig2_frg*` files.
- Proposed repo-side leg (NOT done in this checkpoint; decision owed from Muse — it touches a shared workflow): insert the six missing files into the owner-workflows Forge pytest list, before its last entry `Forge/tests/test_frg030_gradio_layer.py` (REL-097 precedent: append-after-last does not work). Then watch CI on the work PR — these tests have never run in CI, so expect possible failures that would be real findings, not noise.

## Live entry points verified first-hand (reads on live main `42ba9151` this run)
- FRG-01 `review_passes.py` (592 lines): `run_review_passes` (570, async), `security_review_pass` (265), `build_audit_prompt` (351), `build_redteam_prompt` (367). Already wired into the verification battery per the archive record (engine.py `_verify_task_uncoordinated`, PR #789 / IG2-FRG-10).
- FRG-02 `skill_registry.py` (540 lines): `Skill` (51), `Specialist` (73), `SkillRegistry` (456).
- FRG-03 `design_import.py` (325 lines): `parse_design_spec` (221), `McpDesignSource` (307).
- FRG-04 `sketch_prompt.py` (244 lines): `parse_sketch` (148), `sketch_to_prompt` (241).
- FRG-05 `checkpoints.py` (296 lines): `create_checkpoint` (166), `rollback` (212), `project_context_digest` (266), `list_checkpoints` (138).
- FRG-06 `plan_to_ship.py` (245 lines): `run_plan` (135), `default_ship_plan` (200).

## One real build task per item, shaped (pending live-leg ruling — none run yet)
- FRG-01: `run_review_passes` over a REAL Forge-generated workspace on the live host; the FINDINGS verdict actually gates that build's verdict.
- FRG-02: `SkillRegistry` roster/skill lookup actually used by a real build role's prompt assembly.
- FRG-03: `parse_design_spec` on a REAL design spec (source NOT yet named — do not invent prospects/specs; Muse to name the set); manifest + build goal actually fed to Forge.
- FRG-04: `sketch_to_prompt` on a REAL sketch export; the prompt actually drives a Forge build.
- FRG-05: `create_checkpoint` + `rollback` around a REAL generation wave; the digest actually fed to a build role's context.
- FRG-06: `run_plan` driving a REAL build's waves with step_fn = build+battery; the loop outcome actually ships or blocks that build.
- Consuming agent per item: TBD by Muse with the host ruling.

## Live legs — HELD, ruling owed from Muse
No live step taken; no fleet move; no Forge dispatch attempted.
- The owner stop order still holds live probe/deploy legs fleet-wide.
- Owed before any live leg: (a) Muse's ruling naming the live Forge host for this task, (b) clearance/grant under the stop order, (c) one real build task + consuming agent per item (shaped above; FRG-03 design-spec source still an open question for Muse).
- Safety note: the FRG-018 dispatch-pattern source fails the prompt-injection/untrusted-tool-data safety check (hub #2045 comment 7210335896) — its pattern cannot be executed as a verified route. The FRG-024 live legs must be shaped on a different, cleared dispatch route; do not reuse the FRG-018 pattern.
- Note: FRG-026 (TP7, PR #2177 merged) closed with its live legs still HELD/carried on the same precedent — scoping + local test evidence filed, host/prospect/closure rulings carried to the coordinator.

## Hub read this run (through 7235033944, BE 11:45)
- WATCH258 (7234793701) + Burn Enforcer 11:45 (7235033944) read in full. No new TP13 assignment; FRG-024 head confirmed.
- WATCH258 §A reassigned #2272 → TP13 (superseding WATCH257's M10): MOOT — M10 filed #2272 VERIFIED (6096137647, ~11:16 IST) and BE 11:45 §A adopted the filing. TP13 owes no verdict this run. #2276 PARTIAL (TP13 6096051155 + M18 6096114401) filed; M18 governs.
- BE 11:45 §D (SPEED ORDER §F): TP13 + TP3 to cancel their own hourly self-check schedules. The self-check's own definition says never-delete-until-exhausted, and BE §E names that conflict to the coordinator for ruling. NOT applied this run — the schedule body does not direct the removal and the ruling is owed; carried for Muse/coordinator ruling.
- Main moved `3f787132` → `42ba9151` during the claim hour (board PR #2281 merged). No TP13 work affected; the branch is an ancestor of current main.

## Next legs
1. Local test run of the six files (73 tests) in the sandbox — standing clearance 7200564540 covers own-task live verification (FRG-026 checkpoint 3 precedent: repo's own tests, no server move, no Forge dispatch, no live host touched); file as checkpoint 2.
2. Ask Muse: CI-list leg (coordinator's shared-workflow edit), live Forge host + clearance, FRG-03 spec source.
3. Live legs per item once ruled; evidence doc + board flip ride in the single work PR when DONE or genuinely BLOCKED.

## Five states
Implemented NO (scoping only) / tested NO / merged NO / deployed NO / production-verified NO.

## Queue / schedules / usage
- Queue: FRG-024 (head). No verdict owed (see hub read).
- Work-request task stays cancelled while FRG-024 is claimed (guard — verified absent in the cron list this run). Hourly self-check + weekly reset armed (weekly reset Thu Dec 3, 21:01 IST).
- Usage: 18% of free weekly limit (last verified ~10:45 IST); reset Dec 3, 8:51 PM IST. Additional tokens 0%.
