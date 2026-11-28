# TASK-VOI-029 — Checkpoint 2: session plan (M5 workflow 5, 3 consecutive live voice sessions)

- Task: TASK-VOI-029 — Voice: prove M5 workflow 5, 3 consecutive live voice sessions (consumes the VOI-027 verdict)
- Owner: muse_6. Branch: `muse6/task-voi-029-m5-three-live-sessions`. Base: main `dfa2e8a9` (2026-11-27).
- Filed: 2026-11-28 ~14:30 IST, per coordinator ruling WATCH263 §D.2 (hub #2045 comment 7236357595): "file the session plan NOW as a repo deliverable — it needs no live call. Live sessions still await the VOI-027 calm-window verdict." Adopted BE 13:45 §C and BE 14:00 §C (demand: file now or post a one-line block by next run, or VOI-029 re-slots — filed now, no block needed).
- Five states: implemented NO / tested NO / merged NO / deployed NO / production-verified NO (claim + scoping + plan only; no live session run yet).
- Checkpoint 1: `docs/collaboration/TASK-VOI-029-CHECKPOINT-1.md` (branch @ `462d9870`, commit `ac580308`).

## 1. Acceptance (board, live main `c339c31b`, read first-hand this run)

- "Three consecutive live voice sessions with FRIDAY (speak, be understood, get spoken answers), each recorded with its trace and per-probe latency; a session that fails to converse resets the count. If the VOI-027 calm-window verdict is negative, fix the cause first and re-prove."
- M5 definition (`docs/MASTER_PLAN.md` §M5): a workflow counts as proven only after **3 consecutive successful live runs on production, each recorded with its trace** (request, routing, agent evidence, result) in ACTIVITY_LOG/handoff records. A silent failure — a wrong answer presented as success, a dropped result, a fabricated status — resets that workflow's count.
- Board record this run: VOI-029 CLAIMED/muse_6, branch `muse6/task-voi-029-m5-three-live-sessions`, pr null, P1. VOI-027 CLAIMED/muse_6 (queue position 2).

## 2. What one session is (fixed, no tuning at run time)

One session = one pass of the shipped voice acceptance harness, `FRIDAY/voice_acceptance/` (read first-hand on live main `c339c31b`):

- Runner: `FRIDAY/voice_acceptance/run_acceptance.sh`, run ON Server 1 (uses the loopback token endpoint and the FRIDAY-Voice journal). A server-side participant joins a real LiveKit room through FRIDAY's production token endpoint and speaks the fixed battery; artefacts land in `/tmp/frd005/runs/<run-id>/` (room `friday-frd005-<run-id>`).
- Battery: `FRIDAY/voice_acceptance/battery.json` v1, declared 2026-11-15, thresholds fixed before the first post-VOI-009 run — **must not be tuned after seeing results** (a change needs a `battery_version` bump and a note in the run report). 7 turns, speed first (owner's criterion):

| # | Turn | Proves | Silence limit |
|---|---|---|---|
| 0 | greeting (FRIDAY speaks first) | warm pool + session setup | 8.0 s |
| 1 | delegation_stratex ("FRIDAY, check Stratex for me…") | tool delegation with real figures | 12.0 s |
| 2 | context follow-up ("how many closed trades was that, exactly?") | conversation context; count must match turn 1 | 4.0 s |
| 3 | clock_tokyo ("What time is it in Tokyo right now?") | deterministic fast path | 4.0 s |
| 4 | memory_remember ("My favourite colour is teal.") | Memora write path | 6.0 s |
| 5 | memory_recall ("What is my favourite colour?") | Memora read path; answer must contain "teal" | 5.0 s |
| 6 | goodbye | clean close | 4.0 s |

- Utterances are synthesised once by `make_utterances.py` (edge-tts, voice/rate pinned) and cached; the sha256 of every WAV is recorded in the run manifest, so every run speaks byte-identical prompts.
- Scoring: `score.py` merges timeline + journal + status into `results.json` / `results.md` with per-turn verdicts. Exit codes: **0 PASS, 1 FAIL, 3 UNVERIFIED** (missing evidence is never a pass), **2 infrastructure failure** (participant could not complete the call). Provider contract: Gemini Live only — any Groq/Whisper/Orpheus **serving** path in the journal is an automatic FAIL.
- Precedent: M1 VOI-030 run-17 (PR #2100, VERIFIED review 6085510230) ran this harness — greeting 0.58 s < 8 s bar, all 7 latencies inside limits, all 7 preflight md5s re-derived exact.

## 3. Session verdict rule (count arithmetic)

- Scorer exit 0 → session PASS, count +1.
- Scorer exit 1 → session FAIL, count resets to **0**. The reset and its cause are filed, not hidden.
- Scorer exit 3 (UNVERIFIED) or 2 (infrastructure failure) → session VOID, count unchanged, re-attempt. A void is not a pass and not a reset.
- Three consecutive PASS (count 3/3) = M5 workflow 5 proven. "Consecutive" is consecutive in count, not wall-clock time (checkpoint 1 §3.3, as read).
- A session that fails to converse (no spoken answer, dropped call, wrong-path serving) is a FAIL under exit 1, per the acceptance — it resets the count.

## 4. Entry gates (checked before each session, filed with the session record)

1. **VOI-027 gate (STILL OWED):** live sessions still await the VOI-027 calm-window verdict (WATCH263 §D.2). The verdict stands NOT RUN (hub 7208389980, filed 2026-11-27 08:08 IST). If it lands negative, fix-first per the acceptance before the count can stand. If the coordinator rules VOI-029 may proceed on the harness participant without it, that ruling is filed here and the gate is met by the ruling — no session starts on an assumed ruling.
2. **Calm box:** no FRIDAY OOM kill in the preceding cycle and `/health` 200 on :10000 immediately before the run. Current state (this run): **NOT MET** — TP1 FRD-064 checkpoint 22 (hub 7236153523): kills #43/#44/#45 in 33 min, tally 45; FRD-064 fix ruling still owed. VOI-046 (malloc_trim fix, M14) PR #2305 is IN_REVIEW; deploy HELD until it merges with a paired VERIFIED (WATCH263 §D.4).
3. **Service preflight** (the harness's own checks): `FRIDAY-Voice` active; fleet venv has `livekit`, `httpx`, `edge_tts`; PyAV or an ffmpeg binary present. Any preflight failure is exit 2 — session void, not a run.
4. **Server-move freeze:** WATCH174 (a) still stands — a session needing a restart or re-sync needs separate clearance.

## 5. §3.1 who speaks — decision owed, plan written so either answer works

- The harness participant speaks (synthesised TTS, byte-identical prompts) — the session does **not** need Surendra to speak. That is how the VOI-030 precedent runs were executed.
- **Open ruling (coordinator):** does the M5 workflow-5 proof accept participant-driven sessions, or is at least one owner-spoken session required? The VOI-027 acceptance needs Surendra's call; whether VOI-029 does is UNVERIFIED (checkpoint 1 §3.1).
- **Recommendation (not a ruling):** run sessions 1–3 on the harness participant; if the coordinator requires an owner-spoken session, it replaces session 3 (same battery, same scoring, same trace capture) or is filed as the acceptance-grade session after the 3/3 count. The plan, probe set, scoring, and evidence shape are identical either way — the ruling changes only who speaks, not what is measured.

## 6. §3.2 probe commands + trace capture route

- **Probe commands:** the battery itself — `battery.json` v1, run by `run_acceptance.sh` (see §2). No per-session ad-hoc prompts: the fixed battery is the probe set, so sessions are comparable and the count is meaningful.
- **Run command (Server 1, coordinator-side):** `HARNESS_HOME=/tmp/frd005/harness bash run_acceptance.sh` (harness staged from `/opt/friday_universe/FRIDAY/voice_acceptance` or the repo checkout; artefacts in `/tmp/frd005/runs/<run-id>/`).
- **Trace capture:** per-run artefacts — `<room>_timeline.json`, `journal.txt` (`journalctl -u FRIDAY-Voice.service --since <start>`), `status.json` (`/opt/friday_universe/FRIDAY/data/voice_worker_status.json`), `results.json` / `results.md`, `utterances_manifest.json`. Filed per session as `docs/collaboration/TASK-VOI-029-SESSION-n.md` + the results files in the work PR, and recorded in ACTIVITY_LOG/handoff records per M5.
- **Route:** live legs are coordinator-side via bridge `run_shell` under standing clearance 7200564540 (grant settled per WATCH224 §C / WATCH230 §C.5 context). **No bridge route from this VM** — no bridge client copy and no bridge key here; per-sandbox registration is the alternative (TP6 7211823359; M16 failed 403). The operator holding the live leg confirms the exact run command at run time; this plan does not invent a route.
- **Limits (carried):** the live journal on FRIDAY-Server cannot be re-derived from this VM — taken as filed by the operator, as in the VOI-030 precedent.

## 7. Per-session evidence record (what counts)

Per session, filed before the next session starts:

- Session identity (date/time, run number 1–3, count state before/after), run id + room, speaker (harness participant or owner — see §5).
- The spoken request per turn (battery ids 0–6) and FRIDAY's spoken answers; whether the session conversed end-to-end.
- Per-probe latency table (turn, threshold, measured, pass/fail) + scorer exit code and `results.md` verdict.
- Trace locations (timeline, journal, status, results) + pre-session gate checks (§4: VOI-027 verdict state, OOM-kill check, /health, preflight).
- Session verdict (PASS / FAIL / VOID) and the count after it. A FAIL names its cause.

## 8. Blockers and risks (stated, not solved here)

- FRIDAY stability: FRD-064 tally 45 (checkpoint 22, kills #43–45 in 33 min, ~16-min cadence) — a mid-session kill fails that session and resets the count. The VOI-046 fix (PR #2305) is the path out; deploy is HELD until merge + paired VERIFIED.
- VOI-027 calm-window verdict still owed (call by Surendra only; P0 voice-note ruling WATCH094 still owed). Sessions do not start until §4 gate 1 is met by verdict or ruling.
- No live move from this VM (see §6). Checkpoint 2 is the plan; live sessions are owed coordinator-side or once a route is settled.

## 9. Next

- Session 1 attempt once §4 gates are met (VOI-027 verdict or ruling + calm box + preflight). Sessions 2–3 follow on consecutive PASS; any FAIL resets to 0 and is filed.
- Work PR follows this checkpoint (this doc is the deliverable; paired verification + merge are the coordinator's call).
- Hourly self-check 15:08 IST; VOI-027 calm-window watch continues (next check 15:08 IST, queue position 2).

— Muse 6, 2026-11-28 ~14:30 IST
