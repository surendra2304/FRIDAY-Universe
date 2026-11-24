# TASK-VYR-058 — Reddit sourcing adapter for the discovery pipeline

- **Task:** TASK-VYR-058 — "VyralX: Reddit sourcing adapter for the discovery pipeline"
- **Branch:** `muse7/task-vyr-058-reddit-sourcing` from main `b0276946`
- **Claim:** hub issue #1483, comment 7143388084 (Muse 7, 2026-11-25 ~01:55 IST)
- **Status:** implemented + tested (repo-side). Merged: NO. Deployed: NO.
  Production-verified: NO — live leg held under the owner stop order
  (see "Still gated" below).

## Acceptance

> Discovery can ingest Reddit-sourced (subreddit) candidates through the
> same machine-QA gates as YouTube candidates.

## What was verified first-hand (repo at `b0276946`)

- **Board record:** TASK-VYR-058, status AVAILABLE, owner null, P2
  (coordinator calls it P1 in watch056), acceptance as above; evidence
  cites GAP-LIST.md section 2, TASK-VYR-REDDIT (IG package audit gap
  B113). Note: `GAP-LIST.md` itself is **not in the repo** at this
  commit (no file matches; no `TASK-VYR-REDDIT` / `B113` reference
  outside the board record and the IG3-VYR-03 test header), so the
  board record is the source of truth for the acceptance.
- **YouTube candidate flow:** `VyralX/app/services/viral_discovery.py`
  — `discover_candidates` / `discover_candidates_api` build
  `Candidate` objects; the discovery gates live in `_accept`
  (comedy lane only, duration window, minimum views, reuse-licence
  policy, dedup/exclude) with ranking by `score_candidate`. The
  API fallback `youtube_api_discovery.discover_via_api` applies the
  same `_accept` with a COMEDY lane fallback and refuses the pool
  outright under `reuse_licensed` (no licence proof in the API).
  Downstream, `viral_loop.run_cycle` merges the trending + API pools
  into one ranked pool, auditions each candidate (VYR-020 two-pass
  speech routing), and production applies the five TASK-VYR-014
  quality gates (event-arc/static-scene, vision grounding,
  consistency, hook/payoff structure, narration fit).
- **Prior Reddit work:** `app/services/reddit_trends.py`
  (TASK-IG3-VYR-03, cluster B113) already sources Reddit *story*
  self-posts into briefs — but nothing fed Reddit posts into the
  *video discovery pipeline*. That is the gap VYR-058 closes.

## What shipped

| File | Change |
|---|---|
| `VyralX/app/services/reddit_discovery.py` | **New.** The adapter (see below). |
| `VyralX/app/services/viral_discovery.py` | `Candidate` gains six optional provenance fields (`source_platform`, `source_subreddit`, `source_post_id`, `source_url`, `reddit_score`, `reddit_comments`, all defaulted; YouTube candidates keep `source_platform="youtube"`) and `to_dict()` carries them. No existing construction site changes (all use kwargs). |
| `VyralX/app/services/reddit_trends.py` | `_normalise_post` additionally keeps `link_url` (the post's external link; previously dropped). Additive only; IG3-VYR-03 tests unaffected. |
| `VyralX/app/config.py` | `viral_reddit_subreddits` ("" = pool off, the default) and `viral_reddit_min_score` (0). |
| `VyralX/app/services/viral_loop.py` | `run_viral_loop_cycle` merges the Reddit pool into the same ranked pool as the trending/API lanes (`pool.setdefault`, same dedup), best-effort try/except like the lanes. |
| `VyralX/tests/test_vyr058_reddit_discovery.py` | **New.** 29 tests, fully offline (injected listing fetcher + metadata resolver). |
| `.github/workflows/friday-universe-ci.yml` | New test file added to the VyralX tier-1 pytest invocation (REL-068 contracts guard: a PR test must run in PR CI). |

## The adapter (`reddit_discovery.py`)

- **Input:** one subreddit, a comma-separated string, or an iterable
  of names. Empty = pool off: returns `[]` and makes no network call.
- **Selection:** `select_video_posts` picks non-stickied link posts
  pointing at YouTube videos (`watch?v=`, `youtu.be/`, `/shorts/`,
  `/embed/`), NSFW excluded by default, minimum Reddit score
  enforced, duplicates keep the higher-scored post. Deterministic
  ranking (score, comments, newest, post id). Every rejected post is
  reported with its reason (`self_post_no_video`, `stickied`,
  `nsfw`, `non_youtube_link`, `below_min_score`, `duplicate_video`).
  Self posts are **not** video candidates — the story lane
  (`reddit_trends`) already covers them.
- **Metadata:** resolved per video — YouTube Data API
  (`video_details`, same helper as the API discovery path) first,
  then yt-dlp metadata. A video whose metadata cannot be resolved is
  skipped as `metadata_unavailable`; views/duration/score are never
  invented, so a candidate that cannot prove it passes the gates
  never enters the pool.
- **Gates — the same ones:** every resolved video goes through
  `viral_discovery._accept` with the lane from `_lane_for` (COMEDY
  fallback, exactly the `discover_via_api` precedent) and the
  configured `viral_source_policy`. Under `reuse_licensed` the pool
  is refused before any fetch (no licence proof in a listing) —
  same as the API path.
- **Output:** `Candidate` objects with Reddit provenance attached,
  ranked by `score_candidate`; `discover_reddit_candidates_detailed`
  also returns a report counting received / video posts / accepted /
  skipped-by-reason, so a thin or empty pool is always explainable.
- **Failure modes:** a listing fetch failure raises `RuntimeError`
  (loud — a dead subreddit never masquerades as an empty one); a
  bad subreddit name is refused before any fetch (`ValueError`).

## Tests (local, this run)

Run from `VyralX/` with the repo venv (`.venv/bin/python -m pytest`).
New file: `tests/test_vyr058_reddit_discovery.py` —
**29 tests pass** (16 URL-extraction cases + 13 behaviour/loop
tests, ruff clean).

Regression files run in the same local invocation, all green:
`tests/test_ig3_vyr03_reddit_trends.py`,
`tests/test_viral_loop.py`, `tests/test_viral_loop_audition.py`,
`tests/test_vyr037_discovery_helpers.py`,
`tests/test_vyr055_discovery_helpers.py` — **78 passed** in the
five-file run (56 passed in the four-file re-run after the ruff
fix).

Full VyralX suite (local): two runs disagreed with each other,
which is itself the signal. Run 1 showed 15 failures across five
render files; run 2 showed **30 failures**, including
network/config-dependent tests (`test_mixkit` httpx errors,
`test_postgres_database` missing `psycopg2`,
`test_universe_nine_peers` peer config,
`test_ai_visuals` malformed-URL) and render tests failing with
`ffmpeg failed: Error sending frames to consumers: Resource
temporarily unavailable`. The four non-render failures
(`test_vyr009_compliance_gate` `ImportError: cannot import name
'_run' from 'app.services.viral_remix'`,
`test_universe_nine_peers`, `test_postgres_database`,
`test_ai_visuals`) were **reproduced identically on clean main
`b0276946`** (separate worktree, same venv) — pre-existing, not
caused by this change. The render failures pass in isolation and
together (52 passed) — full-suite ffmpeg-render contention on the
1.5-CPU VM. The PR's CI run is the authoritative check; the tier-1
CI set (which includes the two VYR-075 render files) is the gate
that must go green.

## Five states

| State | Value | Evidence |
|---|---|---|
| Implemented | YES | Adapter + provenance + config + loop wiring in the work PR. |
| Tested | YES | 15 new offline tests green locally (see above); CI run pending — see PR checks. |
| Merged | NO | Work PR open, awaiting Muse merge. Never merged by Muse 7. |
| Deployed | NO | Owner stop order in force; no deploy attempted. |
| Production-verified | NO | Live leg not run (see below). |

## Still gated (owed, not faked)

1. **Live Reddit fetch:** no live subreddit listing was fetched in
   this run (owner stop order freezes all live moves; no live probes).
   The adapter's live leg — real `r/<sub>/top.json` fetch, real
   Data-API metadata, one supervised loop cycle with
   `viral_reddit_subreddits` set — is owed once the freeze lifts.
2. **yt-dlp metadata leg:** the download break is NOT fixed
   (VYR-056 closed evidence-only, PR #1710). The adapter's yt-dlp
   fallback therefore usually returns nothing on this host; that
   surfaces as honest `metadata_unavailable` skips. The Data API
   leg is the working metadata path until yt-dlp is repaired.
3. **VyralX-Server route:** not granted; no server-side verification
   of the loop change.
4. **Autopilot script:** `scripts/run_viral_autopilot.py` (the
   second cycle driver) is NOT wired to the Reddit pool yet — the
   loop (`viral_loop.run_cycle`) is the wired consumer. Follow-up
   task, not claimed as done.
5. **Subreddit selection is operator configuration**, not code:
   which subreddits feed the pool is set via
   `viral_reddit_subreddits` (env / `.env`); no subreddit is
   hard-coded into the adapter.
