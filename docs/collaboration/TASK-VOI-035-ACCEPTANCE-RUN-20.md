# TASK-VOI-035 — FRIDAY voice: acceptance run 20 (calm-window run)

**Worker:** Muse 1. **Claim:** hub #1483 comment 7154911576, 2026-11-25 ~12:05 IST,
on coordinator watch082 assignment (7154799918).
**Branch:** `muse1/task-voi-035-acceptance-run-20` from main `f73bddd7`.
**Board:** main `f73bddd7`, 22,618 lines; VOI-035 verified AVAILABLE, owner null,
branch null, pr null, P1, before claiming. Prior claim (Muse 13, 7119841152)
released 2026-11-24 ~21:52 IST; no competing claim.
**Acceptance host:** FRIDAY-Server (15.134.130.145), per coordinator ruling
(watch 7126818611).
**Live build:** `fFKg6fXVVhWz4qvLQD0Pi` (FRD-042 build, confirmed in the served page).

## 1. The task

Acceptance: *"Per-probe latency filed with a pass/fail verdict on the 8s greeting-onset bar."*
Sequel to VOI-034 (run 19, Muse 1, MERGED via PR #1732). The run uses the
`FRIDAY/voice_acceptance/` probe caller (participant + `run_acceptance.sh`, proven
end-to-end by Muse 13 in TASK-FRG-020) against the deployed FRIDAY-Voice worker on
FRIDAY-Server. Route: bridge `run_shell` on Oracle Server 2 →
`ssh -i ~/.ssh/Oracle-Cloud-x-AWS-Key ubuntu@15.134.130.145`.

## 2. Stop-order check — first-hand, hub #1483 full scan (1,275 comments)

- Owner stop order ~16:42 IST Nov 24 ("Don't move anything now") froze ALL server
  moves; partial lift 17:26 IST covers ONLY (1) key architecture, (2) bridge work,
  (3) the Inference move. Under it Muse 13 released VOI-035 ~21:52 IST Nov 24
  (no calm-window call + stop order) and Muse 2 released VOI-036.
- The voice-probe leg is NOT a server move: coordinator ruling 7126818611
  (Nov 24 ~13:52 IST, read first-hand in the scan): "RULING — acceptance host is
  FRIDAY-Server, not S1... VOI-030/035 hold LIFTS: M13, probe in the next calm
  window against FRIDAY-Server." Run 19 (VOI-034) executed the identical leg
  2026-11-25 ~02:38 IST and MERGED (PR #1732, merge `4bed6107`).
- Watch082 (~12:00 IST Nov 25) assigns VOI-035 to Muse 1 as queue head with
  "calm-window probes" — a fresh coordinator direction, post-dating the stop order.
  No newer stop-order change in the hub through comment 7154955335.
- The S2 VyralX tree deletion (watch082 fleet alert: 1,801 files deleted, VyralX
  service down) was NOT touched — no restore, no install, no server move; out of
  scope for this task.

**Verdict: live leg callable as a read-only probe against FRIDAY-Server.**

## 3. Calm check — 2026-11-25 ~12:09 IST (FRIDAY-Server, read-only, first-hand)

- Load average: **0.17 / 0.13 / 0.10** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, **1112 MB available**; swap 125/8191 MB.
- **FRIDAY.service: active, NRestarts 2** (was 1 in run 19 — one restart since,
  ActiveEnterTimestamp 2026-11-24 21:27:28 UTC, ~02:57 IST, shortly after run 19
  ended; reason unknown, service healthy at run time). **MemoryCurrent 42,291,200
  / 209,715,200 — 20.2% of its 200 MB cgroup cap.** Real headroom.
- **FRIDAY-Voice.service: active since 07:21:18 UTC Nov 24**, NRestarts 0,
  MemoryCurrent 262,508,544. **Inference.service: active.**
- **/health 200 in 3.33 s** (slower than run 19's 0.75 s, still 200); **/ready 200
  in 0.85 s; token endpoint `http://127.0.0.1:10000/api/livekit/token` 200 in
  1.39 s.**
- Voice status file: state `closed` ("owner left; session closed"), room
  `friday-frd005-20261124-210843` (run 19), updated 21:20:15 UTC — worker idle,
  no other participant running.

**Verdict: calm window confirmed.** Probes run.

Preflight (same probe): all 7 `FRIDAY/voice_acceptance/` files byte-identical to
main (md5 MATCH against raw main files fetched this run); fleet venv imports
livekit/httpx/edge_tts and PyAV OK; served page contains build
`fFKg6fXVVhWz4qvLQD0Pi`; journal shows the voice worker alive (key keeper
refreshing the Gemini key 06:37 UTC). First bridge attempt dropped mid-read
(IncompleteRead, known flaky transport); retry landed.

## 4. The run — room `friday-frd005-20261125-064054`

- **Launched 06:40:54 UTC (12:10:54 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi035-launch.log`), so bridge
  transport drops cannot kill it. The launching exec call hit a local service
  restart mid-flight; verified first-hand afterwards that the launch DID apply
  (log exists, participant running) — no duplicate launch. Call 06:40:55–
  06:52:27 UTC (~11.5 min).
- Agent joined in <1 s (`agent-AJ_9QLk3SB9DbmY`, 06:40:57.262 UTC). Provider
  `gemini-realtime:gemini-3.8-live` — PASS, no contamination lines.
- Host stayed calm through the run (load 0.78 at 06:52 UTC, 0.25 at 06:54 UTC).
- Run artefacts on FRIDAY-Server, `/tmp/frd005/runs/20261125-064054/`: timeline
  (3.9 KB), `journal.txt` (46 KB), `results.json` (3.8 KB), `results.md`
  (1.6 KB), `status.json`, utterances manifest, 66 MB agent WAV. Launcher log
  `/tmp/frd005/voi035-launch.log`.

## 5. Per-probe latency — the acceptance table

| # | Turn | Silence gap (s) | Limit (s) | Latency | Content | Verdict |
|---|------|-----------------|-----------|---------|---------|---------|
| 0 | greeting | 0.52 | 8.0 | PASS | PASS | PASS |
| 1 | delegation_stratex | −7.59 | 12.0 | PASS | FAIL | FAIL |
| 2 | context_followup | −2.50 | 4.0 | PASS | UNVERIFIED | UNVERIFIED |
| 3 | clock_tokyo | −1.96 | 4.0 | PASS | FAIL * | FAIL * |
| 4 | memory_remember | −3.96 | 6.0 | PASS | PASS | PASS |
| 5 | memory_recall | −1.54 | 5.0 | PASS | FAIL * | FAIL * |
| 6 | goodbye | −2.73 | 4.0 | PASS | FAIL * | FAIL * |

\* Scorer verdict; first-hand journal read (§6) shows the correct answer WAS given —
attribution artefact of the order-based fallback, not a genuine gap.

Latency (silence gap) is inside its limit on **all 7 turns**. Negative gaps mean
FRIDAY began answering before the prompt audio finished — the same
overlapping-answer shape as runs 19/22/23, caused by the 239.9 s greeting burst
(see §7).

**Acceptance verdict: PASS — greeting onset 0.52 s against the 8 s bar.**
Every turn's latency is inside its silence limit. This is the task's
acceptance criterion, and it is met.

## 6. Overall scorer: FAIL — content, not latency; most of it attribution

Scorer output (`results.md`, battery v1): overall **FAIL** (scorer exit 1).
Reasons, verbatim: delegation_stratex content FAIL (number=False
stratex_terms=False); context_followup content UNVERIFIED (followup_count=None
delegation_count=None); clock_tokyo content FAIL (no time in answer);
memory_recall content FAIL ('teal' missing from answer); goodbye content FAIL
(no assistant reply in journal).

What the evidence actually shows (first-hand from `results.json` + `journal.txt`):

- **Alignment is the order-based fallback (8 user finals for 6 turns).** The STT
  "heard" text is shifted one turn throughout: memory_recall's heard text is
  "My favorite color is teal." (the recall answer itself), goodbye's heard text
  is "What is my favorite color?" (the recall prompt). Only 5 journal-order
  answers were extracted for 7 turns — but the journal holds **8 assistant
  `conversation_item_added` entries**. The scorer cannot attribute content
  reliably under this shape — the same known harness weakness documented in
  runs 19 and 22 (VOI-037).
- **Three of the five scorer failures are attribution artefacts, verified
  first-hand in the journal:**
  - **Clock:** FRIDAY answered "It is currently 3:48 PM in Tokyo, Japan."
    at 06:48:16 UTC — correct (06:48 UTC = 15:48 JST). The scorer attributed
    that answer to the greeting turn.
  - **Memory recall:** FRIDAY answered "Your favorite color is teal." at
    06:50:26 UTC (`role=assistant`, journal line 2026-11-25 06:50:26,598) —
    **the Memora read path IS verified by this run** (new vs run 19, where no
    'teal' answer existed anywhere in the journal). The scorer attributed that
    answer to the context_followup turn.
  - **Goodbye:** FRIDAY replied twice — "Understood, Boss. Just let me know
    if you need anything else." (06:51:23 UTC) and "Goodbye, Boss. Have a
    wonderful day." (06:51:26 UTC). The scorer saw no reply because its
    5-answer extraction ended before them.
  - **Memory remember** is a genuine PASS, and stronger than the scorer's
    "reply present": "Of course, I can remember that for you." (06:49:15 UTC)
    followed by "Got it, Boss — locked in: my favorite color is teal.
    That's mine to keep now." (06:49:30 UTC).
- **One genuine gap: delegation.** FRIDAY gave holding lines only —
  "I'm currently pulling up the latest details for you and will have those
  numbers ready in just a..." (06:45:11 UTC) and "I'm still retrieving those
  details and will let you know the exact number of closed trades very..."
  (06:47:15 UTC) — and no Stratex figures appear anywhere in the journal:
  'balance' 6 mentions and 'stratex' 8 mentions are all user-prompt lines;
  'portfolio' 0 mentions; no `10,xxx` balance figure. No tool-call line for
  the Stratex lookup. Unlike run 19, where the greeting burst carried the
  portfolio snapshot, this run produced no figures in the journal at all.
  The delegation content FAIL stands.
- **Context followup** stays UNVERIFIED (no delegation figures exist to match
  against, so followup_count/delegation_count are both None).

## 7. Greeting anomaly (recorded, not scored)

FRIDAY's greeting speech ran **239.9 s** (06:40:57–06:44:57 UTC) — the same
shape as runs 19/22/23. Unlike run 19, the greeting burst has NO journal text
at all: the first assistant `conversation_item_added` is the delegation
holding line at 06:45:11 UTC, so the burst's content is only in the 66 MB
agent WAV and is UNVERIFIED from the journal. That is why every later turn's
gap is negative: the agent was already speaking when each prompt arrived.

## 8. States

- implemented YES (run executed on the live FRD-042 build, first-hand) /
  tested YES (scorer ran; latency 7/7 inside limits, greeting 0.52 s vs 8 s bar) /
  merged NO (work PR open, merge is Muse's — workers never merge own PRs) /
  deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window run; the latency bar is met; the
  recall/clock/goodbye content legs are verified by first-hand journal read
  despite the scorer's attribution; the delegation figures leg needs a re-probe
  under a fixed attribution).
- Usage: 62% of free weekly limit (per coordinator watch082; reset Nov 28 21:57 IST).
- No restarts, no deployments, no live writes in this run. No approval blocks.
- Bridge transport was flaky through this run (several IncompleteRead drops on
  poll/preflight/journal reads; fresh MCP sessions recovered each time). The run
  itself was detached on FRIDAY-Server and unaffected.

— Muse 1
