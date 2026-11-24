# TASK-VOI-038 — FRIDAY voice: acceptance run 23 (calm-window run)

**Worker:** Muse 15. **Claim:** hub #1483 comment 7124001417, 2026-11-24 ~12:00 IST
(hourly self-check), per coordinator watch 7122246187 (~10:25 IST).
**Branch:** `muse15/task-voi-038-acceptance-run-23-r2` from main `89605ae4`
(the claim branch `muse15/task-voi-038-acceptance-run-23` stands at the
claim-time main `af42c676`; this `-r2` branch carries the run evidence so
the PR diff is clean). **Board:** main `89605ae4`; VOI-038 verified CLAIMED,
owner muse_15, before filing. No prior work PR.

## 1. The task

Acceptance: *"Per-probe latency filed with a pass/fail verdict on the 8s
greeting-onset bar."* Next action on the record: *"Wait for a calm window,
then run the probes and file per-probe latency + pass/fail verdict."*
Sequencing gate (run 22, VOI-037) cleared: evidence PR #1648 MERGED
(merge `239c9ef4`). Deploy gate cleared by the coordinator in watch
7129798495 (16:17 run): **"M15 VOI-038 run 23: GO — deploy gate cleared;
fresh calm check first, then run in the next calm window."** FRD-042
deployed live by Muse 5 ~16:14 IST (live build `fFKg6fXVVhWz4qvLQD0Pi`,
FRIDAY restarted, /health + /ready 200 — hub #1483 comment 7129301409).

The run uses the `FRIDAY/voice_acceptance/` probe caller (participant +
`run_acceptance.sh`, proven end-to-end by Muse 13 in TASK-FRG-020) against
the deployed FRIDAY-Voice worker on **FRIDAY-Server** (15.134.130.145),
per the coordinator's ruling (watch 7126818611, 14:17 run) that
FRIDAY-Server is the acceptance host. Route: bridge `run_shell` on Oracle
Server 2 → `ssh -i ~/.ssh/Oracle-Cloud-x-AWS-Key ubuntu@15.134.130.145`.

## 2. Calm check — 2026-11-24 ~16:58 IST (read-only, first-hand)

Bridge `run_shell` on Server 2 → FRIDAY-Server (11:28:51 UTC):

- Load average: **0.03 / 0.33 / 0.32** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, 256 free, **1104 available**; swap 102/8191 MB.
- **FRIDAY.service: active, NRestarts 0, MemoryCurrent 61,775,872 /
  209,715,200 — 29.5% of its 200 MB cgroup cap.** Real headroom (contrast
  S1's 99.98% earlier today). ActiveEnterTimestamp 10:48:22 UTC
  (16:18:22 IST — the FRD-042 restart).
- **FRIDAY-Voice.service: active**, NRestarts 0, MemoryCurrent 257,581,056
  (no cap). **Inference: active.**
- Live build: `_next/static/` shows **`fFKg6fXVVhWz4qvLQD0Pi`** — the
  post-#1647 FRD-042 build, confirmed live.
- **/health 200 in 0.82 s; /ready 200 in 0.74 s** (loopback 127.0.0.1:10000
  on FRIDAY-Server). (Note: `/friday/health` is 404 on this service — that
  path does not exist here; it was 404 before the restart too, per M5.
  `/health` + `/ready` are the live health endpoints.)

Preflight on FRIDAY-Server (same probe): harness files present
(`FRIDAY/voice_acceptance/` — all 7 files); fleet venv
`/opt/friday_universe/venv/bin/python` imports livekit/httpx/edge_tts and
PyAV OK; `journalctl -u FRIDAY-Voice.service` readable; status file
`/opt/friday_universe/FRIDAY/data/voice_worker_status.json` readable.

**Verdict: calm window confirmed.** Probes run.

## 3. The run — room `friday-frd005-20261124-113017`

- **Launched 11:30:17 UTC (17:00:17 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi038-launch.log`), so bridge
  transport drops cannot kill it.
- **Prior run on the same host:** room `friday-frd005-20261124-111319`
  ran 16:43–16:55 IST, overall **FAIL** (latencies all PASS; content FAIL
  on memory_recall/goodbye, out-of-order alignment). Owner not identified
  from the run artefacts; no hub post about it as of the 16:56 IST hub
  read. The voice worker was idle when run 23 launched — status file
  `closed` at 16:54:59 IST ("owner left; session closed") — and no other
  participant was running. Run 23 is an independent run, not a re-run of
  111319.
- **Bridge transport note:** the launch call's response was dropped
  ("MCP request did not complete"); the launch was verified landed by
  re-probe (run dir `20261124-113017` created, participant pid 18363,
  agent joined `AJ_qg92VBwiNx6p`, status `ready`). No duplicate launch —
  one participant process only. Four later poll attempts also dropped
  before landing; nothing was claimed from a failed attempt.
- **Mid-run poll 11:37:30 UTC:** greeting done (gap 0.67 s), delegation
  turn done (gap −7.59 s), context_followup underway; host still calm
  (load 0.76, 1052 MB available).
- **Completed 11:43:32 UTC (17:13:32 IST):** `results.md` + `results.json`
  written, participant exited, host calm (load 0.08, 1118 MB available).
  Run duration ~13 min.

## 4. Results — overall PASS

Scorer output (`/tmp/frd005/runs/20261124-113017/results.md`, battery v1,
provider `gemini-realtime:gemini-3.8-live` — PASS, no contamination lines):

| # | Turn | Silence gap (s) | Limit (s) | FRIDAY's answer (truncated) | Verdict |
|---|------|-----------------|-----------|------------------------------|---------|
| 0 | greeting | 0.67 | 8.0 | Still waiting on those Stratex details, but I will update you the moment the data comes in | PASS |
| 1 | delegation_stratex | −7.59 | 12.0 | The Stratex data just came in: you have a balance of 10,465.58, 29 open positions, and 81 closed trades in the ledger… | PASS |
| 2 | context_followup | −2.51 | 4.0 | There were exactly 81 closed trades recorded in the ledger. | PASS |
| 3 | clock_tokyo | −1.95 | 4.0 | Right now, it is 8:37 PM in Tokyo, Japan. | PASS |
| 4 | memory_remember | −3.95 | 6.0 | Of course. What exactly… | PASS |
| 5 | memory_recall | −1.54 | 5.0 | Your favorite color is teal. | PASS |
| 6 | goodbye | −2.72 | 4.0 | Understood, Boss. Just… | PASS |

**Acceptance verdict: PASS.** Greeting onset 0.67 s against the 8 s bar;
every turn inside its silence limit; content PASS on all turns. The
delegation figures match live state independently verified the same day
(29 open positions per M4's STR-060 reconciliation, merge `ea4f786a`;
81 closed trades in the ledger); the follow-up count matches the
delegation count (81); "teal" recalled; goodbye answered.

Answers in journal order (from `results.json`): "Still waiting on those
Stratex details, but I will update you the moment the data comes in." /
"The Stratex data just came in: you have a balance of 10,465.58, 29 open
positions, and 81 closed trades in the ledger. Also, please note that live
trading remains blocked by your fail-closed guard, so this is only the demo
account." / "There were exactly 81 closed trades recorded in the ledger." /
"Right now, it is 8:37 PM in Tokyo, Japan." / "Of course. What exactly" /
"Your favorite color is teal." / "Understood, Boss. Just".

## 5. Caveats — read before citing the PASS

- **Alignment is the order-based fallback (9 user finals for 6 turns).**
  Answers arrive out of order / overlapping (negative gaps) — the known
  shape from run 22's doc and the 111319 run. The scorer resolved every
  turn's content PASS this time (unlike 111319, where the same shape
  produced content FAILs on memory_recall and goodbye), but the per-turn
  latency attribution carries the fallback caveat: the gaps are
  measurement artefacts of interleaving, not clean silence measurements.
- **The greeting answer is a holding line** ("Still waiting on those
  Stratex details…") with the real figures arriving in turn 1. The scorer
  passes it as "agent spoke"; it is not evidence the greeting itself
  carried figures.
- **Run artefacts live on FRIDAY-Server**, `/tmp/frd005/runs/20261124-113017/`
  (timeline, journal window, status snapshot, `results.json`/`results.md`,
  66 MB agent WAV) — not in the repo. The launch log is
  `/tmp/frd005/voi038-launch.log`.

## 6. States

- implemented YES (run executed on the live FRD-042 build, first-hand) /
  tested YES (scorer overall PASS, 7/7 turns, provider PASS) /
  merged NO (work PR open, merge is Muse's — workers never merge own PRs) /
  deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window PASS on FRIDAY-Server; the
  out-of-order alignment caveat above stands).
- Usage: 9% of free weekly limit (checked this run via subscription-status;
  reset Nov 30, 7:04 PM IST). Additional tokens 0% used. No wrap-up,
  no cancellations.
- Schedules verified this run: muse15-hourly-self-check enabled (1h),
  muse15-weekly-reset enabled (Mon 19:14 IST), muse15-work-request absent —
  correct while mid-task (VOI-038 claimed; FRD-043 + VOI-033 queued).

— Muse 15
