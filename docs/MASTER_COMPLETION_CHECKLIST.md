# FRIDAY Universe — Master Completion Checklist

**Purpose.** The owner asked for one honest checklist covering EVERYTHING needed to reach 100% of FRIDAY Universe — "even if they are 100 or more." This is it: 123 items across 9 modules. No item is ticked without evidence (live reproduction, test, or deploy verification). Item counts are not capability weights — they measure *remaining work*, not importance.

**Legend:** ✅ done & evidenced · 🔶 partial (works but gaps) · ⬜ not done · ⛔ blocked on an external dependency

**Snapshot:** 2026-11-12 (IST; batch 4 COMPLETE by ZAI Agent 1: B8/B11/B12, A6/A7/A9/A11/A12/A14 - 76/76 + 235 battery green; batch 5 COMPLETE by ZAI Agent 2: G5/G6/G7/G8/G11/G12 + H8/H9 - 42 new tests, 0 regressions; batch 6 COMPLETE by ZAI Agent 2: F8/F9 watchlist briefings + change detection, F13 SSRF-guarded web fetch/summarize, F14/F15 site sweeps, F17/F18 dependency+CI health, F20 Sentinel digest, F21 pre-push secret guard - 35 new tests, 0 regressions; batch 9 part 1 COMPLETE by ZAI Agent 1: I1-I4 battery rescue, real-usage battery 29/29 green, 3 routing hijacks fixed, 0 regressions vs clean tree)

---

## A. FRIDAY Brain — chat intelligence (14 items)

- [x] **A1** Boss recognition: "I am Surendra / I am your boss" → instant affirmation (live verified 2026-11-11; 12-test contract suite)
- [x] **A2** No "I am an AI, I don't have a Boss" deflection — banned phrasing removed from persona, deterministic fast-path layered on top
- [x] **A3** Friend-tone baseline: warm, personal, first-person — not corporate-AI (live verified)
- [x] **A4** Empty-turn resilience: reasoning-model empty visible turns get one nudged retry instead of dying at "action limit" (TASK-ORCH-005, 5 tests)
- [x] **A5** Greeting fast-path (no tool-loop burn on "hello")
- [x] **A6** Multi-turn coherence: 10+ turn conversation keeps context and goals (DONE 2026-11-11 IST, batch 4: `tests/test_batch4_memory_brain.py::test_a6_twelve_turn_conversation_keeps_context` — a scripted 12-turn conversation through the REAL chat router with a fake store: fact stored at turn 1 and goal stated at turn 3 both survive 9+ intervening turns spanning greetings, banter, identity, consolidation and follow-up surfaces; recall at turn 10+ returns the fact, goal query at turn 12 answers "still on it, Boss" with the exact goal text)
- [x] **A7** Reasoning benchmark suite: 20 real delegation-style prompts scored pass/fail, run weekly (DONE 2026-11-11 IST, batch 4: `friday/evaluation/reasoning_benchmark.py` — 20 owner-style prompts (memory 7, goals 3, boss identity 2, boss-gate 1, tone 2, followup 1, consolidation 1, greeting/clarify/security 3) replayed through the REAL `_dispatch_command` with a deterministic fake store; per-case metadata + reply-content assertions, no case passes on a fabricated reply; JSON report persisted to reports/reasoning_benchmark/latest.json + timestamped run; weekly cadence hook (`should_run_weekly`, Sunday IST); benchmark test asserts 20/20 green)
- [ ] **A8** Personality consistency across chat AND voice (same persona contract enforced on Gemini Live prompt)
- [x] **A9** Casual/sarcastic tone matching (owner jokes → FRIDAY plays along, doesn't lecture) (DONE 2026-11-11 IST, batch 4: `friday/persona/tone.py` — narrow exact-match banter table (fired/useless/lift/sandwich/roast/sentient/sing/bored/praise/lol) with warm first-person comebacks, never lectures, never "as an AI"; wired into the chat ladder AFTER the memory gates and BEFORE the mode toggles so real commands are never hijacked — the non-fire matrix locks that: "can you make me a dashboard" and "you're fired but first tell me the portfolio balance" do NOT match)
- [x] **A10** Clarification quality: asks ONE sharp question when ambiguous, never interrogates (DONE 2026-11-11 IST, batch 3: `routing/clarification.py` — intent matched but operand missing/bare-pronoun → exactly ONE Boss-tone question through `_clarification_response` (state machine + memory + Memora record so the next turn resolves it); wired into the batch3 + research + forecast fast paths; complete requests proceed untouched; every question verified single-question-mark by test)
- [x] **A11** Long-goal persistence: a goal stated Monday is still tracked Friday ("still on it, Boss") (DONE 2026-11-11 IST, batch 4: `friday/proactive/goals.py` — "my goal this week is X" stores a PINNED `GOAL (active):` memory (importance 1.0); any goal-shaped query answers "Still on it, Boss" from the real store; "I finished my goal" retires it through the auditable supersede lifecycle and records a `GOAL (complete):` marker; active goals also join the morning brief (A11 line in `morning_brief.py`); goal gate wired into the chat ladder before recall/remember so goal phrasing is never eaten)
- [x] **A12** Proactive follow-up: unfinished tasks get a status ping without being asked (DONE 2026-11-11 IST, batch 4: `friday/proactive/followup.py` — a sweep every 30 min (server lifespan loop) over the shared task ledger finds submitted/assigned/dispatched tasks with no transition for 45+ min and posts ONE honest ping each through the proactive NotificationManager (the same channel the morning brief and voice line read), rate-limited to one ping per task per 6 h; "what needs my attention?" is the on-demand chat view of the same data; store failures and quiet ledgers are honest empties)
- [x] **A14** Boss-only command surface: owner-exclusive commands (mode switches, agent shutdown) keyed to owner identity (DONE 2026-11-11 IST, batch 4: `friday/security/boss_gate.py` — five boss-only categories (mode switches, agent shutdown, live-trading toggles, whole-memory wipes, fleet deploy/rollback/shutdown) gated at the TOP of the chat ladder; the command console passes boss_verified=True (its control token IS the owner key), every other surface fails CLOSED unless the owner authorizes with "authorize boss <passphrase>" (BOSS_PASSPHRASE env; unset = never passes) or speaker biometrics verify; refusals name the blocked category, confirm nothing executed, and say how to verify; ordinary commands never gated — "forget about the old marker color" (single fact) and "deploy the new dashboard design" (no fleet scope) pass through)
- [x] **A13** Response formatting policy: consistent lists/emoji use, no wall-of-text (DONE 2026-11-11 IST, batch 3: `persona/response_format.py` — deterministic idempotent post-processor on free-form LLM replies in execute_command; walls split into ≤3-sentence paragraphs, run-on inline enumerations reflowed to bullets, code blocks + structured lists untouched; fast-path/tool replies exempt)

## B. Memory — Memora (12 items)

- [x] **B1** Store fact via chat: "remember this: X" → persisted (live verified with unique marker)
- [x] **B2** Recall fact in a FRESH session (live verified — cross-session works)
- [x] **B3** "What do you remember about me?" probe leads with personal facts (live verified)
- [x] **B4** Auto-record dialogue turns to Memora (MEM-003)
- [x] **B5** Proactive recall: relevant memory injected into answers (BRAIN-002)
- [x] **B6** Recall ranking: personal facts beat agent logs; noise filtered (committed; live-verified once — needs soak)
- [x] **B7** Nightly consolidation: summarize/dedupe/merge the day's memories (DONE 2026-11-11 IST: `friday/proactive/nightly_consolidation.py` — real MemoraClient.recent_memories (date-filtered, not keyword-guessed) gathers the day's live records; near-duplicates merged via containment-aware similarity (0.85) through the auditable supersede lifecycle (new public MemoraClient.supersede_fact — same one B10 corrections use); one marked day summary stored, idempotent per night; background loop in the server lifespan (15-min gate check, 02:00–05:00 IST window, once per night, honest per-component failures, never fatal); "consolidate your memories" chat fast-path runs it on demand (wired BEFORE the recall gate so "clean up your memory" is not eaten by the recall patterns); 32-test suite; BONUS: fixed a pre-existing routing regression found by the delegation suite — "assign a task to X… then show me its result" was intercepted by the task-status gate (ORCH-008 chain order); now a shared delegation matcher arbitrates, 99/99 delegation+status tests green)
- [x] **B8** Importance scoring: trivial facts age out, core facts pinned (DONE 2026-11-11 IST, batch 4: `friday/memory/importance.py` — deterministic 0.0–1.0 scoring with three tiers: PINNED ≥0.90 (identity, contact, preferences, relationships, schedule, health, goals + stored GOAL records), NORMAL 0.55 (substantive), TRIVIAL ≤0.30 (questions, marker words, transient states, agent-log noise, <15 chars); the remember path now stores the SCORED importance and tells the owner the tier ("pinned — never fades" / "small stuff fades after a while"); the nightly pass (B7 loop + on-demand "consolidate your memories") ages out trivial facts older than 7 days through the same auditable supersede lifecycle — pinned and normal facts untouched, daily summaries exempt, honest per-component counters; 17-case scoring matrix + aging lifecycle suite green)
- [x] **B9** Forget command: "forget that" removes a stored fact (LIVE 2026-11-11: 'forget about the unique test marker color' → soft-deleted, recall returns nothing; MemoraClient.forget_fact + chat fast-path; 34-test suite)
- [x] **B10** Memory edit: "actually my number is X" updates, doesn't duplicate (LIVE 2026-11-11: teal marker corrected to indigo → recall returns ONLY indigo; old fact superseded in the audit trail, not duplicated; MemoraClient.correct_fact via Memora's supersede API + chat fast-path)
- [x] **B11** Voice-path memory: say "remember X" on the voice line → stored (untested) (DONE 2026-11-11 IST, batch 4: `friday/memory/voice_memory.py` + wiring in `gemini_live_session.py` — BOTH voice paths now intercept memory intents BEFORE the Live model (which has no Memora access): typed CLI input (`process_typed_input`) and completed spoken turns (`_audio_receiver_loop`) route "remember X" through the same scored store path as chat (B8 tier note included), "forget about X" through the honest soft-delete, and both confirm OUT LOUD via native TTS/Live send_text; corrections are deliberately redirected to chat/typed form (voice transcripts drop punctuation — a half-heard correction must never overwrite a stored fact); store outages are SPOKEN honestly, never "saved" when they weren't)
- [x] **B12** Memory visibility: what-FRIDAY-knows browser in the dashboard (DONE 2026-11-11 IST, batch 4: `GET /api/memory/browser` (control-token protected, read-only) — the live Memora store as a browsable list: text, importance tier (B8 scoring), score, category, created_at, active-goal flag + a tier/goal summary block; honest "unreachable" status on store outage, never a fabricated list; edits stay chat commands (forget/correct) with their audit trails)

## C. Orchestration — FRIDAY assigns work to agents (14 items)

- [x] **C1** IntelX research via chat (INT-002, live)
- [x] **C2** Stratex portfolio answers via chat (STR-002, live)
- [x] **C3** Forge code tasks via chat (FOR-002, live)
- [x] **C4** Unified task records: TASK-ID, owner agent, status, result (CORE-003)
- [x] **C5** Empty-turn fix unblocks delegation requests (ORCH-005 — this batch; live re-verify after deploy)
- [x] **C6** Generic "assign <task> to <agent>" phrasing routes to the right agent tool (ORCH-006/007, live verified 2026-11-11)
- [x] **C7** VyralX delegation: video scripts/clips on request (DONE 2026-11-11 IST, batch 3: `vyralx_script` tool → FleetClient.request_vyralx_script → VyralX's REAL Hyperframes engine, draft-only — nothing rendered or published by the chat path; SCRIPT_KEYWORDS routing before the fleet probe)
- [x] **C8** Sentinel delegation: "run a security scan" on request (DONE 2026-11-11 IST with F19: "run a security check" / "any vulnerabilities" answer from Sentinel's REAL posture + finding engines via sentinel_security (read-only); active assessments stay behind Sentinel's owner-authorized scope gate — stated in every answer; security fast-path runs BEFORE the fleet-status probe so "check the fleet's security posture" is a security lookup, not a fleet ping; delegation-shaped asks ("tell Sentinel to run a security scan") still route to delegation; 33-test suite)
- [x] **C9** Cortex delegation: web fetch/monitor tasks on request (DONE 2026-11-11 IST, batch 3: `cortex_web_ops` tool → FleetClient.request_cortex_web_ops → Cortex's REAL health summary + governed properties roster, read-only, no outreach; WEB_OPS_KEYWORDS routing before the fleet probe)
- [x] **C10** Futuris delegation: forecast requests on demand (DONE 2026-11-11 IST with F10: "forecast X over 24h" / "what does Futuris predict for Y" reach Futuris's real FRIDAY delegation contract (POST /v1/friday/forecast) via futuris_forecast; forecast fast-path runs BEFORE the fleet-status probe so "predict the fleet load" is a forecast, not a fleet ping; delegation-shaped asks still route to delegation; 32-test suite)
- [x] **C11** Memora delegation: owner-facing memory ops (search/edit) as first-class tasks (DONE 2026-11-11 IST, batch 3: `memora_memory` tool → FleetClient.request_memora_memory_op → Memora's REAL context DB, honest empties; MEMORA_OP_KEYWORDS routing; this-form keywords "save this to fleet memory" added in the batch-3 completion pass after the routing gap was found)
- [x] **C12** Multi-agent pipelines: "research X, then draft the email about it" (chained dispatch) (DONE 2026-11-11 IST, batch 3: `ecosystem/pipeline.py` — connector-based chain detection mapping every fragment to a stage kind via the router's own keyword sets; `_pipeline_fast_path` runs BEFORE every single-intent fast path so a chain is never eaten by its first stage's dispatcher; sequential real dispatches (IntelX/VyralX/Memora-write/Futuris/Cortex) where stage N consumes stage N-1's real output; per-stage honest failures; combined report; per-stage live activity events)
- [x] **C13** Task status queries: "what happened to that IntelX task?" → real record lookup (TASK-ORCH-008 + gap fix, LIVE-VERIFIED 2026-11-11 end-to-end: chat dispatch → receipt task_036e6b93ecaa → 'what happened to the stratex task?' returned the REAL failed record with the actual 401 error, routing rationale, IST timestamps and full trail; the gap fix records chat delegations into the shared ledger because FleetClient bypasses the in-process bus; 84-test suite)
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
- [x] **D9** React Bits integration (owner request — animated component kit, not hand-rolled CSS only) (LIVE 2026-11-11: full React-Bits component inventory in effects.tsx — ScrambleText, Aurora(AuroraBackground), Magnetic, Spotlight(SpotlightCard), CountUp, Reveal + new pointer-driven Parallax and Orbital, all React components with compositor-safe animation, reduced-motion + touch-pointer safe; deployed in the 0055eef build)
- [x] **D10** Floating/dynamic element pass: orbitals, parallax, magnet buttons, aurora backgrounds (LIVE 2026-11-11: Orbital = 9 satellite dots orbiting the voice core (one per fleet agent); Parallax = pointer-depth layers on console rail (6px) + chat (2px); Magnetic wired onto nav tabs + fleet card buttons; AuroraBackground + FloatingOrbs already live — deployed bundle serves orbitalSpin/orbital-dot CSS + the new effects chunk)
- [x] **D11** Live activity feed richness: every agent action streams in real time (WS exists; event coverage partial) (DONE 2026-11-11 IST, batch 3: coverage widened — `chat_command` events from execute_command (every owner command streams), `agent_action` events from the batch3 delegation dispatch, per-stage events from multi-agent pipelines; dashboard WS handler accepts activity + agent_action + chat_command frames)
- [x] **D12** "What is each agent doing RIGHT NOW" — live status per card, auto-refreshed (TASK-UI-004: GET /api/agents/live merges reachability + the unified task ledger — in_flight/last_outcome per agent; dashboard polls it in the 30s refresh and renders 'Working now' + 'working <freshness>'; 9/9 endpoint tests; ALSO fixed the blocking defect — the Python-template `lib/` gitignore rule had silently hidden FRIDAY/ui/lib, so lib/api.ts was never committed and a fresh clone could not rebuild the dashboard)
- [x] **D13** Task timeline: delegation history with status chips (queued/running/done/failed) (DONE 2026-11-11 IST, batch 3: GET /api/tasks/timeline — newest-first unified-ledger history with honest chip mapping + empty ledgers returned empty, never fabricated; registered BEFORE /api/tasks/{task_id} so the parameterized status route can't swallow it; dashboard TaskTimeline panel in the ACTIVITY tab with chip styling, fetched in the 30s refresh; BONUS routing fix found on the way: "save THIS to fleet memory" never matched MEMORA_OP_KEYWORDS — the this-form keywords were added)
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
- [x] **F8** Scheduled briefings on owner's watchlist topics (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: `proactive/agent_watch.py` — chat intake "watch topic X"/"keep an eye on X" (casing preserved); daily 17:30–20:00 IST brief per topic (≤6) through IntelX's real dispatch, delivered on the owner Telegram channel; empty watchlist sends nothing — no noise)
- [x] **F9** Watchlist monitoring with change detection (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: each topic stores its last brief's SHA-256 + headline lines; identical brief → "no change since yesterday", changed brief → only NEW lines, first brief labeled as such — locked by tests)

**Futuris (forecasting)**
- [x] **F10** Forecast requests via chat (capability exists; untested live) (DONE 2026-11-11 IST: FuturisForecastTool + FleetClient.request_futuris_forecast — real POST /v1/friday/forecast (target + horizon 1h/24h/7d/30d + quoted-target/horizon extraction); Futuris's honest statuses (BLOCKED/INSUFFICIENT_DATA) reported as-is; every answer states prediction-never-authorization; FORECAST_KEYWORDS routing → TOOL_EXECUTION futuris_forecast, never VISION_MODEL/never DIRECT_REASONING; registered in the default registry; live E2E lands with the next deploy; 32-test suite + 347 related-suite passes)
- [ ] **F11** Scheduled forecast refresh (markets/topics)
- [ ] **F12** Prediction accuracy tracking (log predictions, score later)

**Cortex (web ops)**
- [x] **F13** Web fetch/summarize on request (limited today) (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: `web_fetch_summarize` tool — SSRF guard the old fetch tools lacked (loopback/link-local/private/metadata/non-http/odd-port refused BEFORE connect + post-redirect re-check), cleaned page summarized through the same SynthesizeInformationTool; FETCH_SUMMARIZE_KEYWORDS routing → TOOL_EXECUTION, never DIRECT_REASONING)
- [x] **F14** Uptime/availability checks for owned properties (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: daily site sweep probes all 10 gateway routes (status + latency, honest per-site results) + Cortex governed-properties through the same read-only path as the chat tool)
- [x] **F15** Scheduled site health sweeps (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: 08:00–12:00 IST window, once per day; healthy fleet → ONE compact line, degraded → per-site alert lines; failed delivery unlatches and retries next tick)

**Forge (engineering)**
- [x] **F16** Real code tasks via chat (live, sandboxed)
- [x] **F17** Repo hygiene ops: dependency bumps, CI watch (partial tooling) (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: `.github/dependabot.yml` — weekly Monday cadence for github-actions (root + FRIDAY) and pip (FRIDAY), grouped minor/patch, security-first)
- [x] **F18** Scheduled dependency/CI health report (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: `.github/workflows/agent-health-digest.yml` — weekly Monday 10:00 IST: pip-audit (FRIDAY + Memora) + last-7-days workflow failures; 30-day artifact; read-only, fixes stay in the owning lane)

**Sentinel (security)**
- [x] **F19** Security scan on request (capability partial) (DONE 2026-11-11 IST: SentinelSecurityTool — posture (overall + per-domain scores, severity counts, audit-chain verdict, via FleetClient.ask_sentinel) + findings (open finding ledger, severity filter, via NEW FleetClient.ask_sentinel_findings, honest empties/failures); SECURITY_SCAN_KEYWORDS routing → TOOL_EXECUTION sentinel_security, never VISION_MODEL/never DIRECT_REASONING; registered in the default registry; read-only by construction — active assessments stay behind Sentinel's fail-closed owner-authorized scope (the live C6 400 rejection remains the correct behavior for unscoped assessments); 33-test suite + 191 related-suite passes)
- [x] **F20** Scheduled vulnerability scans + report (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: weekly Monday 09:30–14:00 IST Sentinel digest via FleetClient.ask_sentinel + ask_sentinel_findings (read-only, real scores/severities) on the owner Telegram channel; unreachable Sentinel reported honestly, never "all clear")
- [x] **F21** Secret-leak guard on the public repo (pre-push scan) (DONE 2026-11-11 IST, batch 6 / ZAI Agent 2: `scripts/guard_secrets_pre_push.py` + `.githooks/pre-push` — scans ADDED lines of pushed commits for the token shapes this fleet uses (Telegram bot, GitHub PAT, Oracle DSN, AWS key, private-key block, Binance key); allowlist for .example shapes; 7-case self-test green; local seatbelt next to CI Gitleaks)

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
- [x] **G5** Telegram two-way: text FRIDAY from the phone, get answers (DONE 2026-11-11 IST, batch 5 / ZAI Agent 2: `proactive/telegram_gateway.py` — owner-gated (sender id = TELEGRAM_CHAT_ID, non-owners refused in one line, never reach the brain), polls the FRIDAY Universe bot, routes every message through the SAME execute_command brain as the dashboard (bridge onto the server's main event loop — no second loop, no mini-brain); /status and /missions deterministic; honest brain failures; rate-limited sending with 4000-char splitting; unconfigured → stays silent; runs as a lifespan task in server.py)
- [x] **G6** Overnight mission loop: queue tasks at night, execute, report in the morning (DONE 2026-11-11 IST, batch 5 / ZAI Agent 2: `proactive/mission_queue.py` — file-backed queue (atomic tmp+replace writes, survives restarts), night execution window 03:00–05:00 IST via a lifespan gate loop, bounded retries (2 attempts), refused missions are skipped not retried, budget-capped per night; morning report via render_morning_report into the daily report; E2E-verified through /api/chat)
- [x] **G7** Daily self-report: "what I did today" (21:00 IST, Telegram) (DONE 2026-11-11 IST, batch 5 / ZAI Agent 2: `proactive/daily_self_report.py` — composed ONLY from real records: conversation history, TaskRecordStore dispatch report, fleet supervision snapshot, mission outcomes, Memora growth; zero records reported as zero; component failures reported as honest "could not read" lines; once-per-day latch; send failure retries next cycle without latching)
- [x] **G8** Weekly summary report (Sunday evening) (DONE 2026-11-11 IST, batch 5 / ZAI Agent 2: same module — Sunday 20:00 IST weekly roll-up with per-status ledger totals and fleet posture, before the 21:00 daily)
- [ ] **G9** 🔶 ARM sniper: 2 workflows hunting hourly; 0 servers captured so far (capacity-gated) — partial, capacity-gated
- [ ] **G10** Second-server workload split once ARM lands (self-host SFU = E8) (⛔ blocked on G9 capacity)
- [x] **G11** Self-healing sweep: disk, certs, backups checked daily (DONE 2026-11-11 IST, batch 5 / ZAI Agent 2: `scripts/friday_self_heal_sweep.py` + `deploy/friday-self-heal.{service,timer}` — daily 07:30 IST systemd timer per server; checks disk %, TLS expiry (LIVE-VERIFIED: cert expires 2027-01-12, 61 days), journald usage vs cap, failed units, backup manifest freshness, + public gateway 10/10 on Server 1; Telegram alert only on threshold crossings; honest "check failed" lines, never guessed values)
- [x] **G12** Autonomous task intake: owner's TODO list becomes FRIDAY's queue (DONE 2026-11-11 IST, batch 5 / ZAI Agent 2: chat intake "add to tonight's missions: X" / "queue for tonight: X" / "add to my todo: X" queues real work with casing preserved (same rule as the memory paths); "my missions" lists; "run my missions now" executes on demand through the real brain; run-intent takes precedence over list-intent (E2E lesson locked by test); never hijacks remember/recall/delegation/fleet-status/research (route-level suite green))

## H. Infrastructure & ops (10 items)

- [x] **H1** IST everywhere: code, servers (OS clock), dashboard, notifiers (D-026)
- [x] **H2** Wrong-date strings corrected to IST (TZ-001)
- [x] **H3** CI/CD fleet deploy green on main
- [x] **H4** Backups + restore tested (INF-003)
- [x] **H5** Secrets purged from history (2026-11-10 rewrite)
- [ ] **H6** Docs sync: every doc reflects the current state (this checklist is step 1)
- [ ] **H7** Public status/uptime page
- [x] **H8** Cert-expiry auto-check (duckdns domain) (DONE 2026-11-11 IST, batch 5 / ZAI Agent 2: daily sweep check — openssl s_client + x509 enddate with GMT-aware parsing; LIVE-VERIFIED first run: cert expires 2027-01-12 (61 days), alert threshold 21 days; runs in the 07:30 IST self-heal timer)
- [x] **H9** Log rotation verified on both servers (VERIFIED 2026-11-11 IST, batch 5 / ZAI Agent 2: read-only inspection — BOTH servers have /etc/systemd/journald.conf.d/size-limit.conf with SystemMaxUse=200M + SystemMaxFileSize=20M; usage at check: S1 212M, S2 180M (within cap); the daily sweep now re-checks usage vs cap and alerts at 400M)
- [ ] **H10** $0-cost audit: prove no accidental PAYG exposure (quarterly)

## I. Tech debt & hygiene (6 items)

- [x] **I1** Fix `test_real_usage_battery.py::test_the_agent_remembers_and_recalls_a_fact` (pre-existing failure on main) (FIXED 2026-11-12, batch 9: hermetic test-only sqlite memory in the battery `_agent()` — shared per-test file so agent 2 recalls agent 1's fact through the real search_memory FTS path; PLUS contacts `who is <name>` hijack fixed — possessive/relational questions like "who is my sister" now reach the reasoning path, bare names still look up contacts)
- [x] **I2** Fix `test_real_usage_battery.py::test_tasks_round_trip` (pre-existing failure on main) (FIXED 2026-11-12, batch 9: ManageTasksTool re-registered with the test-only SQLiteTaskStore per test; the task created by agent 1 is listed by agent 2 through the real tool path — battery 29/29)
- [x] **I3** Fix `test_real_usage_battery.py::test_user_rebalance_request_gets_no_fabricated_targets_without_market_data` (pre-existing) (FIXED 2026-11-12, batch 9: `_portfolio_fast_path` no longer hijacks advice phrasing — "Should I rebalance my portfolio?" reaches VoiceTradingSkill, which answers honestly "can't recommend rebalancing — no supported market regime has been measured"; snapshot questions like "how is my portfolio" still get the Stratex snapshot)
- [x] **I4** Full battery green: `test_real_usage_battery.py` 29/29 (DONE 2026-11-12, batch 9: 29/29 passed — also removed the batch-3 regression where "website status" (singular, the Nexus skill's domain) was swallowed by Cortex WEB_OPS_KEYWORDS; Cortex keeps every locked plural/fleet phrase; related-suite failure diff vs clean tree IDENTICAL — 0 regressions)
- [ ] **I5** Coverage gate in CI (no untested regression classes)
- [ ] **I6** Dead-code sweep: unused tools/modules removed or wired
- [x] **I7** Fix duplicate `(path, method)` route registration in server.py (pre-existing `test_api_command_truthfulness` failure on main) (FIXED with the D12 tranche: unauthenticated shadow POST /api/autonomous/decompose deleted, live handler keeps the control gate + returns the real plan_id; shadowed GET /api/v1/mesh/health duplicate removed; BONUS: POST /api/autonomous/execute gained the control gate its siblings already had; route-truthfulness suite 57/57)
- [x] **I8** Contacts fast-path hijack: "get X to do Y" (no contact intent) is intercepted by the contacts lookup — reproduce test_delegation 'get IntelX' case; tighten the contacts matcher to explicit contact verbs (save/edit/find contact) (FIXED with C13 tranche: matcher now requires the word "contact" or a possessive contact field; statement form requires a real phone/email value; 40-case hijack/keep matrix, 13-failure attack replay on old matcher)

---

## Scoreboard

| Module | Done | Total | % |
|---|---|---|---|
| A. Brain | 13 | 14 | 93% |
| B. Memory | 12 | 12 | 100% |
| C. Orchestration | 14 | 14 | 100% |
| D. Website | 13 | 18 | 72% |
| E. Voice | 2 | 10 | 20% |
| A. Brain | 13 | 14 | 92% |
| B. Memory | 12 | 12 | 100% |
| C. Orchestration | 14 | 14 | 100% |
| D. Website | 13 | 18 | 72% |
| E. Voice | 2 | 10 | 20% |
| F. Agents | 18 | 27 | 66% |
| G. Autonomy | 10 | 12 | 83% |
| H. Infra | 7 | 10 | 70% |
| I. Tech debt | 6 | 8 | 75% |
| **Universe** | **95** | **125** | **76%** |

*Method note: capability-weighted completion (what the owner experiences) is ≈ 55%; checklist-item completion (remaining work to 100%) is 34% because the checklist now includes every polish, autonomy and agent-depth item the owner requested — items that were never part of the earlier milestone accounting. Both numbers are honest; they measure different things.*

**Execution order (owner-approved priority):** C6/C13/C14 (delegation that feels real) → D9/D10/D12 (React Bits + live "who's doing what") → B7/B9/B10 (memory maturity) → F per-agent depth (Sentinel, VyralX, Futuris, Cortex) → G6/G7 (overnight autonomy) → E3/E4 (voice) → the rest.
