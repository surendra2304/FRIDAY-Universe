# Claude-BugHunter Workflow Adoption — TASK-EARN-026 checkpoint 1

**Task:** TASK-EARN-026 (P2, bug-bounty lane). **Date:** 2026-11-26.
**Status:** workflow adopted as the hunting method; no live target touched, no
account created, no testing done. This document is adoption + method only.

## What was adopted (verified first-hand this run)

- **Bundle:** `elementalsouls/Claude-BugHunter`, MIT licence.
- **Pinned commit:** `464251e55a62d2a397bba20353db0c8a03d5fda7`
  (main head, verified via the git-refs API 2026-11-26 ~02:30 IST).
- **Count verified first-hand:** the recursive git tree lists **84 `SKILL.md`
  files** — the EARN-026 record's "83 skills" is stale; the bundle grew to 84
  (repo description agrees: "84 skills, 15 slash commands, 681
  disclosed-report patterns across 24 core vulnerability classes", updated
  2026-11-25T20:55:03Z). Skill catalog `docs/skills.md` cross-checked:
  58 hunt + 10 enterprise + 5 recon/OSINT + 4 methodology + 7 reporting = 84.
- **Install path for this fleet:** clone-pin only. The bundle's plugin path
  (`/plugin marketplace add …`, `/plugin install claude-bughunter@…`) targets
  Claude Code; fleet workers are Muse agents, not Claude Code, so no plugin
  install is run. The skills are plain `SKILL.md` files: the pinned clone is
  the reference, and the skill files below are read as the working method for
  each hunt phase. The HackerOne API username/token the install asks for are
  left blank — no account exists yet, and the owner creates accounts
  (WATCH117 ruling; see below).
- **Read first-hand this run:** `README.md` (350 lines), `docs/skills.md`
  (catalog), `skills/bb-methodology/SKILL.md` (514 lines),
  `skills/bug-bounty/SKILL.md` (1,605 lines),
  `skills/recon-scope-triage/SKILL.md` (90 lines),
  `skills/report-writing/SKILL.md` (569 lines),
  `skills/triage-validation/SKILL.md` (419 lines).

## Adopted skill map (phase → skills)

The bundle's own structure is four layers (Think / Hunt webapps / Perimeter /
Ship it). This lane adopts the web-bounty layers and leaves the enterprise
red-team layer out (see "Not adopted").

| Phase (fleet workflow) | Adopted skills |
|---|---|
| 0 — Mode + scope confirm | `bb-methodology` Part 0 (mode confirmation: bug-bounty mode = impact-demonstrated bugs only; hygiene alone is rejected), `recon-scope-triage` (ownership guilty-until-proven; quarantine collisions, soft-404 control before believing any "Critical") |
| 1 — Recon (in-scope assets only) | `web2-recon` (subdomain enum, live hosts, URL crawl, JS analysis), `offensive-osint`, `osint-methodology`, `security-arsenal` (payloads, bypass tables, wordlists), `bb-local-toolkit` (local tool paths: SecLists, ffuf, dalfox, ghauri, trufflehog) |
| 2 — Hunt (1–2 vuln classes per session) | `bug-bounty` (scope → research → test → validate → report), `bb-methodology` (5-phase non-linear workflow; define/select/execute discipline), `hunt-*` classes matched to the 30-day-plan specialisations: `hunt-sqli`, `hunt-xss`, `hunt-idor`, `hunt-ssrf`, `hunt-auth-bypass`, `hunt-csrf`, `hunt-cors`, `hunt-open-redirect`, `hunt-host-header`, `hunt-jwt-crypto`, `hunt-oauth`, `hunt-session`, `hunt-file-upload`, `hunt-graphql`, `hunt-api-misconfig`, `hunt-business-logic`, `hunt-race-condition`, `hunt-ato`, `hunt-forgot-password`, `hunt-mfa-bypass`, `hunt-dom`, `hunt-http-smuggling`, `hunt-lfi`, `hunt-ssti`, `hunt-xxe`, `hunt-deserialization`, `hunt-nosqli`, `hunt-websocket`, `hunt-cache-poison`, `hunt-clickjacking`, `hunt-subdomain`, `hunt-source-leak`, `hunt-spa-api`, `hunt-shadow-api`, `hunt-tls-network`, `hunt-llm-ai` (only where a programme's scope covers AI features) |
| 3 — Validate before writing | `triage-validation` (7-Question Gate + 4 pre-submission gates; always-rejected list; conditionally-valid-with-chain table), `exploit-completion` (drive one attempt to proof; stop after N identical failures and change approach), `evidence-hygiene` (cookie/PII redaction discipline) |
| 4 — Report (human-reviewed, owner submits) | `report-writing` (H1/Bugcrowd/Intigriti/Immunefi templates, impact-first writing, CVSS 3.1, title/impact formulas, downgrade counters), `bugcrowd-reporting` (VRT category search-and-fallback, manual severity override) |

## Explicitly NOT adopted

- **Enterprise / red-team attack matrices (10 skills):** `apk-redteam-pipeline`,
  `ios-redteam-pipeline`, `m365-entra-attack`, `okta-attack`,
  `enterprise-vpn-attack`, `vmware-vcenter-attack`, `cloud-iam-deep`,
  `supply-chain-attack-recon`, `web3-audit`, `meme-coin-audit`. These target
  infrastructure outside any bug-bounty programme scope this lane will hunt.
  Adopting them would invite out-of-scope testing. Not used, not installed.
- **`redteam-report-template` / `mid-engagement-ir-detection`:** client
  red-team deliverables and client-engagement detection — there are no client
  engagements in this lane.
- **Anything needing paid tooling:** none in the bundle is paid; the free-only
  rule still applies to every tool the skills name (Burp Community, not Pro).
- **`hunt-brute-force` / `hunt-captcha-bypass`:** present in the bundle, but
  the lane's rules forbid testing other users' accounts, credential stuffing,
  and automated scanning unless the programme explicitly allows it. These two
  stay shelved until a named programme's rules explicitly permit the technique
  — and even then only against the worker's own test accounts.
- **Social engineering / phishing:** permanently out of scope for this lane
  (pack `scope-and-legal-rules.md`); no skill in the bundle changes that.

## Fleet rules overlay (these outrank the bundle wherever they differ)

1. **Owner one-time accounts (WATCH117 ruling, 2026-11-26 ~02:02 IST):** the
   owner creates the HackerOne / Bugcrowd (and Meta Bug Bounty) accounts
   himself with cometbrowser001@gmail.com. The worker does NOT create accounts.
   Until the accounts exist, no programme can be joined and no live testing
   happens — scoping is read-only public pages only.
2. **Scope-only, ever** (`scope-and-legal-rules.md`): only assets a programme's
   published scope explicitly lists; save a scope snapshot before testing;
   ambiguity resolves to not testing.
3. **Human review:** every AI-drafted report is reviewed by the owner, who
   submits it himself. No report is submitted by the worker, ever.
4. **Labs first:** the 30-day plan (`30-day-plan.md`) runs before any live
   programme work; its go/no-go review gates the first hunt.
5. **Free only:** no paid service, tier, or subscription — ever.
6. **No data:** never access, download, or keep other people's data; prove
   with the smallest evidence, using only the worker's own test accounts.

## How this composes with the existing pack (no duplication)

The EARN-019 methodology pack already on main under `earning/bug-bounty/`
(`README.md`, `platform-comparison.md`, `scope-and-legal-rules.md`,
`tooling.md`, `30-day-plan.md`) is the lane's rules + learning plan. This
document adds only the executable skill layer: which bundle, which pinned
commit, which skills map to which phase, and what is deliberately excluded.
The pack stays the authority on rules; the bundle is the method inside them.

## Pin update 2026-11-28 (checkpoint 3)

- **New pin:** `9b7fc8dcf599a48f5f986971fdc62146a7f5a431` (repo updated
  2026-11-27T18:43:31Z; "85 skills, 16 slash commands"). Recursive-tree diff
  vs the checkpoint-1 pin: 84 → 85 skills, tree 496 → 512 entries, none
  removed; added `skills/regression-hunting/SKILL.md`; 7 files changed
  (`bb-local-toolkit`, `bug-bounty`, `bugcrowd-reporting`,
  `evidence-hygiene`, `exploit-completion`, `hunt-dispatch`,
  `hunt-springboot` — contents not re-read this run; re-read `bug-bounty` +
  `triage-validation` before the first hunt).
- **New skill adopted:** `regression-hunting` as phase-1b (diff-based
  re-testing of previously hunted targets; needs prior recon snapshots, so
  not usable before the first hunt). The 7 changed files are all
  already-adopted skills; the adoption map above is unchanged.

## What is still owed before the first hunt

- Owner creates the HackerOne + Bugcrowd accounts (one-time, owner step).
- The 30-day lab plan runs (PortSwigger Academy + Hack The Box free tier only).
- Go/no-go review, then the first hunt on the programme picked in
  `BEGINNER-SCOPE-2026-11-26.md` (Shopify, own-store rule), inside its saved
  scope snapshot, low-severity classes first.

## Sources (all read first-hand this run)

- Bundle repo `elementalsouls/Claude-BugHunter`, head
  `464251e55a62d2a397bba20353db0c8a03d5fda7`, MIT, 3,925 KB, updated
  2026-11-25T20:55:03Z; recursive tree (496 entries, not truncated), 84
  `SKILL.md` files counted.
- Bundle `README.md` (350 lines) + `docs/skills.md` + the six skill files
  listed above, all read from the pinned commit.
- WATCH117 ruling on EARN-026 accounts (hub #1483 comment 7173839964).
- EARN-019 pack, `earning/bug-bounty/` on main `8abf3a94`.
