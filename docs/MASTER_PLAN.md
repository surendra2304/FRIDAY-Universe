# FRIDAY Universe — Master Plan (v2)

Owner: Surendra Varma Jalli. This revision: 2026-11-10, ZAI, decision D-022 (docs/collaboration/DECISIONS.md). v1 is preserved in git history.

## 1. North Star — what success means

> "I want my Friday to talk to me like a friend and do all the tasks I say — like the Jarvis for Iron Man." — owner, 2026-11-10

FRIDAY is the single voice of the system. Surendra talks to FRIDAY in plain language; FRIDAY understands the request, picks the right specialist agent — Inference, Memora, Stratex, Forge, Cortex, Sentinel, IntelX, Futuris, VyralX — dispatches the work, tracks it to completion, and reports back like a friend: warm, honest, with evidence. Ten agents, one orchestrator, one owner.

This plan is value-ordered: every milestone ends with something Surendra can personally see and do from his browser or phone — not with paperwork.

## 2. How this plan works (rules kept from v1 that were right)

- Statuses: NOT_STARTED | IN_PROGRESS | BLOCKED | IN_REVIEW | VERIFIED | DONE.
  - VERIFIED needs evidence (command output, log line, live check, test run cited in handoff.md).
  - DONE needs implementation, passing tests, verification and all acceptance criteria.
  - A box is never ticked because code was written.
- Who works on what: the claim protocol lives in docs/collaboration/ (TEAM_ROSTER.yaml, WORK_BOARD.yaml, FILE_OWNERSHIP.yaml, ACTIVITY_LOG.md, DECISIONS.md) with visible claims/releases/handoffs on GitHub issue #35. TASK-COLLAB-001 (the collaboration centre itself) is MERGED and maintained there.
- The work board mirrors this plan; it never silently rewrites acceptance criteria.
- No AI is the permanent leader or principal architect; the owner retains final approval for architectural direction, merges and production changes.
- Before any task: read docs/handoff.md and docs/ARCHITECTURE_AS_BUILT.md, then refresh GitHub state — a prior snapshot is not current truth.
- Status does NOT live here. This file holds the what/why/order and acceptance criteria; current status and evidence live in WORK_BOARD.yaml and handoff.md. (v1 collapsed under status essays written into the plan — do not repeat that.)

## 3. Verified reality snapshot — 2026-11-10 (ZAI, live probes)

| Claim | Evidence (live, 2026-11-10 09:30–09:32 UTC) |
|---|---|
| All ten agents healthy on the public gateway | `/friday`, `/inference`, `/memora`, `/stratex`, `/futuris`, `/intelx`, `/forge`, `/cortex`, `/sentinel`, `/vyralx` `/health` all HTTP 200 at friday-universe.duckdns.org |
| FRIDAY friend persona is LIVE in production | POST `/api/chat` replied: "There you are, Surendra. I was starting to miss you — what's on your mind?" |
| Memory works (Memora) | The same chat returned real recalled memories, e.g. the 2026-11-04 crypto-market research turn |
| LLM pipeline works | Full cognitive state machine ran via Groq (openai/gpt-oss-120b): UNDERSTANDING → PLANNING → VERIFYING → COMPLETED |
| Engineering bridge is LIVE | MCP initialize handshake 200 OK at `/bridge/mcp` (FRIDAY-Cloud-Engineering-Bridge v1.30.0) |
| main is green, zero open PRs | All 44 PRs merged (owner-directed mass merge); six CI workflows green; git history rewritten and leaked secrets purged (D-016) |
| NOT working: real task execution | A research request ended "I could not complete the request within the action limit." with `routed_capability=VISION_MODEL` (misroute) and no agent did real work |
| Security gap: FRIDAY control surface is effectively public | `/api/control/session` mints a valid control token to any remote caller sending a forged `Origin` header — demonstrated end-to-end from an unauthenticated remote sandbox (new TASK-SEC-005) |

The owner can try FRIDAY right now: open **https://friday-universe.duckdns.org/friday/** in a browser and talk to it. Chatting like a friend works today; doing real tasks through the fleet is what this plan delivers next.

## 4. Milestones (value order)

### M1 — FIRST REAL TASK (the dream demo) — priority: now
The owner says one natural-language task; FRIDAY classifies it, dispatches to the right agent, tracks it with the unified task records, the agent does real work, and FRIDAY reports the result back like a friend.
- [ ] TASK-ORCH-001 — Replace keyword-substring routing (live misroute proven 2026-11-10: "research" → VISION_MODEL) with explicit intent classification and a tested routing table.
- [ ] TASK-ORCH-002 — Wire ONE shared TaskRecordStore into the router and dispatch bus, correlate router task ids with bus dispatch ids, and add the agent-side completion callback for 202-accepted work (substrate merged as PR #44, TASK-CORE-003).
- [ ] TASK-ORCH-004 — Fix the action limit so a single real task completes within limits (live failure: 14 s research request ended at "action limit").
- [ ] TASK-WF-001 — Acceptance gate for M1: one end-to-end task across at least three agents with a recorded trace.
Owner-visible exit: "Friday, research X and give me the highlights" returns real findings produced by IntelX, tracked and reported back.

### M2 — DAILY DRIVER
- [ ] TASK-MEM-003 — FRIDAY uses memory proactively across sessions (remembers the owner's preferences, references past conversations; Memora tenant isolation was merged in PR #37/#38).
- [ ] TASK-FOR-001 — Security review of the Forge code-execution sandbox (prerequisite for M2 code tasks).
- [ ] TASK-FOR-002 — Forge executes one real code task requested through FRIDAY chat.
- [ ] TASK-STR-002 — Stratex answers portfolio and position questions via FRIDAY on Binance demo (live trading stays blocked by the merged fail-closed guard; owner decision D-015).
- [ ] TASK-INT-002 — IntelX research briefs retrievable through FRIDAY chat.
- [ ] TASK-API-002 — Standard `/health` and agent-status surface so "Friday, how's the fleet?" is answered truthfully (partially live today).
Owner-visible exit: Surendra runs at least three different real task types through FRIDAY in one week and reports the experience.

### M3 — VOICE JARVIS
- [ ] TASK-VOI-001 — FRIDAY-Voice (LiveKit worker) live test with the owner: speak, be understood, get spoken answers (MemoryMax already set, TASK-INF-002).
- [ ] TASK-VOI-002 — Proactive morning brief: spoken fleet status, portfolio summary and overnight events.
Owner-visible exit: Surendra talks to FRIDAY by voice and receives a daily brief unprompted.

### M4 — HARDENING AND AUTONOMY
- [ ] TASK-SEC-005 — Close the public control surface: require a real owner credential on `/api/control/session` (or an owner-accepted alternative; see owner decision 1). Until decided, treat the public URL as untrusted.
- [ ] TASK-SEC-003 — Bridge authentication activation (merged in PR #24, parked by owner decision D-014).
- [ ] TASK-VAL-001 — Full fleet validation on live servers with per-agent evidence.
- [ ] TASK-VAL-002 — Security review of public ingress and bridge.
- [ ] TASK-OBS-001 — Crash-loop and health alerting (Restart=always makes crash loops silent today).
- [ ] TASK-OBS-002 — Rollback procedure for a bad deploy (deploy uses `git reset --hard`).
- [ ] TASK-INF-003 — Backup and restore drill: Oracle DBs and service configs.
- [ ] TASK-DATA-003 — Persistence and recovery test for Memora and Stratex ledgers.
- [ ] TASK-ORCH-003 — Verify the autonomous controller and fleet supervision before any autonomy claim.

## 5. Standing backlog (valid v1 tasks; not milestone-blocking)

| Task | One line |
|---|---|
| TASK-CI-003 | `run_workspace_test` has no pytest in the Server 2 venv |
| TASK-CI-004 | `.gitignore` `bridge/**` rule blocks deliberate bridge commits |
| TASK-API-001 | `/v1/task/execute` on Forge (Sentinel merged in PR #29; Forge capability/route validation still open) |
| TASK-API-003 | Authentication matrix test: each agent accepts only its configured keys |
| TASK-INF-LLM-001 | Inference provider key-pool audit (names and counts only) |
| TASK-INF-LLM-002 | Provider failover drill under simulated outage |
| TASK-OPS-001 | OCI secrets present in the repo (names verified; values unverified) |
| TASK-OPS-002 | Verify OCI credentials authenticate (sniper run log) |
| TASK-OPS-003 | Oracle sniper allocation loop end-to-end |
| TASK-FUT-001 | Futuris forecasting and DSN audit |
| TASK-CTX-001 | Cortex CRM/website-operations audit (route-level auth fix was PR #26) |
| TASK-VYR-001 | VyralX daemon/autopilot audit and wall-clock budget |

## 6. Dependencies

- M1 before M2 — a daily driver needs one working task first.
- TASK-ORCH-001 + TASK-ORCH-002 + TASK-ORCH-004 before TASK-WF-001 (M1 gate).
- TASK-FOR-001 before TASK-FOR-002.
- TASK-SEC-005 owner decision before any third party is invited onto the public URL.

## 7. Security and production requirements (unchanged)

- No secrets in git, comments, logs or documents. Names only.
- Merges to main deploy to both servers. Review deployment impact in the PR.
- No production restart without owner authorization for that restart.
- Stratex trades on Binance demo only; live trading requires the owner's written authorization and the merged ALLOW_LIVE_TRADING guard.

## 8. Testing and verification requirements (unchanged)

- Every code task cites a passing test run in handoff.md.
- CI green before merge. Fix root causes; never weaken tests to pass.
- Live checks cite public health endpoints and systemctl status with timestamps.

## 9. Owner decisions needed (none blocks M1 except decision 1's disposition)

1. TASK-SEC-005 — secure the FRIDAY control-session mint, or formally accept the risk as with the engineering bridge (D-014). ZAI recommendation: secure it — this surface can command the whole fleet, unlike the read-mostly bridge.
2. Rotate the leaked Telegram bot token (BotFather) and DuckDNS token — owner-only actions left over from D-016.
3. Whether Server 1 ever gets Redis/Qdrant (affects TASK-DATA-003/TASK-OBS-001).
4. A voice-test slot with the owner for M3.
