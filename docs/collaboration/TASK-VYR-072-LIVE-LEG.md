# TASK-VYR-072 — Live leg: live evidence per item (IG2-VYR-01..05)

- Task: TASK-VYR-072 — PRODUCTION-VERIFY: VyralX corpus items IG2-VYR-01, -02, -03, -04, -05, live extreme-condition verification (wave 1).
- Owner: Muse 14. Branch: `muse14/task-vyr-072-live-leg` (base main `b9d6aff3`).
- Clearance: WATCH113, hub #1483 comment 7171357668, 2026-11-26 ~00:15 IST — "VYR-072 clearance acknowledged (#1596): the coordinator probe passed 5/5 (VyralX.service running, live tree intact, renders 821 + 825 held, loop OFF, disk 38G free). Muse 14 — proceed with the VYR-072 live leg." WATCH114 (7172052508) does not countermand this.
- Owner stop order (~16:42 IST 2026-11-24, "Don't move anything now") still in force: this leg is verification only. No deploy, no move/copy/delete of server contents, no service restart, no upload. Loop stayed OFF, uploader paused, renders held unlisted throughout.
- Repo-side sanity: the 32 unit tests re-run first-hand on current main `b9d6aff3` — **32 passed, 0 failed** (8+8+7+5+4), pytest 9.2.0, Python 3.12.3, local clone.

## 1. Live agent state (verified first-hand, before and after the runs)

- Host: VyralX-Server `13.211.162.71`, hostname `ip-172-26-12-48`, port 8010.
- `/health` 200, `/ready` 200 (re-checked this run; health: status ok, service vyralx, version 0.2.0; ready: database connected, ffmpeg true).
- `VyralX.service`: active / running, `NRestarts=0`, `ActiveEnterTimestamp Wed 2026-11-25 11:09:44 UTC` — unchanged before, during and after the leg (no restart).
- Disk `/`: 58G total, 38G free. No `vyralx`/`autopilot` processes running (loop OFF).
- Renders dir `/opt/friday_universe/VyralX/renders/`: 221 files (77 mp4 + 77 .ass + 65 jpg + 2 json), 2.2G. Media dir 3.9G, including 232 real viral-source videos.
- Live tree identity: md5 of all seven modules used matches repo main exactly (`audio_content.py 31aaf2d5…`, `pipeline_orchestration.py 24dee046…`, `shorts_factory.py fe0dc88f…`, `shorts_generator.py e954c2eb…`, `film_pipeline.py 8f9ced65…`, `held_render_qa.py b3cdfe9f…`, `captions.py 516a1bfb…`). The code that ran on the server IS the merged code.
- Bridge transport was flaky as documented (IncompleteRead / RemoteDisconnected on several attempts); every call was retried with backoff, and no command whose outcome was unknown was blindly re-run — state was checked first. Long runs were launched with `nohup` on the server and polled, so no bridge timeout could leave an unknown outcome.

## 2. Common real task

One real task threaded through all five items, on the live host, in the live venv (`/opt/friday_universe/venv/bin/python`, cwd `/opt/friday_universe/VyralX`):

- Topic: "Voyager 1 is still calling home", lane `space_science`.
- Real source video: `media/viral_sources/8kggT2ej-lo.mp4` (38.5 s, 1080x1920, video + audio, on disk since Oct 26).
- Real held render used as the QA/quality artifact: `renders/framed--bh5VGbrbLI-5970f1.mp4` (29.23 s, video + audio, sibling `.ass` present, Nov 18).
- Real BGM file referenced: `media/music/ambient_beat.mp3`.
- All live outputs went to `/tmp/vyr072-live-leg/` on the server only (nothing written into the live tree, nothing uploaded, nothing published). Raw evidence JSON: `live-evidence-items.json`, `live-evidence-qa.json` in that dir.

## 3. Per-item live evidence

### IG2-VYR-01 — audio_content.py (Podcastfy-pattern audio lane) — PASS

- Ran `build_audio_job` live: job kind `vyralx.audio_content_job`, execution `batch_offline`, 10 dialogue turns, estimated 0.58 min, 10 Edge TTS segments (`en-US-AriaNeural` / `en-US-GuyNeural`), provider `edge`, `paid_services_used: false`, `publish: false`.
- Failure cases (both raised correctly, live): paid provider `openai` → `AudioContentError: TTS provider 'openai' is paid; free paths only ('edge', 'gemini')`; finance-advice source ("guaranteed returns") → `AudioContentError: dialogue blocked by finance-advice screen: [{'pattern': 'promised returns', ...}]`.
- Observation, not a failure: `within_target_window: false` — the 0.58-min episode sits below the `short` mode's 2.0–5.0 min target window. The module reports this honestly; the source text was short. No silent trimming happened.

### IG2-VYR-02 — pipeline_orchestration.py (OpenMontage-pattern orchestration) — PASS

- Pipelines listed live: `clip_factory`, `documentary_montage`, `explainer_short`, `podcast_repurpose`, `tech_explainer`.
- Provider scoring live: free `edge_tts` eligible, score 95.0; paid GPU candidate ineligible (score 0.0, reasons: "cost $5.00 exceeds budget $0.00", "requires GPU (fleet has none)"). `select_provider` picked `edge_tts`.
- Full run advanced live through all 9 stages (`research → script → storyboard → assets → voice → compose → quality → approval → publish_plan`) to `current_stage: complete`, all stages `done`, `publish: false`.
- Failure cases (all raised/failed correctly, live): advancing past `storyboard` without approval → `OrchestrationError: storyboard approval gate: a human must approve the storyboard before production stages run`; quality gate on an over-cap (120 s, no captions, no provenance) artifact vs `clip_factory` → `passed: false` (all three checks false); quality gate on a finance-advice script → `passed: false` (`no_finance_advice: false`).
- Quality gate on the REAL render (`framed--bh5VGbrbLI-5970f1.mp4`, 29.23 s, captions present via sibling `.ass`, provenance present) vs `clip_factory` → `passed: true` (duration_within_cap, captions_present, provenance_present all true).

### IG2-VYR-03 — shorts_factory.py (Shorts factory) — PASS

- Ran `build_job` live: estimated 15.6 s (< 60 s cap), 14 subtitle cues (first cue 0.0–1.181 s, "Stop scrolling —"), voice plan Edge `en-US-AriaNeural`, 2 mix segments, `bgm_duck_under_voice: true`, 1080x1920. Materials were the two real viral-source files with real YouTube provenance URLs (`youtube.com/watch?v=8kggT2ej-lo`, `...?v=CtYG9NYkRdg`), licence recorded honestly as "YouTube source copy (licence unverified)".
- `fill_batch` to target 3 → 3 jobs, `all_planned: true`.
- Failure cases (both raised correctly, live): material without licence/provenance → `ShortsFactoryError: storyboard material lacks licence/provenance`; empty facts → `ShortsFactoryError: a factory job needs at least one fact beat`.

### IG2-VYR-04 — shorts_generator.py (local-only Shorts generator) — PASS

- Real transcription live: faster-whisper `tiny` (int8, CPU) on the real source video transcribed 55 timed words in 17.5 s, language `en`, opening "If you can beat any animal on the planet, what would it be…". (Footnote: an earlier probe run of the same file with the same model returned 95 words — transcription word counts vary run to run; the live leg uses the 55-word transcript from the live run itself.)
- `generate_shorts` (mode `local`) → 1 clip: `short-01`, 0.0–30.0 s, duration 30.0 s, viral_score 0.2275, `status: pending_review`, `privacy: unlisted`.
- Real end-to-end render live: the clip's crop plan executed with ffmpeg on the real source video → `/tmp/vyr072-live-leg/vyr04-short-01.mp4`, ffmpeg rc 0, ffprobe-verified 1080x1920, 30.0 s, video + audio. Filter `crop=1080:1920:0:0,scale=1080:1920` (plan correctly parameterised for the vertical 1080x1920 source; note the module's built-in plan assumes a 1920x1080 landscape source — `vertical_crop_plan` takes source dims as parameters, which is what was used). Never published, never uploaded.
- Failure cases (both correct, live): mode `api` → `PaidModeRejected: mode='api' uses the paid MuAPI service and is rejected under the FREE-only rule; use mode='local'`; empty transcript → `available: false`, zero clips, reason "no timed transcript supplied; run the off-peak tiny/base faster-whisper batch first" — an honest empty result, never invented clips.

### IG2-VYR-05 — film_pipeline.py (OpenFilm-pattern film pipeline) — PASS

- Ran `build_film` live: 3 shots, 30.0 s total (8 + 10 + 12), kind `short`, lane `space_science`, tracks `video, captions, music` (music track: real `media/music/ambient_beat.mp3`), `status: pending_review`, `privacy: unlisted`, `publish: false`.
- `render_film_html` live → `film.html`, 870 bytes, 3 `<section class="shot">` sections, written to `/tmp/vyr072-live-leg/film.html`.
- Studio edits live: trim `shot-01` 8.0 → 6.0 s, retype `shot-02` text — edited film 28.0 s, edit log 2 entries, still `pending_review`.
- `render_gate(host_role=fleet_service)` → `allowed: false` ("headless-Chromium rendering exceeds the ~180MB fleet service cap", `renders_in_service: false`) — the in-service refusal is the module working as designed. `render_command(host_role=owner_machine)` → `available: true` with the ffmpeg argv — rendering is an off-fleet plan, executed nowhere here.
- Failure cases (both raised correctly, live): short totalling 70 s → `ValueError: short film is 70.0s > 59.0s cap`; unknown studio op `explode` → `ValueError: unknown studio edit op 'explode'`.

## 4. Machine-QA under bad inputs (extreme-condition leg)

Run live on the server with `held_render_qa` / `viral_quality` / `media_quality` against the real held render `framed--bh5VGbrbLI-5970f1.mp4` (29.23 s, 1 audio stream) plus bad inputs built from real server media.

### 4a. Full held-render QA (`run_held_render_qa`) — overall `passed: false`, 3 of 4 gates failing/unmeasured

| Gate | Result | Detail |
| --- | --- | --- |
| loudness | PASS — `loudness_ok` | integrated −13.6 LUFS, true peak −1.5 dBFS, clipped samples null (real ffmpeg loudnorm scan) |
| bgm | `bgm_unmeasured` | No voiceless gap to measure and no silence interval: speech tiles the render, loudness scan found no silence ≥ 1 s below −45 dB. Per the module's own docstring this is the documented unmeasured outcome — "the bed cannot be separated from the voice by this method" — not a pass, not a render failure |
| watermark | FAIL — `watermark_absent` | No `vyralx-provenance:` comment marker; LSB payload absent (1 frame checked). See finding Q2 |
| caption_track | `caption_gate_unmeasured` (vision) | The default vision-frame sampler was NOT run: it paces 65 s per request over up to 120 frames and would burn vision budget. Recorded as unmeasured via the module's own sampler seam (fail-closed). The caption track was instead measured from the render's own `.ass` — see 4b |

### 4b. Caption track measured from the render's own `.ass` — FAIL, doubled captions (finding Q1)

- `.ass` parse: 20 dialogue events, 0 malformed, 20 speech events, 0 hook events.
- `ass_caption_track_count` = **2**; `caption_track_gate` → `(False, "multiple_caption_tracks:2")`.
- Overlapping pairs verified first-hand (different texts on screen at once):
  - 0.0–1.0 "CRAP, PRESS THE BLUE BUTTON." over 0.0–3.34 "WATCH WHAT HAPPENS WHEN HE POINTS AT THAT BUTTON."
  - 0.0–3.34 "WATCH WHAT HAPPENS…" over 1.0–2.0 "OH NO!" and over 2.0–3.56 "WHAT YOU GOT BEEF WITH"
  - 25.28–27.28 "OH NO!" over 25.34–29.23 "HE SMILES AS THE DOG STAYS STILL BESIDE THE TWO BUTTONS."
- This is the 823/841/861 doubled-caption class, found live in a real held render. Precise scope: the defect is in the render's subtitle track; frame-visible confirmation via the vision sampler was not run (see 4a), so the claim is "subtitle track carries doubled captions", not "frames show doubled captions".

### 4c. Bad-input probes (gates must fail bad inputs — all behaved correctly)

- Missing BGM: 6 s video-only cut of the real render (`noaudio.mp4`, 0 audio streams) → `bgm_gate: (False, "no_audio_stream")`; `loudness_gate: (False, "loudness_unmeasured")`. Signals status `analyzed`.
- Doubled captions (synthetic): a second caption line stacked over the first 5 speech events → `count_caption_tracks: 4`, gate `(False, "multiple_caption_tracks:4")`.
- No captions: empty detection list → `(False, "no_caption_track_visible")`.
- Watermark positive control: same render re-muxed with `-metadata comment="vyralx-provenance:vyr072-live-leg"` → `watermark_gate: (True, "watermark_present")`, marker present. The gate detects a marker when one exists — so `watermark_absent` on the real render is a true negative, not a broken gate.

## 5. Metrics-sync against the real channel — NOT RUN (blocked, G2)

- `ypp_tracker.fetch_channel_statistics()` attempted live → `RuntimeError: "Channel statistics unavailable: set youtube_channel_id + youtube_data_api_key, or restore the YouTube OAuth session (RuntimeError)"`.
- No YouTube Data API key / channel id is configured and the OAuth session is not restorable from here. No metrics were fetched, and none were fabricated. Discovery via the live YouTube API is blocked by the same credential gap; the render/discovery cycle in this leg used the server's real discovered-source pool (232 viral-source videos) instead.
- Unblock: owner/coordinator configures `youtube_channel_id` + `youtube_data_api_key`, or restores the YouTube OAuth session; then re-run `fetch_channel_statistics()` and record the returned public stats.

## 6. Findings filed from this record

- **Q1 — Doubled captions in held render `framed--bh5VGbrbLI-5970f1`** (see 4b). Fix task filed: **TASK-VYR-072-FIX-01** (board entry, status AVAILABLE, owner null): repair or re-render the render's caption track to a single track and re-run held-render QA to pass; frame-visible confirmation via the vision sampler is part of the fix verification. This is a defect in a pre-existing Nov 18 held render, not in any of IG2-VYR-01..05 — no item is marked failed and none is left unverified on its account.
- **Q2 — Held renders carry no provenance watermark.** `watermark_absent` on the real render; the gate is proven working by the positive control (4c). Pool-wide, not a single-render defect — recorded for the coordinator's decision (re-watermark the held pool vs accept); no separate fix task filed.
- **G2 — Metrics-sync blocked** (see 5). Owner/coordinator credential action, not a code fix.

## 7. Five states (owner standard: merged code is NOT implemented)

| Item | Implemented | Tested | Merged | Deployed | Production-verified |
| --- | --- | --- | --- | --- | --- |
| IG2-VYR-01 audio_content | YES — live job built | YES — 32/32 unit + live | YES — PR #670 | YES — live tree md5 = main, service active | YES — §3 live evidence |
| IG2-VYR-02 pipeline_orchestration | YES — live run completed | YES — 32/32 unit + live | YES — PR #673 | YES — live tree md5 = main, service active | YES — §3 live evidence |
| IG2-VYR-03 shorts_factory | YES — live job + batch | YES — 32/32 unit + live | YES — PR #679 | YES — live tree md5 = main, service active | YES — §3 live evidence |
| IG2-VYR-04 shorts_generator | YES — live transcript + clips + ffmpeg render | YES — 32/32 unit + live | YES — PR #669 | YES — live tree md5 = main, service active | YES — §3 live evidence |
| IG2-VYR-05 film_pipeline | YES — live film + film.html + edits | YES — 32/32 unit + live | YES — PR #672 | YES — live tree md5 = main, service active | YES — §3 live evidence |

"Deployed" here means the merged code is the code running in the live service (md5-verified identical to main, service active since 2026-11-25 11:09:44 UTC, NRestarts=0). No item was deployed by this leg — the stop order forbids deploys; the live tree already contained the merged code.

## 8. Constraints honoured

- No deploy, no server move/copy/delete, no service restart (NRestarts=0, ActiveEnterTimestamp unchanged across the leg), no upload, no publish. The VYR-04 render and film.html live only in `/tmp/vyr072-live-leg/` on the server.
- Loop stayed OFF (no autopilot/vyralx processes before, during or after); uploader paused (nothing uploaded).
- No credentials read or recorded. The metrics-sync attempt called the service's own function; the failure reason is the only thing recorded.
- yt-dlp was not needed: all source media already existed on disk (232 viral sources), so the VYR-056 download break did not gate this leg.

— Muse 14
