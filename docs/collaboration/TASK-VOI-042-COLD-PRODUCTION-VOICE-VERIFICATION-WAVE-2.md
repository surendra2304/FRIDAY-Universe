# TASK-VOI-042 — Cold production voice verification, wave 2 (P0 head: (a)+(b))

- **Task:** TASK-VOI-042 (P1) — PRODUCTION-VERIFY: voice corpus items IG-VOI-01..05 + IG2-VOI-01, cold production voice verification (wave 2).
- **Claim:** hub #1483 comment 7159847986, 2026-11-25 ~16:03 IST (WATCH093 assignment 7159599715; P0 directive 7159737257).
- **Branch:** `muse1/task-voi-042-cold-production-voice-verification-wave-2` @ main `1371db89`.
- **Voice status (P0 directive, all reporting): NOT WORKING** — until the owner re-tests and accepts. Greeting-run passes are not evidence.

## 1. The defect, proven first-hand from the owner's own session

Owner live test 2026-11-25 ~15:54 IST, FRIDAY-Server (`FRIDAY-Voice.service`, `journalctl -u FRIDAY-Voice.service`), room `friday-451209f0`, job `AJ_hvfDFgdT3gCi`, 10:24:42–10:25:12 UTC. Every line below was read first-hand from the service journal this run (logs `journal2.txt`, `journal3.txt`, `journal4.txt`):

| UTC | Event | What it proves |
|---|---|---|
| 10:24:45 | `user_input_transcribed final=True` text = the whole custom-vocabulary list verbatim (`Stratex Memora Futuris … demo trading stop loss take profit`) | Phantom transcript: the biasing vocabulary itself landed as a user final and became a user conversation item, before the owner spoke. Noted as an anomaly; no cause claimed. |
| 10:24:48–52 | interim then `final=True` text `ए, पड़को।` (Hindi script); assistant answered `Understood, I am working on that request for you right now.` | **(a)** English speech transcribed in Hindi script. **(b)** A fragment answered as if it were a request. |
| 10:24:53 | interim `Stratex`; then livekit ERROR `speech not done in time after interruption, cancelling the speech arbitrarily` (speech `speech_f4e47284cc38`, timeout 5.0 s) | **(d)** — Muse 7's half, NOT touched here. |
| 10:24:56 | assistant `I'm still processing your request…`, then `final=True` text `Stratex` | **(b)** A bare fragment finalized and answered. |
| 10:24:59–10:25:00 | interim then `final=True` text `Stratex స్పష్టంగా తెలుసు.` (Telugu script); `VOICE dropped-fragment suspect` fires for the Hindi final (landed while bridge turn `b20-8cac6a` in flight) | **(a)** again, in Telugu script. **(c)** — Muse 7's half, NOT touched here. |
| 10:25:09–11 | assistant gives the real P&L (balance 10,447.45, unrealized profit 119.46 — the delegation did work), then `P and L of `, then `plus one hundred ` | Fragmented assistant replies, cut mid-answer **(d)**. |

Root causes, both in `FRIDAY/src/friday/voice/livekit_worker.py` on main:

- **(a)** The session ran with **no language configured**: `FRIDAY_VOICE_LANGUAGE` is **not set** in `/opt/friday_universe/FRIDAY/.env` (grep count 0, read first-hand), so `_voice_language()` returned `None`, the realtime model was built with **no `language`**, and `_input_transcription_config()` built an `AudioTranscriptionConfig` with **no `language_codes`** — empty means auto-detect. Gemini auto-detected the owner's English as Hindi/Telugu.
- **(b)** Turn finalization was set to fire on a half-second pause: AAD `silence_duration_ms` **500** with end-of-speech HIGH, session `min_endpointing_delay` **0.5 s**. A mid-sentence beat splits one utterance into two finals, and in `realtime_llm` mode the model answers each finalized turn — so fragments get answered.

## 2. Production state at the time of this work (calm check, read-only)

FRIDAY-Server, 2026-11-25 ~16:07 IST (10:37 UTC), logs `calm1.txt`, `calm2.txt`:

- Load 0.16 / 0.21 / 0.18 (bar < 4). RAM 1097 MB available of 1905 MB. Calm.
- `FRIDAY.service` active, NRestarts 3 (was 2 in runs 20/21 — one restart since, entered 09:10:18 UTC / 14:40 IST; reason unknown, healthy now). `FRIDAY-Voice.service` active since 2026-11-24 07:21:18 UTC, NRestarts 0. `Inference.service` active.
- `/health` 200 in 2.15 s; `/ready` 200 in 0.90 s.
- Deployed checkout: `5b245ffd` (merge #1632) — **behind main `1371db89`**. Production does not yet run the code this PR changes; Fleet CD has not deployed recent mains.
- Deployed SDKs: `google-genai 2.33.0`, `livekit-agents 1.8.11`. `AudioTranscriptionConfig` **has** `language_codes` (verified first-hand on the deployed venv) — no upgrade needed for the fix.
- No `FRIDAY_VOICE_AAD_*` overrides in `.env` — the 500 ms / 0.5 s defaults were in force during the owner's test.
- Live status file `/opt/friday_universe/FRIDAY/data/voice_worker_status.json` (read first-hand, log `statusfile2.txt`): state `closed`, room `friday-451209f0`, job `AJ_hvfDFgdT3gCi`, updated 10:25:12 UTC, voice `Aoede`, **`language: ""`** — the empty language field is the live proof of the pre-fix state.

## 3. Fix (a) — STT language pinned for the owner's English (en-IN)

`FRIDAY/src/friday/voice/language_profiles.py` + `FRIDAY/src/friday/voice/livekit_worker.py`:

- New `effective_language()`: the configured `FRIDAY_VOICE_LANGUAGE` profile when set, else **`en-IN`**. `configured_language()` keeps its old meaning (explicit config or None) for callers that need "was anything configured".
- `_voice_language()` now always returns a code (default `en-IN`; junk values and import failures also land on `en-IN`). The realtime model is therefore always built with `language="en-IN"` unless a profile is set. An old plugin generation that rejects the `language` option still degrades via the existing TypeError-drop loop — the call survives.
- `_input_transcription_config()` now pins `language_codes=[effective language]` on the `AudioTranscriptionConfig`, next to the fleet `custom_vocabulary`. Degradation ladder, newest rung first: vocab + pin → vocab without the pin (an SDK predating `language_codes`) → bare config → None. A failure here would mute the call, so every rung degrades instead of raising.
- `instruction_section()` now returns the effective language's section on every call (default: English (India), `en-IN`) — the model is told to speak primarily English from the first word unless the user switches mid-call.
- `_write_status()` reports the effective language, so the status file reads `en-IN` instead of `""`. `FRIDAY/docs/VOICE_SURFACE_CONTRACT.md` updated to match (empty = no session; a live session always carries a code).
- Rollback: `FRIDAY_VOICE_LANGUAGE=<code>` restores any other pinned language in one var (e.g. `te-IN` for a Telugu session). No code change needed to roll back.

## 4. Fix (b) — turn-taking waits for a complete sentence

`FRIDAY/src/friday/voice/livekit_worker.py`:

- AAD `silence_duration_ms`: **500 → 1200** (`FRIDAY_VOICE_AAD_SILENCE_MS` still overrides; `500` restores the old value in one var).
- Session turn kwargs extracted into `_session_turn_kwargs()` (one dict, so the entrypoint and the tests read the same values): `min_endpointing_delay` **0.5 → 1.0 s**, `max_endpointing_delay` stays 3.0 s, interruptions stay enabled. The call site is now `_build_session(llm=model, **_session_turn_kwargs())`.
- Why these two knobs: in `realtime_llm` mode the model answers each finalized user turn, and the worker has no gate that can hold a final back (the fragment-watch machinery is the dropped-fragment detector, Muse 7's (c) — untouched). The finalization thresholds are the levers that decide when a turn is complete, and both are pinned server-side (AAD) and session-side.
- Accepted trade-off, ordered by the P0 directive: replies start up to ~0.7 s later per turn; a complete sentence is answered instead of a fragment. The 8 s greeting-onset bar is unaffected (greeting is not a user turn).
- **NOT done here (Muse 7's half):** (c) zero dropped fragments, (d) no arbitrary speech cancellation. The `_fragment_*` machinery, the recovery dispatch, and the interruption handling are untouched by this PR.

## 5. Tests (all in the existing `voice-regressions` file list — no workflow edit needed)

9 new tests and 6 updated pins across the listed files; the CI `voice-regressions` job runs them because `FRIDAY/src/friday/voice/**` changed (FUT-030 lesson: the job log must be read to confirm the new tests actually ran — see §7):

- `FRIDAY/tests/test_voice_language_profiles.py` — `effective_language` default/override/junk; instruction section names the default en-IN; default build pins `language="en-IN"`.
- `FRIDAY/tests/test_voice_fleet_terms.py` — transcription config pins `language_codes=["en-IN"]` by default, follows `te-IN`, junk → en-IN; degrade ladder rung 2 (pin dropped, vocab kept); silence pins 500 → 1200; build test with the real `_voice_language` asserting `language="en-IN"` + `language_codes=["en-IN"]`; `_session_turn_kwargs` pins (min 1.0, max 3.0, interruptions on); source-level wiring pins updated to the helper.
- `FRIDAY/tests/test_voice_noise_interruption_voi032.py` — silence pin 500 → 1200 (test renamed: the speed trade is now deliberate, by owner order); `_activity()` helper builds its session from `w._session_turn_kwargs()` instead of a hardcoded copy.
- `FRIDAY/tests/test_voice_noise_robustness_voi018.py` — silence pin 500 → 1200.
- `FRIDAY/tests/test_voice_surface_contract.py` — status `language` is `"en-IN"` when unconfigured.
- Local static check only (`py_compile` clean on all 7 changed Python files; `ruff` not installed on this box — CI is the lint gate). Repo tests were **not** executed locally; CI is the execution gate and its job log is the proof (see §7).

## 6. Corpus items — live evidence per item

| Item | What it is | Live evidence this wave | Verdict |
|---|---|---|---|
| IG-VOI-01 | Confirmation safeguard for voice-initiated actions | Code on main (merged #448). No confirmation-gated request occurred in the owner's session (he asked for P&L, a read). The live drill the item's own acceptance requires (`message her on Instagram` → confirmation question, no action) has not been run. | **NOT VERIFIED live** — drill owed after the (a)+(b) deploy, in the real-use test. Not a failure: nothing gated was attempted. |
| IG-VOI-02 | Hands-free dictation into the owner's laptop | Requires the owner's connected laptop; no laptop is connected in this wave. Nothing dictated, nothing typed. | **NOT VERIFIED live** — gated on the laptop connection. Not a failure. |
| IG-VOI-03 | Indian-language voice profiles | **FAILED live** in the owner's session: English transcribed in Hindi (`ए, पड़को।` 10:24:52 UTC) and Telugu (`Stratex స్పష్టంగా తెలుసు.` 10:25:00 UTC) script; status file `language: ""`. The fix is this PR (§3). | **FAILED live pre-fix; fix implemented + tested here; live re-test owed after deploy.** No separate fix task filed — the fix rides in this PR. |
| IG-VOI-04 | AURA voice surface contract (status file) | Live status file read first-hand: `voice` + `language` keys present, room/job correct, `language: ""` pre-fix. The wiring is proven live; the value was the defect (see IG-VOI-03). Post-fix the live file must read `en-IN`. | **WIRING VERIFIED live; value NOT VERIFIED until the deploy** (must read `en-IN`). |
| IG-VOI-05 | VoiceStudio evaluation (do NOT adopt live) | Documentary item by design: `FRIDAY/docs/VOICESTUDIO_EVALUATION.md` on main (blob `c8cc8d7d`, 4422 bytes) states the verdict (no TTS slot, hardware, licence) and the owner-gated offline options. No code, dependency or install introduced — verified by the file list (doc only). | **VERIFIED** (evaluation, not a live behaviour — there is no live leg by design). |
| IG2-VOI-01 | Spoken-English practice mode (per-sentence corrections) | Code on main (merged #726: `FRIDAY/src/friday/voice/english_practice.py` + skill + registry + `FRIDAY/tests/test_english_practice_ig2.py`). Not invoked in the owner's session and not probed in this wave. | **NOT VERIFIED live** — production probe owed after the deploy (invoke practice mode in a real call, get a per-sentence correction). Not a failure. |

No item is marked verified on code alone. The only item with a live failure is IG-VOI-03, and its fix is this PR.

## 7. What is still owed — the live leg is BLOCKED on deployment clearance

- **Implemented:** yes (this PR). **Tested:** CI `voice-regressions` + `test` jobs — status to be filled from the CI run on the PR head (the job log must show the new VOI-042 tests collected and passing; a green check alone is not proof per the FUT-030 lesson).
- **Deployed:** no. Production runs checkout `5b245ffd`, behind main; this PR's code reaches FRIDAY-Server only via Fleet CD after merge, which is a live-fleet deployment and needs **Muse's hub clearance** (ARCHITECTURE.md §3.6). No such clearance exists for VOI-042 — the P0 directive orders the fix and the claim, not the deploy. The owner stop order is still in force (WATCH093).
- **Production-verified:** no. The live re-test — a real-use call on FRIDAY-Server with the fixed code: full spoken sentences asking FRIDAY to DO things (e.g. Stratex P&L), answered completely and fast, with transcripts in English script and no fragment answers — can only run after the deploy, and the final acceptance is the owner re-testing himself (P0 directive). The follow-up probe plan: calm-window check, deploy via Fleet CD on clearance, harness real-use call (room, journal, per-turn transcript + timing), then the IG-VOI-01/02/IG2-VOI-01 drills from §6.
- **Board flip note (correction):** the claim post said the VOI-042 AVAILABLE→IN_REVIEW flip rides in coordinator board PR #1820. Verified first-hand from #1820's patch: #1820 sets **owner only** (`null` → `muse_1`), status stays AVAILABLE. The status flip therefore rides in **this** work PR, not #1820 — no double-flip; if #1820 merges first, this PR rebases onto its owner line (same value, no conflict in substance).

## 8. What this PR does not claim

- Voice is **NOT WORKING** until the owner re-tests and accepts. Nothing here claims otherwise.
- No S1 service was touched (S1 FRIDAY is retired by design; verified inactive this run). No failure injection was attempted (clearance held). No server moves, installs, or restores were attempted. All FRIDAY-Server access this run was read-only (`journalctl`, `systemctl show/cat`, `curl` health, file reads).
- (c) dropped fragments and (d) speech cancellation are Muse 7's — untouched, still open.
- The phantom vocabulary-dump final (10:24:45 UTC, §1) is recorded as an observed anomaly with no cause claimed; it is not fixed by (a)/(b) and may need its own look if it recurs after the deploy.

— Muse 1
