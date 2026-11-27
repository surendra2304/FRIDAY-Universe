# TASK-EARN-036 — Contra portfolio sample 3: product descriptions (e-commerce before/after)

- **Task:** EARN: Contra portfolio sample 3 — product descriptions (e-commerce before/after), per profile-pack section 5.4.
- **Owner:** Muse TP9. **Claim:** hub #2045 comment 7208850829 (2026-11-27 ~09:10 IST), per WATCH197 §2 / WATCH198 §6 (EARN-036 → TP9).
- **Board verified:** AVAILABLE, owner null, P2, on main `690de63a` at claim time.
- **Branch:** `musetp9/task-earn-036` from main `4af777cc` (main moved between the claim post and the branch creation; the claim post's `690de63a` base is corrected here — branch verified via the branch API at `4af777cc`).
- **Method:** read-only live check of the public Contra profile + draft against `earning/contra/profile-pack.md` §5 item 4 and Service 4. No account access, no sign-in, no message, no booking, no paid tool.
- **States:** implemented YES (sample file) / tested YES (word counts measured, §2) / merged NO / deployed N/A (file ships via PR; attaching it to the Contra profile is the owner's one-time step) / production-verified NO (portfolio item goes live only when the owner attaches it).

## Verdict

**SAMPLE DRAFTED — NOT ALREADY LIVE.** The live Contra profile (https://contra.com/comet_5iw52nen, checked read-only 2026-11-27 ~09:20 IST, browser task `browser-task:f1499bff-6143-53ea-a20e-0d29f44b8afa`, ran 08:48–08:50 IST) shows 4 services and exactly 1 portfolio item — the 30-day social media content pack. No product-descriptions portfolio item exists: the "Product descriptions — benefit-led copy for your store listings" SERVICE is live ($20 Starter), but it carries no before/after sample, no three listings, no sample copy (its cover image shows three $12 price tags — artwork, not sample text). So the acceptance's first branch (already live → close with evidence) does not apply; the sample was drafted instead.

## §1 — Deliverable

`earning/contra/samples/product-descriptions-ecommerce-before-after.md` (+97 lines) — three store listings, each BEFORE (the seller's bare feature list) → AFTER (benefit-led copy) → "What changed, and why" (feature→benefit mapping, objection handled, keyword placement):

1. **Insulated water bottle** (Shopify-style) — keyword "insulated water bottle".
2. **Handmade lavender soy candle** (WooCommerce-style) — keyword "handmade soy candle".
3. **Notion budget planner template** (Payhip-style digital product) — keyword "budget planner template".

Each AFTER leads with the benefit, answers the buyer's silent objections, and places the keyword in the title + first line, matching Service 4 ("benefit-led opening, feature-to-benefit translation, objection-handling details, SEO keywords woven in naturally"). The three store types match the service's stated suitability (Shopify, WooCommerce, Amazon-style, Payhip/digital-product pages).

## §2 — Checks (measured first-hand, this run)

- **Word counts** (AFTER text including title, whitespace-split, punctuation-only tokens excluded): 97 / 99 / 98 — all within the Starter tier (up to 100 words each, $20). Headers in the file state the measured counts.
- **No invented claims:** burn time is "around 45 hours"; insulation times are the seller's own figures carried over from BEFORE; no review, ranking, follower or sales promise anywhere. Products are illustrative samples, not listings for real brands.
- **Blurb match:** the file's header quotes profile-pack §5 item 4 verbatim; the sample is ready to attach as the Contra portfolio item with that blurb.
- **Format precedent:** header + purpose/blurb block mirrors the existing `earning/contra/samples/youtube-script-7-moon-facts.md` (profile-pack §5 item 2 sample).
- **Repo state:** `earning/contra/samples/` previously held only the YouTube-script sample — no product-descriptions sample existed in-repo; nothing was duplicated or overwritten.

## §3 — Live profile state (browser read, 2026-11-27 ~09:20 IST)

- Headline: "SEO Blog Posts · YouTube Scripts · 30-Day Social Content". About: as in profile-pack §2 (shortened live version). Location Gajuvaka, India; "available for work"; $25–$50/hr.
- Services (4): Product descriptions ($20), 30-day social content ($20), YouTube script ($15), SEO blog post ($15).
- Portfolio (1 item): "30-day social media content pack for small businesses" (0 likes · 1 view · Nov 25, 2026) — the social-pack sample (EARN-035) is live; the product-descriptions sample is not.
- Owner step remaining: attach this file as the "Sample product descriptions (e-commerce)" portfolio item with the §5 item 4 blurb (profile-pack §6 item 5).

## §4 — Gaps / follow-ups

- **G1 — OPEN, owner step:** attach the sample to the Contra profile (owner's Contra account; no worker access). Closes when the portfolio shows the item.
- No board hunk in this PR — board flips are coordinator-only per WATCH182 §3. Paired verifier: none named yet — Muse to name one.

— Muse TP9
