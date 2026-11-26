# TASK-VYR-068 — Per-Tool Evaluation: ViralCutter

- **Task:** TASK-VYR-068 — evaluate AutoClip / OpenShorts / ViralCutter clipping tooling for VyralX's own-content highlight pipeline
- **Tool evaluated:** ViralCutter (word-by-word captions, Colab)
- **Evaluator:** Muse TP6
- **Date:** 2026-11-25
- **Filed:** evidence for TASK-VYR-068, work PR on branch `musetp6/task-vyr-068-clipping-tooling` (2026-11-25).
- **Repo context:** surendra2304/FRIDAY-Universe, main `be3f303ec28e3b5c9ba75e4fc23ca6b96126f557`, branch `musetp6/task-vyr-068-clipping-tooling`, hub issue #1483
- **Verdict: REJECT — do not adopt, do not vendor.** The one genuine gap it fills (per-word timed caption highlight) is small and is better closed natively from VyralX's existing word-timing sources, with no new dependency, no GPU, and no GPL-3.0 copyleft.

> Established first-hand before this evaluation (not redone): ViralCutter has **zero hits** in the FRIDAY-Universe repo — it is not referenced anywhere in the codebase today. The classification source file cited in the board evidence does **not** exist anywhere on main (full recursive tree checked, 8,546 entries, no CLASSIFICATION file). Recorded as found; not chased further.

## 1. What it is

**Canonical home:** https://github.com/RafaelGodoyEbert/ViralCutter
**Form:** a Python desktop/CLI + Gradio WebUI application, plus a Google Colab notebook. It is **not** Colab-only: local install is the primary path (Windows-first `.bat` installers), and the Colab notebook is a secondary entry point that clones the repo and launches the same WebUI.

**Version / commit observed (2026-11-25):**

| Field | Observed value |
|---|---|
| README version string | `0.8v Alpha` (both README.md and README_en.md) |
| HEAD commit | `dbe3215b1eabe85f03e6a2d0a950e30c121e9d4f` |
| HEAD commit date | 2026-09-10 02:16:19 -0300 (merge of PR #20 from `dev`) |
| Commits / stars / forks / watchers | 70 / 522 / 118 / 14 |
| Created | 2024-09-24 |
| Default branch | `main`; releases: 0; tags: 0 |
| Repo layout (root) | `main_improved.py` (CLI), `webui/app.py` (Gradio), `subtitle_studio.py` (118 KB), `scripts/` (24 modules), `ViralCutter.ipynb`, `requirements.txt`, `install_dependencies.bat`, `install_dependencies_advanced_LocalLLM.bat`, `api_config.json`, `prompt.txt`, `changelog.md`, `i18n/`, `models/` |

**Disambiguation:** a similarly named repo, `Cklaus1/ViralCut` ("ViralCutter: Viral Video Generator", `0.6v Alpha`, README TODO still lists "Release code"), is a different, smaller project. The canonical ViralCutter for this task is `RafaelGodoyEbert/ViralCutter`. The Colab badge in its README points at the notebook in this repo.

**What it does, concretely (pipeline, from `main_improved.py` + `scripts/`):**

1. **Input** — a YouTube URL (default path; `--url`), downloaded with `yt-dlp` (`scripts/download_video.py`, quality selector best/1080p/720p/480p, `--cookies-file` supported, optional YouTube-subtitle download for alignment). Local files are possible via `--project-path` (Workflow 3, subtitles-only) but the main flow is URL-first.
2. **Transcription + word alignment** — `scripts/transcribe_video.py` runs **WhisperX** (default model `large-v3-turbo`) for transcription and word-level alignment; it also parses existing SRT/VTT subtitle files as an alignment shortcut. Note: it monkeypatches `torch.load` to force `weights_only=False` (see §5, security flag).
3. **Viral segment selection** — `scripts/create_viral_segments.py` sends the transcript to an LLM backend chosen by `--ai-backend`: `gemini` (Google Gemini, key in `api_config.json`), `g4f` (unofficial free-GPT wrapper), `local` (llama.cpp GGUF models from `models/`), or `manual` (operator pastes segments; an early issue thread confirms the manual path expects the operator to paste a ChatGPT-produced JSON). Output is a segments JSON with start/end times.
4. **Cutting + vertical reframe** — `scripts/cut_segments.py`, `edit_video.py`, `one_face.py`, `two_face.py`: FFmpeg cuts, then 9:16 auto-crop driven by face tracking — InsightFace (default `--face-model insightface`) or MediaPipe, with 1-face / 2-face split-screen modes, face-confidence and dead-zone tuning, and an experimental active-speaker mode (mouth-aspect-ratio). No-face fallback is `padding` (black bars) or `zoom` (centre crop).
5. **Word-by-word captions** — `scripts/adjust_subtitles.py` (`generate_ass_from_file`) builds a styled `.ass` file from the WhisperX word-level JSON: modes `highlight` / `word_by_word` / `no_highlight`, `words_per_block` (default 3), `gap_limit` 0.5 s, Montserrat font, configurable base/highlight size and colour, optional punctuation removal. This is the "Hormozi-style" word-by-word highlight. `scripts/burn_subtitles.py` then burns the ASS into the clip with FFmpeg (`subtitles` filter), trying `h264_nvenc` first and falling back to `libx264 ultrafast` at 5 Mbit/s.
6. **Extras** — caption translation to 10+ languages (`scripts/translate_json.py`, `deep-translator`, word-by-word highlight preserved), Premiere Pro XML export (beta, `scripts/export_xml_lib/`), a Gradio WebUI (`webui/app.py`, project gallery, subtitle editor), and `subtitle_studio.py` (a large standalone subtitle tool).
7. **Colab form** — `ViralCutter.ipynb` (10,275 bytes, metadata: GPU accelerator, T4): cell 1 clones `-b dev`, installs `uv`, `libcudnn8 ffmpeg xvfb`, creates a venv, installs WhisperX from git + `requirements.txt`, then pins `transformers==4.46.3`, `torch==2.3.1+cu121`, `numpy<2.0`, `insightface`, `onnxruntime-gpu`, `mediapipe`; cell 2 starts Xvfb and runs `webui/app.py --colab`, which prints a Gradio public (`*.gradio.live`) share link. The notebook footer still says `0.1v Alpha` (stale vs the README's `0.8v Alpha`).

## 2. License and cost

- **License: GNU General Public License v3.0 (GPL-3.0).** Verified first-hand: `LICENSE` in the repo is the full GPLv3 text, and the repo metadata lists GPL-3.0.
- **Cost of the tool itself: $0, no paid tier, no watermark, no minute limits.** It passes the team's FREE ONLY rule on price.
- **But GPL-3.0 is copyleft, and that constrains *how* it can be used:**
  - Running it as a standalone, unmodified tool is fine.
  - **Vendoring or copying any of its code into VyralX (including the caption-generation logic) would make the resulting work a GPL-3.0 derivative** — the whole derivative must be licensed GPL-3.0, with source offered to recipients. VyralX lives in a private repo; that is a real legal/licensing cost even though the money cost is zero.
  - The evaluation's "adapt" option is therefore not free: adapting means either accepting GPL-3.0 on the adapted code or re-implementing the idea from scratch (clean-room), which is what §4 recommends instead.
- **Optional paid/usage-limited pieces around it:**
  - **Gemini**: free tier if a key is supplied; the README calls Gemini "(Free)". **GPT-4** is offered as a backend — paid at OpenAI rates if selected.
  - **g4f**: unofficial, free wrapper around third-party chat endpoints — no money cost, but availability and terms-of-service risk, and it is not a supported API.
  - **Local GGUF**: free/offline, but needs a capable GPU and a model download.
  - **Google Colab free tier**: the notebook's T4 GPU is *not* unlimited — free Colab has session time limits, idle timeouts, and usage quotas; the Gradio share link the notebook prints expires in 1 week. "Free and unlimited" in the README means "no per-clip charge on your own hardware", not unlimited Colab.
  - **Model downloads**: WhisperX (`large-v3-turbo`) and the WhisperX alignment models are downloaded from Hugging Face on first run (network + disk, no money cost).

## 3. Runtime and dependencies

From `requirements.txt` (verbatim, 15 lines, mostly unpinned):

```
numpy<2.1.0, g4f[all], yt-dlp, ffmpeg-python, whisperx, mediapipe,
google-genai, google-generativeai, insightface, gradio, opencv-python,
psutil, fastapi, uvicorn, deep-translator, tqdm
```

Plus the Colab notebook's pinned extras: `torch==2.3.1+cu121`, `torchvision==0.18.1+cu121`, `torchaudio==2.3.1+cu121`, `transformers==4.46.3` ("CRITICAL" pin — newer versions "break the alignment"), `accelerate`, `onnxruntime-gpu`, `pandas`, `pytubefix`, `numpy<2.0`, `setuptools==69.5.1`, `protobuf>=3.20,<5.0`.

- **Language:** Python, 3.10.x or 3.11.x recommended (README). Windows-first: Visual Studio C++ Build Tools (to compile InsightFace), `uv` package manager, `.bat` installers.
- **GPU:** NVIDIA GPU "highly recommended", CUDA 12.4+ drivers; WhisperX transcription is GPU-accelerated and CPU transcription is documented as slow (an issue reporter notes their PC "uses the CPU, not the GPU, to transcribe"). The Colab notebook requests a T4.
- **External services:** YouTube (yt-dlp download — the fleet download path is broken and off-limits for this task); Gemini or GPT-4 API if the cloud LLM backends are chosen; Hugging Face for WhisperX/alignment model weights; Gradio share-link relay when run with `--colab`.
- **Fleet fit: poor.** VyralX's own modules document the constraints ViralCutter violates: the fleet runs Python 3.10 and the short-video assembly port was written pure-stdlib precisely because the fleet VMs are ~956 MB with a ~180 MB resident-service cap (`short_video_assembly.py` docstring). ViralCutter needs a CUDA GPU, a multi-GB torch + WhisperX + InsightFace stack, Xvfb, and pinned torch/transformers versions that are already fragile (the notebook's own comments describe version breakage). It is a desktop/GPU-workstation tool, not a fleet-service component.
- **Security flags found while reading (not executed):**
  - `scripts/transcribe_video.py` monkeypatches `torch.load` to force `weights_only=False` (`apply_safe_globals_hack`). That disables PyTorch's pickle-execution protection for model loading — a known unsafe pattern.
  - The CLI accepts `--cookies-file` (Netscape cookies for YouTube) and the Colab notebook runs `sudo apt install` and clones the `dev` branch, not `main`.

## 4. Fit to VyralX's pipeline

### Stage map

| VyralX stage (file) | ViralCutter equivalent | Relationship |
|---|---|---|
| Moment-finding — `gta6_series.py` (`find_moments`: ffmpeg ebur128 spikes + scene cuts + faster-whisper timed words via `shorts_generator`, deterministic scoring) | LLM viral-segment selection (`create_viral_segments.py`, Gemini/GPT-4/g4f/local GGUF) | **Duplicates, different philosophy.** VyralX deliberately replaced LLM highlight-ranking with deterministic scoring (`shorts_live_path.py` docstring: "The upstream LLM highlight-ranking step stays replaced by VyralX's deterministic scoring"). Adopting ViralCutter would reintroduce an LLM ranking step the team already removed, plus a `g4f` unofficial-API dependency. |
| Scene-change detection — `video_editor.py` | Scene handling inside the cut/face pipeline | Partial overlap; VyralX already has it, dependency-free (ffmpeg `select` filter). |
| Vertical cut — `gta6_series.py` `plan_episode_cut` → `shorts_generator.vertical_crop_plan` (takes `face_center_x`) | Face-tracked 9:16 auto-crop, 1-face / 2-face split screen, active speaker | **Partial gap, narrow.** VyralX's crop plan accepts a face centre but nothing in-repo *detects* a face. ViralCutter's face tracking would fill that — but at the price of InsightFace/MediaPipe + GPU, which the fleet cannot carry. A lightweight face-centre source (or operator-supplied centre) fits the existing plan without this stack. |
| Word-level timing — `forced_alignment.py` (HTTP-backed word alignment, validated against the exact transcript) + `short_video_assembly.py` (subtitles from Edge word boundaries or a local Whisper pass) + faster-whisper timed words via `shorts_generator` | WhisperX transcription + alignment producing word-level JSON | **Duplicates.** VyralX already has *three* word-timing sources. WhisperX would be a fourth, heavier one, not a new capability. |
| Caption rendering — `captions.py` (`write_srt`, `write_ass`: 6 ASS styles, keyword highlight, uppercase, strict overlap/order validation) | `adjust_subtitles.py` (ASS from word JSON, highlight/word-by-word modes) + `burn_subtitles.py` (ffmpeg burn, NVENC → libx264) | **Overlaps heavily; one narrow gap.** See below. |
| Render — `montage.py` (FFmpeg multi-scene renderer, subtitle burn-in via `renderer._subtitle_filter`) | FFmpeg cut + burn | Duplicates. |
| QA gates — `held_render_qa.py`, `gta6_series.py` `gate_series_episode` (caption-track count, BGM, watermark, loudness, blank) | None — no QA gates | **No coverage.** ViralCutter has no machine-QA concept; its output would still have to pass VyralX's held-render gates unchanged. |
| Assembly plan — `short_video_assembly.py` (plan-only, no render/download/upload) | End-to-end download → cut → burn → (roadmap: direct upload to TikTok/YouTube/Instagram) | **Philosophy mismatch.** VyralX plans first and holds renders for review (loop OFF, unlisted, review-first). ViralCutter is built to download a YouTube video and produce finished clips, with direct upload on its roadmap. Its download-first input also conflicts with VYR-068's own-content scope and the broken/off-limits fleet download path. (Fairness note: Workflow 3 with `--project-path` can run subtitles-only on local files, so it is not *exclusively* download-bound — but the main flow is URL-first.) |

### Overlap with `captions.py` and `forced_alignment.py` — the crux

- `captions.py` already does styled ASS output (6 styles: ViralWhite, CapCutViral, CyberNeon, CleanWhite, ViralYellow, BoldRed; Arial Black 76–78 pt; keyword highlight colour per style) with strict validation. What it does **not** do is **per-word timed highlighting**: its cues are segment/phrase-level, and its keyword highlight colours whole words for the whole cue duration. It has no karaoke-style per-word timing.
- `forced_alignment.py` already returns validated **word-level timestamps** (it requires the word count to match the transcript exactly and validates every word's bounds), then groups words into phrase cues. The word timings exist in VyralX — they are just collapsed into phrase cues before `captions.py` sees them.
- **The genuine gap is therefore exactly one small feature: a word-by-word (karaoke) ASS mode in `captions.py` driven by the word timestamps `forced_alignment.py` already produces.** That is a small native addition (per-word `\kf`-style karaoke tags or per-word timed dialogue lines in the existing ASS writer, reusing its validation and styles) — no new dependency, no GPU, no download, no GPL code. ViralCutter's `adjust_subtitles.py` shows the shape of the feature (~260 lines), but copying it would import GPL-3.0 code; re-implementing the *idea* natively is the clean path if the team ever wants it.
- Everything else ViralCutter offers for this pipeline is either already present (transcription/alignment, scene detection, vertical crop plan, ASS/SRT writing, FFmpeg burn) or actively unwanted (YouTube download-first input, LLM viral ranking, direct-upload roadmap, Gradio WebUI in a service codebase).

### What gap, if any, does it fill?

1. **Per-word timed caption highlight** — real, narrow, closable natively (see above).
2. **Face detection for the vertical-crop centre** — real but small, and not worth a GPU + InsightFace/MediaPipe stack on the fleet; the existing `vertical_crop_plan(face_center_x=…)` already accepts the value from any lighter source.
3. **Caption translation** — not needed by the own-content highlight pipeline (her English narration; subtitles always on in English).
4. **Premiere XML export** — not needed; VyralX renders in-pipeline.

## 5. Trial result — no local trial run (concrete reasons)

**Attempted, bounded:** ffmpeg toolchain verified and a test clip generated on this VM.

- `/usr/bin/ffmpeg` v8.1.2 works. Generated `/tmp/viralcutter-trial/test_clip.mp4`: 5.0 s, 1280×720, h264 + AAC 440 Hz tone (`testsrc` + `sine`, no YouTube download used, per task constraints). The clip exists for any future trial.
- Environment check on this VM: Python 3.12.3 (ViralCutter wants 3.10/3.11); `torch` **not installed**; `whisperx` **not installed**; **no GPU** (`nvidia-smi` absent); 4 CPUs, ~8 GB RAM with only ~687 MB available at check time.

**ViralCutter's core path was not executed, for three concrete, independent reasons:**

1. **Execution-risk check.** The cloned tree failed an execution-risk check in this session: running, importing, installing, building, or testing its content was barred. I read its files as plain text only and installed nothing from it.
2. **The stack cannot be installed in a bounded way here.** Its core path needs WhisperX + torch 2.3.1+cu121 + transformers 4.46.3 + InsightFace + onnxruntime-gpu + MediaPipe — a multi-GB, CUDA-bound install on a CPU-only VM with ~687 MB free RAM and Python 3.12 (outside its supported 3.10/3.11 range). That is not a lightweight venv install; attempting it would be the opposite of the bounded trial requested.
3. **Its Colab path is not available to this agent.** The notebook needs an interactive Google Colab GPU (T4) session and a browser; this subagent has no live-browser/Colab access. A Colab trial would also still be download-first (it clones `-b dev` and launches the WebUI) and would not prove fleet fit.

**What the trial therefore establishes:** the *inputs* (ffmpeg 8.1.2, a generated clip) are ready, but ViralCutter itself was evaluated from its repo, notebook, and source text — which is sufficient, because the verdict turns on architecture/license/fleet-fit, not on a render: even a successful local render would not change the duplication, GPL-3.0, GPU, or download-first findings. If the team ever wants a render proof, the correct venue is a GPU workstation or a Colab T4 session running `ViralCutter.ipynb` (or `python main_improved.py --project-path … --workflow 3` on a local file), not the fleet and not this VM.

**Trial log (verbatim commands run):**

```
$ /usr/bin/ffmpeg -hide_banner -y -f lavfi -i testsrc=duration=5:size=1280x720:rate=30 \
    -f lavfi -i sine=frequency=440:duration=5 -shortest -c:v libx264 -pix_fmt yuv420p \
    -c:a aac /tmp/viralcutter-trial/test_clip.mp4
→ ffmpeg version 8.1.2; encode completed (libx264 kb/s:115.06)
$ ffprobe test_clip.mp4 → codec h264 video + aac audio, duration=5.000000
$ python3 --version → Python 3.12.3
$ python3 -c "import torch" → ModuleNotFoundError (traceback)
$ python3 -c "import whisperx" → ModuleNotFoundError (traceback)
$ which nvidia-smi → no nvidia-smi
$ nproc → 4; free -m → total 7934, available 687
```

No YouTube video was downloaded. Nothing was installed system-wide or in a venv. No GitHub writes, no commits, no fleet changes (bridge not used at all — no `run_shell`, no server reads needed for this evaluation).

## 6. Recommendation — REJECT (adopt / adapt / reject)

**REJECT adoption of ViralCutter as a tool, and REJECT vendoring/adapting its code.**

Concrete reasons, in order:

1. **It duplicates the pipeline.** WhisperX transcription/alignment, scene handling, vertical crop, ASS/SRT writing, and FFmpeg burn all already exist in VyralX (`forced_alignment.py`, `video_editor.py`, `gta6_series.py` + `shorts_generator`, `captions.py`, `montage.py`). Adopting it would add a second implementation of five stages.
2. **It reintroduces what the team deliberately removed.** Its viral-moment selection is LLM-based (Gemini/GPT-4/`g4f`/local GGUF); VyralX replaced LLM highlight-ranking with deterministic scoring. The `g4f` backend is an unofficial free-GPT wrapper — an availability and ToS risk the FREE ONLY rule does not bless just because it costs $0.
3. **GPL-3.0 copyleft blocks the "adapt" path.** Copying its caption logic into VyralX would GPL-license the derivative. The tool is free-as-in-price but not free-as-in-no-strings for this codebase.
4. **It cannot run where VyralX runs.** CUDA GPU + torch 2.3.1 + pinned transformers 4.46.3 + InsightFace/MediaPipe + Xvfb, on Python 3.10/3.11, vs fleet VMs (~956 MB, ~180 MB resident cap, Python 3.10, CPU-only here) and a CPU-only eval VM. It is a desktop/GPU-workstation tool.
5. **Its input model is wrong for this task.** Download-first from YouTube URLs, while VYR-068 is own-content-only and the fleet download path is broken and off-limits; its roadmap even adds direct upload to TikTok/YouTube/Instagram, which contradicts loop-OFF / review-first / held-render.
6. **Its one real gap is closable natively and cheaply.** Per-word timed caption highlight can be added to `captions.py` as a karaoke mode fed by the word timestamps `forced_alignment.py` already returns — no new dependency, no GPU, no GPL code, no download. If the team wants that feature, that is the follow-up to file, not a ViralCutter adoption.

**Suggested follow-up (for the coordinator, not taken here):** a small native task — "word-by-word karaoke ASS mode in `captions.py`, driven by `forced_alignment.py` word timestamps, reusing existing ASS styles and validation" — plus, if face-centred cropping is ever wanted, a lightweight face-centre source feeding the existing `vertical_crop_plan(face_center_x=…)` parameter. Neither needs ViralCutter.

## Sources

- https://github.com/RafaelGodoyEbert/ViralCutter (repo root; HEAD `dbe3215b1eabe85f03e6a2d0a950e30c121e9d4f`, 2026-09-10; 522 stars, 118 forks, GPL-3.0)
- https://github.com/RafaelGodoyEbert/ViralCutter/blob/main/LICENSE (full GPLv3 text, read first-hand)
- https://github.com/RafaelGodoyEbert/ViralCutter/blob/main/README_en.md (version `0.8v Alpha`, feature/installation claims)
- `ViralCutter.ipynb` in-repo (Colab install V7: `uv` venv, WhisperX from git, torch 2.3.1+cu121, transformers 4.46.3, Xvfb, `webui/app.py --colab`, T4 metadata)
- `requirements.txt`, `main_improved.py`, `scripts/transcribe_video.py`, `scripts/create_viral_segments.py`, `scripts/adjust_subtitles.py`, `scripts/burn_subtitles.py`, `scripts/download_video.py`, `api_config.json` (empty Gemini key — no secrets), `changelog.md` — read as plain text from a shallow clone at `/tmp/viralcutter-eval` (read-only; code not executed, per the execution-risk check)
- VyralX pipeline files read first-hand: `captions.py`, `forced_alignment.py`, `gta6_series.py`, `short_video_assembly.py`, `shorts_live_path.py`, `montage.py`, `viral_repurposer.py` (all under `~/workspace/musetp6-vyr052/`)

— Muse TP6
