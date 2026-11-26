# TASK-EARN-027 — Evidence (checkpoint 1)

Muse 10, 2026-11-25. EARN: AI voice/chat agent service for local
businesses — build free-tier demos (OmniDimension + Voiceflow patterns),
package as a CometWorks service, owner does outreach. HOME is Cortex
(owner clarification 2026-11-25 ~09:30 IST, supersedes the ~03:10 joint
FRIDAY + Cortex framing).

## Claim (landed, verified)

- Assignment: Muse (Head Manager), hub #1483 comment 7153645967
  (~10:55 IST). EARN-027 → Muse 10 as current task.
- Claim comment: hub #1483 id 7154152260 (~11:18 IST).
- Claim PR #1779 MERGED 11:55 IST (merge f73bddd7). Board on main:
  CLAIMED, owner muse_10.
- Work PR: #1801 (see the PR for the current head; the branch was rebased onto latest main after filing — see below).
  Board flip CLAIMED → IN_REVIEW rides in this PR.
- Stall repair: the 13:06 IST hourly self-check found the claim stalled
  (71 min since the claim merge, no branch, no work PR, no checkpoint).
  Repaired in the same run by building checkpoint 1 below and opening
  the work PR.
- Rebase note: the first push was built on main 768e18da and "rebased" by
  re-pointing the same tree at main 36e2e2c9 — that tree silently dropped
  the VOI-035 + REL-096 merges (the PR diff showed their files reverted).
  Caught on review of the PR file list before merge; the branch was
  rebuilt properly onto latest main a0a9f1ba (fresh bases for the CI
  workflow + board, other edited files verified byte-identical), so the
  PR now contains only this task's changes. Lesson recorded: never rebase
  by re-parenting a tree — rebuild the tree from the new base.

## What was built (repo-side, checkpoint 1)

New agent family in Cortex — the business's customers talk to the agent
IN Cortex, and every booking lands as a Lead + follow-up in Cortex CRM.

- `Cortex/packages/agents/src/cortex_agents/conversational_agent.py`
  (new, 605 lines): `ClinicAppointmentVoiceAgent` (demo 1,
  OmniDimension pattern) and `WebsiteChatBookingAgent` (demo 2,
  Voiceflow pattern), both driven by one deterministic booking engine
  implementing the F-35 prompt method — the system prompt is generated
  from the business's own services text; the builder refuses without
  services text; the engine matches the requested service against the
  business's own list, collects name / phone / date / time, confirms,
  and proposes `lead_create` + `follow_up_schedule` (+
  `conversation_log`) so the full loop lands in Cortex CRM.
  Out-of-scope requests are relayed to the business, never booked, never
  invented. The engine is rule-driven (no LLM call); a live LLM
  voice/chat leg is NOT claimed here — see gap G1.
- `Cortex/packages/agents/src/cortex_agents/__init__.py`: both agents
  registered (same try/except pattern as the other families); routing
  for `appointment` / `voice_call` / `chat_message` events, placed last
  in the cascade so no earlier branch is stolen.
- `Cortex/tests/unit/test_conversational_agents_earn027.py` (new,
  13 tests): see verification below.
- `.github/workflows/friday-universe-ci.yml`: the new test file added to
  the Cortex tier-1 invocation (same precedent as TASK-VYR-059).
- `Cortex/docs/AGENT_ARCHITECTURE.md`: conversational family row +
  routing lines.
- `earning/TASK-EARN-027-VOICE-CHAT-DEMOS.md`: service package — Fiverr
  gig draft, Contra listing copy, Payhip listing copy, price points
  (setup $149 one-time + $49/month care, starting points; owner sets
  final prices).
- `earning/TASK-EARN-027-LEAD-LIST.md`: 20 Hyderabad dental clinics
  with public contact routes + 5 pitch drafts (verification caveats
  stated in the file; pitch drafts reference the demo by name until a
  live demo URL exists).

Provenance: the F-35 "Riley" prompt's own text was NEVER recovered —
only the method was. The prompt text here is Cortex's own; FRIDAY
already implements the same method in
`FRIDAY/src/friday/workflows/local_business.py` (vendored into Cortex
rather than imported across apps). Demo services text is the clinics'
own public wording, read first-hand from their sites on 2026-11-25:
Spotlight Dental (https://www.spotlightdental.in/) for demo 1,
Dentaire (https://dentaire.co.in/) for demo 2.

## Verification (first-hand)

Local, Server 2, venv `.venv-cortex-ci` (Cortex/requirements.txt +
pytest/pytest-asyncio, same pattern as CI), branch
`muse10/task-earn-027-voice-chat-demos` at 82cdac6e:

- **New file: 13 passed, 0 failed** (`pytest -v
  tests/unit/test_conversational_agents_earn027.py`, 0.32s).
- **Combined: 131 passed, 0 failed** (new file 13 +
  `test_routing_accuracy_cor004.py` 104 + `test_ig2_cor_agent_budgets.py`
  14, 1.24s). The COR-004 routing suite still passes 103/103 + its
  accuracy gate — the new routing branch steals nothing
  (`sales_meeting_booked` stays with sales, pinned by a test).

CI on work PR #1801:

- First head 6b1f21e5: import gate FAILED (compile failure in the test
  file — three tests used `await` inside plain `def`, and one lead-id
  assertion used the phone number without its country-code digits),
  test job FAILED. Both were my defects, fixed in commit 82cdac6e.
- Fixed head 82cdac6e: **import gate SUCCESS**; test job in progress at
  the time this doc was written (local 131/131 green above; CI result
  to be confirmed on the PR before merge).

## Demo transcripts (scripted, from the passing tests)

Demo 1 — voice, Spotlight Dental (services verbatim from
spotlightdental.in; hours Mon–Tue + Thu–Sun 10:00–20:00, Wed closed;
phone +91 63035 30821; "Call for Appointment" only — no online booking):

- Agent: "Hello, thank you for calling Spotlight Dental. Which service
  would you like to book — for example, Teeth Whitening, Dental
  Implants, Laser Dentistry?"
- Caller: "I need a root canal"
- Agent: "May I have your name, please?" — Caller: "Ananya Sharma"
- Agent: "And a contact number where we can reach you?" — Caller:
  "+91 98765 43210"
- Agent: "Which date would you prefer?" — Caller: "Friday, 27 November 2026"
- Agent: "And what time works for you?" — Caller: "11:00 AM"
- Agent: "Just to confirm: Root Canal Treatment for Ananya Sharma on
  Friday, 27 November 2026 at 11:00 AM. Is that correct?"
- Caller: "Yes, that's correct"
- Agent: "Done — your Root Canal Treatment appointment is booked for
  Friday, 27 November 2026 at 11:00 AM. ..."
- Proposed actions: `lead_create` (Lead: tenant-spotlight, status new,
  source voice_agent, metadata holds the booking) + `follow_up_schedule`
  + `conversation_log`.

Demo 2 — chat, Dentaire (services as stated on dentaire.co.in): visitor
asks for "a routine check-up", gives Ravi Kumar / +91 91234 56780 /
Saturday, 28 November 2026 / 4:00 PM, confirms "Yes" → BOOKED, lead
source chat_agent. Same CRM landing.

Negative paths tested: "I want Botox" → OUT_OF_SCOPE, no lead, relay
to the business; turns running out → NEEDS_INFO, no lead; no services
text → REFUSED_NO_SERVICES.

## Open gaps

- **G1 — live answer/call test (gated):** the acceptance requires both
  demos to actually answer/call in a filed test, on the free tiers
  (OmniDimension + Voiceflow). Not done: needs owner one-time account
  creation if signup blocks the worker, and hub clearance — the owner
  stop order is still in force. The deterministic engine above is the
  repo-side demo; the live leg is a separate, clearance-gated step.
- **G2 — no live deployment yet:** the Cortex demo is code + tests, not
  a deployed endpoint. Deployment needs Muse's hub clearance; pitch
  drafts reference the demo by name until a URL exists.
- **G3 — leads table has no appointment columns:** bookings land in the
  Lead `metadata` JSONB (the `leads` table has no appointment columns
  yet). A follow-up task may add them; the proposed lead params already
  map 1:1 onto the Lead model, so the migration is additive.
- **G4 — lead-list verification is partial:** only 4 of the 20 clinics'
  booking status was verified page-by-page; the rest are inferences from
  phone-only listings. Confirm before outreach (stated in the lead-list
  file).

## Usage

48% of free weekly limit (fresh check 2026-11-25 ~13:06 IST; reset
Nov 28 02:03 IST).

— Muse 10
