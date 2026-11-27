# TASK-EARN-026 — Checkpoint 2: preparation read + scope re-verified + tooling checked

**Task:** TASK-EARN-026 (P2, owner muse_14) — bug-bounty lane; acceptance:
"Done = workflow adopted + first valid report submitted on a
beginner-scope programme."
**Claim:** hub #2045 comment 7220581759 (~19:46 IST 2026-11-27).
**Branch:** `muse14/task-earn-026-cp2` from main `cf49af6b`.
**Date:** 2026-11-27 ~19:55 IST.
**Status:** preparation only. No live target touched, no account created,
no tool pointed at any live target. The lane remains OWNER-GATED (see §4).

## 1. Pack docs read first-hand this run

- `earning/bug-bounty/scope-and-legal-rules.md` (on main) — read in full.
  The five laws: (1) only in-scope targets, ever — an asset not explicitly
  in scope does not exist for you; (2) only while the programme is live and
  you are registered on its platform — the scope page is the authorisation;
  (3) follow the programme's own rules to the letter (no automated scanning
  on production unless explicitly allowed; rate limits; no testing on other
  users' real accounts — use your own test accounts; no social engineering;
  no DoS; stop at minimum proof); (4) never access, download or keep other
  people's data — smallest possible evidence, own accounts/data only; (5)
  report responsibly, then wait — submit through the platform, no public
  disclosure until the programme allows it. India notes: unauthorised
  access is a crime under IT Act 2000 §§43/66 regardless of intent; save a
  copy of the scope and rules before testing, every time; ambiguity resolves
  to not testing. Practice (PortSwigger Academy, Hack The Box) is kept
  strictly separate from production. Red flags: any "programme" asking
  researchers to pay first; anyone offering to buy vulnerabilities outside a
  platform; testing a competitor/employer/school/government system outside a
  named public programme; Telegram/WhatsApp "hacker" recruitment (prepaid-task
  fraud pattern).
- `earning/bug-bounty/tooling.md` (on main) — read in full. Free toolkit:
  Burp Suite Community Edition (the workhorse; Academy is built around it),
  Firefox/Chromium hunting-browser profile through Burp, PortSwigger Academy
  (the curriculum), nmap, subfinder/amass, httpx, gobuster/ffuf, sqlmap
  (labs freely; live only where automation is explicitly allowed), OWASP ZAP,
  jwt_tool/browser devtools, CyberChef, Obsidian/plain-Markdown notes.
  Deliberately NOT in the toolkit: paid scanners, "AI hacker" subscriptions,
  credential-stuffing/phishing/social-engineering tooling, exploit frameworks
  pointed at production. Setup order (Day 1): create the PortSwigger Academy
  account; install Burp Community; configure the hunting browser profile
  through Burp's proxy; complete Burp's getting-started flow inside an
  Academy lab; install nmap, ffuf, OWASP ZAP from official sources; start the
  notes notebook with the scope-rules page copied at the front.
- Checkpoint-1 basis (already on main, not re-read in full this run):
  `BUGHUNTER-ADOPTION.md` (workflow adopted; bundle pinned
  `464251e55a62d2a397bba20353db0c8a03d5fda7`, 84 skills) and
  `BEGINNER-SCOPE-2026-11-26.md` (Shopify first-hunt pick; OpenAI phase 2).

## 2. Fresh Shopify scope read — CONFIRMED UNCHANGED

Programme page https://hackerone.com/shopify read first-hand this run
(page crawled 2026-11-27 14:20 UTC; read ~19:52 IST). Every fact recorded
in `BEGINNER-SCOPE-2026-11-26.md` (read 2026-11-26 ~02:26 IST) still holds;
**no changes found**:

- Rewards up to **$200,000**; bounty by calculator. Score under 3 → **$500**;
  score ≥ 3 set by the calculator; bonuses up to **$5,000** for high-potential
  zero-score issues. Full policy as a single plain-text file at
  `bugbounty.shopify.com/policy.md`.
- Scope rule: "The scope of the bug bounty program is limited to the assets
  listed on the scope page." Valid vulns on unlisted assets may be accepted
  but are **ineligible for a reward**.
- **Own-store rule (the beginner-safety rule):** "You must test only against
  stores you have created." Testing against live merchants is prohibited and
  can result in reports closed as `Not Applicable` and/or disqualification.
  Test accounts use the `@wearehackerone.com` HackerOne alias email.
- Functional proof of concept required — reports without demonstrated impact
  close as N/A. Duplicates (same root cause) closed as Duplicate. Shopify
  decides eligibility/severity/reward and may modify rules or cancel the
  programme at any time. Do not contact Shopify Support about the programme
  (including scope/security boundaries or report updates); violating this may
  disqualify you and result in a programme ban. Do not disclose before
  resolution or without permission.
- IDOR eligibility judged on identifier predictability + data accessed +
  overall impact. Leaked-credential reports accepted (authenticate then
  immediately deauthenticate, no further use; do not share beyond the report).
- Early Access (invite-only): 4+ reports over 2 years with ≥ 50% success —
  not a starting goal.
- Sanctions-list exclusion; reporter is responsible for tax implications;
  testing/submission must not violate any law or compromise data that is not
  your own.

**First-hunt pick stands: Shopify on HackerOne.** The scope snapshot for a
hunt is still taken at hunt time (per `BEGINNER-SCOPE-2026-11-26.md`), so no
snapshot file was saved in this checkpoint — this read is the
re-verification, not the hunt-time snapshot.

## 3. Tooling availability check (this VM, 2026-11-27 ~19:53 IST)

**None of the free toolkit is installed here.** Verified by `which` +
directory checks:

| Tool | Present? |
|---|---|
| Burp Suite Community Edition | NO — no `burp`/`burpsuite` in PATH, `/usr/local/bin`, or `/opt` |
| nmap | NO |
| ffuf | NO |
| gobuster | NO |
| sqlmap | NO |
| subfinder / amass / httpx | NO |
| Firefox / Chromium / Chrome | NO |
| OWASP ZAP | NO |
| Python 3 | YES — Python 3.12.3 |

Installability: `apt-cache policy nmap ffuf gobuster sqlmap` returned
**empty** (exit 0, no package info) — the apt lists in this VM carry no
record of these tools, so installability via apt is **unverified** here.
Download reachability: `curl` to `portswigger.net` returns **HTTP 404 for
every path tried** (`/`, `/burp/releases`, `/burp/communitydownload`,
`/web-security`) after the proxy connects (`200 Connection Established`),
while `https://www.google.com/` returns `200 OK` from the same VM — so the
Burp download cannot be confirmed reachable from this VM (egress filtering
or the site blocking this egress; same pattern as the INT-046 sandbox
egress blocks). The Day-1 setup (Burp install + nmap/ffuf/ZAP from official
sources) therefore cannot be completed from this VM as-is; it must be done
on a host where `portswigger.net` is reachable, or via the browser download
route. No tool was installed in this checkpoint (check only, per the brief);
no tool was pointed at any live target.

## 4. The owner-gated blocker (exact)

The lane cannot advance past preparation until the owner completes the
one-time account creation. **Nothing in this checkpoint changes that.**

Accounts missing (owner one-time step, per `earning/bug-bounty/README.md`
and the WATCH117 ruling — hub #1483 comment 7173839964 — the worker does
NOT create accounts):

1. **HackerOne** — hackerone.com → Sign Up (hacker profile), with
   cometbrowser001@gmail.com, username `cometworks` where allowed.
2. **Bugcrowd** — bugcrowd.com → Researcher sign up, same email/username.
3. **PortSwigger Web Security Academy** — portswigger.net/web-security →
   free account. This is the practice ground for the 30-day plan; without
   it the lab plan cannot start.
4. **Hack The Box** — hackthebox.com → free account (free tier / Starting
   Point machines). Optional but recommended.
5. **Meta Bug Bounty** — account-gated for the parts that matter; scoped
   when the account exists. Intigriti and YesWeHack only when a specific
   programme there is chosen.

Until the accounts exist: no programme can be joined, no live testing
happens (scoping is read-only public pages only), and the 30-day lab plan
cannot start (it needs the PortSwigger Academy account). Payment setup
(PayPal/bank on HackerOne) is only needed when the first bounty is awarded.

## 5. Readiness state for the 30-day lab plan (once accounts exist)

- Workflow adopted: YES (checkpoint 1, `BUGHUNTER-ADOPTION.md`).
- Scoping current: YES (this checkpoint — Shopify confirmed unchanged
  2026-11-27; OpenAI on Bugcrowd held for phase 2, not re-read this run).
- Pack rules read: YES (this checkpoint — scope-and-legal-rules + tooling).
- Tooling installed: NO (see §3 — Day-1 setup pending, needs a host where
  `portswigger.net` is reachable).
- Lab plan started: NO (blocked on the PortSwigger Academy account).
- First hunt: NO (blocked on HackerOne account + lab plan + go/no-go).

When the owner creates the accounts, the next worker: Day-1 setup (install
Burp Community + nmap/ffuf/ZAP, configure the hunting browser profile,
complete Burp's getting-started flow inside an Academy lab, start the notes
notebook) → 30-day plan (PortSwigger Academy labs + Hack The Box free tier
only; ≥25 labs across ≥5 flaw classes; ≥6 mock reports) → Day-30 go/no-go
review (coordinator + owner) → first hunt on Shopify (own-store rule,
low-severity classes first, inside a saved scope snapshot).

## 6. What was NOT done

- No HackerOne / Bugcrowd / Meta / PortSwigger / Hack The Box account
  created (owner one-time step; worker does NOT create accounts).
- No login, no programme join, no scope snapshot saved (snapshots are taken
  at hunt time so they are current).
- No tool installed and no tool pointed at any live target; no request sent
  to any Shopify asset (the programme page read only).
- No report drafted or submitted. No bounty claimed or expected.

— Muse 14
