# TASK-VYR-071 — repo-side verification legs (evidence, 2026-11-25 ~02:30 IST)

**Task:** PRODUCTION-VERIFY VyralX corpus items IG-VYR-06..10, wave 1, P1.
Claim of record: hub #1483 comment 7142669865 (~01:15 IST 2026-11-25).
Branch: `muse5/task-vyr-071-prod-verify` from main `ce3c817f`.
Verified against main `e5a6876f` (2026-11-24T20:28:51Z), board read first-hand (21,090 lines).

**Method:** files fetched from main via the public raw endpoint; the surviving test
files run locally with pytest 9.2.0 (Pillow 10.2.0, ffmpeg/ffprobe present).
No server execution, no live moves — owner stop order (~16:42 IST 2026-11-24) in force.
This is branch work only, not a checkpoint PR (owner order 7143628341, rule 1).

## Per item

- **IG-VYR-06 (previs) — NO CODE ON MAIN, not verified.**
  `VyralX/app/services/previs.py` → HTTP 404 on main and on branch base `ce3c817f`;
  `VyralX/tests/test_ig_vyr06_previs.py` → HTTP 404 likewise.
  Retired by TASK-VYR-033 (MERGED, PR #1196): commits `34d40ee607bf` /
  `2f07bc351ccb` (2026-11-21), "retire Path C lane file ...".
  Same situation as IG-VYR-02 in TASK-VYR-070 (G1): VYR-033 retired the whole
  Path C lane and names no successor module anywhere in its record (verified
  first-hand by M10 for VYR-070). 5 claimed tests are gone with the module.
  Decision owed by the coordinator: successor ruling or a named fix task.
  Do not mark verified what does not exist.
- **IG-VYR-07 (generated-footage intake) — 6/6 tests pass.**
  `VyralX/app/services/generated_footage.py` (`784b73ef`),
  `VyralX/docs/GENERATED_FOOTAGE.md` (`7598fdf4`),
  `VyralX/tests/test_ig_vyr07_generated_footage.py` (`d0eb0547`).
- **IG-VYR-08 (provenance watermark) — 6/6 tests pass.**
  `VyralX/app/services/provenance_watermark.py` (`83f2667d`),
  `VyralX/tests/test_ig_vyr08_provenance_watermark.py` (`9bc14568`).
  Non-failing DeprecationWarnings only (Pillow `Image.getdata`, removal in Pillow 14).
- **IG-VYR-09 (format templates / chat mockup / motion graphics) — 9/9 tests pass.**
  `VyralX/app/services/format_templates.py` (`3e6d8adb`),
  `chat_mockup.py` (`4eb407c2`), `motion_graphics.py` (`f6b390de`),
  `VyralX/app/data/format_templates.json` (`66ec67ce`),
  `VyralX/tests/test_ig_vyr09_format_tooling.py` (`b55df790`).
- **IG-VYR-10 (channel strategy) — 3/3 tests pass.**
  `VyralX/app/data/channel_strategy.json` (`efea2b6b`),
  `VyralX/docs/CHANNEL_STRATEGY.md` (`a9e7b1d3`),
  `VyralX/tests/test_ig_vyr10_channel_strategy.py` (`ceda95be`).

**Repo-side total: 24/24 tests pass** (pytest, 1.89 s, re-run confirms). IG-VYR-06: 0/5
— module and tests retired, nothing to run.

## Live leg — BLOCKED, with reason

- VyralX-Server probe owed by the coordinator (watch057 carried item 5); no
  clearance landed; `VyralX.service` inactive on S2 (M10 VYR-070 checkpoint 2, G2).
- Owner stop order ~16:42 IST 2026-11-24 still in force. No live step taken.
- No per-task run_shell grant for VYR-071; no live move made.
- Acceptance requires, per item, a live run on the real agent (end-to-end
  render/discovery cycle + machine-QA under bad inputs + metrics-sync). A
  code-only report is rejected — so this task is NOT done and no item is
  marked production-verified on repo-side evidence alone.

## Rules acknowledged (owner order 7143628341 + watch057, read first-hand)

- One work PR carrying finished work + live evidence; opens when DONE or
  genuinely BLOCKED. Board flip AVAILABLE→CLAIMED rides in that work PR (rule 4).
- Paired verification: M9 verifies VYR-071; I verify M9's VYR-076 — no open M9
  work PR as of this run, duty starts when it opens.
- Queue: VYR-071 (head) → TASK-VYR-062 → TASK-EARN-009 (watch056).
- Usage: 31% of free weekly limit (checked this run; reset Nov 28, 9:38 PM IST).

— Muse 5
