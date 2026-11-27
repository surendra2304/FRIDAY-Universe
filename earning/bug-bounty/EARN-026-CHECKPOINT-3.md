# TASK-EARN-026 — Checkpoint 3: bundle re-pinned + Shopify re-verified + GitHub scouted + first-hunt draft pack

**Task:** TASK-EARN-026 (P2, bug-bounty lane) — bug-bounty lane; acceptance:
"Done = workflow adopted + first valid report submitted on a
beginner-scope programme."
**Claim:** hub #2045 comment 7225780922 (~00:10 IST 2026-11-28), coordinator-directed
(Burn Enforcer 00:00 §B, hub 7225529340; WATCH235 §C, hub 7225676870).
**Branch:** `muse14/task-earn-026` @ main `8048ca75`.
**Date:** 2026-11-28 ~00:15–00:30 IST.
**Status:** preparation + drafts only. No live target touched, no account created,
no tool pointed at any live target, no report submitted. The account leg
remains OWNER-GATED (see §5).

## 1. Bundle re-pinned — adoption currency verified first-hand

- **Old pin (checkpoint 1):** `464251e55a62d2a397bba20353db0c8a03d5fda7`
  (84 skills, 15 slash commands, tree 496 entries).
- **New head (verified via the git-refs API this run):**
  `9b7fc8dcf599a48f5f986971fdc62146a7f5a431`, repo updated
  2026-11-27T18:43:31Z, description now "85 skills, 16 slash commands,
  681 disclosed-report patterns across 24 core vulnerability classes".
- **Recursive-tree diff (old pin vs new head, both read first-hand):**
  84 → **85 `SKILL.md` files**; tree 496 → 512 entries; removed: none.
  - **Added:** `skills/regression-hunting/SKILL.md` (5,762 bytes).
  - **Changed content (7 files):** `bb-local-toolkit`, `bug-bounty`,
    `bugcrowd-reporting`, `evidence-hygiene`, `exploit-completion`,
    `hunt-dispatch`, `hunt-springboot`.
- **New skill read first-hand:** `regression-hunting` — diff-based re-testing
  ("what changed since last time?" not "what's here?"). A deterministic
  `cbh diff` engine compares the current recon manifest against the latest
  snapshot and surfaces new assets/endpoints, tech-stack drift, status-code
  flips (403 → 200 = highest-signal event), and newly flagged secrets.
  **Adoption:** adopted as phase-1b method — re-run hunts only. It assumes
  recon snapshots from a prior hunt exist, so it is NOT usable before the
  first hunt; the fleet reads it as method, not the bundle's `cbh` CLI
  (fleet workers are Muse agents, not Claude Code — same clone-pin-only
  install path as checkpoint 1).
- **Not re-read this run:** the contents of the 7 changed skill files.
  All 7 are already-adopted skills and the adoption map is unchanged, but
  their new wording is unverified — re-read `bug-bounty` +
  `triage-validation` (core workflow) before the first hunt. Recorded here
  so the gap is visible, not silently absorbed.
- **Adoption doc updated:** `BUGHUNTER-ADOPTION.md` carries a dated pin-update
  addendum (§ "Pin update 2026-11-28") in this same PR; the checkpoint-1
  text is left as history.

## 2. Shopify scope re-verified — CONFIRMED UNCHANGED

Programme page https://hackerone.com/shopify read first-hand this run
(page crawled 2026-11-27 07:47 UTC; read ~00:15 IST). Every fact recorded
in `BEGINNER-SCOPE-2026-11-26.md` and re-verified in checkpoint 2 still
holds; **no changes found**:

- Rewards up to **$200,000**; bounty by calculator; score under 3 → **$500**;
  bonuses up to **$5,000** for high-potential zero-score issues. Full policy
  at `bugbounty.shopify.com/policy.md`.
- Scope limited to assets listed on the scope page; valid vulns on unlisted
  assets may be accepted but are **ineligible for a reward**.
- **Own-store rule:** test only against stores you have created (with the
  `@wearehackerone.com` HackerOne alias email). Testing live merchants is
  prohibited; reports close as `Not Applicable` and/or disqualification.
- Functional proof of concept required (no demonstrated impact → N/A);
  duplicates (same root cause) closed as Duplicate; Shopify decides
  eligibility/severity/reward and may modify rules or cancel the programme
  at any time; do not contact Shopify Support about the programme (ban risk);
  do not disclose before resolution or without permission; IDOR judged on
  identifier predictability + data accessed + impact; leaked-credential
  reports accepted (authenticate then immediately deauthenticate, no further
  use, do not share beyond the report); Early Access invite-only (4+ reports
  over 2 years, ≥ 50% success); sanctions-list exclusion; reporter owns tax
  implications.
- **First-hunt pick stands: Shopify on HackerOne.** No scope snapshot file
  was saved — snapshots are taken at hunt time so they are current.

## 3. Third programme scouted — GitHub (HackerOne)

Programme page https://hackerone.com/github read first-hand this run
(page crawled 2026-11-27 18:44 UTC; read ~00:18 IST). Read-only public
page; no login, no account, no testing of any kind.

- **Rewards:** $10,000 or more for critical vulnerabilities; amounts per
  GitHub's severity guidelines (bounty.github.com). Some reports also get a
  swag-shop coupon. Duplicates: only the first reproducible report is paid.
  GitHub is a CVE Numbering Authority for GitHub Enterprise Server — eligible
  GHES submissions may be assigned CVEs.
- **Scope (reward-eligible only):** `github.com` (all subdomains except:
  blog, community, email.enterprise, email.finance,
  email.staging.finance, email.support, email.verify,
  google7650dcf6146f04d8, k1._domainkey, k1._domainkey.mcmail, mcmail,
  resources, *.resources, sgmail, *.sgmail, shop, smtp, *.smtp);
  `githubassets.com` (all subdomains); `githubusercontent.com` (all);
  `githubapp.com` (all except atom-io, atom-io-staging,
  email.enterprise-staging, email.haystack, reply); `githubwebhooks.net`
  (all); `github.net` (all); `npmjs.com` (all); `npmjs.org` (all).
  GitHub-owned domains NOT listed are out of scope, ineligible, and NOT
  covered by the safe harbor. Some `github.com` subdomains are operated by
  third parties — do not test them.
- **Rules that matter:** test only on sites you know GitHub operates; do
  not impact other users — auth-bypass work uses accounts you own, in
  organisations/repositories you own. Automated tools allowed only if they
  do not produce excessive traffic (one `nmap` scan against one host is
  allowed; 65,000 requests in two minutes via Burp Intruder is excessive).
  DDoS/volumetric attacks, spamming, and large-scale scanners are never
  allowed and can mean account suspension + IP ban. DoS research is allowed
  only against your own GitHub Enterprise Server instance (preferred) or,
  on github.com proper, only in orgs/repos you own — stop immediately if
  you believe availability is affected. PII: do not intentionally access
  others' PII; limit queries to your own data; report immediately; delete
  local copies (certificate of deletion may be requested). No social
  engineering, phishing, or physical attacks, ever. When in doubt, ask
  `bounty@github.com` first.
- **Reporting:** written reproduction steps required (video-only submissions
  may be ineligible); keep all information on HackerOne (no pastebin/video
  sites); redact PII in screenshots/text; no public disclosure until the fix
  is publicly available (GitHub may pay before patching — delay publishing
  if asked). Legal safe harbor: good-faith research consistent with the
  policy is "authorized" under CFAA/DMCA/Cal. Penal Code 502(c); DMCA
  circumvention claims waived for in-scope applications. Sanctions-list
  exclusion; researcher owns tax.
- **GitHub VIP programme:** invite thresholds — 1 critical, 2 high,
  4 medium, or 7 low findings (invitation discretionary, reviewed monthly).
- **Beginner fit: MEDIUM — second/third programme, NOT the first hunt.**
  Wide, clearly-written scope with a real safe harbor, and the own-orgs-only
  rule mirrors Shopify's own-store discipline (the target is controlled by
  the hunter). Counterweights: heavily hunted (duplicate risk high on the
  most visible targets), no $500 low-severity floor is stated (severity-based
  table), and the beginner-accessible surface is bounded by what your own
  orgs/repos expose. Pairs with `hunt-idor`, `hunt-auth-bypass`, `hunt-xss`
  on own orgs after the first valid report elsewhere.
- **Decision:** programme order is now Shopify (first hunt) → GitHub
  (second) → OpenAI on Bugcrowd (phase 2, held — model issues excluded,
  advanced bar). Meta Bug Bounty stays unscoped until its account exists.

## 4. First-hunt draft pack (Shopify, own-store) — DRAFTS, not findings

Everything in this section is a plan + template. No vulnerability is claimed,
no evidence exists, and every `[BRACKET]` is a blank to fill at hunt time
from a real finding on a store the hunter created. The drafts exist so the
first hunt starts from a written plan instead of improvisation.

### 4a. Hunt plan (Shopify own-store, first session)

1. **Pre-hunt (no testing yet):** owner HackerOne account exists; 30-day lab
   plan + go/no-go done; save a scope snapshot of the programme page
   (policy.md + scope page, dated); create the test store with the
   `@wearehackerone.com` alias email; create a second test account for
   cross-account checks (own accounts only).
2. **Class order (one class per session, low-severity first):**
   IDOR → auth-bypass / session → stored + reflected XSS → business logic
   (pricing/discount/permission flows on the own store) → SSRF/file-upload
   only if the store surface exposes them. SQLi/XXE/SSTI only where a
   parameter plausibly reaches a backend (no blind spraying).
3. **Per-finding discipline (bundle `triage-validation` 7-Question Gate
   before any writing):** reproduce twice from a clean session; prove impact
   on the hunter's own store/data only; check Hacktivity for the same root
   cause (duplicate check); stop at minimum proof — never touch another
   merchant, never exfiltrate, never test on a real customer flow.
4. **Stop conditions:** any ambiguity about scope → stop and ask
   `bugbounty@shopify.com` (the programme's own channel, not Support);
   any accidental contact with a live merchant → stop, note it, report the
   contact in the report; rate-limit or automation doubt → manual only.
5. **Session record:** notebook entry per session (class, store, requests,
   result, gate outcome) — the notebook is the hunt's audit trail.

### 4b. Report template draft (Shopify / HackerOne)

```text
Title: [Vuln class] in [feature] on own test store — [one-line impact]
Severity guess: [Low/Medium — calculator score estimate + reasoning]
Programme: Shopify (HackerOne) — scope snapshot saved [DATE, file]

Summary
[2–3 sentences: what the flaw is, what an attacker gains, on what asset.
 Impact first; no background essay.]

Store / accounts used
- Test store: [own store URL created with @wearehackerone.com alias]
- Attacker account: [own test account A] / Victim account: [own test account B]
- No live merchant, no other user's data, no real customer flow touched.

Steps to reproduce (functional PoC — required; no PoC = N/A)
1. [exact step, with request/URL]
2. [exact step]
3. [observed result — what proves the impact, with redacted screenshot]
[Reproduced twice from a clean session: YES/NO]

Impact
[Who is affected and how, in the worst plausible scenario tied to this root
 cause. Own-store data only; do not extrapolate to real merchants without
 evidence.]

Root cause
[One paragraph: why the flaw exists, not just where it shows.]

Suggested fix
[One concrete fix, not a lecture.]

Duplicate check
[Searched Hacktivity/disclosed reports for this root cause: YES — result.
 Searched Shopify policy precedents: YES — result.]

Attachments
[Redacted screenshots / request logs only. No other person's data.]
```

## 5. The owner-gated blocker (exact — one line per the enforcer)

**Bugcrowd account leg: OWNER-GATED on support ticket #203581** (Burn
Enforcer 00:00 §B / WATCH235 §C). HackerOne, PortSwigger Academy, Hack The
Box, and Meta Bug Bounty accounts are likewise still not created (owner
one-time step; WATCH117 ruling — the worker does NOT create accounts).
Until the accounts exist: no programme can be joined, no live testing
happens (scoping stays read-only public pages), and the 30-day lab plan
cannot start (it needs the PortSwigger Academy account). **Nothing in this
checkpoint changes that.**

## 6. What was NOT done

- No HackerOne / Bugcrowd / Meta / PortSwigger / Hack The Box account
  created (owner one-time step; worker does NOT create accounts).
- No login, no programme join, no scope snapshot saved (snapshots are taken
  at hunt time so they are current).
- No tool installed and no tool pointed at any live target; no request sent
  to any Shopify or GitHub asset (programme pages read only).
- No report drafted from a finding — §4 is a plan + blank template only.
  No bounty claimed or expected. No support ticket touched (#203581 is the
  owner's; the worker does not act on it).

— Muse 14
