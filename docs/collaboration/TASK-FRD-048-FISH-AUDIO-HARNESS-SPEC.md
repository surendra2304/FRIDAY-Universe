# TASK-FRD-048 — Fish Audio vs Gemini Live: throwaway-harness spec + cost arithmetic (checkpoint 3)

**Date:** 2026-11-26 ~07:2x IST (Muse TP3)
**Status:** REPO-SIDE ONLY. No live run, no account created, no key used.
**Branch:** `musetp3/task-frd-048-fish-audio-voice-eval`
(checkpoint 1: `d4312b88`; checkpoint 2: `9fc7a307`)
**Board:** TASK-FRD-048 AVAILABLE / owner muse_tp3 / P2 (verified on main
`4dda14b1`, board blob `a0e5edaf`, 23,404 lines).
**Builds on:** `TASK-FRD-048-FISH-AUDIO-EVAL-SCOPE.md` (checkpoint 1),
`TASK-FRD-048-FISH-AUDIO-EVAL-BATTERY.md` (checkpoint 2).

Checkpoint 2 fixed the battery, arms, and gates. This checkpoint fixes
everything that must be decided *before* the first live render, so the
live leg (when cleared) is execution, not design: request shape,
manifest schema, latency method, blinding, and the cost arithmetic at
the battery's real byte count.

## 1. Throwaway harness spec (Arms B/C; no FRIDAY wiring)

- **Shape:** one standalone script, run once per arm, outside FRIDAY's
  live path. No LiveKit room, no FRIDAY import, no service change.
  Output: audio files + one JSON manifest (§2). The harness is deleted
  or archived with the work PR; it is never wired into FRIDAY.
- **Request (per utterance):** single TTS render of the exact battery
  text (checkpoint 2, §2), no text normalisation beyond the vendor's
  own (record any vendor-side change if the response echoes it).
  Model `s2.1-pro-free` (free tier only — nothing-paid gate). Output
  format: the vendor default for the model; record format + sample
  rate in the manifest. FRIDAY's live path is 24 kHz PCM out
  (checkpoint 1, §2) — if the render format differs, resampling for
  playback is a scorer-side step, recorded, never silent.
- **Voice selection:** Arm B — one female library voice, chosen once,
  voice id recorded in the manifest, never changed mid-battery.
  Arm C — own-voice clone from a consented female source only
  (≥10 s clean audio per vendor docs; 1–2 min better), or Arm C is
  dropped and the drop is recorded as a finding. Never an
  unconsented person. FRIDAY is female (she/her) — a male voice arm
  would not be a like-for-like comparator.
- **Timeout / retry:** per-request timeout 30 s; at most one retry on
  a transport error, zero retries on 4xx (a 401/429 is a finding, not
  a retry trigger). Every attempt, including failures, gets a
  manifest row.
- **Failure probes (after the 20 clean renders, same harness):**
  empty text, 5,000-character text, bad key (401), quota exhaustion
  (429 — only if reachable without spending; otherwise recorded as
  not-probed with reason). Network timeout is probed by the 30 s cap
  on a deliberately unreachable endpoint variant only if it costs
  nothing; otherwise not-probed. Record status + body shape + loud
  vs silent. A silent failure (success-shaped response, no audio)
  is an automatic reject for any live use (checkpoint 2, §3).
- **Key handling:** own account only, key read from Server 2
  `CREDENTIALS.md` / Secure Vault at run time, never in the script,
  manifest, repo, hub, or chat. The displayed key in the source reel
  is never used, copied, or stored (board SECURITY line, binding).

## 2. Manifest schema (one row per render attempt)

```json
{
  "utterance_id": "numbers_money",
  "arm": "B",
  "model": "s2.1-pro-free",
  "voice_id": "<recorded at run time>",
  "text_utf8_bytes": 63,
  "attempt": 1,
  "http_status": null,
  "ttfa_ms": null,
  "full_render_ms": null,
  "audio_sha256": null,
  "audio_format": null,
  "sample_rate_hz": null,
  "error_shape": null,
  "started_at_ist": null
}
```

Fields are null here by design — this is the schema, not results.
`text_utf8_bytes` is filled from §4 now (it needs no live run).
`audio_sha256` follows the `make_utterances.py` render-once
discipline (checkpoint 2, §1): byte-identical reuse across scoring
passes; a re-render with a different hash is a new attempt row, never
an overwrite.

## 3. Latency method (pre-declared, not tunable after results)

- **TTFA** = wall time from request send to first audio byte
  received, measured in the harness process on the run host.
  **Full render** = request send to last byte. Both recorded per
  attempt; the battery figure per utterance per arm is the median of
  3 attempts (attempts 1–3; failures recorded, not dropped).
- **Vantage:** renders run from our network (Server 2 or owner
  machine — recorded in the work PR). Vendor-claimed TTFA ~70–90 ms
  (checkpoint 1, §3) is a vendor-vantage claim; our figure will
  include our network hop and is reported as ours, never compared
  raw against the vendor number without the vantage note.
- **Families stay separate** (checkpoint 2, §1): Arm A conversational
  silence (FRD-005 thresholds) is never averaged with Arms B/C TTFA.
  The verdict table reports them side by side with the difference
  named.

## 4. Cost arithmetic (computed now, at the battery's real byte count)

UTF-8 byte counts of the 20 battery utterances (checkpoint 2, §2),
computed 2026-11-26:

- Per utterance: 131, 45, 35, 57, 28, 29, 63, 65, 61, 66, 48, 52, 69,
  55, 32, 50, 59, 135, 43, 52. **Total 1,175 bytes; mean 58.8
  bytes/turn.**
- Cost per 1,000 turns at the battery mean, under each pricing claim
  (checkpoint 1, §3 — claims conflict; all three carried):
  - Free tier `s2.1-pro-free` $0 (through 2026-11-30): **$0.00**.
  - Paid $15 / 1M UTF-8 bytes: **$0.88 / 1,000 turns**
    (58.8 × 1,000 / 1M × $15).
  - Gateway $0.005 / 1K bytes (= $5 / 1M): **$0.29 / 1,000 turns**.
- Sensitivity (paid $15/1M): 40 bytes/turn → $0.60/1k; 60 → $0.90/1k;
  100 → $1.50/1k. The battery mean (58.8) sits at the 60-byte line.
- The evaluation itself (20 utterances × 2 Fish arms = 2,350 bytes)
  costs $0.04 at the paid rate — cost is not a reason to skip the
  eval; it is a reason the *production* decision needs the free-tier
  question answered (§5). Under the nothing-paid rule, any nonzero
  per-byte production cost fails unless the owner rules otherwise —
  the arithmetic above is the input to that ruling, not a substitute
  for it.

## 5. Blinding + free-tier expiry decision tree

- **Blinding:** renders shuffled with a recorded seed; arm labels
  replaced by clip ids; the id→arm mapping is held by the paired
  verifier (owner rule 3, a different chat) and revealed only after
  scores are filed. Scorer sees clip id + audio only. Medians decide;
  worst three clips per arm reported by utterance name (checkpoint 2,
  §3).
- **Expiry:** the free tier runs through **2026-11-30**. If Muse
  clearance lands after that date:
  1. Re-read pricing on the own account before any render. If no $0
     tier exists, Arms B/C do not run — the verdict is filed on
     paper evidence + the cost gate alone (candidate fails
     nothing-paid), with the expiry named as the cause.
  2. If a $0 tier exists under new terms, re-read the training-data
     terms first (privacy gate, checkpoint 2, §4); probe renders use
     battery text only, never personal text.
  3. Either way, the architecture gate is unchanged: a quality win
     does not clear the live path (owner Gemini-only rule; Fish
     implies the rejected STT → LLM → TTS shape). Verdict options
     stay adopt (owner ruling required) / reject / offline-only.

## 6. Next

- Live leg still needs Muse clearance on #1483; owner stop order in
  force (WATCH129–131 carry no lift; WATCH130/131 rulings restate
  it). No account, no render, no server change until cleared.
- On clearance, execution order is fixed: privacy/licence terms read
  → voice selection → 20 renders × 3 attempts (Arms B/C) → failure
  probes → blind scoring by verifier → verdict in the work PR with
  manifest + audio hashes.
- Board flip (AVAILABLE → CLAIMED, branch) rides in the work PR per
  owner rule 4; this checkpoint is a branch commit, not a PR (rule 1).

— Muse TP3, checkpoint 3
