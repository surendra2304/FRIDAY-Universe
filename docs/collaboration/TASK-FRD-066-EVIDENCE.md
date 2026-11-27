# TASK-FRD-066 — FRIDAY OOM memory-guard live proof (trip receipt)

- **Worker:** Muse 13. **Assignment:** WATCH218 §F / Burn Enforcer 17:47 §B (hub #2045) — queue head, IG2 pair blocked. Follow-up to TASK-FRD-043 (PR #2088 MERGED).
- **Claim:** hub #2045 comment 7217947941 (17:41:36 IST). Branch `muse13/task-frd-066-oom-live-proof` @ `896ceb7a`.
- **Live leg:** bridge `run_shell`, server 3 (FRIDAY-Server), read-only recon 2026-11-27 ~17:43–17:52 IST (12:13–12:22 UTC). No production change made; no allocator, no restart, no config touched. Standing clearance 7200564540 (own-task live verification).

## Acceptance

"The FRD-043 memory guard is proven live on FRIDAY-Server: it trips (sheds load / restarts cleanly) before memory exhaustion, with the trip receipt filed as docs/collaboration/TASK-FRD-066-EVIDENCE.md. No voice session is dropped without a filed receipt; guard thresholds recorded in the evidence."

## Live state at recon

- **Service:** `FRIDAY.service` active/running. Current worker **pid 100296**, started **09:37:09 UTC** (15:07:09 IST), elapsed 2h36m at recon. Server process up since 09:37:24 UTC; LiveKit token request served 200 at 09:55:14 UTC.
- **Cgroup:** `/sys/fs/cgroup/system.slice/FRIDAY.service` — `memory.max` 209,715,200 (200 MB), `memory.swap.max` 201,326,592 (192 MB). At 12:12:58 UTC: `memory.current` 61,046,784 (~58 MB, 29.1%), `memory.swap.current` ~109.7 MB. `memory.events` since the 09:37 restart: `max 9488, oom 0, oom_kill 0` — no OOM kill since the restart.
- **Guard code:** live file byte-identical to main — sha256 `8c351d7af1a17bd7db15e2e231a9cd88c9132ad479906da5b74c005cce5a2c06` (main blob `a43782bd`). Live checkout HEAD `06ff9ee6` (the FRD-043 deploy-leg sync); working tree has only the pre-existing `FRIDAY/ui/out/*` build dirt.
- **Thresholds** (from `FRIDAY/src/friday/observability/proactive_engine.py` on main): warning `MEMORY_WARN_PERCENT = 75.0`, critical `MEMORY_CRITICAL_PERCENT = 90.0`, recovered `MEMORY_RECOVERED_PERCENT = 60.0`. Poll loop default 30 s in code (FRD-043 doc cites a 120 s configured interval; observed alert cadence is seconds-to-minutes — see sequence below).

## Trip receipt — the guard trips live on natural pressure

`friday.log` holds **94 guard lines today: 42 warnings, 26 criticals, 26 recoveries**. No staged allocator was needed: the worker's own memory is volatile enough to trip the guard repeatedly. Headline sequence since the 06:44 UTC restart (all times UTC, all from `friday.observability.notifications`):

| Time | Event | Reading |
|---|---|---|
| 11:45:00 | warning | 76.4% (152.9 MB) |
| 11:45:04 | warning | 85.4% (170.7 MB) |
| **11:45:31** | **critical** | **100.0% (200.0 MB)** |
| 11:46:01 | recovered | below 60% |
| 12:01:02 | warning | 77.1% (154.2 MB) |
| 12:01:25 | warning | 83.5% (166.9 MB) |
| **12:01:34** | **critical** | **100.0% (199.9 MB)** |
| 12:02:05 | recovered | below 60% |

Earlier today the same pattern ran all morning (e.g. critical 97.3% 04:25:06 → 100.0% 04:25:15 → recovered 04:27:39; critical 99.9% 04:59:35 → recovered 05:00:12). **Every critical was followed by a recovery below 60% within ~30–90 s, with the worker surviving** — the memory pressure eased (pages swapped out) without a kill in these instances.

**Telegram delivery:** 0 `Memory-guard Telegram send failed` lines in the log. Criticals carry the direct Telegram send (`_send_telegram` → gateway to the owner chat); the gateway logs failures only, so a successful send leaves no line — owner-side receipt is owner-confirmed only, same caveat as FRD-043.

## The honest caveat — the guard trips, but it does not prevent the kill

The guard is a smoke alarm, not a sprinkler (FRD-043's own wording). **Three OOM kills hit this cgroup today**, each after the guard warned:

| Kill (UTC / IST) | Killed pid | Guard warning just before |
|---|---|---|
| 06:21:02 / 11:51:02 | 78229 | warning 75.2% 06:20:21, warning 86.4% 06:20:51 (FRD-043 doc) |
| 08:07:11 / 13:37:11 | 96773 | (warnings all morning; see log) |
| **09:37:02 / 15:07:02** | **100277** | warnings/criticals through the morning, incl. 100% criticals |

For the 09:37 kill, the journal shows the full clean-restart sequence: `09:37:02 FRIDAY.service: A process of this unit has been killed by the OOM killer` → `09:37:04 Failed with result 'oom-kill'` → `09:37:09 Started FRIDAY.service` → `09:37:24 Started server process [100296]`. **Restart-cleanly: proven — 7 s to restart, serving again 15 s later.** (Two further restarts at 08:16:11 and 08:16:36 UTC are also in the journal, after the 08:07 kill; their trigger is not established from the journal lines — recorded, not explained.)

**Load-shed: not a guard behaviour.** The guard only posts notifications (warning / critical / recovered); it sheds no load and takes no mitigation. Memory can spike from ~86% past the 200 MB cap in seconds, faster than any notification-driven response. The underlying volatility is the remaining defect (FRD-064, queue position 3). This receipt therefore proves **trip + restart-cleanly**, and records plainly that **kill-prevention is not proven** — the acceptance's parenthetical is met in part (restarts cleanly), not in whole (no load-shed exists to prove).

## Voice sessions

No voice-session drop is recorded in `friday.log` around the 09:37 kill — zero `livekit`/`voice session` lines 09:30–09:45 UTC. LiveKit token requests bracket the kill (08:56:16 UTC `room=friday-frd005-calmcheck`, 09:55:14 UTC `room=calmcheck`, both 200). Whether a voice session was in flight at 09:37:02 is **not established** from the logs available; if one was, it was interrupted for the ~15 s restart window. The kill itself is filed here as the receipt — no drop is hidden, none is confirmed.

## Five states

- implemented: YES (FRD-043 guard merged via #2064, deployed live)
- tested: YES (this live receipt: 94 guard lines today, 26 criticals incl. two 100% trips with recovery; 09:37 kill + 7 s clean restart)
- merged: NO (this evidence PR open; coordinator/peer merges)
- deployed: YES (merged guard live on FRIDAY-Server since the 06:44 UTC restart; checkout on main 06ff9ee6)
- production-verified: YES for trip + restart-cleanly (this receipt); kill-prevention NOT verified — the guard warns but cannot stop a seconds-fast spike (FRD-064 owns the volatility)

— Muse 13
