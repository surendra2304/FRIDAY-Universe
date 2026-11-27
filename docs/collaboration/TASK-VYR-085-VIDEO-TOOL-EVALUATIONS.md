# TASK-VYR-085 — VyralX: listicle video-tool evaluations (free tiers verified live)

- Task: TASK-VYR-085 (P3, owner muse_17). Claim: hub #2045 comment 7207397042 (~07:04 IST 2026-11-27). Branch: muse17/vyr-085 @ 091bc349.
- Method: vendor pricing pages read live + real render attempts in the live browser. No sign-up, no card, no account, no payment at any point.

## Leg 1 — free-tier verdicts from vendor pricing pages (2026-11-27 ~08:15 IST)

| Tool | Free tier (live) | Allowance | Watermark | Export limits | Sign-up / card | Verdict |
|---|---|---|---|---|---|---|
| Wireflo (vendor spells Wireflow, wireflow.ai) | $0 Free | 60 starter credits + 10/day while balance < 60; free video-editor exports | n/a (editor) | Video models (Veo, Kling, Seedance) on PAID plans only; new accounts get one free video | No card | PARTIAL — free to build/browse + editor exports; AI video generation effectively paid. Not adoptable as a free video route except the single free video. |
| ZSKY AI (zsky.ai) | $0 Free forever, unlimited generation, no credits | Unlimited image + video; 5 s max video, HD; shared queue | Small 'MADE WITH / zsky.ai' plate | Creations deleted after 7 days (review-reported); commercial use allowed | No card; generate without account per vendor claims (zsky.ai/create) | VERIFIED FREE on pricing page — adoptable as an option pending a real render; watermark is the catch. |
| D-ID Studio (d-id.com) | NO free plan — 14-day trial only | 3 min video total across videos/agents/translate/API | Full-screen watermark | Personal use only; trial 14 days | Card asked on mobile-app trial | REJECTED — trial only; paid under free-only (Lite $5.90/mo). |
| Steve AI (web.steve.ai) | $0 Free plan listed on vendor page | 1,200 s AI video/mo, 200 credits, unlimited generation, publish to YouTube | Yes (paid unlocks watermark-free) | 2 free local downloads/mo; HD on paid | Account required | VERIFIED FREE on pricing page with limits — adoptable as an option pending a real render; watermark + 2 downloads/mo. (Note: some third-party reviews say no permanent free plan; vendor's own page lists Free $0 and governs.) |
| Pictory (pictory.ai) | NO free plan — 14-day trial only | 300 credits (~10 min), 3 projects, 720p, 14 days | Pictory branding on all trial exports | 500 MB storage; no card required | Account required | REJECTED — trial only; paid under free-only (Starter $25/mo billed yearly). |

Sources: wireflow.ai/pricing, zsky.ai/pricing, d-id.com/pricing/studio (via whathetech/revoyant/soku/aivideovault checks Nov 2026), web.steve.ai, pictory.ai (via pictory.ai pages + revoyant/ai-alternative/genmedialab checks Oct–Nov 2026).

## Leg 2 — real render attempt, ZSKY AI (2026-11-27 ~09:04–09:06 IST)

- Source: https://zsky.ai/create, live browser, not signed in. Prompt: "a sunrise over mountains, cinematic, short clip". Video mode selected; default/free settings shown: Fast | 720p | 16:9 | 5s (720p default despite the 1080p headline).
- Result: BLOCKED at Generate. Clicking Generate immediately opened a sign-up dialog ("Almost there! — Your creation is queued — sign in to start generating!"), offering Continue with Google / Apple / Microsoft / Discord / X / GitHub / Facebook / Twitch / LinkedIn / Email + Password, 18+ / Terms checkbox, "Sign Up & Generate" button. No account created, no personal/payment data entered, dialog closed.
- Verdict: ZSKY AI does NOT generate without an account — the vendor's "generation without an account" claim FAILED on the first real test. No video rendered, no watermark observable, no paywall/credit/card step reached (sign-up wall came first).
- Consequence: ZSKY AI is NOT adoptable as a no-signup free video route. Whether its $0 plan renders after signup is UNVERIFIED — verifying it needs an account, which was not created in this task.

## Leg 3 — real render attempt, Steve AI (2026-11-27 ~09:06–09:15 IST)

- Source: https://web.steve.ai, live browser, not signed in. Homepage is marketing-only — no prompt box or guest generator; creation only via call-to-action buttons.
- Result: BLOCKED at the first click, twice over. "Try Creating AI Video For Free" redirected to a registration URL (https://snb-accs.animaker.com/register/steveai/?trackId=u1rfvkvfqulfse9nrv9qqudf) which TIMED OUT in the browser on three attempts (original click, reload, direct open). Second entry point "Try Prompt to Video AI" went to the identical registration URL and timed out the same way. No prompt was ever entered — no generator page was reachable without registering.
- Independent confirmation: https://app.steve.ai/ redirects to a sign-in page (https://accounts.animaker.com/login/steveai/?redirect_url=https://app.steve.ai&path=/prompt), "Sign In with Steve.ai", Google/Facebook buttons, email + password fields. The redirect target path=/prompt confirms the prompt-to-video generator sits behind login. Nothing entered, no account created, no sign-in.
- Pricing observed on the homepage Free card: "$0", "1200 seconds AI Videos", "200 Credits for AI & Stock Media Generation" — consistent with leg 1. Paid plans list "No Steve AI Watermark" (Starter ₹1666/mo, Pro ₹3416/mo, Generative AI ₹6916/mo). The "2 free downloads/mo" figure from leg 1 could NOT be re-verified from the pricing page view captured (app.steve.ai/pricing showed only Starter/Pro/Generative AI/Enterprise columns, prices not rendered).
- Verdict: Steve AI generation is NOT available without an account. No video rendered, no watermark observable, no paywall/credit/card step reached (sign-in wall came first).

## Final verdicts

- VERIFIED FREE on pricing pages only: ZSKY AI, Steve AI. Both REQUIRE an account to generate — neither renders without signup (ZSKY: wall at Generate; Steve AI: wall at first click + registration page timeout).
- PARTIAL: Wireflo/Wireflow (free build + editor; video models paid; one free video for new accounts).
- REJECTED (trial-only, paid): D-ID Studio, Pictory.
- Bottom line: NO tool in this class renders a video without an account. No free video route is adoptable for VyralX on a no-signup basis. Whether ZSKY AI / Steve AI $0 plans actually render after signup is UNVERIFIED — it needs an account, which was not created in this task. That is an open question for Muse (see Remaining).

## Five states
- Implemented: YES (evaluation + live render attempts)
- Tested: YES (pricing pages live; 2 real render attempts in the live browser)
- Merged: NO (work PR pending)
- Deployed: N/A
- Production-verified: NO (verification task; no VyralX deployment)

## Remaining
- Paired verification + coordinator merge of this work PR; close ruling owed by coordinator.
- Open question for Muse: whether a free vendor account (no card, no payment) may be created to finish the render verification of ZSKY AI / Steve AI, and if so with what email — NOT done in this task.
