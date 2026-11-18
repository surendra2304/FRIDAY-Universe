# Wake word — what FRIDAY has, what it does not, and why

*Status as of 2026-11-16 (IG implementation wave, FRIDAY lane).
Update 2026-11-18 (TASK-FRD-026): the owner reversed the default —
the wake word is now ARMED by default; see the behaviour rules.*

## The gap this closes

The wave-2 triage marked wake-word behaviour as already covered. The lane
baseline audit disproved that: before this change there was **no wake word
anywhere in FRIDAY's code** — searching `FRIDAY/src/friday/voice/` for
`wake` returned exactly one hit, a docstring in
`voice/confirmation_policy.py` about an unrelated policy. Nothing listened
for a spoken phrase; the only way to start a conversation was to open the
site and press the control.

## What shipped

A **browser wake word** for the FRIDAY stage (the Halo site):

- `FRIDAY/ui/lib/wakeWord.ts` — pure logic: transcript normalization,
  wake-phrase matching (word-boundary containment, so interim speech
  results match), the would-be command after the phrase, and the
  persisted arm/disarm preference. Unit-tested with plain Node
  (`lib/wakeWord.test.ts`).
- `FRIDAY/ui/components/stage/WakeListener.tsx` — the listener: the
  browser's Web Speech API (`SpeechRecognition` /
  `webkitSpeechRecognition`), continuous + interim results, `en-IN`.
  On a match it starts the voice line through the exact same
  `VoiceLinkControls.start()` the "Start the voice line" Veil command
  uses — no second call path.
- Wiring in `Stage.tsx`: a Veil command ("Arm the wake word" /
  "Disarm the wake word"), a status line under the voice controls, and
  the preference persisted in `localStorage` (`friday.wakeWord`).

Behaviour rules:

- **Armed by default** (owner decision 2026-11-18, TASK-FRD-026;
  originally shipped off-by-default on 2026-11-16). The stage listens
  from first load. The Veil's "Disarm the wake word" stores an explicit
  "off" — that, and the blocked-browser auto-disarm below, are the
  only things that turn it off.
- Phrases: "hey friday", "ok friday", "okay friday", "yo friday".
  A bare "friday" deliberately does **not** trigger — it would fire
  constantly in conversation about FRIDAY.
- **Paused while a call is live.** The listener unmounts when the voice
  line opens; LiveKit owns the microphone during a call. It re-arms when
  the line closes.
- **A refused microphone disarms it.** If the browser denies mic access
  (or has no speech recognition at all), the stage disarms the wake word
  and shows why, instead of retrying in a loop.

## What it is NOT — the honest limits

- **Tab-bound.** It works only while the FRIDAY stage is open in a
  browser tab. Close the tab and there is no wake word.
- **Chromium-family only.** It needs the Web Speech API; Firefox does not
  expose it for recognition. Safari's support is partial.
- **The browser vendor does the recognition.** Chrome's implementation
  of `webkitSpeechRecognition` streams audio to Google's servers for
  transcription. The wake phrase is detected from the returned
  transcripts, in the page — but the audio path is the browser's, not
  FRIDAY's, and not on-device.
- **Not an OS-level always-on listener.** It cannot hear the owner from
  another app, a locked screen, or a device where the site is not open.
- **Not on the phone or laptop surfaces.** PHONE-001 / LAP-001 control
  channels are unaffected; neither has a wake word.

## What a true always-on wake word would require

A native listener on the device itself — e.g. openWakeWord or Picovoice
Porcupine running in the laptop client or a phone companion app, with an
on-device model, mic arbitration against the LiveKit call, and a
privacy story the owner approves. That is a separate build on the native
surfaces, **not** part of this change, and it should not be described as
shipped until it exists and is heard working on the owner's own device.
