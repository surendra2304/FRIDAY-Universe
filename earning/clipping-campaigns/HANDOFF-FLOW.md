# Hand-off Flow — Tracker → TASK-VYR-081 Production → Campaign Submission

Deliverable (2) of TASK-EARN-024: how a ranked campaign in
`CAMPAIGNS-TRACKER.md` becomes a submitted clip. The production target already
exists and is merged: `VyralX/app/services/gta6_series.py` (TASK-VYR-081,
series `gta6-clips`, version `vyr081-1`). Function names and thresholds below
were read first-hand from that file on main, 2026-11-26.

## The flow

### 1. Pick from the tracker — live brief or nothing

- Take the top-ranked campaign in `CAMPAIGNS-TRACKER.md` **that has a live
  brief**. The brief must explicitly allow the footage to be clipped.
- Record the brief (platform, campaign, allowed footage, pay/1K, cap, rules)
  in the tracker row at the next refresh. No live brief → no production.

### 2. Footage provenance gate (fail-closed, before any work)

- Campaign footage enters the pipeline only as
  `footage_source="earn024_campaign"`. The only permitted provenances are
  `FOOTAGE_SOURCES = ("own_capture", "earn024_campaign")`.
- `validate_footage_source(source)` rejects anything else with a
  `ValueError` before any work starts. Third-party streamer footage outside
  a campaign brief is never permitted (`FOOTAGE_RULE`).

### 3. Moment-finding and cut plan

- `find_moments(...)` — ffmpeg ebur128 audio-spike detection plus
  scene-filter cuts; moments are 8–59 s, at most 5 per pass.
- `plan_episode_cut(...)` — the 9:16 vertical-cut plan for the chosen
  moment.

### 4. Series render gate (fail-closed)

`gate_series_episode(...)` applies the standing machine-QA gates; any
unmeasured input fails the gate:

- **Captions:** exactly one caption track (via `viral_quality`).
- **BGM:** present (mandatory, ducked under narration).
- **Watermark:** verified.
- **Loudness:** −24 to −10 LUFS, true peak at most −1.0 dBFS.
- **Blank check:** VYR-061 blank self-verification over the signal scan's
  black intervals.
- **Bad takes:** VYR-060 verdict — advisory when absent, fails the gate when
  present with bad takes.

Series model throughout (`SERIES_MODEL`): short excerpts, her English
narration over the clip, source voice ducked under hers, subtitles ALWAYS
on, BGM mandatory and ducked, unlisted + review-first, renders held for the
owner.

### 5. Episode record — held, never auto-published

- `build_series_episode(...)` returns `held_for_review` only when the gate
  passed (otherwise `rejected` with the reason carried). Privacy is
  `unlisted`, `publish` is `False`, `review_first` is `True` — nothing
  publishes from the pipeline.
- `episode_qa_evidence(episode)` produces the compact QA evidence filed with
  the review.

### 6. Owner review, then campaign submission

- The held episode goes to the owner for review first. Only an approved
  episode is submitted, and only under the live brief it was cut for, on the
  campaign's own platform.
- Submission and any payout happen inside the platform under the owner's
  account. Muse never sees or handles payout credentials.

## Gates that stop the flow (by design)

| Gate | Stops when |
|---|---|
| Live brief | No live brief, or brief does not allow the footage |
| `validate_footage_source` | Provenance is not `own_capture` / `earn024_campaign` |
| `gate_series_episode` | Any check unmeasured or failed (captions, BGM, watermark, loudness, blank, bad takes) |
| Owner review | Episode not approved |
| Owner accounts | Whop / Content Rewards / clip.tech accounts + payout setup do not exist yet (deliverable 3 gate) |

## Honest limits (carried from the pipeline and the board)

- YouTube pays NOTHING on raw compiled clips (reused-content policy);
  Rockstar/Take-Two fan-content rules are non-commercial with takedown at
  will. Any money attached to GTA 6 clips comes only through TASK-EARN-024
  campaign platforms under their own terms, never from YouTube revenue on
  the clips (`HONEST_LIMITS` in `gta6_series.py`).
- Deliverable (3) — first clip submitted under a live brief — remains gated
  on the owner one-time accounts plus a live brief. This flow is ready; the
  accounts are the owner's step.

— Muse TP5, 2026-11-26
