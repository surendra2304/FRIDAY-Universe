# TASK-FUT-049 — checkpoint 1 (claim + scoping, 2026-11-28 ~11:25 IST)

**Task:** TASK-FUT-049 (P2) — "Futuris: forecast quality — score the next unscored batch after FUT-047 + fit-cost cap check".
**Worker:** Muse TP11. **Claim:** WATCH258 §D (hub #2045 comment 7234793701) assigns FUT-049 → TP11 as head; BE 11:15 §B (hub 7234754534) named it TP11's next head when boarded. Boarded in board PR #2279, merged → live main `300ab00c`.
**Branch:** `musetp11/task-fut-049-forecast-quality-next-batch`, created from main `300ab00c`.

## Board verification (live main `300ab00c`, WORK_BOARD.yaml blob `6c05821a`, first-hand)

- FUT-049: status AVAILABLE, owner null, branch null, pr null, priority P2, blockers [] — no competing claim in hub #2045 through comment #1178 (7234822915).
- Acceptance: "Next unscored forecast batch scored against outcomes with accuracy evidence filed as docs/collaboration/TASK-FUT-049-EVIDENCE.md; fit-cost cap checked."
- Live-proof route: "Futuris scheduler cycles on IntelX-Server; scored forecasts from live runs."
- Board flip to CLAIMED rides the work PR (coordinator-only flip rule).

## Predecessor chain (first-hand)

- FUT-044: re-slotted from TP11 to the pool (WATCH256 §D; board on live main reads AVAILABLE / owner null, branch `musetp11/task-fut-044-forecast-quality-scoring` kept). **Release confirmed this run.** WATCH258 §D assigns FUT-044 → Muse 13 as head.
- FUT-045: MERGED via PR #2260 (merge `da6b61e9`); TP11 VERIFIED review 6095522915 (filed 09:02 run).
- FUT-046: claimed by Muse 11 (hub 7234284282); work PR not verified this run.
- FUT-047: AVAILABLE / owner null on live main `300ab00c`; Muse 9's hold lapsed per WATCH258 §D ("both tasks stay AVAILABLE in the pool; any free chat may pull them").

## Scoping question — stated plainly

FUT-049's batch is defined as "the next unscored batch after FUT-047". FUT-047 is currently unscored and unclaimed, so FUT-049's batch does not exist yet — it comes into being when FUT-047 is scored. Two paths, decided at checkpoint 2:

- (a) If FUT-047 gets scored first (by whoever pulls it), FUT-049 scores the next unscored batch after it.
- (b) Queue-drain fallback, per the FUT-045 precedent: M7's ~08:50 IST sweep found 0 unscored and the batch scored was the newest scheduler-scored one. If the scheduler keeps the queue drained, FUT-049 scores the newest scheduler-scored batch and says so in the evidence.

## Grounding (from the verified FUT-045 record — my own #2260 verdict, 09:02 run)

- Live hit rate 0.0 vs synthetic 1.0 — 0.0 is expected, NOT a queue-drain artifact: the live fleet-demand model systematically under-predicts (~269 vs ~1750, mean pct error 85.7%), a persistent FUT-016 finding repeated in the 72h window (live 0.0, n=55; synthetic 1.0, n=445). Synthetic 1.0 is vacuous (one series under seven labels, prediction 875.05).
- Cap mechanism on main: `Futuris/futuris/infra/config.py:149-161` (`FUTURIS_FIT_MEMORY_BUDGET_MB` default 256, half the 512M backstop) and `Futuris/futuris/models/selection.py:129-147` (shortlist + `fit_cost_cap` stamping). Evidence cites the paths without the `Futuris/` prefix and one line off; substance exact.
- OOM counter-evidence: TP14 hub 7232898215 (02:35 UTC OOM kill, peak 512.2M vs 512M cap; restart 03:07:33 UTC, new PID 60746). FUT-045 evidence carries the cap caveat honestly (zero cap events; cap checked, not proven to bind first).
- Tracker report at FUT-045: n_scored 1266.

## Checkpoint 2 (live scoring) — the live leg

- Score the batch per §Scoping, file `docs/collaboration/TASK-FUT-049-EVIDENCE.md`, check the fit-cost cap (cap-event count + whether the cap binds first), open the work PR.
- First-hand data needed from IntelX-Server: tracker report (n_scored), scheduler job times for the last 3 cycles, cap-event count.
- Authorization basis for the live leg: WATCH248 §D (standing clearance 7200564540 covers TP11's own-task live verification) + WATCH256 §D (grant question SETTLED, not owed: full run_shell approved for all worker chats; owner tap 2026-11-26 18:25:56 IST; rulings 7192682851, 7197725825, burn order 7200414167). The broader main-agent decision on burn-order genuineness remains formally open in TP11's log; the live leg proceeds on these two rulings as the task's authorization basis, stated plainly here.

## States

- Implemented: N/A (scoring task — no code change expected; evidence only)
- Tested: NO (live scoring not run yet)
- Merged: NO (work PR not open yet)
- Deployed: N/A
- Production-verified: NO

## Files

- This checkpoint doc: `docs/collaboration/TASK-FUT-049-CHECKPOINT-1.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-FUT-049 AVAILABLE / owner null on live main `300ab00c`)
- Prior evidence: `docs/collaboration/TASK-FUT-045-EVIDENCE.md` (M7, PR #2260, MERGED)

— Muse TP11, 2026-11-28 ~11:25 IST
