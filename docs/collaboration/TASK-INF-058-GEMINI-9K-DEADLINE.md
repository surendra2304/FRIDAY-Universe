# TASK-INF-058 — Gemini ~9k-token completion timing and routing deadline

**Worker:** Muse 7 · **Date:** 2026-11-27 · **Branch:** `muse7/task-inf-058-gemini-9k-deadline`  
**Claim:** hub issue #1483 comment 7204223797.  
**Board acceptance:** measure Gemini completion time on ~9k-token prompts and set the routing deadline from that evidence; file the numbers.

## Verdict

**Fresh live measurement: BLOCKED-WITH-REASON. Deadline recommendation: PROVISIONAL KEEP.**

No new Gemini timing was run in this leg. The public Inference route is reachable from this VM for unauthenticated health/status reads, but the measurement endpoints require authentication, and this task did not authorize retrieving or using the Inference credential. The direct Gemini adapter measurement also needs a server-local harness; the board names live Inference on FRIDAY-Server, while the bridge tool schema available to this worker describes `run_shell` for Oracle Server 1 or 2, so a FRIDAY-Server harness route is not verified from this VM.

On the filed evidence already in the repo, the routing deadline should stay at `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0` (primary slice `min(60 × 0.6, 15) = 15.0 s`). This is a provisional KEEP, not a fresh measurement result. No deadline constant is changed in this PR.

## Route check performed in this leg

Read-only checks only; no server move, restart, config change, credential use, or live-money action:

- `GET https://friday-universe.duckdns.org/inference/health` returned HTTP 200. The body reported `status: healthy`, service `inference`, providers including `gemini`, and `observed_at` `2026-11-26T23:01:26.275692+00:00`.
- `GET https://friday-universe.duckdns.org/inference/status` returned HTTP 200 and reported the Inference service operational.
- The measurement routes are authenticated in code: `Inference/app/main.py` mounts the v1 and providers routers with `Depends(require_inference_api_key)`, and `Inference/app/core/security.py` requires `X-INFERENCE-API-KEY`, `X-API-Key`, `X-FRIDAY-API-Key`, or `Authorization: Bearer <key>`.
- No authenticated `POST /v1/providers/execute`, `POST /v1/chat/completions`, or direct Gemini adapter call was attempted.

Exact route needed to unblock the fresh measurement: a coordinator-approved server-local harness on the live Inference host (FRIDAY-Server per the board record) with the Inference/Gemini credentials kept server-side, or explicit authorization to use the Inference credential for the public gateway-path leg plus a server-local harness for the direct Gemini adapter leg. The harness should reuse the INF-019 prompt shape: 35,214 chars, `max_tokens=200`, `temperature=0`, direct Gemini adapter trials with a 150 s cap, then gateway default-path and explicit-60 s trials with `no_cache=true`, recording elapsed time, upstream latency, served model, prompt tokens, completion tokens, finish reason, HTTP status, and fallback receipt fields.

## Filed evidence used for the provisional deadline

The prompt label "~9k-token" is the old `chars // 4` figure. For the INF-019 probe prompt (35,214 chars), Gemini's own count is 13,519 prompt tokens; after TASK-INF-021 calibration the gateway estimate is 13,543 tokens. The prompt is therefore in the large class (`> 7000` tokens) either way.

### Direct Gemini completion times already filed

TASK-INF-LLM-003 direct trials, full prompt:

| Trial | Elapsed | Served model | Outcome |
|---:|---:|---|---|
| 1 | 6.38 s | gemini-3.6-flash | served |
| 2 | 99.32 s | gemini-flash-latest | served |
| 3 | 67.32 s | gemini-flash-latest | served |

The compressed-prompt direct attempt in TASK-INF-LLM-003 did not complete within the 150 s cap (153.29 s elapsed, `TimeoutError`).

TASK-INF-029 direct trials, full prompt, n=5 fresh:

| Trial | Elapsed | Served model | Outcome |
|---:|---:|---|---|
| 1 | 5.42 s | gemini-3.6-flash | served |
| 2 | 150.13 s | — | timeout, right-censored |
| 3 | 42.00 s | gemini-3.6-flash | served |
| 4 | 14.27 s | gemini-3.6-flash | served |
| 5 | 74.76 s | gemini-3.6-flash | served |

Combined direct full-prompt sample (TASK-INF-029 + TASK-INF-LLM-003, n=8): 5.42, 6.38, 14.27, 42.00, 67.32, 74.76, 99.32, >150 s. Median 54.66 s; 3/8 inside the 15 s primary slice; 4/8 inside 60 s; p95 is at least 150 s because the tail is right-censored.

### Gateway/routing outcomes already filed

- INF-019 probe A: oversized prompt served by fallback in 53.3 s and 31.5 s wall time after Gemini exceeded the 14.7 s provider deadline 2/2.
- TASK-INF-LLM-003 gateway path: 21.39 s elapsed; Gemini primary cut at 14.7 s; fallback served.
- TASK-INF-029 gateway explicit-60 s path: 18.34 s elapsed; Gemini primary cut at 15.0 s; fallback served.
- TASK-INF-031 default path: 20.12 s wall, 14,412.84 ms gateway latency; large-class bypass skipped Gemini and fallback served.
- TASK-INF-032: deadline proven live in routing, but 0/6 provider-path attempts at the 9k size completed during a fallback-ladder/provider availability outage; failures were typed 503s inside the 60 s budget.
- TASK-INF-033: execute endpoint oversized probe served in 10.52 s via bypass/fallback; live client path retry served in 40.39 s; one client-path attempt returned typed 503 at 51.96 s after the journal recorded the exact 15.0 s Gemini primary timeout.

## Deadline analysis

Current code on main keeps the INF-029 decision: `Inference/app/core/config.py` sets `REQUEST_TIMEOUT` default 60.0 and `PRIMARY_ATTEMPT_MAX_SECONDS` default 15.0, with the field description citing the INF-029 measurement. `Inference/app/providers/gateway.py` sets `GROQ_PROMPT_TOKEN_LIMIT = 7000`, `LARGE_PROMPT_TOKEN_THRESHOLD = GROQ_PROMPT_TOKEN_LIMIT`, computes the primary slice as `min(budget × fraction, PRIMARY_ATTEMPT_MAX_SECONDS)`, and annotates the large-prompt bypass with `large_prompt_primary_skipped`.

The filed direct-Gemini distribution does not support raising the primary slice to cover Gemini's tail. A slice large enough to cover the observed p95 would need to be at least 150 s, which would hold timed-out primaries for about 2.5 minutes before fallback and defeat the purpose of the primary cap. The system-level evidence points the other way: the large-prompt bypass and fallback ladder have served the same prompt shape inside the 60 s request budget in multiple filed runs (10.52 s, 18.34 s, 20.12 s, 21.39 s, 31.5 s, 40.39 s, 53.3 s), while the observed failures were typed provider-availability 503s inside the budget rather than deadline overruns.

Provisional recommendation: **KEEP** `60.0 / 0.6 / 15.0`. Do not change constants until a fresh server-local measurement is run, because model alias resolution and provider availability have changed across the filed runs (for example `gemini-flash-latest` resolving to `gemini-3.6-flash`, and TASK-INF-033 recording `gemini-3.8-flash` 503 high demand before failover). If the coordinator wants Gemini itself, rather than the fallback ladder, to serve this prompt class, that is a separate design decision for a dedicated long-budget reroute path, not a primary-slice tweak.

## States

- **implemented:** YES — repo-side evidence and provisional deadline recommendation filed; no deadline constant changed.
- **tested:** NO — fresh live measurement not run; PR CI can verify only doc/board integrity for this leg.
- **merged:** NO — work PR opened this run, awaiting merge.
- **deployed:** NO — no deploy performed or requested.
- **production-verified:** NO — fresh Gemini timing remains blocked on the authenticated/server-local route above.

— Muse 7
