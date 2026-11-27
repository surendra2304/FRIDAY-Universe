# TASK-VOI-045 — Checkpoint 3 (token endpoint resolved; fresh calm check; firing held on FRD-064 collision + slow health)

Worker: Muse TP10. This checkpoint: 2026-11-27 ~14:23 IST self-check run.
Branch `musetp10/task-voi-045` @ `a51d1246` (checkpoint 2), ahead 2 / behind 62
vs main `7175b9b0`, docs-only, no PR yet.

## 1. Token endpoint — RESOLVED

- Correct route (first-hand, server 3): `GET http://127.0.0.1:10000/api/livekit/token?room=<room>&identity=muse-frd005`
  (`FRIDAY/voice_acceptance/participant.py:42` TOKEN_URL; `get_token` GET with
  room+identity params).
- The 13:24 IST 404 was my probe hitting `/token` on :10000 — wrong path, not a
  service fault. Calm-check token read at 08:56 UTC: **HTTP 200 in 1.24 s**,
  keys `[agent_dispatch, identity, room, server_url, token]`, token present
  (value not recorded). Run-27 precedent endpoint confirmed.

## 2. Fresh calm check — FRIDAY-Server, 2026-11-27 08:55–08:56 UTC (read-only)

- Load **0.00 / 0.05 / 0.07** — calm. FRIDAY + FRIDAY-Voice + Inference active.
- FRIDAY.service: PID 98045, active since **08:16:37 UTC**, NRestarts 0.
  MemoryCurrent 3 samples (08:55:53/58, 08:56:03): 38,289,408 / 38,199,296 /
  38,199,296 = **18.2% of 209,715,200 cap** — stable, well under the WATCH210-CORR
  85% gate. cgroup memory.events: oom_kill 0 (max 2673 historical).
- FRIDAY-Voice: PID 87938 since 06:03:19 UTC. Voice status file: state
  `closed`, "owner left; session closed", room `friday-frd005-20261127-074037`
  (VOI-030's run), updated 07:52:09 UTC. No participant process. Voice journal
  since 07:52: key-keeper refresh only, no jobs.
- **/health 200 in 4.18 s; /ready 200 in 3.07 s** — both 200 but ~4x slower than
  the 12:23 IST calm check (1.06 s / 1.06 s) and run 27 (1.52 s / 0.88 s).
- Checkout `06ff9ee6` (deployed build unchanged since checkpoint 2; dirty
  `FRIDAY/ui/out/` only). Ports 8001 + 10000 LISTEN.

## 3. Why firing is HELD this run (collision + degraded calm bar)

1. **FRIDAY.service is being actively restarted by live FRD-064 work.**
   auth.log (first-hand): deliberate `sudo systemctl restart FRIDAY.service` at
   07:51:14, 08:10:16, **08:16:10 and 08:16:36 UTC** (twice in 26 s). Muse 1
   claimed TASK-FRD-064 (OOM kills chat turns) 13:40 IST (hub 7213239303) and
   filed the restart-actor note (7213275166). A mid-run restart would kill the
   acceptance call (infra failure, exit 2) and burn the exactly-once probes.
2. **Calm bar not clean:** /health 4.18 s is not the steady state run 27
   measured. Voice is judged on SPEED first; firing into a slow, freshly
   restarted FRIDAY measures the incident, not the build.
3. VOI-030 collision is cleared (Muse 1 COMPLETE, PR #2100, hub 7213226573);
   the open collision is FRD-064 sequencing, which is Muse's call.

Ask (hub #2045, this run): Muse to sequence run 28 vs Muse 1's FRD-064 live
work, or clear firing once FRIDAY restarts stop and /health returns to ~1 s.
Next run re-checks (memory 3 samples, /health timing, restart log, FRD-064
state) and fires each probe exactly once on a clean window.

## 4. Paired verification filed this run

PR #2085 (Muse 12, TASK-MEM-038 checkpoint 1) → Muse TP10 verdict **VERIFIED**
(PR comment 7214073779, 14:25 IST, inside the ~14:45 WATCH211 §4 deadline):
head `3e17e481`, mergeable clean, 1 file +89/-0, CI 9 runs 0 fail; live
read-back on Oracle Server 1 — memory `eba43f3c-...` scope UNIVERSAL, lifecycle
active, marker search 1 hit. Checkpoint-1 scope.

Five states (VOI-045): implemented NO / tested NO / merged NO / deployed NO /
production-verified NO. Usage 12% free weekly (reset Dec 2, 6:34 PM IST).

— Muse TP10
