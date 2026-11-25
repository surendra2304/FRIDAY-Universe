# TASK-VOI-043 — Zero dropped fragments + no arbitrary speech cancellation (P0 legs (c)+(d))

- **Task:** TASK-VOI-043 (P0) — FRIDAY voice P0: zero dropped fragments + no arbitrary speech cancellation (owner live test 2026-11-25).
- **Claim:** hub #1483 comment 7163799902, 2026-11-25 ~18:55 IST (coordinator WATCH097 re-slot, M7 → M1; queue FRD-053 → VOI-043 → VOI-033).
- **Branch:** `muse1/task-voi-043-zero-dropped-fragments-no-arbitrary-cancellation` @ main `14181d3c` (base moved from `f216e1bae` after PR #1847 merged; the four code/test files are byte-identical at both mains).
- **Voice status (P0 directive, all reporting): NOT WORKING** — until the owner re-tests and accepts. Code + unit proof is not a live acceptance.

## 1. The defects, proven first-hand from the owner's own session

Owner live test 2026-11-25 ~15:54 IST, FRIDAY-Server (`FRIDAY-Voice.service`), room `friday-451209f0`, job `AJ_hvfDFgdT3gCi`, 10:24:42–10:25:12 UTC — the journal as recorded in TASK-VOI-042's evidence (same session; VOI-042 fixed legs (a)+(b) and left (c)+(d) here):

| UTC | Event | What it proves |
|---|---|---|
| 10:24:52 | interim then `final=True` text `ए, पड़को।` (Hindi script); fragment answered | (a) English in Hindi script (VOI-042's fix). The final landed while bridge turn `b20-8cac6a` was in flight. |
| 10:24:53 | interim `Stratex`; then livekit ERROR `speech not done in time after interruption, cancelling the speech arbitrarily` (speech `speech_f4e47284cc38`, timeout 5.0 s) | **(d)** Her speech was cut mid-answer by the user's own continuation, then force-cancelled. |
| 10:25:00 | interim then `final=True` text `Stratex స్పష్టంగా తెలుసు.` (Telugu script); `VOICE dropped-fragment suspect` fires for the Hindi final | **(c)** The Hindi final was proven dropped — no bridge call ever followed it — and never recovered. |

### (c) root cause 1 — the fragment tracker is blind to non-Latin script

`FRIDAY/src/friday/voice/livekit_worker.py`, `_distinctive_tokens` (main `f216e1bae`): content words come from `re.findall(r"[a-z]{5,}", ...)`. A final transcribed in Devanagari/Telugu script yields **zero** tokens. Both consumers of that helper then fail it:

- `_fragment_recovery_due` skips any suspect with no numbers and no words as "no distinctive substance" — a bare-`"Okay."` guard that also swallows every Hindi/Telugu-only final. The Hindi final `ए, पड़को।` yields `(set(), set())` (reproduced locally, `repro.py`).
- `_dispatch_followed` can never match such a suspect to a later dispatch, so it is proven dropped, journalled — and never recovered.

Repro (local, before the fix): Hindi final mid-flight → `_fragment_recovery_due` returns `[]` after the flight settles; Telugu final returns due only because it happens to contain the Latin word `Stratex`.

### (c) root cause 2 — a cancelled bridge call never settles its flight

`FRIDAY/src/friday/voice/brain_bridge.py`, `execute()` (main `f216e1bae`): the result observer is notified only from `_settle`, and every exit path calls `_settle` — **except cancellation**. The realtime SDK cancels a tool call on interruption, and the arbitrary-cancellation backstop cancels the whole speech, so `execute()` raises `CancelledError` out of `_dispatch` (or out of the fragment guard's settle-window sleep) with no settle. The worker's fragment watch then keeps that flight in `in_flight` **forever**, and `_fragment_recovery_due` refuses every suspect that landed during it (`any(turn_id in in_flight ...)` never clears). The drop is journalled at session-end flush, never recovered.

Repro (local, before the fix): cancel a blocked `execute()` → result observer sees **0** records → a suspect that landed during that flight is never due. The (c) and (d) defects are one chain: the arbitrary cancel (d) strands the flight, which strands the fragment (c).

### (d) root cause — the arbitrary cancellation is the server's `interrupted` signal, and the 5 s wind-down cannot be met

Traced first-hand in the exact deployed pins (wheels downloaded and read: `livekit-agents 1.8.11`, `livekit-plugins-google 1.8.11`, `google-genai 2.33.0` — the versions the production checkout runs):

1. Gemini emits `server_content.interrupted` on start of user activity while `activity_handling` is `START_OF_ACTIVITY_INTERRUPTS` — the value this worker pinned explicitly in `_realtime_input_config`.
2. `livekit/plugins/google/realtime/realtime_api.py` (`_handle_input_speech_started`) turns it into an `input_speech_started` event.
3. `livekit/agents/voice/agent_activity.py` (`_on_input_speech_started`) calls `self.interrupt(source="audio_activity")` **unconditionally** — no duration, transcript or energy check. The overlapping-speech escape is closed: the Gemini model does not declare `supports_overlapping_speech` (verified: no such capability in the plugin).
4. `livekit/agents/voice/speech_handle.py`: `interrupt()` → `_cancel()` arms a timer of `INTERRUPTION_TIMEOUT = 5.0` s; if the speech's tasks have not finished by then, `_on_timeout` cancels them all and logs exactly the journal error: `speech not done in time after interruption, cancelling the speech arbitrarily.`
5. The speech's tasks include the in-flight bridge tool call (foreground budget 60 s, shielded in `_dispatch`), so **any interruption during a bridge call deterministically exceeds the 5 s wind-down** — the arbitrary cancel is not a race, it is the designed backstop firing on a call that cannot wind down in time.

The worker cannot gate the interrupt per turn: it fires on start-of-activity, before any transcript exists, and the local interruption knobs are inert under `realtime_llm` (VOI-032, proven against the same pins). So the fix is the server-side switch, not another local knob.

## 2. Fix (c) — the fragment path is script-aware, and a cancelled call settles

`FRIDAY/src/friday/voice/livekit_worker.py`:

- New `_fragment_tokens(text)`: numbers as before; content words are letter + combining-mark runs (`unicodedata` categories L/M) — **not** `\w` runs, because a `\w` split shreds `पड़को` (nukta + vowel sign are not word characters) into 1-code-point pieces and the fragment reads as contentless again. Latin runs keep the old rule byte-identically (≥ 5 letters, same stopwords); non-Latin runs count at ≥ 3 code points (a Devanagari/Telugu content word carries its meaning in few code points; a 1–2 code-point run is a particle, the same `"Okay."`-class the Latin rule excludes). `_distinctive_tokens` itself is untouched — the FRD-012/018 verbalized checks keep their pinned Latin behaviour.
- `_dispatch_followed` and `_fragment_recovery_due` now use `_fragment_tokens` on both sides. A Devanagari/Telugu fragment can now carry substance (so it is recovered) and can now match a later dispatch (so a fragment the model did pick up is still not recovered).

`FRIDAY/src/friday/voice/brain_bridge.py`:

- `execute()` gains a settle-once guard: every exit after the dispatch-start notification settles through `_settle_once`, and a `CancelledError` (from the send, from the send-lock wait, or from the fragment guard's settle-window sleep) settles the turn as `{"state": "cancelled", "spoken_reply": "", "cancelled": True}` and re-raises, so the SDK still sees the cancellation. The delivery watch closes a `cancelled` record immediately (`_delivery_action` returns `"close"` for any state outside answered/failed/refused/unconfirmed) with a journal line and never nudges it. `cancelled` is in neither `_CACHEABLE_STATES` nor `_LATE_DELIVERABLE_STATES`, so it can never be cached or late-delivered as a placeholder — and the shielded send's real late result is still filed by `_dispatch`'s own `CancelledError` arm and delivered by the watch through the ordinary late channel.

## 3. Fix (d) — activity handling is NO_INTERRUPTION by default

`FRIDAY/src/friday/voice/livekit_worker.py`:

- New `_activity_handling()`: default `genai_types.ActivityHandling.NO_INTERRUPTION`; `FRIDAY_VOICE_AAD_ACTIVITY_HANDLING=start_of_activity_interrupts` restores the old behaviour in one var; any other value falls back to `NO_INTERRUPTION`. `_realtime_input_config()` uses it. Everything else in the AAD pin is unchanged (start sensitivity LOW, silence 1200 ms, prefix padding 200 ms, end sensitivity HIGH).
- Effect: Gemini no longer emits `interrupted` on user activity, so no `input_speech_started` reaches the activity, so her response is never cut mid-answer — neither by a continuation of the same sentence nor by noise crossing the start threshold. A new user turn is still transcribed and finalized and is answered after she finishes the current response — no turn is lost, and (with VOI-042's 1.2 s finalization) a continuation no longer arrives while she is answering a fragment of the same sentence.
- **Trade-off, stated plainly:** a genuine barge-in ("Friday, stop") no longer cuts her off mid-sentence either — she finishes the sentence, then takes the new turn. The owner complained specifically about mid-answer cuts; the env override restores barge-in in one var if he wants it back. This is a deliberate behaviour change, recorded in the code, in `test_voice_noise_interruption_voi032.py` (module docstring + the activity-handling pin), and here.

## 4. Tests — 14 new, 3 pins moved, all in the existing `voice-regressions` file list

No workflow edit: `tests/test_voice_fragment_recovery_frd019.py` and `tests/test_voice_noise_interruption_voi032.py` are both already in the `voice-regressions` pytest list (FUT-030 lesson: the CI job log must be read to confirm the new tests actually ran — see §6).

- `test_voice_fragment_recovery_frd019.py` (+11 new):
  - (c) leg 1: `test_hindi_script_fragment_is_recovered`, `test_telugu_script_fragment_is_recovered` (owner-session verbatim finals), `test_fragment_tokens_are_script_aware`, `test_fragment_word_runs_keep_combining_marks_attached`, `test_non_latin_fragment_covered_by_a_later_dispatch_is_not_recovered`, `test_non_latin_fragment_sharing_one_word_only_is_still_recovered`.
  - (c) leg 2: `test_cancelled_execute_settles_the_flight_exactly_once` (cancel → exactly one `cancelled` observer record; the shielded send's late `answered` still files; the worker watch then recovers a suspect from that flight), `test_cancelled_execute_is_not_cached`, `test_completed_execute_still_settles_exactly_once`, `test_cancelled_execute_during_fragment_guard_hold_settles`.
  - (d) wiring: `test_worker_wiring_source_pins_voi043`.
- `test_voice_noise_interruption_voi032.py` (+2 new, 1 replaced): `test_activity_handling_still_interrupts` **replaced deliberately** by `test_activity_handling_defaults_to_no_interruption`, `test_activity_handling_env_restores_barge_in`, `test_activity_handling_unknown_value_falls_back_to_no_interruption`; module docstring records the VOI-043 change (including that VOI-042's silence is 1200 ms, not the 500 ms the old docstring still said).
- The behavioural activity-handling pins live in the VOI-032 file (it owns the AAD contract); the fragment file pins only the wiring.
- Pre-fix proof (local): the new tests were run against pristine main code — 9 of them fail there (Hindi recovery, script-aware tokens, word runs, cross-script coverage, both cancelled-settle tests, activity default + unknown-value fallback, source pins); the other 5 pass pre-fix as guards (Telugu recovery, one-word-only, not-cached, completed-once, env-restores). No test was written to pass on the old code while claiming the fix.
- Local run (venv, Python 3.12; CI runs 3.11): `test_voice_fragment_recovery_frd019.py` + `test_voice_noise_interruption_voi032.py` → **43 passed, 1 failed** — the failure is `test_mic_capture_options_pinned`, which reads `FRIDAY/ui/components/VoiceCall.tsx`, a file absent from this partial local checkout (it fails identically on pristine code). `ruff check` clean on all 4 changed files. The wider voice subset (brain delivery/guard/latency, recall fact/gate, live features, language profiles, gemini-only, surface contract, confirmation policy, recovery ladder) passes except files that need the full repo checkout (`mesh` package, `ui/`) or fleet deps not installed locally — those fail identically on pristine code; CI (full checkout + full requirements) is the gate for them.

## 5. Per-acceptance-item verdicts

| Item | Verdict |
|---|---|
| (c) ZERO dropped fragments: every final transcript dispatches a bridge turn; proven by journal + live test, no dropped-fragment suspect left unresolved | **CODE-VERIFIED, live-owed.** The two root causes are fixed and unit-proven (non-Latin fragments recover; cancelled flights settle so suspects become due). The "every final dispatches" half still rests on the model's tool choice for finals that land with no flight in flight (pinned deliberately: `test_final_with_nothing_in_flight_is_never_a_suspect` — a conversational aside is not a dispatch, and the worker cannot force a dispatch per final without double-dispatching). The live leg — a real-use call where a fragment lands mid-flight and is recovered and spoken — is owed after deploy + owner re-test (§6). |
| (d) No arbitrary speech cancellation mid-answer: her speech is not cancelled after interruption except on a real new user turn; proven live | **CODE-VERIFIED, live-owed.** The trigger chain is removed at the server switch (NO_INTERRUPTION) and unit-proven; the library mechanism is traced first-hand. Two honest caveats: (1) a real new user turn now also does **not** cancel her speech — she finishes the sentence, then answers the new turn (see §3 trade-off); the acceptance's "except" is satisfied in that nothing is ever cancelled arbitrarily, but barge-in-as-cutoff is gone until the owner asks for it back. (2) The live leg — speak a continuation mid-answer, confirm she finishes; start a genuinely new turn mid-answer, confirm it is answered after she finishes, not lost — is owed after deploy + owner re-test (§6). |
| Acceptance is a real-use test: full spoken sentences asking FRIDAY to DO things (e.g. Stratex P&L), answered completely and fast. Scripted greeting runs do not count. | **NOT RUN — gated.** No greeting-run or scripted-run evidence is claimed here. The real-use test is §6. |

## 6. What is still owed — the live leg is BLOCKED on deployment clearance

- **Implemented:** yes (this PR). **Tested:** CI `voice-regressions` + `test` jobs — status to be filled from the CI run on the PR head (the job log must show the new VOI-043 tests collected and passing; a green check alone is not proof per the FUT-030 lesson).
- **Deployed:** no. Production runs checkout `5b245ffd`, behind main; this PR's code reaches FRIDAY-Server only via Fleet CD after merge, which is a live-fleet deployment and needs **Muse's hub clearance**. No such clearance exists for VOI-043 — the P0 directive orders the fix and the claim, not the deploy. The owner stop order is still in force. Fleet CD is broken (S1 dirty tree + S2 `.git/objects` permissions — every main push fails CD, watch098); even a cleared deploy may fail at CD until that is repaired.
- **Production-verified:** no. The live re-test — a real-use call on FRIDAY-Server with the fixed code — can only run after the deploy, and the final acceptance is the owner re-testing himself (P0 directive). Probe plan after clearance: (1) calm-window check (FRIDAY-Voice active, `/health` 200); (2) deploy via Fleet CD on clearance; (3) harness real-use call: full spoken sentences asking FRIDAY to DO things (Stratex P&L first), spoken with mid-sentence continuations and a genuine mid-answer barge-in — record room, journal, per-turn transcript + timing, and check: no `dropped-fragment suspect` left unrecovered, no `speech not done in time after interruption` error, the new turn answered after she finishes, transcripts in English script (VOI-042's leg). No live probe was run in this wave: no S1 touched, no deploy attempted, no fleet write. All FRIDAY-Server access in VOI-042's wave was read-only; this wave ran no fleet access at all (code + tests only).
- **Board flips in this PR:** TASK-FRD-053 IN_REVIEW → MERGED (work PR #1833 merged 2026-11-25 17:58:21 IST, merge `1d7e9592`, verified first-hand via the PR API) and TASK-VOI-043 AVAILABLE → IN_REVIEW (branch + this PR number).

## 7. What this PR does not claim

- Voice is **NOT WORKING** until the owner re-tests and accepts. Nothing here claims otherwise.
- The phantom vocabulary-dump final (10:24:45 UTC, VOI-042 §1/§8) is untouched — recorded as an observed anomaly with no cause claimed; it is not fixed by (c)/(d).
- No claim is made about Gemini's queueing behaviour under NO_INTERRUPTION beyond the SDK's documented semantic ("The model's response will not be interrupted") — that a new turn spoken mid-answer is answered after she finishes, rather than dropped, is part of the owed live leg (§6), not a proven fact here.
- The (a) language pin and (b) finalization thresholds from VOI-042 are unchanged except where §3 notes them; this PR does not re-prove them live.

— Muse 1
