# TASK-VYR-068 — Per-tool evaluation: AutoClip

- **Task:** TASK-VYR-068 (VyralX: evaluate AutoClip / OpenShorts / ViralCutter clipping tooling for the own-content highlight pipeline)
- **Tool evaluated:** AutoClip — subtitle-driven highlight detection
- **Worker:** Muse TP6
- **Repo:** surendra2304/FRIDAY-Universe, main `be3f303ec28e3b5c9ba75e4fc23ca6b96126f557`, branch `musetp6/task-vyr-068-clipping-tooling`, hub issue #1483
- **Date:** 2026-11-25
- **Filed:** evidence for TASK-VYR-068, work PR on branch `musetp6/task-vyr-068-clipping-tooling` (2026-11-25).
- **Scope:** Evaluation only. Evaluation phase was read-only on the fleet (no `run_shell` on the Friday Bridge — only `get_system_info` / `read_text` are authorised); no YouTube downloads; loop OFF. Filed as evidence via the work PR on this branch.

## 0. Identity — which "AutoClip" this is

There are several unrelated projects called AutoClip. This evaluation is about **one** of them:

- **This tool:** `zhouxiaoka/autoclip` — "AutoClip｜一个链接，一键出片" — open-source AI video clipping & content repurposing.
  - Repo: https://github.com/zhouxiaoka/autoclip
  - Homepage: https://zhouxiaoka.github.io/autoclip_intro/en/
- **Not evaluated here:** `Farkoal2128/AutoClip-MVP` (a separate Windows/Ollama MVP, v1.2.1, also MIT), `Rohitpati8464/autoclip` (another fork-style project), or `ass-autoclip` on PyPI (BSD 3-Clause, an unrelated ASS-subtitle utility). Do not mix their claims into this file.

Established first-hand before this evaluation (not redone): **AutoClip has ZERO hits in the FRIDAY-Universe repo** — it is not referenced anywhere in the codebase today. The classification source file cited in the board evidence **does not exist anywhere on main** (full recursive tree checked, 8,546 entries, no CLASSIFICATION file) — recorded as found, not chased further.

## 1. What it is

AutoClip turns long-form video into short, ready-to-post clips. Paste a YouTube or Bilibili link, drop a local file, or import a live-stream replay (OBS Studio, Twitch, YouTube, Kick, Discord, local recording — v1.6), and it finds the best moments, tracks the speaker, burns in captions, generates covers, and exports clips for TikTok, Shorts, Reels, YouTube, Douyin, Xiaohongshu and Bilibili.

### How highlight detection works (concrete)

It is **text-first, not vision-first**: the video is treated as a transcript, and an LLM reads the subtitles like a script. The core is a 6-step pipeline, each step a dedicated Python module (`step1_outline.py` … `step6_video.py` in the earlier `src/pipeline/` layout):

1. **Outline extraction** — parse the SRT with `pysrt`; chunk subtitles into ~30-minute blocks (`TextProcessor.chunk_srt_data()`); LLM extracts a structural outline (what topics the video covers). Output: `step1_outlines.json`.
2. **Timeline extraction** — for each outline topic, the LLM locates precise start/end times against the SRT text. Output: `step2_timeline.json`.
3. **Highlight scoring** — each timeline segment is scored by the LLM on multi-dimensional criteria; the scoring criteria live in an **external prompt file** (`recommendation` prompt), not hardcoded. Output: scored clips.
4. **Title generation** — LLM titles per selected clip.
5. **Topic clustering** — groups clips into themed collections/compilations.
6. **Video generation** — FFmpeg cuts the selected ranges, applies the vertical crop / speaker framing, burns in captions, and renders the export kits.

Subtitles come from platform captions or a supplied `--srt` file; if none exist, local Whisper / SenseVoice transcription, or cloud ASR (Alibaba Bailian — audio is uploaded). The README is explicit about the limits of the text-first approach: *"For gameplay or low-dialogue streams, enable a vision-capable model"* — i.e. subtitle-only scoring misses visual-only moments. v1.6 adds a generalised "Game Highlights" path (8s+ standalone plays, tighter vision/OCR budgets), which is vision-model calls, not free signal.

### Inputs / outputs

- **Inputs:** YouTube / Bilibili URL, local video file, live-stream replay; optional SRT. Minimum length enforced by the CLI: a clip under 20 s is rejected at screening in v1.5.7 (see trial log §4); v1.5.9 release notes say the subtitle-highlight minimum was lowered from 20 s to 10 s, but that is not the version on PyPI.
- **Outputs:** up to 10 ranked clips per run (per README benchmarks), vertical or horizontal, with burned-in subtitles, cover image, title, description/hashtags and per-platform export kits. Also a desktop app, Docker web UI, CLI (`autoclip produce … --srt … --platform tiktok --json`, `autoclip outputs PROJECT_ID --export-kits`) and an MCP server (`autoclip mcp`, `start_quick_output` / `get_quick_output_status`).

### Version / commit observed

- Repo page (crawled 2026-11-25 07:41 UTC): default branch `main`, **current commit `2f511907a72cbfbb8d86639f6441967b826acb6a`**, 1,547 commits, **15,706 stars, 2,292 forks**, created 2025-07-08, 23 releases, 26 tags.
- Releases page (same crawl): latest entry is **AutoClip Desktop v1.6.1, marked Pre-release**; v1.6.0 is the latest full release. No Linux desktop build exists (macOS Apple Silicon `.dmg` / Windows x64 `-setup.exe` only; "Linux … use Docker, `uvx`, or `pip install -e .`").
- **PyPI is behind GitHub:** `autoclip-mcp` latest on PyPI is **1.5.7.post1**; the installed CLI reports `autoclip 1.5.7`. The trial below therefore tested 1.5.7, not 1.6.x.
- README benchmarks (maintainer's own numbers, Apple Silicon Mac, qwen-plus LLM cost, excluding cloud ASR / AI images): 1h 43m video with subtitles → **7.5 min / 10 clips, est. ¥0.09**; 2h 52m without subtitles (local Whisper) → **29.5 min / 10 clips, ¥0.20**.

## 2. License and cost — FREE ONLY verdict

- **Software license: MIT.** Confirmed three ways: GitHub repo metadata ("License: MIT License (MIT)"), the `LICENSE` file in the repo root, and the README ("Free, MIT-licensed, zero subscriptions — everything cuts and renders on your machine"). MIT is permissive (commercial use, modification, distribution with attribution). **The software itself passes the team's FREE ONLY rule.**
- **But the intelligence is metered.** The README FAQ states it plainly: *"AutoClip is free and MIT-licensed. Cloud analysis, transcription, and AI covers use your own API keys at provider rates."* Default provider is **DashScope (Alibaba Tongyi Qianwen / Qwen, model `qwen-plus`)**; other providers are OpenAI / OpenAI-compatible, Gemini, DeepSeek, SiliconFlow, Seed, Kimi, GLM, Grok, plus sponsored aggregators. Every highlight-detection run spends provider credits unless a local model is used.
- **Fully-free path exists, but it is not free of cost:** local analysis via **Ollama** (default `http://localhost:11434/v1`, default model `qwen2.5:7b`, no key) or **LM Studio** (`http://localhost:1234/v1`), plus local Whisper / SenseVoice transcription. That needs a local model download (the release notes say the first local-transcription component download is ~220 MB), enough RAM/CPU (or GPU) to run a 7B model, and long-video context set to 16384+ tokens or subtitles get truncated. Nothing on the VyralX fleet provides this today.
- **No subscription, no watermark, no export paywall** in the tool itself. Direct publishing uses your own Bilibili or Upload-Post account (separate service). Maintainer notes: solo-maintained, async replies, no live setup support; desktop installers are **unsigned / not notarised** (tracked in issue #119) — first-run OS warnings on macOS 15+ / Windows SmartScreen.
- **Cost verdict:** software = free (MIT). **Running it the way it is designed = pay-per-use LLM calls**, or a heavyweight local-model setup. Under the team's FREE ONLY rule as applied to *running* costs, the cloud path fails the "free to run" test; the local path is free-to-run only after provisioning Ollama + a 7B model, which the fleet does not have.

## 3. Runtime and dependencies

| Area | Observed |
|---|---|
| Language | Python (backend) + TypeScript/React (frontend) + Rust (Tauri 2 desktop shell) |
| Python | 3.10+ (3.11 recommended); CLI/MCP needs no Redis |
| Video | FFmpeg / ffprobe on PATH (bundled in desktop installers; `/usr/bin/ffmpeg` v8.1.2 on this VM satisfies it) |
| Download | yt-dlp (YouTube / Bilibili ingestion) |
| Transcription | faster-whisper (local) or SenseVoice, or Alibaba Bailian cloud ASR (audio uploaded) |
| LLM | DashScope/Qwen by default; OpenAI-compatible, Gemini, DeepSeek, SiliconFlow, Ollama, LM Studio |
| Full stack (Docker/web) | FastAPI + Celery + Redis + SQLite (PostgreSQL-upgradable); React + TypeScript + Ant Design + Vite frontend |
| Delivery | Desktop (macOS arm64 / Windows x64 only), Docker + Compose v2, CLI/MCP wheel (`uvx autoclip-mcp` / `pip install autoclip-mcp`) |
| GPU | Not required for the cloud path; local Whisper/LLM runs on CPU but slowly — GPU helps. No GPU requirement is documented as mandatory. |
| Fleet fit | **Poor.** VyralX's resident service runs under a ~180 MB cap on ~956 MB fleet VMs and its pipeline modules are pure-stdlib Python 3.10 *plan-only* code (see §5). AutoClip is a whole second stack: the trial venv alone was **327 MB** before any model download, and the Docker path adds FastAPI + Celery + Redis + a React frontend. It is an offline/batch desktop tool, not a resident-service component. |

## 4. Trial result (bounded local trial — attempted, core step blocked)

Trial directory: `/tmp/autoclip-trial` (ephemeral; nothing committed, nothing uploaded). No YouTube video was downloaded at any point; both test clips were generated locally with ffmpeg.

**Setup**
- `ffmpeg` v8.1.2 at `/usr/bin/ffmpeg` (verified: `ffmpeg version 8.1.2 … built with gcc 13`).
- Python 3.12.3 on this VM. No `uv`/`uvx`, no Ollama, no Docker on this VM.
- Test clip 1: `testsrc` 1280×720 30 fps + 440 Hz sine tone, 12 s, H.264 + AAC, 375,992 bytes (`ffprobe`: duration 12.000000). Hand-written `test.srt`, 3 cues, 0.5–11.5 s.
- Test clip 2: same construction, 30 s, with a 5-cue `test30.srt` spanning 0.5–29.5 s.
- Install: `python3 -m venv venv && ./venv/bin/pip install autoclip-mcp` — **succeeded** (exit 0, ~150 s). Resolved version **`autoclip-mcp 1.5.7.post1`**, CLI reports **`autoclip 1.5.7`**, venv **327 MB**.

**`autoclip doctor` (verbatim, abridged)**
```
数据目录 /home/hatch/.local/share/AutoClip · Python 3.12.3
✓ ffmpeg   /usr/bin/ffmpeg
✗ whisper  未安装（无字幕的视频需要；桌面应用 设置 → 转写 一键安装）
✗ 模型       dashscope · qwen-plus  未配置 API Key。需要自备密钥，到「设置 → 模型」填写提供商、密钥和模型名后再测试连接。
```
Translation: ffmpeg OK; Whisper not installed; model DashScope qwen-plus has no API key configured.

**`autoclip providers` (verbatim, abridged)** — 12 providers listed; all cloud providers "需要 key" (key required); only `ollama` and `lmstudio` are key-free (local). Current selection: `dashscope · qwen-plus (未配置 key)`.

**Attempt 1 — `produce` on the 12 s clip + SRT (bounded 120 s)**
```json
{"version": "1.5.7", "project_id": "9af2dc98-70cb-4f4d-897a-8ff8ac2eb3c8",
 "status": "failed", "phase": "failed",
 "error": "视频太短：不到 20 秒，按字幕切不出完整片段。请换一段 20 秒以上的视频。",
 "outputs": [], "ok": false}
```
"Video too short: under 20 seconds, cannot cut a complete segment from subtitles. Use a video over 20 seconds." (Process exit code was 0 despite `ok: false` — the failure is in the JSON, not the exit code.) This is v1.5.7's screening gate; v1.5.9 notes claim the minimum was later lowered to 10 s, but that version is not on PyPI.

**Attempt 2 — `produce` on the 30 s clip + SRT (bounded 120 s)**
```json
{"version": "1.5.7", "project_id": "0ab149e9-4f46-4d61-9585-077e1d29dba1",
 "status": "failed", "phase": "failed",
 "error": "没有可用的 LLM 提供商（当前选择：阿里通义千问 · qwen-plus），缺少 API Key 或本地服务地址。 需要自备 API Key（本机 Ollama / LM Studio 则先启动服务）。到「设置 → 模型」填写提供商、密钥和模型名，点「测试连接」后再试。密钥在该提供商的控制台申请，只保存在这台机器上。",
 "outputs": [], "ok": false}
```
"No usable LLM provider (currently selected: Tongyi Qianwen · qwen-plus), missing API Key or local service address. Bring your own API Key (for local Ollama / LM Studio, start the service first)."

**Attempt 3 — `run` with the local path, `--provider ollama` (bounded 60 s)**
```json
{"ok": false, "project_id": "70697e98-a216-4847-be05-5e695ea0c611",
 "error": "无法连接模型服务，请检查接口地址与网络；本地模型请先启动服务后重试。"}
```
"Cannot connect to the model service" — no Ollama is running on this VM (nothing on `localhost:11434`), and downloading a 7B model (`ollama pull qwen2.5:7b`) is heavyweight and out of the bounded scope of this trial.

**Trial conclusion:** the CLI installs cleanly, its screening stage works (it correctly rejected the 12 s clip), and `--srt` correctly skips transcription — but **the core highlight-detection step (LLM outline → timeline → scoring) could not be exercised at all**: it needs either a cloud API key (metered, not provisioned, and not free-to-run) or a local Ollama/LM Studio model (not installed). **Zero clips were produced. Nothing was uploaded anywhere.** Trial artefacts (`venv/` 327 MB, `data/` 1.5 MB with three failed project dirs) live only under `/tmp/autoclip-trial` and will not persist as deliverables.

## 5. Pipeline fit — what it duplicates vs what gap it fills

Pipeline files read first-hand for this mapping: `gta6_series.py`, `captions.py`, `viral_repurposer.py`, `short_video_assembly.py`, `forced_alignment.py`, `video_editor.py`, `montage.py`, `shorts_live_path.py`, `held_render_qa.py` (function inventory).

| VyralX stage | In-repo owner | AutoClip equivalent | Verdict |
|---|---|---|---|
| Moment-finding (semantic) | `gta6_series.find_moments()` — audio-spike (ffmpeg ebur128) + scene-cut (ffmpeg `select='gt(scene,…)'`) + transcript windows via `shorts_generator.candidate_windows`, deterministic, no LLM, no network | LLM outline → timeline → scoring over SRT | **GAP FILL — the only real one.** VyralX has no semantic/LLM moment ranking; its transcript windows are scored by deterministic heuristics. AutoClip reads the transcript for topic boundaries, scores segments and titles them. |
| Moment-finding (signal) | Same `find_moments()`; `video_editor.detect_scenes()` (histogram diff) | Vision/OCR game-highlights (v1.6) | Duplicates / weaker for VyralX's case. AutoClip's text-first scoring *misses* visual-only gameplay and silent reactions; its own docs say to enable a vision model for low-dialogue footage (more model cost). VyralX's spike+cut method exists precisely because gameplay highlights are not transcript-driven. |
| Vertical cut / reframing | `gta6_series.plan_episode_cut()` + `shorts_generator.vertical_crop_plan()` (face-center aware) | Smart reframing, speaker tracking | **Duplicates.** Speaker tracking is nicer, but the capability exists; VyralX already takes a face-center parameter. |
| Captions | `captions.write_srt()` / `write_ass()` — 6 tuned ASS styles (ViralWhite, CapCutViral, CyberNeon, …), keyword highlight colour, strict ordering/overlap validation | Burned-in captions from SRT/Whisper | **Duplicates.** VyralX's styles are already tuned for its Shorts look; AutoClip's are generic. |
| Transcription / alignment | `forced_alignment.py` (optional HTTP word-level alignment, validated against transcript + duration); `short_video_assembly.py` subtitle sources = Edge word boundaries or local Whisper | Local Whisper / SenseVoice, cloud ASR | **Partial overlap.** Local Whisper is a usable free transcription path, but VyralX already plans Edge boundaries + local Whisper. No new capability. |
| Render / montage | `montage.render_montage()` (FFmpeg multi-scene, BGM ducking, loudnorm, media-root confinement); `viral_repurposer.remix_viral_short()`; `shorts_live_path.execute_render_plan()` | FFmpeg cutting + export kits | **Duplicates.** VyralX's renderers carry BGM ducking, loudness normalisation and provenance handling AutoClip does not. |
| Assembly planning | `short_video_assembly.build_assembly_plan()` — *plan-only by design* (fleet ~180 MB cap; rendering runs batch/off-fleet) | Full local render | **Different execution model, conflicting.** AutoClip renders on the machine; VyralX deliberately does not render on the resident service. |
| Machine QA gates | `held_render_qa.run_held_render_qa()` + `gta6_series.gate_series_episode()` — caption-track count, BGM mandatory, watermark verified, loudness −24…−10 LUFS, true peak ≤ −1.0 dBFS, blank/black check; fail-closed | **Nothing equivalent.** No loudness gate, no BGM-mandatory check, no watermark/provenance, no held-for-review gate | **Gap — in the wrong direction.** AutoClip adds no QA; adopting it would bypass the gates VyralX already has. |
| Footage provenance / rights | `gta6_series.validate_footage_source()` — only `own_capture` or `earn024_campaign`, rejected before any work | Accepts any YouTube/Bilibili link; downloads via yt-dlp; no provenance or rights gate | **Conflict.** No gate at all, and download-first design assumes the YouTube download path that is broken/off-limits for this fleet (VYR-052: S2 cookie jar and niche guard still missing; owner stop order 2026-11-24 ~16:42 IST). |
| Publish / review model | Unlisted + review-first, renders held for the owner, loop OFF, uploader paused (`gta6_series`, `shorts_live_path`: `publish: False`) | One-click publish (Upload-Post to TikTok/Instagram/Shorts/X; Bilibili upload in development) | **Direct conflict.** AutoClip is built to ship clips; VyralX's model is built to hold them. |
| LLM use policy | `shorts_live_path.py` (docstring): "FREE ONLY: no paid mode, **no LLM call**, no MuAPI. The upstream LLM highlight-ranking step stays replaced by VyralX's deterministic scoring" | LLM call is the *entire* highlight engine | **Direct conflict with a deliberate design decision.** Adopting AutoClip's scoring reverses that decision. |

**Net:** one genuine gap filled (semantic, transcript-based highlight ranking with titles), everything else duplicates existing VyralX code — and the gap-fill arrives attached to a metered LLM dependency, a second full stack, no QA gates, no provenance gate, and a publish-first posture that contradicts the held-render / review-first model.

## 6. Recommendation — REJECT (adopt nothing; adapt only the idea, if ever)

**Verdict: REJECT AutoClip as a pipeline component for VyralX's own-content highlight pipeline.**

Concrete reasons, in order:

1. **Its only unique value requires a paid-or-heavyweight LLM, and VyralX has deliberately ruled that out.** Semantic scoring is the one thing VyralX lacks — but AutoClip's scoring *is* an LLM call (default DashScope `qwen-plus`, billed per use), and `shorts_live_path.py` explicitly records the decision to replace LLM highlight-ranking with deterministic scoring under FREE ONLY / no-LLM-call rules. There is no free-to-run way to use it on the fleet: no cloud key is provisioned, and the local alternative (Ollama + `qwen2.5:7b`) is not installed anywhere in the fleet. The trial proved the point: install succeeded, screening worked, and the pipeline then failed for exactly this reason — no usable LLM provider.
2. **It would bypass the QA and review model instead of strengthening it.** AutoClip has no loudness gate, no BGM-mandatory check, no watermark/provenance check, no held-render gate, and it offers one-click publishing — the opposite of VyralX's fail-closed `held_render_qa` + `gate_series_episode` + unlisted/review-first posture. Adopting it means either bolting VyralX's gates on afterwards (duplicating work) or silently dropping them.
3. **It is a second stack, not a library.** FastAPI + Celery + Redis + React + Tauri as Docker, or a 327 MB CLI venv plus model downloads, against VyralX's pure-stdlib Python 3.10 plan-only modules under a ~180 MB resident cap. There is no small, embeddable "highlight scorer" to lift out; the scoring lives inside the full app behind its own provider configuration.
4. **Its ingestion model conflicts with the fleet's constraints.** AutoClip is download-first (yt-dlp from YouTube/Bilibili) with no footage-provenance gate, while VYR-068 is own-content only, the fleet download path is broken/off-limits, and the owner stop order stands. Its subtitle-driven scoring is also the weakest fit for the GTA-6 series case — low-dialogue gameplay, where VyralX's audio-spike + scene-cut moment-finding already works without any model.
5. **Version/maintenance risk is real but secondary:** solo maintainer, unsigned/unnotarised installers, PyPI (1.5.7.post1) behind GitHub releases (v1.6.1 pre-release). Not disqualifying alone; it matters only because the case for adoption is already weak.

**What to do instead (adapt, not adopt):** if the team ever wants semantic scoring, the cheaper path is to port AutoClip's *staging* — outline → timeline → score → title, with scoring criteria in an external prompt file — as a plan-only step onto the fleet's existing free-tier LLM keys, gated by `held_render_qa` and the existing review-first flow. That borrows the idea (which is genuinely good) without importing the stack, the metered dependency, or the publish-first posture. That is a future decision for the coordinator, not a recommendation to build now: VyralX's deterministic scoring is the recorded design, and nothing in this evaluation shows it failing at its job.

## 7. Sources observed

- https://github.com/zhouxiaoka/autoclip — repo (MIT; main `2f511907a72cbfbb8d86639f6441967b826acb6a`; 15,706 stars; 2,292 forks; crawled 2026-11-25 07:41 UTC)
- https://github.com/zhouxiaoka/autoclip/releases — v1.6.1 (pre-release), v1.6.0, v1.5.9, v1.5.8
- https://zhouxiaoka.github.io/autoclip_intro/en/ — project homepage ("v1.6.0 · Open source, MIT · Free")
- https://github.com/quriosity-agent/articles/blob/HEAD/2026-03-10/autoclip-automated-video-clipping-en.md — 6-step pipeline deep dive (step1_outline → step6_video, pysrt, ~30-min chunks, prompt-file scoring)
- https://deepwiki.com/zhouxiaoka/autoclip_mvp/2.3-ai-processing-pipeline — pipeline module map
- https://github.com/zhouxiaoka/autoclip/blob/HEAD/README-EN.md — CLI/MCP install, provider table (Ollama `localhost:11434`, LM Studio `localhost:1234`), `autoclip produce … --srt …`
- https://runany.dev/blog/autoclip/ and https://m.toris.kr/en/posts/autoclip-open-source-local-ai-video-clipping-guide — independent confirmations of MIT licence, local-first rendering, cloud-model billing
- PyPI `autoclip-mcp` 1.5.7.post1 — version actually installed and trialled (see §4)
- In-repo files read first-hand: `~/workspace/musetp6-vyr052/gta6_series.py`, `captions.py`, `viral_repurposer.py`, `short_video_assembly.py`, `forced_alignment.py`, `video_editor.py`, `montage.py`, `shorts_live_path.py`, `held_render_qa.py` (function inventory)

— Muse TP6
