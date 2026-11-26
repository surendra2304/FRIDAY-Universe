# TASK-VOI-036 — FRIDAY voice: acceptance run 21 (calm-window run)

**Worker:** Muse 1. **Claim:** hub #1483 comment 7156377968, 2026-11-25 ~13:24 IST,
on coordinator watch086 assignment (7156322977: "Muse 1: VOI-035 merged — claim
VOI-036 now").
**Branch:** `muse1/task-voi-036-acceptance-run-21` from main `2c6f913`.
**Board:** main `2c6f913`, 22,652 lines; VOI-036 verified AVAILABLE, owner null,
branch null, pr null, P1, before claiming. Prior claim (Muse 2, 7127132406)
released 2026-11-24 ~22:40 IST per coordinator ruling 7137935600; no competing
claim. VOI-035 and VYR-069 MERGED flips owed from earlier runs ride in this PR
(see §9).
**Acceptance host:** FRIDAY-Server (15.134.130.145), per coordinator ruling
(watch 7126818611).
**Live build:** `fFKg6fXVVhWz4qvLQD0Pi` (FRD-042 build, confirmed in the served page).

## 1. The task

Acceptance: *"Per-probe latency filed with a pass/fail verdict on the 8s greeting-onset bar."*
Sequel to VOI-035 (run 20, Muse 1, MERGED via PR #1790, merge `2c6f913`). The run
uses the `FRIDAY/voice_acceptance/` probe caller (participant +
`run_acceptance.sh`, proven end-to-end by Muse 13 in TASK-FRG-020) against the
deployed FRIDAY-Voice worker on FRIDAY-Server. Route: bridge `run_shell` on
server 3 (FRIDAY-Server) directly.

## 2. Stop-order check — first-hand, hub #1483 read through comment 7156471557

- Owner stop order ~16:42 IST Nov 24 ("Don't move anything now") froze ALL server
  moves; partial lift 17:26 IST covers ONLY (1) key architecture, (2) bridge work,
  (3) the Inference move. Under it Muse 2 released VOI-036 ~22:40 IST Nov 24
  (no calm-window call + stop order).
- The voice-probe leg is NOT a server move: coordinator ruling 7126818611
  (Nov 24 ~13:52 IST): "RULING — acceptance host is FRIDAY-Server, not S1...
  VOI-030/035 hold LIFTS: M13, probe in the next calm window against
  FRIDAY-Server." Runs 19 (VOI-034) and 20 (VOI-035) executed the identical leg
  and MERGED (PR #1732, merge `4bed6107`; PR #1790, merge `2c6f913`).
- Watch086 (~13:24 IST Nov 25, hub #1483 comment 7156322977) assigns VOI-036 to
  Muse 1 as queue head with "claim VOI-036 now" — a fresh coordinator
  direction, post-dating the stop order. No newer stop-order change in the hub
  through comment 7156471557 (~13:29 IST).
- The S2 VyralX tree state (watch086: restored, actor/authorisation unconfirmed)
  was NOT touched — no restore, no install, no server move; out of scope.

**Verdict: live leg callable as a read-only probe against FRIDAY-Server.**

## 3. Calm check — 2026-11-25 ~13:31 IST (FRIDAY-Server, read-only, first-hand)

- Load average: **0.02 / 0.11 / 0.12** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, **1080 MB available**; swap 122/8191 MB.
- **FRIDAY.service: active, NRestarts 2** (same as run 20 — no restart since,
  ActiveEnterTimestamp 2026-11-24 21:27:28 UTC). **MemoryCurrent 51,589,120
  / 209,715,200 — 24.6% of its 200 MB cgroup cap.** Real headroom.
- **FRIDAY-Voice.service: active since 07:21:18 UTC Nov 24**, NRestarts 0,
  MemoryCurrent 258,920,448. **Inference.service: active.**
- **/health 200 in 3.16 s**; **/ready 200 in 0.80 s; token endpoint
  `http://127.0.0.1:10000/api/livekit/token` 200 in 0.18 s.**
- Voice status file: state `closed` ("owner left; session closed"), room
  `friday-frd005-20261125-064054` (run 20), updated 06:52:27 UTC — worker idle,
  no other participant running.

**Verdict: calm window confirmed.** Probes run.

Preflight (same probe): all 7 `FRIDAY/voice_acceptance/` files byte-identical to
main `2c6f913` (md5 MATCH: README.md, battery.json, make_utterances.py,
participant.py, run_acceptance.sh, score.py, score_check.py); fleet venv imports
livekit/httpx/edge_tts and PyAV OK; served page contains build
`fFKg6fXVVhWz4qvLQD0Pi`; journal shows the voice worker alive (key keeper
refreshing the Gemini key 07:35 UTC).

## 4. The run — room `friday-frd005-20261125-080422`

- **Launched 08:04:22 UTC (13:34:22 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi036-launch.log`), so bridge
  transport drops cannot kill it. Call 08:04:23–08:15:51 UTC (~11.5 min).
- Agent joined in <1 s (`agent-AJ_YeFNLMJsh9Pe`, 08:04:25.546 UTC). Provider
  `gemini-realtime:gemini-3.8-live` — PASS, no contamination lines.
- Host stayed calm through the run (load 0.54 at 08:08 UTC, 0.18 at 08:18 UTC).
- Run artefacts on FRIDAY-Server, `/tmp/frd005/runs/20261125-080422/`: timeline
  (3.9 KB), `journal.txt` (52 KB), `results.json` (4.0 KB), `results.md`
  (1.6 KB), `status.json`, utterances manifest, 66.6 MB agent WAV. Launcher log
  `/tmp/frd005/voi036-launch.log`.

## 5. Per-probe latency — the acceptance table

| # | Turn | Silence gap (s) | Limit (s) | Latency | Content | Verdict |
|---|------|-----------------|-----------|---------|---------|---------|
| 0 | greeting | 0.68 | 8.0 | PASS | PASS | PASS |
| 1 | delegation_stratex | −7.60 | 12.0 | PASS | PASS | PASS |
| 2 | context_followup | −2.50 | 4.0 | PASS | UNVERIFIED | UNVERIFIED |
| 3 | clock_tokyo | −1.96 | 4.0 | PASS | FAIL * | FAIL * |
| 4 | memory_remember | −3.95 | 6.0 | PASS | PASS | PASS |
| 5 | memory_recall | −1.55 | 5.0 | PASS | FAIL * | FAIL * |
| 6 | goodbye | −2.73 | 4.0 | PASS | FAIL * | FAIL * |

\* Scorer verdict; first-hand journal read (§6) shows the correct answer WAS given —
attribution artefact of the order-based fallback, not a genuine gap.

Latency (silence gap) is inside its limit on **all 7 turns**. Negative gaps mean
FRIDAY began answering before the prompt audio finished — the same
overlapping-answer shape as runs 19/20/22/23, caused by the ~240 s greeting burst
(see §7).

**Acceptance verdict: PASS — greeting onset 0.68 s against the 8 s bar.**
Every turn's latency is inside its silence limit. This is the task's
acceptance criterion, and it is met.

## 6. Overall scorer: FAIL — content, not latency; all of it attribution

Scorer output (`results.md`, battery v1): overall **FAIL** (scorer exit 1).
Reasons, verbatim: context_followup content UNVERIFIED (followup_count=None
delegation_count=82); clock_tokyo content FAIL (no time in answer);
memory_recall content FAIL ('teal' missing from answer); goodbye content FAIL
(no assistant reply in journal).

What the evidence actually shows (first-hand from `results.json` + `journal.txt`):

- **Alignment is the order-based fallback (9 user finals for 6 turns).** The STT
  "heard" text is shifted one turn throughout: clock_tokyo's heard text is the
  followup prompt, memory_recall's heard text is the clock prompt, goodbye's
  heard text is "My favorite color is teal." (the recall prompt). Only 5
  journal-order answers were extracted for 7 turns — but the journal holds
  **8 assistant `conversation_item_added` entries** (16 `role=assistant` lines
  counting the JSON-duplicate format). The scorer cannot attribute
  content reliably under this shape — the same known harness weakness documented
  in runs 19, 20 and 22 (VOI-037).
- **All four scorer content failures are attribution artefacts, verified
  first-hand in the journal:**
  - **Clock:** FRIDAY answered "It is currently 5:11 PM in Tokyo, Japan."
    at 08:11:44 UTC — correct (08:11 UTC = 17:11 JST). The scorer attributed
    that answer to the context_followup turn.
  - **Memory recall:** FRIDAY answered "Your favorite color is teal." at
    08:13:55 UTC — **the Memora read path IS verified by this run** (second
    run in a row, after run 20's 06:50:26 UTC recall). The scorer attributed
    that answer to the clock_tokyo turn.
  - **Goodbye:** FRIDAY replied "Goodbye, Boss. I'll be here whenever you
    need me." at 08:14:55 UTC. The scorer saw no reply because its 5-answer
    extraction ended before it.
  - **Context followup:** FRIDAY answered "That was exactly 82 closed trades
    recorded in the ledger." at 08:10:41 UTC — the followup figure IS in the
    journal; the scorer reports followup_count=None only because its
    attribution cannot match it.
  - **Memory remember** is a genuine PASS, and stronger than the scorer's
    "reply present": "Got it, Boss — locked in. That's mine to keep now,
    pinned and it never fades." at 08:12:55 UTC. (The scorer's extracted
    answer "Understood, Boss. Just let me..." is timestamped 08:14:51 UTC in
    the journal — a truncated fragment just before the goodbye prompt, not a
    remember-turn reply; the attribution shift again.)
- **Run 20's one genuine gap is CLOSED: delegation.** FRIDAY gave real Stratex
  figures this run — "The current balance is 10,444.12, with 30 open positions
  and 82 closed trades recorded in the ledger. Please note that live trading is
  currently blocked by your fail-closed guard, so this is for the demo account
  only." (08:08:59 UTC) — and the delegation turn scores a genuine PASS
  (figures + Stratex terms present), the first clean delegation PASS in the
  run 19/20/21 sequence. No holding-lines-only leg remains: 'stratex' 10
  mentions in the journal, all with figures attached.

## 7. Greeting anomaly (recorded, not scored)

FRIDAY's greeting speech ran **~240 s** (08:04:25–08:08:25 UTC) — the same
shape as runs 19/20/22/23. As in run 20, the greeting burst has NO journal text
at all: the first assistant `conversation_item_added` after joining is an empty
role=None item at 08:04:25 UTC, and the first spoken text is "I'm pulling up
the latest Stratex data for you right now." at 08:08:37 UTC, so the burst's
content is only in the 66.6 MB agent WAV and is UNVERIFIED from the journal.
That is why every later turn's gap is negative: the agent was already speaking
when each prompt arrived.

## 8. States

- implemented YES (run executed on the live FRD-042 build, first-hand) /
  tested YES (scorer ran; latency 7/7 inside limits, greeting 0.68 s vs 8 s bar) /
  merged NO (work PR open, merge is Muse's — workers never merge own PRs) /
  deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window run; the latency bar is met; the
  clock/recall/goodbye/followup content legs are verified by first-hand journal
  read despite the scorer's attribution; the delegation figures leg is now
  verified too — new vs run 20).
- Usage: 65% of free weekly limit (checked first-hand this run; reset Nov 28 21:57 IST).
- No restarts, no deployments, no live writes in this run. No approval blocks.
- Bridge transport was flaky on the launch call (the launching exec hit the
  120 s local timeout while the remote nohup kept running; verified first-hand
  afterwards that the launch DID apply — log exists, participant running — no
  duplicate launch). The run itself was detached on FRIDAY-Server and unaffected.

## 9. Board flips riding in this PR

- **TASK-VOI-036 AVAILABLE → IN_REVIEW** (owner muse_1, branch
  `muse1/task-voi-036-acceptance-run-21`, this work PR) — this task.
- **TASK-VOI-035 IN_REVIEW → MERGED** (work PR #1790, merge `2c6f913`,
  merged 2026-11-25 13:16:55 IST by surendra2304, CI 9/9 green on head
  `5395cb40`, verified first-hand) — owed: the flip was not in PR #1790.
- **TASK-VYR-069 IN_REVIEW → MERGED** (work PR #1774, merge `f6b912a6`,
  merged 2026-11-25 11:27:00 IST by surendra2304, head `763e953d`,
  CI 10/10 green with 485/485 VyralX tests in the contracts job log, verified
  first-hand) — owed: the flip was not in PR #1774.
- No code or test files in this PR (evidence doc + board only), so the FUT-030
  CI-coverage lesson does not apply — there are no new tests to list in any
  workflow; CI green here means the board YAML parses and the validators pass.

— Muse 1
