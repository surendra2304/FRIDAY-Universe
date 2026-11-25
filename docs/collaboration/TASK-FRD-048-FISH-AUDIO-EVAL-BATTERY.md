# TASK-FRD-048 — Fish Audio vs Gemini Live: utterance battery + scoring sheet (checkpoint 2)

**Date:** 2026-11-26 ~05:2x IST (Muse TP3)
**Status:** REPO-SIDE ONLY. No live run, no account created, no key used.
**Branch:** `musetp3/task-frd-048-fish-audio-voice-eval` (checkpoint 1: `d4312b88`)
**Board:** TASK-FRD-048 AVAILABLE / owner muse_tp3 / P2 (verified on main
`8600d3e4`, board blob `153ac2fe`).
**Builds on:** `TASK-FRD-048-FISH-AUDIO-EVAL-SCOPE.md` (checkpoint 1).

## 1. Harness finding (verified in repo at main `8600d3e4`)

The existing voice acceptance harness (`FRIDAY/voice_acceptance/`,
TASK-FRD-005) cannot score a Fish Audio arm inside FRIDAY's live path:

- `battery.json` (v1, declared 2026-11-15) fixes 6 turns + greeting with
  pre-declared silence thresholds under the owner's speed-first criterion
  ("a correct answer after a long silence is a FAIL"). Thresholds must not
  be tuned after seeing results.
- `score.py` enforces the post-VOI-009 provider contract: Gemini Live
  only. Its contamination scan (`groq|whisper|orpheus` in a serving
  context) auto-FAILs any non-Gemini serving path. Fish Audio is not in
  that regex, but the contract it enforces is `gemini-realtime` only —
  a Fish TTS stage is the STT → LLM → TTS pipeline shape the owner
  rejected in live test #2 (checkpoint 1, §2).
- `make_utterances.py` renders prompts once with edge-tts (voice/rate
  pinned in the battery, sha256 manifest, byte-identical reuse). That
  render-once discipline is reusable for this evaluation; the LiveKit
  room, participant, and scorer are not.

**Consequence:** this evaluation runs in a separate throwaway harness —
offline render + timed playback per arm, no LiveKit room, no wiring into
FRIDAY. Arm A (Gemini Live) numbers come from the FRD-005 harness shape;
Arms B/C (Fish) are measured as TTS renders and reported separately.
The two latency families are never averaged together: end-to-end
conversational silence (Arm A) vs time-to-first-audio of a render
(Arms B/C) are different facts.

## 2. The 20-utterance battery

Anchor turns 1–6 reuse `battery.json` v1 verbatim so Arm A stays
comparable with every FRD-005 run. Turns 7–20 are evaluation-only,
chosen to stress what a TTS swap actually changes: numbers, names,
code-switching, prosody, and failure-prone consonant clusters.

| # | ID | Text | Stresses |
|---|----|------|----------|
| 1 | delegation_stratex | "FRIDAY, check Stratex for me. What is the balance, how many open positions are there, and how many closed trades are in the ledger?" | long turn, tool answer |
| 2 | context_followup | "And how many closed trades was that, exactly?" | short follow-up |
| 3 | clock_tokyo | "What time is it in Tokyo right now?" | deterministic fast path |
| 4 | memory_remember | "Please remember this for me. My favourite colour is teal." | write path |
| 5 | memory_recall | "What is my favourite colour?" | read path |
| 6 | goodbye | "That is all for now. Goodbye." | clean close |
| 7 | numbers_money | "The invoice total is 12,450 rupees, due on the 3rd of December." | digit grouping, currency |
| 8 | date_time | "Remind me at 6:30 in the evening on Friday, the 28th of November." | date/time prosody |
| 9 | place_names | "Book a cab from Hyderabad to Vijayawada for tomorrow morning." | Indian place names |
| 10 | person_names | "Tell Priya Sharma that the meeting with Arjun Mehta moved to 4 PM." | Indian person names |
| 11 | code_switch | "Kal subah meeting hai, please remind me at nine." | Hindi-English code-switch |
| 12 | abbreviation | "The API returned a 401 at 05:10 IST. Check the logs." | abbreviations, error code |
| 13 | list_turn | "Add three things to my list: milk, a new keyboard, and train tickets." | list intonation |
| 14 | negative | "No, do not send that email yet. I have not approved it." | negation stress |
| 15 | question_rise | "You finished the report already?" | question intonation |
| 16 | cheerful | "That is wonderful news. I am really happy for you." | cheerful emotion |
| 17 | serious | "This is urgent. The server is down and users cannot log in." | serious/urgent emotion |
| 18 | long_sentence | "When the build finishes, run the full test suite, and if everything passes, deploy to staging and send me the summary with the timings." | long sentence, clause pauses |
| 19 | cluster_stress | "The sixth sick sheikh's sixth sheep's sick." | consonant clusters (intelligibility floor) |
| 20 | quiet_instruction | "Speak softly now. It is late and everyone is asleep." | quiet register request |

Render discipline (from `make_utterances.py`): each utterance rendered
once per arm, sha256 recorded in the run manifest, byte-identical reuse
across scoring passes. FRIDAY's voice is female (she/her): Arm B uses a
female library voice; Arm C (clone) uses only a consented female voice
or is dropped — never an unconsented person.

## 3. Arms and blind scoring

- **Arm A — Gemini Live native voice** (baseline). Measured with the
  FRD-005 shape: silence gap per turn vs `battery.json` thresholds.
- **Arm B — Fish Audio library voice** (female). Offline render per
  utterance; TTFA + full-render time from our network vantage.
- **Arm C — Fish Audio own-voice clone** (consented female source only,
  ≥10 s clean audio per vendor docs). Same measures as Arm B.

Blind pass: renders shuffled, arm labels hidden, one scorer (a
different chat per owner rule 3, paired verification) scores each clip
1–5 on intelligibility, naturalness, emotion fit. Scores are recorded
per utterance per arm in the sheet below; medians decide, not means
(one bad clip must not hide behind nineteen good ones — report the
worst three clips per arm by name).

| Utterance | Arm | Intelligibility (1–5) | Naturalness (1–5) | Emotion fit (1–5) | TTFA (ms) | Full turn (s) | Notes |
|-----------|-----|------------------------|-------------------|-------------------|-----------|---------------|-------|
| (20 rows × 3 arms = 60 rows in the live run) | | | | | | | |

Failure-behaviour probes (Arms B/C, throwaway harness only): empty
text, 5,000-character text, network timeout, bad key (401), quota
exhaustion (429). Record status + body shape + whether the failure is
loud or silent. A silent failure is an automatic reject for any live
use.

## 4. Cost and gates (pass/fail before quality is even read)

- **Nothing-paid gate:** vendor free tier `s2.1-pro-free` is $0 through
  **2026-11-30** (four days from checkpoint 1; no SLA). Paid tier
  quoted at $15 / 1M UTF-8 bytes (third-party, conflicts with the free
  claim — checkpoint 1, §3). Cost per 1,000 turns is computed under
  both claims at the battery's real byte count; if the free tier lapses
  or trains on inputs, the candidate fails regardless of quality.
- **Privacy gate:** free-tier training-data terms read on the own
  account before any render; no personal text in probe renders.
- **Licence gate:** library voice + clone terms read before use;
  commercial/attribution terms recorded in the work PR.
- **Architecture gate:** even a quality win does not clear the live
  path — Fish Audio implies rebuilding voice as a pipeline, against
  the owner's Gemini-only rule. Verdict options stay: adopt (owner
  ruling required) / reject / offline-only (e.g. VyralX narration,
  where a TTS stage legitimately exists).

## 5. Push-to-talk (paper assessment checklist)

Evaluated separately from the TTS engine (checkpoint 1, §3):

- Key capture: hold-Space in the Halo console — focus conflicts,
  browser shortcuts, mobile surface (no keyboard).
- Turn latency added: press-to-speak + release-to-send vs current
  server-side VAD; measured against battery thresholds 4.0–6.0 s.
- Barge-in loss: current dual-layer barge-in (local RMS purge
  ~1.935 ms) vs explicit turn-taking — interruption becomes a
  two-handed action.
- Accessibility: hold-to-talk excludes hands-busy use, which is the
  current hands-free contract's point.
- No UI change without an owner ruling; this checklist is the input.

## 6. Next

- Live leg (Arms B/C renders) needs Muse clearance on #1483; owner
  stop order in force (WATCH125 carries no lift). Timing risk: the
  free tier expires 2026-11-30 — if clearance lands after that, the
  cost gate must be re-read before any render.
- SECURITY held: the displayed key in the source reel is never used,
  copied, or stored; own accounts only, keys in Server 2
  `CREDENTIALS.md` / Secure Vault, never in repo, hub, or chat.
- Board flip (AVAILABLE → CLAIMED, branch) rides in the work PR per
  owner rule 4; this checkpoint is a branch commit, not a PR (rule 1).

— Muse TP3, checkpoint 2
