# TASK-VYR-077 — REPO-IMPLEMENT: VyralX repos (wave 1) — Checkpoint 1 (repo-side scoping)

- Task: TASK-VYR-077, P1, REPO-IMPLEMENT VyralX repos, wave 1.
- Claim: hub issue #1483 comment 7139661577 (2026-11-24 ~23:15 IST). Branch `musetp3/task-vyr-077-repo-implement-wave1` from main `6e3fe049`.
- Board verified first-hand this run: main `6e3fe049`, TASK-VYR-077 AVAILABLE / owner null / P1, branch null, pr null. No competing claim on the hub through the latest read (938 comments). Pool order: Wave 1 Stratex fully spoken for (coordinator watch 22:17 IST); VYR-077 is the first free Wave 1 VyralX task (VYR-070 M10, VYR-071 M5 pre-staged, VYR-072 M14, VYR-073 M14 pre-staged, VYR-074 M4, VYR-075 M7, VYR-076 M9).
- State: implemented NO, tested NO, merged NO, deployed NO, production-verified NO. Checkpoint 1 only: scoping.

## Scope (board record)

- Adapt: Short Video Factory, AI YouTube Shorts Generator.
- Reference-only: Social Media Agent / LangChain, Lemo-Opuscar, MG Styles 15, Claude Animation Base.
- Target: VyralX.
- Acceptance: adapt entries must run in VyralX's live production path, proven by one real end-to-end use incl. a failure case; reference-only entries need live evidence (trial or guardrail proof of absence from every production path), filed per repo. Live leg: real end-to-end render/discovery cycle on VyralX-Server with real source videos + machine-QA under bad inputs (missing BGM, doubled captions, watermark) + metrics-sync against the real channel; loop stays OFF, uploader paused, renders held unlisted.

## VyralX structure (verified from live main tree, 6e3fe049)

- VyralX has 436 tree entries; top level: `app/`, `docs/`, `scripts/`, `tests/`.
- `VyralX/app/` has 188 entries. Entry points: `app/main.py`, `app/config.py`, `app/database.py`, `app/media_store.py`.
- Render / caption / audio services relevant to the two adapt repos: `app/services/captions.py`, `app/services/audio_mixer.py`, `app/services/film_pipeline.py`, `app/services/full_pipeline_engine.py`, `app/services/discovery.py`, `app/services/generated_footage.py`, `app/services/format_clone.py`, `app/services/format_templates.py`.
- Docs: `VyralX/README.md` (12,354 bytes), `VyralX/docs/ARCHITECTURE.md`, `VyralX/docs/OPERATIONS.md`, `VyralX/docs/BGM_SHELF.md`.
- No code has been changed yet. No adapt component has been wired into any production path yet.

## Repo scouting (in progress)

- The six scouted repo names come from the board record only; no source URLs were in the board record, and no URLs are claimed here.
- Scouting is running in parallel (public GitHub search, authenticated as surendra2304, plus web search as fallback): exact owner/name, license, stars, key components, and whether the core runs without paid keys, per repo. Results will be filed here as Checkpoint 2, with only URLs returned by the search tools — no invented URLs.
- Reference-only judgements will not be paper-only: each needs a live trial or a guardrail proof of absence from every production path, filed per repo.

## Live leg — BLOCKED (bridge pending)

- The VyralX-Server live leg cannot run yet: the Oracle bridge link is still pending via secure entry flow (asked Surendra 2026-11-24 ~23:16 IST; GitHub PAT is already connected and verified, so it was not asked for again). No bridge, no fleet shell, no CREDENTIALS.md read.
- Loop stays OFF, uploader paused, renders held unlisted, per the task. No deploys without Muse clearance.
- Repo-side work proceeds first: scouting, adapt design against the services above, local trial with no paid keys where possible. The live end-to-end leg and machine-QA under bad inputs will be posted as blocked until the bridge arrives — not assumed.

## Checkpoint 2 — repo scouting (research only, 2026-11-24 ~23:20 IST)

- All six scouted repos were identified from public GitHub search / web search. No repos were cloned, downloaded, installed or run. No GitHub posts, branches, PRs, fleet or bridge work was done for scouting. URLs below are only those returned by the search tools.
- One caveat: a raw-text fetch of the Lemo-Opuscar LICENSE/README and the LangChain social-media-agent README was flagged by an execution-risk check during scouting. That output was not run, cloned, installed or processed, and no commands or scripts from it are reproduced here. The identifications for repos 3 and 4 rest on the unflagged GitHub search API results, web search and root directory listings — not on the flagged output. Lemo-Opuscar's license is therefore reported as uncertain until its LICENSE file is read directly.

1. Short Video Factory (adapt) — YILS-LIN/short-video-factory — https://github.com/YILS-LIN/short-video-factory — AGPL-3.0, 6,279 stars, 862 forks, confidence high. One-click short-video generation, AI batch auto-clipping, Electron/Vue/TypeScript desktop tool; ffmpeg-static, subtitle parsing, pixi.js effects, LLM via Vercel AI SDK. Closest to a full short-video factory for VyralX's excerpt series. Needs an LLM API key for AI generation; rendering is local. FLAG: AGPL-3.0 is copyleft — adapting its code into VyralX needs an AGPL-compliance decision (source disclosure) before merging any of its code.
2. AI YouTube Shorts Generator (adapt) — Anil-matcha/AI-Youtube-Shorts-Generator — https://github.com/Anil-matcha/AI-Youtube-Shorts-Generator — MIT, 6,536 stars, 1,202 forks, confidence high. Turns long-form YouTube videos into viral 9:16 shorts: LLM highlight detection, Whisper transcription, auto-cropping. Key files: main.py, shorts_generator/ (pipeline.py, highlights.py, transcriber.py, clipper.py, downloader.py, config.py, muapi.py, local/). Local mode (yt-dlp + faster-whisper + FFmpeg/OpenCV face tracking) is the most VyralX-friendly path; only the highlight-ranking LLM call is remote. Alternate same-named candidate: SaarD00/AI-Youtube-Shorts-Generator (MIT, 280 stars) — generates from trending topics rather than excerpting long-form, so less likely the match for VyralX's excerpt series.
3. Social Media Agent / LangChain (reference-only) — langchain-ai/social-media-agent — https://github.com/langchain-ai/social-media-agent — MIT, 3,057 stars, ~552 forks, confidence high. TypeScript/LangGraph agent for sourcing, curating and scheduling social posts with human-in-the-loop. Publishing/distribution only, not video rendering. Its human-in-the-loop review step maps onto VyralX's review-first rule (unlisted, review-first). Needs Anthropic + LangSmith + Arcade keys.
4. Lemo-Opuscar (reference-only) — lemomo-ai/lemo-opuscar — https://github.com/lemomo-ai/lemo-opuscar — license uncertain (GitHub API reports NOASSERTION; repo has LICENSE, LICENSES/ and REUSE.toml — verify the license text before using any material), 20,601 stars, 2,651 forks, confidence high. Toolbox of 99 film styles made in code for Claude Code, each a style prompt plus a demo film. A style library VyralX could borrow for distinct visual looks per category, without a video model. No captions, TTS or editing pipeline.
5. MG Styles 15 (reference-only) — Vincentwei1021/mg-styles-15 — https://github.com/Vincentwei1021/mg-styles-15 — MIT, 3,914 stars, 486 forks, confidence high. 15 motion-design styles, each made by Claude Opus 5.5 writing code from one prompt; prompts/, demos/, videos/, harness/, lib/, template + rubric for judging new styles. Compact MIT-licensed motion-graphics style library for title cards, transitions and motion looks. No captions, TTS or editing pipeline.
6. Claude Animation Base (reference-only) — JohnHeibel/ClaudeAnimationBase — https://github.com/JohnHeibel/ClaudeAnimationBase — MIT, 3,230 stars, 315 forks, confidence high. Starter kit for animating hand-painted cartoons with Claude: p5.js + p5.brush, Clawd character, 31 acted emotions, headless Chromium frame-accurate renderer to MP4 (render.mjs). Rendering is local, no paid key needed; Claude access only to author new animations. Niche fit (cartoon explainers/intros), not a general short-video engine.

- Next: adapt design for the two adapt repos against VyralX's services (captions, audio_mixer, film_pipeline, full_pipeline_engine, discovery); AGPL-compliance decision owed before any Short Video Factory code is merged; Lemo-Opuscar license read owed before any of its material is used. Live trials for reference-only repos still need the bridge (blocked).

## Checkpoint 3 — adapt design (2026-11-24 ~23:30 IST)

- Baseline read first-hand from live main 6e3fe049: both adapt repos already have pattern-only ports in VyralX from earlier IG2 tasks, with tests. No upstream code is vendored in either. VYR-077 is the wave-1 implementation that makes these ports actually run in VyralX's live production path, proven by one real end-to-end use including a failure case.

### Repo 1 — Short Video Factory (adapt) — port exists: `VyralX/app/services/shorts_factory.py` (TASK-IG2-VYR-03, 190 lines, tested)

- What the port already does: headless planning core — prompt + storyboard material in, deterministic copy (hook + narration + title), compliance screen via `compliance_gate.find_finance_advice`, EdgeTTS voice plan (free), auto-mix segment plan, timed subtitle cues via VyralX's own `captions.segment_script`, batch queue via `fill_batch` that fills to a preset target. Owner rules baked in: Shorts <60s (rejected, never silently trimmed), lanes space_science / history / tech_ai, money is stories never advice, storyboard materials must carry licence + source URL or the job is refused, anything published stays UNLISTED.
- What does NOT transfer (per the port's own docstring): the upstream app is a TypeScript/Electron desktop GUI and cannot run inside VyralX's ~180MB service cap on the ~956MB fleet VMs. The port renders nothing itself; rendering is by VyralX's existing renderer.
- Gaps VYR-077 must close: (a) the port plans from storyboard materials but does not auto-clip existing footage — upstream's AI batch auto-clipping has no VyralX equivalent yet; the live path must cut real source material, not just plan from it. (b) Upstream subtitle parsing and pixi.js effects have no fleet equivalent (film_pipeline is stdlib-only, no Node/Chromium) — effects must be expressed through VyralX's own `motion_templates` / `motion_graphics`, or recorded as absent. (c) The port is not yet wired into `full_pipeline_engine.execute_pipeline` as a stage — it must be called by the live pipeline, not only by its unit test.
- AGPL: pattern-only, no upstream code vendored. The compliance decision is still owed before ANY Short Video Factory code is merged into VyralX. This design keeps pattern-only.

### Repo 2 — AI YouTube Shorts Generator (adapt) — port exists: `VyralX/app/services/shorts_generator.py` (TASK-IG2-VYR-04, 176 lines, tested)

- What the port already does: long-form to Shorts repurposing, LOCAL mode only, from a transcript dict — deterministic highlight-window scoring on named virality signals (`score_window`), de-duplication of overlapping windows, 9:16 vertical-crop plans. Binding mode rule: the upstream default `--mode api` (MuAPI, pay-per-call) is rejected by `ensure_local_mode` / `PaidModeRejected`.
- Upstream local mode (read first-hand from Anil-matcha main): yt-dlp download (`local/downloader.py`) → faster-whisper transcribe (`local/transcriber.py`, returns `{duration, segments[start, end, text]}`, with SRT cache) → LLM highlight ranking (`local/llm.py`, OpenAI or Gemini) → ffmpeg subclip + OpenCV face-aware vertical crop (`local/clipper.py`, Haar cascade, no external models).
- Gaps VYR-077 must close: (a) transcript source — VyralX has no faster-whisper transcriber yet; confirm whether faster-whisper is installed on VyralX-Server, and if absent, record the install as a fleet change needing Muse clearance (FREE, pip, but a fleet change all the same). (b) Download — VyralX has `ytdlp_support.py` (cookie-jar handling for YouTube's bot challenge) and `youtube.py`; wire the download through it. (c) Clipping — VyralX has `renderer.py` (`render_video`, ffmpeg subprocess) and `video_editor.py`, but no OpenCV face-aware vertical crop; the crop must be reimplemented natively (ffmpeg crop filter, or an OpenCV step if OpenCV is present on the fleet — check first, do not assume). (d) Ranking — the upstream LLM step is PAID and must NOT be used; VyralX's deterministic `score_window` replaces it, and the design keeps it that way (FREE ONLY).
- Live path wiring: `generate_shorts` output (clip plans) → `captions.py` (`write_srt` / `write_ass`) → `audio_mixer.py` (voiceover ducking, BGM) → `renderer.render_video` → unlisted, review-first. One real long-form source, end to end.

### Reference-only repos — evidence plan

- Social Media Agent / LangChain (MIT): publishing/distribution only, no video code. Evidence: map its human-in-the-loop review step to VyralX's existing `gatekeeper.py`, `compliance_gate.py` and `review_notes.py`; guardrail proof that its publishing code is absent from every VyralX production path.
- Lemo-Opuscar: license read owed FIRST (GitHub API: NOASSERTION; repo has LICENSE, LICENSES/, REUSE.toml). No material used until the licence text is read. If it is not permissive, the evidence is the read itself plus guardrail proof of absence.
- MG Styles 15 (MIT): 15 motion-design styles as prompts + demos + source. Evidence: trial one style prompt as a title-card / transition look through VyralX's own `motion_templates.py` / `motion_graphics.py`, unlisted; if a style cannot be expressed there, record that instead of vendoring its code.
- Claude Animation Base (MIT): p5.js + headless-Chromium renderer (`render.mjs`). The fleet has no Chromium (film_pipeline: "no Node/Chromium here"). Evidence: guardrail proof of absence from the production path, unless Muse clears a local-only trial. Do not install Chromium on the fleet without Muse clearance.

### Live trial plan — CLEARANCE REQUESTED FROM MUSE (no fleet shell run yet)

- Scope: one real end-to-end trial on VyralX-Server via the bridge, read-only checks first, then one render. Loop stays OFF, uploader paused, renders held unlisted, review-first.
- Read-only checks first: Python version, ffmpeg presence, faster-whisper installed or not, OpenCV installed or not, disk space on VyralX-Server.
- Then one real trial: a real long-form source → transcript → highlight windows → 9:16 clips → captions → BGM mix → render via `renderer.render_video`, unlisted.
- Failure case included (per acceptance): missing BGM (audio_mixer must fall back to its ambient-pad synthesis, not fail silently), doubled captions (captions dedupe), watermark (provenance_watermark handling). The trial must show the failure case handled, not just the happy path.
- Metrics-sync against the real channel is part of the acceptance but is a separate step after the render proves out; it is not claimed here.
- **I have not run any fleet shell yet. This is a clearance request: Muse, please clear or amend the live-trial scope above on #1483 before I run anything on VyralX-Server.**

## Checkpoint 4 — live-path wiring written (2026-11-24 ~23:35 IST)

- New module `VyralX/app/services/shorts_live_path.py` (272 lines) + new tests `VyralX/tests/test_vyr077_shorts_live_path.py` (116 lines, 7 tests), written on the task branch. Both files are new; no existing VyralX file was edited.
- What the wiring does: `build_factory_render_plan` turns a `shorts_factory` job spec into a render plan (preset `shorts`, 1080x1920, <60s, unlisted, pending_review, never publishes); `build_clip_render_plan` turns a `shorts_generator` clip into a render plan with its trim window, face-tracked crop filter and subtitles sliced from the transcript's timed words; `dedupe_cues` removes exact duplicate captions and counts them; `resolve_bgm` names the ambient-pad fallback when the music library has nothing; `execute_render_plan` writes the SRT via `captions.write_srt`, synthesises the ambient pad when the fallback applies, and renders with `renderer.render_video` (preset `shorts`). Nothing is uploaded or published by this module. FREE ONLY: no paid mode, no LLM call.
- Why this is the first real caller: a read-only grep of the live main tree found `shorts_factory` / `shorts_generator` imported nowhere in the live path — only mentioned in docstrings elsewhere and exercised by their IG2 unit tests. `renderer.render_video` is called live from `VyralX/app/worker.py` and `VyralX/app/services/autonomous_orchestrator.py`; the wiring calls the same renderer.
- Failure cases covered in code: missing BGM → ambient-pad fallback named in the plan; doubled captions → deduped and counted (write_srt would otherwise raise on overlap); over-long short → rejected, not trimmed.
- Lemo-Opuscar licence RESOLVED (read the full 8,315-byte LICENSE text first-hand): a custom composite licence, not a standard SPDX id (that is why the API says NOASSERTION). Docs and style prompts: CC BY-NC 4.0 plus an additional permission to read, follow, copy and adapt the docs to make your own films, commercial films included, with credit "Lemo-Opuscar by Lemomo (LemoLab)". Code (core/, tools/, styleboard/, plugin/, demo code): MIT. Demo films/pictures: CC BY 4.0. Films made with the library are yours, commercial included, no credit needed. Excluded: six voice tracks (Edge TTS / Doubao TTS terms), Clawd (Anthropic's, no licence), third-party marks and interfaces. Commercial use of the docs beyond the permission (for example selling them or putting them into a product or service for commercial advantage) needs a commercial licence. VYR-077 consequence: style prompts may be adapted to make films; the docs must NOT be shipped as a VyralX product feature. Reference-only evidence for this repo is the licence read plus a style-prompt trial, not vendored code.
- TEST VERIFICATION — NOT RUN LOCALLY, by rule: the local repo copy failed an execution-risk check, so no repo code was imported, run or tested on this VM. The 7 new tests are written and syntax-checked only (`py_compile` OK). Verification will be the repo's own CI `test` check on the PR — that is the established path and it runs the tests in CI, not on this VM. This is stated plainly, not claimed as tested.
- Main has moved: live main is now `36cde725` (was `6e3fe049` at claim). The task branch is still based at `6e3fe049`; a rebase onto current main is owed before the PR opens, per board-craft rules. The new files are additive (no edits to existing files), so no conflict is expected.
- Live-trial clearance request from checkpoint 3 is still open — no fleet shell run yet.

## Checkpoint 5 — reference-only evidence (2026-11-24 ~23:55 IST)

- No fleet shell was run for this checkpoint. All evidence below is from first-hand reads of live main 6e3fe049 (via the GitHub API) and public upstream reads. No upstream code was vendored anywhere.

### Social Media Agent / LangChain (reference-only) — review mapping + absence proof

- Upstream (from scouting, unflagged search results): a TypeScript/LangGraph agent that drafts Twitter/LinkedIn posts from a URL, with a human-in-the-loop review step, then schedules them. No video, caption, TTS or editing components.
- Correction to checkpoint 3: `VyralX/app/services/gatekeeper.py` is NOT the review gate — it is a mesh-auth client (verifies tokens with the Gatekeeper service). The real review equivalents in VyralX are: `compliance_gate.py` (TASK-VYR-009, 521 lines, enforcement layer — provenance must be present and licence-allowed, sync must be *measured* never asserted, `assert_ready_to_upload` blocks upload until the measured record passes), `remix_flow.compliance_checklist` (TASK-VYR-004, advisory checklist stored on the review-queue entry while the render waits for approval), and `review_notes.py` (operator-visible provenance notes, fact_check_notes, max 20 notes x 500 chars).
- Mapping: the upstream human-in-the-loop review step maps onto VyralX's measured gate + review queue + operator notes — stronger than a human glance, because the gate is evidence-based (measured sync, licence-checked provenance) rather than a skim before posting.
- Absence proof: a read-only grep of live VyralX/app found no Arcade API, no Tweepy, no Twitter/LinkedIn posting client. Platform names appear only as scoring tables (`viral_predictor.py`: platform weights and posting-time tables), ads platform lists (`real_claude_ads.py`) and route fields (`real_media_routes.py`). The upstream's publishing/scheduling code is absent from every VyralX production path.

### MG Styles 15 (reference-only) — style-prompt mapping

- Upstream (read first-hand): 15 prompts in `prompts/` (e.g. `01-flat-vector.md`, 7,284 chars), each a bilingual director brief — style, fixed output spec (1920x1080, 30 fps, 10 s, H.264, -14 LUFS), suggested technical route (HTML + SVG + GSAP), creative seed, signature features. The prompt itself says to change the Output size for vertical 1080x1920.
- VyralX targets: `motion_templates.py` (TASK-IG3-VYR-07, 315 lines: template library + slot editor — `list_templates`, `get_template`, `fill_template`, `export_spec`) and `motion_graphics.py` (TASK-IG-VYR-09, 145 lines: `title_card_plan`, `lower_third_plan`, `kinetic_text_plan`, `hyperframes_export` — HTML/CSS compositions).
- Mapping: an MG style prompt is the same shape as a VyralX motion-template entry — a style brief with output spec and signature features. A trial expresses one prompt (e.g. 01-flat-vector, re-specced to 1080x1920) as a `motion_templates` entry / title-card plan. No upstream code is vendored; the prompt text is a reference, not a dependency.
- Fleet constraint (honest limit): the prompt's own route needs Node + Chrome to render, and `motion_graphics.py` already records that headless-Chrome rendering is far too heavy for the ~1 GB fleet servers — compositions are artifacts rendered on the owner's machine, never on the fleet. So the style trial's render cannot happen on VyralX-Server; the evidence is the mapping plus the template entry, and any render is an owner-machine step, not a fleet step.

### Claude Animation Base (reference-only) — absence proof

- Upstream needs headless Chromium (`render.mjs`) to render p5.js frames to MP4. The fleet has no Chromium (film_pipeline: "no Node/Chromium here"; motion_graphics.py: headless Chrome far too heavy for ~1 GB fleet servers). No p5.js renderer exists in VyralX. Guardrail proof of absence from the production path; a trial would be owner-machine only, and is not claimed here.

### Lemo-Opuscar (reference-only) — licence resolved in checkpoint 4

- Licence read stands: docs/style prompts CC BY-NC 4.0 + additional permission to adapt them to make films (commercial included, with credit); code MIT; docs must not be shipped as a VyralX product feature without a commercial licence. No material used yet; a style-prompt trial follows the same owner-machine render constraint as MG Styles 15.

## Usage

- 0% of free weekly limit (checked this run; reset Mon Nov 30, 3:03 PM IST). Additional tokens 0% used.

— Muse TP3

## Checkpoint 6 — TP5 takeover scoping (2026-11-25 ~05:20 IST)

- Claim: hub issue #1483 comment 7146797722 (2026-11-25 ~04:25 IST, in the VYR-064 completion post). Branch `musetp5/task-vyr-077-repo-implement` from main `2c51d17b` (verified on origin, no commits).
- Board re-verified first-hand this run on origin/main `07c526bf`: VYR-077 AVAILABLE / owner null / branch null / pr null, P1. No competing live claim.
- Prior claim: TP3 claimed VYR-077 (hub comment 7139661577, 2026-11-24 ~23:15 IST), branch `musetp3/task-vyr-077-repo-implement-wave1` from main `6e3fe049`, checkpoints 1–5 filed in this doc. That slot is dead: TP3's branch no longer exists on origin, its work PR #1709 merged (`97944537`), no TP3 VYR-077 hub activity since checkpoint 5 (~23:55 IST 2026-11-24). My claim stands as the live claim of record. No re-do of TP3's scoping: checkpoints 1–5 stand.
- Repo-side work DONE and merged (verified first-hand on origin/main `07c526bf`): `VyralX/app/services/shorts_live_path.py` present; `VyralX/tests/test_vyr077_shorts_live_path.py` present; merge commit `97944537` ("Merge pull request #1709 from surendra2304/musetp3/task-vyr-077-repo-implement-wave1") in main history. CI green is inherited from the merge (merge authority requires fully green CI); not re-run here — no local execution of repo code on this VM, per the standing API-only pattern.
- Registry re-verified first-hand this run from origin/main `IntelX/intelx/registries/scouted_repos.json` (102 entries): all six VYR-077 entries present, fits match the board — Short Video Factory adapt (AGPL-3.0), AI YouTube Shorts Generator adapt (MIT), Social Media Agent / LangChain reference-only (MIT), Lemo-Opuscar reference-only (custom composite licence, resolved in checkpoint 4), MG Styles 15 reference-only (MIT), Claude Animation Base reference-only (MIT).
- What remains for DONE (the live leg): real end-to-end render/discovery cycle on VyralX-Server with real source videos + machine-QA under bad inputs (missing BGM, doubled captions, watermark) + metrics-sync against the real channel; loop OFF, uploader paused, renders held unlisted. HELD under the owner stop order (2026-11-24 17:26 IST, partial lift for key architecture / bridge / Inference only); coordinator watch 04:37 IST confirms live legs stay gated by the stop order. Clearance requested from Muse in this run's hub post (renewing TP3's checkpoint-3 request). No fleet shell run by TP5 in this run.
- Board flip: AVAILABLE → CLAIMED, owner muse_tp5, branch `musetp5/task-vyr-077-repo-implement`, pr (this PR) — rides in this PR.
- Next: (a) Muse clearance for the live trial; (b) once cleared, read-only fleet checks (Python / ffmpeg / faster-whisper / OpenCV / disk) then one real end-to-end trial incl. the failure case; (c) completion post with live evidence + board flip to DONE.
- States: implemented PARTIAL (repo-side wiring merged; live path not yet proven end-to-end), tested NO (live trial not run), merged PARTIAL (repo-side PR #1709 merged; this flip PR open), deployed NO, production-verified NO.
- Usage: 3% of free weekly limit (checked this run via subscription-status; reset Nov 30 14:05 IST).

— Muse TP5
