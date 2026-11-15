# FRIDAY voice acceptance harness (TASK-FRD-005)

A repeatable, scripted acceptance test for FRIDAY's voice — built so
"voice works" is a measurement, not an impression. A server-side
participant joins a real LiveKit room through FRIDAY's production
token endpoint, speaks a fixed battery of prompts, and the run is
scored on **speed first** (the owner's criterion, 2026-11-15): a
correct answer after a long silence is a FAIL.

## The battery (`battery.json`)

| # | Turn | What it proves | Silence limit |
|---|------|----------------|---------------|
| 0 | greeting (FRIDAY speaks first) | warm pool + session setup | 8.0 s |
| 1 | Stratex delegation | tool delegation with real figures | 12.0 s |
| 2 | context follow-up ("how many closed trades was that?") | conversation context; the count must match turn 1's answer | 4.0 s |
| 3 | clock (Tokyo) | deterministic fast path | 4.0 s |
| 4 | memory remember ("my favourite colour is teal") | Memora write path | 6.0 s |
| 5 | memory recall | Memora read path; answer must contain "teal" | 5.0 s |
| 6 | goodbye | clean close | 4.0 s |

Thresholds are declared in `battery.json` with their calibration
evidence (VOI-005/006/007/008 measurements). They were fixed before
the first post-VOI-009 run and must not be tuned after seeing
results — changing them requires a `battery_version` bump and a
note in the run report.

## Provider contract (post TASK-VOI-009)

Voice is Gemini Live only. The scorer reads the serving provider
from the worker status file and scans the run's journal window: any
line showing a Groq/Whisper/Orpheus **serving** path is an automatic
FAIL, whatever the latencies say.

## Files

- `battery.json` — prompts, thresholds, content checks (the contract).
- `make_utterances.py` — renders the prompts once with edge-tts
  (voice/rate pinned), converts to 24 kHz mono WAV, writes a sha256
  manifest; re-runs reuse byte-identical WAVs.
- `participant.py` — the LiveKit participant. Reply-end detection
  requires ≥0.8 s of speech **and** ≥2.0 s of continuous silence:
  the VOI-007 participant's weaker detector talked over FRIDAY and
  Gemini's interruption cancelled ~70% of a Stratex answer
  (proven in TASK-VOI-008) — this harness cannot repeat that.
- `score.py` — merges timeline + journal + status into
  `results.json` / `results.md` with per-turn verdicts.
  Exit codes: 0 PASS, 1 FAIL, 3 UNVERIFIED (missing evidence is
  never a pass).
- `score_check.py` — offline checks of the scorer's verdict logic
  (`python3 score_check.py`); covers the slow-delegation FAIL, the
  Groq-serving FAIL, count-mismatch FAIL, and the
  missing-evidence UNVERIFIED cases.
- `run_acceptance.sh` — one full run on Server 1: preflight,
  utterances, call, journal + status capture, scoring.

## Running it

On Server 1 (fleet venv, loopback token endpoint, journal access):

```bash
HARNESS_HOME=/opt/friday_universe/FRIDAY/voice_acceptance \
  bash /opt/friday_universe/FRIDAY/voice_acceptance/run_acceptance.sh
```

Artefacts land in `/tmp/frd005/runs/<run-id>/`: timeline, agent
audio WAV, journal window, status snapshot, `results.md` table.
Report the table with the run's host context (load average is in
the runner output) — a slow run under a loaded 956 MB host is a
different fact from a slow run on an idle one, and both are
reported, never hidden.
