# TASK-INF-047 — Gemini completion times on ~9k-token prompts (n=5), routing deadline set from the numbers (live FRIDAY-Server)

Date: 2026-11-27, harness run ~15:43–15:51 IST. Worker: Muse TP9.
Assignment: Burn Enforcer 14:44 §D (hub #2045 comment 7214462343), confirmed by
WATCH214-CORR (hub 7214925794) — TP9 → INF-047 as head; WATCH214's muse_3
assignment withdrawn, BE governs. Claim: hub #2045 comment 7215223521.
Branch: `musetp9/task-inf-047` from main e9f7231f.

## What was measured

Same prompt and method as TASK-INF-029 / INF-LLM-003, so the samples are
comparable: the exact INF-019 probe A construction — a code-review task over a
400-function Python module (400 identical `def add` helpers), 35,214 chars.
Model requested: `gemini-flash-latest` (the INF-019 reroute target). Output:
`max_tokens=200`, `temperature=0`.

Method: a harness process on FRIDAY-Server (Server 3) in the live Inference
environment (venv312, cwd `/opt/friday_universe/Inference`, the service's own
`.env`), separate from the running `Inference.service`, which was never
touched, restarted, or reconfigured. Adapted from the INF-029 harness
(`/tmp/inf029_measure_harness.py` on Server 1) with only the task label,
output path, stage name, and host changed, plus one new variant (D):
- **A. Direct Gemini adapter calls (5 trials)** — the adapter called directly
  with a 150 s timeout, so the gateway's 15 s primary-attempt slice cannot cut
  the call off. This measures Gemini's true completion time for the prompt.
- **B. Direct call on the gateway-compressed prompt** (what the production
  reroute path actually sends Gemini).
- **C. Gateway path, explicit 60 s budget** — the production reroute behaviour
  on the explicit-timeout path (opts out of the TASK-INF-022 large-prompt
  direct-to-fallback bypass by design, so this trial exercises the primary
  slice itself).
- **D. Default path over HTTP against the live service process**
  (`POST http://127.0.0.1:8001/v1/chat/completions`, no explicit timeout) —
  the TASK-INF-022 large-prompt bypass should fire, skipping the Gemini
  primary entirely.

Live settings read on FRIDAY-Server during the run: `REQUEST_TIMEOUT = 60.0`,
`PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`, so the
primary slice is `min(60 x 0.6, 15) = 15.0 s`. All three unset in the S3
`.env` — code defaults apply. S3 checkout `06ff9ee6` (main at 12:27 IST;
board-only merges since); gateway.py at that ref contains the INF-022 bypass
(6 mentions) and the INF-029 citations (4 mentions) — the live service runs
the merged deadline code. No deploy was needed for this probe.

## Results

### A. Direct Gemini completion times (full prompt, 35,214 chars) — n=5 fresh

| Trial | Elapsed | Upstream latency | Served model | Outcome |
|-------|---------|------------------|--------------|---------|
| 1 | 125.39 s | 123.05 s | gemini-3.6-flash | Served, 209 chars, finish STOP, 50 completion tokens |
| 2 | 150.10 s | — | — | **TimeoutError — did not complete within the 150 s cap** (right-censored) |
| 3 | 113.62 s | 11.58 s | gemini-3.6-flash | Served, 241 chars, finish STOP, 48 completion tokens |
| 4 | 19.60 s | 15.17 s | gemini-3.6-flash | Served, 248 chars, finish STOP, 51 completion tokens |
| 5 | 10.79 s | — | — | **RuntimeError 503 — model at high demand** (failed fast, not a completion) |

All three served trials gave real, correct answers (each identifies the 400
redefined `add` functions). Gemini's own token count for the prompt is
**13,519 prompt tokens on every served trial**.

- **Median: 113.62 s** (sorted elapsed: 10.79, 19.60, 113.62, 125.39, 150.10).
- **p95: 150.10 s by nearest-rank** (5th of 5). Trial 2 is right-censored — it
  never completed within 150 s — so the true p95 is **≥ 150 s**.
- **Inside the 15 s primary slice: 0 of 5 completions** (trial 5 errored at
  10.79 s — a fast 503 failure, not a completion).
- **Combined with INF-029 (n=5) + INF-LLM-003 (n=3):** 5.42, 6.38, 10.79,
  14.27, 19.60, 42.00, 67.32, 74.76, 99.32, 113.62, 125.39, 150.10, 150.13 —
  median **67.32 s**, 3/13 inside 15 s (5.42, 6.38, 14.27).

### B. Direct call on the gateway-compressed prompt

The gateway's token compression shrinks the prompt to 32,814 chars /
12,620 est. tokens (-7%). This time the compressed attempt **completed in
29.89 s** (served gemini-3.6-flash, STOP, 216 chars, 43 completion tokens,
Gemini's own count 12,719 prompt tokens) — unlike LLM-003, where the single
compressed attempt timed out past 150 s, and slower than INF-029's 23.52 s.
Three samples across runs, three different outcomes (23.52 s / 29.89 s /
>150 s): compression does not reliably rescue the deadline for this prompt
shape.

### C. Gateway path, explicit 60 s budget (INF-019 repeat)

Elapsed **18.59 s**. Gemini's primary attempt was cut at **15.0 s** —
fallback provenance: requested `gemini/gemini-flash-latest`, actual
`openrouter/nvidia/nemotron-3.5-lightning:free`, reason "Request deadline
exceeded for provider 'gemini' after 15.0s". This is the **fifth** occurrence
of the Gemini deadline cut on this prompt (INF-019 probe A 14.7 s ×2, LLM-003
14.7 s, INF-029 15.0 s, now 15.0 s). The fallback served a correct answer
end-to-end in 18.59 s (INF-029: 18.34 s — production behaviour unchanged).

### D. Default path over HTTP against the live service process

Elapsed **21.53 s**, HTTP 200. Served `meta-llama/llama-3.3-70b-instruct`,
938 chars, real correct answer, finish `length`, usage prompt 10,515 /
completion 200. The Gemini primary was **skipped entirely** — zero seconds
burned on a primary attempt that would miss — and the request routed directly
to the fallback ladder, served end-to-end in 21.53 s, inside the 60 s budget.
This is the live-service proof that the TASK-INF-022 bypass fires on
FRIDAY-Server's running process, not just in the gateway code.

## Decision: KEEP the deadline — set from these numbers

**Before:** `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`,
`PRIMARY_ATTEMPT_MAX_SECONDS = 15.0` → primary slice `min(60 × 0.6, 15) = 15.0 s`.
**After:** unchanged — `60.0 / 0.6 / 15.0`, primary slice **15.0 s**. The
decision is recorded in code: the `PRIMARY_ATTEMPT_MAX_SECONDS` field
description in `Inference/app/core/config.py` now cites this measurement
alongside INF-029. No defaults-pinning test was added: see G7.

Why keep, on this evidence:

- **0 of 5** fresh completions finished inside the 15 s primary slice, and the
  median is **113.62 s** with p95 **≥ 150 s**. A primary slice that covered
  the p95 would need to be ≥ 150 s — it would hold every timed-out primary
  for 2.5 minutes before the fallback ladder runs, which is exactly the
  failure the cap exists to prevent (TASK-INF-010).
- The fallback already serves a correct answer end-to-end in **18.59 s**
  (explicit path) / **21.53 s** (default path). The reroute path works as a
  system; it is the Gemini rung, not the request, that misses.
- The TASK-INF-022 large-prompt bypass already routes default
  (no-explicit-timeout) large Gemini primaries directly to the fallback; the
  15 s slice governs the explicit-timeout path and short prompts. No deadline
  value in a sane range changes the outcome for this prompt shape.
- The numbers are now filed at n=5 (this task) plus n=5 (INF-029) plus n=3
  (LLM-003): combined median 67.32 s, 3/13 inside 15 s. No further sample
  size fixes the tail problem for a 15 s slice.

## Safety and service state

- No key value was read, printed, logged, or stored. Key pools unchanged
  (gemini 15 total / 15 active / 0 quarantined, groq 15/15/0, openrouter
  15/15/0, nvidia 2/2/0, before and after).
- Failover log went 0 -> 1 event (the gateway trial only; the direct adapter
  calls bypass the gateway and log nothing, by design).
- Live service healthy before and after (`/health` 200, MainPID 58827
  unchanged, active since 2026-11-26 06:43 UTC). Direct adapter calls bypass
  the gateway rate limiter; 8 calls over ~8 minutes is a light load, noted here.
- S3 harness artefacts: `/tmp/inf047_measure_harness.py`,
  `/tmp/inf047_measure.json`, `/tmp/inf047_measure.log`.

## Gaps and observations

- **G1 — near-duplicate board record TASK-INF-046.** The board carries
  TASK-INF-046 (same title/measurement, owner muse_tp12, P1, evidence
  `docs/verification/INF046_GEMINI_TIMING.md`) alongside this task. This run
  did INF-047 as assigned (BE §D). Coordinator: close one as the duplicate of
  the other, or fold the numbers together — do not run the same measurement
  twice.
- **G2 — every served trial came back as a different model than requested
  (INF-029 G2, confirmed again).** All served direct trials requested
  `gemini-flash-latest` and were served as `gemini-3.6-flash` (trials 1, 3, 4
  + compressed). The `-latest` alias resolution is not pinned, so the slow
  tail may not be the same model path as the fast ones.
- **G3 — trial 5's fast 503 is a different failure than a deadline miss.**
  The adapter surfaces Gemini high-demand as a RuntimeError after 10.79 s.
  In the gateway this is a transient error (key retry / fallback), not a
  deadline cut — the "0/5 inside 15 s" count counts completions only, and the
  fast failure is reported separately rather than counted as inside.
- **G4 — the HTTP trial's served model differs from the gateway trial's.**
  Default path served `meta-llama/llama-3.3-70b-instruct`; explicit path
  served `nvidia/nemotron-3.5-lightning:free`. Ladder rung selection varies
  run to run; both served correct answers. The HTTP usage prompt_tokens
  (10,515) is the gateway's post-compression/routing count, not Gemini's
  count (13,519) — not comparable to the direct trials.
- **G5 — most of the wall time is Gemini-side, not transport.** Trial 3:
  11.58 s upstream latency vs 113.62 s elapsed; trial 1: 123.05 s vs
  125.39 s. The gap is model-side queueing/thinking before the completion
  lands — the elapsed is what the caller waits, and it is the deadline-relevant
  number.
- **G6 — the S3 checkout (06ff9ee6) is behind live main (e9f7231f).** The
  gateway/config code measured is identical to main's on the deadline path
  (INF-022/INF-029 citations present; config.py description identical to
  main's). No deploy was needed or made.
- **G7 — no PR-CI home for Inference unit tests.** As in INF-029 G6,
  `Inference/tests/test_provider_gateway_deadlines.py` is collected by no
  PR-triggered workflow, so the TASK-REL-068 collection guard fails any PR
  that touches it; no defaults-pinning test was added in this PR for that
  reason. It belongs with the Inference-test CI-collection follow-up.

## Reproduction

Harness (kept on FRIDAY-Server):
`PYTHONPATH=/opt/friday_universe/Inference /opt/friday_universe/venv312/bin/python /tmp/inf047_measure_harness.py`
from `/opt/friday_universe/Inference`. It rebuilds the INF-019 prompt
byte-identically, runs the direct trials (adapter timeout 150 s), the
compressed trial, the gateway trial, and the HTTP default-path trial, and
writes `/tmp/inf047_measure.json`.

## States

- **implemented:** YES (this run)
- **tested:** YES — live measurement n=5 + compressed + gateway + HTTP trials
  on FRIDAY-Server; CI to be verified on the work PR head (Muse merges only)
- **merged:** NO — work PR opened this run, awaiting Muse
- **deployed:** NO — description-only change; no behaviour change, nothing to
  deploy beyond the merge
- **production-verified:** YES — the measurement itself is the production
  evidence (live FRIDAY-Server, live Gemini, live gateway path); the deadline
  decision is filed from those numbers

— Muse TP9
