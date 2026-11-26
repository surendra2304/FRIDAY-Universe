# TASK-VOI-041 — FRIDAY voice: acceptance run 26 (calm-window run)

**Worker:** Muse 15. **Claim:** hub #1483 comment 7170221048, 2026-11-25 ~23:26 IST,
on WATCH109 assignment (7169671316, M7 re-slot) and the board next_action
("claim via hub #1483 when it reaches queue head, after VOI-040 files");
the gate opened when VOI-040 filed as work PR #1879 (verified first-hand).
**Branch:** `muse15/task-voi-041-acceptance-run-26` from main `3efe8b04`.
**Board:** main `3efe8b04`, VOI-041 verified AVAILABLE, owner muse_15, branch null,
pr null, P1, before claiming. Queue: FRD-043 (HELD) → VOI-041 → EARN-025.
**Acceptance host:** FRIDAY-Server (15.134.130.145), per coordinator ruling
(watch 7126818611).
**Live build:** `fFKg6fXVVhWz4qvLQD0Pi` (FRD-042 build, confirmed in the served page).

## 1. The task

Acceptance: *"Per-probe latency + pass/fail filed on the 8s greeting-onset bar
for run 26."* Sequel to VOI-040 (run 25, Muse 1, work PR #1879 open) and
VOI-039 (run 24, Muse 15, MERGED PR #1868, merge `5188dff3`). The run uses the
`FRIDAY/voice_acceptance/` probe caller (participant + `run_acceptance.sh`,
proven end-to-end by Muse 13 in TASK-FRG-020) against the deployed FRIDAY-Voice
worker on FRIDAY-Server. Route: bridge `run_shell` on server 2, SSH to
FRIDAY-Server.

## 2. Stop-order check

- Owner stop order ~16:42 IST Nov 24 ("Don't move anything now") froze ALL server
  moves; partial lift 17:26 IST covers ONLY (1) key architecture, (2) bridge work,
  (3) the Inference move.
- The voice-probe leg is NOT a server move: coordinator ruling 7126818611
  (Nov 24 ~13:52 IST): "RULING — acceptance host is FRIDAY-Server, not S1...
  VOI-030/035 hold LIFTS: M13, probe in the next calm window against
  FRIDAY-Server." Runs 19 (VOI-034), 20 (VOI-035), 21 (VOI-036), 24 (VOI-039),
  18 (VOI-033) and 25 (VOI-040) executed the identical leg and MERGED/filed.
- WATCH110 (7170134760, ~23:25 IST) carried "fleet CD broken (deploy clearances
  still blocked — owner stop order stands)" — that blocks deploys, not read-only
  probes. No newer stop-order change is known to this run.
- Precondition satisfied: VOI-040 (run 25) filed via PR #1879 (open, head
  `c583b67c`, base `3efe8b04` = current main, mergeable true, verified
  first-hand via the PR API).

**Verdict: live leg callable as a read-only probe against FRIDAY-Server.** No
server moves, no installs, no restores, no deploys attempted.

## 3. Calm check — 2026-11-25 ~23:28 IST (FRIDAY-Server, read-only, first-hand)

- Load average: **0.01 / 0.09 / 0.18** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, **1071 MB available**; swap 117/8191 MB.
- **FRIDAY.service: active, NRestarts 8** (same as run 25 — no restart since),
  **MemoryCurrent 53,305,344 / 209,715,200 — 25.4% of its 200 MB cgroup cap.**
  ActiveEnterTimestamp 2026-11-25 16:25:34 UTC.
- **FRIDAY-Voice.service: active since 07:21:18 UTC Nov 24**, NRestarts 0,
  MemoryCurrent 263,766,016. **Inference.service: active.**
- **/health 200 in 0.75 s**; **/ready 200 in 0.74 s; token endpoint
  `http://127.0.0.1:10000/api/livekit/token` 200 in 0.23 s.**
- Voice status file: state `closed`, room `friday-frd005-20261125-173321`
  (run 25), updated 17:44:53 UTC. No participant process running.
- **Calm window confirmed; worker free; no run in progress — launched at once.**

Preflight (same probe): all 7 `FRIDAY/voice_acceptance/` files byte-identical to
main `3efe8b04` (md5 MATCH: README.md, battery.json, make_utterances.py,
participant.py, run_acceptance.sh, score.py, score_check.py); fleet venv imports
livekit/httpx/edge_tts and PyAV OK (the import statements executed with no
ImportError; the harness's own preflight gate passed at launch — `active`,
utterances reused); served page contains build
`fFKg6fXVVhWz4qvLQD0Pi`; checkout at `5b245ffd` with dirty `ui/out/` build
output only — the checkout is behind main and is not the deployed-service
version marker (same note as run 24).

## 4. The run — room `friday-frd005-20261125-180043`

- **Launched 18:00:43 UTC (23:30:43 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi041-launch.log`), so bridge
  transport drops cannot kill it. The launching bridge call timed out after
  60 s (transport) but the launch HAD landed (pid 50344) — verified first-hand
  by re-probe (log exists, run dir created, participant pid 50359, agent
  joined `AJ_DeV3MZ3vx8bz`). No duplicate launch — one participant process only.
- Agent joined 18:00:50 UTC (~5.4 s after the participant connected 18:00:45
  UTC — slower join than run 25's <1 s; see §7).
- Host stayed calm through the run (load 0.33 at 18:09 UTC, 0.20 at 18:14 UTC).
- Greeting onset decomposition (TASK-VOI-026, journal 18:00:50 UTC):
  job-to-connect 0.12 s, connect-to-key 0.00 s, key-to-participant 0.00 s,
  participant-to-gate 0.30 s, gate LISTENING after 0.00 s,
  **connect-to-first-audio 0.30 s** (fixed-line greeting).
- Run artefacts on FRIDAY-Server, `/tmp/frd005/runs/20261125-180043/`: timeline
  (3.9 KB), `journal.txt` (46,671 B), `results.json` (4,150 B), `results.md`
  (1,646 B), `status.json`, utterances manifest, 66.6 MB agent WAV. Launcher log
  `/tmp/frd005/voi041-launch.log`.
- **Completed 18:12 UTC (23:42 IST)**; participant exited; status file `closed`.

## 5. Per-probe latency — the acceptance table

| # | Turn | Silence gap (s) | Limit (s) | Latency | Content | Verdict |
|---|------|-----------------|-----------|---------|---------|---------|
| 0 | greeting | 5.54 | 8.0 | PASS | PASS | PASS |
| 1 | delegation_stratex | −7.59 | 12.0 | PASS | PASS | PASS |
| 2 | context_followup | −2.50 | 4.0 | PASS | UNVERIFIED | UNVERIFIED |
| 3 | clock_tokyo | −1.94 | 4.0 | PASS | FAIL | FAIL |
| 4 | memory_remember | −3.96 | 6.0 | PASS | PASS | PASS |
| 5 | memory_recall | −1.55 | 5.0 | PASS | FAIL | FAIL |
| 6 | goodbye | −2.73 | 4.0 | PASS | FAIL | FAIL |

Full-precision gaps from `results.json`: greeting 5.543959856033325,
delegation −7.594019174575806, followup −2.4975132942199707,
clock −1.9443397521972656, remember −3.9575555324554443,
recall −1.5478055477142334, goodbye −2.726548433303833.

Latency (silence gap) is inside its limit on **all 7 turns**. Negative gaps mean
FRIDAY began answering before the prompt audio finished — the same
overlapping-answer shape as runs 18/19/20/21/24/25, caused by the ~240 s greeting
burst (see §7).

**Acceptance verdict: latency PASS — greeting onset 5.54 s against the 8 s bar.**
Every turn's latency is inside its silence limit. This is the task's
acceptance criterion, and it is met — but the greeting gap jumped from 0.70 s
(run 25) to 5.54 s (this run); see §7.

## 6. Overall scorer: FAIL — and what the journal actually shows

Scorer output (`results.md`, battery v1): overall **FAIL**. Reasons, verbatim:
context_followup content UNVERIFIED (followup_count=None delegation_count=82);
clock_tokyo content FAIL (no time in answer); memory_recall content FAIL
('teal' missing from answer); goodbye content FAIL (no assistant reply in
journal).

What the evidence actually shows (first-hand from `results.json` + `journal.txt`):

- **Alignment is the order-based fallback (9 user finals for 6 turns; 2 extra
  items folded into greeting).** The STT "heard" text is shifted one turn
  throughout: clock_tokyo's heard text is the followup prompt,
  memory_recall's heard text is the clock prompt, goodbye's heard text is
  "My favorite color is teal." (the recall prompt). The journal holds 8
  assistant items (16 `role=assistant` lines — each logged twice), 9 `role=user`
  items, 36 `conversation_item_added` total — the same shape as runs 18/24/25.
  The scorer cannot attribute content reliably under this shape — the same known
  harness weakness documented in runs 19, 20, 21, 24, 25 and 18.
- **Clock is a genuine PASS:** "It is currently 3:08 AM on Thursday, November
  26, 2026, in Tokyo, Japan." at 18:08:12 UTC — correct (18:08 UTC = 03:08 JST).
  The scorer attached the recall answer to the clock turn instead.
- **Memory recall is a genuine PASS:** "Your favorite color is teal." at
  18:10:19 UTC — **the Memora read path IS verified by this run** (second
  scorer-clean recall in a row after run 25).
- **Memory remember is a genuine PASS, and stronger than the scorer's
  "reply present":** "Got it, Boss — locked in: My favorite color is teal.
  That's mine to keep now. That one's pinned — it never fades." at 18:09:22 UTC.
  (The scorer's extracted answer "Understood, Boss. Just let" is the truncated
  fragment from the NEXT turn; the attribution shift again.)
- **Goodbye is a genuine PASS:** "Goodbye, Boss. Have a great day ahead." at
  18:11:20 UTC.
- **Delegation is a genuine PASS (figures + Stratex terms present), the fifth
  clean delegation PASS in a row (runs 21, 18, 24, 25, 26).** FRIDAY gave real
  Stratex figures — "The current Stratex balance is 10,454.33, with 30 open
  positions and 82 closed trades in the ledger." (18:05:22 UTC) — plus the
  fail-closed guard line ("live trading remains blocked by your fail-closed
  guard, so this is the demo account only").
- **Followup is a genuine PASS in substance:** "There are exactly 82 closed
  trades recorded in the ledger." at 18:07:06 UTC — the followup figure IS in
  the journal. The scorer reports followup_count=None but delegation_count=82,
  because the delegation turn's answer was the count-only line; its rule cannot
  match the two turns apart.
- **One REAL defect, not attribution:** the truncated fragment "Understood,
  Boss. Just let" at 18:11:16 UTC — the VOI-043 symptom, on the PRE-VOI-043
  build (voice worker untouched since Nov 24 07:21 UTC; VOI-043 merged but not
  deployed — CD broken). Same finding as run 24. The reply pipeline lagged a
  full turn behind all call, so the scorer's goodbye slot is empty.

## 7. Greeting anomalies (recorded, not scored)

- **Greeting onset 5.54 s vs 0.70 s (run 25) / 0.52 s (run 24)** — still PASS
  vs the 8 s bar, but an ~8x jump. Worker-side onset is unchanged
  (decomposition: connect-to-first-audio 0.30 s, gate LISTENING after 0.00 s).
  The extra ~5 s is agent join: participant connected 18:00:45.24 UTC, agent
  joined 18:00:50.63 UTC (~5.4 s); run 25's agent joined in <1 s. Cause
  unknown — single-run observation, not a trend yet; watch the next run.
- FRIDAY's greeting speech ran the same ~240 s burst shape as runs 19/20/21/24/25/18:
  agent joined 18:00:50 UTC and the first substantive assistant journal text is
  the "still pulling up" filler at 18:05:06 UTC, then the Stratex balance at
  18:05:22 UTC (~4.9 min later); the burst's content is only in the 66.6 MB
  agent WAV and is UNVERIFIED from the journal. That is why every later turn's
  gap is negative: the agent was already speaking when each prompt arrived.

## 8. States

- implemented YES (run executed on the live FRD-042 build, first-hand) /
  tested YES (scorer ran; latency 7/7 inside limits, greeting 5.54 s vs 8 s bar;
  scorer overall FAIL on attribution legs + one real truncated fragment) /
  merged NO (work PR open, merge is Muse's — workers never merge own PRs) /
  deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window run; the latency bar is met; the
  clock/recall/followup/delegation/goodbye content legs are verified by first-hand
  journal read, and the scorer agrees on delegation + remember).
- **Voice status is NOT WORKING until the owner re-tests and accepts** (P0,
  owner live test 2026-11-25 15:54 IST). This run is calm-window probes only;
  the live leg (production deploy + owner re-test) is BLOCKED on Muse's hub
  clearance.
- Usage: 30% of free weekly limit (reset Nov 30, 7:14 PM IST).
- No restarts, no deployments, no live writes in this run. No approval blocks.
- Bridge transport was flaky on the launch call (timed out after 60 s while the
  remote nohup kept running; verified first-hand afterwards that the launch DID
  apply — log exists, participant running — no duplicate launch). The run itself
  was detached on FRIDAY-Server and unaffected.

## 9. Board flip riding in this PR

- **TASK-VOI-041 AVAILABLE → IN_REVIEW** (owner muse_15, branch
  `muse15/task-voi-041-acceptance-run-26`, this work PR) — this task.
- No code or test files in this PR (evidence doc + board only), so the FUT-030
  CI-coverage lesson does not apply — there are no new tests to list in any
  workflow; CI green here means the board YAML parses and the validators pass.

— Muse 15
