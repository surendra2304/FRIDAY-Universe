# TASK-VYR-072-FIX-01 — Live leg: repair the doubled-caption render + re-run held-render QA + vision sampler

- Task: TASK-VYR-072-FIX-01 — "Held render framed--bh5VGbrbLI-5970f1 carries doubled captions (multiple_caption_tracks:2): repair or re-render the caption track to a single track and re-run held-render QA to pass."
- Owner: Muse 14. Work PR #2013 MERGED (merge bf3c76c9, ~05:57 IST 2026-11-27).
- Clearance: WATCH181 §2c (hub #1483 comment 7201871583, ~01:12 IST): "VYR-072-FIX-01 live leg GRANTED under standing clearance 7200564540 (own-task live verification). Muse 14: run the repair/re-render on VyralX-Server + held-render QA + vision sampler now. Loop stays OFF, uploader stays paused, renders held unlisted." WATCH182 §2d corroborates.
- Host: VyralX-Server 13.211.162.71, hostname ip-172-26-12-48, port 8010. Live venv /opt/friday_universe/venv/bin/python, cwd /opt/friday_universe/VyralX.
- Live-leg outputs on the server: /tmp/vyr072-fix01-live-leg/ (baseline.json, repair.json, qa_after.json, vision.json, the repaired .ass, the original .ass backup, and the run scripts). Nothing written into the live tree except the render's .ass (see §2). No deploy, no service restart, no upload, no publish.

## 0. How this leg ran (duplicate-agent note)

A parallel agent ran the same leg on the server starting 2026-11-27T00:40:14Z (baseline), 00:45:43Z (repair), 00:48:40Z (QA after), 00:52:05Z–01:02:35Z (vision sampler), writing to /tmp/vyr072-fix01-live-leg/. This evidence doc is compiled by a second subagent (Muse 14) which verified every result below first-hand from the server artifacts and the live files — the repair, the QA, and the vision sampler were NOT re-run (re-running them would duplicate vision spend and conflict on the same .ass). The duplicate is reported to the parent for reconciliation; no second work PR was filed from this verification pass.

## 1. Live agent state (verified first-hand, before and after the runs)

- /health 200, /ready 200 (live VyralX service).
- VyralX.service: active / running, NRestarts=0, ActiveEnterTimestamp Thu 2026-11-26 06:42:52 UTC — unchanged before, during and after the leg (no restart). Note: the timestamp moved from the VYR-072 leg's Wed 2026-11-25 11:09:44 UTC; the service was stopped/started once between the two legs (not by this leg; NRestarts=0).
- Disk /: 58G total, 38G free. No vyralx/autopilot processes running (loop OFF). vyralx-daemon.service and vyralx-autopilot.service both inactive. Only vyralx timer: vyralx-metrics-sync.timer (next run 05:35 UTC; it is the metrics timer, not the loop).
- Live tree /opt/friday_universe/VyralX is a deployed copy (NOT a git checkout — no .git). It does NOT contain the FIX-01 code (grep count 0 for repair_doubled_ass in viral_framing.py and for "must not overlap" in viral_remix.py) — PR #2013 merged to main after the owner stop order and no deploy has run since. The repair therefore ran from an overlay: the FIX-01 modules were copied from main into /tmp/vyr072-fix01-live-leg/overlay/ (md5-verified matching main) and loaded from there; the live tree is unchanged.
- Render: renders/framed--bh5VGbrbLI-5970f1.mp4 (29.23 s, 720x1280, 1 audio stream, Nov 18), sibling .ass, job 802, series PETS, "Dog Watches Man Press Buttons", status HELD, privacy unlisted (manifest data/viral_loop_manifest.jsonl).

## 2. Baseline (before the repair) — defect confirmed

Run 2026-11-27T00:40:14Z–00:40:24Z (baseline.json / baseline.out):
- .ass: 20 dialogue events, 0 malformed, 20 speech events, 0 hook events. ass_caption_track_count = 2.
- Overlapping pairs (Q1, verified first-hand from the original .ass backup): 0.0–1.0 "CRAP, PRESS THE BLUE BUTTON." over 0.0–3.34 "WATCH WHAT HAPPENS WHEN HE POINTS AT THAT BUTTON."; 0.0–3.34 over 1.0–2.0 "OH NO!" and over 2.0–3.56 "WHAT YOU GOT BEEF WITH"; 25.28–27.28 "OH NO!" over 25.34–29.23 "HE SMILES AS THE DOG STAYS STILL BESIDE THE TWO BUTTONS."
- Held-render QA on the original: overall passed False, failed_gates [caption_track, bgm, watermark].

## 3. Repair — the .ass is now a single track (verified first-hand)

Run 2026-11-27T00:45:43Z (repair.json / repair.out). repair_doubled_ass from the overlay (FIX-01 code, fail-closed writer confirmed: the Q1 cue list is rejected with "Caption cues in style AntonBold must not overlap by more than 0.10s"):
- Source: renders/framed--bh5VGbrbLI-5970f1.ass (md5 6a1e049f3e301f0fdeea752d48173771, 2315 bytes, Nov 18). Destination: /tmp/vyr072-fix01-live-leg/framed--bh5VGbrbLI-5970f1.repaired.ass.
- hook_text "Watch what happens when he points at that button.", payoff_text "He smiles as the dog stays still beside the two buttons." (job-802 texts from the live-leg evidence).
- Result: events_in 20, events_out 20, framing_restyled 2 (hook 0.0–3.34 and payoff 25.34–29.23, both to AntonFraming), dropped_duplicates 0, ass_caption_tracks 1.
- The repaired .ass (md5 7849d5eafd2a31bccf1cad39426706d9, 2440 bytes) was placed as the render's .ass; the original was backed up to /tmp/vyr072-fix01-live-leg/framed--bh5VGbrbLI-5970f1.ass.orig (2315 bytes). The repair function itself never overwrote its source; the placement is a separate copy step, per the filed plan (implementation doc §6 step 1).
- Independent verification (second subagent, stdlib-only parse of both files): original = 20 events, 20 speech, 0 hook, track count 2, 4 speech-speech overlaps. Repaired (live) = 20 events, 18 speech, 2 hook, track count 1, 0 speech-speech overlaps. Live .ass md5 matches the repaired file exactly.

## 4. Held-render QA after the repair — caption corroboration passes, overall still False

Run 2026-11-27T00:48:40Z–00:48:44Z (qa_after.json / qa_after.out). run_held_render_qa on the render with the repaired .ass (vision sampler stubbed to unmeasured in this pass; the vision run is §5):
- ass_file = renders/framed--bh5VGbrbLI-5970f1.ass (live, repaired). ass_events 20, ass_speech_events 18, ass_hook_events 2, ass_malformed_lines 0, ass_caption_tracks 1.
- Gates: caption_track passed False, reason caption_gate_unmeasured (vision sampler not run in this pass); bgm passed TRUE, reason bgm_present (voiceless gap 27.28–29.23 at -25.7 dBFS, above the -45 floor — the payoff is now a hook event, excluded from speech, so the tail gap is measurable; in the VYR-072 leg bgm was unmeasured); watermark passed FALSE, reason watermark_absent (pre-existing Q2, pool-wide — no vyralx-provenance marker); loudness passed TRUE, reason loudness_ok (integrated -13.6 LUFS, true peak -1.5 dBFS).
- Overall passed False, failed_gates [caption_track, watermark].

## 5. Vision sampler — the frames still show doubled captions (re-render needed)

Run 2026-11-27T00:52:05Z–01:02:35Z (vision.json / vision.err / vision.out). Deployed sampler scene_analysis.sample_render_caption_detections with interval_seconds=2.0 (deliberate: 15 frames at t=1.0, 3.0, …, 29.0 in 5 vision requests, instead of the 0.5s default's 58 frames / 20 requests; the .ass overlaps live only in 0–3.56s and 25.28–29.23s, and this sample covers both windows with decisive frames — t=3.0 hook + "WHAT YOU GOT BEEF WITH", t=27.0 "OH NO!" + payoff). Pacing stayed at the deployed 65s default. The mp4 is byte-identical before/after the .ass repair, so this one run characterises the frames for both states.
- 5 vision requests, all HTTP 200, ~24,463 estimated tokens total. Groq primary (qwen/qwen3.8-27b) rejected every request with HTTP 429 — the sampler requests max_tokens=1500 but the model's output-tokens-per-minute limit is 1000 ("Request too large … Limit 1000, Requested 1500"). The sampler's built-in failover (TASK-VYR-028) then succeeded against Gemini (gemini-3.5-flash-lite, VISION_FAILOVER_*). 7 Groq 429 lines in vision.err; all 5 logical requests completed via failover.
- 30 detections across the 15 frames. Decisive frames: at 0.0–2.0s four lines at once — "WATCH WHAT HAPPENS WHEN", "HE POINTS AT THAT BUTTON.", "Crème press the blue button." (vision misread of "CRAP, PRESS THE BLUE BUTTON."), "OH NO!"; at 2.0–4.0s three lines — hook (2 lines) + "WHAT YOU GOT BEEF WITH"; at 26.0–28.0s three lines — payoff (2 lines) + "OH NO!".
- caption_gate_from_detections: passed FALSE, reason multiple_caption_tracks:4, tracks 4.
- Full QA re-run reusing the same detections (no second sampler pass): ass_caption_tracks 1; gates caption_track FALSE (multiple_caption_tracks:4), bgm TRUE (bgm_present), watermark FALSE (watermark_absent), loudness TRUE (loudness_ok); overall passed FALSE, failed_gates [caption_track, watermark].
- Why the vision gate fails: the mp4's captions were burned in by ffmpeg from the ORIGINAL .ass (Nov 18). Repairing the .ass does not change the frames. The vision sampler reads the frames, so it still sees the doubled burned-in captions. Only a re-render (burning the repaired .ass into a new mp4) can make the frames show a single track.
- Re-render feasibility: NOT reproducible from the available job record. The manifest (data/viral_loop_manifest.jsonl) records job 802 (source -bh5VGbrbLI, excerpt start 0.0 / 29.23s, series PETS, bgm synth_fallback) but not the render_framed inputs (hook/payoff audio files, BGM bed path, cues, category). The source video media/viral_sources/-bh5VGbrbLI.mp4 (1080x1920, 29.23s) and the video-only excerpt framed--bh5VGbrbLI-5970f1-excerpt.mp4 (1080x1920, 29.17s, no audio) are on disk, but the narration/ducking/BGM mix cannot be reproduced without the job inputs.

## 6. Verdict (honest, per the owner standard)

- The caption TRACK (the .ass) is repaired: 20 events, 2 framing lines restyled to the AntonFraming top band, 0 dropped, track count 1, 0 overlaps — verified first-hand twice (the leg's repair report and an independent parse). The render's .ass now counts a single track.
- The held-render QA does NOT pass overall: failed_gates [caption_track, watermark]. The watermark failure is the pre-existing pool-wide Q2 (not this task). The caption_track failure is the vision gate: the frames still show 4 caption tracks because the mp4 carries the old burned-in captions.
- The board acceptance ("repair or re-render the caption track to a single track and re-run held-render QA to pass") is therefore PARTIALLY met: the .ass repair is done and verified, but the frame-visible caption gate cannot pass without a re-render, which is not reproducible from the available job record. The remaining step is a re-render of job 802 from its production inputs (or a coordinator decision to accept the .ass repair as the fix for this held render, with the frames as-is).
- Do NOT flip FIX-01 to MERGED on this evidence alone: the vision gate fails. The task stays IN_REVIEW until the re-render (or a coordinator ruling) closes the caption gate.

## 7. Five states (owner standard: merged code is NOT implemented)

| State | Value |
| --- | --- |
| Implemented | YES — repo-side (PR #2013 merged) + live .ass repaired to a single track |
| Tested | YES — repair verified (track count 1, 0 overlaps); QA re-run twice; vision sampler run (30 detections, 5 requests) |
| Merged | YES — work PR #2013 merged (merge bf3c76c9); this live-leg evidence doc is NOT yet filed as a work PR |
| Deployed | NO — no deploy; the live tree does not contain the FIX-01 code (overlay used); the live .ass was replaced per the filed plan |
| Production-verified | NO — the vision caption gate fails (multiple_caption_tracks:4); a re-render is owed |

## 8. Constraints honoured

- Verification only: no deploy, no service restart (NRestarts=0, timestamp unchanged), no move, no upload, no publish. Loop stayed OFF, uploader paused (autopilot/daemon inactive), renders held unlisted (job 802 privacy unlisted, status HELD).
- The live tree is unchanged (overlay used for the FIX-01 code; the only live-tree write is the render's .ass, replaced per the filed plan with the original backed up).
- No second vision pass was run from this verification (the sampler already ran once; re-sampling would double the vision spend for the same frames).
- Groq 429 note: the deployed sampler requests max_tokens=1500 but the Groq model qwen/qwen3.8-27b enforces an output-tokens-per-minute limit of 1000, so every primary request 429s and the Gemini failover carries the run. A future sampler run should cap max_tokens at 1000 for the Groq primary (or rely on the failover as here).

— Muse 14
