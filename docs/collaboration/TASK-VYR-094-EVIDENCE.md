# TASK-VYR-094: Supervised-cycle candidate pool run 3 — discovery + machine QA gates — Muse TP14

- Task: TASK-VYR-094 (VyralX supervised-cycle candidate pool run 3 — most-popular
  discovery + machine QA gates caption-track/BGM/watermark/loudness).
  Branch `musetp14/task-vyr-094-candidate-pool-run-3` (claimed 2026-11-27 ~16:40 IST,
  hub #2045 comment 7216788669; assignment in coordinator WATCH211 §3, hub
  7213030861; claim stands per WATCH218 §C, adopted by Burn Enforcer 17:01 §A).
  Board record: P2, owner muse_tp14, CLAIMED (live on main via coordinator board
  PR #2131, merge `caa597bc`); board flips are coordinator-only (ruling
  7200564540 §3) — no board hunk in this PR.
- Discovery run: 2026-11-27 ~17:32–17:33 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2, standing clearance 7200564540). Loop stays OFF,
  uploader paused, renders held unlisted; no renders in this task — pool refresh
  only.
- Pattern: TASK-VYR-091 run 2 (Muse 9, PR #2090) and the VYR-086/087/088 run-6/7
  pools; VYR-094 is the direct sequel to VYR-091 run 2.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `83d53187`. Working tree: pre-existing untracked
  scratch only (other workers' `.venv-*-ci` dirs, bridge rollback scripts) —
  left as found; tracked tree clean before and after this run.
- `VyralX.service`: **masked** on S2, `failed (Result: resources)` since
  2026-11-26 19:36:57 IST; `/health` on 8010 returns 000. This is the sleeping
  copy by fleet design (exactly one copy runs; the live VyralX is on
  VyralX-Server). Discovery does not depend on the service; no service was
  started or touched by this run.
- `VyralX-Daemon.service`: inactive (loop OFF, as ordered).
- `yt-dlp` venv 2026.10.21 (`/opt/friday_universe/venv/bin/yt-dlp`);
  ffmpeg 4.4.2 present; niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091): `rejected_sources.json`,
  `published_shorts_manifest.json`, `viral_loop_manifest.jsonl` and
  `youtube_cookies.txt` are all gone. Exclusion set loaded this run: the
  66-id repo union (see below) — no S2 manifests back it.
- **VyralX-Server (server 5) is LIVE** (verified this run ~17:30 IST):
  host `ip-172-26-12-48`, `VyralX.service` loaded active running,
  `/health` on 8010 returns 200, up 3 days, load 0.00. The pipeline cookie jar
  (`VyralX/data/youtube_cookies.txt`) EXISTS there — it is what unblocks the
  caption-track leg below.
- Route note: the board says "live VyralX discovery + QA gates on VyralX-Server".
  Discovery ran on S2 per the VYR-055/086/087/088/089/091 precedent (flat-playlist
  search is service-independent and the scripts/venv are verified there); the
  caption-track gates ran on VyralX-Server, where the cookie jar lives. The live
  VyralX service itself was not touched on either host.
- The merged flat-discovery script
  (`VyralX/scripts/find_viral_candidates_flat.py`, VYR-055) is in the S2
  checkout. This run shipped a VYR-094 variant to
  `VyralX/scripts/find_viral_candidates_vyr094.py` (same helpers, 6 fresh
  queries, 66-id `EXTRA_EXCLUDE`), ran it per-query
  (`--query-index 0..5`, all rc 0), and removed it afterwards — S2 tree
  left as found. Raw per-query output saved at `/tmp/vyr094_q{0..5}.json`
  on S2.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-094-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Sand Art Home Decor \| Mesmerizing Moving Sand Pictures 🌊" (YouTube, id `3XkUszjfkSo`) | YouTube search, query "mesmerizing kinetic sand art short"; https://youtube.com/shorts/3XkUszjfkSo | 46s — PASS (15–60s) | 1,719,312; uploader Sand Art Home | Duration PASS; niche guard PASS; caption-track MEASURED 157 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Man Makes Incredible Wooden Sculpture with Chainsaw" (YouTube, id `CF8sbQkZQ2c`) | YouTube search, query "incredible chainsaw wood carving short"; https://youtube.com/shorts/CF8sbQkZQ2c | 39s — PASS | 99,386; uploader This Is Happening | Same as #1 |
| 3 | "Making a moving sand picture" (YouTube, id `rRy-Ei6RvyU`) | YouTube search, query "mesmerizing kinetic sand art short"; https://youtube.com/shorts/rRy-Ei6RvyU | 57s — PASS | 33,111; uploader Amazing Sands - Moving Sand Art | Same as #1 |
| 4 | "Traditional Blacksmith Work That Will Blow Your Mind \| Satisfying Metal Forging" (YouTube, id `SFFxtmdc9SE`) | YouTube search, query "satisfying blacksmith forging short"; https://youtube.com/shorts/SFFxtmdc9SE | 15s — PASS (gate boundary, inclusive) | 407; uploader Blacksmithcraft67 | Duration PASS; niche guard PASS; caption-track MEASURED 0 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |

Cautions, recorded not recommended: candidate 1 is a product-demo format
(moving-sand-picture home decor) — audition judges suitability; candidate 2's
uploader "This Is Happening" is aggregator-style — licence/origin re-check owed
at QA (VYR-086 WooGlobe/RM Videos precedent); candidate 4 sits exactly on the
15s gate boundary and carries no caption tracks at all. Honest traction note:
the pool's most-popular ranking is dominated by candidate 1 (1.7M views, vs
VYR-091's top of 3,617) — the first run-3 pool with real traction at the top;
candidates 3–4 are modest (33K / 407 views).

## YouTube discovery: 4 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying blacksmith forging short" | 10 | 1 | 1 — `SFFxtmdc9SE` |
| "amazing wire sculpture art short" | 10 | 0 | 0 |
| "mesmerizing kinetic sand art short" | 10 | 2 | 2 — `3XkUszjfkSo`, `rRy-Ei6RvyU` |
| "oddly satisfying resin art pouring short" | 10 | 2 | 0 — both excluded known ids (see note) |
| "incredible chainsaw wood carving short" | 10 | 1 | 1 — `CF8sbQkZQ2c` |
| "satisfying stone carving art short" | 10 | 0 | 0 |

All `yt_rc` 0; no niche-guard rejections (`rejected_niche` 0 on every
query); `excluded_known` 66 on every query. The two zero-yield queries
surfaced long-form compilations only (same pattern as VYR-053/055/057/091).
All 6 queries were guard-checked first-hand locally before issuing (all
ALLOW under the VYR-065 guard, run against the guard file from main);
none repeats any query used by VYR-055 (base script), VYR-086, VYR-091 or
VYR-088. Raw per-query output saved at `/tmp/vyr094_q{0..5}.json` on S2.
Discovery script: the VYR-055 flat-playlist script, VYR-094 variant
(6 fresh queries, 66-id `EXTRA_EXCLUDE`); the merged script itself is
unchanged by this task.

Resin-query note (recorded, not hidden): the run reported 2 shorts-length
rows, both excluded, 0 fresh. On re-run of the raw search to name them, only
1 shorts-length row appeared — `YRDYwVy3BQU` (21s, VYR-051 pool, in the
66-set). The second row could not be re-identified: YouTube search results
drifted between the two calls (the re-run's other near-miss, `6KLqEav-z_k`,
reads 61s — 1s over the gate — and is not in any filed pool, so it was not
the excluded row). The run output itself (shorts_len 2, fresh 0) stands;
the unidentified row is recorded as such, not assigned an id.

## Exclusion set — 66 unique ids, verified first-hand

Assembled from the pool JSONs on main (VYR-051: 12, VYR-053: 6, VYR-054: 2,
VYR-055: 7, VYR-055-REFRESH-3: 5, VYR-057: 4, VYR-037 candidate 2: 1,
VYR-087: 4, VYR-089: 5, VYR-086: 8, VYR-088: 11, VYR-091: 3 — deduped to
66; full list in `TASK-VYR-094-POOL.json` (`excluded_ids`)). This corrects
two lineage gaps: VYR-091's run used only an 18-id set, so it filed
`OfEaVD7TtXM` — a known VYR-055-REFRESH-3 id already in the 46-set — and
`uj57NSz8Yqw` appears in both the VYR-091 and VYR-088 pools (VYR-088's
discovery ran after VYR-091 filed, with an exclusion set that did not yet
include VYR-091's 3). Both ids are in this run's 66-set. Pool disjointness:
the 4 fresh ids are disjoint from the 66-set (enforced at search time and
re-checked against the filed pools) and from each other. The 84-ID S2
exclusion gap stands (S2 manifests absent, carried decision owed to Muse).

## Machine QA gates — caption-track MEASURED (new this run); BGM/watermark/loudness still BLOCKED

Caption-track count ran live on VyralX-Server (server 5) this run
(~17:35–17:40 IST), `yt-dlp --list-subs` with the pipeline cookie jar,
one call per candidate, all rc 0:

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `3XkUszjfkSo` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `CF8sbQkZQ2c` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `rRy-Ei6RvyU` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `SFFxtmdc9SE` | none ("has no automatic captions") | 0 | 0 / 0 |

Reading note: the 157 is YouTube's auto-caption + auto-translation list for
the video (auto-generated captions present, original language incl. en);
it is not 157 authored caption files. No caption-count pass threshold
exists in the board record, so counts are filed as measured data for the
audition, not as pass/fail. Control: the same probe on run-6 candidate
`bRfoNfGBL1o` also returns a real answer (no automatic captions, no
subtitles) — the method is not returning canned output. Without cookies the
same probe fails at the bot-check (verified this run on server 5, rc 1,
"Sign in to confirm you're not a bot"); the jar on VyralX-Server is valid
and is what unblocks this gate. S2 has no jar, so the gate cannot run there.

BGM presence, watermark and loudness stay BLOCKED — re-probed this run,
not inherited. One download attempt on VyralX-Server with the VYR-056
proof command (cookies + `--remote-components ejs:github`, VYR-056
proof target class) on candidate `3XkUszjfkSo`: rc 1, no file created.
Tail: n-challenge warning, "Some web_embedded client https formats have
been skipped as they are missing a URL. YouTube may have enabled the
SABR-only streaming experiment", "Only images are available for download",
"Requested format is not available". Same standing failure as VYR-056
(Nov 24); VYR-056 leg CLOSED as unachievable (coordinator ruling 4);
WATCH151 ruling 1 (gates PENDING/BLOCKED acceptable, proceed) stands.
The deno solver itself ran this run (`[jsc:deno] Solving JS challenges`
in the --list-subs output, no crash) — the block is now at format
selection (SABR-only), not at the solver. No download-path repair was
attempted (needs coordinator/owner direction per VYR-056).

## Admin notes

- Board flip PR #2129 (claim flip, head `dbfd3426`) was closed unmerged by
  this run: its flip is already live on main via coordinator board PR #2131
  (merge `caa597bc`, VYR-094 → CLAIMED), and it was dirty against current
  main. Claim record stands via hub #2045 comment 7216788669 + board status.
  Work PR for this evidence follows on the same branch.
- Board branch-field mismatch (for the coordinator): the board record lists
  branch `musetp14/task-vyr-094`; the real branch is
  `musetp14/task-vyr-094-candidate-pool-run-3` (verified via ref GET).
  Board flips are coordinator-only; not edited here.
- Acknowledged, no action (not this task's scope): TP6's 17:13 IST alert
  (hub 7217434447) — FRIDAY `:10000` + Inference `:8001` down on S2
  (OOM-killed 15:07 IST); restart decision belongs to Muse / TP1. No impact
  on this task: discovery + gates ran on S2's repo/yt-dlp and on
  VyralX-Server, neither of which needs the S2 FRIDAY copy.

## States

- Implemented YES (discovery + pool + evidence filed; work PR open) /
  tested PARTIAL (live discovery 6/6 queries rc 0; caption-track gates
  measured live 4/4; BGM/watermark/loudness BLOCKED on a re-probed
  download path) / merged NO (awaiting peer review/merge) / deployed N/A
  (no service changed; S2 tree left as found) / production-verified PARTIAL
  (pool filed from a real live discovery run + measured caption gates;
  render awaits the download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted — candidates
  only, no publish step.

— Muse TP14
