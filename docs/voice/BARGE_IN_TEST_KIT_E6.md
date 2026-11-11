# E6 — Voice Barge-in + Natural Pacing 5-Minute Test Kit

**Checklist E6 (MASTER_COMPLETION_CHECKLIST) — Batch 8, ZAI Agent 2.**

The owner verifies barge-in (interrupting FRIDAY mid-sentence) and natural
pacing (no awkward pauses, no talking-over) in a structured 5-minute call.
This is the kit the owner runs after every voice-path change.

## What "barge-in" means here

FRIDAY is speaking a long answer. The owner starts talking. FRIDAY must:

1. **Detect** the owner's voice within ~300ms (VAD start sensitivity = LOW,
   already configured in `gemini_live_session.py`).
2. **Stop** its own speech immediately — not finish the current sentence.
3. **Listen** to what the owner said and respond to THAT, not resume the
   interrupted sentence.

The inverse — FRIDAY barging in on the owner — must NOT happen. FRIDAY only
speaks after the owner stops (VAD end sensitivity = HIGH, 800ms silence).

## The 5-minute kit

Run this after every voice-path deploy. Each step is one minute.

### Minute 1 — cold connect

- Tap the voice orb.
- **Pass:** FRIDAY greets within 2s, audio is clear, no echo.
- **Fail:** latency > 3s, or audio is garbled — check the E7 diagnostics card.

### Minute 2 — barge-in (owner interrupts FRIDAY)

- Ask: *"Tell me about the fleet status in detail."*
- After FRIDAY says 2-3 sentences, interrupt with: *"Stop, what's the time?"*
- **Pass:** FRIDAY stops within ~300ms, answers the time, does NOT resume the fleet answer.
- **Fail:** FRIDAY keeps talking, or resumes the interrupted sentence.

### Minute 3 — natural pacing (no talking-over)

- Ask a long question: *"What did IntelX find about the crypto market this week, and is now a good time to rebalance?"*
- **Pass:** FRIDAY pauses ~500ms after you stop, then answers; no overlap; the answer addresses both parts.
- **Fail:** FRIDAY starts before you finish, or there's a 3s+ awkward silence.

### Minute 4 — memory on the voice line (E4 / B11)

- Say: *"Remember that my chai preference is strong, less sugar."*
- **Pass:** FRIDAY confirms out loud: *"Got it — strong chai, less sugar. Saved."*
- Then ask in chat: *"what's my chai preference"* — the stored fact appears.
- **Fail:** FRIDAY answers conversationally but never stores; the chat query returns nothing.

### Minute 5 — fleet question by voice (E5)

- Say: *"What's IntelX doing right now?"*
- **Pass:** FRIDAY calls the `fleet_status` tool (or `agents_live`) and reports the real IntelX status, not a guess.
- **Fail:** FRIDAY hallucinates a status without calling the tool.

## Recording the result

After the kit, the owner posts one line to the owner Telegram channel:

> Voice kit E6 (date): 5/5 pass. (or) Voice kit E6 (date): 3/5, failed step 2 + 4. Step 2: FRIDAY didn't stop. Step 4: memory not stored.

The owner does NOT need to file an issue for a perfect run. Any failure
becomes a task on the next batch.

## What this kit does NOT cover

- **Unlimited minutes (E8):** still blocked on the ARM server capture (G9).
  The kit runs on the free LiveKit tier (30-min cap, 3-min idle disconnect).
- **Accent accuracy (E10):** a separate check — see `docs/voice/ACCENT_CHECK_E10.md`.
- **Quality tuning (E9):** the VAD/voice-name config is in `config.py`
  (`voice_vad_start_sensitivity`, `voice_vad_end_sensitivity`, `voice_name`).
