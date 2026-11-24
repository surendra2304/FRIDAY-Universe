# TASK-VOI-032 — Background-noise interruption defect

**Task:** Voice — FRIDAY stops mid-answer when fan or room noise hits the
microphone. Reproduce with a noise-injected probe, root-cause (VAD/barge-in
threshold or send-path), fix, and prove with calm-vs-noise A/B evidence that
she finishes her answers under noise without losing real barge-in. Speed
stays the headline metric (8 s greeting-onset bar from VOI-028 still
applies).
**Claim:** hub #1483 comment 7123027488 by Muse 2, 2026-11-24 ~10:58 IST.
Branch `muse2/task-voi-032-background-noise-interruption` from main
`bc303ea0`. Claim PR #1630 (board-only flip AVAILABLE → CLAIMED).
**Status:** implemented, in review. Live calm-vs-noise A/B still owed
(see §7).

## 1. The defect (production evidence, already on file)

Owner live test, 2026-11-17 ~21:06 IST (FRIDAY-Voice journal, Server 1,
worker MainPID 3029461), recorded in the VOI-018 test docstring: ordinary
background noise — a fan — kept stopping FRIDAY mid-answer. Her
agent_state flipped speaking→listening at 21:07:00, :02, :05, :08, :10,
:13, :19 and :20 — speech segments of ~1–4.6 s separated by ~1 s
listening gaps, **≥9 interruptions in ~37 s**, each gap carrying a short
fragment transcript ('FRIDAY', 'Hi.', 'Irena', single Telugu words).
Non-speech room audio was being scored as user turns. VOI-018 fixed it
by flipping the AAD start sensitivity to LOW; VOI-024 reverted the
default to HIGH on the transcript-gap correlation. The defect is back
because the default is HIGH again — this task resolves the oscillation
instead of re-running it.

## 2. Reproduction (offline noise-injected probe, this task)

No live call was made for the reproduction: S1 was not calm at 11:00
IST (Muse 15 hub report, same morning), and the live leg needs a calm
window + coordinator clearance. The probe below is deterministic and
runs offline against the deployed pins (livekit-agents 1.8.11,
livekit-plugins-google 1.8.10, google-genai 2.33.0) in
`FRIDAY/tests/test_voice_noise_interruption_voi032.py`:

- **Config arm (the noise):** with no env override the worker builds
  `_realtime_input_config()` with start sensitivity HIGH and activity
  handling START_OF_ACTIVITY_INTERRUPTS. Pre-fix run of the new suite:
  the 4 default-sensitivity tests FAIL (HIGH where LOW is required),
  11 mechanism/guard/send-path tests pass — the defect is the
  default, not the guards.
- **Library arm (the cut):** a real `AgentSession` + `AgentActivity`
  built with the worker's exact session kwargs on a dummy-key model
  (construction is local, no network, no room):
  - `turn_detection` resolves to `realtime_llm`;
    `_rt_turn_detection_enabled` True;
    `_rt_overlapping_speech_enabled` False;
    `_interruption_by_audio_activity_enabled` False.
  - A **5 s VAD speech event** — far past the 0.8 s
    `min_interruption_duration` floor — produces **zero** interrupt
    calls under `realtime_llm`. Control arm: the same event under
    `"stt"` turn detection DOES interrupt, so the harness can see
    an interruption and the empty list is the library's branch,
    not a dead spy.
  - A server `input_speech_started` event (what Gemini's
    `server_content.interrupted` becomes) calls
    `interrupt(source="audio_activity")` unconditionally — no
    duration, transcript or energy check in between.
  - With `_rt_overlapping_speech_enabled` forced True the same
    event does NOT interrupt — the arm that would save her, which
    the deployed Google model cannot engage (capability False).

Local run (scratch venv, production pins): **15/15 pass** post-fix;
pre-fix the 4 default tests fail as above. Full affected set
(voi032 + voi018 + voi025 + fleet_terms + voi026 + voi028 +
voi024): **96 passed** locally.

## 3. Root cause

The interruption chain on the deployed configuration has exactly one
effective gate, and it was set to the noise-eager value:

1. **Browser mic** (`FRIDAY/ui/components/VoiceCall.tsx`) published
   with `setMicrophoneEnabled(true)` and no capture options — nothing
   upstream stated any noise attenuation for the fan noise.
2. **Gemini server-side AAD** (`_realtime_input_config` in
   `FRIDAY/src/friday/voice/livekit_worker.py`): start sensitivity
   HIGH + `START_OF_ACTIVITY_INTERRUPTS` (VOI-012 value, restored as
   the default by VOI-024). HIGH is maximum eagerness to treat any
   detected activity as speech onset. Fan noise crosses it.
3. **Plugin** (`livekit-plugins-google 1.8.10`, `realtime_api.py`):
   `server_content.interrupted` → `_handle_input_speech_started()`
   → emits `input_speech_started`, in both the active-generation
   and no-generation cases.
4. **Activity** (`livekit-agents 1.8.11`, `agent_activity.py`
   `_on_input_speech_started`): because overlapping speech is off,
   it calls `self.interrupt(source="audio_activity")` — terminal;
   the answer is truncated, not paused. `interrupt()` has no
   resume path on this route.
5. **The believed backstops do not exist on this path.** The local
   VAD gates are inert under `turn_detection="realtime_llm"`:
   `on_vad_inference_done` returns early for `realtime_llm` (and
   `manual`), and `_interrupt_by_audio_activity` returns early
   while server-side turn detection is on — so
   `min_interruption_duration=0.8`, `resume_false_interruption`
   and `false_interruption_timeout` never gate anything (proven
   in §2, not asserted from source). The client also cannot take
   turn-taking over: the Google model reports
   `can_disable_turn_detection=False` and
   `supports_overlapping_speech=False`.

Two findings that dissolve the VOI-018/VOI-024 oscillation:

- **The HIGH revert's premise is gone.** VOI-024 reverted on the
  correlation "every transcript-positive session ran HIGH, every
  zero-transcript run ran LOW" — but VOI-024's own diagnosis then
  convicted the real transcript mechanism, **send-path pacing**
  (the plugin's send task delivered ~15.2 audio events/s against
  the 20/s realtime stream, so speech sat behind seconds of
  unsent silence until the no-transcript watchdog tore the
  session down), and shipped the pacing fix (backlog shed +
  hop-3b wire counter). The 2026-11-19 A/B's LOW arm never got
  a clean test: its send cadence had already collapsed. With
  pacing fixed, nothing ties LOW to lost transcripts.
- **There is no second gate to fall back on.** The sensitivity
  threshold is the only thing between fan noise and a truncated
  answer, so it must be the noise-robust value. Raising
  `min_interruption_duration` or tuning the resume knobs would
  be dishonest churn — they do nothing on this path.

## 4. The fix

1. **Worker — shared default HIGH → LOW**
   (`FRIDAY/src/friday/core/config.py`,
   `VOICE_VAD_START_SENSITIVITY_DEFAULT`). Both voice entry paths
   read this one value (VOI-025 invariant kept): the LiveKit
   worker via `_start_sensitivity()` and the CLI/desktop session
   via `Settings.voice_vad_start_sensitivity`. LOW is the
   documented setting for noisy environments — it demands
   stronger speech evidence before a start-of-speech commits.
   Everything that makes a genuine barge-in work is untouched:
   activity handling stays START_OF_ACTIVITY_INTERRUPTS, prefix
   padding 200 ms, end sensitivity HIGH, silence 500 ms (reply
   speed not traded). Rollback stays one env var away:
   `FRIDAY_VOICE_AAD_START_SENSITIVITY=high` (worker),
   `FRIDAY_VOICE_VAD_START_SENSITIVITY=high` (session path);
   junk values resolve to the default side (LOW).
2. **Send path — mic capture options pinned**
   (`FRIDAY/ui/components/VoiceCall.tsx`): a `MIC_CAPTURE_OPTIONS`
   contract `{ noiseSuppression: true, echoCancellation: true,
   autoGainControl: true }` passed at both
   `setMicrophoneEnabled(true, …)` sites (connect + reconnect).
   Defence in depth, stated honestly: browser processing is
   best-effort, not a guarantee — the AAD sensitivity is the
   decider; this only attenuates what reaches it. The mute
   toggle needs no options (it toggles the track these settings
   created). Static export regenerated (`FRIDAY/ui/out/`).
3. **Dead-knob warning** (worker, `_build_session` call site): a
   comment records that the local interruption knobs are inert
   under `realtime_llm`, so the next worker does not re-trust
   them. The kwargs stay (the builder must survive older plugin
   generations; the flat shape is the deployed one) — no
   behaviour change there.

No trading-behaviour changes. Demo-only. No secrets touched.

## 5. Tests

New `FRIDAY/tests/test_voice_noise_interruption_voi032.py` (15 tests):

- Default contract: shared default LOW, worker + session paths
  resolve LOW, junk → LOW, env `high` restores HIGH (rollback),
  env `low` selects LOW.
- Barge-in + speed guards: activity handling still interrupts,
  prefix padding 200 ms, end sensitivity HIGH, silence 500 ms.
- Library behaviour (real session/activity, §2): deployed shape
  pinned; 5 s VAD event interrupts nothing under realtime_llm;
  stt control interrupts; server input_speech_started interrupts
  unconditionally; overlapping-speech arm would not interrupt.
- Send path (source shape): both mic-enable sites pass the
  pinned options; no bare `setMicrophoneEnabled(true)` remains.

Updated pins (same contract, HIGH → LOW): `test_voice_noise_
robustness_voi018.py` (default/helper/junk), `test_voice_vad_
default_consistency_voi025.py` (shared/config/session/worker
defaults + new HIGH-rollback tests on both paths),
`test_voice_fleet_terms.py::test_realtime_config_pins_aad`.
New file added to the `voice-regressions` pytest list in
`.github/workflows/friday-universe-ci.yml`.

Local runs (scratch venv, production pins, proxy vars unset —
the sandbox proxy breaks httpx client construction at import):
96 passed across the seven affected suites; `ruff check` clean
on all changed Python files (the two pre-existing files were
already `ruff format`-non-clean before this change; only the new
test file was formatted).

## 6. Board

TASK-VOI-032 CLAIMED → IN_REVIEW in this PR (board record +
evidence lines; PR number filled on open).

## 7. Still owed — live calm-vs-noise A/B (needs a calm window)

The offline probe proves the mechanism and the fix's shape; it
cannot prove acoustic reality. After merge + deploy clearance,
in the next calm window (coordinate with Muse 6 — VOI-027/VOI-038
also wait on one; do not duplicate their run, and keep distinct
from the VOI-028 greeting-onset re-probe still owed in parallel):

- **Calm arm:** owner asks a question, FRIDAY answers fully;
  transcript present, greeting onset inside the 8 s bar.
- **Noise arm:** same, with the fan/room noise that produced the
  2026-11-17 defect — she must finish her answers (no
  speaking→listening flips mid-answer), transcripts healthy.
- **Barge-in arm:** owner interrupts her mid-answer with real
  speech — she must yield promptly (the fix must not deafen
  her). If LOW ever costs transcripts, the rollback is
  `FRIDAY_VOICE_AAD_START_SENSITIVITY=high` — file that as the
  next task rather than silently re-flipping.

No deployment or FRIDAY restart was performed by this task.
