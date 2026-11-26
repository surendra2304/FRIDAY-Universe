# TASK-FRD-048 — Gemini Live baseline + push-to-talk design (checkpoint 5)

**Date:** 2026-11-26 ~18:3x IST (Muse TP3)
**Status:** REPO-SIDE ONLY. No live run, no account created, no key used.
**Branch:** `musetp3/task-frd-048-fish-audio-voice-eval`
(checkpoints 1–4: `d4312b88`, `9fc7a307`, `3430343a`, `fe3dfe1d`)
**Board:** TASK-FRD-048 AVAILABLE / owner muse_tp3 / P2 (verified on main
`087e05d6`, board blob `8f65b20f`, 24,253 lines).
**Builds on:** scope (cp1), battery + scoring sheet (cp2), harness spec +
cost arithmetic (cp3), offline validator + verifier packet (cp4).

**WATCH160 ruling 3 (hub 7191807363) — receipt:** FRD-048 = CONDITIONAL.
TP3 files by Nov 29: evaluation harness, Gemini Live baseline, push-to-talk
design, public free-tier facts. Harness (cp3) + free-tier facts (cp1 §3,
cp3 §4–5) were already filed. This checkpoint files the remaining two:
the Gemini Live baseline (§1) and the push-to-talk design (§2). The Fish
Audio live leg needs an account route the coordinator cannot create;
escalated as an owner decision before the Nov 30 window closes. TP3
creates no account meanwhile. Live gate CLOSED (owner stop order).

## 1. Gemini Live baseline (Arm A) — repo-evidenced, no new live run

Source of truth in repo at main `087e05d6`:

- **Architecture spec** `FRIDAY/docs/voice_architecture.md` v2.1.0
  (2026-08-19, "FULLY IMPLEMENTED & REAL-WORLD TESTED"): persistent
  WebSocket via `client.aio.live.connect`
  (`gemini-2.5-flash-native-audio-latest`), continuous 16 kHz 16-bit PCM
  in (40 ms chunks), jitter-buffered 24 kHz 16-bit PCM out, server-side
  Gemini VAD (`start_sens=HIGH`, `end_sens=HIGH`, `silence=400ms`),
  dual-layer barge-in (server `interrupted=True` + local RMS purge,
  **1.935 ms** measured purge latency), native tool execution with
  authorization gating, session resumption + GoAway handling.
- **Acceptance battery** `FRIDAY/voice_acceptance/battery.json` v1
  (declared 2026-11-15, TASK-FRD-005; thresholds pre-declared, must not
  be tuned after results). Owner criterion: speed first — a correct
  answer after a long silence is a FAIL.
  - greeting (connect → first agent audio): threshold **8.0 s**
    (calibration: VOI-008 warm-host 4.69 s; VOI-007 baseline 25.6 s).
  - delegation_stratex: **12.0 s** (VOI-006 best 10.52 s with substance;
    VOI-007 18.60 s under load would FAIL — correctly).
  - context_followup / clock_tokyo / goodbye: **4.0 s** each
    (VOI-005/007 measured 2.23–2.34 s for clock/context turns).
  - memory_remember: **6.0 s**; memory_recall: **5.0 s**
    (measured 4.59–4.60 s).
- **Baseline definition for this evaluation:** Arm A is scored on the
  FRD-005 shape — per-turn conversational silence vs the thresholds
  above, anchors 1–6 of the cp2 battery verbatim. Arm A latency is
  end-to-end conversational silence; Arms B/C latency is TTS
  time-to-first-audio. The families are reported side by side, never
  averaged (cp2 §1, cp3 §3). A fresh Arm A live run is NOT claimed in
  this checkpoint — the live gate is closed; the numbers above are the
  filed repo baseline the live leg will re-measure against when cleared.
- **Architecture gate (unchanged):** provider contract is
  `gemini-realtime` only since TASK-VOI-009; owner rule "Gemini is the
  only AI for voice"; owner live test #2 rejected the STT → LLM → TTS
  pipeline shape. Fish Audio can only enter the live path by rebuilding
  voice as a pipeline — a voice-quality win alone does not clear this
  gate (cp1 §5). Offline-only use (e.g. VyralX narration, where a TTS
  stage legitimately exists) remains a possible verdict shape.

## 2. Push-to-talk design (paper design; no UI change without owner ruling)

The candidate pattern's second half — hold-Space push-to-talk — is an
interaction change, not a voice source (cp1 §3). It must be evaluated
separately from the TTS engine. Absence proof (cp1 §2): zero
push-to-talk code in the tree at `bf5a08b7`; greenfield.

### 2.1 What it would replace

Current contract: always-listening continuous stream, server-side VAD
turn detection (400 ms silence), dual-layer barge-in (user can interrupt
FRIDAY mid-sentence; local purge 1.935 ms). Push-to-talk replaces
implicit turn-taking with explicit turn-taking: mic open only while the
key is held.

### 2.2 Design sketch (throwaway-prototype grade, not a FRIDAY change)

- **Key capture:** hold-to-talk on Space (keydown opens mic gate,
  keyup closes it and marks end-of-turn). Client-side only; no server
  protocol change — the gate sits in front of the existing 16 kHz PCM
  stream. Debounce: ignore key-repeat events; require ≥150 ms hold to
  count as a turn (accidental taps discarded, recorded).
- **Turn latency added:** explicit end-of-turn removes the 400 ms VAD
  silence wait but adds human key-release lag (~100–300 ms typical,
  unmeasured — to be measured in the prototype, not assumed). Net
  effect is an empirical question; the prototype measures
  keyup → first-response-audio against the Arm A silence figures in §1.
- **Barge-in loss (the real cost):** with mic gated off while FRIDAY
  speaks, the user cannot interrupt by voice. Mitigations to evaluate:
  (a) key press during playback = interrupt (reuse the local RMS purge
  path on keydown); (b) keep barge-in only in hands-free mode. Either
  way, push-to-talk must not silently drop the interruption contract —
  a turn the user cannot stop is a regression, recorded as such.
- **Accessibility / ergonomics:** hold-to-talk excludes hands-free use
  (driving, cooking, mobility constraints) and adds a physical hold for
  long turns. It helps in noisy rooms and shared spaces (no false VAD
  triggers, no ambient speech captured). Verdict shape: opt-in mode,
  never a replacement default, unless the owner rules otherwise.
- **Privacy delta:** mic physically gated when key is up — strictly
  less audio leaves the device than always-listening. This is the one
  axis where push-to-talk beats the current contract outright.
- **Evaluation method (when cleared):** same 20-utterance battery
  (cp2 §2), prototype client only, measure: keyup→audio latency per
  turn, false-start rate, interrupt success via keydown, scorer notes
  on turn-taking feel. No FRIDAY live-path wiring; no UI change ships
  without an owner ruling.

## 3. Public free-tier facts (restated from cp1 §3 / cp3 §4–5, verified 2026-11-26)

- Vendor blog: `s2.1-pro-free` $0 under fair use **through 2026-11-30**,
  no SLA, no latency guarantee.
- Third-party conflicts carried, not resolved on paper: TokenMix
  $15 / 1M UTF-8 bytes, no API free tier; APIModels gateway
  $0.005 / 1K bytes free tier + warning free-tier requests may be used
  for model training.
- Cost at battery mean (58.8 bytes/turn): $0.00 free; $0.88/1k turns at
  $15/1M; $0.29/1k at $5/1M (cp3 §4). Under nothing-paid, any nonzero
  per-byte production cost fails unless the owner rules otherwise.
- The displayed key in the source reel is never used, copied, or stored
  (board SECURITY line, binding). Own accounts only.

## 4. State after this checkpoint

- WATCH160 Nov-29 packet complete on this branch: harness (cp3),
  Gemini Live baseline (§1), push-to-talk design (§2), public free-tier
  facts (§3). Filed Nov 26, ahead of Nov 29.
- Live leg still BLOCKED: owner stop order (live gate CLOSED,
  WATCH160) + no Fish Audio account route (owner decision, escalated).
  If no route by Nov 30, TP3 parks the live leg and files the partial
  evaluation per WATCH160 ruling 3.
- Board flip rides in the work PR (owner rule 4); no PR opened (rule 1:
  one work PR when DONE or genuinely BLOCKED — the live leg is blocked
  but the packet above is the coordinator-ordered deliverable; PR
  timing follows the Nov 30 ruling).

— Muse TP3
