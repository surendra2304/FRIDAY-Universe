# TASK-VYR-067 — CHECKPOINT 2 — discovery complete, top-3 formed with caveat — Muse 20

- Task: TASK-VYR-067 (P2, VyralX: reference-video style-guide editing for renders).
- Claimed 2026-11-27 ~11:35 IST (hub #2045 comment 7211172252). Branch
  `muse20/task-vyr-067` @ `36be5b0f` (checkpoint 1; this commit adds
  checkpoint 2). Base `83d53187`; main has since moved — rebase owed at
  work-PR time, not now.
- Board on live main `a284c307` (blob `14a6baf6`, verified first-hand this
  run): VYR-067 AVAILABLE / muse_20 / branch null / pr null. The CLAIMED
  flip rides the coordinator board PR (ruling 7200564540 §3 — coordinator-only
  flips; no board hunk in my diff).

## Discovery — complete (attempts 1–3, S2, read-only)

- Method: VYR-089 replication — S2 flat-playlist via bridge `run_shell`
  (standing clearance 7200564540), raw yt-dlp, ytsearch10, 10 results per
  query, 15–60s + fresh + VYR-065 banned-niche guard
  (`VyralX/app/services/niche_guard.py` check_query + filter_candidates,
  used exactly). 18 queries, 180 results, 0 guard rejections at query or
  candidate level.
- Attempt 1 (~15:28 IST, 6 queries): 1 passing video.
  Attempts 2–3 (~16:40–16:50 IST, 12 new Shorts-weighted queries): 4 + 4
  hits, all duplicates of attempt 1–2 finds except one new upload.
  Full raw output: hidden working notes (attempts 2–3 record in the
  self-check log; attempt 1 in the prior self-check record).
- Bridge verified working this run: `list-tools` exit 0; read-only
  `run_shell` probes exit 0 on S2. The fleet-wide outage premise from
  checkpoint 1 is corrected (WATCH210 §2; my own probes confirm).

## Locate leg — RESOLVED: cookie jar + ledgers do NOT exist live on S2

- Canonical paths are relative to the run cwd (`./data/...`, config.py:28
  `data_dir = Path("./data")`, `youtube_cookies_file =
  Path("./data/youtube_cookies.txt")`).
- `/opt/friday_universe/data/` holds only backups/, storage/,
  temp_thumbs/, test_intelx.db, worker-heartbeat.json — no cookie jar, no
  rejected_sources.json, no published_shorts_manifest.json, no
  viral_loop_manifest.jsonl. `/opt/friday_universe/VyralX/data/` absent.
- Fleet-wide find (/opt + /home/ubuntu + /srv, maxdepth 5): the only cookie
  file is `/opt/quarantine-2026-11-26/tmp-old/youtube_cookies.txt.tar.gz`
  (quarantined Nov 26). NOT used — quarantined credentials are not restored
  without a ruling. No VYR-089 doc names a cookie path.
- Consequence: all three attempts ran WITHOUT cookies; EXCLUDED_KNOWN = 0,
  so the fresh gate is unverified against the ledgers. Recorded as a
  standing deviation.

## Top-3 by views (unique passing videos, live view counts at run time)

1. `mGwNcInn5LA` — "Cinematic Trailer Video (Kinemaster Edit)" — 33s —
   493,787 views — Creativeajit —
   https://youtube.com/shorts/mGwNcInn5LA
2. `R5dyIHd_mKI` — "How to edit amazing cinematic trailer in capcut ||
   cinematic trailer tutorial in capcut #shorts" — 32s — 248,745 views —
   How To Edit — https://youtube.com/shorts/R5dyIHd_mKI
3. `jVPcLcxUtx4` — same title as #2, same channel (How To Edit) — 29s —
   2,031 views — https://youtube.com/shorts/jVPcLcxUtx4

## Caveat — read before accepting the top-3

- Only 2 distinct tutorials: #2 and #3 are the same tutorial, different
  uploads. The editing-tutorial niche is long-form heavy: 3/180 unique
  results pass the 15–60s gate.
- Decision point for Muse (not decided unilaterally): (a) accept this
  top-3 with the caveat recorded; (b) widen the query set further
  (diminishing returns — attempts 2–3 added zero new uniques); (c) rule on
  the quarantined cookie jar (restore vs stay without cookies — cookied
  results may differ).

## Owed next (not claimed done here)

- Style-guide extraction: view the 3 reference videos and extract cuts,
  B-roll, captions, music — evidenced per video, not asserted.
- A new render edited against the guide (acceptance: pauses cut,
  word-by-word captions, B-roll matched to spoken words, clean voice +
  SFX; steps rest on the reel's on-screen text; spoken Telugu narration
  not recovered — named gap, carries forward).

## Five states

implemented NO / tested NO / merged NO / deployed NO / production-verified NO.
Checkpoint 2 is discovery evidence only; the style guide and the render
are owed.

— Muse 20, 2026-11-27 ~16:52 IST
