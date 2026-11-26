# TASK-VOI-044 — FRIDAY voice: acceptance run 27 (calm-window run)

**Worker:** Muse 10. **Claim:** hub #1483 comment 7181525062, 2026-11-26 ~08:43 IST,
on WATCH135 assignment (7181402891, P1, no blockers). Claim PR #1942 closed
unmerged by coordinator ruling WATCH136 (hub 7181836172): claim PRs are abolished
(owner-approved process 2026-11-22) — a claim is a hub comment + branch push, and
the board flip rides inside the work PR. **Branch:**
`muse10/task-voi-044-acceptance-run-27` from main `5aafed1e`, merged main
`02b86511` into this work PR (force-push unavailable — bridge git_push rejects
non-fast-forward; see §9).
**Board:** main `02b86511`, VOI-044 AVAILABLE, owner muse_10, branch null,
pr null, P1, before this work PR (coordinator board PRs #1941/#1947 set owner muse_10
+ assignment lines).
**Acceptance host:** FRIDAY-Server (15.134.130.145), per coordinator ruling
(watch 7126818611).
**Live build:** `fFKg6fXVVhWz4qvLQD0Pi` (FRD-042 build, confirmed in the served page).

## 1. The task

Acceptance: *"Run the probes in the next calm window; file per-probe latency +
pass/fail. Speed is the headline metric."* Sequel to VOI-041 (run 26, Muse 15,
MERGED) and VOI-040 (run 25, Muse 1, work PR #1879). The run uses the
`FRIDAY/voice_acceptance/` probe caller (participant + `run_acceptance.sh`,
proven end-to-end by Muse 13 in TASK-FRG-020) against the deployed FRIDAY-Voice
worker on FRIDAY-Server. Route: bridge `run_shell` on server 2, SSH to
FRIDAY-Server (`ssh -i ~/.ssh/Oracle-Cloud-x-AWS-Key ubuntu@15.134.130.145`,
per VOI-039; the default id_rsa key is refused).

## 2. Stop-order check

- Owner stop order ~16:42 IST Nov 24 ("Don't move anything now") froze ALL server
  moves; partial lift 17:26 IST covers ONLY (1) key architecture, (2) bridge work,
  (3) the Inference move.
- The voice-probe leg is NOT a server move: coordinator ruling 7126818611
  (Nov 24 ~13:52 IST): "RULING — acceptance host is FRIDAY-Server, not S1...
  VOI-030/035 hold LIFTS: M13, probe in the next calm window against
  FRIDAY-Server." Runs 18–26 executed the identical leg and MERGED/filed.
- WATCH136 (7181836172, ~09:05 IST) carried "fleet CD broken (deploy clearances
  still blocked — owner stop order stands)" — that blocks deploys, not read-only
  probes. No newer stop-order change is known to this run.

**Verdict: live leg callable as a read-only probe against FRIDAY-Server.** No
server moves, no installs, no restores, no deploys attempted.

## 3. Calm check — 2026-11-26 ~09:18 IST (FRIDAY-Server, read-only, first-hand)

- Load average: **0.03 / 0.07 / 0.08** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, **1094 MB available**; swap 120/8191 MB.
- **FRIDAY.service: active, NRestarts 10** (was 8 in run 26 — restarted
  2026-11-25 23:36:48 UTC, after run 26 ended), **MemoryCurrent 46,108,672 /
  209,715,200 — 22.0% of its 200 MB cgroup cap.**
  ActiveEnterTimestamp 2026-11-25 23:36:48 UTC.
- **FRIDAY-Voice.service: active since 07:21:18 UTC Nov 24**, NRestarts 0,
  MemoryCurrent 269,262,848. **Inference.service: active.**
- **/health 200 in 1.52 s**; **/ready 200 in 0.88 s; token endpoint
  `http://127.0.0.1:10000/api/livekit/token` 200 in 1.48 s** (slower than run 26's
  0.75 / 0.74 / 0.23 s, all still 200).
- Voice status file: state `closed`, room `friday-frd005-20261125-180043`
  (run 26), updated 2026-11-25T18:12:20Z, provider
  `gemini-realtime:gemini-3.8-live`, voice Aoede. No participant process running.
- **Calm window confirmed; worker free; no run in progress — launched at once.**

Preflight: all 7 `FRIDAY/voice_acceptance/` files byte-identical to main
`036fb2da` (blob SHAs MATCH: README.md, battery.json, make_utterances.py,
participant.py, run_acceptance.sh, score.py, score_check.py); fleet venv imports
livekit/httpx/edge_tts and PyAV OK; served page contains build
`fFKg6fXVVhWz4qvLQD0Pi`; checkout at `5b245ffd` with dirty `ui/out/` build
output only — the checkout is behind main and is not the deployed-service
version marker (same note as runs 24/25/26).

Bridge transport was flaky during this run (several IncompleteRead /
event-stream-ended failures on `run_shell`, recovering on retry); the launch call
itself timed out after 60 s while the remote nohup kept running — verified
first-hand afterwards that the launch DID apply (log exists, participant running
— no duplicate launch).

## 4. The run — room `friday-frd005-20261126-035014`

- **Launched 03:50:14 UTC (09:20:14 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi044-launch.log`), so bridge
  transport drops cannot kill it. The launching bridge call timed out after
  60 s (transport) but the launch HAD landed (pid 56287) — verified first-hand
  by re-probe (log exists, run dir created, participant pid 56300, agent
  joined `AJ_rKwAWMWDyunN`). No duplicate launch — one participant process only.
- Agent joined 03:50:17 UTC (~0.4 s after the participant connected 03:50:16
  UTC — back to the fast join of run 25's <1 s, vs run 26's 5.4 s; see §7).
- Host stayed calm through the run (load 1.24 at 03:54 UTC, 0.81 at 04:02 UTC).
- Greeting onset decomposition (TASK-VOI-026, journal 03:50:17 UTC):
  job-to-connect 0.11 s, connect-to-key 0.00 s, key-to-participant 0.00 s,
  participant-to-gate 0.30 s, gate LISTENING after 0.00 s,
  **connect-to-first-audio 0.31 s** (fixed-line greeting).
- Run artefacts on FRIDAY-Server, `/tmp/frd005/runs/20261126-035014/`: timeline
  (3.9 KB), `journal.txt` (57,664 B), `results.json` (4,409 B), `results.md`
  (1,504 B), `status.json`, utterances manifest, 66.6 MB agent WAV. Launcher log
  `/tmp/frd005/voi044-launch.log`.
- **Completed 04:01 UTC (09:31 IST)**; participant exited; status file `closed`
  (updated 04:01:46 UTC, job `AJ_rKwAWMWDyunN`).

## 5. Per-probe latency — the acceptance table

| # | Turn | Silence gap (s) | Limit (s) | Latency | Content | Verdict |
|---|------|-----------------|-----------|---------|---------|---------|
| 0 | greeting | 0.54 | 8.0 | PASS | PASS | PASS |
| 1 | delegation_stratex | −7.60 | 12.0 | PASS | PASS | PASS |
| 2 | context_followup | −2.50 | 4.0 | PASS | UNVERIFIED | UNVERIFIED |
| 3 | clock_tokyo | −1.95 | 4.0 | PASS | PASS | PASS |
| 4 | memory_remember | −3.95 | 6.0 | PASS | PASS | PASS |
| 5 | memory_recall | −1.54 | 5.0 | PASS | PASS | PASS |
| 6 | goodbye | −2.72 | 4.0 | PASS | PASS | PASS |

Full-precision gaps from `results.json`: greeting 0.5422041416168213,
delegation −7.598482847213745, followup −2.50108003616333,
clock −1.951523780822754, remember −3.948552131652832,
recall −1.5402779579162598, goodbye −2.7185237407684326.

Latency (silence gap) is inside its limit on **all 7 turns**. Negative gaps mean
FRIDAY began answering before the prompt audio finished — the same
overlapping-answer shape as runs 18/19/20/21/24/25/26, caused by the ~240 s greeting
burst (see §7).

**Acceptance verdict: latency PASS — greeting onset 0.54 s against the 8 s bar.**
Every turn's latency is inside its silence limit. This is the task's
acceptance criterion, and it is met — and the greeting gap is back in the
~0.5 s band after run 26's 5.54 s jump; see §7.

## 6. Overall scorer: UNVERIFIED — and what the journal actually shows

Scorer output (`results.md`, battery v1): overall **UNVERIFIED**. Reason, verbatim:
context_followup content UNVERIFIED (followup_count=2 delegation_count=None).

What the evidence actually shows (first-hand from `results.json` + `journal.txt`):

- **Alignment is the order-based fallback (9 user finals for 6 turns; 2 extra
  items folded into greeting).** The STT "heard" text is shifted one turn
  throughout: clock_tokyo's heard text is the followup prompt,
  memory_recall's heard text is the clock prompt, goodbye's heard text is
  "My favorite color is teal." (the recall prompt). The journal holds 10
  assistant items (20 `role=assistant` lines — each logged twice), 9 `role=user`
  items, 40 `conversation_item_added` total — the same shape as runs 18/24/25/26.
  The scorer cannot attribute content reliably under this shape — the same known
  harness weakness documented in runs 19, 20, 21, 24, 25, 18 and 26.
- **Clock is a genuine PASS:** "It is currently 12:57 PM in Tokyo." at 03:57:35 UTC
  — correct (03:57 UTC = 12:57 JST).
- **Memory recall is a genuine PASS:** "Your favorite color is teal." at
  03:59:46 UTC — **the Memora read path IS verified by this run** (third
  scorer-clean recall in a row after runs 25 and 26). Caveat: "teal" was already
  stored by earlier runs, so this verifies the read path, not this run's write.
- **Memory remember is a genuine PASS, and stronger than the scorer's
  "reply present":** "Got it, Boss — locked in: my favorite color is teal.
  That's mine to keep now. That one's pinned — it never fades." at 03:58:49 UTC
  (the same confirmation line as run 26, verbatim). The scorer's extracted
  answer "I can certainly store that for you." (03:58:35 UTC) is the generic
  line from the previous turn; the attribution shift again.
- **Goodbye is a genuine PASS:** "Goodbye, Boss. I'll be here whenever you need
  anything else." at 04:00:47 UTC. The scorer's extracted answer "Understood,
  Boss. Just let me know" (04:00:42 UTC) is the truncated fragment from the
  VOI-043 symptom (see below); the attribution shift again.
- **Delegation is a genuine PASS (figures + Stratex terms present), the sixth
  clean delegation PASS in a row (runs 21, 18, 24, 25, 26, 27).** FRIDAY gave real
  Stratex figures — "Portfolio snapshot (Stratex, FUTURES mode): - Balance:
  10,465.60 - Open positions: 30 SHORT TRXUSDT @ 0.31288 LONG ADAUSDT @ 0.1494
  SHORT FILUSDT @ 0.5691 SHORT ARBUSDT @ 0.1273 SHORT XRPUSDT @ 0.925 SHORT
  SOLUSDT @ 69.02 SHORT BCHUSDT @ 206.88 SHORT MANAUSDT @ 0.06061 - Unrealized
  P&L: +35.91 - Ledger P&L recorded fills: 82 closed trade(s), net P&L +117.95,
  win rate 18%, profit factor 1.34 LEGACY" (03:56:26 UTC) — plus the greeting's
  balance line "The Stratex balance is 10,465.60 with 30 open positions and 82
  closed trades in the ledger." (03:54:46 UTC).
- **Followup is a genuine PASS in substance:** "That was exactly eighty-two
  closed trades in the ledger." at 03:56:33 UTC — the followup figure IS in
  the journal and matches delegation's 82. The scorer reports followup_count=2
  but delegation_count=None, because its rule cannot match the two turns apart
  under the attribution shift.
- **One REAL defect, not attribution:** the truncated fragment "Understood,
  Boss. Just let me know" at 04:00:42 UTC — the VOI-043 symptom, on the PRE-VOI-043
  build (voice worker untouched since Nov 24 07:21 UTC; VOI-043 merged but not
  deployed — CD broken). Same finding as runs 24 and 26. The reply pipeline lagged
  a full turn behind all call, so the scorer's goodbye slot holds the fragment
  while the proper farewell sits 5 s later in the journal.

## 7. Greeting anomalies (recorded, not scored)

- **Greeting onset 0.54 s vs 5.54 s (run 26) / 0.70 s (run 25) / 0.52 s (run 24)**
  — PASS vs the 8 s bar, and back in the ~0.5 s band. Worker-side onset is
  unchanged (decomposition: connect-to-first-audio 0.31 s, gate LISTENING after
  0.00 s). The extra ~5 s in run 26 was agent join: participant connected
  03:50:16.88 UTC, agent joined 03:50:17.27 UTC (~0.4 s) this run, vs run 26's
  ~5.4 s. Run 26's jump was a single-run observation, not a trend — confirmed
  by this run.
- FRIDAY's greeting speech ran the same ~240 s burst shape as runs 19/20/21/24/25/26:
  agent joined 03:50:17 UTC, first substantive assistant journal text is the
  filler "Still waiting on the system response, but I'll update you as soon as
  the Stratex data come..." at 03:54:31 UTC, then the Stratex balance at
  03:54:46 UTC (~4.5 min later); the burst's content is only in the 66.6 MB
  agent WAV and is UNVERIFIED from the journal. That is why every later turn's
  gap is negative: the agent was already speaking when each prompt arrived.

## 8. States

- implemented YES (run executed on the live FRD-042 build, first-hand) /
  tested YES (scorer ran; latency 7/7 inside limits, greeting 0.54 s vs 8 s bar;
  scorer overall UNVERIFIED on the followup attribution leg + one real truncated
  fragment) / merged NO (work PR open, merge is Muse's — workers never merge own
  PRs) / deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window run; the latency bar is met; the
  clock/recall/followup/delegation/goodbye content legs are verified by first-hand
  journal read, and the scorer agrees on delegation + remember + recall + clock +
  goodbye).
- **Voice status is NOT WORKING until the owner re-tests and accepts** (P0,
  owner live test 2026-11-25 15:54 IST). This run is calm-window probes only;
  the live leg (production deploy + owner re-test) is BLOCKED on Muse's hub
  clearance.
- Usage: ~55% of free weekly limit (WATCH136 lag table; reset Nov 28 02:03 IST).
- No restarts, no deployments, no live writes in this run. No approval blocks.

## 9. Board flip riding in this PR

- **TASK-VOI-044 AVAILABLE → IN_REVIEW** (owner muse_10, branch
  `muse10/task-voi-044-acceptance-run-27`, this work PR) — this task.
- Note: this branch merges main `02b86511` instead of rebasing onto it, because
  the bridge `git_push` tool does a plain push and rejects the rebased history as
  non-fast-forward, and no force-push route exists in the bridge tooling. The
  merge brings main in; the PR diff vs main is the evidence doc + this flip only.
- No code or test files in this PR (evidence doc + board only), so the FUT-030
  CI-coverage lesson does not apply — there are no new tests to list in any
  workflow; CI green here means the board YAML parses and the validators pass.

— Muse 10
