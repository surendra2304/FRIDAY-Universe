# TASK-EARN-023 — CHECKPOINT 2 (deliverable drafted)

- Worker: Muse TP6 — 2026-11-26 ~09:2x IST
- Branch: `musetp6/task-earn-023-swiggy-builders-club` @ main `7e4dea62` (branch recreated from current main; claim base was `5b703635`, see below)
- Hub claim: 7181154926
- Task: EARN — Swiggy Builders Club option (corpus reel DYg_b2ZTK70, @lavin_creator)

## Stall repaired

- Branch sat at checkpoint 1 (`49d47e58`, ~08:20 IST) with no new commit for ~1h at the 09:13 IST self-check. This checkpoint files the deliverable itself as the repair.

## What was verified first-hand this run

- Live public pages, 2026-11-26 ~09:17–09:18 IST (read-only browser check, nothing filled in or submitted, no sign-in, no personal data entered):
  - `https://mcp.swiggy.com/builders` — 4 MCP servers (Food, Instamart, Dineout, Scenes), 62 API tools, builders@swiggy.in; path to prod as in checkpoint 1.
  - `https://mcp.swiggy.com/builders/access/` — "Apply for Production Access": two tracks (Developer / Enterprise-Startup), 12-item application checklist, 5-item review list, ground rules, enterprise turnaround 4+ weeks.
  - Developer form (https://forms.gle/4vkeKyqm15Qb6fnJA): "Swiggy Builders Club - Developer Application", ~5 minutes, Google Form, sign-in required to submit; all 15 first-page fields read verbatim (fields 1–15 in the pack). A "Next" button implies further pages, not viewable without filling in answers and signing in.
  - Enterprise form (https://forms.gle/U6hYGYLYWQPHWY826): redirects straight to Google sign-in; fields not readable under the no-sign-in constraint. Not the track for this application (individual developer), so no loss.

## Deliverable filed

- `earning/TASK-EARN-023-SWIGGY-BUILDERS-CLUB-PACK.md` — one-page prototype concept (FRIDAY Food: voice ordering via Swiggy Food + auto-restock via Swiggy Instamart, voice confirmation on every order) + field-for-field application answers for the Developer track + brief drafts for the access-page checklist items.
- House pattern followed (cf. `earning/TASK-EARN-028-PITCH-PACK.md`): OWNER ONE-TIME called out, [VERIFY]/[DRAFT]/[OWNER TO FILL] marks on anything unproven or owner-owned, no invented facts.

## Honest blockers on submission (owner-side, not TP6's to clear)

- **No demo video exists** — the form requires a Working Demo Video Link (field 14). The application cannot be submitted until a prototype is built and a demo recorded.
- **No production deployment exists** — the form requires Production Redirect URIs (field 12); localhost URIs must not be entered there.
- **Owner personal fields** (email, full name, LinkedIn) are [OWNER TO FILL]; TP6 does not submit the form.

## Branch note (why recreated)

- Claim branch was created at main `5b703635`; main has since moved through the watch134/135/136 board PRs to `7e4dea62`. A board flip PUT on the stale base would have reverted those board PRs, so the branch was deleted and recreated at `7e4dea62` under the same name (STR-086 precedent, PR #1840 → #1863), and checkpoint 1 re-filed byte-identical plus the pack and this checkpoint. Hub claim 7181154926 still names the same branch.

## Board

- Main `7e4dea62` verified first-hand (blob `89253513`): TASK-EARN-023 AVAILABLE / muse_tp6 / branch null / pr null.
- Board flip rides this work PR per WATCH136 (claim PRs abolished): AVAILABLE → CLAIMED, branch `musetp6/task-earn-023-swiggy-builders-club`, pr = this work PR number.

## Next

- Work PR open (this branch). Merge is the coordinator's call (peer merge only; TP6 never merges its own PR).
- After merge: owner one-time — confirm drafts, build localhost prototype, record demo, deploy, fill personal fields, submit the Developer form. If Swiggy declines or never replies, close with that verdict recorded.
