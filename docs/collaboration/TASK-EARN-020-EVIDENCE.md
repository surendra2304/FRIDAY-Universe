# TASK-EARN-020 — itch.io Direct second product: evidence (Muse 1)

**Task:** TASK-EARN-020 — "EARN: itch.io Direct second product (owner order 2026-11-25: implement all) - owner account + tax interview, product page live from existing packs" (P2, queue position 3, earning lane)
**Claim:** hub #1483 comment 7181726076, 2026-11-26 ~08:56 IST (Muse 1), on coordinator assignment WATCH132 (7180339294) as amended by WATCH135 top-ups; STR-088 implementation in progress in parallel.
**Branch:** `muse1/task-earn-020-itchio-direct-product-2` @ main `036fb2da`
**Board record verified first-hand:** AVAILABLE / owner muse_1 / branch null / pr null on main `036fb2da` (board blob `53de3c97`, git blob sha match).

## 1. Product choice — from existing packs, missing pieces built only

The board offered two sources: the lead-magnet eBook from TASK-EARN-004, or the 30-day social content pack. I read the full repo tree on main `036fb2da` first-hand (recursive tree, not truncated):

- **The 30-day social content pack has no source file on main.** The only `30-day` path under `earning/` is `earning/bug-bounty/30-day-plan.md` (a bug-bounty plan, not a content pack). No Payhip/social-pack file exists anywhere under `earning/`. Building it would mean inventing a product, not building from an existing pack — so it was not chosen.
- **The lead-magnet eBook exists** at `earning/products/lead-magnet-ebook/the-7-day-email-list-starter-kit.md` (TASK-EARN-004, merged draft): 5 title options, full outline (~3,100 words planned), Chapter 1 drafted in full, CTA pages A + B, and Payhip/Contra listing copy. That is the base.

**Second product (this PR): "The 7-Day Email List Starter Kit"** under `earning/itchio/product-3/` — the complete eBook plus the Day 1 worksheet plus itch.io listing copy. It is distinct from product 2 (EARN-016, YouTube Creator Starter Pack, $14) and from the KDP ebook lane (EARN-022, separate task, not touched).

## 2. Verification — counts checked first-hand on main 036fb2da + on the new files (not trusted from the README)

| File | Claim | Verified |
|---|---|---|
| EARN-004 draft (main) — Chapter 1 | ~925 words, in the 800–1,000 band | **922 words confirmed** by count (heading included; the EARN-004 checkpoint's "925" is the same text within counting-method noise). Carried over verbatim into the new eBook — verified by string match, not retyped. |
| EARN-004 draft (main) — outline + CTAs | outline ~3,100 words; CTA pages A + B | **Confirmed** — outline table + chapter bullets + both CTA pages present; CTA pages carried over verbatim (string match). |
| `product-3/source/01-the-7-day-email-list-starter-kit.md` — complete eBook | intro + Ch1–6 + CTAs | **3,610 words confirmed** by count. Sections: Introduction 197, Ch1 922, Ch2 512, Ch3 433, Ch4 425, Ch5 395, Ch6 408, CTA pages 196. Chapters ran modestly over the outline's round targets (e.g. Ch2 512 vs ~450, Ch5 395 vs ~350) — actuals stated here, outline targets not repeated as fact. Section order verified: Intro, Ch1, Ch2, Ch3, Ch4, Ch5, Ch6, CTA A, CTA B. |
| `product-3/source/02-day-1-worksheet.md` | Day 1 worksheet, one printable page | **Confirmed** — the three Day 1 questions, the promise-sentence template, the three worked examples referenced, the format picker (checklist / template / short guide), and the result-named title prompt. |
| `product-3/README-listing.md` | complete listing copy | **Confirmed** — title ("The 7-Day Email List Starter Kit — From Zero Subscribers to Your First 100"), short tagline, **$9** price (pay-what-you-want OFF, min $9; net ~$7.54/sale after ~$0.56 processor fee + $0.90 default 10% itch.io share in Direct mode), full description with What's-inside / Who-this-is-for / What-this-is-not, **10 tags** (email-marketing, lead-magnet, ebook, creators, coaching, newsletter, content-creation, freelancing, marketing, productivity — itch.io's max), classification/settings suggestions, owner setup checklist. |

What was built here vs carried over: the Introduction and Chapters 2–6 are newly drafted in this task, following the outline's spec bullets in the EARN-004 file (Ch2 smallest format / one sitting / name after result; Ch3 one page one job; Ch4 three welcome emails with reply prompts; Ch5 five free sources; Ch6 honest free→paid path). Chapter 1 and the CTA pages are verbatim carry-over, not rewritten. No topic, audience or title was invented — all are the coordinator brief's spec (hub #1483 comment 7117142695, cited in the EARN-004 checkpoint).

## 3. First-money path — honest status, not buyable yet

Per itch.io's own payments documentation ("Accepting Payments and Getting Paid", read via web search this run), itch.io has **two** payout modes, and the board's shorthand "tax interview" covers only one of them:

- **Direct to you:** the seller manually connects each payment provider (Stripe and/or PayPal); money lands in the seller's own provider balance per sale; the seller is merchant of record and handles VAT/chargebacks; tax information goes to each payment provider, not to itch.io.
- **Collected by itch.io (Payouts):** no manual provider connection; the seller completes **one tax interview on itch.io** and accepts the seller terms; itch.io collects, and payouts are requested later (minimum $5, sales available 7 days after purchase, staff review typically 10–14 days, paid via PayPal or Payoneer).

**Blockers, stated plainly:**

1. **Payout setup is unverified and not done by me.** The board records the itch.io account `cometworks.in` as created 2026-11-25 — I have not verified that myself (no login, no account access, by rule) and I do not know whether the tax interview is complete or whether Stripe/PayPal is connected. Either the tax interview (Payouts mode) or a Stripe/PayPal connection (Direct mode) is required before the page can take money. This is the owner's one-time step.
2. **No product page is live.** The owner must upload the two `source/` files and publish from `README-listing.md`. Nothing was uploaded here — no login, no account creation, no platform touched.
3. **No test checkout has happened, so the lane is NOT claimed buyable.** The listing copy now tells the owner to run a test checkout before announcing the product. The first Direct sale remains the unproven step.

## 4. The remaining step — owner one-time actions (NOT this PR)

Create/confirm the itch.io account, complete the payout setup (tax interview OR Stripe/PayPal connection — see §3), upload the two files in `earning/itchio/product-3/source/`, paste the listing copy from `earning/itchio/product-3/README-listing.md`, publish, and run a test checkout. itch.io charges nothing upfront; it takes a revenue share only out of completed sales (seller-set, default 10%) — free-only rule honoured.

## 5. Five states

- implemented: YES — second product built and filed in this PR (complete eBook + worksheet + listing copy).
- tested: YES — counts verified first-hand (§2); this PR's CI is the proof the changed files are clean. No new tests were added, so the FUT-030 lesson (verify new tests actually ran) does not arise.
- merged: NO (Muse merges; this PR is the work PR).
- deployed: n/a — the upload + publish is the owner's one-time action (§4); no live change by me.
- production-verified: NO — no page is live, no test checkout has run, no first sale has happened (§3).

## 6. Board flip

EARN-020 AVAILABLE/muse_1 → IN_REVIEW (branch `muse1/task-earn-020-itchio-direct-product-2`, pr this PR). Flip built from the current main board blob (`53de3c97`, main `036fb2da`) and re-read before committing; only the EARN-020 record changes, verified by parse + diff. After this PR merges, the MERGED flip rides in the coordinator's board PR.

— Muse 1
