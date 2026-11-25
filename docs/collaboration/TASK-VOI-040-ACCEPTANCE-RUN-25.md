# TASK-VOI-040 — FRIDAY voice: acceptance run 25 (calm-window run)

**Worker:** Muse 1. **Claim:** hub #1483 comment 7169589169, 2026-11-25 ~23:00 IST,
on coordinator assignment.
**Branch:** `muse1/task-voi-040-acceptance-run-25` from main `2f77de04`
(rebased from `a759a031`; main moved via coordinator watch109 board PR #1876).
**Board:** main `2f77de04`, VOI-040 verified AVAILABLE, owner muse_1, branch null,
pr null, P1, before claiming. Queue: VOI-040 → IG-FRD-006-FIX-01 → EARN-028.
**Acceptance host:** FRIDAY-Server (15.134.130.145), per coordinator ruling
(watch 7126818611).
**Live build:** `fFKg6fXVVhWz4qvLQD0Pi` (FRD-042 build, confirmed in the served page).

## 1. The task

Acceptance: *"Per-probe latency filed with a pass/fail verdict on the 8s greeting-onset bar."*
Sequel to VOI-039 (run 24, Muse 15, MERGED PR #1868, merge `5188dff3`,
merged 2026-11-25 22:08:31 IST) and VOI-033 (run 18, Muse 1, MERGED PR #1870,
merge `da49f52e`). The run uses the `FRIDAY/voice_acceptance/` probe caller
(participant + `run_acceptance.sh`, proven end-to-end by Muse 13 in TASK-FRG-020)
against the deployed FRIDAY-Voice worker on FRIDAY-Server. Route: bridge
`run_shell` on server 2, SSH to FRIDAY-Server.

## 2. Stop-order check

- Owner stop order ~16:42 IST Nov 24 ("Don't move anything now") froze ALL server
  moves; partial lift 17:26 IST covers ONLY (1) key architecture, (2) bridge work,
  (3) the Inference move.
- The voice-probe leg is NOT a server move: coordinator ruling 7126818611
  (Nov 24 ~13:52 IST): "RULING — acceptance host is FRIDAY-Server, not S1...
  VOI-030/035 hold LIFTS: M13, probe in the next calm window against
  FRIDAY-Server." Runs 19 (VOI-034), 20 (VOI-035), 21 (VOI-036), 24 (VOI-039)
  and 18 (VOI-033) executed the identical leg and MERGED.
- The VOI-040 claim (hub #1483 comment 7169589169, ~23:00 IST Nov 25) is a fresh
  coordinator direction, post-dating the stop order. No newer stop-order change
  is known to this run.
- Precondition satisfied: VOI-039 (run 24) merged via PR #1868
  (`5188dff3`, merged 2026-11-25T16:38:31Z, verified first-hand via the PR API).

**Verdict: live leg callable as a read-only probe against FRIDAY-Server.** No
server moves, no installs, no restores, no deploys attempted.

## 3. Calm check — 2026-11-25 ~23:02 IST (FRIDAY-Server, read-only, first-hand)

- Load average: **0.08 / 0.16 / 0.12** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, **1092 MB available**; swap 118/8191 MB.
- **FRIDAY.service: active, NRestarts 8** (was 7 in run 18 — one restart since,
  ActiveEnterTimestamp 2026-11-25 16:25:34 UTC; reason unknown, healthy now).
  **MemoryCurrent 40,534,016 / 209,715,200 — 19.3% of its 200 MB cgroup cap.**
  Real headroom.
- **FRIDAY-Voice.service: active since 07:21:18 UTC Nov 24**, NRestarts 0,
  MemoryCurrent 266,223,616. **Inference.service: active.**
- **/health 200 in 1.69 s**; **/ready 200 in 0.80 s; token endpoint
  `http://127.0.0.1:10000/api/livekit/token` 200 in 1.54 s.**
- Voice status file: state `closed`, room `friday-frd005-20261125-154327`
  (run 18), updated 15:54:59 UTC. No participant process running.
- **Calm window confirmed; worker free; no run in progress — launched at once.**

Preflight (same probe): all 7 `FRIDAY/voice_acceptance/` files byte-identical to
main `2f77de04` (md5 MATCH: README.md, battery.json, make_utterances.py,
participant.py, run_acceptance.sh, score.py, score_check.py); fleet venv imports
livekit/httpx/edge_tts and PyAV OK; served page contains build
`fFKg6fXVVhWz4qvLQD0Pi`; journal shows the voice worker alive (key keeper
refreshing the Gemini key, 17:16:57 UTC).

## 4. The run — room `friday-frd005-20261125-173321`

- **Launched 17:33:21 UTC (23:03:21 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi040-launch.log`), so bridge
  transport drops cannot kill it. The launching bridge call hit the 120 s local
  timeout while the remote nohup kept running; verified first-hand afterwards
  that the launch DID apply (log exists, participant running) — no duplicate
  launch. Call 17:33:22–17:44:53 UTC (~11.5 min).
- Agent joined in <1 s (`agent-AJ_gwA3L3vzpVD4`, 17:33:24 UTC). Provider
  `gemini-realtime:gemini-3.8-live` — PASS, no contamination lines.
- Host stayed calm through the run (load 0.24 at 17:46 UTC).
- Greeting onset decomposition (TASK-VOI-026, journal 17:33:24 UTC):
  job-to-connect 0.12 s, connect-to-key 0.00 s, key-to-participant 0.00 s,
  participant-to-gate 0.30 s, gate LISTENING after 0.00 s,
  **connect-to-first-audio 0.30 s** (fixed-line greeting).
- Run artefacts on FRIDAY-Server, `/tmp/frd005/runs/20261125-173321/`: timeline
  (3.9 KB), `journal.txt` (56,280 B), `results.json` (4.6 KB), `results.md`
  (1.5 KB), `status.json`, utterances manifest, 66.6 MB agent WAV. Launcher log
  `/tmp/frd005/voi040-launch.log`.

## 5. Per-probe latency — the acceptance table

| # | Turn | Silence gap (s) | Limit (s) | Latency | Content | Verdict |
|---|------|-----------------|-----------|---------|---------|---------|
| 0 | greeting | 0.70 | 8.0 | PASS | PASS | PASS |
| 1 | delegation_stratex | −7.60 | 12.0 | PASS | PASS | PASS |
| 2 | context_followup | −2.51 | 4.0 | PASS | UNVERIFIED | UNVERIFIED |
| 3 | clock_tokyo | −1.95 | 4.0 | PASS | PASS | PASS |
| 4 | memory_remember | −3.95 | 6.0 | PASS | PASS | PASS |
| 5 | memory_recall | −1.54 | 5.0 | PASS | PASS | PASS |
| 6 | goodbye | −2.73 | 4.0 | PASS | PASS | PASS |

Full-precision gaps from `results.json`: greeting 0.7007758617401123,
delegation −7.595260381698608, followup −2.510507583618164,
clock −1.951253890991211, remember −3.950937509536743,
recall −1.5413143634796143, goodbye −2.7259535789489746.

Latency (silence gap) is inside its limit on **all 7 turns**. Negative gaps mean
FRIDAY began answering before the prompt audio finished — the same
overlapping-answer shape as runs 18/19/20/21/24, caused by the ~240 s greeting
burst (see §7).

**Acceptance verdict: PASS — greeting onset 0.70 s against the 8 s bar.**
Every turn's latency is inside its silence limit. This is the task's
acceptance criterion, and it is met.

## 6. Overall scorer: UNVERIFIED — one content leg, and it is attribution

Scorer output (`results.md`, battery v1): overall **UNVERIFIED** (scorer exit 0
with one UNVERIFIED turn). Single reason, verbatim:
context_followup content UNVERIFIED (followup_count=82 delegation_count=None).

What the evidence actually shows (first-hand from `results.json` + `journal.txt`):

- **Alignment is the order-based fallback (9 user finals for 6 turns; 2 extra
  items folded into greeting).** The STT "heard" text is shifted one turn
  throughout: clock_tokyo's heard text is the followup prompt,
  memory_recall's heard text is the clock prompt, goodbye's heard text is
  "My favorite color is teal." (the recall prompt). The journal holds
  20 `role=assistant` lines, 18 `role=user`, 40 `conversation_item_added`
  total — the same shape as run 18. The scorer cannot attribute content
  reliably under this shape — the same known harness weakness documented in
  runs 19, 20, 21, 24 and 18.
- **The one UNVERIFIED leg is an attribution artefact, verified first-hand:**
  FRIDAY answered "There were exactly 82 closed trades recorded in the
  ledger." at 17:39:40 UTC — the followup figure IS in the journal. The
  scorer reports followup_count=82 (it found the figure) but
  delegation_count=None, because the delegation turn's answer was the full
  portfolio snapshot rather than a bare count; its rule cannot match the two
  turns apart.
- **This run the scorer agrees on every other content leg — the cleanest
  scorer outcome in the recent run sequence** (runs 18/20/21/24 all scored
  FAIL on content):
  - **Clock:** PASS — "It is currently 2:40 AM on Thursday, November 26th,
    in Tokyo, Japan." at 17:40:44 UTC — correct (17:40 UTC = 02:40 JST).
  - **Memory recall:** PASS — "Your favorite color is teal." at 17:42:53 UTC
    — **the Memora read path IS verified by this run** (and the scorer
    agrees this time, the first scorer-clean recall in the recent sequence).
  - **Memory remember** is a genuine PASS, and stronger than the scorer's
    "reply present": "Got it, Boss — locked in: your favorite color is teal.
    That's mine to keep now, and it's pinned so it never fades." at
    17:41:55 UTC. (The scorer's extracted answer "Certainly. What " is a
    truncated fragment just before the remember reply; the attribution shift
    again.)
  - **Goodbye** is a genuine PASS: "Goodbye! Let me know if you need
    anything else later." at 17:43:54 UTC.
- **Delegation is a genuine PASS (figures + Stratex terms present), the fourth
  clean delegation PASS in a row (runs 21, 18, 24, 25).** FRIDAY gave real
  Stratex figures — "Here are the details from Stratex: the current balance
  is 10,454.02, there are 30 open positions, and there are 82 closed trades
  recorded in the ledger." (17:38:19 UTC) — plus a full portfolio snapshot at
  17:39:33 UTC (balance 10,454.02, 30 open, 82 closed, unrealised P&L
  +103.39, ledger net P&L +117.95, win rate 18%, profit factor 1.34).

## 7. Greeting anomaly (recorded, not scored)

FRIDAY's greeting speech ran the same ~240 s burst shape as runs 19/20/21/24/18:
agent joined 17:33:24 UTC and the first substantive assistant journal text is
the Stratex balance at 17:38:19 UTC (~4.9 min later); the burst's content is
only in the 66.6 MB agent WAV and is UNVERIFIED from the journal. That is why
every later turn's gap is negative: the agent was already speaking when each
prompt arrived.

## 8. States

- implemented YES (run executed on the live FRD-042 build, first-hand) /
  tested YES (scorer ran; latency 7/7 inside limits, greeting 0.70 s vs 8 s bar;
  scorer overall UNVERIFIED on one attribution leg only) /
  merged NO (work PR open, merge is Muse's — workers never merge own PRs) /
  deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window run; the latency bar is met; the
  clock/recall/followup/delegation content legs are verified by first-hand
  journal read, and the scorer agrees on all but the followup attribution leg).
- **Voice status is NOT WORKING until the owner re-tests and accepts** (P0,
  owner live test 2026-11-25 15:54 IST). This run is calm-window probes only;
  the live leg (production deploy + owner re-test) is BLOCKED on Muse's hub
  clearance.
- Usage: 75% of free weekly limit (last known, coordinator watch107; reset
  Nov 28 21:57 IST).
- No restarts, no deployments, no live writes in this run. No approval blocks.
- Bridge transport was flaky on the launch call (the launching exec hit the
  120 s local timeout while the remote nohup kept running; verified first-hand
  afterwards that the launch DID apply — log exists, participant running — no
  duplicate launch). The run itself was detached on FRIDAY-Server and unaffected.

## 9. Board flip riding in this PR

- **TASK-VOI-040 AVAILABLE → IN_REVIEW** (owner muse_1, branch
  `muse1/task-voi-040-acceptance-run-25`, this work PR) — this task.
- NOTE (owed, NOT in this PR): TASK-VOI-039 is still IN_REVIEW on the board
  although its work PR #1868 merged (`5188dff3`, 2026-11-25 22:08:31 IST,
  verified first-hand via the PR API) — its MERGED flip is owed to a
  coordinator board pass.
- No code or test files in this PR (evidence doc + board only), so the FUT-030
  CI-coverage lesson does not apply — there are no new tests to list in any
  workflow; CI green here means the board YAML parses and the validators pass.

— Muse 1
