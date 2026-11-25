# TASK-FRD-048 — Fish Audio voice + push-to-talk vs Gemini Live: evaluation scope (checkpoint 1)

**Date:** 2026-11-26 ~04:2x IST (Muse TP3)
**Status:** SCOPED, repo-side only. No live run, no account created, no key used.
**Branch:** `musetp3/task-frd-048-fish-audio-voice-eval`
**Board:** TASK-FRD-048 AVAILABLE / owner muse_tp3 / P2 (verified on main `bf5a08b7`, board blob `49eaef16`).

## 1. Acceptance (from board)

An evaluation compares the make-your-own-jarvis pattern (Fish Audio voice
library / own-voice clone, OpenRouter free key, hold-Space push-to-talk) with
FRIDAY's current Gemini Live voice source and interaction, using our own
accounts only.

**SECURITY (binding):** the source reel displays what appears to be a real API
key on screen; that key must never be used, copied, or stored — by this task
or any other. This evaluation uses only accounts/keys created for FRIDAY
Universe, held in Server 2 `CREDENTIALS.md` / Secure Vault, never in repo,
hub, or chat.

## 2. Current FRIDAY voice (verified in repo at main `bf5a08b7`)

- **Live path is Gemini Live end-to-end.** `FRIDAY/src/friday/voice/gemini_live_session.py`
  (1,374 lines): full-duplex WebSocket via google-genai `client.aio.live.connect`,
  16 kHz PCM in / 24 kHz PCM out, dual-layer barge-in, native tool execution
  with authorization gating, session resumption + GoAway handling, memory
  transcription commitment. Credentials via `friday.auth.credential_pool.GeminiCredentialPool`.
- **Architecture spec:** `FRIDAY/docs/voice_architecture.md` v2.1.0 — server-side
  Gemini VAD, local RMS barge-in purge ~1.935 ms, jitter-buffered playback.
- **Provider contract is `gemini-realtime` only** since TASK-VOI-009
  (`FRIDAY/docs/VOICESTUDIO_EVALUATION.md`). Owner standing rule: Gemini is
  the only AI for voice; owner live test #2 rejected the STT → LLM → TTS
  pipeline shape ("like Google voice search").
- **Legacy local stack still in config:** `FRIDAY/config/voice_config.json` —
  faster-whisper large-v2 STT + Piper TTS + Porcupine wake word. This is NOT
  the live path; it is the fallback/local surface.
- **Absence proof:** full repo tree at `bf5a08b7` (8,717 paths) contains zero
  Fish Audio references and zero push-to-talk code (only `.githooks/pre-push`
  matches "push"). Both halves of the candidate pattern are greenfield.

## 3. Candidate pattern (public sources, 2026-11-26; conflicts flagged)

Fish Audio S2.1 Pro (vendor + third-party, verify on own account before use):

- Neural TTS with streaming (HTTP + WebSocket), 83 languages, instant voice
  clone from ≥10 s clean audio (1–2 min better), Python/JS SDKs, MCP server.
- Vendor-claimed time-to-first-audio ~70–90 ms (single source; third parties
  quote ~100–200 ms). Treat as unproven until measured from our servers.
- **Pricing conflict — must resolve live:** fish.audio blog says
  `s2.1-pro-free` is $0 under fair use **through 2026-11-30** (four days
  away), no SLA, no latency guarantee. TokenMix (Jun 2026) says API is
  $15 / 1M UTF-8 bytes with no API free tier. APIModels gateway lists
  $0.005 / 1K bytes on the free tier and warns free-tier requests may be used
  for model training. Under the owner's nothing-paid rule, a paid per-byte
  tier is out unless the owner rules otherwise; a free tier expiring
  2026-11-30 cannot anchor a production voice decision.
- Push-to-talk (hold-Space) is an interaction change, not a voice source:
  it replaces always-listening VAD + barge-in with explicit turn-taking.
  It must be evaluated separately from the TTS engine.

## 4. Evaluation design (what "done" requires)

Repo-side (no clearance needed):

1. Pin the comparator: same 20-utterance battery (reuse
   `FRIDAY/voice_acceptance/battery.json` shape) spoken by (a) Gemini Live
   native voice, (b) Fish Audio library voice, (c) Fish Audio own-voice
   clone — FRIDAY's voice is female (she/her); clone source must be a
   consented female voice or a library voice, never an unconsented person.
2. Score blind on: intelligibility, naturalness, emotion control, latency
   (TTFA + full-turn), failure behaviour (timeout, 4xx/5xx, quota), cost per
   1,000 turns at real usage, privacy (training-data terms), licence.
3. Push-to-talk prototype assessment on paper first: key capture, turn
   latency added, barge-in loss, accessibility — against the current
   hands-free contract. No UI change without owner ruling.

Live leg (needs Muse clearance on #1483; owner stop order currently in
force — WATCH122, no lift):

4. Own Fish Audio account (free tier only), key in CREDENTIALS.md, one real
   end-to-end turn through a throwaway harness — NOT wired into FRIDAY's
   live path. Evidence: audio files + timings + API responses filed in the
   work PR.
5. Verdict with live evidence: adopt / reject / offline-only (e.g. VyralX
   narration, where a TTS stage legitimately exists) — the VoiceStudio
   precedent (`FRIDAY/docs/VOICESTUDIO_EVALUATION.md`) is the format.

## 5. Gates and risks

- Owner rule "Gemini is the only AI for voice" + rejected STT→LLM→TTS shape:
  Fish Audio can only enter the live path by rebuilding voice as a pipeline.
  The evaluation must state this cost plainly; a voice-quality win alone does
  not clear the architecture gate.
- Free-tier expiry 2026-11-30 + training-data terms: if the free tier lapses
  or trains on inputs, the candidate fails the nothing-paid / privacy bars
  regardless of quality.
- Oracle servers (~956 MB RAM) cannot host local inference; Fish Audio is a
  cloud API, so RAM is not the blocker — network hop + quota + cost are.
- No key from the source reel is used, copied, or stored at any step.

## 6. Next

- Repo-side: draft the 20-utterance battery + scoring sheet (this branch).
- Live leg: clearance request stands with this checkpoint; no server run,
  no account creation until Muse clears it on #1483.
- Board flip (AVAILABLE → CLAIMED, branch) rides in the work PR per owner
  rule 4; this checkpoint is a branch commit, not a PR (rule 1).

— Muse TP3, checkpoint 1
