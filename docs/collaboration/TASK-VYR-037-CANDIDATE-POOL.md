# TASK-VYR-037: Next supervised-cycle candidate pool — discovery pass 1

- Task: TASK-VYR-037 (pool-7 item iii). Branch `muse5/task-vyr-037-candidate-pool`
  (base main `047c99b7`). Board AVAILABLE → CLAIMED flip rides in the work PR
  (new standing orders, coordinator comment 7077319027).
- Discovery run: 2026-11-22 ~17:15–17:26 IST, on U2 via bridge `run_shell` on
  Server 2. Read-only probes only. Loop stays OFF, uploader paused, renders held
  unlisted; nothing in this pool uploads until a render passes the coordinator's
  end-to-end browser watch.
- Discovery re-run: 2026-11-22 ~19:20–19:35 IST, same path (fixed-script
  equivalent: venv yt-dlp + cookies + `ytsearch10` + Python-side 15–60s filter,
  exclusions applied). All 4 scripted queries + the `#shorts` variant. Pool
  grows 1 → 2 candidates (see below).

## U2 state at discovery time

- `/opt/friday_universe` @ `03378ba4` (VYR-032 fix), working tree clean.
- `vyralx-daemon`: inactive (loop OFF, as ordered).
- `VyralX/data/viral_loop_state.json`: 11 cycles completed, last cycle
  2026-11-21T01:27:06Z — cycle 11: pool 106, attempts 24, produced 1,
  `held_publish_jobs: [861]`.
- `VyralX/data/published_shorts_manifest.json`: 11 entries; latest is the VYR-034
  re-render `sOZrJUkCLYU` → `tNoyCbR9uek` (private draft, 2026-11-21T16:24:39Z).
- `VyralX/data/viral_loop_manifest.jsonl`: 11 HELD renders (cycles 2/5/6/11,
  `yt_id` null) — prior-cycle outputs awaiting the coordinator's watch decision.
  They are NOT new candidates.
- `VyralX/data/remix_review_queue.jsonl`: 2 lines, both PENDING_REVIEW, same
  provenance record (see candidate 1 — duplicate queue entries).

## Candidate pool (pass 1)

| # | Candidate | Source | Category | Machine QA gate | Result |
|---|-----------|--------|----------|-----------------|--------|
| 1 | "Gradient Sun" (NASA) | remix queue, record `1e06e9e0b37a` (queue ids `remix-1e06e9e0b37a-4820ed` 2026-11-15T07:46:37Z and `remix-1e06e9e0b37a-c4f678` 2026-11-15T08:41:59Z — same record twice, deduped to one candidate) | SPACE | Licence is public-domain / CC0, allows derivatives + commercial use | PASS — provenance on file: "Public Domain — NASA (U.S. Government work)" |
| 1 | same | `http://images-assets.nasa.gov/video/GSFC_20121018_Gradient_m11112_Sun.en/GSFC_20121018_Gradient_m11112_Sun.en~small.mp4` | SPACE | Media reachable | PASS — `curl -I` 2026-11-22 returns HTTP 301 to the https asset |
| 1 | same | — | SPACE | Duration 15–60s (provenance `duration_seconds` is null) | PENDING — ffprobe at audition time (`ffprobe` present on U2) |
| 1 | same | — | SPACE | Audition gates: `source_captioned` / `watermark_visible` / `source_has_no_narration` / `script_unverifiable` / `vision_unavailable` | PENDING — run at supervised-cycle audition/render time, not yet run |
| 2 | "Mw2 Newest TrickShot The Barrel Roll - Tutorial" (YouTube, id `CpQGaTtppnU`) | YouTube search, query "insane human precision trickshot silent" (re-run 2026-11-22 ~19:24 IST); url https://youtube.com/shorts/CpQGaTtppnU | TRICKSHOT | Shorts-length discovery (15–60s) | PASS — 23s |
| 2 | same | — | TRICKSHOT | Licence / source terms | PENDING — not yet checked; check at audition (YouTube standard licence expected) |
| 2 | same | — | TRICKSHOT | Audition gates: `source_captioned` / `watermark_visible` / `source_has_no_narration` / `script_unverifiable` / `vision_unavailable` | PENDING — run at supervised-cycle audition/render time, not yet run |
| 2 | same — note | — | — | — | Caution, recorded not recommended: 2011 footage, 1,310 views, gaming tutorial. Audition judges suitability; candidate by the machine gate only. |
| — | YouTube search leg (4 scripted queries) | `VyralX/scripts/find_viral_candidates.py` | — | Shorts-length discovery (15–60s) | 0 fresh candidates this pass — see below |

## YouTube discovery: 0 fresh candidates — evidence

1. Shipped `find_viral_candidates.py` fails as-is on U2: `FileNotFoundError:
   'yt-dlp'` — bare `yt-dlp` is not on PATH under system python3 (it lives in
   the repo venv at `venv/bin/yt-dlp`).
2. With venv PATH but no `--cookies`, the search returns `[]`: YouTube answers
   "Sign in to confirm you're not a bot" (same for a direct known video id).
3. With `--cookies VyralX/data/youtube_cookies.txt` (the pipeline's own jar,
   `VyralX/app/services/ytdlp_support.py:cookies_file()`), search works — but
   `ytsearch2` + `--match-filter "duration <= 60 & duration >= 15"` returns 0
   for all 4 queries.
4. `ytsearch10` on query 1 ("oddly satisfying visual craft silent") returns 10
   results, 0 Shorts-length: durations 249–29866s. YouTube search surfaces
   long-form compilations for these queries, not Shorts.
5. A `#shorts` query variant timed out once at 50s; not retried this pass.

Fix in this commit (`VyralX/scripts/find_viral_candidates.py`): resolve yt-dlp
(PATH, else `<repo>/venv/bin/yt-dlp`), pass `--cookies
<repo>/VyralX/data/youtube_cookies.txt` when present, use `ytsearch10` with a
Python-side 15–60s filter, dedupe. Each piece validated on U2 this run; a full
end-to-end re-run is the next step.

## Discovery re-run (fixed script) — 2026-11-22 ~19:20–19:35 IST

Same path (bridge `run_shell` on S2 → ssh U2), one call per query; the
fixed-script equivalent (venv yt-dlp + `--cookies
VyralX/data/youtube_cookies.txt` + `--dump-json ytsearch10:<query>` +
Python-side 15–60s filter). Exclusion sets applied: 82 known ids
(rejected 50 + published 11 + held 11 + overlaps). All `yt_rc` 0. Raw
per-query JSON saved at `/tmp/vyr037_rerun_q{0,1,2,3,shorts}.txt`. Bridge
SSE read timed out twice on query 0 (retried, 3rd attempt succeeded);
queries 1–3 + `#shorts` variant each completed first try.

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "oddly satisfying visual craft silent" | 10 | 0 | 0 |
| "insane human precision trickshot silent" | 10 | 1 | 1 — `CpQGaTtppnU` (23s, see candidate 2) |
| "mesmerizing soap cutting satisfying asmr" | 10 | 0 | 0 |
| "satisfying industrial loop machine silent" | 10 | 0 | 0 |
| "oddly satisfying visual craft silent #shorts" | 10 | 0 | 0 |

Finding: YouTube search keeps surfacing long-form compilations for these
queries even with the fixed script and the `#shorts` variant — 1 fresh
Shorts-length candidate from 50 results. The YouTube leg is exhausted for
these queries; further growth needs different sources (remix queue,
NASA/other public-domain stock) or different query angles, not more of the
same searches.

## Exclusion sets (applied to every fresh id)

- `VyralX/data/rejected_sources.json`: 50 ids.
- Published manifest: 11 entries (`video_id` + `yt_id`).
- Held loop manifest: 11 `video_id`s.

## Next

1. ~~Re-run the fixed discovery (all 4 queries, plus Shorts-oriented queries) and
   grow the pool.~~ DONE 2026-11-22 ~19:35 IST — pool 1 → 2 (candidate 2,
   `CpQGaTtppnU`); YouTube leg exhausted for these queries (see re-run section).
2. Audition gates per candidate at the next supervised cycle (caption, watermark,
   narration, script, vision) — pass/fail recorded here.
3. Work PR after rebase onto current main: this doc + script fix + board
   AVAILABLE → CLAIMED flip + offline test for the discovery helpers (new test
   file joins the contracts workflow list in the same PR, per standing orders).
