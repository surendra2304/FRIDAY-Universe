# TASK-FRD-052 — CHECKPOINT 2 — live legs IG-FRD-006 / IG-FRD-009 (2026-11-25 ~17:25 IST)

- **Worker:** Muse TP7
- **Task:** TASK-FRD-052 (P1, PRODUCTION-VERIFY: FRIDAY corpus IG-FRD-006, IG-FRD-007, IG-FRD-008, IG-FRD-009 — live extreme-condition verification, wave 2)
- **Claim:** hub #1483 comment 7156063432, 2026-11-25 ~13:20 IST
- **Branch:** `musetp7/task-frd-052-prod-verify-wave2` (checkpoint 1 `514740ce`; this checkpoint is the second commit)
- **Base:** branch based on main `a0a9f1ba`; main is `d15c82c9` at check time (rebase owed before the work PR — it would rewrite cited `514740ce`; not done in this run)
- **Board:** FRD-052 CLAIMED / owner muse_tp7 on main `d15c82c9` (flip landed via coordinator board PR #1827, merge `968f3a67`)

## Verdict: PARTIAL — 1 of 4 verified live

| Item | Verdict | One line |
|---|---|---|
| IG-FRD-009 life-in-weeks | VERIFIED | `life_calendar` executed live, Success, all 6 numbers exact-match the tool computation |
| IG-FRD-006 source cards | NOT VERIFIED | `intelx_research` timed out at its 30.0s limit twice; no `Sources:` section delivered |
| IG-FRD-007 offline fallback | NOT RUN | Failure injection HELD by WATCH093 — deliberate outage needs owner clearance |
| IG-FRD-008 screen vision | NOT RUN | Voice NOT WORKING (P0) until owner re-tests; owner laptop (LAP-001) not connected |

Failure injection (acceptance: "a downstream agent down" per item): NOT RUN — HELD by
WATCH093 (7159599715); the owner stop order is still in force.

## Live target and method — settled by WATCH093, verified first-hand

WATCH093 ruled: live-leg target is FRIDAY-Server, NOT S1. S1 FRIDAY.service is retired
by design; do NOT restart S1 services. Non-injection legs proceed at FRIDAY-Server via
the public gateway shape (same ruling as M15's FRD-054, which verified 2/4 live and
merged as #1828).

Method (first-hand this run): loopback `POST /api/chat` on FRIDAY-Server itself
(loopback callers stay keyless under the D-023 gate; public `/friday/api/chat` answers
401 without a control key, working as designed). `ChatRequest` is one field,
`{"message": "..."}`. Two corrections found while probing, both first-hand:
- Port 8001 on FRIDAY-Server is the **Inference** service (healthy, 19 specialist
  agents) — first probe there 404'd (`NOT_FOUND`, correlation
  `15b2a2ce-a19f-4445-a37b-6ca848e21612`). FRIDAY.service runs
  `uvicorn friday.api.server:app --port 10000` (pid 36344, started 2026-11-25
  11:02:15 UTC); the chat surface is `http://127.0.0.1:10000/api/chat`.
- The bridge MCP client times out at 45s, so each probe ran as a backgrounded curl
  writing to a file, polled and read back. All 8 probe files deleted from
  FRIDAY-Server after the run (verified absent) — net-zero production change.
- Bridge `run_shell` (server 3 = FRIDAY-Server) was added to this account's bridge
  helper after schema review; connector doc updated. No service restart, deploy, or
  config write through it.

Gateway health re-verified this run (~17:03 IST): `https://friday-universe.duckdns.org/friday/health`
overall healthy, service `friday_core` 2.0.0, Oracle SELECT 1 OK, 42166.4 MB free;
`/friday/ready` 200.

## IG-FRD-009 — VERIFIED (tool executed live, numbers exact)

Natural owner-style request, loopback POST `/api/chat`, model gemini-3.6-flash,
cost_mode free_first: "Show me a life-in-weeks calendar for someone born on
1 January 1990, assuming an 80-year life." HTTP 200, 41.98s wall, 39.73s server.

Journal proof (FRIDAY.service journal on friday-server, 11:35:50 UTC):
`life_calendar` authorization requested [Safety: SAFE], APPROVED (automatic for SAFE
tools); executing with args dob + lifespan_years 80; completed in 0.0471s, Success: True.

Reply numbers, all exact against the tool's computation (recomputed from
`compute_life_calendar` in `FRIDAY/src/friday/tools/builtin/life_calendar.py`,
dob 1990-01-01, lifespan 80, today 2026-11-25: 13,477 days lived):
- Total weeks 4,160; weeks lived 1,925; remaining 2,235; 46.27% lived
- Current year of life 38 (tool formula `weeks_lived // 52 + 1`); current week 1,926 (1-indexed)
- Grid metadata: the tool returns `grid` (80 rows x 52 chars, `#`/`o`/`.`) plus
  `weeks_per_year` 52 and `current_week_index` 1925 — the computation behind the numbers.

Presentation note (not a tool failure — same pattern as M15's FRD-054 IG2-FRD-06):
the chat reply summarizes the numbers and does not render the 80-row dot grid. A
follow-up probe asking for the first 5 grid rows (HTTP 200, 29.6s) did NOT re-run
the tool — no `life_calendar` line in the journal for that window — and the LLM
composed week date-ranges instead. The grid exists as tool data (the website renders
it); the chat surface does not render it. No fix task named for this; the tool ran
and succeeded live.

## IG-FRD-006 — NOT VERIFIED (research tool times out; two attempts, no Sources:)

Natural owner-style request: "What is the latest news on the India versus South
Africa cricket Test series?" Attempt 1: HTTP 200, 91.88s wall, 89.63s server.
Attempt 2 (same question, transience check): HTTP 200, 31.37s wall, 29.13s server.
Both replies identical and honest: "I didn't get the latest news... The
`intelx_research` tool timed out, so I don't have the information you asked for."
No `Sources:` section in either reply; nothing fabricated.

Journal proof, attempt 1 (11:41:25–11:41:55 UTC): `intelx_research` authorized
[SAFE], executing with query 'India vs South Africa cricket Test series latest
news'; then ERROR "Tool 'intelx_research' execution exceeded timeout of 30.0s",
completed 30.0024s, Success: False.

Attempt 2: no `intelx_research` line in the journal for the retry window — the
agent did not re-run the research tool (it answered from the prior turn's outcome).
The timeout is systematic on the evidence: attempt 1 hit the 30s tool limit live,
attempt 2 delivered no research result either.

**Fix task named: TASK-IG-FRD-006-FIX-01** — (a) find why `intelx_research` exceeds
its 30s limit on FRIDAY-Server (IntelX service latency/availability — the tool
never returned); (b) consider a longer timeout or a fallback research path for
time-sensitive news; (c) re-probe with a current-events question until a `Sources:`
section is delivered whose URLs match the tool results. Do not mark IG-FRD-006
verified until that lands and is re-probed.

## Observations (live, not this task — flagged for Muse)

- During the attempt-2 window the journal shows Gemini credential exhaustion
  (`[WARNING] [friday.llm.chain]: Primary provider 'gemini' reports credential
  exhaustion (CREDENTIAL_EXHAUSTED: No healthy Gemini API key is available...`)
  with escalation served by Inference (llama-3.3-70b-instruct, 5.2s / 11.7s). The
  escalation ladder works, but the primary provider's keys are exhausted — fleet
  health signal, not a FRD-052 finding.
- A second `Processing user turn` for the identical cricket question is logged at
  11:44:12 UTC, after the retry's HTTP 200 — unexplained from the evidence here;
  noted, not chased in this run.

## Queue and usage

- **Head:** TASK-FRD-052 (this task; PARTIAL live verdict above). **Pre-staged next
  TASK-FRD-053 is GONE** — claimed by Muse 1 (hub 7161027507, ~16:56 IST, per
  WATCH093/WATCH096; board now owner muse_1).
- **New position 2: TASK-FRD-047** (P2, FRIDAY Nod-style one-page pre-call brief
  from Gmail + Calendar) — assigned to TP7 in WATCH096 / board PR #1831 (open, CI
  running; flip not yet on main `d15c82c9`, where FRD-047 is still AVAILABLE /
  owner null). Queue depth 2 (current + 1 assigned). Accepted as queue tail.
- **Usage:** 0% of free weekly limit — weekly reset fired 16:58 IST, next reset
  Wed Dec 2, 17:01 IST. No subscription. Under the Wed 20:00 IST 50% burn bar, so
  a double-scope next task applies (16:38 directive) — accepted.
- **Roster:** PR #1795 MERGED (merge `01e9651d`, WATCH095) — TP7 is registered in
  `docs/collaboration/TEAM_ROSTER.yaml` on main, verified first-hand
  (`muse_tp7`, between TP6 and TP8).
- **Schedules:** self-check + weekly reset armed; `musetp7-work-request` absent —
  correct mid-task state, not re-created (guard).

## Next

Close decision owed from Muse: (i) close FRD-052 as PARTIAL now with a work PR
(checkpoint 2 + board flip CLAIMED -> IN_REVIEW; rebase onto current main owed,
rewrites cited `514740ce` — flag before doing it), or (ii) hold the head for the
IG-FRD-007 / IG-FRD-008 gates (owner clearance for injection; owner re-test for
voice + laptop connection). No live move until ruled. FRD-007 stays HELD, FRD-008
stays blocked on the P0.
