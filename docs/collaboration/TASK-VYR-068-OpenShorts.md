# TASK-VYR-068 — Per-tool evaluation: OpenShorts

**Tool:** OpenShorts — open-source AI clip generator (9:16 recut, face tracking, auto subtitles, dubbing)
**Task:** TASK-VYR-068 (VyralX: evaluate AutoClip / OpenShorts / ViralCutter clipping tooling for the own-content highlight pipeline)
**Evaluator:** Muse TP6 — 2026-11-25
- **Filed:** evidence for TASK-VYR-068, work PR on branch `musetp6/task-vyr-068-clipping-tooling` (2026-11-25).
**Repo under evaluation:** `mutonby/openshorts`, commit `29ccbf372d6b3a99586ba7de2bf49d426bc2c69b` (main, observed 2026-11-25)
**VyralX context:** repo `surendra2304/FRIDAY-Universe`, main `be3f303ec28e3b5c9ba75e4fc23ca6b96126f557`, branch `musetp6/task-vyr-068-clipping-tooling`, hub issue #1483
**Verdict: ADAPT — do not adopt the platform; port its two proven reframing ideas into VyralX's existing ffmpeg-only render path.**

— Muse TP6

---

## 1. What it is

OpenShorts is an open-source, self-hosted AI clip generator: feed it a long video (YouTube URL via yt-dlp, or a local upload) and it returns finished 9:16 vertical clips for TikTok / Reels / YouTube Shorts — reframed, captioned, with a hook line, a virality score and per-platform titles. It calls itself "the open-source OpusClip alternative". Homepage: https://www.openshorts.app/ — self-hosting guide: https://www.openshorts.app/self-hosted-ai-clip-maker

Canonical repo (the one the homepage's own clone instructions point to):

- **URL:** https://github.com/mutonby/openshorts
- **Observed state 2026-11-25:** default branch `main`, current commit `29ccbf372d6b3a99586ba7de2bf49d426bc2c69b`, 749 commits, 9,867 stars, 2,061 forks, **0 releases, 0 tags** (no version number exists — pin by commit), created 2025-12-19. GitHub flags the repo itself as a fork (parent not named on the fetched repo page); the similarly-named `tayonike/openshorts.-ugc` and `faris-sait/openshorts` repos are forks/copies of it. All evidence below is from the `mutonby/openshorts` tree at the commit above, cloned shallow and read first-hand, plus the repo README and the openshorts.app self-hosting page as crawled 2026-11-25.

### What it does, concretely

Clip Generator pipeline (README "Technical Pipeline", verified against the source files):

1. **Ingest** — YouTube URL (yt-dlp) or local upload.
2. **Transcribe** — faster-whisper (or Parakeet on GPU) with **word-level timestamps** (`subtitles.py`, `transcribe_backends.py`; default model `small`, `large-v3-turbo` on GPU).
3. **Detect scenes** — TransNetV2 neural shot-boundary detector by default (48×27 frames, torch), falling back to PySceneDetect `ContentDetector` (`scene_detection.py`; `SCENE_ENGINE` env switch).
4. **Analyse / moment-pick** — Google Gemini 3.1 Flash-Lite receives the timestamped transcript + scene boundaries and returns **3–15 moments of 15–60 s, each with a virality score** (`clip_selection.py`, `gemini_worker.py`). A local LLM via `LLM_BASE_URL` (Ollama / LM Studio / vLLM, OpenAI-compatible, 7–8B+ recommended, 16k context) can replace Gemini for this step.
5. **Extract** — FFmpeg precise clip cutting.
6. **Reframe to 9:16** — per scene, one of four layouts, picked per video by Gemini or forced from the dashboard (`reframe_v2.py`, 936 lines):
   - **TRACK** — MediaPipe BlazeFace face tracking with a smoothed cameraman trajectory (per-frame crop-x, `sendcmd` dynamic crop in ffmpeg), YOLOv8 person-box fallback when no face is found;
   - **GENERAL** — blurred-background bed (foreground scaled over a blurred, centre-cropped copy of itself);
   - **SPLIT** — two speakers stacked vertically, captions on the seam;
   - **SCREENCAST** — screen above the presenter / webcam inset.
   Output is 1080×1920 (delivery floor `DELIVERY_MIN_WIDTH = 1080`; a 720p source's 406×720 crop is upscaled to it, never shipped sub-HD).
7. **Effects** — word-level subtitles burned in with FFmpeg (SRT or karaoke ASS), AI hook text overlay, Gemini-generated FFmpeg filter effects.
8. **Dubbing (optional)** — ElevenLabs, 30+ languages with voice cloning; the dubbed track is re-transcribed so subtitles match the new language.
9. **Publish (optional)** — S3 backup + Upload-Post social distribution to TikTok / Instagram / YouTube / Facebook / LinkedIn / Threads / Bluesky; Autopilot (Cloud, paid) clips every new channel video automatically.

Around the clipper it also ships: a clip editor with word-level cuts and fast re-renders (`recut.py`: FAST path re-cuts the already-reframed canonical file, SOURCE path re-reframes from source), AI Shorts / UGC video creator (AI actors via fal.ai Flux/Hailuo/Kling — pay-per-use, ~$0.50–2.00/video), YouTube Studio (AI titles, thumbnails, one-click publishing), and a built-in MCP server + REST API + CLI (`pip install openshorts`) for agents.

### Inputs / outputs

- **In:** long-form video file or YouTube URL; topics: podcasts, webinars, livestreams, vlogs, interviews — i.e. **speech-led, face-on-camera material**.
- **Out:** 3–15 vertical clips (15–60 s), 1080×1920, burned-in word-level captions, hook overlay, virality score, titles. A video with no speech cannot be clipped without a Gemini key (README: silent videos are sent to Gemini to be clipped by what's on screen; without a key they fail with a message saying so).

---

## 2. License and cost — passes FREE ONLY for the core, with paid edges that must stay off

- **Core application: MIT License** — verified first-hand from the cloned tree (`LICENSE`, "Copyright (c) 2024 OpenShorts", standard MIT text). GitHub repo metadata also reports "MIT License (MIT)". Commercial use, modification and redistribution allowed.
- **Exception (README "License" section):** the `cloud/` directory (billing, managed keys, hosted-service infrastructure behind the `BILLING_ENABLED` flag) is source-available under a separate **OpenShorts Commercial License** — readable/modifiable/self-hostable for personal or internal use, but **not** offerable to third parties as a paid/hosted service. Self-hosting the core never requires that directory. VyralX would not touch it.
- **Self-hosted cost: $0 in software** — free forever, no watermark, no cap, no per-minute meter (README + self-hosting page). What you pay is the machine, electricity, your time, and API usage:
  - Google Gemini: free tier for individual use; under $0.01 per 10-min video beyond it. Replaceable with a local LLM ($0).
  - ElevenLabs dubbing/voiceover: pay-per-use, free tier available — **paid path; closed under VyralX FREE ONLY**.
  - fal.ai (AI Shorts actors/lip-sync): pay-per-use, ~$0.50–1.50 per AI Short — **paid path; out of scope**.
  - Upload-Post auto-publishing: 10 free uploads/month, then pay-per-use — **paid path; also forbidden on safety grounds (see §4)**.
  - AWS S3 backup: optional, ~$0.023/GB.
- **Hosted Cloud: paid from $12/mo** (100 min), free plan = first video up to 60 min then 20 min/mo, watermarked. **Not usable under FREE ONLY**, and it would send footage to a third party.
- **Verdict on license/cost:** the clipping core **passes** the team's FREE ONLY rule (MIT, $0 self-hosted). The dubbing, AI-Shorts and auto-publishing features are paid and must stay disabled; they are optional and the core does not need them.

---

## 3. Runtime and dependencies

From `requirements.txt`, `requirements-cpu.lock`, `Dockerfile` and the README "Tech Stack", all read first-hand at the observed commit:

- **Language/runtime:** Python 3.11 (Docker image `python:3.11-slim`, pinned by digest), FastAPI backend + React 18 / Vite frontend. **VyralX fleet runs Python 3.10** — the upstream stack does not run on the fleet interpreter as-is.
- **Install method:** Docker + Docker Compose only (`docker compose up --build`; dashboard on `http://localhost:5175`, API on `:8000`). No supported bare-metal install path.
- **Hardware:** **8 GB+ RAM and a modern multi-core CPU**; first start downloads the transcription and detection models. CPU: ~5–8 min to clip an 8-min video. Optional NVIDIA GPU (NVENC, 8 GB VRAM) cuts that to ~1 min; GPU image is ~2 GB larger.
- **Heavy dependencies (exact pins):** `torch==2.11.0`, `torchvision==0.26.0`, `ultralytics==8.4.46` (YOLOv8), `mediapipe==0.10.14` (BlazeFace), `opencv-python==5.0.0.93`, `faster-whisper==1.2.1` (CTranslate2), `scenedetect==0.7`, `transnetv2-pytorch==1.0.5`, `google-genai==1.75.0`, `yt-dlp`, FFmpeg, `onnxruntime` / `onnx-asr` (Parakeet). Full CPU lock is ~100 pinned packages.
- **External services:** Gemini (moment picking, layout picker, silent-video clipping) unless a local LLM is pointed at; ElevenLabs only for dubbing; fal.ai only for AI Shorts; Upload-Post only for publishing. With a local LLM and no Gemini key, nothing leaves the machine (transcription, scene detection, face tracking, reframing and encoding all run locally); with Gemini, the moment picker sends transcript text (never video) and the layout picker sends a handful of still frames.
- **Fleet fit:** this stack is **orders of magnitude above the fleet envelope**. VyralX's own ports are pure-stdlib plan builders precisely because the resident service is capped at ~180 MB on ~956 MB VMs (see `short_video_assembly.py` docstring). OpenShorts needs Docker, 8 GB RAM, a multi-GB torch/mediapipe/whisper model set and Python 3.11. It cannot run on the fleet, and there is no Docker on this VM either. It could only ever run **off-fleet** (owner machine / post-ARM batch), the same execution slot VyralX already reserves for rendering.

---

## 4. Fit to VyralX's pipeline

### Stage-by-stage mapping

| OpenShorts stage | VyralX equivalent (file read first-hand) | Relationship |
|---|---|---|
| Transcribe, word-level timestamps (faster-whisper) | `forced_alignment.py` (word-level alignment, optional HTTP-backed) + `shorts_live_path.clip_subtitles` (timed words → ≤4-word SRT cues) + Edge TTS word boundaries (`short_video_assembly.py`) | **Duplicates.** VyralX already has word-level timing; it does not have a local Whisper pass, but that is a small gap, not a reason to adopt a platform. |
| Scene detection (TransNetV2 / PySceneDetect) | `video_editor.py` (scene-change detection) + `gta6_series.detect_scene_cuts` (ffmpeg `select='gt(scene,…)'`, no new dependency by design) | **Duplicates, more cheaply.** VyralX deliberately uses ffmpeg's own detector to avoid adding a library; TransNetV2 is more accurate on fades/flashes, but costs torch. |
| Moment-finding (Gemini scores transcript + scenes, 3–15 clips, virality score) | `gta6_series.find_moments` (audio-spike via ffmpeg ebur128 + scene cuts + transcript windows via `shorts_generator.candidate_windows`, deterministic scoring) | **Duplicates, and conflicts in method.** VyralX's scoring is deterministic and key-free by design; OpenShorts' is an LLM call (Gemini free tier or a local 7–8B model). Also note the duration mismatch is nil (OpenShorts 15–60 s vs VyralX moments 8–59 s) but the **material mismatch is real**: OpenShorts is built for speech-led podcasts/interviews; VyralX's GTA-6 series is gameplay with *no speech*, which OpenShorts can only clip by sending frames to Gemini — the one path that leaks footage to a third party and fails entirely without a key. |
| 9:16 reframe, TRACK mode (per-frame face-tracked crop, smoothed) | `shorts_generator.vertical_crop_plan` via `gta6_series.plan_episode_cut` + `shorts_live_path` `fit_mode="crop"` (crop filter from the clip's own plan, `face_tracked` flag) | **Partially duplicates — and this is the one genuine gap.** VyralX's crop is a *static* window (one `face_center_x` for the whole clip). OpenShorts computes a *per-frame* crop-x trajectory with a smoothed cameraman + speaker tracker, so the frame follows the speaker instead of sitting on a fixed centre. That is a real quality difference for talking-head material, and it is the single most portable idea in the tool. |
| 9:16 reframe, GENERAL mode (blurred background) | `montage.py` `fit_mode="blur_pad"` / `"smart_vertical"` (blurred bed + centred foreground) | **Duplicates.** VyralX already has the blurred-background layout. |
| 9:16 reframe, SPLIT (two speakers stacked) + SCREENCAST (screen over presenter) | Nothing in the files reviewed | **Gap, narrow.** No VyralX file implements stacked-speaker or screencast layouts. Relevant only to two-person / screen-share material, which is not the GTA-6 own-content series (single gameplay feed). Low priority. |
| Subtitles, burned-in, word-level, styled + hook overlays | `captions.py` (`write_srt` / `write_ass`, 6 ASS styles, keyword highlight, word-level cues) + `shorts_live_path` (dedupe, burn via renderer) | **Duplicates.** VyralX's ASS styles + keyword highlight already match this, including the same 1080×1920 play resolution. |
| Dubbing (ElevenLabs, 30+ languages, voice cloning) | `short_video_assembly.py` voiceover = Edge TTS only, free, no key; GTA-6 series model = *her* English narration over ducked source voice | **Not a fit.** Dubbing is a paid ElevenLabs path (closed by FREE ONLY) and answers a question VyralX does not ask — the series uses her own narration, not a translated/cloned voice. |
| Clip editor / recut (word-level EDL, fast re-render) | No editor in VyralX; plans are built then rendered once | **Gap, minor.** A recut/EDL step would help human review, but VyralX's review-first flow re-plans rather than re-edits; not needed for this pipeline. |
| Auto-publishing / Autopilot / YouTube Studio one-click publish | Nothing — deliberately: loop OFF, uploader paused, unlisted + review-first, renders held for the owner | **Direct conflict. Must never be enabled.** Autopilot publishes a clip a day on its own; that violates the owner stop order (2026-11-24 ~16:42 IST), the loop-OFF rule and review-first. Any adoption must exclude the publishing half entirely. |
| Ingest via yt-dlp (YouTube URL in) | `viral_repurposer.py` / `ytdlp_support` — the fleet download path is broken and off-limits for this task | **Unusable here.** OpenShorts' YouTube ingest is exactly the path that is broken/off-limits; only local-upload ingest would ever apply, and VyralX's footage rule admits only own capture / campaign footage anyway. |
| Machine QA | `held_render_qa.py` + `gta6_series.gate_series_episode`: caption-track count, BGM presence (mandatory), watermark verified, loudness −24…−10 LUFS, true peak ≤ −1.0 dBFS, blank-gate — all fail-closed | **OpenShorts has none of this.** No BGM handling at all (VyralX mandates BGM, ducked), no watermark/provenance step, no loudness gate, and its captions are *burned in* — VyralX's caption-track gate counts caption tracks/ASS sidecars, so an OpenShorts render would need its sidecar SRT/ASS preserved and fed to the gate, not just the burned-in picture. An OpenShorts clip would fail VyralX machine QA as produced. |

### What it duplicates (summary)

Moment-finding, scene detection, static vertical crop, blurred-background layout, word-level subtitles with styled burn-in, and the assembly/montage render path. VyralX already owns all of these in small, dependency-free, deterministic form.

### What gap (if any) it fills

One real gap and one narrow one:

1. **Per-frame face-tracked crop trajectory (TRACK mode)** — VyralX's vertical crop is a single fixed window per clip; OpenShorts tracks the speaker frame-by-frame with smoothing (`SmoothedCameraman`/`SpeakerTracker` state machines in `reframe_v2.py`/`main.py`, MediaPipe BlazeFace primary, YOLOv8 person-box fallback). This is the only capability that would visibly improve VyralX's own-content talking-head clips and that VyralX cannot already do.
2. **SPLIT / SCREENCAST layouts** — genuinely absent from VyralX, but only relevant to two-person or screen-share material, not to the GTA-6 single-feed series. Park it.

Everything else OpenShorts offers for this pipeline is either already built, paid, publishing-shaped (forbidden), or aimed at speech-led material VyralX's gameplay series does not have.

### Notes recorded as found (per task brief, not re-chased)

- **OpenShorts has zero hits in the FRIDAY-Universe repo** — it is not referenced anywhere in the codebase today (established first-hand before this evaluation; not redone).
- **The classification source file cited in the board evidence does not exist on main.** The full recursive tree (8,546 entries) was checked before this evaluation and contains no `CLASSIFICATION` file. The only local artefact is `~/workspace/musetp6-vyr052/CLASSIFICATION-2026-11-24.md`, whose entire contents are the 14 bytes `404: Not Found` — i.e. the fetched copy is itself a 404 placeholder, not a classification record. Recorded as found; not chased further.

---

## 5. Trial result — partial success (bounded local trial, this VM)

Trial scope, per the task constraints: generated test clip only, **no YouTube download** (fleet download path broken and off-limits), no system-wide installs, no commits, no fleet access. Trial directory: `~/workspace/musetp6-vyr052/openshorts-trial/`.

### What was attempted

1. **Source checkout (read-only):** shallow sparse `git clone https://github.com/mutonby/openshorts.git` at `~/workspace/musetp6-vyr052/openshorts-src/`, HEAD `29ccbf372d6b3a99586ba7de2bf49d426bc2c69b` (matches the repo page's current commit). Two large demo media files (65 MB GIF, 5.5 MB demo MP4) were deleted after checkout to keep the checkout lean; all `.py`, `LICENSE`, `requirements*.txt`, `Dockerfile`, `README.md` retained.
2. **Test clip:** ffmpeg-generated, `testsrc2` 1280×720 @ 30 fps + 880 Hz sine tone, 6.0 s (`test_input.mp4`, 2.0 MB). Verified with ffprobe: video 1280×720, audio present, duration 6.000000 s.
3. **Detector dependencies:** created a venv in the trial dir and installed the exact upstream pins — `opencv-python-headless==5.0.0.93`, `mediapipe==0.10.14`, `numpy==2.4.6` (`pip install --no-cache-dir`, `TMPDIR` redirected into the trial dir). First attempt failed with `OSError: [Errno 28] No space left on device` because pip's default temp dir is the 512 MB tmpfs `/tmp` (65% full at the time); retry with `TMPDIR=$PWD/tmp` succeeded (exit 0). Verified: `cv2 5.1.0, mediapipe 0.10.14, numpy 2.4.6`.
4. **Real-code filtergraph check:** imported the actual `reframe_v2` module in the venv (it imports cleanly with only numpy + opencv present) and called its pure helpers:
   - `delivery_size(1280, 720, 9/16)` → `(1080, 1920)` ✓
   - `source_already_fits(1280, 720, 9/16)` → `False` ✓
   - `general_filtergraph(1080, 1920, orig_w=1280, orig_h=720)` → the exact string used for the render below (diff clean apart from the `,ass=trial.ass` I appended for caption burn-in, which OpenShorts applies as a separate step, not inside this function).
5. **GENERAL-mode 9:16 render + burned captions:** ran ffmpeg with OpenShorts' own GENERAL filtergraph (blurred bed at quarter resolution, `gblur=sigma=3`, foreground scaled to 806 px high, centred overlay, `setsar=1`) plus an ASS subtitle file generated with **VyralX's own** `captions.write_ass` (`ViralWhite`, keyword `trial` highlighted) — mirroring OpenShorts' burn-in step. Output `general_9x16.mp4`: **1080×1920, 6.000 s, video + audio, 1.7 MB, rendered in 24.4 s wall** for a 6 s clip on this 1.5-CPU VM. Frame extracted at t=1.5 s and inspected visually: blurred background bed, centred sharp foreground, burned-in caption "Hello from the **trial** clip" with the keyword highlighted — all as designed (`frame_1s5.png`, `frame_4s0.png` in the trial dir).
6. **MediaPipe face-detection smoke test:** ran upstream's exact detector config (`mp.solutions.face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)`, as in `main.py:110-111`) on a real frame of the test clip: **ran in 0.12 s, detections: None** — expected and honest, because `testsrc2` contains no human face. This proves the detector loads and executes on this VM; it does **not** prove face tracking, because no face was available to track and no real face footage may be used here.

### What could NOT be trialled, and the concrete reasons

- **Full TRACK-mode pipeline (the face-tracked recut): not runnable on this VM.** `reframe_v2._analyze_trajectory` does `import main as m`, and `main.py` imports `ultralytics` (YOLOv8) at module level and loads `yolov8n.pt` at import time (`main.py:23,106`). `ultralytics` pulls in **torch (~GBs)**; installing torch + the YOLO weights + the faster-whisper model set is heavyweight, exceeds the bounded-trial remit, and would still leave the moment-picker (Gemini key or a local 7–8B LLM) and the transcription model (faster-whisper, model download) unprovisioned. Verified: `import ultralytics` fails in the trial venv (`ModuleNotFoundError`). The TRACK trajectory code path was therefore verified **by source reading only**, not by execution.
- **Full end-to-end job (transcribe → Gemini moment-pick → reframe): not runnable.** No Docker on this VM (`docker: command not found`), no Gemini API key, no local LLM, and the documented minimum is Docker + 8 GB RAM (this VM: 1.5 shared CPUs, ~580 MB free RAM at trial time). The full `docker compose up --build` path was not attempted.
- **Dubbing:** not trialled — ElevenLabs key required, paid path, out of scope under FREE ONLY.
- **No YouTube ingest** was attempted, per the task constraint.

### Trial verdict

The **render stage is verified end-to-end with OpenShorts' own code**: real `reframe_v2` helpers → real ffmpeg filtergraph → real 1080×1920 output with burned-in styled captions, visually confirmed. The **detection stage is verified only as far as MediaPipe loading and running**; the face-tracking trajectory (the actual value-add) and the Gemini moment-picking were **not** executed here, for the concrete dependency reasons above. Any adoption decision must treat TRACK-mode quality as **unproven on VyralX footage** until it is run off-fleet with a real face on camera.

### Trial artefacts (all under `~/workspace/musetp6-vyr052/openshorts-trial/`)

- `test_input.mp4` — generated 1280×720, 6 s test clip (testsrc2 + sine tone)
- `trial.ass` — ASS subtitles from VyralX `captions.write_ass` (ViralWhite, keyword highlight)
- `general_filtergraph.txt` / `general_filtergraph_real.txt` — filtergraph used vs the string returned by real `reframe_v2.general_filtergraph()` (identical modulo the appended `ass=` burn-in)
- `general_9x16.mp4` — rendered 1080×1920 output (ffprobe-verified)
- `frame_1s5.png`, `frame_4s0.png` — extracted frames (caption burn-in visually confirmed)
- `pip_install.log`, `pip_install2.log` — install attempts (first failed: /tmp tmpfs full; second succeeded with TMPDIR redirected)
- `venv/` — trial venv (opencv/mediapipe/numpy at upstream pins; **removed after the trial to reclaim ~1.2 GB** — reinstall with the pins above to reproduce)
- `tmp/` — pip temp dir used for the successful install

### Trial log (key lines)

```
$ ffmpeg -f lavfi -i testsrc2=size=1280x720:rate=30:duration=6 -f lavfi -i sine=frequency=880:duration=6 \
    -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p -c:a aac -shortest test_input.mp4
  -> video 1280x720, audio present, duration 6.000000 s

$ pip install opencv-python-headless==5.0.0.93 mediapipe==0.10.14 numpy==2.4.6
  -> attempt 1: ERROR: Could not install packages due to an OSError: [Errno 28] No space left on device
     (pip temp defaults to 512 MB tmpfs /tmp)
  -> attempt 2 (TMPDIR=$PWD/tmp): exit=0 ; cv2 5.1.0, mediapipe 0.10.14, numpy 2.4.6

$ python -c "import reframe_v2; delivery_size(1280,720,9/16); general_filtergraph(1080,1920,orig_w=1280,orig_h=720)"
  -> delivery_size = (1080, 1920); source_already_fits = False
  -> filtergraph matches the rendered one (diff clean except appended ,ass=trial.ass)

$ ffmpeg -i test_input.mp4 -filter_complex "<general_filtergraph>,ass=trial.ass" ... general_9x16.mp4
  -> 1080x1920, 6.000 s, video+audio, 1.7 MB, 24.4 s wall (6 s clip, CPU-only)

$ mediapipe FaceDetection(model_selection=1, min_detection_confidence=0.5) on test frame
  -> ran in 0.12 s; detections: None (testsrc has no face — expected)

$ python -c "import ultralytics"
  -> ModuleNotFoundError: No module named 'ultralytics'  (TRACK path blocked: needs torch/YOLOv8)
```

---

## 6. Recommendation — ADAPT (do not adopt the platform)

**Do not adopt OpenShorts as a VyralX component.** **Do adapt two of its ideas** into VyralX's existing ffmpeg-only code, off-fleet, when a talking-head need arises.

Concrete reasons:

1. **It cannot run where VyralX runs.** Docker-only, Python 3.11, 8 GB+ RAM, torch + YOLOv8 + faster-whisper + MediaPipe + OpenCV — against a Python 3.10 fleet with a ~180 MB resident-service cap. Whole-platform adoption would mean a new off-fleet service, new keys, and a new runtime, for a job VyralX already does.
2. **It mostly duplicates what exists.** Moment-finding, scene detection, static vertical crop, blurred-background layout, word-level styled subtitles and montage rendering are all already implemented in VyralX in smaller, deterministic, dependency-free form (`gta6_series.py`, `video_editor.py`, `captions.py`, `montage.py`, `short_video_assembly.py`, `shorts_live_path.py`).
3. **Its headline differentiators are either paid or forbidden here.** Dubbing is ElevenLabs pay-per-use (FREE ONLY closes it); auto-publishing/Autopilot/YouTube Studio one-click publish violate loop OFF, review-first and the owner stop order; YouTube ingest via yt-dlp is the broken, off-limits path.
4. **Its output would fail VyralX machine QA as produced.** No BGM (mandatory, ducked), no watermark/provenance step, no loudness gate, and captions burned in with no sidecar discipline for the caption-track gate (`held_render_qa.py`).
5. **Its moment-picker is the wrong method for this series.** LLM scoring of transcripts fits speech-led podcasts; VyralX's GTA-6 series is gameplay with no speech, which OpenShorts can only clip by sending frames to Gemini — and VyralX's deterministic audio-spike + scene-cut + transcript-window scoring already covers that case without a key or a third-party call.
6. **What is worth taking is small and portable.** The per-frame face-tracked crop trajectory (TRACK mode) is the one genuine gap: VyralX's crop is one fixed window per clip, OpenShorts' follows the speaker. That idea ports as a modest addition to the existing crop planning — a MediaPipe/face-position sampling pass producing a per-frame crop-x series rendered through ffmpeg `sendcmd`, reusing the `crop` filter VyralX already emits — without importing the platform, its torch stack, its Gemini dependency, or its publishing half. The SPLIT/SCREENCAST layouts are a second, lower-priority port for two-person or screen-share material only.

**Suggested next step (for the coordinator, not taken here):** if a talking-head clip need is confirmed, run OpenShorts' TRACK path **once, off-fleet, on the owner's machine** with real face-on-camera own-content footage and a Gemini free-tier key, and compare its moving crop against VyralX's static `vertical_crop_plan` on the same clip through the standing machine-QA gates. Adopt nothing until that comparison exists; port only the trajectory idea if it wins. No action taken in this evaluation — evaluation only, no commits, no PRs, no GitHub writes, no merges.

---

## 7. Sources

- Repo (observed 2026-11-25): https://github.com/mutonby/openshorts — main, commit `29ccbf372d6b3a99586ba7de2bf49d426bc2c69b`, 749 commits, 9,867 stars, 2,061 forks, MIT, 0 releases/tags. Cloned shallow to `~/workspace/musetp6-vyr052/openshorts-src/`; files read first-hand: `LICENSE`, `requirements.txt`, `requirements-cpu.lock`, `Dockerfile`, `README.md`, `reframe_v2.py` (936 lines), `recut.py`, `subtitles.py`, `scene_detection.py`, `clip_selection.py`, `active_speaker.py`, `burned_subtitles.py`, `ffmpeg_utils.py` (blurred_backdrop), `main.py` (imports/YOLO load, via grep).
- Homepage: https://www.openshorts.app/
- Self-hosting guide (requirements, costs, privacy): https://www.openshorts.app/self-hosted-ai-clip-maker
- VyralX files read first-hand: `~/workspace/musetp6-vyr052/gta6_series.py`, `captions.py`, `shorts_live_path.py`, `short_video_assembly.py`, `montage.py`, `video_editor.py` (defs), `held_render_qa.py` (defs), `forced_alignment.py` (head), `viral_repurposer.py` (head). Repo context: `surendra2304/FRIDAY-Universe`, main `be3f303ec28e3b5c9ba75e4fc23ca6b96126f557`.
- Prior established facts (not redone): OpenShorts zero hits in the repo; classification source file absent from main (8,546-entry tree checked); local `CLASSIFICATION-2026-11-24.md` is 14 bytes reading `404: Not Found`.
- Trial artefacts: `~/workspace/musetp6-vyr052/openshorts-trial/` (see §5).

— Muse TP6
