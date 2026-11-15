# Publish priority: which ready video goes public first (TASK-VYR-010)

Code: `app/services/publish_priority.py` · Tests:
`tests/test_vyr010_publish_priority.py` · Model version `vyr010-1` ·
Input snapshot: `docs/publish_priority_input_2026-11-15.json`
(production rows read 2026-11-15 via read-only SELECT probes — the
same evidence base as `docs/AUTOPSY_29_UNLISTED.md`; nothing was
uploaded, scheduled, or made public by this task).

## The question

The day the owner's YouTube re-auth lands, VyralX holds a pool of
already-made videos: 29 uploaded-but-unlisted shorts (2026-11-03 →
11-09) and 17 more that rendered fine and only failed at upload when
the OAuth credential died (11-10 → 11-15). Publishing all 46 at once
would bury the strongest under the weakest. This model ranks the
pool so the strongest publish first.

## The honest headline: there is no performance data

Stated before the model, because it bounds everything after it:

* `VIDEO_METRICS` — the table built to hold views/likes per video —
  contains **0 rows**. `CONTENT_PACKS` also contains **0 rows**.
  No view, like, comment, watch-second, or retention figure exists
  for any of the 46 videos, anywhere on either server.
* Selection recorded nothing either: `trend_score` is 0.0 for all 46
  projects; `trend_query` and `trend_source_video_id` are empty for
  all 46. Even the fact that the sources were viral is unquantified —
  no source view counts were ever stored.
* The videos are **unlisted**: they had no audience by design, so
  even a working API today would show near-zero engagement that
  reflects the privacy setting, not the content.

**Therefore this is not a performance predictor and must not be
called one.** It is a transparent heuristic over production metadata,
in the spirit of the TASK-VYR-005 packaging system: stated weights,
deterministic scoring, every component visible per video so the
order can be argued with. Its accuracy is unknowable until real
metrics exist; the moment they do, the model's `engagement`
component (weight 0.35, currently never firing) activates and the
heuristic must be re-validated against reality or replaced.

## The model

Five metadata components, each 0..1, weighted and renormalised over
whichever components exist for a video (missing data is reported in
the row's `missing` list — never invented, never silently zeroed):

| Component | Weight | What it reads | Basis |
|---|---:|---|---|
| `duration_fit` | 0.30 | Render duration | <15s too thin to retain; 25–45s is the band the researched formats target; >60s leaves Shorts and hits the claim-block line |
| `title_strength` | 0.30 | Upload title | PACKAGING.md rules as scores: ≤60 chars, 1–2 emoji, a concrete anchor, a curiosity device, and clarity (the autopsy era's multi-fragment word-salads are penalised) |
| `source_signal` | 0.20 | Source video's title | The only demand proxy that exists — the source was viral, but its virality was never recorded, so this reads only its title's packaging markers. Weakest-evidence component; labelled a proxy everywhere |
| `format_fit` | 0.10 | Width × height | 1080×1920 is the pool standard; the one 480×600 outlier and any non-vertical render are defects |
| `freshness` | 0.10 | Creation time within the pool | A tiebreak with a deliberately narrow spread (0.6–1.0): newer is not better, merely closer to the current pipeline |

`engagement` (views/likes, log-scaled) exists in the code at weight
0.35 and is **inactive for this entire pool** — coverage 0/46.

Tiers: A ≥ 70 (publish first), B 55–70, C < 55.

## Flags that outrank the score

Every legacy row carries flags the score cannot clear:

* **HOLD_PROVENANCE** (all 46): the pool's only licence record is
  the blanket string *"Transformative commentary - original creator
  credited (operator policy)"* — a self-attestation the
  TASK-VYR-005 pre-publish checklist rejects by name. The ranking
  orders the queue; it does not clear this hold. Under the owner's
  current direction (researched lanes, per-source PD/CC provenance),
  the realistic fate of most of this pool is retirement, not
  publication — the ranking exists so that whatever *is* cleared,
  in whatever subset, goes out strongest-first.
* **SYNC_UNVERIFIED** (all 46): every legacy render predates the
  TASK-VYR-003 sync fix; the one production render ever measured had
  73.6% narration coverage and captions late by up to 1.5s. No
  per-video sync measurement exists in stored data.
* **METRICS_NO_DATA** (all 46): see the headline above.
* **NOT_UPLOADED** (17): rendered, never reached YouTube — these
  need an upload, not a privacy flip, when the credential returns.

## The ranking (2026-11-15 pool)

| Rank | Job | YouTube ID | Score | Tier | Dur | Title | Src | Fmt | Fresh | Flags | Upload title |
|---:|---:|---|---:|:--:|---:|---:|---:|---:|---:|---|---|
| 1 | 61 | SCd4k8TumuI | 85.5 | A | 0.96 | 0.87 | 0.70 | 1.00 | 0.66 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Guy Covers His Face After Phone Shock 😱📱 #Shorts |
| 2 | 1 | rE2wCU6bYAk | 85.0 | A | 0.87 | 0.87 | 0.85 | 1.00 | 0.60 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Rescue Mission Gone Wrong: Kitchen Chaos Unleashed 😱🚒 #Shorts |
| 3 | 661 | (not uploaded) | 84.8 | A | 0.82 | 0.77 | 0.85 | 1.00 | 1.00 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | My Secret Chocolate Mission! 🤫 😱🔥 #Shorts |
| 4 | 301 | ravCNdoDFRQ | 84.4 | A | 0.88 | 0.87 | 0.70 | 1.00 | 0.79 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | The Confidence Was Real Until This 💀😭 #Shorts |
| 5 | 641 | (not uploaded) | 84.0 | A | 0.98 | 0.70 | 0.70 | 1.00 | 0.98 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | This Looks Terrifying 🫣 😱🔥 #Shorts |
| 6 | 601 | (not uploaded) | 83.9 | A | 0.98 | 0.80 | 0.55 | 1.00 | 0.95 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Center Student Strikes Hip Pose Then Crashes 😂💥 #Shorts |
| 7 | 102 | ijP1b4U9zO8 | 83.6 | A | 0.95 | 0.80 | 0.70 | 1.00 | 0.70 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Woman Waves Red Lipstick Beside White Car 😱🚗 #Shorts |
| 8 | 501 | (not uploaded) | 83.1 | A | 0.85 | 0.72 | 0.85 | 1.00 | 0.90 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Yellow Shirt Guy Flips Pink Girl Over Orange Fruit 🍊🚀 #Shorts |
| 9 | 2 | v63Knfew8Z8 | 82.5 | A | 0.95 | 0.80 | 0.70 | 1.00 | 0.60 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | He Claims His Machine Beats Light Speed 🚀😱 #Shorts |
| 10 | 261 | DEkCs4Afylg | 82.4 | A | 0.93 | 0.76 | 0.70 | 1.00 | 0.77 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Man Points at Store Entrance After Epic Toilet Paper Fail 😱🚪 #Shorts |
| 11 | 41 | sNXEKVlSUrQ | 81.3 | A | 0.80 | 0.80 | 0.85 | 1.00 | 0.63 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Gravity Flip Sends Crowd Into Chaos 😱🔥 #Shorts |
| 12 | 481 | (not uploaded) | 81.1 | A | 0.95 | 0.65 | 0.70 | 1.00 | 0.90 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | She Was Fooled In The End😱🙄 😱🔥 #Shorts |
| 13 | 621 | (not uploaded) | 80.6 | A | 0.97 | 0.70 | 0.55 | 1.00 | 0.96 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Dashboard Panic As Car Skims Guardrail 🚗⚠️ #Shorts |
| 14 | 201 | udAJT1B-HB4 | 80.4 | A | 0.83 | 0.80 | 0.70 | 1.00 | 0.75 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Pink‑Haired Woman Stares Through Mystery Hole 😱 #Shorts |
| 15 | 541 | (not uploaded) | 80.2 | A | 0.94 | 0.80 | 0.45 | 1.00 | 0.92 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Pink Sari Showdown: Tongue‑Out Pose Shocks Viewers 😱✨ #Shorts |
| 16 | 321 | 8_2Xkxfp0Zs | 79.8 | A | 0.65 | 0.84 | 0.85 | 1.00 | 0.80 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Only One Cheese Ball Survives the Pink Shirt Bite 😱🤯 #Shorts |
| 17 | 3 | eId2hMpgXFA | 79.7 | A | 0.86 | 0.80 | 0.70 | 1.00 | 0.60 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Pillow Chase Turns Hallway Into Runway 😱✨ #Shorts |
| 18 | 181 | ySBPklkYFQ0 | 79.6 | A | 0.81 | 0.80 | 0.70 | 1.00 | 0.74 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Yoga Stretch Turns Into Weight Shock 😱🤯 #Shorts |
| 19 | 103 | XW7dYQElJDQ | 79.2 | A | 0.81 | 0.80 | 0.70 | 1.00 | 0.70 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Man Lies with Drill, Woman Grips Him 😱✨ #Shorts |
| 20 | 561 | (not uploaded) | 78.3 | A | 0.80 | 0.80 | 0.55 | 1.00 | 0.93 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Yellow Hard Hat Meets Toy Excavator Chaos 😱🚧 #Shorts |
| 21 | 5 | MFv1_qcx-Mk | 77.7 | A | 0.62 | 0.87 | 0.85 | 1.00 | 0.60 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Smartphone Food Photo vs Real Plate Switch 🤯 #Shorts |
| 22 | 241 | RXe3BT98J_c | 77.7 | A | 0.83 | 0.71 | 0.70 | 1.00 | 0.77 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Shaved Head Clip Battle Turns Bathroom Into Hair War 😱🔥 #Shorts |
| 23 | 341 | (not uploaded) | 77.2 | A | 0.79 | 0.80 | 0.55 | 1.00 | 0.84 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Girl's Ice Cream Selfie Disaster on Motorcycle 😱📸 #Shorts |
| 24 | 4 | 5O-zcwIWnq8 | 76.9 | A | 0.74 | 0.72 | 0.85 | 1.00 | 0.60 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Crazy Creamy Egg Toast Shocked My Taste Buds 😱🔥 #Shorts |
| 25 | 161 | WWKjBdNN5uk | 76.7 | A | 0.71 | 0.80 | 0.70 | 1.00 | 0.73 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Massive Confetti Cannon Explosion Shocks Everyone 😱💥 #Shorts |
| 26 | 101 | rioS2ab0YKs | 75.5 | A | 0.69 | 0.80 | 0.70 | 1.00 | 0.69 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Orange‑Haired Girl Leaps Onto Bed With Handbag 😱🤯 #Shorts |
| 27 | 461 | (not uploaded) | 74.8 | A | 0.83 | 0.80 | 0.55 | 0.60 | 0.89 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Black Hoodie Ladder Climb Defies Gravity 😱✨ #Shorts |
| 28 | 42 | qkXyrPQyc54 | 74.7 | A | 0.59 | 0.89 | 0.70 | 1.00 | 0.64 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | She Did NOT See That Coming 😱😂 #Shorts |
| 29 | 141 | D3ICu0s8m6M | 74.6 | A | 0.76 | 0.69 | 0.70 | 1.00 | 0.72 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Spider‑Man Tied To Chair While Orange‑Shirt Girl Sips Cup 😱🤯 #Shorts |
| 30 | 441 | (not uploaded) | 74.1 | A | 0.66 | 0.72 | 0.70 | 1.00 | 0.88 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Tree Hug, Car Phone Shout, Mirror Towel Hug 😱🤯 #Shorts |
| 31 | 7 | g5bx8HTy-nw | 74.0 | A | 0.66 | 0.80 | 0.70 | 1.00 | 0.61 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | His Reaction Says Everything 😂💀 #Shorts |
| 32 | 81 | of7cKrPk1Eg | 73.7 | A | 0.71 | 0.72 | 0.70 | 1.00 | 0.67 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Lighter Ignites Wallet as Sticky Hand Holds Flame 😱🔥 #Shorts |
| 33 | 43 | hX2pDrW7o0U | 73.0 | A | 0.64 | 0.68 | 0.85 | 1.00 | 0.64 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Closet Reach Meets Car Window Slam and Toilet Head Surprise 😱🚗 #Shorts |
| 34 | 21 | KUcWZdBE6po | 72.9 | A | 0.62 | 0.80 | 0.70 | 1.00 | 0.62 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Hallway Hand‑Off: Maroon Man Carries Pink Woman 😱🚀 #Shorts |
| 35 | 401 | (not uploaded) | 72.8 | A | 0.50 | 0.74 | 0.85 | 1.00 | 0.86 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Ronaldo & Elon Musk: +99999 Missed Calls📞☄️ 😱🔥 #Shorts |
| 36 | 121 | Ga73ufVsZDg | 72.6 | A | 0.69 | 0.69 | 0.70 | 1.00 | 0.71 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Blue‑Shirt Guy’s Pastry Tray, Wig Dive & Egg Carton Face 😱🤯 #Shorts |
| 37 | 281 | QwoJAeGOjhg | 72.3 | A | 0.55 | 0.80 | 0.70 | 1.00 | 0.78 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Man Hoists Crouching Woman Over Broken Egg 😱💥 #Shorts |
| 38 | 381 | (not uploaded) | 72.2 | A | 0.62 | 0.80 | 0.55 | 1.00 | 0.85 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Maximum Main Character Energy 💀😂 #Shorts |
| 39 | 221 | oQ8eyaHAcNg | 71.3 | A | 0.60 | 0.72 | 0.70 | 1.00 | 0.76 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Maroon Hoodie Noodle Stunt Ignites Ring of Fire 😱🔥 #Shorts |
| 40 | 521 | (not uploaded) | 70.2 | A | 0.65 | 0.65 | 0.60 | 1.00 | 0.91 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Acchi Lag Rahi Hu Na ❤️🤔 😱🔥 #Shorts |
| 41 | 82 | KeOl3n0BahU | 69.6 | B | 0.49 | 0.80 | 0.70 | 1.00 | 0.68 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Striped‑Top Stare Meets Blazing Orange Blur 😱🔥 #Shorts |
| 42 | 421 | (not uploaded) | 69.5 | B | 0.58 | 0.65 | 0.70 | 1.00 | 0.87 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Someone Save His Arms, Legs, And Head🦾🦿🤖 😱🔥 #Shorts |
| 43 | 361 | (not uploaded) | 68.9 | B | 0.49 | 0.72 | 0.70 | 1.00 | 0.84 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Mickey Mouse Tank Top Girl Faces Dark Floor Sweep 😱✨ #Shorts |
| 44 | 6 | GEJjgDwYidA | 68.6 | B | 0.68 | 0.60 | 0.70 | 1.00 | 0.60 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | Steak Plate Switch From Kitchen to Beach to Bathroom 😱🍽️ #Shorts |
| 45 | 62 | jLnrAHNMhYk | 68.4 | B | 0.64 | 0.62 | 0.70 | 1.00 | 0.66 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA | White Shirt Pavement Pose Meets Cozy Couch Yawn and Car Kiss 😱✨ #Shorts |
| 46 | 581 | (not uploaded) | 68.4 | B | 0.61 | 0.72 | 0.45 | 1.00 | 0.94 | HOLD_PROVENANCE, SYNC_UNVERIFIED, METRICS_NO_DATA, NOT_UPLOADED | Pink Sari Flower Parade Turns Into Laughing Burst 😱✨ #Shorts |

*Reading this ranking: the pool is formula-identical, so scores cluster tightly (68.4–85.5 across all 46). Treat adjacent ranks as effectively tied; the robust signal is top-quartile versus bottom-quartile. Tier A (≥70) holds 40 videos and tier B the remaining 6 — the tiers are coarse by design; the publish order is the deliverable, not the tier.*

## What would make this model real

1. Owner re-auths YouTube OAuth and publishes the consent screen
   out of Testing status; a valid Data API v3 key lands
   (both already on the owner's deferred list).
2. A metrics job populates `VIDEO_METRICS` for the pool (the
   follow-up TASK-VYR-005 already recorded) — even unlisted-era
   numbers would calibrate the metadata weights.
3. New remix-era videos arrive with per-source provenance, sync
   measurements, and recorded selection signals — at which point
   this heuristic should be re-fit or retired in favour of measured
   performance, and this doc updated with what the data showed.
