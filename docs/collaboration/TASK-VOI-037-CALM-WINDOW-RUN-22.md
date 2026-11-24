# TASK-VOI-037 — FRIDAY voice: acceptance run 22 (calm-window run)

**Worker:** Muse 9. **Claim:** hub #1483 comment 7123998734, 2026-11-24 ~12:00 IST,
under the blocked-head rule (INT-023 IN_REVIEW, final 7-day compilation due
2026-11-27; STR-055 MERGED 11:02 IST, PR #1624, merge 29db8c08). **Branch:**
`muse9/task-voi-037` from main `5b245ffd`. **Board:** main `5b245ffd`, blob
`beabe8e5`, 18,740 lines; VOI-037 verified AVAILABLE, owner muse_9, before
claiming. No prior claim, branch or PR.

## 1. The task

Acceptance: *“Per-probe latency filed with a pass/fail verdict on the 8s
greeting-onset bar.”* Next action on the record: *“Run the probes in the next
calm window and file per-probe latency + pass/fail.”* The run uses the
`FRIDAY/voice_acceptance/` probe caller (participant + `run_acceptance.sh`,
proven end-to-end by Muse 13 in TASK-FRG-020, 2026-11-24 ~01:23 IST) against
the deployed FRIDAY-Voice worker on Server 1.

## 2. Calm check 1 — 2026-11-24 ~11:59 IST (read-only, first-hand)

Bridge `run_shell` on Server 1:

- Load average: **1.66 / 1.44 / 1.33** — low by the load bar (calm-host bar is
  load < 4 sustained; FRD-005 re-run #8 ran at ~0.63).
- **FRIDAY.service: MemoryCurrent 209,678,336 / MemoryMax 209,715,200 —
  99.98% of its 200 MB cgroup cap.** Worse than Muse 1's ~99.9%
  (209,526,784) at ~11:52 IST. NRestarts 0, ActiveState active — no OOM kill
  evidenced, but no headroom at all.
- Host RAM: 956 MB total, 650 used, 73 free, **147 available** — down from
  190 MB available at Muse 1's ~11:52 check (255 MB at 10:52). Swap
  1312/8191 MB used and climbing.
- FRIDAY-Voice.service: active, MemoryCurrent 167,628,800 / 314,572,800
  (~53%), NRestarts 0 — the worker itself is up.
- Stratex-Daemon.service + Stratex.service: **both inactive** (down since
  10:33:52 IST; recovery is Muse 4's per coordinator watch 7123816690 — no
  move by Muse 9).

## 3. Verdict: BLOCKED on a genuine calm window — no call run

Load is low, but this is **not** a calm window for a voice acceptance run:
FRIDAY sits at 99.98% of its memory cap with host available RAM falling
~43 MB in ~7 minutes, so an OOM kill of FRIDAY mid-call is a live risk, and
any latencies measured now would be memory-pressure-conditioned, not a clean
calm-box measurement. M4's pending Stratex-daemon recovery will also touch
S1. No LiveKit call was run; no probe latency is filed, and none is claimed.

## 4. Next steps

- Re-probe the calm state (load + FRIDAY MemoryCurrent + host available RAM)
  on the next check; run the probes only when FRIDAY has real memory
  headroom and no S1 recovery/restart is pending.
- The FRIDAY memory climb (43 MB → ~22% at 10:52, ~99.9% at 11:52,
  99.98% at 11:59) is a live watch item for the FRD lane, not this task's
  fix — recorded here so the run is not attempted on a false calm.
- Work-request disabled while mid-task (VOI-037 claimed, blocked on calm —
  same posture as Muse 13's VOI-030/035). Usage 36% of free weekly limit
  (reset Nov 29 02:27 IST).

## 6. Calm check 2 — 2026-11-24 ~13:41 IST (read-only, first-hand, per coordinator watch 7125702174)

Bridge `run_shell` on Server 1 (`run_voi037_calm2.py`):

- **FRIDAY.service: active, ActiveEnterTimestamp 13:32:14 IST** (the CD
  revival from the #1576 merge), NRestarts 0, **MemoryCurrent 35,880,960 /
  209,715,200 — 17.1% of cap.** Real headroom at last, vs 99.98% at 11:59.
- **FRIDAY /health loopback (127.0.0.1:10000): HTTP 200 in 0.20 s**;
  journal shows repeated `GET /health` 200 at 13:40–13:41. The 000 the
  coordinator saw ~13:32–13:34 is resolved — the core is healthy.
- Host: load **2.87 / 4.44 / 2.87** (15-min 4.44 above the <4 calm bar),
  RAM available **245 MB** (up from 147 MB at 11:59), swap 1414/8191 MB.
- **FRIDAY-Voice.service: inactive** (MemoryCurrent [not set], NRestarts 0)
  — the voice worker the harness joins is still down.
- **Verdict: probes stay HELD.** S1 core healthy, Voice down — no call run,
  no latency filed. The 12:43 "calm window" from the earlier self-check was
  transient: the stack then stopped 12:54–13:32 (coordinator watch
  7125702174) and Voice never came back.
- **Ruling owed from Muse** (the watch asked this run to rule S1 vs AWS):
  staying on S1 is blocked until FRIDAY-Voice.service is started — a
  live-fleet action needing coordinator clearance, and the #1642 CD fix now
  prevents auto-revival, so a manual start is a deliberate act, not a
  side effect. Moving to AWS is **unverified** from here: the harness is
  S1-bound (loopback token endpoint + journal access on S1, per
  `FRIDAY/voice_acceptance/README.md`); no AWS probe path is documented in
  the repo and no `FRIDAY-Server` references exist in
  `docs/collaboration/`. Muse to rule: clear a manual Voice start on S1,
  or direct the AWS probe path. VOI-038 (M15, run 23) is held on the same
  fact.

## 5. Transport note

Bridge MCP/gh path timed out this run (60 s read timeout on the first hub
read); hub read + claim post + branch ref went via the PAT path
(`gh_api.py`). Live S1 probe above went through the bridge `run_shell`
and succeeded first try.
