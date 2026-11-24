# TASK-VYR-075 — REPO-IMPLEMENT: VyralX repos, wave 1 — evidence

- **Task:** TASK-VYR-075 (P1, wave 1) — Uplika (adapt), Hypit (adapt),
  HyperFrames (adapt), LTX-2 (reject), Claude Ads (adapt),
  Open Generative AI (reference-only), target VyralX.
- **Worker:** Muse 7. **Claim:** issue #1483 comment 7138902105
  (2026-11-24 ~22:47 IST). **Branch:**
  `muse7/task-vyr-075-repo-implement-wave1` from main `3a2009b8`.
- **Source of the six verdicts:** `IntelX/intelx/registries/scouted_repos.json`
  (cards uplika.md, hypit.md, hyperframes.md, ltx-2.md, claude-ads.md,
  open-generative-ai.md). The board record cites
  `PRODUCTION-VERIFICATION-PROGRAMME.md` as its source; that file is
  **not in the repo** (code search returns 0 hits) — flagged here, the
  registry is the verified source used instead.
- **States:** implemented YES (repo-side, see below), tested YES (24 new
  tests + existing suites, all green — see §7), merged NO (work PR owed),
  deployed NO (no server change in this PR), production-verified PARTIAL
  (repo-side + local live-path proof done; VyralX-Server live legs owed
  under the owner freeze — see §8).

## 1. Uplika — ADAPT — done repo-side, live route added

The pattern (approval-gated channel-operator loop) already existed
natively in `VyralX/app/services/channel_operator.py` (TASK-IG-VYR-01):
analytics → winning formats → packaging → schedule → comment drafts,
all `pending_review`, `publish=False`, privacy `unlisted`. It was
reachable only from its unit tests — it was NOT wired into any live
route or pipeline.

New in this PR: `POST /api/v1/vyralx/engines/operator/cycle`
(`VyralX/app/services/real_media_routes.py`).

Live end-to-end proof (new test
`VyralX/tests/test_vyr075_operator_cycle.py`, TestClient against the
mounted router):

- Snapshot with measured views (12,000 + 8,000) → winner `explainer`,
  `measured_videos` 2, plan `publishes_anything` False, every proposal
  and schedule entry `publish` False / `unlisted`, comment drafts
  `posted` False.
- Snapshot with no metrics → `metrics_available` False,
  `winning_formats` [], `measured_videos` 0 — no winner is named
  from no views.
- Failure cases (all 422): unknown lane, empty topic, naive start
  (no timezone).

The paid Uplika service itself is never touched (setup repo only, no
code; $10/mo/brand after free/beta stays the owner's call).

## 2. Hypit — ADAPT — done repo-side, clone leg wired live

The pattern (word-anchored format cloning, hook scoring, ffmpeg
keyframe extraction) already existed natively in
`VyralX/app/services/format_clone.py` (TASK-IG-VYR-03). Only
`score_hook` was reachable from the live path (via competitor_ads /
idea_generator); the clone leg itself was not.

New in this PR (all under `/api/v1/vyralx/engines/format-clone/`):

- `POST /template` — word-anchored template from timed words
  (structure only: `carries_reference_media` False,
  `carries_reference_words` False).
- `POST /clone` — new script mapped onto the template's beats,
  plan stays `pending_review`, `publish` False.
- `POST /variants` — one clone plan per script.
- `POST /keyframes` — scene-change keyframes from a reference video;
  the video must live inside VyralX media storage (traversal
  defence); missing file / missing ffmpeg returns honest
  `available: False`, never invented frames.

Live end-to-end proof (new test
`VyralX/tests/test_vyr075_format_clone_e2e.py`): template from 24
timed words → clone plan for a new script (hook beat first, hook
score > 0) → 2 variants; keyframes extracted from a real
ffmpeg-generated test video (≥1 real PNG frame on disk); missing
video → `available` False, frames []; path outside media storage
→ 422. Failure cases: empty timed words, empty script, template
without beats — all 422.

## 3. HyperFrames — ADAPT — real render added (code render)

The pre-existing `VyralX/app/services/real_hyperframes.py` was a
model layer only (scene math, estimates, manifests). `render_script`
returned estimates; nothing rendered anything.

New in this PR: a real render — `render_film()` in
`real_hyperframes.py` plus `POST /api/v1/vyralx/engines/hyperframes/render`.

- Each scene becomes a Pillow frame (background colour + title +
  wrapped text) and FFmpeg encodes the frames to a real MP4
  (libx264, yuv420p). The film is probed with ffprobe and
  signal-checked with `media_quality.analyze_media_signals`.
- This is a CODE render (the Hypit $0 pattern), explicitly NOT a
  headless-Chrome render of the HTML: the result dict carries
  `"renderer": "code_render_pillow_ffmpeg"` and the Chrome note on
  its face. Headless-Chrome rendering never runs inside the fleet
  service (`film_pipeline.render_gate`: owner_machine / post_arm
  only) — the Chrome-fidelity leg stays gated off-fleet.
- The film is SILENT by design — no BGM track (BGM is a separate
  mix step, `renderer.render_video` `bgm_path`); the result says so.

Proof (local run, this VM, ffmpeg 8.1.2):

- Demo film from a 2-scene script (`Demo`, 3 s/scene, preset
  `shorts`): MP4, h264, 1080x1920, 6.000 s, 38,394 bytes,
  sha256 `ec76a4f027eb8b335f2da44e7f1f3e3e36be16326e9d2dfa830f36b2d206ea4d`.
- New test `VyralX/tests/test_vyr075_hyperframes_render.py` renders
  films in both presets (shorts 1080x1920, long 1920x1080) and
  verifies them with ffprobe (codec, resolution, duration) plus
  the route end-to-end (create-script → render → file exists).
- Failure cases, all honest: unknown script → KeyError / route 404;
  empty script → ValueError; unknown preset → ValueError / route 400;
  bad `#RRGGBB` colour → ValueError; ffmpeg missing →
  `available: False` with the reason.

## 4. LTX-2 — REJECT — live evidence of absence

Verdict (registry card + `VyralX/docs/GENERATED_FOOTAGE.md` line 52):
reject on hardware alone — 22B model, ~66 GiB weights, no GPU on
the fleet, no CPU path; revisit only if the owner gets GPU hardware.

Live evidence (new test `VyralX/tests/test_vyr075_ltx2_reject.py`):

- A fully-provenanced LTX-2.5 clip (generator, model, prompt,
  timestamp, media URL, commercial+derivative rights assertion with
  terms URL) through `generated_footage.intake_generated_clip`
  evaluates `terms_class` `ai_generated_terms`, `terms_grant` True —
  and is STILL refused as a remix candidate (`candidate` False:
  the VYR-004 gate admits only cc0 / public_domain / cc_by /
  cc_by_sa / owner).
- The reject verdict is recorded in `VyralX/docs/GENERATED_FOOTAGE.md`.
- Guardrail scan of `VyralX/app/**/*.py`: the only LTX mentions are
  the model-catalog name in `real_open_higgsfield.py` (a string in a
  reference list, no execution path behind it — `generate()` refuses
  all models) and the intake module's docstring citing the reject
  verdict. No LTX import, no weights path, no Hugging Face download,
  no inference call anywhere in VyralX's production code.

## 5. Claude Ads — ADAPT — live route added; gate hole found + fixed

The model layer (`VyralX/app/services/real_claude_ads.py`: accounts,
campaigns, audits, capability gates, versioned reports) existed and
was reachable via `/ads/campaign`, `/ads/compliance`,
`/ads/report/{platform}`. Two gaps:

- No route exposed the audit or the capability-gated action.
- **Gate hole (found by this task's end-to-end test):**
  `manage_campaign` passed the route-level action (`pause` /
  `activate`) straight to `CapabilityGate.authorize_action`, but the
  gate's action map only knows `campaign_pause` — an unknown action
  required NOTHING, so every pause was authorised regardless of
  capabilities. Fixed in this PR: `pause` / `activate` now map to
  `campaign_pause` for the authorisation check.

New in this PR: `POST /engines/ads/audit` and
`POST /engines/ads/campaign/{campaign_id}/action`.

Live end-to-end proof (new test
`VyralX/tests/test_vyr075_claude_ads_e2e.py`, TestClient):

- Create campaign → compliance (disclosed creative passes) →
  audit of the known account (0 critical) → audit of an unknown
  account (critical finding `Account not found`, still 200 — the
  audit IS the result) → pause without `campaign_control` → 403
  with `missing: ["campaign_control"]` → pause with the capability
  → success → unknown campaign → 404 → report aggregates real
  in-memory state (`total_spend` 0.0 — no spend exists).
- Guardrail: the module imports no HTTP client — it never calls an
  ad platform (there are no ad accounts; upstream is pre-release
  with scoring disabled).

## 6. Open Generative AI — REFERENCE-ONLY — fabricated generate() fixed

The registry verdict is reference-only: the studio shell is free
and MIT, but using it means paying the MuAPI gateway per generation
(barred by the FREE-only rule) and the free local engines need a
GPU the fleet does not have.

**Defect found by this task:** `MultiModelStudio.generate()`
fabricated a result — an `output_path` for a file never written,
an `elapsed` time computed from an estimate (`expected * 0.85`), a
`quality_score` derived from the fabrication — and the
`/studio/generate` route returned it as `"status": "success"`.
Two existing tests asserted this behaviour.

Fixed in this PR (`VyralX/app/services/real_open_higgsfield.py`):

- `generate()` now returns `available: False`, empty `output_path`,
  `elapsed` 0.0, `quality_score` 0.0, with
  `STUDIO_UNAVAILABLE_REASON` (no local GPU; paid MuAPI barred by
  the FREE-only rule; studio is a reference catalog only). Refused
  calls are NOT appended to `results`, so `total_generations`
  counts only media actually produced (zero).
- The route now answers 503 with the honest reason.
- The two existing tests that asserted fabrication are updated to
  assert the honest behaviour (`tests/test_real_batch4a.py`
  `test_multi_model_studio`,
  `tests/test_e2e_real_repo_integration.py`
  `test_higgsfield_generate`).

What VyralX keeps (the reference value): the multi-studio layout
pattern for a future creation console — new data file
`VyralX/app/data/studio_layout_reference.json` (note: `data/` is
gitignored; this file is force-added like the other shipped data
files) + `studio_layout_reference()` + `GET /engines/studio/layout-reference`.
The 5 studios named in the verified registry card are listed
(Image, Video, Lip Sync, Cinema, Workflows); the upstream lists 14
and the remaining 9 are marked unverified rather than guessed.
Guardrail test: no MuAPI endpoint / key / HTTP call anywhere in
`VyralX/app` (naming MuAPI in a refusal reason is required and
allowed; the same refusal pattern already exists in
`shorts_generator.py`).

## 7. Tests run

All on this VM (Python 3.12.3, venv from `VyralX/requirements.lock`
+ pytest/ruff; ffmpeg 8.1.2, node v24.22.1):

- New tests (6 files, 24 tests): `24 passed`.
  - `VyralX/tests/test_vyr075_hyperframes_render.py`
  - `VyralX/tests/test_vyr075_claude_ads_e2e.py`
  - `VyralX/tests/test_vyr075_operator_cycle.py`
  - `VyralX/tests/test_vyr075_format_clone_e2e.py`
  - `VyralX/tests/test_vyr075_ltx2_reject.py`
  - `VyralX/tests/test_vyr075_studio_reference.py`
- `tests/test_real_batch4a.py` (full file): `192 passed`.
- `tests/test_e2e_real_repo_integration.py::TestVyralXE2E` +
  `tests/test_deep_universe_engines_full.py::TestVyralXGrowthDeepEngines`:
  `11 passed`.
- VyralX full suite (119 files, run in 3 chunks from `VyralX/`,
  junit XML): **1,126 tests — 1,119 passed, 7 failed**. All 7
  failures are PRE-EXISTING: each was re-run against a pristine
  worktree at main `3a2009b8` and fails identically there, and none
  touches a file this PR changes:
  - `test_ai_visuals::test_generate_scene_visual_mocked` — mocked
    URL parses as an invalid port (`':1]'`).
  - `test_mixkit::test_search_videos_returns_candidates` and
    `test_search_videos_empty_query_falls_back` — network-dependent
    (the first is flaky: it passed in one run, failed in the next).
  - `test_postgres_database::test_make_engine_postgresql_configuration`
    — `ModuleNotFoundError: No module named 'psycopg2'` (the lock
    does not include it).
  - `test_universe_nine_peers::test_configured_peers_all_nine` —
    `'memora'` missing from the configured peer set.
  - `test_vyr009_compliance_gate` (2 tests) —
    `ImportError: cannot import name '_run' from
    'app.services.viral_remix'`.
- `ruff check` on every file touched by this PR: clean (0 errors).
  Notes: full-tree `ruff check app tests scripts` reports 142
  pre-existing errors in untouched files, and the two touched
  repo-root test files carry 23 pre-existing errors (22 + 1, same
  counts as main) — none introduced by this PR. One pre-existing
  ruff error in a file this PR touches was fixed as a drive-by:
  `real_hyperframes.py` `SceneTransition.render_css` assigned an
  unused `direction` (F841); the assignment is removed, the
  returned CSS is byte-identical.

## 8. Live legs owed (not attempted — freeze in force)

- Owner stop order ~16:42 IST 2026-11-24 still in force: NO live
  moves. The acceptance's end-to-end render/discovery cycle on
  VyralX-Server with real source videos + machine-QA under bad
  inputs (missing BGM, doubled captions, watermark) + metrics-sync
  against the real channel is therefore OWED, not done. Loop stays
  OFF, uploader paused, renders held unlisted — no change made
  here.
- Real source videos are additionally blocked by the yt-dlp/EJS
  break (VYR-056; precise cause in M18 status 7138471168: deno
  2.9.8 EJS solver crashes `TypeError: a.addOnDisposeCallback is
  not a function`; repair options on M18's branch commit 55c189dd;
  any server-side version change needs coordinator/owner direction).
- VyralX-Server route was never granted to Muse 7 (M18 holds scoped
  read-only for VYR-051/VYR-056); the route must be requested via
  Muse when the freeze lifts.

## 9. Files changed

- `VyralX/app/services/real_hyperframes.py` (+287/-~0): code-rendered
  film (`render_scene_frame`, `render_film`, `HyperframesManager.render_film`)
  + the pre-existing F841 drive-by fix.
- `VyralX/app/services/real_media_routes.py` (+271): render, ads
  audit/action, operator cycle, format-clone (4 routes), studio
  layout-reference routes; `/studio/generate` now 503s honestly.
- `VyralX/app/services/real_claude_ads.py` (+8): pause/activate →
  `campaign_pause` gate mapping (the hole fix).
- `VyralX/app/services/real_open_higgsfield.py` (+68): honest
  `generate()` refusal + `studio_layout_reference()`.
- `VyralX/app/data/studio_layout_reference.json` (new, force-added):
  multi-studio layout reference.
- `VyralX/tests/test_vyr075_*.py` (6 new files, 24 tests).
- `tests/test_real_batch4a.py`, `tests/test_e2e_real_repo_integration.py`:
  the two fabrication-asserting tests updated to assert honest behaviour.
- `docs/collaboration/WORK_BOARD.yaml`: TASK-VYR-075 AVAILABLE →
  IN_REVIEW, owner muse_7, branch
  `muse7/task-vyr-075-repo-implement-wave1`, pr (work PR number).

— Muse 7
