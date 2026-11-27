# TASK-VYR-092: BGM batch verification run 2 — per-render evidence — Muse 9

- Task: TASK-VYR-092 (VyralX: BGM batch verification run 2). Acceptance:
  "Verify BGM presence + loudness on the held-render batch; file
  per-render pass/fail." + "No render goes public; held renders stay
  unlisted."
- Claim: hub #2045 comment 7214362552 by Muse 9, 2026-11-27 ~14:38 IST.
  Branch `muse9/task-vyr-092` (claim commit `c1e41b17`; fast-forwarded
  to current main `cb3a9c6d` immediately before this PR — claim-only
  branch, no unique commits; merge-base = `cb3a9c6d`).
- Gate run: 2026-11-27 ~15:43–15:46 IST, read-only on VyralX-Server
  via the bridge (`run_shell`, server 5, host `ip-172-26-12-48`).
  Results file `/tmp/vyr092_results.json` on VyralX-Server (22,767
  bytes, written 10:16 UTC; kept for the verifier). Driver:
  `/tmp/vyr092_driver.py` on the server (imports the agent's own
  `held_render_qa` gates; no repo code changed by this task).
- Route note (stated plainly): the task's assumed route was Oracle
  Server 2. Verified first-hand this run: S2 (`friday-universe-vnic-2`)
  holds only a sleeping VyralX copy — no renders, no `data/bgm`
  shelf (`viral_bgm.library_status()` = 0 tracks), no media files at
  all under `VyralX/`. Server 1 holds a mirror of the renders +
  shelf but has no ffmpeg/ffprobe. The live VyralX host is
  VyralX-Server (AWS, bridge server 5) — renders, shelf, ffmpeg
  6.1.1 and the service venv are there, and `VyralX.service` is
  active (`/health` 200, v0.2.0). The run therefore executed on
  VyralX-Server via the bridge, same host and route as the
  TASK-VYR-044 run. For the record: direct S2→U2 probes still fail
  (ping 100% loss, TCP 22/8000 FAIL — the TASK-VYR-047 run-1
  blocker), but the bridge server-5 route reaches the host fine.

## The batch

`VyralX/data/viral_loop_manifest.jsonl` on VyralX-Server: exactly 11
rows, all `"status": "HELD"` (jobs 801–804, 821–825, 841, 861),
verified before and after the run (`grep -c` = 11 both times). All 11
render files exist under `VyralX/renders/framed-*.mp4` with sibling
`.ass` files; render mtimes are 2026-11-18…21 (untouched by this
run; e.g. job 801 `framed-ClQTsoa23FU-2a2df6.mp4` 2026-11-18
17:43 UTC, job 861 `framed-bhw0Cxw9WGs-b4e71e.mp4` 2026-11-21
01:17 UTC). Loop last cycle 2026-11-21 (cycle 11, per
`viral_loop_state.json`) — loop OFF, uploader paused throughout;
nothing published, started, re-rendered, deleted, or deployed.

## How each gate is measured (the agent's own tooling)

- **Loudness** — `media_quality.analyze_media_signals` (ffmpeg
  ebur128) judged by `held_render_qa.loudness_gate`: pass iff
  integrated loudness in [-24, -10] LUFS AND true peak <= -1.0 dBFS
  (the VYR-081 series-gate constants). `clipped_samples` is None on
  the deployed scanner — carried as None, never a pass/fail input.
  Pipeline target is -14 LUFS (`loudnorm=I=-14:LRA=9:TP=-1.5` in
  `viral_repurposer.py` / `transformative_commentator.py`).
- **BGM presence** — `held_render_qa.bgm_gate` (VYR-047 method,
  measured on the finished render, not read off the manifest):
  ffmpeg volumedetect RMS per segment; voiced stretches from the
  sibling `.ass` speech timings (hook/title styles excluded via
  `speech_events`), voiceless gaps >= 0.5 s. Pass iff every voiceless
  gap measures above the -45 dBFS floor AND no silence interval
  from the ebur128 scan falls in a voiceless stretch. When the
  speech union tiles the whole render there is no gap to measure:
  then a silence interval is itself the absence evidence, and with
  neither, the gate is `bgm_unmeasured` — fail-closed, never a pass.
  Limit, stated plainly: RMS confirms audible non-voice energy in
  the gaps, not the bed's identity; the manifest `bgm_source` is
  the corroboration for what that energy is.
- Per render the driver also recorded ffprobe stream listing (all 11:
  exactly 1 AAC stereo audio stream, 96 kHz) and SHA-256 of the
  render file (first 16 hex in the table notes below).

Exact commands (server side, via bridge `run_shell` server 5):
`cd /opt/friday_universe/VyralX && /opt/friday_universe/venv/bin/python /tmp/vyr092_driver.py`
(driver calls `analyze_media_signals`, `loudness_gate`,
`parse_ass_dialogue`, `speech_events`, `bgm_gate` per HELD manifest
row; ffprobe via `ffprobe -v error -show_format -show_streams -of json`).

## The table — per held render, BGM + loudness (run 2, 2026-11-27)

| job | video | series | bgm_source (manifest) | BGM | loudness |
|---:|---|---|---|---|---|
| 801 | ClQTsoa23FU | COMEDY | synth_fallback | PASS `bgm_present` (voiced -17.3 dBFS, voiceless -18.1 dBFS, 1 gap 4.00–10.60 s @ -18.1) | PASS `loudness_ok` (-14.1 LUFS, peak -1.5 dBFS) |
| 802 | -bh5VGbrbLI | PETS | synth_fallback | PASS `bgm_present` (voiced -16.4 dBFS, voiceless -25.7 dBFS, 1 gap 27.28–29.23 s @ -25.7) — see delta note | PASS `loudness_ok` (-13.6 LUFS, peak -1.5 dBFS) |
| 803 | uKbWHP3Bvew | HOWTO | synth_fallback | UNMEAS `bgm_unmeasured` (speech tiles render, no silence interval) | FAIL `true_peak_too_high` (-13.5 LUFS, peak -0.6 dBFS) |
| 804 | x_iPi08PdZU | COMEDY | synth_fallback | PASS `bgm_present` (voiced -16.4 dBFS, voiceless -14.9 dBFS, 2 gaps) | FAIL `true_peak_too_high` (-13.5 LUFS, peak -0.9 dBFS) |
| 821 | REZwUljF8cc | PETS | growth:viral_imagine-dragons_enemy | PASS `bgm_present` (voiced -20.6 dBFS, voiceless -21.4 dBFS, 3 gaps) | PASS `loudness_ok` (-13.4 LUFS, peak -1.3 dBFS) |
| 822 | zE6Htw50oaM | AUTOS | growth:howto_dua-lipa_levitating | PASS `bgm_present` (voiced -14.4 dBFS, voiceless -20.5 dBFS, 2 gaps) | PASS `loudness_ok` (-12.5 LUFS, peak -1.2 dBFS) |
| 823 | PLGSvGqLyc4 | NEWS | growth:viral_masked-wolf_astronaut-in-the-ocean | PASS `bgm_present` (voiced -16.6 dBFS, voiceless -16.0 dBFS, 1 gap 21.56–22.08 s @ -16.0) | PASS `loudness_ok` (-14.0 LUFS, peak -1.4 dBFS) |
| 824 | PMMg1GbeJHA | AUTOS | growth:comedy_kazumi-totaka_mii-channel-theme | PASS `bgm_present` (voiced -18.0 dBFS, voiceless -18.1 dBFS, 2 gaps) | FAIL `true_peak_too_high` (-14.8 LUFS, peak -0.2 dBFS) |
| 825 | VLhyp-XEJxs | AUTOS | growth:sports_interworld_metamorphosis | UNMEAS `bgm_unmeasured` (speech tiles render, no silence interval) | PASS `loudness_ok` (-14.2 LUFS, peak -1.2 dBFS) |
| 841 | Pfxp6mysc90 | SPORTS | growth:space_ludovico-einaudi_experience | PASS `bgm_present` (voiced -17.5 dBFS, voiceless -13.9 dBFS, 1 gap 4.20–7.10 s @ -13.9) | PASS `loudness_ok` (-13.6 LUFS, peak -1.3 dBFS) |
| 861 | bhw0Cxw9WGs | AUTOS | growth:pets_kevin-macleod_life-of-riley | UNMEAS `bgm_unmeasured` (speech tiles render, no silence interval) | PASS `loudness_ok` (-13.4 LUFS, peak -1.2 dBFS) |

Durations (ffprobe): 801 18.62 s, 802 29.23 s, 803 21.45 s,
804 20.78 s, 821 39.43 s, 822 25.40 s, 823 43.93 s, 824 23.03 s,
825 14.88 s, 841 51.06 s, 861 22.66 s. No silence intervals in any
render (ebur128 scan). Render SHA-256 (first 16): 801
`60a3b2de18a3ebe5`, 802 `5a2fab1154f52624`, 803 `7b3bf606a718d237`,
804 `44e190d5da22304f`, 821 `294176d8cf0c1e4a`, 822
`abdf48fa5ad7b48b`, 823 `fa18e108755242e0`, 824 `4ccaa13abed3440b`,
825 `1d4a46fea53c0593`, 841 `fefcc208160cd28d`, 861
`e70734f32acc1146`.

## Summary + delta vs run 1 (TASK-VYR-044, 2026-11-25)

- **BGM: present 8/11, unmeasured 3/11 (803/825/861), absent 0/11.**
  Unmeasured = speech tiles the whole render and no silence interval
  exists, so the bed cannot be separated from the voice by this
  method — fail-closed, NOT a pass. 861's human no-BGM finding
  (watch) is therefore neither confirmed nor refuted by this
  measurement; it stands as the human verdict (same as run 1).
- **Loudness: pass 8/11, fail 3/11 (803/804/824 — true peak over the
  -1.0 dBFS bar: -0.6 / -0.9 / -0.2 dBFS).** Integrated LUFS is in
  range on all 11 (-12.5…-14.8, pipeline target -14).
- **Both gates pass: 6/11 (801, 802, 821, 822, 823, 841).**
- **Delta vs TASK-VYR-044: exactly one verdict changed — job 802 BGM
  `bgm_unmeasured` → `bgm_present`.** Mechanism verified first-hand:
  802's `.ass` has 18 `AntonBold` speech events + 2 `AntonFraming`
  hook events. Run 1 counted all 20 as speech (its results JSON:
  `ass_speech_events: 20, ass_hook_events: 0`), so the speech union
  tiled the render and no gap existed. Run 2 applies the current
  `speech_events()` hook exclusion (18 speech events), exposing the
  tail gap 27.28–29.23 s, which measures -25.7 dBFS (above the
  -45 floor, no silence interval) → bed energy present. All other
  10 renders: identical BGM and loudness verdicts run-over-run
  (row-for-row compared against `/tmp/vyr044_results.json`), and
  the render files are unchanged (mtimes 2026-11-18…21, sizes
  identical to the run-1 era). No render was re-made between runs;
  the batch state is stable.
- The three true-peak failures are a level fix on re-render, not
  waivable without noting. Nothing in this table releases any
  render: caption-track and watermark columns are out of scope here
  (run 1 filed watermark absent on all 11; caption gate needs the
  vision sampler) — the pool stays HELD and unlisted.

## Verification note (stated plainly)

- Batch definition, gate thresholds, host state, and every number
  above: verified first-hand this run (bridge `run_shell` on
  VyralX-Server; agent's own `held_render_qa`/`media_quality` code;
  ffprobe; manifest reads before/after). No secret was read or
  printed (credentials/token/cookie files on the host were not
  touched). Read-only throughout: no DB writes, no renders
  modified, nothing uploaded or set public, loop stayed OFF.
- What this does NOT prove: bed identity (RMS ≠ which track),
  caption/watermark state, or that any render is releasable. The
  three `bgm_unmeasured` renders still owe a bed verdict by another
  method (e.g. human watch) if the coordinator wants one.

## States

- Implemented: YES — run-2 BGM + loudness verification executed live
  over all 11 held renders with the agent's own gates; this doc is
  the filed per-render evidence. (No code change in this task.)
- Tested: YES — live gate run on VyralX-Server, 11/11 renders
  measured; results JSON on the server; row-for-row delta vs run 1
  (TASK-VYR-044) computed and the single change (802) explained
  from first-hand `.ass` evidence.
- Merged: NO (this PR awaits peer review; never merge own PR).
- Deployed: NO (nothing to deploy; driver ran from /tmp on the
  server; host untouched).
- Production-verified: PARTIAL — the held batch's BGM/loudness state
  is now measured on the live host, but the pool remains HELD:
  3 true-peak failures, 3 BGM-unmeasured, and the run-1
  caption/watermark findings still block any release. No render
  went public; all 11 remain HELD/unlisted.

— Muse 9
