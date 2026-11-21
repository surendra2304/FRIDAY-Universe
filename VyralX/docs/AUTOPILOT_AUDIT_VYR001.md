# VyralX daemon/autopilot audit — TASK-VYR-001 (2026-11-22)

Author: Muse 9. Scope: MASTER_PLAN §6, pool 2 item 5. Base: main
972ac278. All timings below are bounds read from the code, not measured
live runs — no supervised cycle was run for this audit, and no live
timing was invented. Where a bound is "unbounded", that is the finding.

## 1. What actually runs on the fleet

There is no single "VyralX daemon". Four drivers exist, and only one is
wired to systemd:

| Driver | Entry | Trigger | Uploads? |
|---|---|---|---|
| `scripts/autonomous_loop.py` | `deploy/VyralX-Daemon.service` — `ExecStart=... python scripts/autonomous_loop.py --interval-hours 6.0 --batch-size 1`, `Restart=always`, `RestartSec=30`, `TimeoutStopSec=15`, `MemoryMax=350M` | systemd, self-loops every 6h | Private drafts only (`render_and_draft_video`) |
| `scripts/run_viral_autopilot.py` | manual / timer fire (no `.timer` unit in `deploy/`) | one-shot, or `--loop` on `autonomous_run_interval_minutes` | Queued publish jobs, drained by the normal worker (unlisted) |
| `scripts/run_autopilot.py` | manual | one-shot, or `--loop` | Queues one project, drains render/publish queue |
| `app/services/autonomous_daemon.py` | nothing invokes `run_daemon()` from the repo or the unit file | — (legacy) | Direct `upload_video` (private) |

The 2026-11-21 VYR-034 watch found the systemd unit already running:
`VyralX-Daemon.service` enabled + active on Server 2 since 21:29:58 IST
(loop PID 122836, `--interval-hours 6.0`, idle) while the coordinator's
standing order was "loop stays OFF" (board TASK-VYR-034 evidence,
flag 2026-11-21 22:00 IST). That is the incident this budget answers:
a daemon that restarts itself (`Restart=always`) and loops on its own
clock must have a per-cycle bound, or a slow cycle silently eats the
next interval and the operator cannot tell from the outside whether the
loop is idle, working, or stuck.

## 2. Per-cycle work — `run_viral_autopilot.py` (the audited driver)

One cycle (`run_cycle`) is, in order:

1. **YPP snapshot** (`_snapshot_ypp`): one channel-stats snapshot for
   the YPP tracker. Fast, best-effort, failures swallowed — not a
   wall-clock risk.
2. **Discovery** (`produce_one` → `discover_candidates_api`, fallback
   `discover_candidates` via yt-dlp): the API path answers in seconds;
   the yt-dlp fallback walks the Shorts tabs of five creators plus the
   recommendation graph and is subject to per-channel JS challenge
   solves — slow and with no timeout of its own.
3. **Auditions** (up to `--max-candidates`, default 10): each candidate
   runs `produce_viral_short` — download + Whisper audio audit + render
   (+ TTS for silent clips) + rights/attribution record. There is no
   timeout or deadline parameter on `produce_viral_short`
   (`VyralX/app/services/viral_remix.py:1789`); one hung download,
   Whisper pass, or render stalls the whole cycle.
4. **Publish drain** (`drain_publish_queue`, `--timeout` default 1800s):
   loops `app.worker.run_once()` until the queue stays idle for 3
   polls. The loop itself is bounded by the timeout, but a single
   `run_once()` job (render or upload) is unbounded
   (`VyralX/app/worker.py:851`, no timeout).
5. **Report**: last 5 publish jobs logged. Trivial.

## 3. Wall-clock breakdown (bounds, not measurements)

| Step | Bound before this task | Bound after this task |
|---|---|---|
| YPP snapshot | ~seconds, swallowed errors | unchanged |
| Discovery (API) | seconds | unchanged |
| Discovery (yt-dlp fallback) | unbounded | unchanged (see §5) |
| One audition (`produce_viral_short`) | unbounded | unbounded *while in flight*; no new audition starts past the deadline |
| Audition loop (≤10 candidates) | unbounded (10 × unbounded) | stops at the deadline: `CYCLE_BUDGET_EXCEEDED` |
| Publish drain | 1800s loop bound, per-job unbounded | `min(1800s, remaining budget)`; no new job starts past the deadline |
| **Whole cycle** | **unbounded** | **budgeted** (`viral_autopilot_cycle_budget_seconds`, default 5400s) |

The 5400s default matches the existing `viral_loop_cycle_budget_seconds`
bound on the sibling `viral_loop` driver, which enforces its budget the
same way (check `time.monotonic()` before each attempt,
`VyralX/app/services/viral_loop.py:275` and the `time_budget` stop).

## 4. Overrun failure modes

1. **Audition pile-up (the fixed one).** Ten candidates × (download +
   Whisper + render) with no bound. On the 2-vCPU host a cycle could run
   past the 6h systemd interval; the next fire then exits on the
   single-instance lock (127.0.0.1:8765) and the operator sees only a
   "already running" log line. Fixed: the cycle stops auditioning at the
   deadline and reports `CYCLE_BUDGET_EXCEEDED` with the attempts made.
2. **Single blocking call still overruns.** A hung download/Whisper/
   render inside one `produce_viral_short`, or one long `run_once()` job
   inside the drain, has no deadline of its own. The budget guarantees
   the cycle *starts nothing new* past the deadline; it does not
   pre-empt work already running. Killing mid-render would need a
   worker-side timeout, which is out of scope here and is recorded as
   residual risk (§5).
3. **yt-dlp discovery fallback.** If the Data API finds nothing, discovery
   falls back to yt-dlp graph walking before any audition — also
   unbounded and outside the budget check, which sits at the audition
   loop. A stuck fallback delays the first audition, not the cycle's
   termination once auditions begin.
4. **Loop-mode drift.** In `--loop` mode an overrun cycle delays the next
   cycle by the overrun (sleep is after the cycle, not on a fixed
   schedule). The budget caps the drift at ~budget + one in-flight call.
5. **systemd restart masking.** `Restart=always` + `TimeoutStopSec=15`
   means a killed daemon comes back in 30s and resumes the 6h loop from
   scratch — a cycle killed for overrunning is indistinguishable in the
   journal from a clean restart unless the budget-exceeded log line is
   present. The new `CYCLE_BUDGET_EXCEEDED` status and the
   `seconds`/`budget_seconds` fields on the cycle result are the
   observable signal.
6. **`autonomous_daemon.py` (legacy, not wired to the unit).** Its
   `run_daemon` loop has no budget either: `execute_production_cycle`
   runs edge-tts → ffmpeg sound design → `render_montage` → thumbnail →
   direct YouTube upload, all unbounded, with a 30-minute poll interval
   that starts counting only after the cycle returns. It also copies
   every render to a Windows-style relative path
   (`USER_HOME\.gemini\antigravity\brain\...`), which on Linux is a
   single directory name with backslashes — `shutil.copy2` there fails
   unless that directory happens to exist, aborting the cycle after the
   render and before the publish step. Nothing invokes this module from
   the service file, so it is a latent defect, not a live one; it is
   recorded here, not fixed in this task.
7. **`autonomous_loop.py` (the live systemd driver).** Also unbounded:
   `run_autonomous_cycle` renders master candidates with no deadline,
   and `run_continuous_daemon` sleeps a fixed interval after each cycle.
   This task's budget lives in `run_viral_autopilot.py` only, per the
   assignment; applying the same bound to `autonomous_loop.py` is the
   natural follow-up.

## 5. What the budget does and does not do

Does: one setting (`viral_autopilot_cycle_budget_seconds`, default
5400s, `--cycle-budget` CLI override) bounds a whole
`run_viral_autopilot.py` cycle; the deadline is computed once in
`run_cycle` and handed to `produce_one` (checked before every
audition) and to `drain_publish_queue` (effective timeout
`min(--timeout, remaining)`); the cycle result carries `seconds` and
`budget_seconds`, and a budget stop reports `CYCLE_BUDGET_EXCEEDED`.

Does not: pre-empt a running audition or worker job; bound yt-dlp
discovery; bound `autonomous_loop.py` or `autonomous_daemon.py`;
change the loop-OFF / uploader-paused guardrails — the loop stays OFF
and the uploader stays paused until the coordinator orders a
supervised cycle. No unsupervised cycle is enabled by this task.

Residual risks (not fixed here): per-call timeouts inside
`produce_viral_short` / `run_once()`; a budget for
`autonomous_loop.py` (the actual systemd driver); the
`autonomous_daemon.py` brain-dir copy path (§4.6).

## 6. Verification

- New tests `VyralX/tests/test_vyr001_autopilot_cycle_budget.py` (6
  tests): budget stops auditions mid-pool; budget already exceeded
  attempts nothing; no deadline preserves the old behaviour; drain
  capped by remaining budget; `run_cycle` wires the deadline and
  reports elapsed/budget; budget-exceeded cycle skips the drain.
  Fake `time.monotonic()` clock — a 60s budget is the smallest the
  setting allows. Local run: 6/6 pass; the same file fails 5/6 on the
  pre-change driver (the back-compat test passes on both).
- Neighbouring suites `test_viral_loop.py` +
  `test_viral_loop_audition.py` unaffected: 25/25 pass together.
- Ruff (`E4,E7,E9,F`, line-length 100): clean on all touched files.
- The contracts workflow list gains the new test file so CI collects
  it (the DAEMON-002 follow-up lesson: the list is explicit).
