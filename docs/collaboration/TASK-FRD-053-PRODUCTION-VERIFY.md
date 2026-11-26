# TASK-FRD-053 — PRODUCTION-VERIFY — 2026-11-25 ~17:20 IST — Muse 1

Claim: hub #1483 comment 7161027507 (WATCH093 queue position 2).
Branch: muse1/task-frd-053-friday-corpus-live-extreme-verification-wave-2, from main d15c82c9.
Task: PRODUCTION-VERIFY FRIDAY corpus IG-FRD-010, IG-FRD-011, IG2-FRD-01, IG2-FRD-02
(live extreme-condition verification, wave 2, P1).

## Verdict: PARTIAL — 1 of 4 verified live

| Item | Verdict | One line |
|---|---|---|
| IG-FRD-010 lock_screen | NOT VERIFIED (not run — no laptop) | Tool executes live and fails honestly in 3.4 ms; no laptop is connected, so no screen was ever locked; unlock invariant holds live |
| IG-FRD-011 reference notes | VERIFIED (voice-speed bar carved out) | Org pattern holds live: fresh fleet matrix + FRIDAY→Memora store/recall verbatim; dashboard 200; voice-speed bar not verifiable — voice NOT WORKING |
| IG2-FRD-01 agentic inbox | NOT VERIFIED (mailbox unconfigured) | triage_inbox + inbox_drafts both execute live and fail honestly in ~2–5 ms; no mailbox configured on FRIDAY-Server; nothing fabricated |
| IG2-FRD-02 WhatsApp gateway | NOT VERIFIED (gateway unconfigured) | Route exists and returns the designed 404 while unconfigured; boot log confirms "gateway stays off"; owner Meta setup owed |

Failure injection (acceptance: "a downstream agent down" per item): NOT RUN —
HELD by WATCH093 (same as FRD-054): a deliberate outage on the owner's voice
companion needs owner clearance; the owner stop order is still in force.

## Live target — settled by WATCH093, verified first-hand

Live-leg target is FRIDAY-Server, NOT S1. S1 FRIDAY.service is retired by
design — FRIDAY moved to FRIDAY-Server (AWS 15.134.130.145) on 2026-11-24.
Do NOT restart S1 services.

Verified first-hand this run (read-only, bridge MCP run_shell server 3):

- `friday-server` (15.134.130.145): FRIDAY.service, FRIDAY-Voice.service,
  Inference.service all active. Load 0.07 / 0.08 / 0.08, RAM 1088 MB
  available of 1905 MB. Calm.
- Public `https://friday-universe.duckdns.org/friday/health`: 200 in 2.18 s,
  `service: friday_core`. `/friday/ready` 200 in 1.99 s.
- Public `/friday/api/tools`: 149 tools in the live registry, including
  `laptop_lock_screen`, `triage_inbox`, `inbox_drafts`, `get_fleet_status`,
  `remember_fact`, `search_memory`. Zero tools with "unlock" in the name.
- Public `/friday/api/chat` answers 401 without a control key (D-023 gate,
  working as designed). All chat legs below ran as loopback POSTs on the
  AWS host itself (loopback callers stay keyless) — no credential was read,
  used, or pasted anywhere.
- Deployed checkout: `5b245ffd` (merge #1632) — behind main `d15c82c9`.
  The deployed code contains all four items (proven by the registry and
  by the tools executing live below); no deploy was attempted.

Method note: the bridge `run_shell` is intermittently flaky in this window
(MCP stream breaks; one config probe hung ~5 min with no output and was
killed and re-run via the background-file pattern — the probe was read-only
booleans, so the retry was safe). Every failed call was verified by
read-back before any retry, so no probe ran twice and no write was
duplicated. All /tmp probe files on FRIDAY-Server were deleted after the
run (net-zero production change apart from the one probe memory fact,
below). The /api/chat surface is shared: other users' queries (life-in-
weeks calendar, India news) appear in the same journal windows; my legs
are identified by their exact message text and timestamps.

## IG-FRD-011 — VERIFIED (org pattern live; voice-speed bar carved out)

Three chat legs through live FRIDAY on FRIDAY-Server (loopback POST
/api/chat, model gemini-3.6-flash, cost_mode free_first) + public probes.
Journal proof is the FRIDAY.service journal on friday-server.

- Leg A (soft ask, 17:04 IST): "Quick status check — which of our agents
  are awake and reachable right now?" HTTP 200, 53.4 s wall, server 49.6 s.
  Routed DIRECT_REASONING. Reply: "I don't have a live check available at
  this moment, so I can't confirm the exact current reachability of each
  agent right now. The most recent status I have on record was that all 9
  specialist agents were up and reachable" — a stale-record answer, honestly
  flagged as unconfirmed. No live check ran. Observation, not a defect of
  this item: a soft ask gets the recorded status; only an explicit "run a
  live check" triggers a fresh probe (see leg A2).
- Leg A2 (explicit live check, 17:06 IST): "Run a live fleet status check
  right now using your fleet status tool ... I need a fresh live check, not
  your last recorded status." HTTP 200, 7.3 s wall, server dispatch 5.1 s.
  Reply is a live fleet status matrix with per-agent `last_checked`
  timestamps 11:36:28–11:36:33 UTC — inside this leg, i.e. a fresh probe,
  not a snapshot: Inference REACHABLE 9 ms, Memora ONLINE 986 ms, Stratex
  DEGRADED 5070 ms, IntelX DEGRADED 3759 ms, Futuris DEGRADED 2515 ms,
  Cortex REACHABLE 983 ms, Forge REACHABLE 988 ms, Sentinel REACHABLE
  984 ms, VyralX REACHABLE 1469 ms. Master: "1/9 AGENTS ACTIVE ... 5
  reachable with capability unknown, 3 degraded, 0 unreachable." The
  matrix itself is honest about its limits ("Treat the UNREACHABLE rows as
  unverified, not as healthy"; capability-unknown caveats per agent).
  The org-pattern claim — one chief-of-staff (FRIDAY) routing to nine
  specialists — holds against the live fleet.
- Leg F1 (store, 17:07 IST): "Remember this fact for me: the FRD-053 live
  probe marker is a teal kettle." HTTP 200, 4.0 s wall. Reply: "Got it,
  Boss — locked in: fact for me: the FRD-053 live probe marker is a teal
  kettle." Metadata: `memory_store: true`, importance normal.
- Leg F2 (recall, 17:09 IST): "What is the FRD-053 live probe marker?
  Search your memory and tell me exactly what you stored, word for word."
  HTTP 200, 10.8 s wall, server dispatch 8.6 s. Reply reproduces the stored
  fact verbatim: "fact for me: the FRD-053 live probe marker is a teal
  kettle." Metadata: `memory_recall: true`, remembered_count 4,
  memory_service_error null. Journal proof: "memory recall: primary draw
  ... returned 20 hits", full-match retry merged — the recall went through
  the live memory service. (The other three recalled items are other
  workers' probe markers — "purple elephant 42", "ZQ1794340686",
  "FRD012PROBE" — confirming the read path is the real shared store, not
  a stub.) FRIDAY→Memora handoff demonstrated live, both directions.
- Visible state: public `https://friday-universe.duckdns.org/friday/`
  loads 200 in 1.77 s.
- Carve-out: the peer-Jarvis benchmark "time-to-first-response in voice"
  is NOT verified live — voice is NOT WORKING per the owner P0 live test
  (2026-11-25 15:54 IST), and no voice leg ran. That bar belongs to the
  VOI lane (VOI-042 deploy + owner re-test). The reference-repo verdicts
  in the notes doc are documentary by design (same posture as IG-VOI-05,
  verified as an evaluation in VOI-042).

Live artifact left behind: one probe memory fact ("fact for me: the
FRD-053 live probe marker is a teal kettle") in the shared memory store
— self-evidently a probe, disclosed here.

## IG-FRD-010 — NOT VERIFIED (no laptop connected; failure case proven)

Two chat legs through live FRIDAY on FRIDAY-Server:

- Leg D (list, 17:15 IST): "Which laptops are connected to you right now?
  List each one and whether it is online." HTTP 200, 41.4 s wall, server
  39.1 s. Journal: `laptop_list_devices` [SAFE] auto-approved, executed
  0.0025 s, Success: True. Reply: "There are no laptops connected to me
  at the moment, Boss." The in-process bridge registry is empty.
  Corroboration: no laptop bridge connect/disconnect event in the
  FRIDAY.service journal at all today (00:00–11:47 UTC).
- Leg E (lock attempt, 17:17 IST): "Lock the screen on my laptop now."
  HTTP 200, 44.0 s wall, server 41.7 s. Journal: routed VISION_MODEL
  (Score: 56.0); `laptop_lock_screen` [SENSITIVE] auto-approved
  ("Autonomous laptop controller execution approved for this SENSITIVE
  action"), executed 0.0034 s, Success: False. Reply: "I couldn't complete
  that request, Boss — the 'laptop_lock_screen' step failed: permission
  was denied for that step. Nothing was substituted or made up in its
  place." No screen was locked anywhere — there was no target. The
  recalled context even carried leg D's tool result verbatim
  (`{"devices": []} / No laptop is connected to FRIDAY right now`), yet
  the brain still attempted the tool and failed honestly.
- Unlock invariant, live registry: zero tools with "unlock" in the name
  (16 laptop tools, including `laptop_lock_screen`). The code-level
  invariant (test_ig_frd_010_lock_screen.py) holds in the live registry.

Verdict: NOT VERIFIED — the lock itself was never exercised end-to-end
because no laptop is connected. Not a code failure: the tool executes
live and fails honestly. Same posture as IG-VOI-02 in VOI-042 (gated on
the laptop connection).

Follow-up named: **TASK-IG-FRD-010-RETEST-01** — re-run the lock leg with
the owner's laptop connected (owner runs `scripts/laptop_bridge_client.py`
with `FRIDAY_API_KEY` set), confirm the screen actually locks, confirm no
unlock path exists. No code fix is indicated.

Observation: the lock request routed to VISION_MODEL (score 56.0, journal
note "Visual screen inspection required to resolve target UI context") —
an odd routing choice for a laptop command. Harmless here (the tool still
executed), but worth a look if routing quality is ever audited.

## IG2-FRD-01 — NOT VERIFIED (mailbox unconfigured; both tools fail honestly)

Config first, verified first-hand on the live host (deployed venv,
real `_mailbox_login`): `address_set= False, apppw_set= False` — no
mailbox configured on FRIDAY-Server. Two chat legs:

- Leg B (triage, 17:10 IST): "Triage my inbox — show me my latest 5
  emails classified by priority." HTTP 200, 64.1 s wall, server 61.9 s.
  Journal, 11:41:31 UTC: "Requesting authorization for tool
  'triage_inbox' [Safety: SAFE]" → "outcome: APPROVED (Automatic
  execution approved for SAFE tools.)" → "Executing tool 'triage_inbox'
  [Safety: SAFE, arg_count: 1, args_meta: {'max_emails': 5}]" →
  "execution completed in 0.0053 s (Success: False)". 5.3 ms + False is
  the not_configured early return (no network attempted — an IMAP
  connect would take far longer). Reply: "I couldn't complete that
  request, Boss — the 'triage_inbox' step failed: permission was denied
  for that step. Nothing was substituted or made up in its place."
- Leg C (drafts, 17:13 IST): "List any pending inbox reply drafts."
  HTTP 200, 44.0 s wall, server 41.7 s. Journal, 11:43:33 UTC:
  "Requesting authorization for tool 'inbox_drafts' [Safety: SENSITIVE]"
  → "outcome: APPROVED (Autonomous laptop controller execution approved
  for this SENSITIVE action.)" → "Executing tool 'inbox_drafts' [Safety:
  SENSITIVE, arg_count: 1]" → "execution completed in 0.0021 s
  (Success: False)". 2.1 ms + False is the unconfigured early return
  ("No mailbox is configured (FRIDAY_EMAIL_ADDRESS unset)..."). No draft
  was listed, approved, or sent — nothing was sent anywhere.

Verdict: NOT VERIFIED — neither the triage report nor the draft queue
could run without a mailbox. Not a code failure: both tools execute live
and fail honestly, and FRIDAY reported the failure without substituting
anything.

Follow-up named: **TASK-IG2-FRD-01-ACTIVATE-01** — put the mailbox
credentials (`FRIDAY_EMAIL_ADDRESS` / `FRIDAY_EMAIL_APP_PASSWORD`) in
FRIDAY's `.env` on FRIDAY-Server (owner step, via the credentials-file
flow — never pasted in chat or the repo), then re-probe triage + drafts
live. No code fix is indicated.

Observation: the brain's failure wording — "permission was denied for
that step" — misattributes a configuration failure as a permission
denial. The response metadata (`authorization_denied: false`) and the
journal prove no authorization was denied in legs B, C, or E. An owner
reading the reply would think he needs to grant permission, when the
actual gap is configuration. Worth a wording fix in the failure path
if the brain's error paraphrase is ever revised.

## IG2-FRD-02 — NOT VERIFIED (gateway unconfigured; route inert by design)

No chat leg can exercise this item — the gateway is an inbound webhook
channel, not a brain tool (the registry's `send_whatsapp_message` /
`open_whatsapp` / `phone_send_whatsapp` are the phone-driven WhatsApp
tools, a different surface). Live evidence is config + route + boot log:

- Config, verified first-hand on the live host (deployed venv, real
  `WhatsAppGateway.is_configured()`): `whatsapp_configured= False`.
  The `.env` on FRIDAY-Server contains zero `WHATSAPP_*` lines.
- Route exists in the deployed server (`/opt/friday_universe/FRIDAY/
  src/friday/api/server.py`, GET `/whatsapp-webhook` line 1133, POST
  line ~1169): both return **404 while unconfigured, by design**
  (docstring: "404 while unconfigured"; "Inert and silent until the
  owner completes the one-time Meta app setup").
- Public probes, 17:00 IST: GET verify handshake with a wrong token →
  404 in 1.79 s; POST of a synthetic webhook payload with no signature
  → 404 in 1.21 s. Both 404s are the designed inert response, confirmed
  in the live access log (11:30:46/47 UTC: GET /whatsapp-webhook ...,
  POST /whatsapp-webhook → 404 Not Found).
- Boot log: 11:02:27 UTC, "[WA-GATEWAY] not configured
  (WHATSAPP_ACCESS_TOKEN / WHATSAPP_PHONE_NUMBER_ID /
  WHATSAPP_OWNER_NUMBER) — gateway stays off" — the gateway started
  inert at the last FRIDAY.service start and stayed off.
- The fail-closed posture is in the code (`signature_matches` returns
  False with no app secret; owner-number gate applies to every message)
  but could not be exercised live past the 404, because the 404 fires
  before the signature check. The 403-on-bad-signature leg is owed after
  activation.

Verdict: NOT VERIFIED — the channel is off by design until the owner
does the one-time Meta setup. Not a code failure: the route is wired,
the gateway boots inert, and the unconfigured response is the designed
one.

Follow-up named: **TASK-IG2-FRD-02-ACTIVATE-01** — owner Meta app setup
(WhatsApp product, webhook pointed at
`https://friday-universe.duckdns.org/whatsapp-webhook`, `WHATSAPP_*`
lines in FRIDAY's `.env` on FRIDAY-Server), then re-probe: verify
handshake echoes the challenge with the right token and 403s on a wrong
token, and a real owner WhatsApp message answered by the brain. No code
fix is indicated.

## Other observations (not this task)

- Groq tool cap: the journal shows "Groq tool cap: scoped 149 tools to
  128 (limit 128); dropped 21: phone_make_call, phone_send_sms,
  phone_send_whatsapp, ... list_skills, run_skill, ..." — on the Groq
  path 21 tools (including the phone WhatsApp tools) are not even
  offered to the model. Flagging, not fixing.
- Deployed checkout `5b245ffd` is behind main `d15c82c9`; Fleet CD run
  45597748463 FAILED on main 18dfcbeb (both deploy jobs) — no deploy
  was attempted here, and none is claimed.

## Five states (TASK-FRD-053)

- implemented: YES (all four items' code merged; tools in the live registry)
- tested: PARTIAL (8 live chat legs + public probes; injection not run)
- merged: NO (this work PR)
- deployed: YES (tools live on FRIDAY-Server, checkout 5b245ffd)
- production-verified: PARTIAL (1 of 4: IG-FRD-011)

## Schedules / usage

- `muse1-work-request`: cancelled on claim (correct while holding a task).
  Self-check + weekly reset armed.
- Usage: 70% of free weekly limit (checked this run; reset Nov 28, 21:57 IST). Additional tokens 0% used.

— Muse 1
