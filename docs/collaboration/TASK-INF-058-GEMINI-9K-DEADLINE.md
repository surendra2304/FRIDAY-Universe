# TASK-INF-058 — Gemini ~9k-token completion timing and routing deadline

**Worker:** Muse 7 · **Date:** 2026-11-27 · **Branch:** `muse7/task-inf-058-gemini-9k-deadline`  
**Claim:** hub issue #1483 comment 7204223797.  
**Board acceptance:** measure Gemini completion time on ~9k-token prompts and set the routing deadline from that evidence; file the numbers.

## Verdict

**Fresh live measurement: RUN. Deadline decision: KEEP `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`.**

The approved server-local route was used on FRIDAY-Server (`friday-server`, bridge server 3), the live Inference host: `Inference.service` active, MainPID 58827 before and after, listening on port 8001. The measurement ran 2026-11-27T00:08:09Z to 2026-11-27T00:09:51Z. No server move, restart, env flip, deploy, or live-money action was performed. Credentials stayed server-side; no secret value was read into this record, printed, or stored.

Fresh direct Gemini sample (n=5): median **5.642 s**, p95 by nearest-rank **48.889 s**, max **48.889 s**, **3/5** inside the 15 s primary slice, **5/5** inside 60 s. The fresh sample is faster than TASK-INF-029, but it does not erase the tail: 2/5 fresh direct calls still exceeded 15 s. Combined with the filed n=8 sample, n=13 median is **32.595 s**, **6/13** inside 15 s, **9/13** inside 60 s, and p95 remains **>150 s** right-censored. That combined distribution still does not support raising the primary slice.

## Method

Prompt: the exact INF-019 probe A construction — a code-review task over a 400-function Python module (400 identical `def add` helpers), **35,214 chars**. The gateway estimator gives **13,543 tokens**; Gemini reported **13,519 prompt tokens** on every direct trial. The “~9k-token” label is the old `chars // 4` figure; by current counts this is a ~13.5k-token large-class prompt.

Model requested: `gemini-flash-latest`. Output settings: `max_tokens=200`, `temperature=0`.

Legs run:

- **Direct Gemini adapter trials (n=5):** separate process on FRIDAY-Server in `/opt/friday_universe/Inference` with `/opt/friday_universe/venv312/bin/python`, adapter timeout 150 s, so the gateway primary slice could not cut the call off.
- **Live routing-path HTTP trials (n=2):** `POST http://127.0.0.1:8001/v1/providers/execute` on FRIDAY-Server with `provider="gemini"`, `model="gemini-flash-latest"`, `no_cache=true`, `fast_lane=false`, `speculative=false`: one default-budget call and one explicit `timeout=60.0` call. Routing receipts were read from the running service `/status` before/after each HTTP trial and matched by stage/provider/model/new-receipt diff.

Live settings read during the run: `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`, primary slice `min(60 × 0.6, 15) = 15.0 s`. Gemini key pool in the harness process: 15 total / 15 active / 0 quarantined before and after. Service `/health` returned HTTP 200 after the run; service receipt counts moved only by the two HTTP gateway trials (total 61 → 63, success 61 → 63, fallback_used 39 → 40, fallback_direct 1 → 2).

Harness artefacts on FRIDAY-Server: `/tmp/inf058_measure_harness.py` (sha256 `4e9b91edcf45544be3c0b5ea9765ccb347f83114f188516c3581cdb5f49b39bb`), `/tmp/inf058_measure.json` (sha256 `b273bd3c78758d5c31ed1734d9f40e542f8bd2a553df98cef5a9f278de835262`), `/tmp/inf058_measure.log`.

## Fresh direct Gemini results

| Trial | Elapsed | Upstream latency | Served model | Finish | Prompt tokens | Completion tokens | Outcome |
|---:|---:|---:|---|---|---:|---:|---|
| 1 | 48.889 s | 48.888 s | gemini-flash-latest | STOP | 13,519 | 85 | served |
| 2 | 32.595 s | 32.595 s | gemini-flash-latest | STOP | 13,519 | 42 | served |
| 3 | 5.642 s | 5.642 s | gemini-flash-latest | STOP | 13,519 | 95 | served |
| 4 | 3.009 s | 3.008 s | gemini-flash-latest | STOP | 13,519 | 54 | served |
| 5 | 4.305 s | 4.305 s | gemini-flash-latest | MAX_TOKENS | 13,519 | 23 | served but truncated: 172 thought tokens vs 23 visible, thinking_overflow=true |

Sorted elapsed: 3.009, 4.305, 5.642, 32.595, 48.889 s. Median **5.642 s**; p95 nearest-rank **48.889 s**; inside 15 s: **3/5**; inside 60 s: **5/5**. Trial 5 completed quickly but was truncated at `MAX_TOKENS`; its elapsed time is a real completion time, but the answer was incomplete.

## Live routing-path results

| Variant | HTTP | Elapsed | Served provider/model | Receipt latency | Receipt fallback | Outcome |
|---|---:|---:|---|---:|---|---|
| default budget | 200 | 2.279 s | openrouter / nvidia/nemotron-3.5-lightning:free | 2,273 ms | fallback_used=true, fallback_direct=true | success via large-prompt bypass; receipt prompt_tokens_est=13,561, deadline_class=large, timeout_budget_s=60.0 |
| explicit 60 s | 200 | 5.276 s | gemini / gemini-flash-latest | 5,269 ms | fallback_used=false, fallback_direct=false | Gemini served inside the primary slice; finish_reason=MAX_TOKENS, token_usage prompt=12,728 completion=36 reasoning=160 |

The default-budget receipt routing note was `large prompt: Gemini primary skipped (INF-LLM-003)`. The explicit-60 s receipt was `stage=unified_direct`, `provider_requested=gemini`, `model_requested=gemini-flash-latest`, `provider_served=gemini`, `model_served=gemini-flash-latest`, `outcome=success`. The explicit call therefore exercised the primary slice and Gemini answered in 5.269 s receipt latency this run, but the visible answer was truncated (`MAX_TOKENS`) because thought tokens consumed most of the 200-token output budget.

## Deadline analysis

The fresh sample improves the central tendency but not the deadline conclusion. A 15 s primary slice captured 3/5 fresh direct completions and the explicit gateway Gemini serve. The two fresh misses were 32.595 s and 48.889 s — not marginal overruns. Raising the slice to cover the fresh p95 would require roughly 49 s, which would delay fallback for every slow primary and still would not cover the combined-sample tail.

Combined direct evidence (fresh n=5 + filed n=8): 3.009, 4.305, 5.42, 5.642, 6.38, 14.27, 32.595, 42.00, 48.889, 67.32, 74.76, 99.32, >150 s. Median **32.595 s**; inside 15 s **6/13**; inside 60 s **9/13**; p95 **>150 s** right-censored. The system-level routing evidence remains stronger than the Gemini-rung evidence: the default large-prompt path served via fallback in 2.279 s, and the explicit path served via Gemini in 5.276 s this run. The deadline’s job is to bound a slow primary and preserve fallback time; the measured tail still argues for the existing cap.

Decision: **KEEP** `60.0 / 0.6 / 15.0`. No deadline constant is changed in this PR. If the coordinator wants Gemini itself, rather than the fallback ladder, to serve this prompt class reliably, that is a separate design decision for a dedicated long-budget reroute path, not a primary-slice increase.

## States

- **implemented:** YES — fresh measurement and deadline decision filed; no deadline constant changed.
- **tested:** YES — live direct measurement n=5 plus two live routing-path HTTP trials on FRIDAY-Server; PR CI verifies doc integrity after the update.
- **merged:** NO — work PR awaiting merge.
- **deployed:** NO — no behaviour change to deploy; no deploy performed.
- **production-verified:** YES — the measurement itself ran against live Gemini and the running Inference service routing path; the deadline decision is filed from those numbers.

— Muse 7
