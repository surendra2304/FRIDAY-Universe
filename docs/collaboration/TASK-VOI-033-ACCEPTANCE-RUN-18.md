# TASK-VOI-033 — FRIDAY voice: acceptance run 18 (calm-window run)

**Worker:** Muse 1. **Claim:** hub #1483 comment 7166876669, 2026-11-25 ~20:58 IST,
on coordinator assignment.
**Branch:** `muse1/task-voi-033-acceptance-run-18` from main `0eeaa43a`.
**Board:** main `0eeaa43a`, VOI-033 verified AVAILABLE, owner muse_1, branch null,
pr null, P1, before claiming. Queue: VOI-033 → VOI-040. VOI-043 MERGED flip owed
from the P0 run rides in this PR (see §9).
**Acceptance host:** FRIDAY-Server (15.134.130.145), per coordinator ruling
(watch 7126818611).
**Live build:** `fFKg6fXVVhWz4qvLQD0Pi` (FRD-042 build, confirmed in the served page).

## 1. The task

Acceptance: *"Per-probe latency filed with a pass/fail verdict on the 8s greeting-onset bar."*
Sequel to VOI-035 (run 20) and VOI-036 (run 21), both Muse 1, both MERGED
(PR #1790, merge `2c6f913`; PR #1802, merge `c554c54f`). The run uses the
`FRIDAY/voice_acceptance/` probe caller (participant +
`run_acceptance.sh`, proven end-to-end by Muse 13 in TASK-FRG-020) against the
deployed FRIDAY-Voice worker on FRIDAY-Server. Route: bridge `run_shell` on
server 2, SSH to FRIDAY-Server.

## 2. Stop-order check

- Owner stop order ~16:42 IST Nov 24 ("Don't move anything now") froze ALL server
  moves; partial lift 17:26 IST covers ONLY (1) key architecture, (2) bridge work,
  (3) the Inference move.
- The voice-probe leg is NOT a server move: coordinator ruling 7126818611
  (Nov 24 ~13:52 IST): "RULING — acceptance host is FRIDAY-Server, not S1...
  VOI-030/035 hold LIFTS: M13, probe in the next calm window against
  FRIDAY-Server." Runs 19 (VOI-034), 20 (VOI-035) and 21 (VOI-036) executed the
  identical leg and MERGED (PR #1732, merge `4bed6107`; PR #1790, merge `2c6f913`;
  PR #1802, merge `c554c54f`).
- The VOI-033 claim (hub #1483 comment 7166876669, ~20:58 IST Nov 25) is a fresh
  coordinator direction, post-dating the stop order. No newer stop-order change
  is known to this run.
- The VOI-043 P0 fix merged 20:39 IST Nov 25 (PR #1856, merge `34e1aa68`) — the
  queue head is now VOI-033.

**Verdict: live leg callable as a read-only probe against FRIDAY-Server.** No
server moves, no installs, no restores, no deploys attempted.

## 3. Calm check — 2026-11-25 ~21:02 IST (FRIDAY-Server, read-only, first-hand)

- Load average: **0.39 / 0.39 / 0.27** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, **1044 MB available**; swap 98/8191 MB.
- **FRIDAY.service: active, NRestarts 7** (was 2 in run 21 — five restarts since,
  ActiveEnterTimestamp 2026-11-25 13:59:44 UTC; reason unknown, healthy now).
  **MemoryCurrent 66,162,688 / 209,715,200 — 31.6% of its 200 MB cgroup cap.**
  Real headroom.
- **FRIDAY-Voice.service: active since 07:21:18 UTC Nov 24**, NRestarts 0,
  MemoryCurrent 259,452,928. **Inference.service: active.**
- **/health 200 in 0.73 s**; **/ready 200 in 0.73 s; token endpoint
  `http://127.0.0.1:10000/api/livekit/token` 200 in 0.02 s.**
- Voice status file: state `ready`, room `friday-frd005-20261125-152842`,
  updated 15:28:46 UTC — a run had JUST launched in that room (see §4).

**Verdict: calm window confirmed — but a run was already in progress (see §4),
so this run waited.**

Preflight (same probe): all 7 `FRIDAY/voice_acceptance/` files byte-identical to
main `0eeaa43a` (md5 MATCH: README.md, battery.json, make_utterances.py,
participant.py, run_acceptance.sh, score.py, score_check.py); fleet venv imports
livekit/httpx/edge_tts and PyAV OK; served page contains build
`fFKg6fXVVhWz4qvLQD0Pi`; journal shows the voice worker alive (key keeper
refreshing the Gemini key).

## 4. Sequencing — VOI-039 run 24 was live when this run started

- At calm check 1 (~21:02 IST) another acceptance run was already in progress:
  room `friday-frd005-20261125-152842`, launched 15:28:42 UTC (20:58:42 IST), launch log `/tmp/frd005/voi039-launch.log`,
  participant pid 46392 live. That is VOI-039 run 24, launched by another worker
  ~27 s after this task arrived.
- This run did NOT launch alongside it: two concurrent participants would share
  the single FRIDAY-Voice worker and contaminate both runs' latency evidence.
- Poll at 15:39 UTC: VOI-039 in its memory_recall turn (5 of 7). Poll at
  15:42 UTC: finished 15:40 UTC, no participant running. Its results (read
  first-hand from its `results.md`, NOT this run's evidence): greeting 0.52 s,
  all 7 turns inside silence limits, scorer FAIL on content (same attribution
  shape as runs 20/21).
- Calm check 2 (~21:13 IST): load **0.17 / 0.39 / 0.37**, RAM **1096 MB
  available**, FRIDAY NRestarts 7 (unchanged), FRIDAY-Voice NRestarts 0, no
  participant running, status file state `closed`, room
  `friday-frd005-20261125-152842`, updated 15:40:16 UTC. **Calm window
  re-confirmed. Probes run.**

## 5. The run — room `friday-frd005-20261125-154327`

- **Launched 15:43:27 UTC (21:13:27 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi033-launch.log`), so bridge
  transport drops cannot kill it. The launching bridge call hit the 120 s local
  timeout while the remote nohup kept running; verified first-hand afterwards
  that the launch DID apply (log exists, participant running) — no duplicate
  launch. Call 15:43:28–15:54:59 UTC (~11.5 min).
- Agent joined in <1 s (`agent-AJ_BCUYjraAnTNJ`, 15:43:30 UTC). Provider
  `gemini-realtime:gemini-3.8-live` — PASS, no contamination lines.
- Host stayed calm through the run (load 0.75 at 15:54 UTC, 0.06 at 15:57 UTC).
- Greeting onset decomposition (TASK-VOI-026, journal 15:43:30 UTC):
  job-to-connect 0.11 s, connect-to-key 0.00 s, key-to-participant 0.00 s,
  participant-to-gate 0.30 s, gate LISTENING after 0.00 s,
  **connect-to-first-audio 0.30 s** (fixed-line greeting).
- Run artefacts on FRIDAY-Server, `/tmp/frd005/runs/20261125-154327/`: timeline
  (3.9 KB), `journal.txt` (50 KB), `results.json` (4.7 KB), `results.md`
  (1.6 KB), `status.json`, utterances manifest, 66.6 MB agent WAV. Launcher log
  `/tmp/frd005/voi033-launch.log`.

## 6. Per-probe latency — the acceptance table

| # | Turn | Silence gap (s) | Limit (s) | Latency | Content | Verdict |
|---|------|-----------------|-----------|---------|---------|---------|
| 0 | greeting | 0.70 | 8.0 | PASS | PASS | PASS |
| 1 | delegation_stratex | −7.59 | 12.0 | PASS | PASS | PASS |
| 2 | context_followup | −2.50 | 4.0 | PASS | UNVERIFIED | UNVERIFIED |
| 3 | clock_tokyo | −1.95 | 4.0 | PASS | FAIL * | FAIL * |
| 4 | memory_remember | −3.95 | 6.0 | PASS | PASS | PASS |
| 5 | memory_recall | −1.54 | 5.0 | PASS | FAIL * | FAIL * |
| 6 | goodbye | −2.72 | 4.0 | PASS | PASS | PASS |

\* Scorer verdict; first-hand journal read (§7) shows the correct answer WAS given —
attribution artefact of the order-based fallback, not a genuine gap.

Latency (silence gap) is inside its limit on **all 7 turns**. Negative gaps mean
FRIDAY began answering before the prompt audio finished — the same
overlapping-answer shape as runs 19/20/21/24, caused by the ~240 s greeting burst
(see §8).

**Acceptance verdict: PASS — greeting onset 0.70 s against the 8 s bar.**
Every turn's latency is inside its silence limit. This is the task's
acceptance criterion, and it is met.

## 7. Overall scorer: FAIL — content, not latency; all of it attribution

Scorer output (`results.md`, battery v1): overall **FAIL** (scorer exit 1).
Reasons, verbatim: context_followup content UNVERIFIED (followup_count=None
delegation_count=82); clock_tokyo content FAIL (no time in answer);
memory_recall content FAIL ('teal' missing from answer).

What the evidence actually shows (first-hand from `results.json` + `journal.txt`):

- **Alignment is the order-based fallback (9 user finals for 6 turns; 2 extra
  items folded into greeting).** The STT "heard" text is shifted one turn
  throughout: clock_tokyo's heard text is the followup prompt,
  memory_recall's heard text is the clock prompt, goodbye's heard text is
  "My favorite color is teal." (the recall prompt). The journal holds **10
  unique assistant `conversation_item_added` entries** (20 `role=assistant`
  lines counting the JSON-duplicate format, 18 `role=user`, 40
  `conversation_item_added` total). The scorer cannot attribute content
  reliably under this shape — the same known harness weakness documented in
  runs 19, 20, 21 and 24.
- **All three scorer content failures are attribution artefacts, verified
  first-hand in the journal:**
  - **Clock:** FRIDAY answered "It is 12:50 AM in Tokyo, Japan." at 15:50:48
    UTC — correct (15:50 UTC = 00:50 JST). The scorer attributed that answer
    to the context_followup turn.
  - **Memory recall:** FRIDAY answered "Your favorite color is teal." at
    15:52:59 UTC — **the Memora read path IS verified by this run** (third
    run in a row, after run 20's 06:50:26 UTC and run 21's 08:13:55 UTC
    recalls). The scorer attributed that answer to the memory_remember turn.
  - **Context followup:** FRIDAY answered "There were 82 closed trades in the
    ledger." at 15:49:45 UTC — the followup figure IS in the journal; the
    scorer reports followup_count=None only because its attribution cannot
    match it.
  - **Memory remember** is a genuine PASS, and stronger than the scorer's
    "reply present": "Got it, Boss — locked in: your favorite color is teal.
    That's mine to keep now." at 15:51:59 UTC. (The scorer's extracted answer
    "Understood. I am here whenever" is a truncated fragment just before the
    goodbye prompt, not a remember-turn reply; the attribution shift again.)
  - **Goodbye** is a genuine PASS: "Goodbye, Boss. Have a great day!" at
    15:53:59 UTC.
- **Delegation is a genuine PASS (figures + Stratex terms present), the second
  clean delegation PASS in a row after run 21.** FRIDAY gave real Stratex
  figures — "Your Stratex balance is 10,438.67, with 30 open positions and
  82 closed trades in the ledger." (15:47:53 UTC) — plus a full portfolio
  snapshot at 15:49:37 UTC (balance 10,438.67, 30 open, 82 closed,
  unrealised P&L +143.60, ledger net P&L +117.95, win rate 18%). Run 20's
  genuine delegation gap stays closed.

## 8. Greeting anomaly (recorded, not scored)

FRIDAY's greeting speech ran the same ~240 s burst shape as runs 19/20/21/24:
agent joined 15:43:30 UTC and the first substantive assistant journal text is
the Stratex balance at 15:47:53 UTC (~4.4 min later); the burst's content is
only in the 66.6 MB agent WAV and is UNVERIFIED from the journal. That is why
every later turn's gap is negative: the agent was already speaking when each
prompt arrived.

## 9. States

- implemented YES (run executed on the live FRD-042 build, first-hand) /
  tested YES (scorer ran; latency 7/7 inside limits, greeting 0.70 s vs 8 s bar) /
  merged NO (work PR open, merge is Muse's — workers never merge own PRs) /
  deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window run; the latency bar is met; the
  clock/recall/followup content legs are verified by first-hand journal read
  despite the scorer's attribution; the delegation figures leg is verified too —
  second clean PASS in a row).
- **Voice status is NOT WORKING until the owner re-tests and accepts** (P0,
  owner live test 2026-11-25 15:54 IST). This run is calm-window probes only;
  the live leg (production deploy + owner re-test) is BLOCKED on Muse's hub
  clearance.
- Usage: 74% of free weekly limit (per task brief; reset Nov 28 21:57 IST).
- No restarts, no deployments, no live writes in this run. No approval blocks.
- Bridge transport was flaky on the launch call (the launching exec hit the
  120 s local timeout while the remote nohup kept running; verified first-hand
  afterwards that the launch DID apply — log exists, participant running — no
  duplicate launch). The run itself was detached on FRIDAY-Server and unaffected.

## 10. Board flips riding in this PR

- **TASK-VOI-033 AVAILABLE → IN_REVIEW** (owner muse_1, branch
  `muse1/task-voi-033-acceptance-run-18`, this work PR) — this task.
- **TASK-VOI-043 IN_REVIEW → MERGED** (work PR #1856, merge `34e1aa68`,
  merged 2026-11-25 20:39:14 IST by surendra2304, CI 10/10 green on head
  `d6eb0191`, verified first-hand via the PR API) — owed: the flip was not in
  PR #1856.
- No code or test files in this PR (evidence doc + board only), so the FUT-030
  CI-coverage lesson does not apply — there are no new tests to list in any
  workflow; CI green here means the board YAML parses and the validators pass.

— Muse 1
