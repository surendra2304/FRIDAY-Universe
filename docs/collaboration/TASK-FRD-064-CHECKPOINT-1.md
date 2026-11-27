# TASK-FRD-064 — Checkpoint 1: scoping (investigation + fix plan)

**Task:** FRIDAY: investigate + fix FRIDAY.service OOM-kills under chat turns.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-064-oom-kills-chat-turns` (@ `f5374e4c`, verified via ls-remote).
**Claimed:** 2026-11-27 ~16:15 IST (hub #2045, Burn Enforcer 16:00 §C: FRD-064 returned to pool top priority after Muse 1 wrapped up on exhausted allowance; "the next chat to post free/completion claims FRD-064 FIRST" — this claim, in the FRD-062 completion post).
**Board on live main `3db9f11a`:** CLAIMED / owner `muse_1` / branch null / pr null / P1 (flip to the new owner rides the coordinator's board PR; M1's claim released by the BE ruling, not by a board edit from me).

## 1. Handover from Muse 1 (wrap-up hub 7215915452, 15:57 IST)

- M1's branch `muse1/task-frd-064-oom-kills-chat-turns` @ `b1fe4365`, zero commits; investigation notes current in M1's `WORK_NOTES.md` (not in the repo — M1-local).
- Core lead: fresh workers climb to 74% of the 200 MB cap within 60s.
- Restart cluster 07:51–08:10 UTC is peer-initiated graceful stops, actor TBD (hub 7213275166 unanswered) — not OOM.
- FRIDAY OOM-killed 15:07 IST; VOI-045 firing (TP10) waits on this fix.

## 2. Source record: TASK-FRD-051 production-verify (PR #2044, merge d6ca83b8)

- OOM kills observed mid-verification in legs 2 and 4; restart counter 3+ (pids 70495 → 73891 → 75069, ~22:46 / ~23:34 / ~23:51 UTC 2026-11-26). Auto-restart recovers, but the owner-facing assistant dying under a chat turn is a real defect.
- Hub verdicts 7205056708, 7205437623, 7206115187. Follow-up registry and errand store both survived auto-restart (state is durable; the defect is the process dying, not data loss).
- FRD-051 live findings routed to this task: OOM-kills under chat turns, repeatedly.

## 3. Live state measured this run (first-hand, bridge server 3 = FRIDAY-Server, ~16:15 IST)

- `FRIDAY.service`: active / running, MainPID `100296`, entered active state 09:37:09 UTC after the 09:37:02 UTC OOM kill; `NRestarts=1` in this activation.
- Memory: `MemoryCurrent=36,507,648` (~34.8 MB) / `MemoryMax=209,715,200` (200M). Process ~1h old at probe time and still low — the climb is tied to chat-turn load, not idle time.
- Unit: `uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1`, `WorkingDirectory=/opt/friday_universe/FRIDAY`, `Restart=always`, `RestartSec=5`, `MemorySwapMax=192M`.
- OOM kills on 2026-11-27 (journal, first-hand): **06:21:02, 08:07:11, 09:37:02 UTC** (11:51, 13:37, 15:07 IST) — three kills, roughly every 1.5–2.5h under chat-turn load. TP10 independently read the 09:37 kill at 199.9 MB / 200 MB (hub 7215274604).
- Bridge note for the sweep: `run_shell` intermittently returns NO RESULT PARSED with SSE pings (~60–90s) though the command keeps running — background + poll is the working pattern (FRD-051 finding 5).

## 4. Working hypotheses (ranked)

1. **Per-turn memory growth not released** — the chat-turn path accumulates (conversation history / context, tool-call artifacts, caches) and never returns it; each turn ratchets RSS toward the cap.
2. **A specific turn type spikes memory** — large context, file/tool payloads, or a particular tool (goal loop, job-hunt scan) allocates a big chunk in one turn.
3. **Baseline footprint too close to the cap** — warm-up growth (M1's 74%-in-60s lead) leaves little headroom, so ordinary turns tip it over.
4. **Cap simply too small for the workload** — fix is a code-side leak fix first; any unit-file / `MemoryMax` change is a server move and needs coordinator clearance, not a unilateral edit.

## 5. Investigation plan

1. Memory sampling across controlled chat turns on the live service (read-only first): `MemoryCurrent` before/after each turn, plus per-turn RSS — find the ratchet and which turn type drives it.
2. Correlate journal kill times with the turns that ran just before each kill (turn type, size, tool used).
3. Inspect in-memory stores for unbounded growth: goal loops, missions queue, conversation history, caches, any per-turn append-only structure.
4. Name the root cause with numbers, then fix in code (repo PR). A unit-file change is only proposed, never applied unilaterally.

## 6. Acceptance (board)

- FRIDAY.service no longer OOM-killed under chat turns: root cause found and fixed, proven by a live verification sweep of chat turns with the service stable throughout.
- Live-proof route: live FRIDAY on FRIDAY-Server; file probe output as evidence.

## 7. Five states

- Implemented: NO. Tested: NO. Merged: NO. Deployed: NO. Production-verified: NO.

## 8. Next

- Run the memory-sampling investigation (§5.1–5.3), then checkpoint 2: the fix PR with live evidence.
- Queue: FRD-064 (head) → TASK-EARN-015 (pre-staged next) → TASK-EARN-017.
