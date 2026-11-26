# TASK-VOI-039 — FRIDAY voice: acceptance run 24 (calm-window run)

**Worker:** Muse 15. **Claim:** hub #1483 comment 7166811723, 2026-11-25 ~20:55 IST
(work-request run), per coordinator WATCH104 (hub #1483 comment 7166508436).
**Branch:** `muse15/task-voi-039-acceptance-run-24` from main `0eeaa43a`.
**Board:** main `0eeaa43a`; VOI-039 verified AVAILABLE, owner null, before claiming.
No prior work PR. Board flip (AVAILABLE → IN_REVIEW) rides in the
coordinator's next board PR per WATCH104 — not in this PR.

## 1. The task

Acceptance: *"Per-probe latency + pass/fail filed on the 8s greeting-onset bar
for run 24."* Next action on the record: *"Run the probes in the next calm
window; file per-probe latency + pass/fail."* Sequencing gate (run 23,
VOI-038) cleared: evidence PR #1666 MERGED (merge `6ea282d6`).

The run uses the `FRIDAY/voice_acceptance/` probe caller (participant +
`run_acceptance.sh`, proven end-to-end by Muse 13 in TASK-FRG-020 and by
Muse 15 in run 23) against the deployed FRIDAY-Voice worker on
**FRIDAY-Server** (15.134.130.145), per the coordinator's ruling that
FRIDAY-Server is the acceptance host. Route: bridge `run_shell` on Oracle
Server 2 → `ssh -i ~/.ssh/Oracle-Cloud-x-AWS-Key ubuntu@15.134.130.145`.

## 2. Calm check — 2026-11-25 ~20:56 IST (read-only, first-hand)

Bridge `run_shell` on Server 2 → FRIDAY-Server (15:26:05 UTC):

- Load average: **0.14 / 0.22 / 0.19** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, 457 free, **1112 available**; swap 109/8191 MB.
- **FRIDAY.service: active, NRestarts 7, MemoryCurrent 50,151,424 /
  209,715,200 — 23.9% of its 200 MB cgroup cap.** ActiveEnterTimestamp
  13:59:44 UTC (19:29:44 IST).
- **FRIDAY-Voice.service: active, NRestarts 0, MemoryCurrent 261,181,440.**
  ActiveEnterTimestamp Tue 2026-11-24 07:21:18 UTC — the voice worker has
  run untouched since Nov 24 ~12:51 IST.
- **Inference.service: active.**
- **/health 200 in 0.73 s; /ready 200 in 0.84 s** (loopback 127.0.0.1:10000
  on FRIDAY-Server).
- Voice worker status file at launch: `closed` (owner session ended
  15:55:12 IST, room `friday-451209f0`) — worker idle, no other participant
  running.

Preflight: harness files present (`FRIDAY/voice_acceptance/` — all 7
files); fleet venv imports livekit/httpx/edge_tts + PyAV (script's own
preflight gates passed — `active`, utterances reused).

**Build note (matters for the verdict):** the voice worker predates the
VOI-043 merge (PR #1856, merge `34e1aa68`, ~20:45 IST today) and fleet CD
is broken (WATCH098), so **run 24 measures the PRE-VOI-043 live build** —
the P0 dropped-fragment / arbitrary-cancellation fixes are merged but not
yet deployed. No `BUILD_ID` file exists under `/opt/friday_universe`; the
FRIDAY-Server checkout sits at `5b245ffd` (merge #1632) with dirty
`ui/out/` build output — the checkout is behind main and is not the
deployed-service version marker. Service state above is the ground truth
used.

**Verdict: calm window confirmed.** Probes run.

## 3. The run — room `friday-frd005-20261125-152842`

- **Launched 15:28:42 UTC (20:58:42 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi039-launch.log`), so bridge
  transport drops cannot kill it.
- **Bridge transport note:** the first launch call's response was dropped
  ("MCP request did not complete") and the launch had NOT landed — verified
  by re-probe (no new run dir, no participant, no launch log), so it was
  relaunched. The second launch call's response was also dropped ("MCP
  event stream ended before the matching result") but the launch HAD landed
  — verified by re-probe (run dir `20261125-152842` created, participant
  pid 46392, agent joined `AJ_6j9wd8BQ7vmY`). No duplicate launch — one
  participant process only. Two later poll calls also dropped before
  landing; nothing was claimed from a failed attempt.
- **Mid-run poll 15:36:48 UTC (21:06:48 IST):** greeting done (gap 0.52 s),
  delegation + context_followup done, clock_tokyo underway; host still calm
  (load 0.36, 1112 MB available).
- **Completed 15:42:04 UTC (21:12:04 IST):** `results.md` + `results.json`
  written, participant exited, host calm (load 0.29). Run duration ~13 min
  (connect 15:28:46 → last turn_done 15:40:12 UTC + scoring). Status file
  `closed` at 15:40:16 UTC ("owner left; session closed", job
  `AJ_6j9wd8BQ7vmY`).

## 4. Results — scorer overall FAIL; latency leg PASS 7/7

Scorer output (`/tmp/frd005/runs/20261125-152842/results.md`, battery v1,
provider `gemini-realtime:gemini-3.8-live` — PASS, no contamination lines):

| # | Turn | Silence gap (s) | Limit (s) | FRIDAY's answer (truncated) | Verdict |
|---|------|-----------------|-----------|------------------------------|---------|
| 0 | greeting | 0.52 | 8.0 | Your Stratex demo account balance is 10,439.95. There are 30 open positions and 82 closed trades in the ledger. Please note that live trading remains blocked by your fail-closed guard. | PASS |
| 1 | delegation_stratex | −7.59 | 12.0 | There are exactly 82 closed trades in the ledger. | PASS |
| 2 | context_followup | −2.51 | 4.0 | Your favorite color is teal. | UNVERIFIED |
| 3 | clock_tokyo | −1.95 | 4.0 | Understood, Boss. Just let me | FAIL |
| 4 | memory_remember | −3.96 | 6.0 | Goodbye, Boss. Have a great day! | PASS |
| 5 | memory_recall | −1.54 | 5.0 | *(no answer in journal)* | FAIL |
| 6 | goodbye | −2.73 | 4.0 | *(no answer in journal)* | FAIL |

**Acceptance verdict: latency PASS, content FAIL.** Greeting onset 0.52 s
against the 8 s bar; every turn inside its silence limit. The per-probe
latency + pass/fail the acceptance asks for is filed above.

Answers in journal order (from `results.json` — 5 assistant utterances for
7 slots): "Your Stratex demo account balance is 10,439.95. There are 30
open positions and 82 closed trades in the ledger. Please note that live
trading remains blocked by your fail-closed guard." / "There are exactly 82
closed trades in the ledger." / "Your favorite color is teal." /
"Understood, Boss. Just let me " / "Goodbye, Boss. Have a great day!"

## 5. Caveats — read before citing the FAIL

- **Alignment is the order-based fallback (9 user finals for 6 turns).**
  Answers arrive out of order / overlapping (negative gaps) — the known
  shape from runs 22–23. The scorer assigns journal answers to turns in
  order, so two of the four content problems are demonstrable
  misattribution, verified first-hand in `results.json`: "Your favorite
  color is teal." is the correct memory_recall answer but is attached to
  context_followup; "Goodbye, Boss. Have a great day!" is the correct
  goodbye answer but is attached to memory_remember (which then scores
  PASS on "reply present" for the wrong text).
- **One failure is a real dropped fragment, not attribution.** The
  clock_tokyo answer is the truncated fragment "Understood, Boss. Just let
  me " — cut off mid-sentence, no time given. That is the exact symptom
  VOI-043 (P0) was merged to fix — and run 24 measures the pre-VOI-043
  build (§2), so this is evidence the defect was still live at run time,
  not evidence the fix failed.
- **Two turns genuinely have no journal answer.** memory_recall and
  goodbye produced no assistant utterance in the journal despite full
  ~60 s turn windows each (timeline: `utt_end` → `turn_done` ~60 s later
  for every turn; the call ran to completion, all 6 prompts spoken). The
  STT "heard" text also lags one turn behind throughout (e.g. goodbye's
  heard text is "My favorite color is teal." — the memory_recall prompt),
  so the agent's reply pipeline was a full turn behind the participant
  for the whole call. Whether the two missing answers are a real agent
  miss or a session-close artefact cannot be settled from `results.json`
  alone; the timeline + journal are in the run dir for a re-read.
- **The greeting carried figures this time.** Unlike run 23 (holding line
  "Still waiting on those Stratex details…"), the greeting itself delivered
  the Stratex figures (balance 10,439.95, 30 open, 82 closed). Run-23
  comparison (17:00 IST Nov 24: 10,465.58 / 29 / 81): +1 open, +1 closed,
  balance −25.63 — consistent drift, reported as spoken; the ledger was
  NOT independently verified in this run.
- **Run artefacts live on FRIDAY-Server**,
  `/tmp/frd005/runs/20261125-152842/` (timeline, journal, status snapshot,
  `results.json`/`results.md`, agent WAV) — not in the repo. The launch log
  is `/tmp/frd005/voi039-launch.log`. Other runs in `/tmp/frd005/runs/`
  (`20261124-210843`, `20261125-064054`, `20261125-080422`) are not mine;
  no hub post about them was read this run.

## 6. What this means for the queue

- VOI-039's acceptance (per-probe latency + pass/fail filed) is met: the
  latency leg is a clean PASS. The content leg is FAIL, but two of its
  four failures are scorer-attribution artefacts and the run measures a
  build that predates the VOI-043 fix.
- The meaningful next measurement is a re-probe **after VOI-043 deploys**
  (VOI-040, run 25, Muse 1) — that run tests whether the truncated-fragment
  symptom is gone. VOI-031 (greeting-onset diagnosis, claimed next in the
  completion post) should carry the alignment-artefact finding: the
  order-based fallback misattributes answers whenever the reply pipeline
  lags a turn behind, which it did for the whole of run 24.

## 7. States

- implemented YES (run executed on the live pre-VOI-043 build, first-hand) /
  tested YES (scorer ran: latency 7/7 PASS, content FAIL — see §5) /
  merged NO (work PR open, merge is Muse's — workers never merge own PRs) /
  deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window run on FRIDAY-Server;
  latency verdict clean, content verdict confounded by the alignment
  artefact + pre-fix build).
- Usage: 30% of free weekly limit (checked live this run via
  subscription-status; reset Nov 30, 7:04 PM IST).
- Work-request cron cancelled on the VOI-039 claim (this run); hourly
  self-check continues.
