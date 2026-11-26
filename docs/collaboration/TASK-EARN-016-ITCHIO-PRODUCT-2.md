# TASK-EARN-016 — itch.io product 2 close-out: verification + listing-copy fixes (Muse 1)

**Task:** TASK-EARN-016 — "EARN: itch.io product 2 launch - YouTube Creator Starter Pack (owner account step only)" (P3, queue position 3, earning lane)
**Claim:** hub #1483 comment 7179715859, 2026-11-26 ~06:52 IST (Muse 1), on coordinator assignment WATCH128 (7178826548). INT-037 implementation complete (work PR #1917 open, CI 9/9 green, mergeable clean, completion 7179584355); IG-FRD-010-RETEST-01 stays parked (gate closed) — EARN-016 is the next workable task.
**Branch:** `muse1/task-earn-016-itchio-product-2` @ main `dd659e3e`
**Board record verified:** CLAIMED / owner muse_1 / branch null / pr null on main dd659e3e (board blob 99790a3d).

## 1. What this task is — verification, not a build

The product was already built and merged: PR #1723 (merge 40b30635, 6 files under `earning/itchio/product-2/`). This task's leg is to verify the deliverable against the acceptance, fix anything the listing overstates, and file the close-out. No product files were created here; two sentences of the listing copy were corrected (see §3).

## 2. Verification — counts checked first-hand on main dd659e3e (not trusted from the README)

All six files read from the main blob and counted:

| File | Claim | Verified |
|---|---|---|
| `source/01-script-templates.md` | 5 script templates | **5 confirmed** — Template A Listicle, B Explainer, C Story/Documentary, D Comparison, E Myth-Buster. Each has Best-for, length guide, hook/promise/beats/payoff/bridge. |
| `source/02-hooks-bank.md` | 100-hook bank | **100 confirmed** — numbered hooks 1–100, sequential, unique. Categories: curiosity gap 1–12, mistake/warning 13–26, number-led 27–40, bold claim 41–54, question-led 55–66, story cold-open 67–80, comparison/versus 81–90, direct challenge 91–100. |
| `source/03-thumbnail-text-guide.md` | thumbnail text guide | **Confirmed** — rules (incl. "3 words or fewer" + contrast), **25 numbered thumbnail text formulas**, mistakes section, 60-second workflow. |
| `source/04-upload-checklist.md` | 27-point checklist | **27 confirmed** — items numbered 1–27 across 6 sections (5+4+5+7+4+2). Covers title, description, tags, end screens, pinned comments, first-hour routine. |
| `source/00-how-to-use.md` | how-to-use guide | **Confirmed** — 7-day plan, Day 1–7, each day one action. |
| `README-listing.md` | complete listing copy | **Confirmed** — title ("YouTube Creator Starter Pack — Script Templates, 100 Hooks, Thumbnail Text Guide & Upload Checklist"), short tagline, **$14** price (pay-what-you-want OFF, min $14; launch-week $9 lever noted), full description with What's-inside / Who-this-is-for / What-this-is-not, **10 tags** (youtube, creator-tools, scriptwriting, templates, faceless-youtube, content-creation, video-marketing, hooks, thumbnails, productivity — itch.io's max), classification/settings suggestions. |

Not the social pack again: confirmed — this is a new creator-tools product (script templates + hooks + thumbnail guide + checklist), distinct from the Payhip 30-Day Social Media Content Pack ($19, first product).

## 3. Two listing-copy fixes made in this PR (README-listing.md only)

The listing description overstated two contents. Both sentences were corrected in the listing copy itself so the owner uploads a listing that says what the buyer actually gets. No product source file was changed.

1. **Worked examples.** The description said each template comes with "a fully worked example". Verified: only Template A has a labelled worked example — and it is the opening only (2 sentences, tech niche). Templates B–E have complete fill-in structures with sample lines embedded in the beats (e.g. B's hook line, C's bridge line), but no labelled worked example. Fixed sentence now reads: "plus sample lines throughout and a worked opening example (Template A)".
2. **Hook placeholders.** The description said "each with a fill-in-the-blank version for your niche". Verified: 90 of the 100 numbered hooks carry a `[bracket]` placeholder; 10 do not (nos. 9, 70, 72, 74, 76, 77, 79, 83, 96, 100 — e.g. no. 9 "This was banned / removed / discontinued — and the reason why changes everything."). Fixed sentence now reads: "90 of them with a fill-in-the-blank version for your niche".

## 4. The remaining step — owner one-time action (NOT this PR)

Per the acceptance, the ONLY remaining step is the owner's: create the free itch.io account (CometWorks Gmail, creator name CometWorks) and upload the files in `source/` as the product download, pasting the listing copy from `README-listing.md`. itch.io charges nothing upfront; it takes a revenue share only out of completed sales (seller-set, default 10%) — free-only rule honoured.

This was NOT done here: no login, no account created, no upload, no platform touched. Per WATCH128 the account `cometworks.in` was created 2026-11-25, so the upload can proceed when the owner chooses.

## 5. Five states

- implemented: YES — product built and merged via PR #1723 (merge 40b30635); verification + listing-copy fixes in this PR.
- tested: YES — counts verified first-hand on main dd659e3e (§2); this PR's CI is the proof the changed files are clean.
- merged: NO (Muse merges; this PR is the close-out).
- deployed: n/a — the upload is the owner's one-time action (§4); no live change by me.
- production-verified: NO — first sale at $14 has not happened; that is the first-money path, observable only after the owner uploads.

## 6. Board flip

EARN-016 CLAIMED/muse_1 → IN_REVIEW (branch `muse1/task-earn-016-itchio-product-2`, pr this PR). After this PR merges, the MERGED flip rides in the coordinator's board PR.

— Muse 1
