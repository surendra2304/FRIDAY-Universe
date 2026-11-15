# VoiceStudio Evaluation (TASK-IG-VOI-05)

**Verdict: do NOT adopt into FRIDAY's live voice path. Two offline
uses are legitimate future options, both owner-gated. No code, no
dependency, no install is made by this evaluation.**

Source idea: reel De1wM7TxD8D (@ashutoshwithclaude) — "local
open-source voice cloning/voice design as a candidate TTS voice
source for FRIDAY voice." Spec card:
`~/workspace/ig-references/repos/voicestudio.md` (workspace copy).

## What VoiceStudio is

github.com/debpalash/VoiceStudio — a free, fully local, open-source
voice studio ("the open-source ElevenLabs alternative"): clone a
voice from a short clean reference recording, design a voice from a
text description, dub/translate video, dictate, transcribe, narrate —
646 languages via its default engine (k2-fsa/OmniVoice), dozens of
other engines selectable. Electron desktop app + local Python/FastAPI
backend (Docker option), local API + MCP. Very active project
(~111k stars at the 2026-11-15 snapshot, created Apr 2026).

## Why it has no slot in the live voice path

1. **There is no TTS stage to fill.** Since TASK-VOI-009, FRIDAY's
   live voice is Gemini Live end-to-end: the realtime model hears
   and speaks natively in one session, and the provider contract is
   `gemini-realtime` only. A TTS engine could only enter by
   rebuilding voice as STT → LLM → TTS — precisely the pipeline
   shape the owner's live test #2 rejected ("like Google voice
   search") and his standing rule bans (Gemini is the only AI for
   voice). Adopting VoiceStudio live would regress the architecture
   the fleet just paid to fix.
2. **It cannot run where FRIDAY runs.** VoiceStudio is a desktop app
   for the owner's own hardware, driving inference-class local
   models. The Oracle servers have ~956MB RAM each and already rely
   on swap; there is no capacity for a local TTS engine, and the
   owner's laptop is only a plausible host while it is on and
   connected — a live-path dependency on it would make voice
   availability worse, not better.
3. **Speed.** The owner's criterion is speed first (greeting ≤8s,
   simple turns 4–6s). A local clone/design engine adds a network
   hop to a laptop plus local inference latency to every spoken
   turn. Gemini Live's native speech is the fastest path that
   exists in this stack today.

## Licence position (mandatory care)

- The app is **AGPL-3.0**. Private local use is unproblematic;
  embedding it in anything distributed would carry copyleft
  obligations.
- The default OmniVoice weights are **CC-BY-NC — non-commercial**.
  Fine for the owner's private FRIDAY use; **not** usable for
  published VyralX output or for any business voice-agent
  deployment (cf. TASK-IG-VOI-03) without choosing a
  commercially-licensed engine and verifying its terms — licences
  vary per engine.
- Voice cloning requires the voice owner's permission. Cloning the
  owner's own voice is the clean case; cloning anyone else's is
  out of scope, full stop.

## Legitimate future uses (offline, owner-gated)

1. **Fixed-line re-rendering.** FRIDAY's fixed spoken lines (the
   greeting, `voice_unavailable`, the `unconfirmed_*` notices) are
   pre-rendered WAVs — today, en-IN-NeerjaNeural renders. A
   VoiceStudio-designed or owner-cloned voice could re-render that
   fixed set offline and ship the WAVs through the normal PR path,
   with zero change to the live path. This is the one use that
   improves FRIDAY's voice without touching its architecture. It is
   the owner's call whether he wants it, and his ears are the
   acceptance test.
2. **VyralX narration experiments** — only with a
   commercially-clean engine (never the CC-BY-NC default weights)
   and only as an experiment; VyralX's own pipeline decisions stay
   with that lane.

Its dictation widget is noted and set aside: TASK-IG-VOI-02 already
implements dictation over the deployed laptop path, and a second
dictation stack would be a new dependency for no new capability.

## If the owner wants option 1

Install VoiceStudio on his laptop (his machine, his install), pick
an engine after the licence check above, render the fixed line set,
A/B against the current lines, and ship the chosen WAVs as an
ordinary PR. Estimated effort: an afternoon, mostly his listening
time. Until he asks, nothing here is actioned — this document is
the deliverable, and the idea is closed as *evaluated*.
