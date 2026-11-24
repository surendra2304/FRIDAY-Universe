# TASK-VYR-055: Next supervised-cycle candidate pool refresh — discovery pass

- Task: TASK-VYR-055 (VyralX next supervised-cycle candidate pool refresh —
  most-popular discovery + machine QA gates). Branch
  `muse5/task-vyr-055-candidate-pool` (claimed 2026-11-24 ~10:20 IST, hub
  comment 7122413602; base main `bc303ea0`, rebased onto current main before
  the work PR — see PR body for the head). Board AVAILABLE → CLAIMED flip
  rides in the work PR (standing orders).
- Discovery run: 2026-11-24 ~10:40–11:10 IST, on S2 via bridge `run_shell`
  on Server 2 (U2 deleted 2026-11-23; VyralX lives on S2). Loop stays OFF,
  uploader paused, renders held unlisted; no renders in this task — pool
  refresh only.
- Discovery checkpoint posted on hub #1483 as comment 7123033101 (~11:02 IST).

## S2 state at discovery time

- `/opt/friday_universe` @ `bc303ea0`, checked out on
  `muse5/task-vyr-055-candidate-pool`, working tree clean (only pre-existing
  untracked scratch).
- `VyralX.service`: active/running, PID 611266; /health 200, /ready 200.
- `VyralX-Daemon.service`: inactive (loop OFF, as ordered).
- `yt-dlp` venv 2026.10.21 (`/opt/friday_universe/venv/bin/yt-dlp`; system
  copy same version); cookies `VyralX/data/youtube_cookies.txt` present
  (Nov 23 19:59); ffmpeg/ffprobe 4.4.2 present; deno 2.9.8 system.
- Exclusion sets loaded on S2 this run: `rejected_sources.json` (51 ids,
  incl. `1sYGq2no4Tk`, the VYR-040 watermark rejection) +
  `published_shorts_manifest.json` (11) + `viral_loop_manifest.jsonl` (11)
  + `CpQGaTtppnU` (VYR-037 pool candidate 2) = **84 known ids excluded**.

## Candidate pool (pass 1) — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-055-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Domino Effect V10 The largest domino simulation on Real Footage" (YouTube, id `JxAMNzlUFFE`) | YouTube search, query "amazing domino art chain reaction short"; https://youtube.com/shorts/JxAMNzlUFFE | 49s — PASS (15–60s) | 116,695,080; uploader Idan David Animations | Licence PENDING; caption-track BLOCKED; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED (see blocker) |
| 2 | "Domino Effect - The largest domino simulation on Real Footage V4" (YouTube, id `5uHUVyy3rNw`) | Same query | 47s — PASS | 66,108,212; uploader Domino effect simulation Dude | Same as #1 |
| 3 | "epic basketball trickshot" (YouTube, id `Z-k4pfVfz_g`) | YouTube search, query "epic basketball trick shot short"; https://youtube.com/shorts/Z-k4pfVfz_g | 15s — PASS (lower boundary) | 74,048; uploader KickThePj | Same as #1 |
| 4 | "Epic basketball trick shot will totally blow your mind #Shorts" (YouTube, id `XwMLwKG5WrY`) | Same query | 31s — PASS | 1,752; uploader Rumble Viral | Same as #1 |
| 5 | "5 confusing domino effects (@MrJ01 Chain Reaction Screenlink contest entry)" (YouTube, id `0nb5q5UYjHU`) | Domino query | 26s — PASS | 1,206; uploader jh domino | Same as #1 |
| 6 | "Amazing Domino Trick" (YouTube, id `0QYrrGrwpzs`) | Domino query | 38s — PASS | 636; uploader Art Dominoes | Same as #1 |
| 7 | "Rainbow Soap Carving \| Satisfying ASMR #asmrvideo" (YouTube, id `H99NdQZw_DE`) | YouTube search, query "oddly satisfying soap carving short"; https://youtube.com/shorts/H99NdQZw_DE | 29s — PASS | 4; uploader FUNtertainment 🎉 | Same as #1 |

Cautions, recorded not recommended: candidates 1–2 are labelled
*simulations* on real footage, not real footage — audition judges
suitability; candidate 7 has 4 views (essentially unviewed, last by the
most-popular ranking). Candidates are filed by the machine gates only.

## YouTube discovery: 7 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "most satisfying video ever short" | 10 | 0 | 0 |
| "incredible street magic revealed short" | 10 | 0 | 0 |
| "satisfying hydraulic press crushing short" | 10 | 0 | 0 |
| "amazing domino art chain reaction short" | 10 | 4 | 4 — `JxAMNzlUFFE`, `5uHUVyy3rNw`, `0nb5q5UYjHU`, `0QYrrGrwpzs` |
| "oddly satisfying soap carving short" | 10 | 1 | 1 — `H99NdQZw_DE` |
| "epic basketball trick shot short" | 10 | 2 | 2 — `Z-k4pfVfz_g`, `XwMLwKG5WrY` |

All `yt_rc` 0. Best yield yet (VYR-037: 1 fresh from 50 results; VYR-040:
1 from 50). The three zero-yield queries again surfaced long-form
compilations only. Raw per-query output saved at `/tmp/vyr055_q{0..5}.txt`
on the run host. Script: `VyralX/scripts/find_viral_candidates_flat.py`
(new in this PR — see below).

## BLOCKER — media-level QA gates cannot run: yt-dlp download broken on S2

Verified 2026-11-24 ~10:40–11:35 IST. This is a pipeline-wide failure, not
a VYR-055 defect: the VyralX download path that worked for VYR-040's cycle
on 2026-11-23 now fails for every video and every client tried.

1. Full (non-flat) search hangs: `ytsearch10` timed out at 150s and again
   at 280s with zero results (bridge read retries aside, the yt-dlp process
   itself never returned; no stray yt-dlp processes afterwards).
2. Known-id metadata fetch fails (rc 1): YouTube's n-challenge cannot be
   solved — `[youtube] [jsc] Error solving n challenge request using "deno"
   provider: Error running deno process (returncode: 1): Uncaught (in
   promise) TypeError: a.addOnDisposeCallback is not a function` (deno
   2.9.8 vs yt-dlp 2026.10.21). Followed by `n challenge solving failed:
   Some formats may be missing` and `Some web_embedded client https formats
   have been skipped as they are missing a URL. YouTube may have enabled
   the SABR-only streaming experiment for your account` (cf. yt-dlp
   #12482). End state: `Only images are available for download` — zero
   formats, download impossible.
3. Repair attempts, all on S2, all failed:
   - `--js-runtimes node` (node v20.20.2 present): ignored, still the deno
     provider.
   - `player_client=android`: skips cookies, no formats. `player_client=ios`:
     skips cookies, no formats. `player_client=tv`: search entries error
     "The page needs to be reloaded". `player_client=web_safari`: same
     n-challenge failure.
   - No cookies at all: bot-blocked ("Sign in to confirm you're not a
     bot").
   - `pip install --dry-run --upgrade yt-dlp`: 2026.10.21 already latest —
     no upgrade fix available.
   - Deno 2.2.0 installed alongside (downloaded from GitHub releases to
     `/home/ubuntu/deno-2.2.0`, system deno untouched; backup of the
     2.9.8 binary at `/tmp/deno-2.9.8.bak`): with
     `--js-runtimes deno:/home/ubuntu/deno-2.2.0/deno` the deno traceback
     disappears but the download still fails with no formats — the SABR-only
     gate, not just the Deno crash, blocks downloads.
   - In-place Deno downgrade: blocked — `/usr/local/bin/deno` is
     root-owned, bridge shell runs as ubuntu.
4. Workarounds that work: `--flat-playlist` search (rc 0, fast) — search
   listing needs no per-video extraction, so discovery completed. The
   pipeline's own `ytdlp_support.py` has no player-client / PO-token
   fallback (cookies only), so it hits the same wall.
5. Caption-track via YouTube's timedtext list endpoint: empty response
   (0 bytes) for all 7 ids, with and without the cookie jar — also
   blocked. Thumbnail fetch via `i.ytimg.com` still works (hq720 thumbs
   for the top 3 saved at `/tmp/vyr055_thumb_*.jpg`), but a single poster
   frame is not a watermark gate, so no watermark verdict is claimed.

Consequence for the gates: duration (15–60s) PASS for all 7 candidates;
licence, caption-track count, BGM presence, watermark and loudness are
PENDING/BLOCKED, recorded as such in the pool file — not passed, not
failed. They must run at the supervised cycle once the download path is
repaired. Repair options for the coordinator (no unilateral move made):
fresh YouTube cookie/session, a PO-token provider decision, waiting out
the SABR experiment rollout, or an upstream yt-dlp/Deno fix. VYR-052
(cycle 3) will hit the same wall until one lands.

## What this PR contains

- This doc (`docs/collaboration/TASK-VYR-055-CANDIDATE-POOL.md`).
- `docs/collaboration/TASK-VYR-055-POOL.json`: machine-readable pool.
- `VyralX/scripts/find_viral_candidates_flat.py`: flat-playlist discovery
  script (the VYR-037 script's approach, adapted: `--flat-playlist`
  bypasses the broken per-video extraction; same venv yt-dlp resolution,
  cookies, `ytsearch10`, Python-side 15–60s filter, exclusions, most-
  popular ranking by view_count).
- `VyralX/tests/test_vyr055_discovery_helpers.py`: offline tests for the
  flat-script helpers (stdlib-only, stub yt-dlp, no network), wired into
  the contracts workflow list (`owner-workflows.yml`, VyralX step).
- Board AVAILABLE → CLAIMED flip for TASK-VYR-055.

## Next

1. Repair the S2 YouTube download path (coordinator decision — see
   blocker section).
2. At the supervised cycle (VYR-052): run the four media gates per
   candidate (caption-track count, BGM presence, watermark, loudness) +
   licence check; record pass/fail here; render from the top passing
   candidate, held unlisted, loop OFF, uploader paused.
3. Rejections, if any, go in S2 `VyralX/data/rejected_sources.json` as
   before (currently 51 ids).
