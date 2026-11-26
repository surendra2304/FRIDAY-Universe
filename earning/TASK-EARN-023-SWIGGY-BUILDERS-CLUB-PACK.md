# TASK-EARN-023 — Swiggy Builders Club: Prototype Concept + Application Pack

**Lane:** EARN — Swiggy Builders Club option (corpus reel DYg_b2ZTK70, @lavin_creator)
**Status:** Draft for the owner to submit — nothing here has been sent to Swiggy. No application submitted by TP6.
**Source:** Board record TASK-EARN-023 + live public pages verified first-hand 2026-11-26 ~09:18 IST: `https://mcp.swiggy.com/builders`, `https://mcp.swiggy.com/builders/access/`, and the Developer application form (Google Form, first page read without signing in; submission needs sign-in).
**OWNER ONE-TIME:** the owner fills his personal fields, records the demo video, and submits the form himself (his details, his call). First-money path is indirect and unproven — this task buys an option on the programme, it does not promise income. If Swiggy declines or never replies, close the task with that verdict recorded.

## 0. Programme facts (live page, 2026-11-26)

- Swiggy Builders Club: Swiggy's MCP platform for developers/startups/enterprises. 4 MCP servers (Food, Instamart, Dineout, Scenes), 62 API tools. Contact: builders@swiggy.in.
- Path to prod: (1) build on localhost, NO APPROVAL, prototype against real tool schemas, free; (2) apply for prod access — who you are, what you built, share a demo; (3) quick review of use case + security setup; (4) go live — OAuth redirect details allowlisted; (5) send a demo (standout projects get featured; Swiggy hires from the programme).
- Two application tracks: Developer (individual developers / indie hackers) and Enterprise/Startup (dedicated support, custom onboarding, enterprise SLAs; typical turnaround 4+ weeks). Both get full API access.
- Developer form: "Swiggy Builders Club - Developer Application", "Takes about 5 minutes", Google Form, sign-in required to submit. First page has 15 fields (listed in §2). There may be further pages after "Next" — not viewable without filling in answers and signing in, so the owner should expect a possible page 2 (the access page's 12-item checklist — static IPs, security contact, data-handling declaration, environment/infrastructure details — is the likely page-2 material; brief drafts for those are in §3).
- Ground rules that bind the concept: no reselling/sharing MCP access with unapproved third parties; no aggregation layer hiding Swiggy's brand; never misrepresent prices, availability or delivery times; no scraping beyond what the APIs provide; no dark patterns or deceptive UX; no fake traffic or rate-limit abuse; user data governed by Swiggy's platform terms. The concept below is built to stay inside all of these.

## 1. One-page prototype concept: FRIDAY Food — voice ordering + auto-restock

**What it is.** A FRIDAY voice agent on the Swiggy MCP. The owner talks to FRIDAY (she/her, voice-first) and she orders food and restocks groceries through Swiggy Food and Swiggy Instamart — no app-tapping, no re-typing addresses. Two flows:

1. **Voice food ordering (Swiggy Food).** Owner: "FRIDAY, order my usual from [restaurant]." FRIDAY searches Food via MCP, reads back the exact items, total price and ETA as returned by the API, and places the order only after the owner says yes out loud. Every order is voice-confirmed; nothing is ever ordered silently.
2. **Auto-restock (Swiggy Instamart).** A standing pantry list (owner-defined). Once a week FRIDAY checks the list against Instamart, reads back what is low and the total, and the owner confirms the restock by voice. No subscription, no auto-charge — confirmation every time.

**Why it fits the programme.** The access page explicitly encourages "AI assistants/copilots automating commerce workflows" and "side projects, hackathon builds and prototypes". This is that lane, on FRIDAY — a real voice companion with a real user — not a demo-only toy.

**How it integrates (concept-level).** FRIDAY (Python) gains a Swiggy MCP client adapter: voice intent → MCP tool call (search Food / search Instamart) → spoken read-back of the API's own price/availability/ETA → explicit voice confirmation → MCP order placement → spoken order status. Prototype first on localhost against the real tool schemas (no approval needed); prod only after the application is approved and OAuth redirect URIs are allowlisted. Prices, availability and delivery times are always shown exactly as the API returns them — never re-quoted, rounded or invented.

**What it is NOT.** Not a reseller, not an aggregator, not a price-comparison layer, not a scraper. Swiggy's brand stays visible ("Powered by Swiggy" attribution per their guidelines). No user data leaves the owner's FRIDAY session except the order itself, sent to Swiggy through the MCP tools. No fake traffic, no order-flow manipulation, no dark patterns: the owner confirms every rupee out loud.

**Honest limits.** No prototype code exists yet — this is a concept + application pack, per the board acceptance. No demo video exists yet, and the form requires one (§2, field 14), so the application cannot be submitted until a demo is recorded. No production deployment exists yet, so there are no production redirect URIs (§2, field 12). Expected volume is "Not sure yet" — prototype stage. Monetisation is indirect (partnership / co-branding / hiring / startup path, per the board record), not a per-order cut.

## 2. Application answers — Developer track (field-for-field, form order)

Form: "Swiggy Builders Club - Developer Application" — https://forms.gle/4vkeKyqm15Qb6fnJA
("Apply as Developer" from https://mcp.swiggy.com/builders/access/). Fields below are verbatim from the live form; `*` = required on the form. Answers marked [OWNER TO FILL] are the owner's own details — TP6 does not fill them. Answers marked [DRAFT] are TP6's draft for the owner to confirm.

1. **Email * (Record my email address with my response)** — [OWNER TO FILL — the EARN-024 board record uses cometbrowser001@gmail.com for the owner's platform accounts; confirm whether to use the same address here.]
2. **Full Name *** — [OWNER TO FILL]
3. **Email *** — [OWNER TO FILL — same address as field 1.]
4. **Are you applying as… *** — Individual Developer
5. **Team / Project Name *** — FRIDAY Universe — project: FRIDAY Food (voice ordering + auto-restock agent)
6. **GitHub or Portfolio URL *** — https://github.com/surendra2304/FRIDAY-Universe (public repo; FRIDAY voice companion + the ten-agent Universe system)
7. **LinkedIn *** — [OWNER TO FILL]
8. **What are you building? *** — [DRAFT] FRIDAY Food: a voice-first food-ordering and grocery-restock agent built on FRIDAY, my voice companion. I speak an order ("order my usual", "restock the pantry") and FRIDAY searches Swiggy Food / Instamart through the MCP tools, reads back the exact items, price and ETA from the API, and places the order only after I confirm by voice. Nothing is ordered without spoken confirmation. It automates the commerce workflow — search, confirm, order, track — for one real household, inside the Swiggy brand and the API's own data.
9. **Which MCP servers do you need? *** — Swiggy Food; Swiggy Instamart (Dineout not needed for this concept)
10. **What type of integration is this?** — AI Agent / Copilot
11. **Tech stack & architecture overview (Briefly describe how you'll integrate with MCP) *** — [DRAFT] FRIDAY is a Python voice companion. A Swiggy MCP client adapter connects FRIDAY to the Food and Instamart MCP servers: voice intent → MCP tool call (search/order/track) → spoken read-back of API price, availability and ETA → explicit voice confirmation → MCP order placement → spoken status. Prototype on localhost against the real tool schemas first (no approval needed); production behind OAuth once redirect URIs are allowlisted. No data stored beyond the session except the owner's standing pantry list, kept locally.
12. **Production Redirect URI(s) for Authentication *** — [TO FILL AT PROD STEP — no production deployment exists yet; localhost URIs are already supported and must NOT be entered here. Fill in once the app is deployed.]
13. **Expected request volume** — Not sure yet (prototype stage; one household to start)
14. **Working Demo Video Link *** — [TO RECORD — no demo exists yet. Record a publicly viewable video (YouTube / Loom / Google Drive) showing the prototype in action once it is built; the application cannot be submitted until this link exists.]
15. **I acknowledge Swiggy's MCP integration terms *** — Yes (owner confirms when submitting)

## 3. Access-page checklist — brief drafts (likely page 2 / review material)

From "What to Include in Your Application" on https://mcp.swiggy.com/builders/access/. Items 1–4 and 9 are covered by the form fields above; the rest are drafted here for the owner to confirm.

- **Static IP ranges or gateway IP(s)** — [OWNER TO CONFIRM at prod step — no production gateway exists yet.]
- **Security contact for your team** — [OWNER TO FILL — the owner's own contact.]
- **Data handling and privacy declaration** — [DRAFT] Only the data the owner explicitly speaks or approves is sent to Swiggy, through the MCP tools, for the order itself. No order or transaction data is stored beyond the session; the standing pantry list is kept locally. No data is shared with, resold to, or harvested for any third party. Transaction data stays governed by Swiggy's platform terms.
- **Environment and infrastructure setup details** — [DRAFT] Prototype on localhost; production deployment to be confirmed by the owner (Oracle Cloud, where FRIDAY Universe is hosted, is the likely home — confirm before submitting).
- **Security audit summary** — OPTIONAL, not available — leave blank.
- **SOC2 / ISO certification (if available)** — OPTIONAL, not available — leave blank.
- **Expected traffic and scaling plan** — [DRAFT] One household at launch; volume "Not sure yet". Scale only by adding households with per-household voice confirmation — no bulk or automated ordering.

## 4. What the owner does next (in order)

1. Confirm or correct the [DRAFT] answers above.
2. Build the localhost prototype (no approval needed) and record the working demo video — field 14 blocks submission until this exists.
3. Deploy (or decide the production home) so field 12 has real redirect URIs.
4. Fill fields 1–3 and 7 with his own details, sign in to Google, and submit the Developer form.
5. If Swiggy declines or never replies, tell Muse — the task closes with that verdict recorded.
