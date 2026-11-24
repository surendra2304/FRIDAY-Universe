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

## Usage

- 0% of free weekly limit (checked this run; reset Mon Nov 30, 3:03 PM IST). Additional tokens 0% used.

— Muse TP3
