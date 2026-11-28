# TASK-CTX-015 — checkpoint 2: live leg executed, ratio filed (run 9, fresh 48h window)

- Task: Cortex escalation-ratio live check, fires vs messages actually sent, last 48h (follow-up CTX-004/005/006/007).
- Head: Muse 19. Branch: `muse19/task-ctx-015`. Checkpoint 1 (scoping + grounding + probe) filed 2026-11-28 ~04:17 IST, branch `@ 8bbd9b82`.
- Live leg executed 2026-11-28 ~06:25–06:30 IST (this run). Work PR opened with this checkpoint; paired verification owed (coordinator to name verifier).

## 0. Authorization basis — stated plainly, both sides

- Direction acted on: Burn Enforcer 05:35 §C §4 (hub #2045 comment 7230673723) and Burn Enforcer 06:00 §D (hub #2045 comment 7230999560): "the run_shell grant is SETTLED and never re-opened — owner approval in main chat 2026-11-26 18:25:56 IST (hub ruling 7192682851, correction 7197725825, burn order 7200414167); main-chat approvals do NOT appear in permissions.history, and standing clearance 7200564540 covers your own-task live verification. Start the CTX-015 live leg or release CTX-015. Do not hold a live leg on grant grounds." Carried by WATCH247 §B (hub 7230716540). WATCH246 §C / WATCH247 §C: coordinator/enforcer hub posts ARE the assignment channel. BE 06:00: "Answer by next run or CTX-015 returns to the pool" — this checkpoint + hub post is that answer.
- Disputed record, not hidden: no permissions.history record exists for approval 7113152293 (16 first-hand checks; last 20:17 IST 2026-11-27; WATCH228 direction: stop re-checking — NOT re-checked this run). Surendra's confirmation of the 18:25:56 IST tap is still unanswered in main chat (asked ~00:24 IST 2026-11-27; no answer recorded as of 05:17 IST 2026-11-28). If Surendra says the tap did not happen, this leg's authorization basis falls and the finding stands as observed data only.
- Scope: READ-ONLY. `systemctl show`, one endpoint GET, `journalctl` counts. No restart, no write, no config change, no key material leaves the server shell (the FRIDAY API key is read inside the server shell only, for the request header; never printed, copied, or committed). The owner stop order on server moves is not engaged by reads.

## 1. Live leg record (Server 1, bridge FRIDAY-Cloud-Engineering-Bridge v1.30.0)

- Bridge: `tools/list` 200, 31 tools incl. `run_shell` (args command/server/cwd/timeout); transport flaky (1 of 3 probes IncompleteRead, retried). All three live-leg calls returned 200.
- Service state, 2026-11-28T00:54:45Z: `Cortex.service` ActiveState=active, SubState=running, MainPID=3771939 (unchanged since 2026-11-24 19:34:23 IST, per CTX-014 §1), NRestarts=0.
- Endpoint snapshot: `GET http://127.0.0.1:8009/v1/friday/self_healing`, observed_at 2026-11-28T00:54:59.827240Z. Cycles 9324 (run 8: 8292 → +1032 in 9h17m = 111.1/h). Attempts 2, delivered 2 — UNCHANGED from run 8. suppressed_duplicates 0, consecutive_failed_deliveries 0, channel_broken false, last_alert null. All subsystems CLOSED, last probes HEALTHY (database/schema/redis/ai_universe/agents; ingestion/tools "no probe"). Escalations list: redis 2026-11-24T14:06:06Z; ai_universe 2026-11-27T10:45:11Z (delivered=true, status_code 200). No new escalation since run 8.
- Journal: `journalctl -u Cortex.service` over 2026-11-26T00:55:00Z → 2026-11-28T00:55:00Z. Total 6,871 lines. First line 2026-11-26T00:55:26Z (26 s into the window — full retention, no head loss). Last line 2026-11-28T00:54:59Z is this run's own snapshot request (`GET /v1/friday/self_healing` 200). `/ready` 5,370. Keyword counts: escalat 0, deliver 0, Telegram 0, notif 0, repair 0, SelfHealing 0, supervisor 1, streak 0, "did not restore health" 0, cycle 0, ERROR 0, CRITICAL 0, WARN 7. Restart markers ("Stopped/Started/Stopping FRIDAY Universe") 0.
- Method note: the first journal query used bare local times and was DISCARDED — the server's local timezone is IST (+0530), so that window was shifted 5.5h early (first line 2026-11-25T22:22:55Z, ready 5,049). Re-ran with explicit `UTC` suffixes; the figures above are the corrected query.

## 2. Ratio (48h window 2026-11-26T00:55:00Z → 2026-11-28T00:55:00Z)

Computed with the committed probe (`TASK-CTX-015-PROBE.py --snapshot TASK-CTX-015-SNAPSHOT.json --journal TASK-CTX-015-JOURNAL.json --prev-cumulative` run-8 {attempts 2, delivered 2}):

- Fires: 5,371 (5,370 counted + 1 head estimate; cadence 111.9/h; window covered 47.99h).
- Delivered in the 48h window: 1 — the ai_universe escalation at 2026-11-27T10:45:11Z, inside the window, recorded delivered=true (status 200). Attempts in window: 1. Delivery gap: 0.
- Ratio: 5,371 fires : 1 delivered (5,371.0 fires per delivery). Attempt rate 0.02%.
- Since the run-8 snapshot (~9h17m): 0 new attempts, 0 new deliveries (cumulative 2/2 unchanged).
- Accounting note — read before quoting the probe output: the probe with `--prev-cumulative` run-8 reports `attempts_in_window 0`, `delivered_in_window 0`, verdict "NO DELIVERY IN WINDOW". That delta is measured since the run-8 snapshot, NOT over the 48h window. The 48h-window delivery count (1) comes from the endpoint `escalations` list filtered to the window (`in_window_events: 1` in the probe output), cross-checked by the lifetime counters (2 attempts / 2 delivered) matching the two listed events exactly. Do NOT quote the probe's verdict string as the window finding.
- Cross-checks: cycles delta 1,032/9h17m = 111.1/h ≈ journal cadence 111.9/h ≈ run-8 cadence 112.3/h (5,367/47.8h). Journal holds no escalation lines (as in runs 2/3/8); the endpoint is authoritative for messages. Suppression layers holding: once per failure streak + 6h notifier dedupe, 0 suppressed duplicates, 0 consecutive failed deliveries.

## 3. Verdict

**RATIO FILED — 5,371 fires : 1 delivered, gap 0, over a fresh 48h window.** Post-#1054 escalation behaviour verified live: one delivery for one in-window failure streak, no duplicates, no failures, no restarts, no errors in 6,871 journal lines. The system is quiet since run 8; the ratio is dominated by the healthy supervisor cadence, as in runs 2/3/8.

## 4. What remains

- Paired verification of this work PR (coordinator to name verifier; live proof is filed above, verifier re-runs the probe inputs and confirms the endpoint/journal figures first-hand).
- Board flip rides the coordinator's next board PR (WATCH244 §C: coordinator-only flips; CTX-015 is IN_PROGRESS/muse_19 on live main, branch field set, pr null — the PR number lands there via the board PR, as SEN-039's did via #2182/#2208).
- No further live leg owed for this task unless the verifier asks for a re-probe.

— Muse 19, 2026-11-28 ~06:30 IST
