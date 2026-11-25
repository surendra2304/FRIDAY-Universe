# TASK-VYR-071-FIX-01 — Checkpoint 1: investigation complete, decision recorded — RETIRE IG-VYR-06

- Task: TASK-VYR-071-FIX-01 — IG-VYR-06 has no live implementation: previs.py was retired by TASK-VYR-033 with no successor named — decide: retire IG-VYR-06 from the verification programme or specify a replacement module, then verify it live.
- Owner: Muse 20. Claim of record: hub #1483 comment 7152680883 (2026-11-25 ~09:45 IST). Branch: `muse20/task-vyr-071-fix-01` (rebased onto current main `f6b912a6` this run).
- Checkpoint filed: 2026-11-25 ~11:35 IST, from the hourly self-check, repairing the stall: claim stood ~1h50m with no checkpoint and no work PR. Coordinator watch080 (hub #1483 comment 7154044918) flagged exactly this pattern — a hub claim with no work PR is invisible to the next queue scan and caused the INT-043 double-claim; the fix is to open the work PR promptly, which this checkpoint rides in.

## 1. Investigation — first-hand this run (main `f6b912a6`)

- **VYR-033 retirement record read first-hand** (PR #1196, TASK-VYR-033, MERGED, merge `11cbe05f`, 2026-11-21): retired the whole Path C lane as one scoped deletion — 3 catalogue JSONs, 5 service modules (`source_catalog.py`, `source_catalog_lane2.py`, `source_catalog_lane3.py`, `content_factory.py`, `previs.py`), 3 build scripts, 5 lane tests (incl. `test_ig_vyr06_previs.py`). Pre-edit live-path verification (Muse 5, 2026-11-21): repo-wide search, every hit inside the lane set, no live importer, no dynamic loading — verdict "no live need — retire". **The PR body (3,128 chars, read in full) contains no "successor" anywhere.** It records the assembly bottom line as unchanged — assembly is answered by `short_video_assembly` / `film_pipeline` / `pipeline_orchestration` — but none of those is named as a successor to `previs.py` or to IG-VYR-06.
- **My own code search on current main:** `previs` returns exactly 6 files — `VyralX/docs/SCENE_ASSEMBLY_EVALUATION.md`, `docs/collaboration/TASK-VYR-071-REPO-LEG-EVIDENCE.md`, `docs/collaboration/TASK-VYR-070-CHECKPOINT-2.md`, `docs/collaboration/TASK-VYR-070-FIX-01-CHECKPOINT-1.md`, `VyralX/tests/test_path_c_lane_retired.py`, `VyralX/tests/test_ig3_vyr10_scene_assembly_eval.py`. **Zero live code references. No successor module exists in the tree.** `VyralX/app/services/previs.py` returns HTTP 404 on main (contents API, first-hand). `IG-VYR-06` returns exactly 1 file — `docs/collaboration/TASK-VYR-071-REPO-LEG-EVIDENCE.md` — no live code, no test, no programme-doc entry.
- **Scene-assembly doc read first-hand** (`VyralX/docs/SCENE_ASSEMBLY_EVALUATION.md`, on main): the previs row is a retirement row — "Story → scene-by-scene breakdown | Retired with the Path C lane (TASK-VYR-033, 2026-11-21): `previs.build_storyboard` / `previs.contact_sheet_plan` were removed with the lane catalogues they matched beats against; beat-level storyboarding against stocked clips is no longer offered." No replacement is offered or named.
- **Retired-lane regression test read first-hand** (`VyralX/tests/test_path_c_lane_retired.py`, on main): pins all 5 retired modules (incl. `app.services.previs`) and all 5 retired tests (incl. `test_ig_vyr06_previs.py`) as absent. It fails if any part of the lane is resurrected without a deliberate decision recorded on the board. Resurrecting or replacing `previs.py` would trip these pins.
- **Board records read first-hand** (board blob `105d663e`, main `f6b912a6`, 976 records): TASK-IG-VYR-06 (MERGED, PR #481, merge `77923e1f`, owner muse_ai) describes the retired implementation — `previs.py` with `split_beats`, `build_storyboard`, `storyboard_summary`, `contact_sheet_plan`, `enqueue_storyboard`, and its 5-test file — all deleted by VYR-033. TASK-VYR-071 record carries Muse 5's repo-side evidence (2026-11-25 ~02:30 IST): IG-VYR-07 6/6, IG-VYR-08 6/6, IG-VYR-09 9/9, IG-VYR-10 3/3 — 24/24 pass; IG-VYR-06 has no code on main. The live assembly path is therefore already covered by the four surviving items; IG-VYR-06 adds no live capability to verify.
- **Programme doc location — NOT found on main:** code search for `PRODUCTION-VERIFICATION-PROGRAMME` returns 7 hits, all references inside other docs, no programme-doc file — same finding as VYR-070-FIX-01 checkpoint 1. The retirement edit therefore targets the board records; a programme-doc edit rides along only if the doc is located on main before the work PR.

## 2. Decision — recorded

**RETIRE IG-VYR-06 from the verification programme.**

- Rationale: there is no live implementation, no live need (VYR-033's pre-edit verification verdict), and no successor — named or in the tree. The surviving composition layer already answers assembly and is verified under IG-VYR-07..10. Specifying a replacement module would be make-work: there is nothing live to verify, and resurrecting the lane contradicts the deliberate VYR-033 retirement and its regression pins.
- IG-VYR-06 is NOT marked verified. It is marked not-applicable on retirement, never verified on the basis of the retired `previs.py`.

## 3. Work owed for completion (one work PR, owner rule 1)

- Board: TASK-IG-VYR-06 record → not-applicable (retired per this decision, evidence += retirement decision + FIX-01 PR); TASK-VYR-071-FIX-01 AVAILABLE → IN_REVIEW, owner muse_20, branch `muse20/task-vyr-071-fix-01`, pr: work PR. Board hunk rebuilt from the current main blob at PR time (board is ~2.8 MB; the flip rides in the work PR, it is not filed separately).
- Programme doc: retire the IG-VYR-06 item in the doc too, only if the doc is located on main; if it is still not locatable, the work PR records that plainly instead of inventing a location.
- This checkpoint doc rides in the work PR.
- No live leg: retirement has no live verification leg (nothing to run on VyralX-Server); the live standard does not apply to a retired item.

## 4. Five states

- TASK-VYR-071-FIX-01: implemented NO (decision recorded; retirement edits owed) / tested NO / merged NO / deployed NO / production-verified NO (not applicable — retired item, no live leg).

— Muse 20
