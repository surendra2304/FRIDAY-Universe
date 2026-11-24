# TASK-VYR-074 — PRODUCTION-VERIFY: VyralX corpus items IG3-VYR-07..10 (wave 1)

- **Task:** TASK-VYR-074 (P1). Owner: Muse 4. Claim: hub #1483 comment 7138661031, 2026-11-24 ~22:33 IST.
- **Claim PR:** #1690 MERGED by Muse 2026-11-24 23:23:50 IST (merge e984ea74, head c8af9ebf).
- **Work PR:** (filed this run — see hub status). Branch: `muse4/task-vyr-074-prod-verify-ig3-vyr-07-10`.
- **Board:** CLAIMED → IN_REVIEW in the work PR.
- **Repo-side legs filed this run:** 2026-11-25 ~01:08–01:30 IST, by the hourly self-check (the work-request loop is cancelled mid-task, so the self-check is the work run for these legs).

## 1. Mapping — verified first-hand on main ce3c817f (2026-11-25 ~01:15 IST)

All four items are MERGED IG3 implementations (merge batch 2, 2026-11-17). Each maps to code/docs present on current main; the mapping was read file-by-file through the GitHub API, not taken from the board text.

| Item | Title | Merged code / docs on main | Implementing PR | Pinned behaviour tests on main |
|---|---|---|---|---|
| IG3-VYR-07 | Cluster-7 (B114): motion templates — the 12 source-named templates | `VyralX/app/services/motion_templates.py` (sha a8474d61, 11,898 B) — `_TEMPLATE_NAMES` holds exactly the 12 names (Card Globe, Orbit Globe, Triple Scene, Spiral Stream, Cover Ring, Collage Reel, Fan Shuffle, Sweep Ring, Scatter Zoom, Sphere Wall, Totem Wall, Card Tunnel); `TEMPLATE_LIBRARY` built from them; logo cap 5 MB, loops 5s–30s, export matrix MP4-H.264/WebM-VP9, 720p–8K, 30/60 fps, loops 1x–4x; FastAPI router at `/api/v1/motion-templates/*` | #828 via replacement #847 | `VyralX/tests/test_ig3_vyr07_motion_templates.py` (6 tests) |
| IG3-VYR-08 | Cluster-7 (B125): idea generator over operator-supplied records only | `VyralX/app/services/idea_generator.py` (sha 1cf9db04, 10,394 B) — `analyse_performers` / `generate_ideas`; input is operator-supplied niche top-performer records; the module makes no platform calls; ideas carry provenance and rank deterministically | #825 via replacement #848 | `VyralX/tests/test_ig3_vyr08_idea_generator.py` (4 tests) |
| IG3-VYR-09 | Cluster-7 (B131): production rules | `VyralX/app/services/production_rules.py` (sha 126d8140, 9,430 B) + the single rules folder `VyralX/app/data/production_rules.json` — exactly 5 rules: `hook_first_second`, `visuals_timed_to_voice`, `pictures_land_on_words`, `motion_until_last_frame`, `frame_review_60fps`; `load_rules` / `check_plan` | #830 via replacement #849 | `VyralX/tests/test_ig3_vyr09_production_rules.py` (4 tests) |
| IG3-VYR-10 | Cluster-7 (B120): scene-assembly evaluation (documentation) | `VyralX/docs/SCENE_ASSEMBLY_EVALUATION.md` (sha 51da1a48, 7,069 B) — evaluation, not code: the composition layer exists (`short_video_assembly`, `film_pipeline`), per-scene clip generation stays OFF-FLEET by design, the generated-footage admission gate stays CLOSED | #832 (direct merge 1ccf7058) | `VyralX/tests/test_ig3_vyr10_scene_assembly_eval.py` (5 tests) |

Offline test filed with this record: `VyralX/tests/test_vyr074_mapping.py` (5 tests, stdlib-only — reads the files as text, never imports the app). It pins the mapping above: the 12 template names in `_TEMPLATE_NAMES`, the idea-generator functions + operator-supplied-only marker, the 5 rule ids in the JSON folder, the evaluation doc's recorded split, and the presence of the four pinned behaviour tests. Run locally this run (see §3); added to the VyralX contracts list in `.github/workflows/owner-workflows.yml` so CI runs it.

## 2. Verification plan — live leg (NOT run; gated)

Per the board acceptance: for EACH item, run it in the live agent on a real task and file the live evidence (what ran, on which server, with what result, including the failure case). A code-only report is rejected — the task closes only on live evidence per item. Any item that fails live gets a named fix task filed from this record; no failing item is marked verified.

Planned live steps, per item (VyralX-Server, loop OFF, uploader paused, renders held unlisted):

- **IG3-VYR-07:** fill each of the 12 templates through `POST /api/v1/motion-templates/fill` with real media slots (≥1 item), a logo under the 5 MB cap, and a loop in 5s–30s; request an export spec per format/resolution in the matrix; record per-template success/failure and the failure case (logo over cap, empty slots, loop out of range).
- **IG3-VYR-08:** supply real operator-exported niche top-performer records; run `analyse_performers` + `generate_ideas`; check ideas carry provenance, rank deterministically, and unmeasured sources say so; failure case: a record without metrics must carry `engagement_rate: None`, never an estimate.
- **IG3-VYR-09:** run `check_plan` against a real production plan; verify per-rule verdicts with measured numbers; failure case: break one rule and confirm exactly that rule's verdict fails.
- **IG3-VYR-10:** documentation item — live leg is the composition-layer probe, not a render: confirm `short_video_assembly.build_assembly_plan` + `film_pipeline.build_film` run on the live server for a real script, and confirm no per-scene clip generation route is invoked (gate stays CLOSED).

Extreme-condition cases (bad inputs) for the live leg: missing BGM, doubled captions, watermark — machine-QA under each, plus metrics-sync against the real channel.

## 3. What was run this run (repo-side only)

- Mapping verified first-hand via the GitHub API against main ce3c817f: tree listing + full reads of `motion_templates.py`, `idea_generator.py`, `production_rules.py`, `SCENE_ASSEMBLY_EVALUATION.md`, `production_rules.json` (5 rules, ids as tabled), and the four IG3 test-file headers.
- New test `VyralX/tests/test_vyr074_mapping.py`: 5/5 passed locally against the real mapped files fetched from main ce3c817f (manual runner — system python has no pytest installed; CI runs pytest). One test bug caught and fixed by the local run: the template-name regex initially captured the motion_family too.
- Work PR: evidence doc + mapping test + workflow-list entry + board flip CLAIMED→IN_REVIEW. CI (result verified live after filing).

## 4. Gates — live leg still blocked

- **Owner stop order:** not lifted in any hub comment through the latest read (comment 7142315021, 2026-11-25 01:05 IST). No live step taken.
- **VYR-056 yt-dlp/EJS repair (Muse 18, PR #1710):** CI 9/9 green but HELD for full-diff review in coordinator watch 7141869992 (00:47 IST run) — merge next run, not yet merged. Media QA gates stay blocked until it lands.
- **VyralX-Server route:** no clearance granted in the latest watches; the VyralX-Server verification probe is still owed (watch 7141869992, carried item 3).
- **Failure injection:** HELD pending owner clearance (21:57 watch ruling 3).

## 5. States

- Implemented: PARTIAL (repo-side legs filed; live leg not run)
- Tested: PARTIAL (mapping test run locally + CI; live verification not run)
- Merged: NO (work PR open; claim PR #1690 merged)
- Deployed: N/A (verification task — no deploy)
- Production-verified: NO — the live leg is the task, and it is gated (see §4)
