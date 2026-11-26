# Beginner-Scope Programmes — TASK-EARN-026 checkpoint 1 (scoping leg)

**Task:** TASK-EARN-026 (P2, bug-bounty lane). **Date:** 2026-11-26.
**Status:** scoping only. Both programme pages below were read first-hand from
their public pages (no login, no account, no testing of any kind). No live
target has been touched; no account has been created — account creation is the
owner's one-time step (WATCH117 ruling).

## How these two were chosen

The lane's pack (`platform-comparison.md`) says: start on HackerOne (largest
directory + disclosed-report education) with Bugcrowd as the parallel second
account. These are the first two public programmes scoped under that rule —
one per platform — with the scope, bounty, and beginner-fit facts read from
the programme pages themselves, not from round-ups.

## Programme 1 — Shopify (HackerOne) — FIRST-HUNT CANDIDATE

- **Programme page:** https://hackerone.com/shopify — read first-hand
  2026-11-26 ~02:26 IST (page crawled 2026-11-25 20:56 UTC).
- **Rewards:** up to **$200,000**; bounty by calculator. Score under 3 → **$500**;
  score ≥ 3 set by the calculator; bonuses up to $5,000 for high-potential
  zero-score issues. Full policy: `bugbounty.shopify.com/policy.md`.
- **Scope rule (the one that matters):** "The scope of the bug bounty program
  is limited to the assets listed on the scope page." Valid vulns on unlisted
  assets may be accepted but are **ineligible for a reward**.
- **The beginner-safety rule:** **test ONLY against stores you create** (with
  your `@wearehackerone.com` HackerOne alias email). Testing against live
  merchants is prohibited and can mean reports closed as Not Applicable and/or
  disqualification. This is what makes Shopify the first-hunt pick: the target
  is fully controlled by the hunter.
- **Other rules verified on the page:** functional proof of concept required
  (reports without demonstrated impact close as N/A); duplicates closed as
  Duplicate (same root cause); Shopify decides eligibility/severity/reward and
  may modify rules or cancel the programme at any time; do not contact Shopify
  Support about the programme; do not disclose before resolution/permission;
  IDOR eligibility judged on identifier predictability + data accessed +
  overall impact; leaked-credential reports accepted (authenticate then
  immediately deauthenticate, no further use).
- **Early Access (invite-only):** 4+ reports in 2 years with ≥ 50% success —
  not a starting goal.
- **Beginner fit: HIGH (first hunt).** Wide, clearly-written scope; the
  own-store rule removes the biggest beginner risk (touching a real merchant);
  $500 floor for low scores means a valid low-severity finding still pays.
  Counterweight: a large, popular programme — duplicates are the main risk,
  which is why the first hunt targets low-severity, high-probability classes
  (per the 30-day plan) on a freshly-created store.
- **First-hunt precondition:** owner HackerOne account exists; the 30-day lab
  plan + go/no-go are done; a scope snapshot of the programme page is saved
  before any testing (per `scope-and-legal-rules.md`).

## Programme 2 — OpenAI (Bugcrowd) — SECOND-PHASE CANDIDATE, NOT FIRST

- **Programme page:** https://bugcrowd.com/openai — read first-hand
  2026-11-26 ~02:27 IST (page crawled 2026-11-25 20:57 UTC).
- **In scope (verified on the page):** ChatGPT Web (`chatgpt.com`), ChatGPT
  Plugins, OpenAI APIs (`api.openai.com`), Developer Platform Playground
  (`platform.openai.com/playground`), ChatGPT Dots, ChatGPT Desktop / Codex
  CLI / official browser extension, plus public cloud resources serving the
  API. Interested in: XSS, CSRF, SQLi, auth/authz issues, data exposure,
  payments issues, Cloudflare bypass, pre-release/private-model queries,
  plugin SSRF/OAuth, sandbox bypass.
- **Hard exclusions (verified on the page):** **model-related issues are
  strictly out of scope** for the Security programme and will not be rewarded.
  Root/elevated privileges inside your **own** Dot VM, crashing only your own
  VM, and prompt injection without a demonstrated unauthorised security
  consequence are out of scope. Sandbox-bypass reports must prove a
  cross-account or host-escape effect using test accounts the reporter
  controls (both session IDs, own data only).
- **Beginner fit: LOW for the first hunt.** The scope is wide but the bar is
  advanced (sandbox escapes, API infrastructure, plugin systems), duplicate
  risk is high on the most visible targets, and the most obvious beginner
  angle (prompt/model behaviour) is explicitly excluded. Held for phase 2 —
  after the first valid report elsewhere, when the `hunt-llm-ai` / API skills
  have lab proof behind them.
- **Why it is scoped now anyway:** it is the Bugcrowd-side anchor for the
  second account (per the pack), and its exclusions are the clearest example
  of why scope pages must be read before any testing — a beginner hunting
  "AI bugs" here would earn $0 by design.

## What was NOT done (and why it matters)

- No HackerOne / Bugcrowd / Meta account created (owner one-time step).
- No login, no programme join, no scope snapshot saved yet (snapshots are
  taken when a programme is actually chosen for a hunt, so they are current).
- No tool pointed at any live target; no request sent to either programme's
  assets. The 30-day plan's rule stands: tools point only at PortSwigger
  Academy labs and Hack The Box free-tier machines until the go/no-go.
- Meta Bug Bounty is **not scoped in this document**: its programme is
  account-gated for the parts that matter, and the account is the owner's
  one-time step. It is scoped when the account exists.

## Decision (checkpoint 1)

- **First hunt (after labs + go/no-go): Shopify on HackerOne** — own-store
  rule, $500 low-score floor, clear scope.
- **Second phase: OpenAI on Bugcrowd** — after the first valid report.
- **Next:** owner creates the HackerOne + Bugcrowd accounts; the 30-day lab
  plan runs; the go/no-go review re-confirms this pick against the then-current
  scope pages (scopes change — re-read before hunting).

## Sources (all read first-hand this run)

- https://hackerone.com/shopify (crawled 2026-11-25 20:56 UTC).
- https://bugcrowd.com/openai (crawled 2026-11-25 20:57 UTC).
- Pack: `earning/bug-bounty/platform-comparison.md`,
  `scope-and-legal-rules.md`, `30-day-plan.md` (main `8abf3a94`).
- WATCH117 ruling on EARN-026 accounts (hub #1483 comment 7173839964).
