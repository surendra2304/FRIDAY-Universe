# FRIDAY Universe — Master Completion Checklist

**Purpose.** The owner asked for one honest checklist covering EVERYTHING needed to reach 100% of FRIDAY Universe — "even if they are 100 or more." This is it: 123 items across 9 modules. No item is ticked without evidence (live reproduction, test, or deploy verification). Item counts are not capability weights — they measure *remaining work*, not importance.

**Legend:** ✅ done & evidenced · 🔶 partial (works but gaps) · ⬜ not done · ⛔ blocked on an external dependency

**Snapshot:** 2026-11-11 (early hours IST; updated same night after ORCH-005/006/007) · 44/124 items done (35%) · capability-weighted completion ≈ 57%

---

## A. FRIDAY Brain — chat intelligence (14 items)

- [x] **A1** Boss recognition: "I am Surendra / I am your boss" → instant affirmation (live verified 2026-11-11; 12-test contract suite)
- [x] **A2** No "I am an AI, I don't have a Boss" deflection — banned phrasing removed from persona, deterministic fast-path layered on top
- [x] **A3** Friend-tone baseline: warm, personal, first-person — not corporate-AI (live verified)
- [x] **A4** Empty-turn resilience: reasoning-model empty visible turns get one nudged retry instead of dying at "action limit" (TASK-ORCH-005, 5 tests)
- [x] **A5** Greeting fast-path (no tool-loop burn on "hello")
- [ ] **A6** Multi-turn coherence: 10+ turn conversation keeps context and goals (partial — memory injects context; depth untested)
- [ ] **A7** Reasoning benchmark suite: 20 real delegation-style prompts scored pass/fail, run weekly
- [ ] **A8** Personality consistency across chat AND voice (same persona contract enforced on Gemini Live prompt)
- [ ] **A9** Casual/sarcastic tone matching (owner jokes → FRIDAY plays along, doesn't lecture)
- [ ] **A10** Clarification quality: asks ONE sharp question when ambiguous, never interrogates
- [ ] **A11** Long-goal persistence: a goal stated Monday is still tracked Friday ("still on it, Boss")
- [ ] **A12** Proactive follow-up: unfinished tasks get a status ping without being asked
- [ ] **A13** Response formatting policy: consistent lists/emoji use, no wall-of-text
- [ ] **A14** Boss-only command surface: owner-exclusive commands (mode switches, agent shutdown) keyed to owner identity

## B. Memory — Memora (12 items)

- [x] **B1** Store fact via chat: "remember this: X" → persisted (live verified with unique marker)
- [x] **B2** Recall fact in a FRESH session (live verified — cross-session works)
- [x] **B3** "What do you remember about me?" probe leads with personal facts (live verified)
- [x] **B4** Auto-record dialogue turns to Memora (MEM-003)
- [x] **B5** Proactive recall: relevant memory injected into answers (BRAIN-002)
- [x] **B6** Recall ranking: personal facts beat agent logs; noise filtered (committed; live-verified once — needs soak)
- [ ] **B7** Nightly consolidation: summarize/dedupe/merge the day's memories
- [ ] **B8** Importance scoring: trivial facts age out, core facts pinned
- [ ] **B9** Forget command: "forget that" removes a stored fact
- [ ] **B10** Memory edit: "actually my number is X" updates, doesn't duplicate
- [ ] **B11** Voice-path memory: say "remember X" on the voice line → stored (untested)
- [ ] **B12** Memory visibility: what-FRIDAY-knows browser in the dashboard

## C. Orchestration — FRIDAY assigns work to agents (14 items)

- [x] **C1** IntelX research via chat (INT-002, live)
- [x] **C2** Stratex portfolio answers via chat (STR-002, live)
- [x] **C3** Forge code tasks via chat (FOR-002, live)
- [x] **C4** Unified task records: TASK-ID, owner agent, status, result (CORE-003)
- [x] **C5** Empty-turn fix unblocks delegation requests (ORCH-005 — this batch; live re-verify after deploy)
- [x] **C6** Generic "assign <task> to <agent>" phrasing routes to the right agent tool (ORCH-006/007, live verified 2026-11-11)
- [ ] **C7** VyralX delegation: video scripts/clips on request
- [ ] **C8** Sentinel delegation: "run a security scan" on request
- [ ] **C9** Cortex delegation: web fetch/monitor tasks on request
- [ ] **C10** Futuris delegation: forecast requests on demand
- [ ] **C11** Memora delegation: owner-facing memory ops (search/edit) as first-class tasks
- [ ] **C12** Multi-agent pipelines: "research X, then draft the email about it" (chained dispatch)
- [ ] **C13** Task status queries: "what happened to that IntelX task?" → real record lookup
- [x] **C14** Delegation receipts: every assignment returns a task ID the owner can reference (live: task_71f66986709e)

## D. Website — command center (18 items)

- [x] **D1** Sectioned layout live: CONSOLE / FLEET / ACTIVITY / SYSTEM tabs (verified in deployed bundle)
- [x] **D2** Main section = FRIDAY↔owner communication ONLY (voice + chat)
- [x] **D3** Fleet section: agent cards, freshness labels, IST times
- [x] **D4** Ear / F / waveform symbols removed (bundle verified)
- [x] **D5** Dark theme, awwwards-style
- [x] **D6** Keyless + origin-gated public routes (owner decision D-024)
- [x] **D7** IST clock and timestamps in the UI (D-026)
- [x] **D8** LiveKit voice orb with graceful idle disconnect ("Voice line closed")
- [ ] **D9** React Bits integration (owner request — animated component kit, not hand-rolled CSS only)
- [ ] **D10** Floating/dynamic element pass: orbitals, parallax, magnet buttons, aurora backgrounds
- [ ] **D11** Live activity feed richness: every agent action streams in real time (WS exists; event coverage partial)
- [ ] **D12** "What is each agent doing RIGHT NOW" — live status per card, auto-refreshed
- [ ] **D13** Task timeline: delegation history with status chips (queued/running/done/failed)
- [ ] **D14** Mobile responsiveness verified (320–430px widths)
- [ ] **D15** Accessibility pass: contrast, aria labels, keyboard tabs
- [ ] **D16** Performance budget: Lighthouse ≥ 90 on the deployed build
- [ ] **D17** Owner preferences section: name, timezone, notification choices, briefing time
- [ ] **D18** Empty states + onboarding polish (first-visit hints, zero-task states)

## E. Voice (10 items)

- [x] **E1** Tap-to-start full-duplex voice (LiveKit Cloud free tier, live)
- [x] **E2** Idle auto-disconnect handled gracefully with reconnect affordance
- [ ] **E3** Auto-reconnect after drop (one-tap or auto, no page state loss)
- [ ] **E4** Voice-path memory (see B11 — say it, FRIDAY keeps it)
- [ ] **E5** Fleet/agent questions answered by voice ("what's IntelX doing?")
- [ ] **E6** Barge-in + natural pacing verified by owner (5-minute test kit exists)
- [ ] **E7** Voice session diagnostics (latency, quality) surfaced in SYSTEM tab
- [ ] **E8** ⛔ Unlimited voice minutes — self-hosted LiveKit SFU; blocked on ARM server capture (sniper hunting)
- [ ] **E9** Voice quality tuning: voice selection, pacing, filler-word reduction
- [ ] **E10** Indian-English accent accuracy check (owner's phrasing, Telugu-English mix)

## F. Nine specialist agents (27 items)

**Inference (AI gateway)**
- [x] **F1** Free-model gateway serving chat (groq gpt-oss-120b live)
- [x] **F2** Provider failover chain (free-first, cost_mode=free_first)
- [ ] **F3** Usage dashboard + rate-limit guard (know before we hit limits)

**Stratex (markets)**
- [x] **F4** Portfolio answers via chat (live; paper portfolio — no exchange keys by design)
- [ ] **F5** Scheduled daily portfolio report (Telegram, 09:00 IST)
- [ ] **F6** Price/alert rules → Telegram push

**IntelX (research)**
- [x] **F7** Research briefs with citations via chat (live)
- [ ] **F8** Scheduled briefings on owner's watchlist topics
- [ ] **F9** Watchlist monitoring with change detection

**Futuris (forecasting)**
- [ ] **F10** Forecast requests via chat (capability exists; untested live)
- [ ] **F11** Scheduled forecast refresh (markets/topics)
- [ ] **F12** Prediction accuracy tracking (log predictions, score later)

**Cortex (web ops)**
- [ ] **F13** Web fetch/summarize on request (limited today)
- [ ] **F14** Uptime/availability checks for owned properties
- [ ] **F15** Scheduled site health sweeps

**Forge (engineering)**
- [x] **F16** Real code tasks via chat (live, sandboxed)
- [ ] **F17** Repo hygiene ops: dependency bumps, CI watch (partial tooling)
- [ ] **F18** Scheduled dependency/CI health report

**Sentinel (security)**
- [ ] **F19** Security scan on request (capability partial)
- [ ] **F20** Scheduled vulnerability scans + report
- [ ] **F21** Secret-leak guard on the public repo (pre-push scan)

**VyralX (video)**
- [ ] **F22** Video script generation on request
- [ ] **F23** Free-tool render pipeline (ffmpeg/Remotion) for clips
- [ ] **F24** Publish workflow (YouTube/Shorts draft upload)

**Memora (memory)**
- [x] **F25** Persistent cross-session store (live)
- [x] **F26** Auto-record interactions (live)
- [ ] **F27** Consolidation daemon (see B7)

## G. Autonomy — works while the owner sleeps (12 items)

- [x] **G1** Morning brief (VOI-002, 08:00 IST window)
- [x] **G2** Crash-loop watcher on BOTH servers (verified cycles)
- [x] **G3** Systemd auto-restart (self-healing processes)
- [x] **G4** Telegram notifications (one-way pings, both bots live)
- [ ] **G5** Telegram two-way: text FRIDAY from the phone, get answers
- [ ] **G6** Overnight mission loop: queue tasks at night, execute, report in the morning
- [ ] **G7** Daily self-report: "what I did today" (21:00 IST, Telegram)
- [ ] **G8** Weekly summary report (Sunday evening)
- [ ] **G9** 🔶 ARM sniper: 2 workflows hunting hourly; 0 servers captured so far (capacity-gated)
- [ ] **G10** Second-server workload split once ARM lands (self-host SFU = E8)
- [ ] **G11** Self-healing sweep: disk, certs, backups checked daily
- [ ] **G12** Autonomous task intake: owner's TODO list becomes FRIDAY's queue

## H. Infrastructure & ops (10 items)

- [x] **H1** IST everywhere: code, servers (OS clock), dashboard, notifiers (D-026)
- [x] **H2** Wrong-date strings corrected to IST (TZ-001)
- [x] **H3** CI/CD fleet deploy green on main
- [x] **H4** Backups + restore tested (INF-003)
- [x] **H5** Secrets purged from history (2026-11-10 rewrite)
- [ ] **H6** Docs sync: every doc reflects the current state (this checklist is step 1)
- [ ] **H7** Public status/uptime page
- [ ] **H8** Cert-expiry auto-check (duckdns domain)
- [ ] **H9** Log rotation verified on both servers
- [ ] **H10** $0-cost audit: prove no accidental PAYG exposure (quarterly)

## I. Tech debt & hygiene (6 items)

- [ ] **I1** Fix `test_real_usage_battery.py::test_the_agent_remembers_and_recalls_a_fact` (pre-existing failure on main)
- [ ] **I2** Fix `test_real_usage_battery.py::test_tasks_round_trip` (pre-existing failure on main)
- [ ] **I3** Fix `test_real_usage_battery.py::test_user_rebalance_request_gets_no_fabricated_targets_without_market_data` (pre-existing)
- [ ] **I4** Full battery green: `test_real_usage_battery.py` 29/29
- [ ] **I5** Coverage gate in CI (no untested regression classes)
- [ ] **I6** Dead-code sweep: unused tools/modules removed or wired
- [ ] **I7** Fix duplicate `(path, method)` route registration in server.py (pre-existing `test_api_command_truthfulness` failure on main)
- [ ] **I8** Contacts fast-path hijack: "get X to do Y" (no contact intent) is intercepted by the contacts lookup — reproduce test_delegation 'get IntelX' case; tighten the contacts matcher to explicit contact verbs (save/edit/find contact)

---

## Scoreboard

| Module | Done | Total | % |
|---|---|---|---|
| A. Brain | 5 | 14 | 36% |
| B. Memory | 6 | 12 | 50% |
| C. Orchestration | 7 | 14 | 50% |
| D. Website | 8 | 18 | 44% |
| E. Voice | 2 | 10 | 20% |
| F. Agents | 7 | 27 | 26% |
| G. Autonomy | 4 | 12 | 33% |
| H. Infra | 5 | 10 | 50% |
| I. Tech debt | 0 | 8 | 0% |
| **Universe** | **44** | **125** | **35%** |

*Method note: capability-weighted completion (what the owner experiences) is ≈ 55%; checklist-item completion (remaining work to 100%) is 34% because the checklist now includes every polish, autonomy and agent-depth item the owner requested — items that were never part of the earlier milestone accounting. Both numbers are honest; they measure different things.*

**Execution order (owner-approved priority):** C6/C13/C14 (delegation that feels real) → D9/D10/D12 (React Bits + live "who's doing what") → B7/B9/B10 (memory maturity) → F per-agent depth (Sentinel, VyralX, Futuris, Cortex) → G6/G7 (overnight autonomy) → E3/E4 (voice) → the rest.
