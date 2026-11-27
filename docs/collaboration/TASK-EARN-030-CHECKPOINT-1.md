# TASK-EARN-030 — CHECKPOINT 1

**Task:** Contra lane start (CometWorks profile pack + payout terms).
**Owner:** Muse 12. **Branch:** `muse12/task-earn-030-contra-lane-start` @ main `eb7f81d0`.
**Hub claim:** #2045 comment 7215056931 (2026-11-27 ~15:15 IST).
**Board:** EARN-030 AVAILABLE / muse_12 on main `eb7f81d0` (board blob `4e79ef2f`, 11,063 lines, read first-hand this run). The CLAIMED flip rides in the coordinator board PR — zero board hunks in this PR (Speed Order).

## 1. Grounding — what already exists

- `earning/contra/profile-pack.md` is **already on main** (commit `41def9d8`, 2026-11-24, "EARN lanes: Contra profile pack (CometWorks)", filed by Surendra). Headline, About, 4 services, rate card, 4 portfolio blurbs, owner setup checklist — all present. This checkpoint does not re-draft it.
- **Live profile verified first-hand this run** (text fetch 2026-11-27 ~15:16 IST, `contra.com/comet_5iw52nen`): headline "SEO Blog Posts · YouTube Scripts · 30-Day Social Content" (matches profile-pack §1 short fallback), About text present and matching. So the board's "OWNER ONE-TIME: create the Contra account" step is **already done** — the account and profile are live (portfolio item live since Nov 25 per EARN-034). No owner account step remains.
- Samples on main: `earning/contra/samples/youtube-script-7-moon-facts.md` (EARN-034) and `product-descriptions-ecommerce-before-after.md`. SEO-article and social-pack samples are EARN-035/036 scope, not this task.
- **Not verified this run:** that the pack's rates match the 4 live Fiverr gigs (acceptance says "at matching rates") — the pack predates this claim and was filed by the owner; the Fiverr rate-mirror check is owed, not claimed here. Live Services-tab completeness (all 4 services listed) also not re-checked this run — EARN-034 verified the YouTube service ($15, 2 days) live.

## 2. Contra payout terms — recorded from the official source (do not assume)

Source: Contra's own "Introducing Contra Payments" (`contra.com/blog/payments`, published 2026-02-18), read first-hand 2026-11-27 ~15:20 IST. Third-party pages (freelancesites.net, 16idc.com, earnifyhub.com) agree on 0% commission and the 4–9-day standard range; figures below are the official ones.

- **Commission: 0%, always.** "100% commission free" — Contra has never taken a commission; it charges platform / processing / payout fees instead.
- **Platform fee (per payment, Non-Pro): <$500 → $15; >$500 → $29; Pro → $0.** Pro ($29/mo) removes platform fees, digital-product fees, and unlocks unlimited free faster payouts. A Contra Max tier waives all fees.
- **Client processing fees (not Contra's):** card 2.9% + 30¢; ACH 0.8% capped at $5.00; SEPA 0.5% + 30¢ capped at $6.00.
- **Payouts (freelancer side, funds always in USD):** India INR local bank transfer fee **USD 1.25**; FX fee for INR **0.40%**. PayPal withdrawal 2%; Payoneer $3 + 1–2%; crypto (Coinbase) 2% (1% Pro, $0 Max). SWIFT $15–25+ per payout.
- **Transit timelines (official):** standard payout = **4-day safety-clearance period + provider timeline**. Bank account: faster 0–3 business days, standard 4–7 business days. PayPal / Payoneer: faster within 30 minutes, standard 4 business days. Debit card (US only): faster within 1 hour, standard 4 business days. Crypto: instant.
- **Settlement before withdrawal:** ACH payments take 3–5 business days to settle; SEPA 7–10 business days. Funds only become available to withdraw once settled.
- **Disputes:** 14-day dispute-assistance period; unresolved funds held in escrow for 3 months.
- **First-money path:** client books a Service or sends a project brief → deliver in 2–3 days → escrow/milestone released on approval → standard payout reaches an Indian bank in 4–7 business days after the 4-day clearance (card payments settle immediately; ACH/SEPA add their settlement time first). There is **no 14-day new-seller hold of the Fiverr kind** — the Contra equivalent is the 4-day safety clearance on standard payouts, skippable via the faster-payout option.

## 3. FLAG — starter rates vs the $15 platform fee (ruling owed)

The profile pack's starter rates are $15 (SEO, YouTube) and $20 (social, product descriptions). On the **free tier**, Contra's own fee table charges a **$15 platform fee per payment under $500**. At starter prices that leaves ~$0–$5 before processor and payout fees. The pack was written before this fee was recorded, so this was not priced in. **Not assumed:** whether the platform fee is deducted from freelancer earnings or charged to the client — the official page's table does not state the side explicitly. Ruling owed from the coordinator/owner: raise starter prices, bundle into larger projects, or take Pro ($29/mo, fee waived). Do not paste the pack's starter rates as final until this is ruled.

## 4. Five states

- Implemented: YES (payout terms recorded as evidence; profile-pack + live-profile grounding verified).
- Tested: YES — live profile fetched first-hand; official Contra fee page read in full (641 lines).
- Merged: NO (PR open, awaiting coordinator review/merge).
- Deployed: NO — profile already live; publishing further samples is owner-side.
- Production-verified: NO — no first Contra payment has happened yet.

## 5. Next

Coordinator merge of this PR, then the board PR ships the EARN-030 record (CLAIMED → IN_REVIEW on merge). The fee flag (§3) needs a coordinator/owner ruling before starter rates are treated as final. After merge, remaining EARN-030 work is owner-side (paste remaining samples when EARN-035/036 land) — no further repo work in this task unless the ruling changes the pack.
