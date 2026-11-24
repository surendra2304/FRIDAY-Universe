# TASK-FRG-020 — LiveKit probe-caller tool: pointer or ship?

**Worker:** Muse 13. **Claim:** hub #1483 comment 7111211961, 2026-11-24 ~00:41 IST,
under the blocked-head rule (VOI-030 blocked on calm-window call; REL-089 in
review, PR #1539). **Branch:** `muse13/task-frg-020-livekit-probe-caller`
from main `49126a41`. **Claim PR:** #1549 (head `0dc6bc3f`, board-only,
mergeable true). **Board:** main `49126a41`, blob `fe731e7d`, 761 tasks;
FRG-020 verified AVAILABLE, owner `muse_13`, no branch/PR before claiming.

## 1. The question

Acceptance: *"Probe-caller tool shipped with live proof, or the existing
pointer filed with evidence."*

The record (drafted by the coordinator 2026-11-23 ~19:20 IST, consolidated
board PR watch13; standing backlog pool-7 (viii) continuation; Muse 6
blocked-tool candidate from FRG-001) says: *"Forge: confirm + ship the
missing LiveKit probe-caller tool Muse 13 named, or file the pointer if it
exists."*

My earlier claim, made while scoping VOI-030 (acceptance run 17), was that
*"no self-service LiveKit probe caller exists in the repo"* — the run would
have to harvest journal lines after an owner call. That claim is the thing
being tested here. If the tool exists, the pointer gets filed; if it is
missing or broken, it gets shipped (or repaired) with live proof.

## 2. What exists on main: FRIDAY/voice_acceptance/ (TASK-FRD-005)

A complete, server-side LiveKit probe caller already lives in the repo:

| File | Role |
|---|---|
| `FRIDAY/voice_acceptance/participant.py` | LiveKit participant: GETs a token from FRIDAY's production token endpoint (`http://127.0.0.1:10000/api/livekit/token`), joins a fresh room, stays silent for the greeting (240 s cap, INVALID not a battery played into an unready session), speaks the battery's pre-rendered WAVs, records agent audio with wall-clock timestamps, writes `<room>_timeline.json` + `<room>_agent.wav`. Exit 0 = call completed, 2 = infra failure. Reply-end detection is conservative (>= 0.8 s speech AND >= 2.0 s continuous silence) per the VOI-007/008 lesson. |
| `FRIDAY/voice_acceptance/run_acceptance.sh` | One full run on Server 1: preflight, utterances, call, journal + status capture, scoring. Exit code is the scorer's (0 PASS, 1 FAIL, 3 UNVERIFIED, 2 infra). |
| `FRIDAY/voice_acceptance/battery.json` | 7-turn battery (greeting + Stratex delegation + context follow-up + Tokyo clock + memory remember/recall + goodbye) with pre-declared thresholds and calibration evidence (VOI-005/006/007/008). |
| `FRIDAY/voice_acceptance/make_utterances.py` | Renders prompts once with edge-tts (voice/rate pinned), 24 kHz mono WAV, sha256 manifest; re-runs reuse byte-identical WAVs. |
| `FRIDAY/voice_acceptance/score.py` | Merges timeline + journal + status into `results.json` / `results.md` with per-turn verdicts. Speed first; Gemini-Live-only provider enforcement. |
| `FRIDAY/voice_acceptance/score_check.py` | Offline checks of the scorer (clean pass, slow-delegation FAIL, slow-greeting FAIL, Groq-serving FAIL, count-mismatch FAIL, wrong-recall FAIL, out-of-order degraded). |
| `FRIDAY/voice_acceptance/README.md` | Full runbook; run 1 (2026-11-15, room `friday-frd005-20261115-160000`) lessons documented. |

The participant takes `--battery`, so a custom battery (e.g. a VOI-030
pacing/greeting battery) can be driven through the same caller — the tool
is not locked to the FRD-005 turns.

## 3. Contract checks on main 49126a41 (code review, first-hand)

1. **Token endpoint exists and dispatches the agent.**
   `FRIDAY/src/friday/api/server.py:1841` `@app.get("/api/livekit/token")`;
   lines 1895-1896 mint `api.RoomConfiguration(agents=[api.RoomAgentDispatch(agent_name=voice_agent_name)])`
   with explicit dispatch creation at line 1915. Unit tests
   `FRIDAY/tests/test_livekit_token.py`: 503 unconfigured, 400 invalid
   params, 200 with JWT (`server_url` + `token`), which is exactly the
   shape `participant.py` reads (`url` / `ws_url` / `server_url`).
2. **Worker registers under the dispatched name.**
   `FRIDAY/src/friday/voice/livekit_worker.py:5328` `_agent_name()` returns
   `"friday"`; the docstring states the dashboard token carries
   `RoomAgentDispatch(agent_name="friday")` so joining a room
   deterministically dispatches this worker. `cli.run_app(_worker_options())`
   at line 5434. Service `deploy/FRIDAY-Voice.service` runs
   `/opt/friday_universe/venv312/bin/python src/friday/voice/livekit_worker.py start`.
3. **Journal formats match the scorer's regexes.**
   `livekit_worker.py:3932-3935` logs `VOICE user_input_transcribed final=%s text=%r`;
   lines 3980-3984 log `VOICE conversation_item_added role=%s text=%r`.
   `score.py` parses `user_input_transcribed final=True text='(.*)'` and
   `conversation_item_added role=assistant text='(.*)'`. GitHub code search
   confirms both strings still appear only in the worker, the scorer and its
   checks — no drift.
4. **Staleness note.** `FRIDAY/voice_acceptance/` was last touched
   2026-11-15 (commits `08564e5a`, `d86cf1be` — harness + PyAV/run-1
   fixes). Since then the voice stack moved (VOI-028 greeting-onset fix,
   OBS-011 /health alias, FRIDAY restarts, ORCH-014 endpoint fix). Code
   review finds no contract break, but a live run is the only proof the
   harness still works against the deployed worker — see §4.

## 4. Live verification (S1, read-only first)

Checks run via the bridge (read-only; no writes, no restarts):

1. **S1 checkout contains `FRIDAY/voice_acceptance/` — VERIFIED 2026-11-24
   ~00:53 IST** (bridge `run_shell`, server 1): S1 git branch `main`,
   commit `49126a41`; `ls FRIDAY/voice_acceptance/` shows all 7 harness
   files (README.md, battery.json, make_utterances.py, participant.py,
   run_acceptance.sh, score.py, score_check.py). Note: S1 is 2 merges
   behind GitHub main `0dd136cb` (#1545 board PR + #1533 STR-046); neither
   touches voice code, and the harness files are unchanged since
   2026-11-15, so the lag does not affect the harness.
2. **Fleet venv deps — VERIFIED same run:** `/opt/friday_universe/venv`
   imports `livekit, httpx, edge_tts, av` (prints `venv ok`);
   `/opt/friday_universe/venv312` likewise (`venv312 ok`). So
   `run_acceptance.sh`'s default `VENV_PY` (`/opt/friday_universe/venv`)
   and the service venv both carry the harness deps.
3. **FRIDAY (port 10000) up — VERIFIED 2026-11-24 ~00:54 IST**
   (bridge `oracle_check_service`, agent `friday`): FRIDAY.service
   active (running) since 2026-11-24 00:00:01 IST, Main PID 3187196,
   `uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1`,
   Memory 12.1M (max 200M). Logs show `GET /health 200 OK` repeatedly
   and the autonomous daemon alive. (Also a RAM warning at 00:38 IST:
   90.3% RAM; and one external `GET /api/chat 404` — not this task's
   concern.) The token endpoint itself is exercised by the live probe
   run (§4.5) rather than minted separately.
4. **`FRIDAY-Voice` active — VERIFIED same window** (bridge
   `oracle_check_service`, agent `friday-voice`): FRIDAY-Voice.service
   active (running) since 2026-11-23 23:43:10 IST, Main PID 3179089,
   `livekit_worker.py start`, Memory 151.3M (max 300M). Logs show the
   Gemini key resolved/cached and refreshed by the key-keeper loop, and
   a Gemini `generate_content` call at 00:43:08 IST — the worker is
   alive and doing Gemini work. Footnote: the live process runs from
   `/opt/friday_universe/venv/bin/python` while the repo service file
   names `venv312`; both venvs carry the harness deps, so this does not
   block the run (worth a footnote to Muse, not a repair here). S1
   load 2.53/2.19/2.65 at ~00:47 IST — loaded, not a calm window; the
   probe run's latencies will be load-conditioned (see §4.5).
5. **Live probe run — COMPLETED** — full FRD-005 battery via
   `run_acceptance.sh` on S1 (run `20261124-005937`, room
   `friday-frd005-20261124-005937`), launched ~00:59 IST, finished
   01:23 IST. All 7 turns ran live: token minted, agent `friday`
   dispatched and joined, greeting answered (gap 6.41 s, PASS),
   all 6 probes played, agent audio recorded throughout
   (67.9 MB agent WAV), timeline + journal + status captured,
   scorer produced `results.json` / `results.md`. The caller is
   proven end-to-end on the call leg.
   - **Overall scorer verdict: FAIL** — greeting PASS; 5 turns FAIL,
     1 UNVERIFIED on CONTENT only; every latency PASS. The failure
     is not the caller: the scorer found **0 user finals and no
     assistant items** in the journal window, so every content check
     had nothing to score (`heard` and `answer` empty on all 6
     turns).
   - **Why the journal was empty:** the worker logged zero
     `user_input_transcribed` lines in the whole run window and a
     single empty `conversation_item_added role=None text=''` event
     (01:00:33 IST). Journal (`journal.txt`, 71 KB, 01:00:27–01:21:22
     IST — window correct) shows the cause: `livekit.plugins.google
     error in receive task: 1008 … Session closed due to client
     inactivity` at 01:02:40 IST, ~2 min into the call, during the
     greeting monologue. The first probe was not spoken until
     01:04:32 IST — after the Gemini receive task had died — so no
     probe was ever transcribed. The logging code path itself is
     live (the one empty item came from `livekit_worker.py:3983`,
     the line §3.3 cites); it received no transcription events.
   - **Agent turn-taking broken (worker-side, recorded faithfully
     by the caller):** greeting speech 235.15 s; per-turn agent
     speech 61–126 s; the agent started speaking BEFORE each probe
     finished playing (agent_start < utt_end on all 6 turns), so all
     gaps are negative (−8.41 … −2.08 s). The caller measured a
     misbehaving agent correctly — the negative gaps are evidence,
     not a caller bug.
   - **Teardown hiccup, survived:** after the last turn (01:12:11
     IST) the participant hit a LiveKit disconnect (`signal client
     closed: "ping timeout"`, SDK resuming, attempt 1) and had not
     exited by 01:19 IST; it exited on its own, timeline written
     01:20, scoring done 01:23. No manual intervention.
   - **Scope note:** this run proves the TOOL; its content FAIL is
     a property of this degraded worker session, NOT an acceptance
     verdict for any task — VOI-027/VOI-030 still need their own
     calm-box runs, and content scoring needs the transcription gap
     (below) fixed first.
   - **Observation gap, closed:** bridge transport was down
     01:29–01:35 IST (two session-init timeouts; other workers
     reported the same). Bridge recovered ~01:44 IST; all run
     artefacts were read first-hand from S1 after recovery. The run
     itself was unaffected — only observation was blocked.

Bridge transport was slow/flaky on the night of 2026-11-23/24 (coordinator
watch 7110882697); bridge calls take ~3 min each when degraded, seconds
when healthy.

## 5. Verdict — POINTER (tool exists, proven; gaps filed)

**File the pointer. Do not ship a new tool.** The LiveKit probe caller
already exists and works end-to-end on the call leg, proven live by run
`20261124-005937`:

- **What:** `FRIDAY/voice_acceptance/` on main — `participant.py`
  (LiveKit participant, token from FRIDAY `:10000/api/livekit/token`,
  `--battery` flag takes any battery), `run_acceptance.sh` (one full
  run on S1, artefacts in `/tmp/frd005/runs/<run-id>/`),
  `battery.json` (7-turn FRD-005 battery), `make_utterances.py`
  (edge-tts, pinned voice/rate, sha256 manifest), `score.py` +
  `score_check.py`, `README.md` (runbook; run 1, 2026-11-15).
- **How to run:** on S1, `HARNESS_HOME=/opt/friday_universe/FRIDAY/voice_acceptance bash run_acceptance.sh`
  (defaults: `VENV_PY=/opt/friday_universe/venv/bin/python`,
  `WORK_DIR=/tmp/frd005`). Exit code is the scorer's (0 PASS, 1 FAIL,
  3 UNVERIFIED, 2 infra). A custom battery (e.g. a VOI-030
  pacing/greeting battery) runs through the same caller via
  `--battery`.
- **Live proof:** run `20261124-005937` (2026-11-24 00:59–01:23 IST,
  room `friday-frd005-20261124-005937`): token mint, agent join,
  greeting 6.41 s PASS, 6 probes played, 67.9 MB agent audio
  recorded, timeline/journal/status captured, scoring produced.
  Artefacts on S1 at `/tmp/frd005/runs/20261124-005937/`
  (`results.md`, `results.json`, `<room>_timeline.json`,
  `<room>_agent.wav`, `journal.txt`, `status.json`).
- **Correction to my VOI-030 scoping claim:** "no self-service
  LiveKit probe caller exists in the repo" was wrong — the harness
  has existed since 2026-11-15 (TASK-FRD-005). VOI-030 acceptance
  run 17 can be self-served through it once the gaps below are
  addressed; no owner call needs to be waited on for the caller.

**Gaps found (not caller defects — routed, not fixed here):**
- G1 — Content scoring blind on live runs: the worker session
  produced no transcription log lines (Gemini receive task died
  01:02:40 IST, "Session closed due to client inactivity"; the
  participant stays silent during the greeting by design, and the
  session died before the first probe). Until the worker reliably
  emits `user_input_transcribed` / `conversation_item_added` with
  content, the scorer can only verdict latency/speech, not content.
  Needs a worker-side diagnosis (VOI/OBS queue), not a caller fix.
- G2 — Agent turn-taking: 235 s greeting monologue, 60–126 s
  per-turn monologues, agent talks over probes. VOI-027/VOI-028
  territory; the caller records it faithfully.
- G3 — LiveKit `ping timeout` disconnect near teardown; the
  participant survived it (SDK resume) and completed. Worth a
  footnote; no repair in this task.
- G4 — Minor: the live `livekit_worker.py` process runs from
  `/opt/friday_universe/venv/bin/python` while the repo service
  file names `venv312`; both venvs carry the harness deps, so this
  does not block runs.

## 6. Filing status

- Verdict + evidence complete in this doc 2026-11-24 ~01:55 IST.
- Claim PR #1549 merged (board AVAILABLE -> CLAIMED); board on main
  14fc9650 shows FRG-020 MERGED (coordinator board PR #1591).
- Work PR (this PR): evidence doc + additive-only board edits
  (files/evidence/next_action) — no status flip, following the
  REL-093 #1594 pattern. Filed from main 14fc9650.

## 7. What this unblocks

- VOI-027 (Muse 6) and VOI-030 (Muse 13): acceptance runs become
  self-service — run the caller on a calm box instead of waiting for a
  reported owner call.
- FRG-001 (Muse 6): "ship the first tool another agent is blocked on" —
  this is that tool.

— Muse 13
