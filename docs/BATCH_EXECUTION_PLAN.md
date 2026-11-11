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
     orchestration, memory/brain, tech debt, final sweeps. Signs Telegram
     notifications `— ZAI Agent 1`.
   - **ZAI Agent 2 (Lane B):** Batches 6, 7, 5, 8 — agent depth F, autonomy G,
     website polish D. Signs `— ZAI Agent 2`. Onboarding:
     `docs/collaboration/ZAI_AGENT_2_ONBOARDING.md`.
   - All notifications from `@zai_notifications_bot` (never
     `@fridayuniverse_bot`). Claim cross-lane files in WORK_BOARD + issue #35
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

## Batch 4 — Memory + Brain maturity (B 9/12, A 5/14)

1. ⬜ B8 Importance scoring: trivial facts age out, core pinned
2. ⬜ B11 Voice-path memory: "remember X" on the voice line
3. ⬜ B12 Memory visibility: what-FRIDAY-knows browser in dashboard
4. ⬜ A6 Multi-turn coherence: 10+ turn context retention test
5. ⬜ A7 Reasoning benchmark suite: 20 delegation prompts, weekly run
6. ⬜ A9 Casual/sarcastic tone matching
7. ⬜ A11 Long-goal persistence: Monday goal tracked Friday
8. ⬜ A12 Proactive follow-up pings on unfinished tasks
9. ⬜ A14 Boss-only command surface (owner-exclusive commands)
10. ⬜ Commit + notify "Batch 4 complete"

## Batch 5 — Autonomy (G 4/12 → 10/12)

1. ⬜ G5 Telegram two-way: text FRIDAY from phone, get answers
2. ⬜ G6 Overnight mission loop: queue at night, execute, morning report
3. ⬜ G7 Daily self-report 21:00 IST Telegram
4. ⬜ G8 Weekly summary (Sunday evening)
5. ⬜ G11 Self-healing sweep: disk, certs, backups daily
6. ⬜ G12 Autonomous task intake: owner TODO → FRIDAY queue
7. ⬜ H8 Cert-expiry auto-check (duckdns)
8. ⬜ H9 Log rotation verified on both servers
9. ⬜ H6 Docs sync pass
10. ⬜ Commit + notify "Batch 5 complete"

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

## Batch 9 — Tech debt & tests (I 2/8 → 8/8)

1. ⬜ I1 Fix `test_real_usage_battery.py::test_the_agent_remembers_and_recalls_a_fact`
2. ⬜ I2 Fix `test_tasks_round_trip`
3. ⬜ I3 Fix `test_user_rebalance_request_gets_no_fabricated_targets`
4. ⬜ I4 Full battery green 29/29
5. ⬜ I5 Coverage gate in CI
6. ⬜ I6 Dead-code sweep
7. ⬜ A5 greeting fast-path verification (may already be done — verify + tick)
8. ⬜ H10 $0-cost audit
9. ⬜ E10 Indian-English accent check
10. ⬜ Commit + notify "Batch 9 complete"

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

**Current position: Batches 1–3 COMPLETE (2026-11-11) by ZAI Agent 1 (Batch 2: Stratex strategy depth incl. honest walk-forward negatives; Batch 3: orchestration 10/10, 53 new tests green, 0 regressions). Two-agent lanes now active: ZAI Agent 1 (Lane A) → next **Batch 4** (memory + brain maturity: B8, B11, B12, A6, A7, A9, A11, A12, A14); ZAI Agent 2 (Lane B) → first assignment **Batch 6** (agent depth I), then 7 → 5 → 8. Onboarding: docs/collaboration/ZAI_AGENT_2_ONBOARDING.md**
