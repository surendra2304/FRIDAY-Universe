# TASK-VYR-066 — Checkpoint 1: scoping

**Task:** VyralX long-form AI story-video pipeline (ChatGPT script, Gemini TTS, Hark AI images).
**Worker:** Muse TP1. **Branch:** `musetp1/task-vyr-066-long-form-story-video-pipeline`.
**Main at scoping:** `e0373ced` (2026-11-25). **Claim:** hub 7144888229.
**Status:** scoping done, implementation not started. No work PR yet.

## Acceptance (board, TASK-VYR-066)

- A 5–15 minute story video is produced end to end: ChatGPT script, Google AI
  Studio TTS (Gemini 2.5 TTS, multi-voice), Hark AI images with consistent
  characters, assembly, and YouTube upload through VyralX's existing
  review-first gates (held unlisted until owner review).
- Workflow steps rest on the reel's legible on-screen text; the reel's spoken
  Telugu narration was not recovered (named gap in the watch record).
- Narration is English per VyralX operating rules; the Telugu gap stands.

## What already exists (verified first-hand on main `e0373ced`)

| Piece | File | Finding |
|---|---|---|
| Long-form lane | `VyralX/app/services/viral_longform.py` (10,612 B) | Compilation only: assembles held shorts into a 1920x1080 video, held unlisted. NOT a story pipeline. Reusable: ffmpeg assembly pattern (`render_compilation`), manifest consumption. |
| Film manifest | `VyralX/app/services/film_pipeline.py` (7,314 B) | `build_film` / `render_film_html` / `apply_studio_edit`, stdlib-only. Render gate REFUSES in-service rendering (headless Chromium too heavy for the fleet) — VyralX orchestrates, does not render here. Reusable as the manifest/edit layer. |
| Project pipeline | `VyralX/app/services/project_pipeline.py` (56,609 B) | `execute_project_pipeline`: stock-footage topic-to-video. Already wires captions, montage, Pexels, voiceover, `take_verification`, project quality. Script comes from `generate_content_pack`, not ChatGPT. Reusable as the assembly backbone. |
| Voiceover seam | `VyralX/app/services/voiceover.py` (20,718 B) | `synthesize_voiceover`: eSpeak local default; external / ElevenLabs / Edge per config. Alignment → caption cues. NO Gemini provider. This is the seam the Gemini TTS provider plugs into. |
| TTS voice map | `VyralX/app/services/audio_content.py` (7,913 B) | Podcastfy-pattern dialogue script + TTS segment plan (batch/off-fleet, renders nothing). `FREE_TTS_PROVIDERS = ("edge", "gemini")`; `GEMINI_VOICES = {"host_a": "Kore", "host_b": "Puck"}` — a two-voice Gemini MAP already exists, but no synthesis call. Reusable as the voice registry. |
| AI images | `VyralX/app/services/ai_visuals.py` (3,083 B) | Pollinations free image generation, probe-verified. No Hark AI anywhere. |
| QA gates | `VyralX/app/services/take_verification.py` (31,007 B, VYR-061) + `held_render_qa.py` (23,175 B) | Blank-frame self-verification, take selection, held-render machine-QA gates. Reusable unchanged on held story renders. |
| Upload | `VyralX/app/services/youtube.py` (34,616 B) | Held-unlisted publish-job path. Review-first gates apply as-is. |
| Config | `VyralX/app/config.py` | `tts_provider` default `espeak`; allowed `{espeak, external, elevenlabs, edge}` — NO `gemini` value yet. Gemini keys exist for vision fail-over (`gemini-3.5-flash-lite`). `inference_tts_url` exists (external path). |
| Tests | `VyralX/tests/` | `test_ig2_vyr01_audio_content.py`, `test_ig2_vyr05_film_pipeline.py`, `test_ig3_vyr05_take_verification.py`, `test_project_pipeline_e2e.py`, `test_vyr069_what_if_story.py`, `test_dispatch_and_voiceover_deep.py`. New tests join the owner-workflows.yml VyralX list. |

## What is missing (confirmed by code search on main `e0373ced`)

1. **ChatGPT script step — missing.** Code search `chatgpt`: 31 hits, docs only; no
   VyralX script provider. OpenAI providers exist in Forge / Inference / FRIDAY
   (reusable pattern), but VyralX has no script step and no OpenAI key on file.
2. **Gemini 2.5 TTS multi-voice synthesis — missing.** Code search `gemini tts`:
   voice map exists (above); no synthesis call in VyralX. `voiceover.py` has no
   Gemini path; config has no `gemini` provider value.
3. **Hark AI image adapter — missing.** Code search `hark`: 1 hit, in
   `Sentinel/app/services/real_cyber_skills.py`, unrelated. No adapter, no key,
   no endpoint, no free-tier knowledge on file.
4. **Story orchestrator — missing.** No module chains script → scenes → images →
   voiceover → assembly → held render → QA → publish job for a story.
5. **Source record gap.** The classification file cited by the board evidence
   (`docs/collaboration/CLASSIFICATION-2026-11-24.md`) was not found at that path
   on main, and watch record `DgCvwzbxoWw` has 0 code hits. The board evidence
   is the source of record for the workflow steps until the classification doc
   is located.

## Planned implementation shape

1. `VyralX/app/services/story_video.py` (new orchestrator): story script → scene
   plan → images → voiceover → assembly → held render → QA → publish job.
   Reuses the film manifest, `project_pipeline` assembly patterns, `take_verification`
   + `held_render_qa` gates, and the held-unlisted publish path.
2. `VyralX/app/services/chatgpt_script.py` (new): script provider behind a
   free-only guard. Blocked on Q1 below.
3. `VyralX/app/services/gemini_tts.py` (new): Gemini 2.5 TTS synthesis,
   multi-voice via the `audio_content.py` voice map (Kore/Puck, extensible);
   config gains a `gemini` provider value; `voiceover.py` dispatch extended.
   Fail-closed when the key is absent. Blocked on Q2 below.
4. `VyralX/app/services/hark_images.py` (new): Hark AI adapter with a character
   sheet / seed + reference mechanism for consistent characters. Fail-closed stub
   until Q3 is answered; Pollinations is NOT assumed as a substitute.
5. Tests: `VyralX/tests/test_vyr066_story_video.py` — script shape, voice map,
   image manifest, assembly manifest, QA gates, held-unlisted publish job;
   synthetic ffmpeg render check in the VYR-061 style; CI wiring in
   `owner-workflows.yml` (VyralX list). Evidence doc + board flip ride in the
   work PR.

## Questions for Muse (direction owed)

- **Q1 — ChatGPT script:** no OpenAI key is on file for VyralX and the free-only
  rule stands. Owner key/decision, or a ruling to generate the script with the
  fleet Gemini key instead (a deviation from the acceptance — needs a ruling)?
- **Q2 — Gemini TTS key scope:** may the fleet Gemini key be used for TTS
  synthesis? To be verified on the fleet, not assumed.
- **Q3 — Hark AI:** key / endpoint / free tier, or a ruling to use Pollinations
  (the existing free image path) instead?
- **Q4 — Driver:** TP1's hourly self-check stays removed per rule 7 (owner
  order 7143628341); after this run VYR-066 has no hourly driver. Re-arm an
  hourly verification driver for TP1, or direction per checkpoint?

## Next

Implementation starts when Q1–Q3 are answered (or ruled). Until then no provider
code is written and nothing is invented about keys, endpoints, or free tiers.

— Muse TP1, 2026-11-25 ~17:52 IST
