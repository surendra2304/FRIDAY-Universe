# TASK-FRD-054 — PRODUCTION-VERIFY — 2026-11-25 ~16:40 IST — Muse 15

Claim: hub #1483 comment 7158925963 (WATCH091 assignment 7158754888).
Branch: muse15/task-frd-054-production-verify, from main 76fc7dda, rebased onto 076b3942.
Task: PRODUCTION-VERIFY FRIDAY corpus IG2-FRD-03, IG2-FRD-04, IG2-FRD-05, IG2-FRD-06
(live extreme-condition verification, wave 2, P1).

## Verdict: PARTIAL — 2 of 4 verified live

| Item | Verdict | One line |
|---|---|---|
| IG2-FRD-03 lead_generate | NOT VERIFIED | Tool executes live, but natural requests never reach it (router), FindYello fetch 403s, JaRanks parse returns 65 contact-less rows |
| IG2-FRD-04 meeting follow-up | VERIFIED | create mf-1 PENDING → list shows mf-1 → decide approve releases text, nothing sent |
| IG2-FRD-05 browser wake word | NOT VERIFIED (not run) | Stage loads live; mic refused in the automated browser, listener never armed — hearing test still owed |
| IG2-FRD-06 local_business | VERIFIED | qualify + site_prompt + appointment_prompt all executed live with Success |

Failure injection (acceptance: "a downstream agent down" per item): NOT RUN —
HELD by WATCH093 (7159599715): a deliberate outage on the owner's voice
companion needs owner clearance; the owner stop order is still in force.

## Live target — settled by WATCH093, verified first-hand

WATCH093 ruled: live-leg target is FRIDAY-Server, NOT S1. S1 FRIDAY.service
is retired by design — FRIDAY moved to FRIDAY-Server (AWS 15.134.130.145)
on 2026-11-24, production-verified; S1 services were stopped deliberately.
Do NOT restart S1 services. This supersedes checkpoint 1's "no live FRIDAY
on FRIDAY-Server to probe" (that line was wrong — only S1 had been probed).

Verified first-hand this run (read-only, S2 → S1 → AWS ProxyJump route;
direct S2 → AWS ssh is refused at the bridge/MCP layer, the S1 hop is the
working route — same key the S1 :8001 tunnel uses):

- `friday-server` (15.134.130.145): FRIDAY.service ActiveState=active,
  SubState=running; FRIDAY-Voice.service active/running.
- Public `https://friday-universe.duckdns.org/friday/health`: healthy,
  `service: friday_core`, version 2.0.0, Oracle SELECT 1 ok, AWS host
  (observed 2026-11-25 15:59 IST). `/friday/ready` 200.
- Public `/friday/api/tools`: 149 tools in the live registry, including
  `lead_generate`, `meeting_followup_create/list/decide`, `local_business`.
- Public `/friday/api/chat` answers 401 without a control key (D-023 gate,
  working as designed; the keyless-dashboard fix is TASK-FRD-038, Muse 14's).
  All chat legs below ran as loopback POSTs on the AWS host itself (loopback
  callers stay keyless) — no credential was read, used, or pasted anywhere.

Method note: the bridge `run_shell` is intermittently flaky in this window
(MCP stream breaks on ~40% of calls, including trivial ones; long commands
>~800 chars fail reliably, ~500 chars pass). Every failed call was verified
by read-back before any retry, so no probe ran twice and no write was
duplicated. All /tmp probe files on S2 and FRIDAY-Server were deleted after
the run (net-zero production change apart from the mf-1 draft, below).

## IG2-FRD-06 — VERIFIED (all three actions, live)

Four chat executions through live FRIDAY on FRIDAY-Server (loopback
POST /api/chat, model gemini-3.6-flash, cost_mode free_first). Journal
proof is the FRIDAY.service journal on friday-server; the chat replies are
LLM-composed summaries of the tool results, not verbatim tool output.

- qualify (natural request, "Test Bistro, restaurant, Kingston, rating 4.6,
  120 reviews, no website"): HTTP 200, 47.0s wall, server 42.87s.
  Tool executed 16:08 IST, Success, 0.0958s, args rating 4.6 / reviews 120.
  Reply: ideal F-30 prospect, 100/100 (thresholds 4.3 / 100 correct).
- qualify (explicit "Use the local_business tool with action qualify ..."):
  HTTP 200, 32.7s wall, server 29.83s. Tool executed 16:14 IST, Success,
  0.0026s. Same 100/100 verdict.
- site_prompt (natural request, services as given): HTTP 200, 89.7s wall,
  server 87.39s. Tool executed 16:12 IST, Success, 0.0029s. Reply is an
  LLM-composed site prompt — it does NOT quote the tool's verbatim F-30
  tail lines ("Lazy-load images." etc.), even though the tool returned them.
  Presentation note, not a tool failure: the tool ran and succeeded.
- appointment_prompt (natural request): HTTP 200, 32.8s wall, server
  30.54s. Tool executed 16:16 IST, Success, 0.0049s. Reply reproduces the
  tool's template (all six "How you work" bullets verbatim, section
  structure verbatim; location added, services reformatted into bullets).

## IG2-FRD-04 — VERIFIED (create → list → decide, live)

- create ("FRD-054 live probe test meeting", synthetic notes, attendees
  "Muse 15 probe", "Muse coordinator probe"): HTTP 200, 39.7s wall,
  server 37.39s, routed TOOL_EXECUTION. Tool executed 16:19 IST, Success,
  0.0060s. Draft **mf-1** created, Status PENDING, nothing sent.
  0 action items extracted (the notes were phrased as decisions, not
  action items — the extractor found none; not a failure).
- list: HTTP 200, 32.7s wall, server 30.40s. Tool executed 16:21 IST,
  Success, 0.0021s. Reply lists mf-1: PENDING, created 2026-11-25 10:49 UTC.
- decide approve mf-1: HTTP 200, 63.2s wall, server 60.91s. Tool executed
  16:25 IST, Success, 0.0024s. Draft mf-1 APPROVED; final text returned
  "for you to send", with the explicit note "FRIDAY has not sent this
  email automatically". Nothing was sent anywhere.

Live artifact left behind: draft mf-1 sits APPROVED in FRIDAY's
meeting-follow-up store on FRIDAY-Server (title "FRD-054 live probe test
meeting" — self-evidently a probe; no notification, no send). No delete
operation exists in the tool; recorded here so the owner can ignore it.

## IG2-FRD-03 — NOT VERIFIED (genuine live defects)

Three chat executions, all HTTP 200, all through live FRIDAY on
FRIDAY-Server:

1. Natural request ("Generate leads for me from this business directory
   page ...", FindYello search page, category general, max 1 page):
   59.0s wall, server 56.78s. Routed DIRECT_REASONING (journal: "Routed
   query ... to 'DIRECT_REASONING' (Score: -16.5, Avoided External:
   True)"). `lead_generate` NEVER EXECUTED — zero journal hits. Reply was
   a how-to-scrape guide, no table. The capability router
   (FRIDAY/src/friday/routing/capability_router.py) has NO keyword set or
   TOOL_EXECUTION branch for lead intents — the same file carries per-task
   exclusions for fleet/research/portfolio/code (TASK-API-002, INT-002,
   STR-002, FOR-002) but nothing for lead generation. Natural requests
   cannot reach the tool.
2. Explicit request ("Execute the lead_generate tool with directory_url
   <FindYello search page>, category general, max_pages 1"): 82.1s wall,
   server 79.88s. Tool executed 16:30 IST, authorization APPROVED,
   completed 0.4206s, Success FALSE: "Lead generation failed: Client
   error '403 Forbidden' for url 'https://www.findyel...'". The directory
   blocks the AWS host's plain-HTTP fetcher (bot protection). The agent
   reported honestly ("permission was denied for that step. Nothing was
   substituted or made up") — no fabricated table.
3. Explicit request, second directory (JaRanks best-insurance-brokers page,
   category insurance, max_pages 1): 51.2s wall, server 48.89s. Tool
   executed 16:32 IST, Success TRUE, 1.8156s. Reply: "65 leads" — but the
   table has **0 phone numbers and 0 email addresses** in all 65 rows, and
   includes navigation junk as leads ("JaRanks", "Ask Jamaica", "The
   JaRanks newsletter", "Home", "AH", "How we chose", "Rank", "Profile")
   alongside real broker names (BCIC, Covenant, Guardian General,
   Caribbean Assurance, Advantage General, Axia, BCMG). The parser takes
   every link block on the page, not business listings, and the page's
   contact details are not in tel:/mailto: links the parser reads. The
   tool runs end-to-end live (fetch → parse → dedupe → table) but the
   delivered table is not a usable contact table.

Fix task named: **TASK-IG2-FRD-03-FIX-01** — (a) router rule for lead
intents in capability_router.py (keyword set + TOOL_EXECUTION branch,
same pattern as TASK-API-002/INT-002), so natural requests reach the
tool; (b) fetcher robustness (browser-like headers or a fetch path the
directory accepts — FindYello 403s the current plain client); (c) parser
listing-block tightening (exclude nav/chrome links, require a contact
signal) + re-probe on a real directory until a table with phones/emails
is delivered. Do not mark IG2-FRD-03 verified until it lands and is
re-probed.

## IG2-FRD-05 — NOT VERIFIED (not run — environment block)

Browser task (browser-task:019cacc2-8ba1-5e3f-b55a-bb4c6551969b,
16:29–16:30 IST, measured): the live stage at
https://friday-universe.duckdns.org/friday/ loads (ULTRON COMMAND ·
TASK-WEB-003, LIVE, STANDING BY, agents awake 6/9, Fleet Link answering,
no sign-in). The wake control (CONTROL panel, bottom right) reads
"WAKE WORD OFF" on load. Two arm attempts (click + reload + click)
produced no microphone permission prompt; each returned to OFF with
"Wake word off — the browser refused microphone access." No live
listener ever armed, so neither "hey friday" (should fire) nor bare
"friday" (should stay inert) could be tested. This is the DESIGNED
refusal path, confirmed in code (UltronStage.tsx:345-349 sets armed false
and shows exactly that message on mic refusal; WakeListener.tsx: "If the
browser has no speech recognition, or refuses the microphone ... it never
retries a refused microphone in a loop"). No code defect found. The
hearing test is still owed and needs a mic-capable browser run (owner's
browser, or a run with microphone input available). Open question, not a
defect: the preference default in code is ARMED (wakeWord.ts, owner
decision 2026-11-18), but a fresh browser showed OFF on load — consistent
with the mic-refusal path disarming on mount, but not proven; the retest
should record the initial state in a mic-capable browser.

## Corrections to checkpoint 1 (this run, verified first-hand)

- "No live FRIDAY on FRIDAY-Server to probe" is withdrawn: FRIDAY-Server
  is live (services active, /health healthy, 149-tool registry, 8 chat
  legs executed). Only S1 is down, by design.
- The VOI-038 run-23 note (FRIDAY.service active 2026-11-24 ~17:00 IST)
  remains unreconciled — WATCH093 noted it as not reliable until
  reconciled. Not resolved here.
- S1 FRIDAY.service must NOT be restarted (WATCH093 ruling).

## Five states (TASK-FRD-054)

- implemented: YES (items merged; tools in the live registry)
- tested: PARTIAL (8 live chat legs + 1 browser task; injection not run)
- merged: NO (this work PR)
- deployed: YES (tools live on FRIDAY-Server)
- production-verified: PARTIAL (2 of 4: FRD-04, FRD-06)

## Schedules / usage

- `muse15-work-request`: cancelled on claim (correct while holding a task).
  Self-check + weekly reset armed.
- Usage: 25% of free weekly limit (checked this run; reset Mon Nov 30,
  7:04 PM IST). Additional tokens 0% used.

— Muse 15
