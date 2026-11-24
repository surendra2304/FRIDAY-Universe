# TASK-VOI-034 — FRIDAY voice: acceptance run 19 (calm-window run)

**Worker:** Muse 1. **Claim:** hub #1483 comment 7144471531, 2026-11-25 ~02:36 IST.
**Branch:** `muse1/task-voi-034-acceptance-run-19` from main `677e9e3e`.
**Board:** main `3eab05eb`, blob `47b4b019`, 22,132 lines; VOI-034 verified AVAILABLE, owner muse_1, P1, before claiming. No prior claim, branch or PR.
**Acceptance host:** FRIDAY-Server (15.134.130.145), per coordinator ruling (watch 7126818611).
**Live build:** `fFKg6fXVVhWz4qvLQD0Pi` (FRD-042 build, confirmed in the served page).

## 1. The task

Acceptance: *"Per-probe latency filed with a pass/fail verdict on the 8s greeting-onset bar."*
Sequel to VOI-033 (run 18, never executed — no evidence doc exists) and VOI-030 (run 17,
Muse 13, still CLAIMED, waiting on a calm window). The run uses the
`FRIDAY/voice_acceptance/` probe caller (participant + `run_acceptance.sh`, proven
end-to-end by Muse 13 in TASK-FRG-020) against the deployed FRIDAY-Voice worker on
FRIDAY-Server. Route: bridge `run_shell` on Oracle Server 2 →
`ssh -i ~/.ssh/Oracle-Cloud-x-AWS-Key ubuntu@15.134.130.145`.

## 2. Calm check — 2026-11-25 ~02:37 IST (FRIDAY-Server, read-only, first-hand)

- Load average: **0.10 / 0.10 / 0.09** — calm (calm-host bar is load < 4).
- Host RAM: 1905 MB total, **1101 MB available**; swap 111/8191 MB.
- **FRIDAY.service: active, NRestarts 1, MemoryCurrent 56,229,888 / 209,715,200 —
  26.8% of its 200 MB cgroup cap.** Real headroom. ActiveEnterTimestamp
  2026-11-24 14:48:02 UTC (20:18:02 IST Nov 24 — a restart after the FRD-042 restart
  at 16:18 IST; reason unknown, service healthy at run time).
- **FRIDAY-Voice.service: active since 07:21:18 UTC Nov 24**, NRestarts 0,
  MemoryCurrent 267,644,928. **Inference.service: active.**
- **/health 200 in 0.75 s; /ready 200 in 0.84 s; token endpoint
  `http://127.0.0.1:10000/api/livekit/token` 200 in 1.33 s.**
- Voice status file: state `closed` ("owner left; session closed"), room
  `friday-frd005-20261124-113017` (run 23), updated 11:41:49 UTC — worker idle,
  no other participant running.

**Verdict: calm window confirmed.** Probes run.

Preflight (same probe): all 7 `FRIDAY/voice_acceptance/` files byte-identical to
main (md5 MATCH against main blobs); fleet venv imports livekit/httpx/edge_tts
and PyAV OK; served page contains build `fFKg6fXVVhWz4qvLQD0Pi`; journal shows
the voice worker alive (key keeper refreshing the Gemini key 20:56 UTC).

## 3. The run — room `friday-frd005-20261124-210843`

- **Launched 21:08:43 UTC (02:38:43 IST)**, detached (`nohup bash
  run_acceptance.sh`, output to `/tmp/frd005/voi034-launch.log`), so bridge
  transport drops cannot kill it. Call 21:08:44–21:20:15 UTC (~11.5 min).
- Agent joined in <1 s (`agent-AJ_tDsZKG9rK8y6`, 21:08:45.9 UTC). Provider
  `gemini-realtime:gemini-3.8-live` — PASS, no contamination lines.
- Host stayed calm through the run (load 0.20, 1015 MB available at 21:21 UTC).
- Run artefacts on FRIDAY-Server, `/tmp/frd005/runs/20261124-210843/`: timeline
  (3.9 KB), `journal.txt` (57 KB), `results.json` (4.7 KB), `results.md`
  (1.6 KB), `status.json`, utterances manifest, 66 MB agent WAV. Launcher log
  `/tmp/frd005/voi034-launch.log`.

## 4. Per-probe latency — the acceptance table

| # | Turn | Silence gap (s) | Limit (s) | Latency | Content | Verdict |
|---|------|-----------------|-----------|---------|---------|---------|
| 0 | greeting | 0.73 | 8.0 | PASS | PASS | PASS |
| 1 | delegation_stratex | −7.59 | 12.0 | PASS | PASS | PASS |
| 2 | context_followup | −2.50 | 4.0 | PASS | UNVERIFIED | UNVERIFIED |
| 3 | clock_tokyo | −1.96 | 4.0 | PASS | FAIL | FAIL |
| 4 | memory_remember | −3.96 | 6.0 | PASS | PASS | PASS |
| 5 | memory_recall | −1.54 | 5.0 | PASS | FAIL | FAIL |
| 6 | goodbye | −2.72 | 4.0 | PASS | FAIL | FAIL |

Latency (silence gap) is inside its limit on **all 7 turns**. Negative gaps mean
FRIDAY began answering before the prompt audio finished — the same
overlapping-answer shape as runs 22/23, caused by the 239.8 s greeting burst
(see §6).

**Acceptance verdict: PASS — greeting onset 0.73 s against the 8 s bar.**
Every turn's latency is inside its silence limit. This is the task's
acceptance criterion, and it is met.

## 5. Overall scorer: FAIL — content, not latency

Scorer output (`results.md`, battery v1): overall **FAIL** (scorer exit 1).
Reasons, verbatim: context_followup content UNVERIFIED (followup_count=82,
delegation_count=None); clock_tokyo content FAIL (no time in answer);
memory_recall content FAIL ('teal' missing from answer); goodbye content FAIL
(no assistant reply in journal).

What the evidence actually shows (first-hand from `results.json`):

- **Alignment is the order-based fallback (9 user finals for 6 turns).** The STT
  "heard" text is shifted one turn throughout: clock_tokyo's heard text is the
  followup prompt, memory_remember's heard text is the clock prompt,
  memory_recall's heard text is the remember prompt, goodbye's heard text is
  the recall prompt. Only 5 journal-order answers exist for 7 turns. The
  scorer cannot attribute content reliably under this shape — the same known
  harness weakness documented in run 22 (VOI-037).
- **Delegation content PASS, figures live and consistent.** Greeting answer:
  "The balance is 10,457.75, with 30 open positions and 82 closed trades in
  the ledger." Delegation answer: "Portfolio snapshot (Stratex, FUTURES mode):
  Balance: 10,457.66 — Open positions: 30 SHORT TRXUSDT @ 0.31288 LONG ADAUSDT
  @ 0.1494 SHORT FILUSDT @ 0.5691 SHORT ARBUSDT @ 0.1273 SHORT XRPUSDT @ 0.925
  SHORT SOLUSDT @ 69.02 SHORT BCHUSDT @ 206.88 SHORT MANAUSDT @ 0.06061 —
  Unrealized P&L: +102.41 — Ledger P&L: 82 closed trade(s), net P&L +117.95,
  win rate 18%, profit factor 1.34." The ledger moved since run 23
  (10,465.58 / 29 open / 81 closed) — +1 open, +1 closed, balance −7.83 —
  consistent with a live ledger.
- **Genuine gaps, not attribution artefacts:** the recall question ("What is
  my favourite colour?") received no 'teal' answer anywhere in the journal —
  **the Memora read path is NOT verified by this run** (same as run 22); the
  goodbye turn got no assistant reply in the journal. The clock question's
  time answer was likewise never captured as a separate journal entry. These
  three content legs need a re-probe; they are not latency failures.

## 6. Greeting anomaly (recorded, not scored)

FRIDAY greeted with a full Stratex portfolio snapshot (balance 10,457.75, 30
open positions, 82 closed trades) — **239.8 s of greeting speech**. The
greeting pre-answers the delegation question; that is why every later turn's
gap is negative. Same shape as runs 22/23. Unlike run 23's holding line, the
run-19 greeting itself carried the figures.

## 7. States

- implemented YES (run executed on the live FRD-042 build, first-hand) /
  tested YES (scorer ran; latency 7/7 inside limits, greeting 0.73 s vs 8 s bar) /
  merged NO (work PR open, merge is Muse's — workers never merge own PRs) /
  deployed N/A (acceptance evidence only; no code shipped) /
  production-verified PARTIAL (one calm-window run; the latency bar is met; the
  recall/goodbye/clock content legs need a re-probe under a fixed attribution).
- Usage: 49% of free weekly limit (checked ~02:00 IST; reset Nov 28 21:57 IST).
- No restarts, no deployments, no live writes in this run. No approval blocks.
