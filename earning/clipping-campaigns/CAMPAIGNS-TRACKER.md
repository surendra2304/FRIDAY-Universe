# Campaigns Tracker — TASK-EARN-024

Tracker in the Df5V_2anUAj pattern (board acceptance): per campaign —
platform, pay per 1K views, cap per clip, budget left, rules — ranked by
budget left, refreshed on a stated cadence.

**Seed date:** 2026-11-26. **Seed source:** TASK-EARN-024 board acceptance,
which records the Df5V_2anUAj (@murphmaxxing) table. **Seed figures are
source-derived, NOT live-verified.** Live budget-left and the current
campaign list cannot be verified without the owner's one-time accounts
(Whop / Content Rewards / clip.tech + payout setup — owner-only; Muse never
sees or handles payout credentials). Every unmeasured field below reads
UNMEASURED. Nothing is invented.

## Ranking basis (honest interim)

The board spec ranks by **budget left**. Budget left is unmeasured for every
row until the owner accounts exist, so this seed table is ranked by **pay
per 1K views** as an interim basis, labelled as such. The first refresh after
accounts exist re-ranks by measured budget left and replaces this note.

## Seed table (2026-11-26, source-derived, not live-verified)

| # | Campaign (as recorded in source) | Platform | Pay / 1K views | Cap / clip | Platform fee | Budget left | Status |
|---|---|---|---|---|---|---|---|
| 1 | Best GTA 6 campaign in Df5V_2anUAj table | UNMEASURED (one of Content Rewards / Whop / clip.tech) | $2.00 | $150 | 10% | UNMEASURED | Seed row — verify live after accounts |
| 2 | Other GTA 6 campaigns in Df5V_2anUAj table (range) | UNMEASURED (one of Content Rewards / Whop / clip.tech) | $0.70–$1.00 | $35–$100 | UNMEASURED | UNMEASURED | Seed range — split into per-campaign rows on first live refresh |

Notes on the seed rows:

- The source post calls influencer claims of $5K per million views false;
  do not use them for planning.
- Per-clip money is small; volume is the whole game (board acceptance).
- A campaign only becomes actionable when a **live brief** names the footage
  it allows. No brief, no clip — see `HANDOFF-FLOW.md`.

## Rules that bind every row (board acceptance)

- Clips are made **only** from streams/footage a live campaign brief
  explicitly allows.
- Clips are produced by the TASK-VYR-081 pipeline (narration, subtitles,
  BGM) — never raw re-uploads.
- YouTube pays nothing on raw compiled clips (reused-content policy);
  Rockstar/Take-Two fan-content rules are non-commercial with takedown at
  will; Rockstar runs NONE of these campaigns. Income exists only under each
  platform's own terms.

## Refresh cadence (stated, binding)

- **First live refresh:** as soon as the owner accounts exist — replace seed
  rows with per-campaign rows read from each platform (campaign name,
  platform, pay/1K, cap, fee, budget left, brief link, rules), re-rank by
  budget left, date-stamp the refresh.
- **Standing cadence after that:** weekly, plus an out-of-cycle refresh
  whenever a campaign is joined, a brief changes, or a clip is submitted.
- **Staleness rule:** any row not re-measured at a refresh is marked STALE
  with its last-measured date. Stale figures are never silently carried
  forward as current.
- **Unmeasured rule:** a field that cannot be read is recorded UNMEASURED.
  No estimated budgets, no guessed rates.

## What "current campaigns ranked" still needs

1. Owner one-time accounts (Whop / Content Rewards / clip.tech + payout
   setup — owner-only).
2. First live refresh per the cadence above.
3. A live brief on the top-ranked campaign → hand-off to TASK-VYR-081
   production (`HANDOFF-FLOW.md`) → first submitted clip (deliverable 3).

— Muse TP5, 2026-11-26
