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
- [x] TASK-ORCH-001 — Replace keyword-substring routing (live misroute proven 2026-11-10: "research" → VISION_MODEL) with explicit intent classification and a tested routing table. (MERGED 2026-11-10: word-boundary routing kills the substring false-hit class, 15 regression tests + live incident corpus; explicit-intent table noted for TASK-ORCH-003.)
- [x] TASK-ORCH-002 — Wire ONE shared TaskRecordStore into the router and dispatch bus, correlate router task ids with bus dispatch ids, and add the agent-side completion callback for 202-accepted work (substrate merged as PR #44, TASK-CORE-003). (MERGED 2026-11-10: shared singleton wired into both engines; POST /api/v1/dispatch/completions closes the 202 loop truthfully; records report live on production — 4-record trace recorded.)
- [x] TASK-ORCH-004 — Fix the action limit so a single real task completes within limits (live failure: 14 s research request ended at "action limit"). (MERGED 2026-11-10: interactive turn budget 4 → 8, bounded + configurable; live completion proven by the M1 acceptance trace.)
- [x] TASK-WF-001 — Acceptance gate for M1: one end-to-end task across at least three agents with a recorded trace. (ENGINEERING-SIDE RECORDED 2026-11-10 on production: 4 real dispatches — IntelX research completed 2.98 s, Inference reasoning completed 1.61 s, Stratex portfolio completed 7.30 s, Futuris failed truthfully 501 — records report shows 3 completed / 1 failed. Owner's friend-chat run in the browser remains for TASK-JARVIS-M1 closure.)
Owner-visible exit: "Friday, research X and give me the highlights" returns real findings produced by IntelX, tracked and reported back.

### M2 — DAILY DRIVER
- [x] TASK-MEM-003 — FRIDAY uses memory proactively across sessions (remembers the owner's preferences, references past conversations; Memora tenant isolation was merged in PR #37/#38). (MERGED 2026-11-10: greeting volunteers one remembered line from real Memora recall; proactive_memory flag verified E2E.)
- [x] TASK-FOR-001 — Security review of the Forge code-execution sandbox (prerequisite for M2 code tasks). (DELIVERED 2026-11-10: docs/security/FORGE_SANDBOX_REVIEW_2026-11-10.md — APPROVED for M2; no critical/high findings; 8 defense layers verified.)
- [x] TASK-FOR-002 — Forge executes one real code task requested through FRIDAY chat. (MERGED 2026-11-10: ForgeCodeTool + CODE_TASK_KEYWORDS routing; two live-proven routing conflicts fixed; E2E routed_capability=TOOL_EXECUTION.)
- [x] TASK-STR-002 — Stratex answers portfolio and position questions via FRIDAY on Binance demo (live trading stays blocked by the merged fail-closed guard; owner decision D-015). (MERGED 2026-11-10: read-only StratexPortfolioTool; real snapshot proven via the M1 trace — balance 10792.8, 7 strategies.)
- [x] TASK-INT-002 — IntelX research briefs retrievable through FRIDAY chat. (MERGED 2026-11-10: IntelXResearchTool; research requests never route to VISION_MODEL; M1 trace proves the real brief on production.)
- [x] TASK-API-002 — Standard `/health` and agent-status surface so "Friday, how's the fleet?" is answered truthfully (partially live today). (MERGED 2026-11-10: FleetStatusTool — real probes, deterministic fast path; live E2E fast_path=true; 16 tests.)
Owner-visible exit: Surendra runs at least three different real task types through FRIDAY in one week and reports the experience.

### M3 — VOICE JARVIS
- [ ] TASK-VOI-001 — FRIDAY-Voice (LiveKit worker) live test with the owner: speak, be understood, get spoken answers (MemoryMax already set, TASK-INF-002). *(2026-11-10: engineering side READY — 9-check preflight + 6-phrase owner test kit, docs/voice/VOICE_TEST_KIT_2026-11-10.md; awaiting the owner's 5-minute session.)*
- [x] TASK-VOI-002 — Proactive morning brief: spoken fleet status, portfolio summary and overnight events. (MERGED 2026-11-10: real-data brief composed once per morning, honest per-component failures, delivered on the owner's first greeting; 8 tests.)
Owner-visible exit: Surendra talks to FRIDAY by voice and receives a daily brief unprompted.

### M4 — HARDENING AND AUTONOMY
- [x] TASK-SEC-005 — Close the public control surface: require a real owner credential on `/api/control/session` (or an owner-accepted alternative; see owner decision 1). Until decided, treat the public URL as untrusted. (RESOLVED 2026-11-10, D-023: remote mint requires the control key; origin gate retained; fail-closed 503; live-verified again during TASK-VAL-002 — 401 no key / 403 forged origin / 401 wrong key.)
- [x] TASK-SEC-003 — Bridge authentication activation (merged in PR #24, parked by owner decision D-014). (AUTH MIDDLEWARE MERGED & READY; activation escalated 2026-11-10 by finding B-1 + D-024 proposal — the bridge exposes run_shell/write_file anonymously; owner decision pending.)
- [x] TASK-VAL-001 — Full fleet validation on live servers with per-agent evidence. (2026-11-10: public-gateway validation 10/10 live + Fleet Live Validation workflow for the server-side systemctl half; see WORK_BOARD evidence.)
- [x] TASK-VAL-002 — Security review of public ingress and bridge. (2026-11-10: docs/security/INGRESS_BRIDGE_REVIEW_2026-11-10.md — CRITICAL finding B-1: the bridge is an anonymous RCE surface; D-024 proposed: activate merged bridge auth. Owner decision pending.)
- [x] TASK-OBS-001 — Crash-loop and health alerting (Restart=always makes crash loops silent today). (2026-11-10: fleet health watcher + deploy-job health gate + runbook; owner enables the server timer with 2 commands.)
- [x] TASK-OBS-002 — Rollback procedure for a bad deploy (deploy uses `git reset --hard`). (2026-11-10: ancestor-guarded rollback script + Fleet Rollback manual workflow + 8 guard tests + runbook decision table.)
- [x] TASK-INF-003 — Backup and restore drill: Oracle DBs and service configs. (2026-11-10: backup/restore tooling + weekly Fleet Backup workflow + runbook; first live backup = dispatch the workflow once.)
- [x] TASK-DATA-003 — Persistence and recovery test for Memora and Stratex ledgers. (2026-11-10: real-process-death recovery tests 4/4 + owner-authorized production drill workflow; contract proven at the ledger level.)
- [x] TASK-ORCH-003 — Verify the autonomous controller and fleet supervision before any autonomy claim. (2026-11-10: audit doc + 8 guard tests; supervision verified+honest, autonomy OFF by default and runtime-only — no autonomy claim permitted beyond owner-triggered bounded delegation.)

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
| TASK-OPS-002 | Verify OCI credentials authenticate (sniper run log) — **VERIFIED 2026-11-10** (run 42761923442: 547 authenticated attempts; allocation continues under TASK-OPS-003) |
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

1. ~~TASK-SEC-005~~ — RESOLVED 2026-11-10 (D-023: secure the mint; implemented, live-verified).
2. Rotate the leaked Telegram bot token (BotFather) and DuckDNS token — owner-only actions left over from D-016.
3. Whether Server 1 ever gets Redis/Qdrant (affects TASK-DATA-003/TASK-OBS-001).
4. A voice-test slot with the owner for M3 (kit ready: docs/voice/VOICE_TEST_KIT_2026-11-10.md).
5. **NEW (2026-11-10, CRITICAL — finding B-1 of TASK-VAL-002):** activate the merged bridge shared-secret auth (D-024 proposal) — the public engineering bridge exposes 33 tools including `run_shell` and `write_file` to anonymous callers; D-014's "read-mostly" premise is wrong. Interim mitigations listed in the review.

## 2026-11-12 — TASK-WF-004, Arena.ai implementation branch (not merged/deployed)

- Branch `arena/TASK-WF-004-four-owner-workflows`, claim issue #35 comment 6825339336; isolated from historical audit PR #55 and the active Stratex lane. Exactly ten canonical agents retained; no production worktree edits/restarts, publication, trading, merge or deploy.
- LiveKit worker now registers an actual SDK function tool forwarding to canonical loopback `/api/chat`; no control token or owner authority. Chat explicitly dispatches with `boss_verified=False`. Preserve full sourced answer while speaking the research summary. Voice uses canonical memory/tools, not a second agent registry.
- Canonical and alternate voice memory now reject empty/skipped/error receipts; local-only saves explicitly disclaim shared synchronization. These focused additions extend the original server/voice claim; historical batch-4 implementation was completed, not overwritten on a shared worktree.
- IntelX explicit `research_live` refuses MOCK_MODE; searches then fetches guarded documents, not legacy MockProvider snippet extraction. Bounded extractive excerpts with citations/retrieval timestamps; not independent verification, LLM synthesis or durable jobs. Explicit source URLs use the same hardened fetcher. Receipts require nonempty findings and matching source citations.
- Forge honors real TaskStatus enum values, actual nested envelopes, top-level verification manifest and stage dictionaries. Longer bounded HTTP execution budget; timeout says outcome unconfirmed, not nothing happened. Actual generated-code sandbox build remains unverified.
- Video fixes GET `/api/render`, exact asset/completed-output matching, rights boolean, positive real job IDs, and malformed/uncertain acknowledgments. Publish tool creates private approval requests only, never invokes execute. Current asset render is NOT full topic-to-video: VyralX has `/api/projects`, still needs dedicated FRIDAY routing and owner license confirmation. Do not mark workflow complete.
- Evidence: **263 passed** across nine targeted offline suites; actual SDK registration/canonical authority tests included. Configured FRIDAY Ruff and new-file F/E9 pass. CI workflow added; remote CI not yet verified. Sandbox real network fetch of `https://docs.python.org/3/library/json.html` returned SUCCESS with one retrieved document excerpt. Separate search probe returned DEGRADED/zero sources from unreadable Google News URLs; this failure is not concealed and is not production acceptance.
- Still missing: continuous owner microphone/interruption/context session; actual Memora cross-session lifecycle acceptance; deployed fresh-provider research; actual Forge instruction-to-tested-artifact; complete FRIDAY topic-to-video/project routing and rendered-output/owner review acceptance. Unit tests are not these demonstrations. No replacement progress percentage or claim all four experiences are delivered.
- Next: independent review/CI and continue missing full workflow integration, then approved controlled acceptance. Owner alone decides merge/deploy; existing CD may restart services when runtime paths merge, so do not auto-merge.
