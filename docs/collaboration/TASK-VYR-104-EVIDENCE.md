# TASK-VYR-104: Supervised cycle 18 candidate pool — discovery + machine QA gates — Muse 7

- Task: TASK-VYR-104 (VyralX supervised cycle 18 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-103 cycle 17). Branch
  `muse7/task-vyr-104-cycle-18-candidate-pool` @ `42ba9151` (claim
  2026-11-28 ~11:31 IST, hub #2045 comment 7235039199; assignment Burn
  Enforcer 7235033944 §B — STR-114 ruled to Muse 20, VYR-104 to Muse 7;
  board on main `42ba9151` read AVAILABLE / owner null / branch null /
  pr null, blob `48241373`; no competing claim on the hub through
  comment 7235033944, re-read immediately before claiming). Board flips
  ride the coordinator's board PR (WATCH259) — no board hunk in this PR.
- Discovery run: 2026-11-28 ~11:35–11:45 IST, on S2 via bridge
  `run_shell` server=2 (host friday-universe-vnic-2). Caption-track
  gates + download re-probe: 2026-11-28 ~11:45–11:55 IST on
  VyralX-Server (server 5) via bridge `run_shell` server=5. Loop stays
  OFF, uploader paused, renders held unlisted; no renders in this
  task — pool refresh only.
- Pattern: TASK-VYR-101 (Muse 14) — same flat-search method and gates.
  Usage at run time: 61% of free weekly limit (resets Nov 28 9:25 PM
  IST), verified this run.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py`: `check_query` for all 9
queries before issuing (all ALLOW), `check_candidate` for all 90
returned entries after (0 rejections). Raw per-query output saved at
`/tmp/vyr104_q{0..8}.jsonl` on S2; nothing was written to the S2
checkout (tracked tree clean before and after, verified this run).

All nine topics are new: freshness verified against the 73 candidate
queries recorded in the 22 pool JSONs on main plus the zero-yield
topics from prior cycle evidence tables (chalk art, topiary,
macrame, watercolor, bento box, needle felting, terrarium, origami,
crochet amigurumi, rug tufting, kite flying, paper marbling,
ice-cream rolling, shadow puppetry, bubble tea, wire sculpture,
stone carving) — basket weaving, crystal growing, hula hoop,
woodturning, pottery glazing, boomerang, lava lamp, sandcastle and
glass engraving repeat none of them.

## S2 + VyralX-Server state at run time

- S2 (server 2) host `friday-universe-vnic-2`; checkout
  `/opt/friday_universe` @ `69ff042b`, tracked tree clean (pre-existing
  untracked scratch only — left as found). `VyralX-Daemon.service`
  inactive (loop OFF, as ordered). `yt-dlp` 2026.10.21; niche guard
  present (`VyralX/app/services/niche_guard.py`).
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200. The pipeline cookie jar
  (`VyralX/data/youtube_cookies.txt`, 3146 bytes) EXISTS there —
  existence checked only, contents never read. `yt-dlp`
  `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21.
  `VyralX-Daemon.service` inactive (loop OFF, as ordered). The live
  VyralX service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-104-POOL.json`.
Ranking note: the top 8 of 16 fresh shorts are filed, by views; the
8 below the cut are listed after the table, not filed (VYR-098
precedent). No view gate exists in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "\"Gerhards Big U\", strip laminated boomerang by John Cryderman" (YouTube, id `QCjLXID-QiA`) | YouTube search, query "incredible boomerang throw trick short"; https://youtube.com/shorts/QCjLXID-QiA | 22s — PASS (15–60s) | 2,008,771; uploader Serge Paulin | Duration PASS; niche guard PASS; caption-track BLOCKED (embedding disabled by owner); licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Salt Crystal Garden" (YouTube, id `uoexANHeWoU`) | YouTube search, query "mesmerizing crystal growing short"; https://youtube.com/shorts/uoexANHeWoU | 41s — PASS | 497,708; uploader toolusinganimal | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 3 | "Wooden boomerang returns \| How to Throw and Catch a Boomerang?" (YouTube, id `_JnS4NHdR9U`) | YouTube search, query "incredible boomerang throw trick short"; https://youtube.com/shorts/_JnS4NHdR9U | 42s — PASS | 372,154; uploader Boomerangs by Nemunas | Caption-track MEASURED auto captions available / 0 uploaded; rest same as #1 |
| 4 | "Dremel Tool" (YouTube, id `maDQUJdzBz4`) | YouTube search, query "satisfying glass engraving short"; https://youtube.com/shorts/maDQUJdzBz4 | 56s — PASS | 188,613; uploader Corning Museum of Glass | Caption-track MEASURED auto captions available / 1 uploaded (en); rest same as #1 |
| 5 | "Sandcastle Building Time-lapse Video" (YouTube, id `pOkjt3cpRtI`) | YouTube search, query "amazing sandcastle building short"; https://youtube.com/shorts/pOkjt3cpRtI | 24s — PASS | 142,111; uploader Little Day Out | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "Copper Sulfate Crystals - Timelapse" (YouTube, id `ng4QQkW4ODM`) | YouTube search, query "mesmerizing crystal growing short"; https://youtube.com/shorts/ng4QQkW4ODM | 18s — PASS | 22,748; uploader Scott Cutler | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 7 | "How to Apply Brush-On Ceramic Glaze: Step-by-Step Tutorial" (YouTube, id `ivHm62XEQN4`) | YouTube search, query "satisfying pottery glazing short"; https://youtube.com/shorts/ivHm62XEQN4 | 30s — PASS | 7,540; uploader GLOST glaze | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 8 | "Glass engraving for beginners #shorts seaglass pendant" (YouTube, id `pawIqnrdUHc`) | YouTube search, query "satisfying glass engraving short"; https://youtube.com/shorts/pawIqnrdUHc | 57s — PASS | 1,267; uploader Lesley Pyke Glass Engraver | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Below the cut — 8 further fresh shorts, not filed: `KEoCnNuhuas`
(1,238 views, lava lamp), `PwZW5VBYFjY` (960, crystal growing),
`oj27S9Bl4ck` (863, lava lamp), `TK_5kv_yVF0` (367, crystal growing,
AI-labelled "Growing crystals ASMR ai"), `bkhs369gWgo` (317, glass
engraving), `uHZH8uJfy7U` (207, pottery glazing), `YrBuqb5zmD8` (89,
glass engraving), `oxj4tMPqHiQ` (8, glass engraving).

Cautions, recorded not recommended: candidate 1 has playback on
other websites disabled by the owner — its caption gate is blocked
and the render path may block the same way; candidate 3's title
carries "Boomerangs for Sale" (product framing); candidate 4 is an
institutional upload (Corning Museum of Glass); candidate 7 is a
brand tutorial (GLOST glaze) — licence/origin re-check owed at QA
for each; candidate 8 sits at 57s, near the 60s gate edge. Honest
traction note: this pool's head is the strongest yet (2,008,771
views, vs cycle 9's top 79,244), but traction does not imply
licence clearance. Candidates are filed by the machine gates only;
the audition judges suitability.

## YouTube discovery: 8 filed candidates from 90 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying basket weaving short" | 10 | 0 | 0 (all 10 over 60s) |
| "mesmerizing crystal growing short" | 10 | 4 | 4 — `ng4QQkW4ODM`, `TK_5kv_yVF0`, `PwZW5VBYFjY`, `uoexANHeWoU` |
| "amazing hula hoop trick short" | 10 | 0 | 0 (all 10 over 60s) |
| "mesmerizing woodturning lathe short" | 10 | 0 | 0 (all 10 over 60s) |
| "satisfying pottery glazing short" | 10 | 2 | 2 — `uHZH8uJfy7U`, `ivHm62XEQN4` |
| "incredible boomerang throw trick short" | 10 | 2 | 2 — `_JnS4NHdR9U`, `QCjLXID-QiA` |
| "mesmerizing lava lamp making short" | 10 | 2 | 2 — `oj27S9Bl4ck`, `KEoCnNuhuas` |
| "amazing sandcastle building short" | 10 | 1 | 1 — `pOkjt3cpRtI` |
| "satisfying glass engraving short" | 10 | 5 | 5 — `bkhs369gWgo`, `pawIqnrdUHc`, `oxj4tMPqHiQ`, `YrBuqb5zmD8`, `maDQUJdzBz4` |

All 9 searches rc 0; niche guard on S2: `check_query` ALLOW for all
9 queries before issuing; `check_candidate` over all 90 returned
entries: 0 rejections. Raw per-query output saved at
`/tmp/vyr104_q{0..8}.jsonl` on S2.

## Exclusion set — 157 unique ids, verified first-hand

Assembled from the 22 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 090, 091, 093, 094, 095,
096, 097, 098, 099, 100, 101): union of all candidate ids + all
`excluded_ids` fields = 157 ids, recomputed this run by direct
blob fetch of all 22 pools; full list in `TASK-VYR-104-POOL.json`
(`excluded_ids`). Pool disjointness: the 8 filed ids are disjoint
from the 157-set and from each other (asserted in the filing
script). VYR-102/103 pools are not on main yet (branches only, no
pool filed at run time) — fresh topics avoid collision; the
coordinator reconciles at merge.

## Machine QA gates — caption-track MEASURED (7/8; 1 BLOCKED); BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate (raw outputs at `/tmp/vyr104_sub_<id>.txt` on server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `QCjLXID-QiA` | — | — | BLOCKED (rc 1: "Video unavailable. Playback on other websites has been disabled by the video owner") |
| `uoexANHeWoU` | none ("has no automatic captions") | 0 ("has no subtitles") | 0 auto / 0 uploaded |
| `_JnS4NHdR9U` | available (157 language rows incl. auto-translations) | 0 | auto available / 0 uploaded |
| `maDQUJdzBz4` | available | 1 (en) | auto available / 1 uploaded |
| `pOkjt3cpRtI` | none | 0 | 0 / 0 |
| `ng4QQkW4ODM` | none | 0 | 0 / 0 |
| `ivHm62XEQN4` | none | 0 | 0 / 0 |
| `pawIqnrdUHc` | none | 0 | 0 / 0 |

No caption-count pass threshold exists in the board record, so
counts are filed as measured data for the audition, not as
pass/fail. Control: the same probe on run-6 candidate `bRfoNfGBL1o`
returns 0 auto / 0 uploaded — identical to prior cycles' control
results; the method is not returning canned output.

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`,
`--no-playlist`, `-f 'bv*[height<=1080]+ba/b[height<=1080]'`,
`--merge-output-format mp4`) on candidate `uoexANHeWoU`: rc 1, no
media file created (log at `/tmp/vyr104_dl.log` on server 5). Tail:
"n challenge solving failed", "Some web_embedded client https
formats have been skipped as they are missing a URL. YouTube may
have enabled the SABR-only streaming experiment", "Only images are
available for download", "Requested format is not available". Same
standing failure as VYR-056; WATCH151 ruling 1 (gates
PENDING/BLOCKED acceptable, proceed) stands. No download-path repair
was attempted (needs coordinator/owner direction per VYR-056).

## States

- Implemented YES (discovery + pool + evidence filed; work PR open) /
  tested PARTIAL (live discovery 9/9 queries rc 0; caption-track
  gates measured live 7/8 + control, 1 BLOCKED on owner embedding
  restriction; BGM/watermark/loudness BLOCKED on a re-probed
  download path) / merged NO (awaiting peer review/merge) /
  deployed N/A (no service changed; S2 tree left as found) /
  production-verified PARTIAL (pool filed from a real live
  discovery run + measured caption gates; render awaits the
  download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 7
