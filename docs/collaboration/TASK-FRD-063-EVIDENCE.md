# TASK-FRD-063 — FRIDAY voice calm-window acceptance run 27

## Verdict: FAIL (harness verdict; content unverifiable — see root cause)

- **Run:** `20261127-042219`, room `friday-frd005-20261127-042219`, 04:22:19–04:33:55 UTC (09:52:19–10:03:55 IST), ~11.6 min.
- **Provider:** gemini-realtime:gemini-3.8-live, voice Aoede — provider PASS.
- **Calm window (04:18 UTC, FRIDAY-Server, first-hand):** load 0.15/0.06/0.02; host RAM 1106 MB available of 1905 MB; FRIDAY.service active, 27.2% of cap; /health 200 in 1.06 s; /ready 200 in 1.11 s. Caveat: FRIDAY restarted cleanly 03:53:19 UTC and memory spiked to 91.0% at 04:02 UTC before easing (34.4 → 42.9 MB over 60 s at ~04:20 UTC) — judged a genuine calm window by the run-22 bars.
- **Harness:** all 7 `FRIDAY/voice_acceptance/` files byte-identical to main at preflight; battery v1, fingerprint `aa5a36eb…`.

## Per-probe results (latency = headline metric: 7/7 PASS)

| # | Turn | Silence gap (s) | Limit (s) | Latency | Content | Verdict |
|---|------|-----------------|-----------|---------|---------|---------|
| 0 | greeting | 4.63 | 8.0 | PASS | PASS (agent spoke) | PASS |
| 1 | delegation_stratex | −7.59 | 12.0 | PASS | FAIL (number=False, stratex_terms=False) | FAIL |
| 2 | context_followup | −2.50 | 4.0 | PASS | UNVERIFIED (followup_count=None, delegation_count=None) | UNVERIFIED |
| 3 | clock_tokyo | −1.95 | 4.0 | PASS | FAIL (no time in answer) | FAIL |
| 4 | memory_remember | −3.95 | 6.0 | PASS | FAIL (no assistant reply in journal) | FAIL |
| 5 | memory_recall | −1.54 | 5.0 | PASS | FAIL ('teal' missing from answer) | FAIL |
| 6 | goodbye | −2.72 | 4.0 | PASS | FAIL (no assistant reply in journal) | FAIL |

Negative gaps mean the agent track already had audio before the prompt finished playing — the agent was speaking over the prompts, not answering after them.

## Root cause: the realtime session kept closing — content was never measured

- **Scorer alignment:** `no assistant items in journal window (0 user finals for 6 turns)`; `journal_order_answers: []`; `heard: ""` on every turn. The journal contains zero transcript/final/STT lines (`grep -c` = 0).
- **Session errors (journal.txt, first-hand):** Gemini Realtime closed mid-call, repeatedly — `1008 None. Session closed due to client inactivity` (04:24:30 and 04:28:33 UTC), then `1008 None. Requested entity was not found` / `BidiGenerateContent session not found or expired` (04:30:30, 04:30:32 UTC), each followed by reconnect retries. The model therefore never received or transcribed the probe prompts, so no content check could pass. This is a session-stability failure, not a proven wrong answer.
- **Agent audio flowed anyway:** 692.19 s on the agent track (66,450,284-byte wav); per-turn `speech_s` 62–128 s reflects track audio, not verified model replies. The fixed-line greeting played (`VOICE fixed-line greeting played (recorded line)`); conversation items logged empty (`conversation_item_added role=None text=''`).
- **Regression vs run 26** (`20261126-035014`): that run's scorer had 9 user finals for 6 turns (order-based fallback), overall UNVERIFIED. Run 27 has 0 finals — a new failure mode.
- **Session close:** state `closed`, `owner left; session closed`, job `AJ_kmUsBaWQGazf`, 04:33:55 UTC.

## What this means

- **Speed (headline metric): PASS across the board** — every gap inside its limit, greeting 4.63 s vs 8.0 s.
- **Content: UNVERIFIED, not disproven.** The FAIL verdict is the harness's, driven by an empty journal. Do not read it as "FRIDAY gave wrong answers" — no answer text exists to judge.
- **Recommendation:** investigate the 1008 session closures before run 28 (the plugin's own hint notes a 1008 often means the model name doesn't match the API in use; inactivity close vs key/model mismatch needs a verdict from the voice owner). Do not re-run blindly in the next calm window.

## Artefacts

- FRIDAY-Server `/tmp/frd005/runs/20261127-042219/`: `results.json`, `results.md`, `journal.txt` (65,648 bytes), `friday-frd005-20261127-042219_timeline.json`, agent wav (66.4 MB), `utterances_manifest.json`, `status.json`. Launcher log `/tmp/frd063-run27.log` (launcher pid 84745).
- Run by Muse TP14 (muse_tp14), claimed 2026-11-27 ~09:40 IST; branch `musetp14/task-frd-063-calm-window-acceptance-run-27`; board claim flip PR #2066 held (board already shows CLAIMED on main via coordinator flip).
- Board note: the board's evidence line names `TASK-FRD-061-EVIDENCE.md` (copy typo); the files list + acceptance name this file, `TASK-FRD-063-EVIDENCE.md`.

## Status

- **COMPLETE: work PR opened, verdict FAIL (harness) with content unverifiable per root cause above. Flip request: TASK-FRD-063 → IN_REVIEW.**
