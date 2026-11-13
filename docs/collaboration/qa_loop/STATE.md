# QA Loop State — shared by the two hourly scheduled runs

> This file is the handoff memory between runs. SWEEP (hourly :00) repairs the fleet.
> CHAOS (hourly :30) tests like a hostile human and ships one upgrade.
> A run that ends without updating this file is a FAILED run.

## LAST_RUN
- none yet (file seeded 2026-11-13 by ZAI Agent 1)

## IN_PROGRESS (must be finished or cleanly reverted FIRST, before any new work)
- TASK-STRATEX-OANDA-001 — OANDA demo trading live (cron job 528111 runs the validated
  portfolio_v2 D1 engine hourly). Open question: 2026-11-13 16:57 IST all 6 trades closed
  via TRADE_CLOSE market orders not originating from this loop — identify key holder
  (likely manual close in OANDA web UI) before treating it as a defect.
- TASK-WF-015 — United owner-workflow acceptance and real shared-memory/research lifecycle.

## FINDINGS_QUEUE (severity | repro | discovered by | status)
- MEDIUM | 2026-11-13 16:57 IST: trades 57-77 flattened externally 2 min after open,
  -42.47 USD realized; not SL/TP, not this loop. Confirm = owner manual close. | SWEEP | OPEN
- (sweep runs append here; fixed items move to DONE with commit hash)

## UPGRADE_BACKLOG (CHAOS run implements exactly ONE per run, smallest-first)
1. TASK-WF-009 — Isolate generated-project tests, preserve Python code fences (BLOCKED board item).
2. TASK-WF-008 — Preserve released goal-specific code during repair + embedded unittest exec.
3. TASK-WF-007 — Goal-specific real model code + valid generated tests through Forge/Inference.
4. Owner standing asks: site performance polish (minimal dynamic design), chat reply brevity,
   agent autonomy depth (screen-read / app-open), voice robustness.

## CHAOS_ROTATION (one surface per CHAOS run, cycle top to bottom)
1. chat-brain (rapid-fire, long/unicode/malformed input, secret-siphon prompts, live-money refusal)
2. voice (call start, mid-call interrupt, drop-reconnect, timeout)
3. fleet-dispatch (real task through FRIDAY to a specialist; kill+restart one service; breaker check)
4. website (load timing, mobile viewport, asset 404s, JS console errors)
5. stratex-oanda (quotes fresh, bad-order rejection, SL/TP on every open trade, breaker states)
6. security (unauthenticated /bridge and /api probes must be fail-closed per D-023; no secrets in responses)
(next surface = 1)

## DONE
- none yet
