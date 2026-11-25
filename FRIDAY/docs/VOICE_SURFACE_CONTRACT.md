# Voice Surface Contract (TASK-IG-VOI-04)

The binding contract between FRIDAY's voice worker and any designed
voice surface — the Halo page today, or a stored design candidate
(ULTRON, AURA, orb-core, …) if the owner picks one. Source idea:
reel Da6PwA8z-wq (AURA — a custom-designed assistant front-end over a
live voice pipeline); its candidate is stored at
`~/workspace/design-candidates/aura-assistant/` as reference only.

This contract changes no live surface. It names the truth channels a
surface may bind to, the state vocabulary it may show, and the speed
and honesty rules it must keep — so a design swap is a presentation
change, never a behaviour change. Any surface built from this
contract must also follow the repo design rules (`docs/design-system.md`,
`docs/animation-playbook.md`: `prefers-reduced-motion` fallbacks,
transform/opacity animation only, panels over decoration).

## 1. Truth channels

### 1a. Worker status file — `FRIDAY/data/voice_worker_status.json`

Written by the voice worker (`livekit_worker._write_status`) at every
lifecycle transition; read by `/api/voice/diagnostics` and shown in
the dock. Schema (additive-only — consumers must ignore unknown keys):

| key | type | always | meaning |
|---|---|---|---|
| `state` | string | yes | worker lifecycle state (§2) |
| `provider` | string | yes | serving provider identity, or `pending`/`none` |
| `model` | string | yes | Gemini Live model name (may be empty pre-build) |
| `voice` | string | yes | configured Gemini voice name (e.g. `Aoede`) |
| `language` | string | yes | effective session language code (TASK-IG-VOI-03 + TASK-VOI-042); `en-IN` by default, the configured profile when FRIDAY_VOICE_LANGUAGE is set — never empty on a live session |
| `detail` | string | yes | human-readable last transition note |
| `pid` | int | yes | worker process id |
| `updated_at` | string | yes | local timestamp of the last write |
| `room` | string | when known | LiveKit room the state belongs to |
| `job_id` | string | when known | LiveKit job the state belongs to |

`room`/`job_id` exist because of the 2026-11-14 misattribution: with
several jobs in one worker process, a status line that names its job
is the difference between evidence and confusion. A surface must
never present a status whose `job_id` belongs to another call as the
current call's state.

### 1b. Diagnostics API — `/api/voice/diagnostics`

`GET` returns the last session's measured quality (session id,
duration, RTT, packet loss, reconnect count, quality grade) plus the
worker's status. `POST /api/voice/diagnostics/report` is how the web
surface reports its own session measurements up. Doctrine, already
live and binding on any surface: counters start at zero and stay
there until a real session — **never invented metrics**.

### 1c. In-call state — local to the surface

Listening / speaking / muted are derived by the surface itself from
LiveKit room events and audio levels. They are presentation state,
not worker truth, and must never be written back as if they were.

## 2. State vocabulary

Worker states a surface must be able to render:

| worker `state` | surface shows | notes |
|---|---|---|
| `registered` | standby | worker up, waiting for the first job |
| `job-received` | connecting | participant joined; provider resolving |
| `ready` | live | Gemini Live session built on a verified key |
| `recovering` | working on it | wedged/killed turn; ladder running, no re-greeting |
| `degraded` | troubled | ladder exhausted; an unconfirmed outcome was spoken |
| `unavailable` | unavailable | no session could be built; the recorded notice plays |
| `closed` | ended | owner left; session closed |

Provider honesty: after TASK-VOI-009 the only serving provider is
Gemini Live. A surface must render `provider` as reported and must
never display a fallback brand (there is no Groq in voice — the
owner's standing rule) or a generic "AI" placeholder in its place.

## 3. Speed rules (the owner's acceptance criterion)

FRIDAY voice is judged on SPEED first (FRD-005 thresholds: greeting
≤ 8s to first audio; simple turns 4–6s). A surface must not make a
fast system feel slow, nor a slow one feel fast:

1. **Instant local feedback.** The tap that starts a call changes the
   surface state immediately, from local state alone — zero network
   dependency. Listening indicators come from the local microphone
   and room state, never from a server round-trip.
2. **Honest waiting.** If no audio has arrived ~2s after joining, the
   surface shows a plainly-labelled connecting state. It must never
   show "live"/"listening" before the worker reports `ready` — the
   2026-11-14 failure was a worker that joined and stayed silently
   mute while everything looked fine.
3. **Animation is decoration, never evidence.** Orb motion and
   waveforms may animate from real audio levels; they must not loop
   a "speaking" animation while no audio exists.
4. **Nothing blocks the first word.** No surface asset, font, or
   telemetry call may sit on the path between join and first audio.

## 4. Conversation rules a surface inherits

- **Confirmation (TASK-IG-VOI-01).** When the brain returns the
  `confirmation_required` tool state, the surface's chat stream shows
  FRIDAY's spoken question verbatim. A surface never auto-confirms,
  never paraphrases the question into a weaker one, and never hides
  it behind a toast that can expire unanswered.
- **Dictation (TASK-IG-VOI-02).** While dictation mode is active the
  surface may show a dictating indicator driven by the model's own
  replies; it must not offer a separate "send" button that bypasses
  the spoken control word — the spoken word is the consent.
- **Language (TASK-IG-VOI-03 + TASK-VOI-042).** The effective
  session language (status-file `language`, `en-IN` by default)
  may be displayed; a surface must not offer a language switcher
  that implies mid-call reconfiguration — profiles apply at
  session build.

## 5. AURA candidate mapping (reference)

| AURA element | binds to |
|---|---|
| central orb + pulse | §1c local audio levels; §2 state for colour |
| waveform band | local microphone / remote audio levels only |
| status line | status-file `state` + `detail`, verbatim vocabulary |
| chat stream | brain replies incl. §4 confirmation questions |
| voice/language chips | status-file `voice` + `language` |

## 6. Change discipline

Schema changes are additive-only. Renaming or removing a key, a
state, or a diagnostics field is a breaking change and needs its own
task; adding a key or a state is a contract-compatible change and
must be recorded in this document in the same PR.
