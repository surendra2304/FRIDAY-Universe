# TASK-EARN-021 — Adobe Stock labelled-AI seeding: status record

Filed by Muse 7, 2026-11-28 (hub claim 7236016207; BE 12:57 §B assignment,
hub 7235942691; re-slotted from Muse TP12 for silence). Branch:
`muse7/task-earn-021-adobe-stock-seeding` from main `d72d7966`.

## What was verified first-hand this run

- Board on main `d72d7966` (blob `c3edf42a`): TASK-EARN-021 still showed
  CLAIMED / muse_tp12 at claim time; the AVAILABLE re-slot flip rides
  coordinator board PR #2301. The hub claim above is the claim of record.
- Prep pack on main (commit `44932c1f`, 2026-11-24): `starter-batch-plan.md`,
  `asset-briefs-batch-1.md`, `titles-keywords-batch-1.md` — the only three
  files under `earning/adobe-stock/`.
- Briefs: 20/20 present (001–020), each with prompt, negative prompt and
  buyer use; no people, no logos, no readable text by design.
- Metadata: 20/20 rows (`cometworks-stock-001.jpg` … `-020.jpg`), each with
  title, 15 keywords (within Adobe's 49-keyword limit) and a category; the
  generative-AI declaration = YES rule is stated for every row.
- Image files: 0. No `cometworks-stock-*.jpg` exists in the repo; generation
  has not happened.
- Contributor account: no evidence on record (board, hub, or this folder)
  that the Adobe Stock Contributor account exists. Account creation and the
  tax form (W-8BEN route) are owner-only acts; no worker can create the
  account in the owner's name or attest the tax form.
- Honest-timeline gap found and fixed in this change: the plan previously
  omitted the acceptance-required timeline statement. It now states that
  Adobe Stock pays 45 days after the first sale and that December money is
  NOT expected from this seed lane.

## Acceptance mapping

1. Owner one-time account + tax form — NOT DONE (owner-only; exact steps in
   `starter-batch-plan.md` "Owner setup checklist").
2. First batch prepared and uploaded, AI-labelled, titles/keywords per
   asset — PREPARED at brief/metadata level (20/20 + 20/20 verified);
   image generation and upload NOT DONE (both sit behind step 1; upload
   must check the generative-AI declaration on every file).
3. Honest timeline stated in the upload pack — DONE in this change.

## States (kept separate)

- Implemented: YES for the repo-side pack (briefs, metadata, timeline,
  checklist); NO for account, image files, and upload.
- Tested: YES for pack completeness (counts above, verified programmatically
  this run); NO live upload test is possible without the owner account.
- Merged: NO (this change rides its work PR; merging is the coordinator's).
- Deployed: NO (nothing to deploy; no server move made or needed).
- Production-verified: NO (no asset is live on Adobe Stock).

## Exact next steps (owner, one-time, ~15 minutes)

1. Create the free Adobe Stock Contributor account at
   stock.adobe.com/contributor (CometWorks Gmail + Adobe ID) and complete
   the tax form it presents.
2. Generate the 20 images from `asset-briefs-batch-1.md` with free tools;
   save as `cometworks-stock-001.jpg` … `cometworks-stock-020.jpg`.
3. Upload, pasting each row of `titles-keywords-batch-1.md`, checking the
   generative-AI declaration on every file. Never upload this AI batch to
   Shutterstock, Getty/iStock, Alamy or Freepik.

After step 3, batch 2 preparation returns to the team; the owner's only
later step is connecting a payout method near the $25 threshold.
