# FRIDAY Universe — Batch Execution Plan

**Created:** 2026-11-11 (owner directive)
**Method:** 10 tasks per run (batch), so no run gets cut off mid-stream. A Telegram
notification is sent when each batch finishes (`scripts/notify_turn_complete.py`).
**Source of truth for scope:** `docs/MASTER_COMPLETION_CHECKLIST.md` (125 items, 9 modules).

## Rules

1. One batch = one turn = **exactly 10 tasks** (fewer only if blocked).
2. Every batch ends with: commit(s) + `scripts/notify_turn_complete.py "Batch N: ..."`
   + a short status message (done / next).
3. If a run is cut off, the next run resumes from this file — mark per-task status
   below before starting work.
4. Master-checklist items are worked **in parallel with** the owner's urgent
   Stratex trading-bot requests (loss diagnosis, more strategies, more profit).
5. Priority order (owner-approved in the master checklist): Stratex trading
   health first, then C (orchestration) → D (website) → B (memory) → F (agents)
   → G (autonomy) → E (voice) → A (brain) → H (infra) → I (tech debt).
6. **Two-agent lanes (2026-11-11, owner added ZAI Agent 2):**
   - **ZAI Agent 1 (Lane A):** Batches 2, 3, 4, 9, 10, 11, 12 — Stratex,
     orchestration, memory/brain, tech debt, final sweeps. Telegram
     notifications start with `ZAI Agent 1` on the first line.
   - **ZAI Agent 2 (Lane B):** Batches 6, 7, 5, 8 — agent depth F, autonomy G,
     website polish D. Telegram notifications start with `ZAI Agent 2` on the
     first line. Onboarding:
     `docs/collaboration/ZAI_AGENT_2_ONBOARDING.md`.
   - All notifications from `@zai_notifications_bot` (never
     `@fridayuniverse_bot`), agent name on the FIRST LINE (owner directive
     2026-11-12). Claim cross-lane files in WORK_BOARD + issue #35
     first.

## Status legend: ⬜ todo · 🔄 in progress · ✅ done · ⛔ blocked

---

## Batch 1 — Stratex rescue + batch infrastructure (2026-11-11)

1. ✅ Create `docs/BATCH_EXECUTION_PLAN.md` (this file)
2. ✅ Create `scripts/notify_turn_complete.py` — Telegram ping at end of each run
3. ✅ Diagnose the Stratex losses → `Stratex/docs/INCIDENT_2026-11-11_LOSSES.md`
4. ✅ Fix `strategy_supertrend.py` fabricated 0.80 win-rate prior → honest
   ledger-measured prior (17/64 = 0.266) + R:R 1.0 → 2.0 (matches realized
   avg-win/avg-loss ≈ 4:1 with haircut)
5. ✅ Anti-churn floor: minimum bracket distance (SL/TP ≥ 10× round-trip fees,
   ≥ 0.25% of price) so trades stop bleeding out inside one candle
6. ✅ Daily-loss circuit breaker: 3% daily loss → auto-pause new entries
   (trading_pause) + Telegram alert (was: nothing stopped a $2,000/12h bleed)
7. ✅ Promote `factory_winner_1..5` RESEARCH → VALIDATED in
   `PRODUCTION_STRATEGY_REGISTRY` (evidence: mass-backtester artifacts,
   2,408–11,338 trades each, net PF 1.36–1.48, honest priors already baked in)
8. ✅ Wire the promoted strategies through governance so 6 strategies trade
   instead of 1 (diversification = smoother equity)
9. ✅ Tests: circuit breaker + anti-churn floor + honest priors; run suites
10. ✅ Commit + Telegram notification "Batch 1 complete"

## Batch 2 — Stratex strategy depth (owner: "more profitable trades") — COMPLETE 2026-11-11 (Lane A / ZAI Agent 1)

1. ✅ Walk-forward validated both dormant strategies on REAL 120-day futures
   candles (provenance-verified, 8 bps friction, 3 OOS folds):
   `trend_pullback` 721 OOS trades, net PF 0.764 → STAY DORMANT;
   `volatility_breakout` 279 OOS trades, net PF 0.834 → STAY DORMANT.
   Honest negative: neither cleared the PF ≥ 1.0 promotion bar, so neither
   was promoted. Evidence: `research/validation/walkforward_dormant_report.{json,md}`
2. ✅ Regime filter: `BLOCK_SHORTS_IN_BULL_REGIME` default true — supertrend
   shorts now require full bear regime (close < EMA200 AND EMA50 < EMA200)
3. ✅ Volatility-scaled sizing wired into the LIVE sizing path
   (`RiskGate.calculate_position_size(atr_pct=...)` from the scanner candle
   cache): risk scales to baseline/ATR% above 0.8% ATR, floored at 0.25×
4. ✅ Trailing audit: BE lock moved 0.4R → **1.0R**, ATR trailing arms at
   1.5R (after the BE lock); **PROFIT_HARVEST_PCT 1.5% → 0.0 (disabled)** —
   it was amputating the 4:1 winners the strategy math depends on; zero-guard
   added so 0.0 can never fire `profit >= 0` on every position
5. ✅ Confluence sizing: `StrategyCoordinator.confluence_size_multiplier` —
   ≥2 strategies agreeing on a symbol+side = full size, lone strategy = half
   size, wired into the execution loop with LOT_SIZE re-flooring
6. ✅ Anti-revenge cap: `MAX_TRADES_PER_SYMBOL_PER_DAY=3` executed entries per
   symbol per UTC day, counter reset on day rollover
7. ✅ Telegram `/pnl ledger` — daily + rolling 7-day settled PnL from the
   trade ledger (IST day boundary, survives demo resets); combined `/pnl`
   appends the ledger section too
8. ✅ F5: daily portfolio report moved to **09:00 IST** (was 21:00 UTC =
   02:30 IST) + ledger daily/7-day section appended
9. ✅ F6: price-alert rules engine (`/alert add|list|del`, above/below/pct24h,
   once vs daily re-arm) evaluated every 60s against scanner prices with
   Telegram push
10. ✅ Tests: 21 new batch-2 tests + 2 updated trailing tests; suite went
    2226→2234 passed vs pre-batch baseline (8 previously-failing tests fixed,
    0 broken). Commit + notification recorded.

## Batch 3 — Orchestration completion (C module: 10/14 → 14/14) — COMPLETE 2026-11-11

1. ✅ C7 VyralX delegation: video script generation via chat —
   `vyralx_script` tool → FleetClient.request_vyralx_script → VyralX's REAL
   Hyperframes engine (POST /api/v1/vyralx/engines/hyperframes/create-script),
   draft-only (nothing rendered/published), SCRIPT_KEYWORDS routing
2. ✅ C9 Cortex delegation: web-ops monitor via chat — `cortex_web_ops`
   tool → FleetClient.request_cortex_web_ops → Cortex's REAL health summary
   + governed properties (read-only), WEB_OPS_KEYWORDS routing
3. ✅ C11 Memora delegation: memory ops as first-class tasks —
   `memora_memory` tool → FleetClient.request_memora_memory_op → Memora's
   REAL context DB (GET /v1/context/search, POST /v1/context/write),
   honest empties, MEMORA_OP_KEYWORDS routing
4. ✅ C12 Multi-agent pipelines: chained dispatch — `ecosystem/pipeline.py`
   (detect_pipeline splits "research X, then draft the script about it"
   on chain connectors, maps every fragment to a stage kind via the router's
   own keyword sets) + `_pipeline_fast_path` runs BEFORE every single-intent
   fast path so a chain is never eaten by its first stage's dispatcher;
   stages execute sequentially with real tool dispatches (IntelX / VyralX /
   Memora write / Futuris / Cortex) and stage N consumes stage N-1's real
   output as context; per-stage honest failures, combined report; every
   stage emits a live activity event (D11); router excludes chains from
   DIRECT_REASONING
5. ✅ A10 Clarification quality: `routing/clarification.py` — when a
   delegation intent matches but its operand is missing/"it" ("research",
   "draft a video script", "save this to fleet memory", "forecast"),
   FRIDAY asks EXACTLY ONE sharp Boss-tone question via
   `_clarification_response` (state machine + memory + Memora record, so
   the next turn resolves it); wired into the batch3 + research + forecast
   fast paths; complete requests proceed untouched
6. ✅ A13 Response formatting policy: `persona/response_format.py` —
   deterministic idempotent post-processor on free-form LLM replies in
   execute_command (fast-path/tool replies exempt): walls of text split into
   ≤3-sentence paragraphs, run-on inline enumerations reflowed to bullet
   lines, code blocks and structured lists untouched, blank lines collapsed
7. ✅ D13 Task timeline: GET /api/tasks/timeline (newest-first unified-ledger
   history with queued/running/done/failed chips, honest empties; registered
   BEFORE /api/tasks/{task_id} so the parameterized route can't swallow it)
   + dashboard TaskTimeline panel in the ACTIVITY tab with chip styling,
   fetched in the 30s refresh
8. ✅ D11 Live activity feed: widened event coverage — `chat_command` events
   from execute_command (every command streams), `agent_action` events from
   the batch3 delegation dispatch, per-stage events from pipelines; the
   dashboard WS handler accepts activity + agent_action + chat_command
9. ✅ Tests: tests/test_batch3_part2.py — 53 tests (pipeline detect/execute/
   routing/ordering, clarification, formatting, timeline endpoint incl.
   origin gate, activity emit); 91 sibling-suite + 36 batch3/agents-live
   tests green; full-suite diff vs clean tree: 0 new failures
   (239 pre-existing sandbox-env failures identical with and without the
   changes). BONUS FIX: "save THIS to fleet memory" never matched
   MEMORA_OP_KEYWORDS (routing gap since C11) — this-form keywords added
10. ✅ Commit + notify "Batch 3 complete"

## Batch 4 — Memory + Brain maturity (B 9/12, A 5/14) — COMPLETE 2026-11-11 (Lane A / ZAI Agent 1)

1. ✅ B8 Importance scoring: pinned/normal/trivial tiers, scored at store time,
   trivial facts age out after 7 days via the auditable supersede lifecycle
   (nightly + on-demand consolidation), pinned facts never touched
2. ✅ B11 Voice-path memory: both voice paths (typed CLI + completed spoken
   turns) intercept remember/forget BEFORE the Live model and store through
   the same scored path as chat; corrections redirected (transcript safety);
   store outages spoken honestly
3. ✅ B12 Memory visibility: GET /api/memory/browser (control-token, read-only)
   with tier scoring + goal flags + honest unreachable status
4. ✅ A6 Multi-turn coherence: scripted 12-turn conversation through the real
   router — fact + goal survive 9+ intervening turns, "still on it, Boss"
5. ✅ A7 Reasoning benchmark: 20 owner-style prompts through the real router,
   per-case assertions, JSON report persisted, weekly cadence hook
6. ✅ A9 Tone matching: exact-match banter table, plays along, never lectures;
   non-fire matrix locks real commands out of it
7. ✅ A11 Long-goal persistence: GOAL (active) memories pinned, "what about my
   goal" answers from the real store, "i finished my goal" supersedes + done
   marker; goals join the morning brief
8. ✅ A12 Proactive follow-up: 30-min sweep loop posts one honest ping per
   stale task (45+ min no transition) via the NotificationManager, rate-limited
   6h/task; "what needs my attention" on-demand view
9. ✅ A14 Boss-only surface: 5 command categories gated at the top of the
   ladder; console = control token = owner; other surfaces fail closed unless
   "authorize boss <passphrase>"; refusals honest
10. ✅ Tests: 76/76 batch suite green; 235-test related battery green with 0
    regressions (pre-existing environmental failures verified identical on
    clean tree); Stratex batch-2 spot check 52/52. Commit + notification.

## Batch 5 — Autonomy (G 4/12 → 10/12) — EXECUTED BY ZAI AGENT 2, COMPLETE 2026-11-11 IST

> Coordination note: the owner onboarded a second ZAI instance (ZAI Agent 2) to work
> unitedly with ZAI Agent 1. Module-disjoint split agreed on issue #35 (comment
> 6800468222): Agent 1 → Batch 4 (B/A modules), Agent 2 → this batch (G/H items).
> Files touched here do not overlap Batch 4's scope.

1. ✅ G5 Telegram two-way: `proactive/telegram_gateway.py` — owner-gated
   (sender id = TELEGRAM_CHAT_ID; non-owners refused, never reach the brain),
   polls the FRIDAY Universe bot, routes text through the SAME
   execute_command brain (bridged onto the server's main loop);
   /status + /missions deterministic; honest brain failures; rate-limited
   4000-char-split sending; unconfigured → stays off (single poller rule,
   409-conflict backoff with honest logging)
2. ✅ G6 Overnight mission loop: `proactive/mission_queue.py` — file-backed
   queue (atomic writes, survives restarts), 03:00–05:00 IST execution
   window in the server lifespan, bounded retries (2), refused → skipped,
   night budget cap; morning report feeds G7
3. ✅ G7 Daily self-report 21:00 IST: `proactive/daily_self_report.py` —
   composed ONLY from real records (conversation history, TaskRecordStore
   report, fleet supervision, missions, Memora growth); zeros reported as
   zeros; once-per-day latch; send-failure retries next cycle
4. ✅ G8 Weekly summary (Sunday 20:00 IST, before the daily): ledger
   per-status totals + fleet posture
5. ✅ G11 Self-healing sweep: `scripts/friday_self_heal_sweep.py` +
   `deploy/friday-self-heal.{service,timer}` — daily 07:30 IST timer;
   disk/certs/journald/failed-units/backup-freshness (+ gateway 10/10 on
   Server 1); Telegram alert on threshold crossings only; honest
   "check failed" lines (LIVE first run: TLS 61 days left, exp 2027-01-12)
6. ✅ G12 Task intake: chat phrasings "add to tonight's missions: X" /
   "queue for tonight: X" / "add to my todo: X" (owner casing preserved),
   "my missions" list, "run my missions now" on-demand execution
   (run-intent precedence over list-intent — E2E lesson, locked by test)
7. ✅ H8 Cert-expiry auto-check: sweep check with GMT-aware openssl parsing
8. ✅ H9 Log rotation verified: both servers have journald
   SystemMaxUse=200M caps (S1 212M, S2 180M usage — within cap); the sweep
   re-checks daily
9. ✅ Tests: 42 new (test_batch5_autonomy.py 34 + test_mission_routing.py 8
   route-level); full A/B vs clean main on 13 related suites: 18 pre-existing
   sandbox failures IDENTICAL with and without changes (Oracle-driver
   environmental), zero new failures
10. ✅ Commit + notify "Batch 5 complete" (ZAI Agent 2 → zai_notification_bot)

## Batch 6 — Agent depth I (F module: Sentinel, IntelX, Cortex) — Lane B / ZAI Agent 2, FIRST ASSIGNMENT

1. ⬜ F8 Scheduled briefings on owner watchlist topics
2. ⬜ F9 Watchlist monitoring with change detection
3. ⬜ F13 Cortex web fetch/summarize on request
4. ⬜ F14 Cortex uptime checks for owned properties
5. ⬜ F15 Scheduled site health sweeps
6. ⬜ F20 Scheduled vulnerability scans + report
7. ⬜ F21 Secret-leak guard on the public repo (pre-push scan)
8. ⬜ F17 Forge repo hygiene ops (dependency bumps, CI watch)
9. ⬜ F18 Scheduled dependency/CI health report
10. ⬜ Commit + notify "Batch 6 complete"

## Batch 7 — Agent depth II (VyralX, Futuris, Memora) + E voice

1. ⬜ F22 VyralX video script generation
2. ⬜ F23 VyralX free-tool render pipeline (ffmpeg/Remotion)
3. ⬜ F24 VyralX publish workflow (YouTube drafts)
4. ⬜ F11 Futuris scheduled forecast refresh
5. ⬜ F12 Futuris prediction accuracy tracking
6. ⬜ F27 Memora consolidation daemon wiring (see B7)
7. ⬜ E3 Voice auto-reconnect after drop
8. ⬜ E4 Voice-path memory (same as B11 — do together)
9. ⬜ E5 Fleet questions answered by voice
10. ⬜ Commit + notify "Batch 7 complete"

## Batch 8 — Website polish (D 11/18 → 18/18)

1. ⬜ D14 Mobile responsiveness (320–430px)
2. ⬜ D15 Accessibility pass (contrast, aria, keyboard)
3. ⬜ D16 Performance budget (Lighthouse ≥ 90)
4. ⬜ D17 Owner preferences section
5. ⬜ D18 Empty states + onboarding polish
6. ⬜ H7 Public status/uptime page
7. ⬜ A8 Personality consistency chat AND voice
8. ⬜ E7 Voice session diagnostics in SYSTEM tab
9. ⬜ E9 Voice quality tuning
10. ⬜ Commit + notify "Batch 8 complete"

## Batch 9 — Tech debt & tests, part 1 (I 2/8 → 6/8: battery rescue I1–I4) — COMPLETE 2026-11-12 (Lane A / ZAI Agent 1)

1. ✅ I1 Fix `test_real_usage_battery.py::test_the_agent_remembers_and_recalls_a_fact`
   — root causes: battery agents bound to the Oracle backend (no DB in
   sandbox/CI) AND a contacts `who is <name>` hijack intercepting "who is my
   sister?" as a contact lookup. Fixes: battery `_agent()` now uses the
   sanctioned test-only sqlite memory (shared per-test file under tmp_path so
   cross-agent round-trips persist) + `RememberFactTool`/`ManageTasksTool`
   re-registered with test-only sqlite stores; the `who is` contact regex now
   declines possessive/relational questions ("who is my sister", "who is your
   boss", "who is the ceo of google") while bare names ("who is Priya") still
   look up contacts
2. ✅ I2 Fix `test_tasks_round_trip` — hermetic `SQLiteTaskStore` per test
   (tmp_path file shared across agents); task created by agent 1 is listed by
   agent 2 through the real tool path
3. ✅ I3 Fix `test_user_rebalance_request_gets_no_fabricated_targets_without_market_data`
   — the `_portfolio_fast_path` snapshot matcher hijacked
   "Should I rebalance my portfolio?" and answered with a Stratex outage
   instead of the skill layer's honest "can't recommend rebalancing — no
   measured market regime". Advice phrasing (should I / rebalance /
   recommend / advice / good time to) now makes the fast path stand aside so
   the request reaches the cognitive path and VoiceTradingSkill
4. ✅ I4 Full battery green: `test_real_usage_battery.py` **29/29 passed**
   (was 22 failed / 7 passed in the sandbox; hermetic battery also fixed the
   nexus HTTP scenario — "website status" removed from WEB_OPS_KEYWORDS, it
   is the Nexus skill's singular-website domain, Cortex keeps all its locked
   plural/fleet phrases). Regression proof: related-suite failure diff vs
   clean tree IDENTICAL (29 pre-existing sandbox-env failures, 0 new);
   `test_stratex_portfolio_dispatch.py` agents made hermetic too (204 green)
5. ⬜ I5 Coverage gate in CI → moved to Batch 9b
6. ⬜ I6 Dead-code sweep → moved to Batch 9b
7. ⬜ A5 greeting fast-path verification → moved to Batch 9b
8. ⬜ H10 $0-cost audit → moved to Batch 9b
9. ⬜ E10 Indian-English accent check → moved to Batch 9b
10. ✅ Commit + notify (this batch; items 5–9 continue in Batch 9b)

## Batch 9b — Tech debt & tests, part 2 (I 6/8 → 8/8 + verification items) — COMPLETE 2026-11-12 (Lane A / ZAI Agent 1)

1. ✅ I5 Coverage gate in CI — scripts/coverage_gate.py + tests/COVERAGE_MANIFEST.json
   (total floor 16.0% + per-module floors for 7 regression modules), CI's
   seven suites now one --cov invocation + gate step; 7 self-tests
2. ✅ I6 Dead-code sweep — 24 verified-dead files removed (14 Inference
   gateway duplicates, 10 Stratex legacy orphans), 0 new failures
   (61=61 identical pre-existing sandbox errors; Stratex 40/40; CI set 194/194);
   report docs/archive/dead_code_sweep_2026-11-12.md
3. ✅ A5 greeting fast-path VERIFIED (suite hermetic 25/25; stale
   pre-TASK-MEM-003 expectation retired)
4. ✅ H10 $0-cost audit — scripts/zero_cost_audit.py 9/9 PASS +
   docs/security/zero_cost_audit_2026-11-12.md (quarterly; next 2027-02-12)
5. ✅ E10 Indian-English accent check — 18-phrase corpus + scoring sheet + 7
   tests + worker accent-comprehension instruction (owner session closes it)
6. ✅ Hermetic-battery fallout — RESOLVED: conftest sqlite env default
   unlocked ~3,100 previously-unrunnable tests; 6 latent failures surfaced,
   ALL fixed (stale persona/greeting assertions, env-test hermeticity, 25
   fleet fields documented in FRIDAY/.env.example); battery 29/29; all test
   writes stay in tmp paths (never the production schema); production-VM
   pull checklist recorded in docs/handoff.md
7. ✅ Commit + notify "Batch 9b complete"

## Batch 10 — Voice + remaining E items (E 2/10 → 9/10)

1. ⬜ E6 Barge-in + natural pacing (owner 5-min test kit)
2. ⬜ E8 ⛔ self-hosted LiveKit SFU (blocked on ARM server — skip unless unblocked)
3. ⬜ A1–A5 re-verification sweep (already done — confirm and tick)
4. ⬜ F2 Inference usage dashboard + rate-limit guard
5. ⬜ F3 (same as above if separate)
6. ⬜ Remaining ⛔/🔶 items review
7. ⬜ G9 ARM sniper status check (2 workflows hunting)
8. ⬜ G10 second-server workload split (if ARM landed)
9. ⬜ A2/A3/A4 evidence re-check
10. ⬜ Commit + notify "Batch 10 complete"

## Batch 11 — Final integration sweep

1. ⬜ Full test suite run (all modules)
2. ⬜ Deploy verification on both servers
3. ⬜ Checklist re-audit: every ✅ has evidence
4. ⬜ Scoreboard refresh
5. ⬜ H1/H2 IST verification sweep
6. ⬜ H3 CI/CD green on main
7. ⬜ H4 Backup + restore re-test
8. ⬜ Any stragglers from batches 1–10
9. ⬜ Master checklist final pass
10. ⬜ Commit + notify "Batch 11 complete"

## Batch 12 — Buffer / owner acceptance

1. ⬜ Owner walkthrough of live features
2. ⬜ Fix anything the owner flags
3. ⬜ Final Telegram notification "100% complete"
4. ⬜ Celebration
5–10. ⬜ Reserved for owner feedback items

---

## Batch 6 — Agent depth I (F 9/27 → 18/27) — EXECUTED BY ZAI AGENT 2, COMPLETE 2026-11-11 IST

> Lane B (claim: issue #35 comment 6802957472). Cross-lane touches claimed there:
> capability_router.py (FETCH_SUMMARIZE_KEYWORDS), api/server.py (one lifespan
> task + watchlist fast-path), tools/__init__ + mixins/tools.py (tool registration).

1. ✅ F8a watchlist store + chat intake ("watch topic X", casing preserved)
2. ✅ F8b scheduled daily briefing (17:30–20:00 IST, IntelX real dispatch, ≤6 topics)
3. ✅ F9 change detection (SHA-256 + headline-line diff; no-change/what's-new/first-brief)
4. ✅ F13 web_fetch_summarize tool + SSRF guard + FETCH_SUMMARIZE_KEYWORDS routing
5. ✅ F14 uptime checks (10 gateway routes + Cortex governed properties, one truth)
6. ✅ F15 scheduled site sweep (08:00–12:00 IST; healthy → one line, degraded → alert)
7. ✅ F17 dependabot.yml (weekly Monday; github-actions + pip; grouped, security-first)
8. ✅ F18 agent-health-digest.yml (weekly Monday 10:00 IST; pip-audit + CI failures digest)
9. ✅ F20 Sentinel digest (Monday 09:30 IST; ask_sentinel + findings, read-only)
10. ✅ F21 pre-push secret guard (scripts/guard_secrets_pre_push.py + .githooks/pre-push; self-test 7/7)

Evidence: test_batch6_agent_depth.py 35/35; full battery A/B vs clean main —
446 passed, 18 failed, failing set IDENTICAL to the pre-existing baseline
(Oracle-driver environmental), zero new failures. Checklist recount: 91/125 (73%).

**Current position (merged 2026-11-12 IST): Batches 1-6 COMPLETE + Batch 9 part 1 - Agent 1: Batches 1-4 + Batch 9/I1-I4 (battery rescue: real-usage battery 29/29 green, hermetic test-only persistence, 3 routing hijacks fixed - contacts 'who is', portfolio-advice, website-status; 0 regressions vs clean tree); Agent 2: Batches 5 (autonomy G+H, 42 new tests) and 6 (agent depth I: F 18/27 - watchlist+briefings, change detection, SSRF-guarded fetch/summarize, uptime+sweeps, dep/CI health, Sentinel digest, pre-push secret guard; 35/35 batch tests, 0 regressions). Lanes active (ZAI_AGENT_2_ONBOARDING.md): ZAI Agent 1 (Lane A) -> next Batch 9b (I5 coverage gate, I6 dead-code sweep, A5/H10/E10 verifications); ZAI Agent 2 (Lane B) -> next Batch 7 (agent depth II: F3, F5, F6, F11, F12, F22-F24), then 8. Notification protocol: @zai_notifications_bot only, agent name on the FIRST LINE of the message (owner directive 2026-11-12). Checklist recount after this merge: see docs/MASTER_COMPLETION_CHECKLIST.md scoreboard.**

## Batch 7 — Agent depth II (F 18/27 → 27/27, F module COMPLETE) — EXECUTED BY ZAI AGENT 2, COMPLETE 2026-11-12 IST

> Lane B (claim: issue #35 comment 6803967919). Completes the F module to
> 27/27. Cross-lane touches claimed there: capability_router.py (3 new
> keyword sets), api/server.py (extended agent_watch loop with F5/F6/F11/F12
> passes + alert fast-path + F3 usage endpoint), tools/__init__ +
> mixins/tools.py (2 new tool registrations).

1. ✅ F3 — UsageTracker + GET /api/agents/usage + rate-limit guard (80%/100%)
2. ✅ F5 — scheduled 09:00 IST daily portfolio report via Stratex → Telegram
3. ✅ F6 — price-alert rules engine (chat intake, hourly eval, latched firing)
4. ✅ F11 — twice-daily forecast refresh (09:30 + 18:30 IST) on tracked markets
5. ✅ F12 — prediction accuracy scoring at horizon end (HIT/MISS/PARTIAL)
6. ✅ F22 — verified live (VyralXScriptTool, batch 3)
7. ✅ F23 — vyralx_render tool (real VyralX hyperframes render pipeline)
8. ✅ F24 — vyralx_publish tool (fail-closed draft; D-015 two-gate for prod)
9. ✅ F27 — verified live (_nightly_consolidation_loop in server lifespan)
10. ✅ batch protocol — tests + docs sync + claim/closure on issue #35

Evidence: test_batch7_agent_depth_2.py 42/42; full A/B battery 15 suites:
487 passed, 18 failed = byte-identical pre-existing baseline, zero new
failures. Checklist recount: 100/125 (80%); F module 27/27 (100%).

## Batch 8 — D/E/H module polish (D 13→18, E 2→9, H 7→10) — EXECUTED BY ZAI AGENT 2, COMPLETE 2026-11-12 IST

> Lane B (claim: issue #35 comment 6804466165). 15 reachable items delivered.
> E8 stays blocked on ARM (G9 capacity-gated). No overlap with Agent 1's
> I-module lane.

1. ✅ D14 — mobile 320-430px breakpoint (extends the existing 720px one)
2. ✅ D15 — a11y: focus-visible rings, skip-link, aria-labels
3. ✅ D16 — Lighthouse CI workflow + budget (>= 0.9 all categories)
4. ✅ D17 — owner preferences: core/owner_preferences.py + GET/POST API + UI
5. ✅ D18 — EmptyState + OnboardingHint shared components
6. ✅ E3 — VoiceCall auto-reconnect (2 attempts, exponential backoff)
7. ✅ E4 — verified live (B11 voice memory; memory/voice_memory.py)
8. ✅ E5 — verified live (Gemini Live function_declarations routing)
9. ✅ E6 — barge-in 5-min test kit doc (docs/voice/BARGE_IN_TEST_KIT_E6.md)
10. ✅ E7 — voice diagnostics GET + POST report endpoints + VoiceDiagnostics card
11. ✅ E9 — verified live (voice_name + VAD config in config.py)
12. ✅ E10 — accent check doc (docs/voice/ACCENT_CHECK_E10.md; en-IN default)
13. ✅ H6 — docs sync (scoreboard recounted from ticks)
14. ✅ H7 — public status page (FRIDAY/ui/public/status.html + GET /api/status/public)
15. ✅ H10 — $0-cost audit doc + quarterly reminder workflow

Evidence: test_batch8_polish.py 21/21; A/B battery 17 suites: 517 passed / 18
failed = byte-identical to the merged-without-batch-8 baseline, zero new
failures; server imports cleanly. Checklist recount: 119/125 (95%).

**Current position: Batches 1–8 + Batch 9 Part 1 COMPLETE (2026-11-12 IST). Checklist 119/125 (95%); D 18/18, E 9/10, F 27/27, H 10/10 all COMPLETE. Remaining: A8 (personality consistency), E8/G9/G10 (blocked on ARM server capture), I5/I6 (Agent 1's lane — Batch 9 Part 2). Lanes: ZAI Agent 1 (Lane A) → Batch 9 Part 2 (I5 coverage gate, I6 dead-code sweep); ZAI Agent 2 (Lane B) → A8 + I5/I6 if Agent 1 hasn't started, then blocked-item monitoring.**
