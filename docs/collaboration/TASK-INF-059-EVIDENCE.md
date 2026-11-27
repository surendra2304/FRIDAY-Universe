# TASK-INF-059 — Gemini ~9k-token completion timing run 2 and routing deadline re-verification

**Worker:** Muse TP14 · **Date:** 2026-11-27 · **Branch:** `musetp14/task-inf-059-gemini-9k-completion-time-run-2`
**Claim:** hub issue #1483 comment 7206053070.
**Board acceptance:** measure Gemini completion time on ~9k-token prompts (run 2) and re-verify the routing deadline set from run 1 evidence; file the numbers.
**Follow-up to:** TASK-INF-058 (run 1, Muse 7, PR #2037, evidence `TASK-INF-058-GEMINI-9K-DEADLINE.md`).

## Verdict

**Fresh live measurement: RUN. Deadline decision: KEEP `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`.**

Fresh direct Gemini sample (n=5): median **7.842 s**, p95 by nearest-rank **26.993 s**, max **26.993 s**, **4/5** inside the 15 s primary slice, **5/5** inside 60 s. All five finished `STOP` with complete visible answers (no thinking overflow; `thinking_budget` 0, 48–82 completion tokens). Combined with run 1 (fresh n=5 + filed n=8), the direct evidence is now n=18: median **13.90 s**, **10/18** inside 15 s, **14/18** inside 60 s, p95 still **>150 s** right-censored. The fresh sample is faster than run 1's, but trial 3 (26.993 s) still misses the slice by ~12 s and the combined tail is unchanged: raising the slice to cover the run-2 p95 would need ~27 s and still would not cover the combined tail.

## Method

Prompt: the exact INF-019 probe A construction — a code-review task over a 400-function Python module (400 identical `def add` helpers), **35,214 chars**. The gateway estimator gives **13,543 tokens**; Gemini reported **13,519 prompt tokens** on every direct trial. The "~9k-token" label is the old `chars // 4` figure; by current counts this is a ~13.5k-token large-class prompt.

Model requested: `gemini-flash-latest`. Output settings: `max_tokens=200`, `temperature=0`.

Legs run:

- **Direct Gemini adapter trials (n=5):** separate process on FRIDAY-Server in `/opt/friday_universe/Inference` with `/opt/friday_universe/venv312/bin/python`, adapter timeout 150 s, so the gateway primary slice could not cut the call off. `PYTHONPATH=/opt/friday_universe/Inference:/opt/friday_universe` as in the live service unit — the first launch without it failed at import (`ModuleNotFoundError: app`) and made no calls; the relaunch with the service's `PYTHONPATH` ran clean.
- **Live routing-path HTTP trials (n=2):** `POST http://127.0.0.1:8001/v1/providers/execute` on FRIDAY-Server with `provider="gemini"`, `model="gemini-flash-latest"`, `no_cache=true`, `fast_lane=false`, `speculative=false`: one default-budget call and one explicit `timeout=60.0` call. Routing receipts were read from the running service `/status` before/after each HTTP trial and matched by stage/provider/model/new-receipt diff.

The approved server-local route was used on FRIDAY-Server (`friday-server`, bridge server 3), the live Inference host: `Inference.service` active, MainPID 58827 before and after (no restart). The measurement ran 2026-11-27T01:00:33Z to 2026-11-27T01:01:39Z (06:30:33–06:31:39 IST). No server move, restart, env flip, deploy, or live-money action was performed. Credentials stayed server-side; no secret value was read into this record, printed, or stored.

Live settings read during the run: `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`, primary slice `min(60 × 0.6, 15) = 15.0 s`. Gemini key pool in the harness process: 15 total / 15 active / 0 quarantined before and after. Service receipt counts moved only by the two HTTP gateway trials (total 86 → 88, success 86 → 88, fallback_used 51 → 52, fallback_direct 2 → 3).

Harness artefacts on FRIDAY-Server: `/tmp/inf059_measure_harness.py` (sha256 `b3cd2dd38274c5c824564a230d7c74300bfca9763a69e678640f83de50760baa`), `/tmp/inf059_measure.json` (sha256 `7c3c29e7e9140ad93e3fa35850a9914ccd7f778d9e64aee3dc3d17b14c1871d0`), `/tmp/inf059_measure.log`. The run-2 harness is the run-1 harness (`/tmp/inf058_measure_harness.py`, sha256 `4e9b91ed…`) with only the output path and task label changed.

## Fresh direct Gemini results (run 2)

| Trial | Elapsed | Upstream latency | Served model | Finish | Prompt tokens | Completion tokens | Outcome |
|---:|---:|---:|---|---|---:|---:|---|
| 1 | 4.463 s | 4.463 s | gemini-flash-latest | STOP | 13,519 | 49 | served |
| 2 | 13.530 s | 13.530 s | gemini-flash-latest | STOP | 13,519 | 48 | served |
| 3 | 26.993 s | 26.992 s | gemini-flash-latest | STOP | 13,519 | 51 | served |
| 4 | 7.842 s | 7.842 s | gemini-flash-latest | STOP | 13,519 | 50 | served |
| 5 | 4.000 s | 4.000 s | gemini-flash-latest | STOP | 13,519 | 82 | served |

Sorted elapsed: 4.000, 4.463, 7.842, 13.530, 26.993 s. Median **7.842 s**; p95 nearest-rank **26.993 s**; inside 15 s: **4/5**; inside 60 s: **5/5**. All five answers were complete and on-topic (duplicate-`add` findings + PEP 8 notes); no trial was truncated.

## Live routing-path results (run 2)

| Variant | HTTP | Elapsed | Served provider/model | Receipt latency | Receipt fallback | Outcome |
|---|---:|---:|---|---:|---|---:|---|
| default budget | 200 | 3.370 s | openrouter / nvidia/nemotron-3.5-lightning:free | 3,363.9 ms | fallback_used=true, fallback_direct=true | success via large-prompt bypass; finish=length (200 completion tokens); receipt prompt_tokens_est=13,561, deadline_class=large, timeout_budget_s=60.0 |
| explicit 60 s | 200 | 5.972 s | gemini / gemini-flash-latest | 5,965.2 ms | fallback_used=false, fallback_direct=false | Gemini served inside the primary slice; finish_reason=MAX_TOKENS, token_usage prompt=12,728 completion=8 reasoning=188 |

The default-budget receipt routing note was `large prompt: Gemini primary skipped (INF-LLM-003)`; the served body adds that the Gemini primary misses the 15 s slice on this shape (INF-LLM-003 + TASK-INF-029: 4/4 gateway trials cut at the slice, 14.7–15.0 s), so routing went directly to the fallback ladder. The explicit-60 s receipt was `stage=unified_direct`, `provider_requested=gemini`, `model_requested=gemini-flash-latest`, `provider_served=gemini`, `model_served=gemini-flash-latest`, `outcome=success`. The explicit call therefore exercised the primary slice and Gemini answered in 5.965 s receipt latency this run, but the visible answer was truncated (`MAX_TOKENS`) because thought tokens (188) consumed most of the 200-token output budget — the same truncation pattern as run 1.

## Deadline analysis

The fresh sample is in the same band as run 1's (run-2 median 7.842 s vs run-1 fresh median 5.642 s), and the combined median improves to 13.90 s from 32.595 s because run 2 adds five mostly-fast values below the old middle — but the deadline conclusion does not change. A 15 s primary slice captured 4/5 fresh direct completions and the explicit gateway Gemini serve. The one fresh miss was 26.993 s — not a marginal overrun. Raising the slice to cover the run-2 p95 would require roughly 27 s, which would delay fallback for every slow primary and still would not cover the combined-sample tail (4/18 over 60 s, p95 >150 s right-censored).

Combined direct evidence (run-1 fresh n=5 + filed n=8 + run-2 fresh n=5 = n=18): 3.009, 4.000, 4.305, 4.463, 5.42, 5.642, 6.38, 7.842, 13.530, 14.27, 26.993, 32.595, 42.00, 48.889, 67.32, 74.76, 99.32, >150 s. Median **13.90 s**; inside 15 s **10/18**; inside 60 s **14/18**; p95 **>150 s** right-censored. The system-level routing evidence remains stronger than the Gemini-rung evidence: the default large-prompt path served via fallback in 3.370 s, and the explicit path served via Gemini in 5.972 s this run. The deadline's job is to bound a slow primary and preserve fallback time; the measured tail still argues for the existing cap.

Decision: **KEEP** `60.0 / 0.6 / 15.0`. No deadline constant is changed in this PR. If the coordinator wants Gemini itself, rather than the fallback ladder, to serve this prompt class reliably, that is a separate design decision for a dedicated long-budget reroute path, not a primary-slice increase.

## States

- **implemented:** YES — fresh measurement and deadline re-verification filed; no deadline constant changed.
- **tested:** YES — live direct measurement n=5 plus two live routing-path HTTP trials on FRIDAY-Server; PR CI verifies doc integrity after the update.
- **merged:** NO — work PR awaiting merge.
- **deployed:** NO — no behaviour change to deploy; no deploy performed.
- **production-verified:** YES — the measurement itself ran against live Gemini and the running Inference service routing path; the deadline decision is filed from those numbers.

— Muse TP14
