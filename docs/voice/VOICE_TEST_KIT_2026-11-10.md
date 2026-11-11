# FRIDAY Voice Test Kit (TASK-VOI-001 — M3 owner session)

**Goal (Master Plan M3):** Surendra speaks to FRIDAY, FRIDAY understands, and answers in its own voice — plus one proactive morning brief (already delivered by TASK-VOI-002's greeting pipeline).

**Status 2026-11-10 (engineering side READY):** FRIDAY-Voice worker verified (`livekit_worker.py` imports cleanly, model `gemini-3.8-live`, voice `Aoede`); token minting verified (LiveKit JWT, 10-minute TTL); LiveKit Cloud `friday-voice.livekit.cloud` resolves and accepts TLS; `FRIDAY-Voice.service` active on Server 1 with memory caps (MemoryMax 300M, TASK-INF-002); 29/29 voice tests green. **The remaining step is the owner's live session.**

## 1. Before the session — run the preflight (2 minutes, on Server 1)

```bash
sudo /opt/friday_universe/venv/bin/python FRIDAY/scripts/voice_preflight.py
```
Expected: `9/9 checks passed — voice loop is READY for the owner test`.
Any FAIL line names the broken link (env var, SDK, token mint, server reachability, FRIDAY token endpoint, worker import). Nothing in the output reveals secrets.

## 2. The owner session (5-minute script)

Open **https://friday-universe.duckdns.org/friday/** (the FRIDAY PRIME dashboard):
1. Authorize with the owner key once (paste when the gate asks; stored in the browser).
2. Enable **Voice mode** (the mic icon) — the dashboard requests a LiveKit room token from `/api/livekit/token`, joins the room, and the FRIDAY-Voice worker picks up the session.
3. Say the six test phrases below, one at a time, waiting for each answer.

| # | Say this | Pass looks like |
|---|---|---|
| 1 | "Hello FRIDAY, are you there?" | Warm greeting in a natural voice, ~2 s latency, no clipping |
| 2 | "What time is it right now?" | Correct spoken time (grounded answer, not hallucinated) |
| 3 | "How's the fleet doing?" | Real per-agent fleet answer (the TASK-API-002 surface, spoken) |
| 4 | "Summarize my portfolio." | Real Stratex snapshot spoken (balance/positions; honest failure if the engine is unreachable) |
| 5 | "నాకు తెలుగు లో మాట్లాడు" (speak Telugu) | Reply in natural conversational Telugu (worker instruction) |
| 6 | "Thanks FRIDAY, that's all." | Polite sign-off |

## 3. What to record as evidence (per the plan's evidence rules)

- Date/time + which device and browser.
- The 6 pass/fail results + any noticeable latency or clipped audio.
- `sudo journalctl -u FRIDAY-Voice --since "-30 min" | grep -iE "session|error|stall"` output (or confirm it's clean).
- Post this to issue #35 → TASK-VOI-001 closes as VERIFIED with the owner's own words as evidence.

## 4. Known caveat to watch (recorded in handoff.md)

LiveKit telemetry logged **event-loop-blocked warnings (158–679 ms; threshold 100 ms)** on 2026-11-08 19:35–20:10 UTC. The cause is not yet root-caused (TASK-INF-002 follow-up). During the test, listen specifically for: chopped/missing first words, long pauses mid-answer, or the mic cutting the owner off. Note any of these per phrase — that's the exact evidence needed to chase the latency issue.

## 5. If something fails

| Symptom | First check |
|---|---|
| No voice mode button / token error | preflight `friday.token_endpoint` line; is the owner key pasted? |
| Token OK but room silent | `systemctl status FRIDAY-Voice` + journal (worker picks up sessions) |
| Voice answers but wrong facts | that's the agent surface, not voice — report the phrase to the relevant task |
| Choppy audio | the event-loop warnings above; grab the journal excerpt |

---

## E10 addendum — accent-accuracy module (2026-11-12, batch 9b)

The kit above verifies the voice loop end-to-end. The E10 module verifies
ACCURACY on the owner's actual speech patterns (Hyderabad Indian-English with
natural Telugu-English code-mixing):

- **Phrase corpus:** `FRIDAY/src/friday/voice/accent_phrase_corpus.json` — 18
  phrases across retroflex traps, Indian-English vocabulary (do the needful,
  prepone, out of station, revert), Telugu-English mixing, lakh/crore trading
  quantities, and fleet-domain phrasing.
- **Scoring sheet:** `python3 FRIDAY/scripts/accent_scoring_sheet.py` prints
  (or `--out FILE.md` writes) the scoring sheet — one row per phrase with the
  pass criteria; ≥90% (17/18) = kit PASS. One "pardon?" per phrase is allowed.
- **Worker side:** the FRIDAY-Voice instruction now explicitly comprehends
  Telugu-accented English and Telugu-English mixes, mirrors the owner's mix,
  and never mocks or over-corrects his accent.
- **Run it:** after the 6-phrase session above, speak the 18 corpus phrases
  and fill the sheet (~5 extra minutes). Post the filled sheet to issue #35
  (TASK-E10 evidence).
