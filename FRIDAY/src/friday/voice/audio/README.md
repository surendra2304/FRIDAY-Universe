# Fixed voice lines — pre-recorded, never synthesized at runtime

TASK-VOI-009 (owner directive 2026-11-15: "Gemini is the only AI for
voice and remove groq") deleted the Groq voice pipeline (Whisper STT +
Groq LLM + EdgeTTS / Groq Orpheus TTS) from `livekit_worker.py`. The
few lines the worker itself must be able to say without a live Gemini
session are therefore **recordings shipped in this directory**, played
verbatim into the room by `_play_fixed_line()`. Playback is a static
file read — no TTS, no provider call, no synthesis of any kind happens
at runtime.

| File | Heard when | Says |
| --- | --- | --- |
| `greeting.wav` | Every call, first thing | "I am here, Boss. What would you like to work on?" |
| `voice_unavailable.wav` | Gemini cannot serve the call (no resolvable valid key / provider unreachable) | "Voice is unavailable right now. Please try again in a little while." |
| `unconfirmed_request.wav` | Recovery ladder exhausted with a request pending | "I have lost my voice connection, and I could not restore it. The outcome of that request is unconfirmed. Please check the task history before repeating it." |
| `unconfirmed_general.wav` | Recovery ladder exhausted between turns | "I have lost my voice connection, and I could not restore it. Please try me again in a moment." |

## Provenance

Rendered ONCE, at build time (2026-11-15), with Microsoft Edge TTS
voice `en-IN-NeerjaNeural` — the voice that had actually spoken every
production fixed line (the Groq Orpheus path never passed its
model-terms probe, so EdgeTTS was the de-facto fixed-line voice).
Converted to the worker's playback format: **24 kHz, mono, 16-bit PCM
WAV**. The renderer was a one-off build step on the voice host; the
`edge_tts` package is not imported by the worker and is not needed to
play these files.

To change a line: re-render it offline in the same voice and format,
replace the WAV, and update the table above. Never wire a runtime
synthesizer back into the worker — that is exactly what TASK-VOI-009
removed.
