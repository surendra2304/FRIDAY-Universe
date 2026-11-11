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

## Batch 2 — Stratex strategy depth (owner: "more profitable trades")

1. ⬜ Walk-forward validate 2 dormant strategies with real data (candidates:
   `strategy_trend_pullback`, `strategy_volatility_breakout`) — only promote
   with ≥30 OOS trades, PF ≥ 1.0
2. ⬜ Add regime filter to supertrend shorts (BLOCK_SHORTS_IN_BULL_REGIME
   default true; ledger shows shorts fighting the trend)
3. ⬜ Position sizing: volatility-scaled (target 1% risk per trade across ATR
   regimes) — verify live sizing path uses it
4. ⬜ Trailing-stop behavior audit: verify `testnet_engine/trailing.py` moves
   stops to break-even at 1R (protects the 4:1 winners)
5. ⬜ Confluence scoring: require ≥2 strategy agreement for full size, single
   strategy = half size (uses `risk/strategy_coordinator.py`)
6. ⬜ Max trades/day per symbol cooldown (stop revenge-entries on one symbol)
7. ⬜ Telegram /pnl command: daily + rolling 7-day PnL from the ledger
8. ⬜ F5: scheduled daily portfolio report (Telegram, 09:00 IST)
9. ⬜ F6: price/alert rules → Telegram push
10. ⬜ Commit + notify "Batch 2 complete"

## Batch 3 — Orchestration completion (C module: 10/14 → 14/14)

1. ⬜ C7 VyralX delegation: video script generation via chat
2. ⬜ C9 Cortex delegation: web fetch/monitor tasks via chat
3. ⬜ C11 Memora delegation: memory ops as first-class tasks
4. ⬜ C12 Multi-agent pipelines: chained dispatch ("research X, then draft")
5. ⬜ A10 Clarification quality: ONE sharp question when ambiguous
6. ⬜ A13 Response formatting policy: consistent lists, no wall-of-text
7. ⬜ D13 Task timeline: delegation history with status chips
8. ⬜ D11 Live activity feed: full event coverage
9. ⬜ Tests for all of the above
10. ⬜ Commit + notify "Batch 3 complete"

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

## Batch 6 — Agent depth I (F module: Sentinel, IntelX, Cortex)

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

**Current position: Batch 1 COMPLETE (2026-11-11) — all 10 tasks done, 71 tests green. Next: Batch 2 — Stratex strategy depth**
