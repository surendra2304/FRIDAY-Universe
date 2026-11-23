# TASK-VYR-043 — VyralX: current scoreboard (5 public videos + held-render pool)

- Task: TASK-VYR-043 (P2, owner muse_15)
- Branch: `muse15/task-vyr-043-vyralx-scoreboard`, from main `c71a1179` (claimed from `3e8a4a1`, rebased onto current main before filing)
- Claim: issue #1483 comment 7103818229 (2026-11-23 ~19:50 IST), on assignment
  in coordinator watch 7103106790 (queue FUT-024 -> VYR-043 -> EARN-002)
- Live pull: 2026-11-23 ~19:55–20:05 IST (14:25–14:35 UTC). Sources: Oracle
  `VIDEO_METRICS` / `PUBLISH_JOBS` / `RENDER_JOBS` via read-only SELECTs
  (VyralX app ORM on Oracle Server 2); live YouTube counters via yt-dlp
  with the pipeline's own cookies on Server 2; `published_shorts_manifest.json`,
  `viral_loop_manifest.jsonl` and `viral_loop_state.json` (Server 2 copy —
  see §5 for why U2 files could not be read directly). All numbers below
  are that pull unless stated.
- Uploads remain PAUSED (vyralx-autopilot.timer disabled). This task scores
  only: no uploads, no re-enables, no publishes, no state changes anywhere.

## 1. Headline

- **5 public videos: 39 views / 8 likes total, 0 comments.** Live views
  are unchanged since the store's last sync (2026-11-22 15:35 UTC) — **0 new
  views in ~23 hours** across all 5 videos.
- **11 held renders**, all status HELD, all framed, all with completed
  render jobs and pending-approval publish jobs (yt_id null — never
  uploaded). Loop OFF; last cycle 2026-11-21T01:27:06Z.
- One of the 5 tracked videos, `8rwdlaLNJT4`, is **not watchable**: YouTube
  answers "We're processing this video. Check back later." It has 0 views /
  0 likes in the store and no publish-job row. See §5.

## 2. The scoreboard — 5 public videos

Views are LIVE (yt-dlp pull this run). Likes and comments are LAST SYNCED
(VIDEO_METRICS `fetched_at` 2026-11-22 15:35:37 UTC for all 5 rows):
yt-dlp returns `like_count=None` for these Shorts, and the deployed YouTube
Data API key is recorded invalid (board evidence, TASK-VYR-005 follow-up),
so no live like pull exists. With 0 view delta since the sync, like deltas
are unlikely but unproven — do not cite the likes as live.

| yt_id | title | views (live) | views (stored) | likes (stored) | comments | availability (live) | uploaded |
|---|---|---:|---:|---:|---:|---|---|
| FWZN1dVfd-g | Wait For The Most Unexpected Plot Twist 😱🤯 #Shorts | 21 | 21 | 1 | 0 | public | 2026-10-29 |
| 1C9CyiqW1kI | Maximum Main Character Energy In School 💀✨ #Shorts | 9 | 9 | 2 | 0 | public | 2026-10-25 |
| sAymMXXCjFQ | The $9,999,999 Michelin Restaurant 💀🧼 #Shorts | 7 | 7 | 3 | 0 | public | 2026-10-24 |
| cCux4eKjLUE | Millimeter-Perfect Extreme Stunt That Shocked Millions 😱🔥 #Shorts | 2 | 2 | 2 | 0 | public | 2026-10-28 |
| 8rwdlaLNJT4 | (unknown — video processing, see §5) | 0 (stored; not fetchable) | 0 | 0 | 0 | unknown (processing) | unknown |
| **Total** | | **39** | **39** | **8** | **0** | | |

- Channel: VyralX Agent (@VyralXAgent) — confirmed on the fetched pages.
- Cross-checks: live views = stored views for all 4 fetchable videos
  (21/9/7/2); totals 39 views / 8 likes match the board's last-filed
  baseline exactly (39/8, coordinator draft 2026-11-23 ~11:47 IST).
- **None of the 5 has a PUBLISH_JOBS row.** Verified: a SELECT for the 5
  yt_ids returns 0 rows, while the query itself is sound (37 jobs carry a
  yt_id; autopsy id `rE2wCU6bYAk` resolves to job 1, uploaded). These are
  channel videos outside the pipeline's job records — the "second gap"
  recorded in the VYR-882 activation note.
- **The published manifest's privacy labels are stale.** It records
  FWZN1dVfd-g as private, 1C9CyiqW1kI as unlisted (draft preview) and
  cCux4eKjLUE as private; all three are public on YouTube now. sAymMXXCjFQ
  is recorded public and still is. 8rwdlaLNJT4 is not in the manifest at
  all. The manifest (11 entries: 1 public, 1 unlisted, 9 private by its
  own labels) describes publish-time state, not current state.

## 3. The held-render pool — 11 renders

All 11 rows come from `viral_loop_manifest.jsonl` (all status HELD),
corroborated row-for-row by Oracle: every render job is `completed` and
every publish job is `pending_approval` with yt_id null. Render MP4s
(+ .ass captions + thumbnails) exist in `renders/` (verified on the
Server 2 copy; sizes 15–37 MB).

| cycle | job | source video_id | series | title | BGM source | render file |
|---:|---:|---|---|---|---|---|
| 2 | 801 | ClQTsoa23FU | COMEDY | Mystery Goat Graphic Pops Up 😂 #Shorts | synth_fallback | renders/framed-ClQTsoa23FU-2a2df6.mp4 |
| 2 | 802 | -bh5VGbrbLI | PETS | Dog Watches Man Press Buttons 😆💀 #Shorts | synth_fallback | renders/framed--bh5VGbrbLI-5970f1.mp4 |
| 2 | 803 | uKbWHP3Bvew | HOWTO | Tear the Journal Strip 🤯 #Shorts | synth_fallback | renders/framed-uKbWHP3Bvew-36817c.mp4 |
| 2 | 804 | x_iPi08PdZU | COMEDY | Unexpected Safe Side Switch During Park Walk 😂 #Shorts | synth_fallback | renders/framed-x_iPi08PdZU-af610a.mp4 |
| 5 | 821 | REZwUljF8cc | PETS | Man discovers hidden cat surprise 😲 #Shorts | growth:viral_imagine-dragons_enemy | renders/framed-REZwUljF8cc-bb2336.mp4 |
| 5 | 822 | zE6Htw50oaM | AUTOS | ATV Rider Approaches Overturned Vehicle, Hand Touches Leg 😱 #Shorts | growth:howto_dua-lipa_levitating | renders/framed-zE6Htw50oaM-ab8684.mp4 |
| 5 | 823 | PLGSvGqLyc4 | NEWS | Crazy India News Bombardment Clip 😱🚀 #Shorts | growth:viral_masked-wolf_astronaut-in-the-ocean | renders/framed-PLGSvGqLyc4-b983b8.mp4 |
| 5 | 824 | PMMg1GbeJHA | AUTOS | Police Car Stops Biker, Boots on Dirt 😱 #Shorts | growth:comedy_kazumi-totaka_mii-channel-theme | renders/framed-PMMg1GbeJHA-52e6fe.mp4 |
| 5 | 825 | VLhyp-XEJxs | AUTOS | Truckers Guide Foggy Student Driver 🚚🌫️ #Shorts | growth:sports_interworld_metamorphosis | renders/framed-VLhyp-XEJxs-aee73d.mp4 |
| 6 | 841 | Pfxp6mysc90 | SPORTS | White Suit vs Baseball Runner Challenge 🏃‍♂️🤖 #Shorts | growth:space_ludovico-einaudi_experience | renders/framed-Pfxp6mysc90-d034ad.mp4 |
| 11 | 861 | bhw0Cxw9WGs | AUTOS | Charger Pulls Two Teslas on Tarmac 🚗⚡ #Shorts | growth:pets_kevin-macleod_life-of-riley | renders/framed-bhw0Cxw9WGs-b4e71e.mp4 |

- Counts: by cycle — 2: 4, 5: 5, 6: 1, 11: 1. By series — AUTOS 4,
  COMEDY 2, PETS 2, HOWTO 1, NEWS 1, SPORTS 1. All 11 framed edit mode.
  Rendered Nov 18 (jobs 801–804), Nov 19 (821–825, 841), Nov 21 (861).
- BGM split: 4 synth_fallback (all cycle 2), 7 real growth tracks
  (cycles 5–11). The cycle-2 synth beds predate the real-track gate
  work (TASK-VYR-038); noted as a fact, not judged here.
- **Hold reason (uniform):** awaiting the coordinator's review/approval
  — the supervised release gate. The loop is OFF, uploads are PAUSED,
  and renders stay held unlisted per standing orders; nothing publishes
  until the coordinator watches a render end-to-end and orders re-enable.
  No per-render hold reason is recorded anywhere; the hold is the gate,
  not a per-video defect.
- Loop state (`viral_loop_state.json`): 11 cycles completed, last cycle
  2026-11-21T01:27:06Z (cycle 11: pool 106, attempts 24, produced 1,
  held_publish_jobs [861]). No cycles since — the Nov 22 supervised
  cycle (TASK-VYR-039) produced no render (one candidate blocked by a
  code defect, one gated out at audition).

## 4. Method — how every number was pulled

1. **Store snapshot:** read-only SELECTs against the VyralX Oracle
   schema from Server 2 (`/opt/friday_universe/venv312/bin/python`,
   app ORM `SessionLocal`): `VIDEO_METRICS` (5 rows, fetched_at
   2026-11-22 15:35:37 UTC), `PUBLISH_JOBS` by status (pending_approval
   11, failed 17, uploaded 37), `RENDER_JOBS` for the 11 held ids
   (all completed), pending_approval job list (exactly the 11 held
   ids, yt_id null, titles matching the manifest).
2. **Live views:** yt-dlp `--dump-json` on Server 2 with the pipeline's
   own cookies (`VyralX/data/youtube_cookies.txt`, fresh Nov 23 15:21).
   Anonymous fetches fail — YouTube bot-checks Oracle datacenter IPs
   ("Sign in to confirm you're not a bot", all 5 ids, no cookies).
   With cookies, 4 of 5 return full metadata (views + availability);
   the android player client was also tried for likes (no like_count
   from either client; see §5).
3. **Manifests:** `published_shorts_manifest.json` (11 entries),
   `viral_loop_manifest.jsonl` (11 HELD lines) and `viral_loop_state.json`
   read from the Server 2 copy via the bridge (U2 SSH down — §5),
   cross-checked against the Oracle rows and against the Nov 22 U2
   readings in TASK-VYR-037/039 (identical counts: 11 entries, 11 HELD,
   last cycle 2026-11-21T01:27:06Z).
4. **Independent confirmation:** the public watch page for FWZN1dVfd-g
   was fetched separately (title + description + @VyralXAgent visible),
   confirming the video is public outside the yt-dlp path.

## 5. Caveats and findings

1. **Likes are last-synced, not live.** yt-dlp returns `like_count=None`
   for all 4 fetchable videos on both the web and android player
   clients. The 8 likes are the VIDEO_METRICS values from the Nov 22
   15:35 UTC sync. Views are live and unchanged since that sync, so
   like movement is unlikely — but it is unmeasured, and this doc does
   not claim otherwise.
2. **8rwdlaLNJT4 is stuck processing.** YouTube answers "We're processing
   this video. Check back later." on both player clients. The store
   holds it at 0/0 (fetched Nov 22). It has no publish-job row and is
   not in the published manifest, so its provenance is unknown from
   VyralX's own records. It counts in the 5 tracked videos but contributes
   nothing watchable. Follow-up for the coordinator: confirm whether it
   is a failed upload to delete or re-upload.
3. **Manifest privacy is stale (§2).** Three of the five videos changed
   privacy after publish without the manifest being updated. Any future
   scoreboard should re-derive privacy live, as this one does.
4. **U2 SSH is down from both Oracle servers.** `ssh ubuntu@16.176.9.247`
   times out (port 22, ConnectTimeout 20s) from Server 1 and Server 2,
   three attempts ~19:53–19:57 IST. The VyralX HTTP service on U2 is UP
   (`/vyralx/health` 200 via the public ingress, 2026-11-23T14:21:23Z),
   so the host and service are alive — only the SSH path is broken.
   This blocks all future U2-side VyralX work that needs a shell
   (manifests, timer logs, metrics-sync runs). The S2 egress failure to
   that AWS IP was previously noted in TASK-ORCH-013 (HTTP 000 from S2);
   SSH now fails from S1 as well. Follow-up for the coordinator/infra:
   restore the SSH path or document the new access route.
5. **Metrics-sync freshness unknown past Nov 22.** The store's last
   refresh is 2026-11-22 15:35:37 UTC. Whether the vyralx-metrics-sync
   timer has fired (and failed or skipped) since cannot be checked
   without U2 shell access. The live pull in this doc supersedes the
   store for views; likes still depend on the next successful sync
   (which needs a valid Data API key — recorded invalid).
6. **No new views in ~23 hours.** The channel's 5 public videos are flat
   at 39 views. That is the honest current state of VyralX progress
   measure (3): views are not growing while uploads are paused and no
   held render has been released.

## 6. Follow-ups for the coordinator's pool

- Restore U2 SSH access (or document the new route) — blocks all
  U2-side VyralX shell work (§5.4).
- Resolve `8rwdlaLNJT4` (stuck processing, no provenance) — delete or
  re-upload (§5.2).
- Live like counts need a valid YouTube Data API key (or an OAuth
  re-auth so the metrics-sync timer can refresh the store) (§5.1, §5.5).
- Refresh the published manifest's privacy labels from live state, or
  stop treating the manifest as a privacy source (§5.3).

— Muse 15
