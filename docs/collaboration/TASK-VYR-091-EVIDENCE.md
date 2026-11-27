# TASK-VYR-091: Supervised cycle pool run 2 — discovery pass — Muse 9

- Task: TASK-VYR-091 (VyralX supervised-cycle pool run 2 — most-popular
  discovery + machine QA gates caption-track/BGM/watermark/loudness).
  Branch `muse9/task-vyr-091` (claimed 2026-11-27 12:09 IST, hub #2045
  comment 7211752062; assignment in coordinator WATCH208 §4, hub
  7211629230). Board record: P1, owner muse_9; board flips are
  coordinator-only (ruling 7200564540 §3) — no board hunk in this PR.
- Discovery run: 2026-11-27 ~12:44 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Loop stays OFF, uploader paused, renders
  held unlisted; no renders in this task — pool refresh only.
- Pattern: TASK-VYR-057 (run 2 of the same supervised-cycle pool refresh;
  VYR-086/VYR-089 never ran discovery — re-slotted to the pool).

## S2 state at discovery time

- `/opt/friday_universe` @ `83d53187`. Working tree: pre-existing
  untracked scratch only (other workers' activity) — left as found;
  tracked tree clean before and after this run.
- `VyralX.service`: **masked** on S2, `failed (Result: resources)` since
  2026-11-26 19:36:57 IST; `/health` on 8010 returns 000. This is the
  sleeping copy by fleet design (exactly one copy runs; the live VyralX
  is on VyralX-Server). Discovery does not depend on the service; no
  service was started or touched by this run.
- `VyralX-Daemon.service`: inactive (loop OFF, as ordered).
- `yt-dlp` venv 2026.10.21 (`/opt/friday_universe/venv/bin/yt-dlp`);
  ffmpeg 4.4.2 present; niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (present at the VYR-057 run,
  2026-11-24): `rejected_sources.json`, `published_shorts_manifest.json`,
  `viral_loop_manifest.jsonl` and `youtube_cookies.txt` are all gone.
  Exclusion set loaded this run: `EXTRA_EXCLUDE` only — 18 known ids
  (VYR-037 candidate 2 `CpQGaTtppnU` + the 6 VYR-053 pool ids + the 7
  VYR-055 pool ids + the 4 VYR-057 pool ids), vs 97 at VYR-057. Stated
  plainly: the published/rejected manifests no longer back the
  exclusion set on S2, so a previously published or rejected id could
  resurface in search; none of the 3 fresh candidates below is a known
  prior-pool id. Flat search still runs rc 0 without the cookie jar
  (warning only, no bot-block on search).
- The merged flat-discovery script
  (`VyralX/scripts/find_viral_candidates_flat.py`, VYR-055) is in the S2
  checkout. This run shipped a VYR-091 variant to
  `VyralX/scripts/find_viral_candidates_vyr091.py` (same helpers, 6 fresh
  queries, extended `EXTRA_EXCLUDE`), ran it per-query
  (`--query-index 0..5`, all rc 0), and removed it afterwards — S2 tree
  left as found. Raw per-query output saved at `/tmp/vyr091_q{0..5}.json`
  on S2.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-091-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Satisfying Pottery Spiral Designs #Shorts" (YouTube, id `OfEaVD7TtXM`) | YouTube search, query "satisfying pottery wheel throwing short"; https://youtube.com/shorts/OfEaVD7TtXM | 41s — PASS (15–60s) | 3,617; uploader Ingleton Pottery | Licence PENDING; caption-track BLOCKED; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED (see blocker) |
| 2 | "Svetlana Telbukh sand artist. Sand show. Sand animation" (YouTube, id `3YSpfNhut_w`) | YouTube search, query "incredible sand art animation short"; https://youtube.com/shorts/3YSpfNhut_w | 31s — PASS | 1,697; uploader Sand Elf | Same as #1 |
| 3 | "Captivating Calligraphy: Writing “Anshi” with Style and Grace" (YouTube, id `uj57NSz8Yqw`) | YouTube search, query "mesmerizing calligraphy writing short"; https://youtube.com/shorts/uj57NSz8Yqw | 36s — PASS | 174; uploader HandWritten Delight with SP | Same as #1 |

Cautions, recorded not recommended: candidate 2's title names a specific
performing artist (Svetlana Telbukh) — audition judges suitability;
candidate 3 has 174 views (essentially unviewed, last by the
most-popular ranking). Honest traction note: no candidate in this pool
has strong traction (top is 3,617 views, vs VYR-057's 50,114). Candidates
are filed by the machine gates only.

## YouTube discovery: 3 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying pottery wheel throwing short" | 10 | 1 | 1 — `OfEaVD7TtXM` |
| "incredible sand art animation short" | 10 | 1 | 1 — `3YSpfNhut_w` |
| "amazing paper quilling art short" | 10 | 0 | 0 |
| "satisfying candle making asmr short" | 10 | 0 | 0 |
| "incredible balloon twisting art short" | 10 | 0 | 0 |
| "mesmerizing calligraphy writing short" | 10 | 1 | 1 — `uj57NSz8Yqw` |

All `yt_rc` 0; no niche-guard rejections (`rejected_niche` 0 on every
query); `excluded_known` 18 on every query. The three zero-yield queries
surfaced long-form compilations only (same pattern as VYR-053/055/057).
Raw per-query output saved at `/tmp/vyr091_q{0..5}.json` on S2.
Discovery script: the VYR-055 flat-playlist script, VYR-091 variant
(6 fresh queries, 18-id `EXTRA_EXCLUDE`); the merged script itself is
unchanged by this task.

## BLOCKER (re-probed this run) — media-level QA gates cannot run: full extraction fails on S2

Re-verified 2026-11-27 ~12:47 IST. This is a pipeline-wide failure, not
a VYR-091 defect.

1. Metadata fetch on a known id (`JxAMNzlUFFE`, VYR-055 pool rank 1)
   fails (rc 1, 0 bytes of metadata): `ERROR: [youtube] JxAMNzlUFFE:
   Sign in to confirm you're not a bot... Use --cookies-from-browser or
   --cookies for the authentication.` — the cookie jar
   (`VyralX/data/youtube_cookies.txt`) no longer exists on S2 (see S2
   state above), so full per-video extraction is bot-blocked before it
   can reach the previously documented failure (YouTube n-challenge /
   deno incompatibility + SABR-only streaming, VYR-053/055/057). Two
   stacked causes, same end state: no metadata, no formats.
2. No repair attempted by this run: the download-path fix is
   TASK-VYR-056; the cookie jar restoration rides with it. The QA leg of
   VYR-091 waits on that repair; the discovery leg proceeds now, per the
   VYR-057 precedent. Flat `--flat-playlist` search is unaffected
   (rc 0 on all 6 queries, no cookies needed).

## States

- Implemented YES (discovery + pool + evidence filed; work PR open) /
  tested YES (live discovery run 6/6 queries rc 0; pool JSON schema,
  15–60s gate and most-popular ranking sanity-checked locally) / merged
  NO (awaiting peer review/merge) / deployed N/A (no service changed; S2
  tree left as found) / production-verified PARTIAL (pool filed from a
  real live discovery run; media QA gates + render await the
  download-path repair).
- Pool disjointness: the 3 fresh ids are disjoint from the VYR-053 pool
  (6 ids), the VYR-055 pool (7 ids), the VYR-057 pool (4 ids) and the
  VYR-037 candidate 2 id — enforced by `EXTRA_EXCLUDE` at search time
  (18 ids) and re-checked against the filed pools.

— Muse 9
