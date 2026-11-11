# E10 — Indian-English Accent Accuracy Check

**Checklist E10 (MASTER_COMPLETION_CHECKLIST) — Batch 8, ZAI Agent 2.**

The owner's speech is Indian English with a Telugu-English mix — common
phrasing includes "do the needful", "revert back", "prepone", and
code-switching to Telugu for emphasis. The STT + Live model must handle
this accurately; a misheard "revert" as "river" loses the meaning.

## Configuration (defaults set in Batch 8)

- **STT accent locale:** `en-IN` (set in `owner_preferences.py` DEFAULTS;
  surfaced in the Owner Preferences UI as "Accent locale (STT hint)").
- **Voice personality:** `assistant` (the Gemini Live system instruction
  includes the owner's name + the en-IN hint; see `gemini_live_session.py`).
- **Live model:** `gemini-3.1-flash-live-preview` (multilingual; handles
  Telugu-English code-switching natively).

## The owner's phrasing — what to expect

These are the phrasings the STT + Live model must handle. Each is tested
once per voice-kit run (E6 step 4 or a dedicated E10 check):

| Owner says | Expected transcription | Common mishear |
|---|---|---|
| "do the needful" | "do the needful" | "do the needle" |
| "revert back to me" | "revert back to me" | "river back to me" |
| "prepone the meeting" | "prepone the meeting" | "prepone the meeting" ✅ (or "postpone") |
| "yeh market upar jaayega" | "yeh market upar jaayega" (Hindi-English) | "yeh market upper jayega" |
| "thoda adjust karo" | "thoda adjust karo" (Hindi-English) | "thoda adjust caro" |

## The check

1. Open a voice session.
2. Say each of the 5 phrases above, in order, with a 2s pause between.
3. After the 5th, ask: *"What did I just say?"*
4. **Pass:** FRIDAY repeats the 5 phrases with the Telugu/Hindi words intact.
5. **Fail:** any phrase is anglicized (e.g. "do the needle") or the code-switch is dropped.

## What the owner does NOT need to do

- Retrain the model — Gemini Live is multilingual out of the box; no
  fine-tuning is needed for conversational Telugu-English.
- Install a separate STT — the LiveKit + Gemini Live pipeline handles STT
  and the model in one stream.

## Tuning (if accuracy is below 4/5)

- Change the accent locale in the Owner Preferences UI to `en-IN` (if the
  owner's account default is `en-US`, the en-IN hint steers the STT).
- Add code-switch phrasings the owner uses often to the Live system
  instruction (in `gemini_live_session.py` — extend the `PERSONA_PROMPT`
  with a "the owner uses these phrasings" section).
- If a specific phrase is consistently misheard, log it in this doc's table
  above so the next voice-kit run re-checks it.

## What this check does NOT cover

- **Voice quality (E9):** the voice_name + VAD config — see `config.py`.
- **Barge-in (E6):** the 5-minute test kit — see `BARGE_IN_TEST_KIT_E6.md`.
- **Unlimited minutes (E8):** still blocked on the ARM server capture (G9).
