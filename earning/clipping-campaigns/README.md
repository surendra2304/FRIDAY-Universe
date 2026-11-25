# Clipping-Campaign Lane — TASK-EARN-024 (Tracker + Hand-off, Preparation)

**Task:** TASK-EARN-024 — clipping-campaign lane: join Content Rewards / Whop /
clip.tech campaigns for GTA 6 clips, campaign tracker, first approved campaign
payout. Claimed by Muse TP5 2026-11-26 (hub #1483 comment 7173245221), branch
`musetp5/task-earn-024-clipping-campaigns`.

**This pack is preparation.** It builds everything that does not need the
owner's platform accounts: the campaigns tracker (`CAMPAIGNS-TRACKER.md`) and
the hand-off flow into the TASK-VYR-081 production pipeline
(`HANDOFF-FLOW.md`). The first submitted clip (deliverable 3) stays gated on
the owner's one-time accounts plus a live campaign brief. Nothing in this pack
joins a campaign, submits a clip, or touches a payout.

## How the lane works (board acceptance, read first-hand)

Clippers join campaigns on Content Rewards (contentrewards.com), Whop, and
clip.tech, cut clips from the streams each campaign brief allows, post them,
and are paid per approved view by the platform — not by YouTube. Method
sources: watches Df5V_2anUAj (@murphmaxxing), Df-NMPUFbEx (@startclipping),
Df6oHpmJ5Yz, as recorded in the TASK-EARN-024 board acceptance.

## Honest money math (source post's own figures — not live-verified)

The source post (Df5V_2anUAj) did the math so we do not have to guess: the
best real GTA 6 campaign it found pays **$2 per 1,000 views**, caps at
**$150 per clip**, and takes a **10% platform fee**. Influencer claims of $5K
per million views are called false by that same post. Other campaigns in its
table pay **$0.70–$1.00 per 1K** with **$35–$100 caps**. Volume is the whole
game; per-clip money is small. These are seed figures from the board
acceptance, **not live-verified rates** — the tracker records every unmeasured
field as unmeasured, never invented.

## Rights limits (binding on this lane)

- YouTube pays nothing on raw compiled clips (reused-content policy).
- Rockstar/Take-Two fan-content rules are non-commercial, with takedown at
  will. **Rockstar runs NONE of these campaigns.**
- Income exists only under each campaign platform's own terms, and clips are
  made **only** from the streams/footage a live campaign brief explicitly
  allows.
- Clips are produced by the TASK-VYR-081 pipeline in VyralX's model
  (narration, subtitles, BGM) — never raw re-uploads.

## The exact accounts the owner must create (one-time, owner-only)

From the board acceptance — the owner does this himself inside each platform;
**Muse never sees or handles payout credentials**:

1. **Whop** — account with cometbrowser001@gmail.com; complete payout setup
   in Whop settings.
2. **Content Rewards** — account with the same email; complete payout setup.
3. **clip.tech** — account with the same email; complete payout setup.
4. In each platform, connect the payout method it requires.

Until the accounts exist, the worker builds everything else — which is what
this pack is.

## Pack contents

- `CAMPAIGNS-TRACKER.md` — the campaigns tracker in the Df5V_2anUAj pattern:
  per campaign — platform, pay per 1K views, cap per clip, budget left,
  rules — ranked, refreshed on a stated cadence.
- `HANDOFF-FLOW.md` — tracker → TASK-VYR-081 production → campaign
  submission, with the pipeline's real function names and gates.

## Done criteria (board)

Done = tracker live with current campaigns ranked + first clip submitted
under a live campaign brief. First-money path: the first approved campaign
payout (small dollars by design — see the rate table above).

— Muse TP5, 2026-11-26
