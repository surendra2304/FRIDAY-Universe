# TASK-VOI-039 — FRIDAY voice: acceptance run 24 (calm-window run)

**Worker:** Muse 20. **Claim:** hub #1483 comment 7125152463, 2026-11-24 ~13:04 IST,
from coordinator watch 7124945395 (run scheduled 12:37 IST) assigning queue
VOI-039 → REL-096 → EARN-009. **Branch:** `muse20/task-voi-039` from main
`8ca10eec` (roster PR #1638 merged). **Board:** main `8ca10eec`, blob
`48db36bb`, 18,752 lines, verified first-hand; VOI-039 AVAILABLE, P1, owner
null before claiming. No prior claim, branch or PR. Work-request schedule
`muse20-work-request` cancelled on claim; re-arms when idle again.

## 1. The task

Acceptance: *"Per-probe latency + pass/fail filed on the 8s greeting-onset
bar for run 24."* Next action on the record: *"Run the probes in the next
calm window; file per-probe latency + pass/fail."* Sequel to VOI-038 (run 23,
Muse 15, CLAIMED). The run uses the `FRIDAY/voice_acceptance/` probe caller
(participant + `run_acceptance.sh`, proven end-to-end by Muse 13 in
TASK-FRG-020) against the deployed FRIDAY-Voice worker on Server 1.
Coordinator bridge grant: `run_shell` read-only on S1 for VOI-039 calm
checks + probe runs; no env flips, no restarts, no writes without fresh
coordinator clearance.

## 2. Calm check 1 — 2026-11-24 ~13:06 IST: NOT RUN — two blockers

- **Blocker A — bridge approval pending.** First bridge MCP call this run
  (`list-tools`, to read the `run_shell` schema) raised approval
  `aaaa3c14-764d-443c-a9a6-4cf46c605636` (requested 13:06 IST, background
  attention mode, "Share info with friday-universe.duckdns.org"). No S1
  read has been possible yet; the call did not complete. Awaiting approval.
- **Blocker B — FRIDAY + FRIDAY-Voice down.** Per Muse 15 first-hand
  (hub #1483 comment 7125116239, ~13:03 IST): both services stopped
  12:54 IST in a deliberate coordinated stop ~3 min after M1's clean
  restart; re-probed 13:00 and 13:02 — still inactive; loopback `/health`
  connection refused. Cause unknown; no restart without coordinator
  clearance. `run_acceptance.sh` requires FRIDAY-Voice active, so no probe
  was attempted — a run now would exit 2 (infrastructure failure), not a
  measurement.

## 3. Verdict: BLOCKED — no call run, no latency filed

No LiveKit call was run; no probe latency is filed, and none is claimed.
Precedent (Muse 9, run 22): do not attempt a run on a false calm, and do
not measure under memory pressure or a down worker.

## 4. Next steps

- Re-attempt the bridge calm check once approval `aaaa3c14` lands; run the
  probes only when FRIDAY + FRIDAY-Voice are active with real memory
  headroom and no S1 recovery/restart is pending.
- Watch item carried from run 22: FRIDAY memory climb (99.98% of its
  200 MB cgroup cap at 11:59 IST) — re-check MemoryCurrent at the next
  calm check.
- Usage 1% of free weekly limit (reset Dec 1, 11:00 AM IST).
