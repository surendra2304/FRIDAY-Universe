# Autopsy: the 29 unlisted autopilot shorts (TASK-VYR-005)

Evidence: VyralX's own production database on Server 2 (tables
`PUBLISH_JOBS`, `VIDEO_PROJECTS`, `RENDER_JOBS`, `ASSETS`, `SOURCES`,
`VIDEO_METRICS`, `CONTENT_PACKS`), read 2026-11-15 via read-only SELECT
probes. No YouTube API was used — the OAuth credential is dead
(`invalid_grant`, TASK-VYR-003) and the deployed Data API key is
invalid — so everything below is what VyralX recorded about itself.

## What was made

The autopilot ran on its ~5-hour timer from 2026-11-03 to 2026-11-15
and produced **46 videos**. Every one followed the same recipe:

* **Source:** another creator's already-viral short, taken from
  YouTube. All 46 `SOURCES` rows say platform `youtube_transformative`.
  The project topic was literally `Repurposed: <the source video's own
  title>` — Zach King, a BTS/JK clip, "Funniest TV Moments", and a
  heavy cluster from one comedy-sketch creator (the "miss your slim
  GF / husband is always hungry / diet failed" series).
* **Edit:** a single scene (`scene_count = 1` for all 46), vertical
  1080×1920 (45 of 46; one 480×600 outlier, which failed to upload),
  target length 15–55s (mean 27.4s).
* **Packaging:** an AI-rewritten sensational title in one formula —
  scene description + 😱/🔥/🤯 + `#Shorts` — plus a frame-grab
  thumbnail. All 46 jobs carry tags and a description.
* **Selection:** no signal at all. `trend_score = 0.0` for all 46
  projects, `trend_query` empty for all 46, `trend_source_video_id`
  empty for all 46. Whatever picked the sources, it recorded no
  reasoning and no score.

## The 29 that reached YouTube (all unlisted, 2026-11-03 → 11-09)

Uploaded durations: 14.7–41.2s, mean 25.1s (<20s: 8 · 20–29s: 14 ·
30–39s: 5 · 40s+: 2). Every upload succeeded on attempt 1.

| Job | YouTube ID | Upload title | Source video (creator's title) | Length |
|----:|---|---|---|---:|
| 1 | rE2wCU6bYAk | Rescue Mission Gone Wrong: Kitchen Chaos Unleashed 😱🚒 #Shorts | Someone save her cooking!🚑💀🥘 | 31.7s |
| 2 | v63Knfew8Z8 | He Claims His Machine Beats Light Speed 🚀😱 #Shorts | He thinks his machine is faster🍎😂 | 39.9s |
| 3 | eId2hMpgXFA | Pillow Chase Turns Hallway Into Runway 😱✨ #Shorts | When the pillow wipes off her makeup😱😭 | 30.8s |
| 4 | 5O-zcwIWnq8 | Crazy Creamy Egg Toast Shocked My Taste Buds 😱🔥 #Shorts | Save Her from the Egg!🥚🚨🚑 | 23.1s |
| 5 | MFv1_qcx-Mk | Smartphone Food Photo vs Real Plate Switch 🤯 #Shorts | Why do we have such funny poop faces?😂💩 | 18.9s |
| 6 | GEJjgDwYidA | Steak Plate Switch From Kitchen to Beach to Bathroom 😱🍽️ #Shorts | She made the world's toughest steak🥩🌎 | 21.1s |
| 7 | g5bx8HTy-nw | His Reaction Says Everything 😂💀 #Shorts | The Cleanest Feet in the World🦶🌎 | 20.5s |
| 21 | KUcWZdBE6po | Hallway Hand-Off: Maroon Man Carries Pink Woman 😱🚀 #Shorts | When you miss your slim GF🥲🙃 | 19.1s |
| 41 | sNXEKVlSUrQ | Gravity Flip Sends Crowd Into Chaos 😱🔥 #Shorts | When you're hungry at 3AM🥫👻 | 25.1s |
| 42 | qkXyrPQyc54 | She Did NOT See That Coming 😱😂 #Shorts | Her husband is always hungry🍚🫩 | 17.9s |
| 43 | hX2pDrW7o0U | Closet Reach Meets Car Window Slam and Toilet Head Surprise 😱🚗 #Shorts | This is why he's afraid of "Hi!"😱💀 | 19.6s |
| 61 | SCd4k8TumuI | Guy Covers His Face After Phone Shock 😱📱 #Shorts | Girls the night before a date🌙💄✨ | 41.2s |
| 62 | jLnrAHNMhYk | White Shirt Pavement Pose Meets Cozy Couch Yawn and Car Kiss 😱✨ #Shorts | When you miss your skinny GF😢🙄 | 19.7s |
| 81 | of7cKrPk1Eg | Lighter Ignites Wallet as Sticky Hand Holds Flame 😱🔥 #Shorts | Eating Chocolate alone was a mistake🍫😂 | 22.1s |
| 82 | KeOl3n0BahU | Striped-Top Stare Meets Blazing Orange Blur 😱🔥 #Shorts | This is why she gets acne🥭🧼🫧 | 14.7s |
| 101 | rioS2ab0YKs | Orange-Haired Girl Leaps Onto Bed With Handbag 😱🤯 #Shorts | Why she's late on FaceTime⏳📲 | 21.3s |
| 102 | ijP1b4U9zO8 | Woman Waves Red Lipstick Beside White Car 😱🚗 #Shorts | I'm not SORRY for everything🙄🫵 | 40.3s |
| 103 | XW7dYQElJDQ | Man Lies with Drill, Woman Grips Him 😱✨ #Shorts | Even now he still doesn't know what happened🤯👨‍🔧 | 25.6s |
| 121 | Ga73ufVsZDg | Blue-Shirt Guy's Pastry Tray, Wig Dive & Egg Carton Face 😱🤯 #Shorts | Funniest TV Moments 📺😂 | 21.3s |
| 141 | D3ICu0s8m6M | Spider-Man Tied To Chair While Orange-Shirt Girl Sips Cup 😱🤯 #Shorts | She found out the truth about almonds🥜😭 | 23.6s |
| 161 | WWKjBdNN5uk | Massive Confetti Cannon Explosion Shocks Everyone 😱💥 #Shorts | This Is Why I Broke Up with Her🌈💔 | 22.1s |
| 181 | ySBPklkYFQ0 | Yoga Stretch Turns Into Weight Shock 😱🤯 #Shorts | This is why her diet failed🤰💀 | 25.7s |
| 201 | udAJT1B-HB4 | Pink-Haired Woman Stares Through Mystery Hole 😱 #Shorts | When JK Came to Save His ARMY😱🥹 | 28.0s |
| 221 | oQ8eyaHAcNg | Maroon Hoodie Noodle Stunt Ignites Ring of Fire 😱🔥 #Shorts | He was much weaker than I thought😱🤣 | 18.5s |
| 241 | RXe3BT98J_c | Shaved Head Clip Battle Turns Bathroom Into Hair War 😱🔥 #Shorts | When he said he didn't like my hairstyle😱😭 | 27.8s |
| 261 | DEkCs4Afylg | Man Points at Store Entrance After Epic Toilet Paper Fail 😱🚪 #Shorts | He wants Toilet paper more than anyone🧻😬 | 38.0s |
| 281 | QwoJAeGOjhg | Man Hoists Crouching Woman Over Broken Egg 😱💥 #Shorts | He's still trying to put it back🌭💀 | 16.6s |
| 301 | ravCNdoDFRQ | The Confidence Was Real Until This 💀😭 #Shorts | How he tried to move my heart🥹💔😬 | 32.9s |
| 321 | 8_2Xkxfp0Zs | Only One Cheese Ball Survives the Pink Shirt Bite 😱🤯 #Shorts | Only 7 Cheese Balls Left🧀😳 | 20.1s |

## The 17 that never arrived (2026-11-10 → 11-15)

Jobs 341–661 all rendered fine (`RENDER_JOBS`: 46/46 completed; the
renders directory holds 153 files, ~1.6 GB) and all failed at upload
with the identical stored error: `RuntimeError: YouTube OAuth refresh
failed (RefreshError)` — the dead credential TASK-VYR-003 proved live.
The autopilot kept producing on schedule the entire time; only the
credential stopped it. This includes job 661, rendered and attempted
on 2026-11-15.

## The provenance rubber stamp

All 46 `SOURCES` rows carry the **identical** licence string —
"Transformative commentary - original creator credited (operator
policy)" — with `rights_verified = 1` and `repeat_use_allowed = 1`
for every row, and all 46 `ASSETS` rows are likewise
`rights_verified = 1`. That is a blanket self-attestation, not a
per-source licence check: no licence URL, no per-video evidence, and
the underlying material is other creators' commercial content, which
YouTube's reused-content policy covers even when the uploader
believes the use is transformative. This is the single largest
channel risk in the autopsy, and it is why TASK-VYR-004's flow
requires a real per-source provenance record (source URL, author,
licence, retrieval date) and why the pre-publish checklist in
`docs/PACKAGING.md` rejects this exact licence string.

## What cannot be known without API access — stated plainly

**No performance data exists locally, at all.** `VIDEO_METRICS` —
the table built to hold view/like/comment counts per video — contains
**0 rows**. `CONTENT_PACKS` also contains 0 rows. Nothing on either
server records a single view, like, comment, click-through, retention
second, or subscriber for any of the 46 videos.

Therefore, until the owner re-auths YouTube OAuth **and** a valid
Data API v3 key exists, the following are **unknowable**, and any
number offered for them would be invented:

* views, watch time, average view duration, retention curves;
* likes, comments, shares, subscribers gained or lost;
* traffic sources and audience geography (which drives RPM);
* Content ID claim / block status of any of the 29 uploads;
* whether any of the 29 were later published, edited, or deleted on
  YouTube (the database records privacy **at upload**: unlisted).

What *is* known is production truth only: what was made, from what,
how long it was, how it was packaged, when it uploaded, and why the
rest failed. Judged on packaging and provenance alone — the parts
measurable without the API — the owner's verdict on these videos
("not good") is consistent with the record: single-scene re-uploads
of other creators' viral clips, formula packaging, no hook design,
no selection signal, and a rubber-stamped rights record. The sync
defects the owner reported by ear were separately root-caused and
fixed by TASK-VYR-003.

## Lessons wired into the remix era

1. **Measure or it didn't happen.** The packaging checklist treats a
   missing measurement as a failed gate, and the remix flow must
   write `VIDEO_METRICS` rows once API access exists — an empty
   metrics table after 46 videos must never recur.
2. **Provenance is per-source evidence, not a policy sentence.**
3. **Packaging is a system, not a formula** — lanes, templates, hook
   archetypes, lints (`docs/PACKAGING.md`, `app/services/packaging.py`).
4. **Selection must record its reasoning** (query, source id, score) —
   three fields sat empty for all 46 projects.
