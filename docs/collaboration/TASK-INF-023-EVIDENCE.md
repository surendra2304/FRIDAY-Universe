# TASK-INF-023 — Gemini ~9k-token completion timing and routing deadline evidence

**Worker:** Muse 15 · **Date:** 2026-11-28 · **Branch:** `muse15/task-inf-023-gemini-9k-timing`
**Claim:** hub issue #2045 comment 7237926970 (WATCH268 §C assignment).
**Board acceptance:** measure Gemini completion time on ~9k-token prompts and set the routing deadline from that evidence; file the numbers.

## Verdict

**Fresh live measurement: RUN. Deadline decision: KEEP `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`.**

The approved server-local route was used on FRIDAY-Server (`friday-server`, bridge server 3), the live Inference host: `Inference.service` active, MainPID 58827 before and after, listening on port 8001. The measurement ran 2026-11-28T10:31:40Z to 2026-11-28T10:41:03Z (16:01–16:11 IST). No server move, restart, env flip, deploy, or live-money action was performed. Credentials stayed server-side; no secret value was read into this record, printed, or stored.

Fresh direct Gemini sample (n=5): median **116.266 s**, p95 by nearest-rank **>150 s** (right-censored), **0/5** inside the 15 s primary slice, **1/5** inside 60 s, **2/5** hit the 150 s adapter timeout without completing. This sample is markedly slower than TASK-INF-058's fresh n=5 (median 5.642 s) on the identical prompt and method — the Gemini rung for this prompt class is currently slow and variable, not just tailed. Combined with the filed n=13 sample, n=18 median is **45.44 s**, **6/18** inside 15 s, **10/18** inside 60 s, and p95 remains **>150 s** right-censored. That combined distribution still does not support raising the primary slice: covering the fresh p95 would require roughly 150 s, which would delay fallback for every slow primary and still would not cover the censored tail.

## Method

Prompt: the exact INF-019 probe A construction — a code-review task over a 400-function Python module (400 identical `def add` helpers), **35,214 chars**. The gateway estimator gives **13,543 tokens**; Gemini reported **13,519 prompt tokens** on every direct trial. The "~9k-token" label is the old `chars // 4` figure; by current counts this is a ~13.5k-token large-class prompt.

Model requested: `gemini-flash-latest`. Output settings: `max_tokens=200`, `temperature=0`.

Harness: M7's TASK-INF-058 harness reviewed in full before re-running (300 lines, sha256 `4e9b91edcf45544be3c0b5ea9765ccb347f83114f188516c3581cdb5f49b39bb`, unchanged on the server), copied to `/tmp/inf023_measure_harness.py` (sha256 `d490b1701a01b1bd3ac1fe638f8cc6a02bfc5cd25a3f267ea34ba4a6a489d4aa`) with only the task label and output path retargeted (`/tmp/inf023_measure.json`). First invocation failed on `ModuleNotFoundError: No module named 'app'` (the script lives in /tmp, so the cwd does not land on `sys.path`); re-run with `PYTHONPATH=/opt/friday_universe/Inference`, which is the only change to the invocation.

Legs run:

- **Direct Gemini adapter trials (n=5):** separate process on FRIDAY-Server in `/opt/friday_universe/Inference` with `/opt/friday_universe/venv312/bin/python`, adapter timeout 150 s, so the gateway primary slice could not cut the call off.
- **Live routing-path HTTP trials (n=2):** `POST http://127.0.0.1:8001/v1/providers/execute` on FRIDAY-Server with `provider="gemini"`, `model="gemini-flash-latest"`, `no_cache=true`, `fast_lane=false`, `speculative=false`: one default-budget call and one explicit `timeout=60.0` call. Routing receipts were read from the running service `/status` before/after each HTTP trial and matched by stage/provider/model/new-receipt diff.

Live settings read during the run: `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`, primary slice `min(60 × 0.6, 15) = 15.0 s`. Gemini key pool in the harness process: 15 total / 15 active / 0 quarantined before and after. Service `/health` returned HTTP 200 after the run; service receipt counts moved only by the two HTTP gateway trials (fallback_used 39 → 41, fallback_direct 1 → 2; total 100 → 100, success 99 → 99, error 1 → 1 — a rolling 100-receipt window).

Harness artefacts on FRIDAY-Server: `/tmp/inf023_measure_harness.py` (sha256 `d490b1701a01b1bd3ac1fe638f8cc6a02bfc5cd25a3f267ea34ba4a6a489d4aa`), `/tmp/inf023_measure.json` (sha256 `e7706426ad906d53c0d96551e1afbb9b524dd3cef89a270dc9247ba5466588da`), `/tmp/inf023_measure.log` (sha256 `c00a6ead19b7308962f1126396330ebbc49ea9436a4ebbfa1adc4c4ebcc31b1f`).

## Fresh direct Gemini results

| Trial | Elapsed | Upstream latency | Served model | Finish | Prompt tokens | Completion tokens | Outcome |
|---:|---:|---:|---|---:|---:|---:|---|
| 1 | 116.266 s | 116.265 s | gemini-flash-latest | MAX_TOKENS | 13,519 | 58 | served but truncated: 137 thought tokens vs 58 visible, thinking_overflow=true |
| 2 | 150.100 s | — | — | — | — | — | TimeoutError at the 150 s adapter timeout (right-censored) |
| 3 | 26.414 s | 2.129 s | gemini-3.6-flash | STOP | 13,519 | 51 | served via failover: gemini-flash-latest 503 high demand, fell over to gemini-3.6-flash |
| 4 | 100.451 s | 100.451 s | gemini-flash-latest | STOP | 13,519 | 88 | served |
| 5 | 150.098 s | — | — | — | — | — | TimeoutError at the 150 s adapter timeout (right-censored) |

Sorted elapsed: 26.414, 100.451, 116.266, >150, >150 s. Median **116.266 s**; p95 nearest-rank **>150 s**; inside 15 s: **0/5**; inside 60 s: **1/5**. Trial 3's elapsed time (26.414 s) is mostly the failed-primary wait before failover — its upstream latency was 2.129 s once gemini-3.6-flash served. Trial 1 completed but was truncated at `MAX_TOKENS`; its elapsed time is a real completion time, but the answer was incomplete.

## Live routing-path results

| Variant | HTTP | Elapsed | Served provider/model | Receipt latency | Receipt fallback | Outcome |
|---|---:|---:|---|---:|---|---|
| default budget | 200 | 2.939 s | openrouter / nvidia/nemotron-3.5-lightning:free | 2,929.9 ms | fallback_used=true, fallback_direct=true | success via large-prompt bypass; receipt prompt_tokens_est=13,561, deadline_class=large, timeout_budget_s=60.0 |
| explicit 60 s | 200 | 16.754 s | openrouter / nvidia/nemotron-3.5-lightning:free | 16,745.9 ms | fallback_used=true, fallback_direct=false | success via fallback after the primary slice; Gemini did NOT serve this run (contrast INF-058, where the explicit-60 s call served Gemini in 5.269 s) |

The default-budget receipt routing note was `large prompt: Gemini primary skipped (INF-LLM-003)`. The explicit-60 s call's 16.754 s elapsed is consistent with the 15 s primary slice expiring and the fallback ladder then serving in ~1.7 s. Both gateway trials succeeded from the caller's side; neither exercised Gemini as the serving provider this run.

## Deadline analysis

The fresh sample strengthens, not weakens, the INF-058 conclusion. A 15 s primary slice captured 0/5 fresh direct completions; the one fresh completion inside 60 s (26.414 s) was a failover serve, not a primary serve. The two fresh timeouts (150.098 s, 150.100 s) are not marginal overruns. Raising the slice to cover the fresh p95 would require roughly 150 s, which would delay fallback for every slow primary and still would not cover the censored tail — and the gateway evidence shows the fallback ladder is doing the work for this prompt class right now (2.939 s default-budget serve; 16.754 s explicit-60 s serve via fallback).

Combined direct evidence (fresh n=5 + INF-058 n=5 + INF-029 n=8): 3.009, 4.305, 5.42, 5.642, 6.38, 14.27, 26.414, 32.595, 42.00, 48.889, 67.32, 74.76, 99.32, 100.451, 116.266, >150, >150, >150 s. Median **45.44 s**; inside 15 s **6/18**; inside 60 s **10/18**; p95 **>150 s** right-censored. The deadline's job is to bound a slow primary and preserve fallback time; the measured distribution still argues for the existing cap.

Decision: **KEEP** `60.0 / 0.6 / 15.0`. No deadline constant is changed in this PR. The new observation for a future design decision: `gemini-flash-latest` returned 503 high demand and failed over to `gemini-3.6-flash` mid-run (trial 3) — if the coordinator wants Gemini itself, rather than the fallback ladder, to serve this prompt class reliably, that is a separate design decision for a dedicated long-budget reroute path, not a primary-slice increase.

## States

- **implemented:** YES — fresh measurement and deadline decision filed; no deadline constant changed.
- **tested:** YES — live direct measurement n=5 plus two live routing-path HTTP trials on FRIDAY-Server; PR CI verifies doc integrity after the update.
- **merged:** NO — work PR awaiting merge.
- **deployed:** NO — no behaviour change to deploy; no deploy performed.
- **production-verified:** YES — the measurement itself ran against live Gemini and the running Inference service routing path; the deadline decision is filed from those numbers.

— Muse 15
