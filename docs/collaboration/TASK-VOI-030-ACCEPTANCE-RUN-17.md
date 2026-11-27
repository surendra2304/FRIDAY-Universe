# TASK-VOI-030 — FRIDAY voice: acceptance run 17 (pacing-fix proof, calm box)

**Worker:** Muse 1. **Claim:** hub #2045 comment 7212629312, 2026-11-27 ~13:06 IST,
on coordinator direction (Burn Enforcer 13:00 §G + WATCH210-CORR §5).
**Branch:** `muse1/task-voi-030-acceptance-run-17` from main `25ce04a3`.
**Board:** main `25ce04a3`, VOI-030 verified AVAILABLE, owner muse_1, queue position 2
(head after VOI-029 re-slotted to muse_6 and FRD-043 IN_REVIEW), pr null, P1.
Queue: VOI-030 → FRD-064.
**Acceptance host:** FRIDAY-Server (15.134.130.145), per coordinator ruling
(watch 7126818611).
**Live build:** `bEQg9SjqU5pOmYL47AybJ` (FRIDAY-Server checkout `06ff9ee6`, the FRD-043
merged guard).

## 1. The task

Acceptance: *"One full acceptance run on a calm box: every probe transcribed,
per-probe latency filed, sent-vs-queued counters filed, greeting onset under the
8s bar; pass or fail verdict filed."*

Follow-on to VOI-027 (Muse 6, calm-window acceptance, verdict still not run) and
VOI-028 (MERGED greeting-onset fix). Run 16 convicted the send-cadence collapse:
the LOW arm queued 577 / sent 380 (ratio 0.66) at ~15.2 sends/s against the 20/s
realtime rate on a calm box; the HIGH arm sent 1,242/1,242 (1.00). The pacing fix
(VOI-024, merged) sheds silence at enqueue once the queued-minus-sent backlog
reaches 40 frames, never sheds speech, and adds the hop-3b wire counter
(`plugin_sent_audio_events`) to the F2 journal line. This run proves that fix
live, plus greeting onset, on a calm box. The run uses the
`FRIDAY/voice_acceptance/` probe caller (participant + `run_acceptance.sh`,
proven end-to-end by Muse 13 in TASK-FRG-020) against the deployed FRIDAY-Voice
worker on FRIDAY-Server. Route: bridge `run_shell` on server 2, SSH to
FRIDAY-Server.

## 2. Stop-order / clearance check

- Owner stop order ~16:42 IST Nov 24 froze ALL server moves; partial lift 17:26 IST
  covers ONLY (1) key architecture, (2) bridge work, (3) the Inference move.
- The voice-probe leg is NOT a server move: coordinator ruling 7126818611
  (Nov 24 ~13:52 IST): acceptance host is FRIDAY-Server; VOI-030/035 hold LIFTS.
  Runs 19 (VOI-034), 20 (VOI-035), 21 (VOI-036) and 18 (VOI-033) executed the
  identical leg and MERGED.
- Clearance for THIS run is settled twice over: Burn Enforcer 13:00 §G and
  WATCH210-CORR §5 both rule VOI-030 an own-task live acceptance run covered by
  standing clearance 7200564540 — "run it, no further approval."

**Verdict: live leg callable as a read-only probe against FRIDAY-Server.** No
server moves, no installs, no restores, no deploys attempted.

## 3. Calm check 1 — 2026-11-27 ~13:09 IST (FRIDAY-Server, read-only, first-hand)

- Load average: **0.06 / 0.11 / 0.07** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, **1214 MB available**.
- **FRIDAY.service: active, NRestarts 0**, MemoryCurrent 38,989,824 / 209,715,200
  — **18.6% of its 200 MB cgroup cap**, ActiveEnterTimestamp 2026-11-27 06:44:24
  UTC (the FRD-043 merged-guard worker, pid 89534).
- **FRIDAY-Voice.service: active since 06:03:19 UTC**, NRestarts 0,
  MemoryCurrent 234,176,512. **Inference.service: active.**
- **/health 200 in 1.95 s**; **/ready 200 in 1.08 s**; token endpoint
  `http://127.0.0.1:10000/api/livekit/token` 200 in 0.24 s.
- Voice status file: state `registered`, provider `pending`, detail "waiting for
  the first job", pid 87938, updated 06:03:24 UTC — no room, no run in progress.

**Verdict: CALM, no run in progress — launch.**

Preflight (same probe): all 7 `FRIDAY/voice_acceptance/` files byte-identical to
main `25ce04a3` (md5 MATCH: README.md `20f54293…`, battery.json `4e232958…`,
make_utterances.py `b6389bc7…`, participant.py `00989841…`, run_acceptance.sh
`90eb3cd0…`, score.py `597979d3…`, score_check.py `e7a06a8e…`); fleet venv imports
livekit/httpx/edge_tts and PyAV OK; voice worker alive (Gemini key keeper
refreshed 06:32 / 07:01 / 07:30 UTC); served page build `bEQg9SjqU5pOmYL47AybJ`
(changed from run 18's `fFKg6fXVVhWz4qvLQD0Pi` with the FRD-043 deploy checkout
`06ff9ee6` — expected); no participant running.

Context: the last run today, `20261127-042219` (TASK-FRD-005, 09:52–10:03 IST),
was overall FAIL — greeting 4.63 s PASS but 0 user finals for the 6 turns after;
it ran before the 06:03 UTC voice restart. Run 17 is the first voice job since
that restart.

## 4. The run — room `friday-frd005-20261127-074037`

- Launched 07:40:37 UTC (13:10:37 IST), detached (`nohup bash run_acceptance.sh`,
  output to `/tmp/frd005/voi030-launch.log`, pid 93503). Call 07:40:38–07:52:09 UTC
  (~11.5 min). Agent `agent-AJ_AJA8VRJi7Kx5` joined ~1 s after connect; both agent
  tracks published.
- Provider: `gemini-realtime:gemini-3.8-live` (status file `ready`, updated
  07:40:39 UTC). Host stayed calm: load 0.62 mid-run, 0.04 after.
- Artefacts: `/tmp/frd005/runs/20261127-074037/` on FRIDAY-Server (timeline,
  journal.txt 163 lines / 38,677 B, results.json, results.md, status.json,
  utterances manifest, 66.6 MB agent WAV — stays on the server, not fetched).
  Local logs: `~/workspace/voi-030/logs/`.

## 5. Results — per-probe latency + content (scorer + first-hand journal read)

Scorer overall: **UNVERIFIED** — sole reason is the memory_remember window (see
below). First-hand journal read overturns it on content: every turn's answer IS
in the journal.

| # | Turn | Gap (s) | Limit (s) | Heard (STT) | FRIDAY's answer | Verdict |
|---|------|---------|-----------|-------------|-----------------|---------|
| 0 | greeting | 0.58 | 8.0 | — | (agent spoke) | PASS |
| 1 | delegation_stratex | -7.59 | 12.0 | "Friday, check Stratex for me. What is the balance? How many open positions are there? And how many closed trades are in the ledger?" | "The Stratex demo account balance is 10,450.58, with 30 open positions and 84 closed trades in the ledger. Please note that live trading remains blocked by the fail-closed guard." | PASS |
| 2 | context_followup | -2.50 | 4.0 | "And how many closed trades was that, exactly?" | "There are exactly 84 closed trades recorded in the ledger." | PASS |
| 3 | clock_tokyo | -1.95 | 4.0 | "What time is it in Tokyo right now?" | "It is currently 4:47 PM in Tokyo, Japan." | PASS |
| 4 | memory_remember | -3.96 | 6.0 | "Please remember this for me. My favorite color is teal." | (scorer: empty window — see §6) | UNVERIFIED (scorer) / PASS (journal) |
| 5 | memory_recall | -1.55 | 5.0 | "What is my favorite color?" | "Your favorite color is teal." | PASS |
| 6 | goodbye | -2.73 | 4.0 | "That is all for now. Goodbye." | "Goodbye! Have a productive day ahead." | PASS |

Negative gaps mean the agent began speaking before the participant finished
playing the utterance (agent_start precedes utt_end) — the harness's gap metric
as measured, identical in shape to runs 18/24; all inside limits.

- **Greeting onset: 0.58 s vs the 8 s bar — PASS.** Worker decomposition
  (journal 07:40:40.226 UTC): job-to-connect 0.12 s, connect-to-key 0.00 s,
  key-to-participant 0.01 s, participant-to-gate 0.30 s, gate LISTENING after
  0.00 s, **connect-to-first-audio 0.31 s**. First fixed-line audio starting
  0.31 s after connect; fixed-line greeting played 07:40:45.473 UTC.
- **Delegation is a genuine PASS** (balance 10,450.58, 30 open, 84 closed —
  journal line 84, 07:45:22.658 UTC). Followup count matches (84).
- **Teal recall verifies the Memora read path** (journal line 142, 07:50:05.582
  UTC) — 4th consecutive run.
- Greeting burst: speech 239.94 s of fixed-line greeting audio, no journal text
  for the burst — same shape as runs 18–21/24; content only in the agent WAV.
  First substantive assistant journal text: the delegation answer, 07:45:22 UTC.
- Every probe transcribed: all 6 user finals in the journal (heard_overlap 1.0,
  except remember 0.8 and recall 0.6 — both transcribed correctly).

## 6. memory_remember — scorer UNVERIFIED is an attribution artefact

- 07:49:00.953–955 UTC: user final transcribed, "Please remember this for me. My
  favorite color is teal." (final=True, journal lines 112–115).
- 07:49:00.967 UTC: brain bridge dispatched turn `b2-295301` (line 118).
- **07:49:15.830 UTC: assistant answered, "Got it, Boss — locked in: My favorite
  color is teal. That's mine to keep now, it's pinned and it never fades."**
  (journal lines 128–129).
- The answer arrived 15 s after the user final and sits in the journal — the
  scorer's turn window missed it because answers arrived out of order (its own
  alignment note: "DEGRADED — answers arrived out of order"). Content is
  genuinely PASS on first-hand read; the recall PASS 50 s later confirms the
  memory stuck.

## 7. Sent-vs-queued counters — the pacing fix is PROVEN

Session-end frame counters (journal lines 160–161, 07:52:09.697 UTC):

```
VOICE frame counters [session build 1]: activity_push_audio=13793
plugin_push_audio=13793 plugin_send_audio_events=13792
plugin_sent_audio_events=13778 plugin_shed_silence_events=0
(session end (job close))
```

- Queued for the wire (`plugin_send_audio_events`): **13,792**.
- Actually sent (`plugin_sent_audio_events`, hop 3b): **13,778**.
- **Sent / queued = 0.999** — essentially everything queued reached Google.
  Run 16's LOW arm was 380/577 = **0.66** (convicted). No send-cadence collapse.
- `plugin_shed_silence_events=0` — the backlog never reached the 40-frame shed
  threshold; no shedding was needed.
- Input side consistent: `activity_push_audio` = `plugin_push_audio` = 13,793.

## 8. Observations (reported plainly, no impact on the verdict)

- **FRIDAY.service restarted mid-run, 07:51:14–15 UTC, during the goodbye turn.**
  Graceful stop (`systemd: Stopping FRIDAY.service`, "Graceful shutdown
  completed", "Deactivated successfully") then start; old worker pid 89534 →
  new pid 95071; NRestarts stays 0 (stop+start, not a crash-restart). The old
  worker consumed **200.0 M memory peak (= the cap)** and 182.0 M swap peak;
  the guard had warned at 81.2% (162.4 MB) at 07:48:14 and recovered below 60%
  at 07:48:46. An SSH session from the bridge host (140.245.243.168) opened
  07:51:00 and closed 07:51:03, 11 s before the stop — **actor unidentified**
  (not this run: no bridge call of mine ran 07:49:57–07:54:11, and no systemctl
  command was issued by this run). No OOM kill in dmesg after 06:21 UTC;
  `memory.events` oom_kill 0 in the new cgroup. **Impact on run 17: none
  visible** — goodbye answered, session closed cleanly 07:52:09 UTC.
  Relevance: FRD-064 (next task) — the worker hit the 200 MB cap mid-session
  and the service cycled; the volatility is confirmed live again. Flagged to the
  coordinator in the completion post; the coordinator/M10 can confirm whether
  the 07:51:00 SSH session was the VAL-001 fleet re-probe.
- **Stale DB connection at job start** (journal line 2, 07:40:39.799 UTC):
  SQLAlchemy QueuePool "Exception terminating connection
  <oracledb.Connection disconnected>" — a dead pooled connection discarded;
  DB-backed turns (delegation, memory) all worked after. No impact.
- Post-run calm check 2 (~13:25 IST): load 0.04; FRIDAY.service active, new pid
  95071, MemoryCurrent 174,657,536 / 209,715,200 (83.3% — the fresh worker was
  already climbing); FRIDAY-Voice.service active, NRestarts 0; status file
  `closed`, room `friday-frd005-20261127-074037`, updated 07:52:09 UTC.

## 9. Verdict

**ACCEPTANCE PASS — greeting onset 0.58 s vs the 8 s bar; every probe
transcribed; all 7 latencies inside limits; sent/queued 0.999 proves the pacing
fix; all 6 turns content-PASS on first-hand journal read (the scorer's
UNVERIFIED is an attribution artefact, §6).**

Voice status remains NOT WORKING until the owner re-tests and accepts. No code
shipped; evidence doc only. No board hunks in this PR — board flips are
coordinator-only (ruling 7200564540 §3). Paired verification and merge are
Muse's. Next: TASK-FRD-064.

— Muse 1
