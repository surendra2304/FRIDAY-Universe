# TASK-INF-004 — Inference Latency & Cost Profile

**Crew:** muse_ai (Inference performance crew, Wave 4) · **Date:** 2026-11-15
**Scope:** performance only — latency and cost. Routing *policy* is
TASK-REL-043 / TASK-REL-044 territory and is deliberately untouched.
**Method:** read-only. Code read at main `337a1e3f`; live probes executed
on Server 1 against `http://127.0.0.1:8001` (the production process,
started 2026-11-15 12:17:22 IST for the REL-043 deploy, 1 uvicorn worker,
~50MB RSS); journal of the current process mined server-side; 10
controlled API calls total (tiny prompts) for the serving map. No
production state was changed by the profiling.

**Honesty box.** Today is a crew-heavy day (~80 crews running; Server 1
load average hit 5.5 on a ~956MB VM). The traffic profiled is therefore
dominated by crew acceptance probes and Forge/FRIDAY delegations, not by
quiet-day organic traffic. Absolute numbers will differ on a quiet day;
the *structural* findings (what is serial, what is re-fetched, what is
deterministically doomed) are load-independent. Small-n probes are
labelled as such.

---

## 1. The headline distribution

From the production process's own `/metrics` (window: process start
12:17 IST → 13:07 IST, 2,963s uptime):

| Metric | Value |
|---|---|
| Requests recorded | 131 |
| Failed (5xx) | 0 |
| **p50 latency** | **0.402s** |
| **p95 latency** | **29.9s** |
| **p99 latency** | **48.4s** |

The median request is fast. The tail is not serving time — it is
*failure-cascade time*: a doomed or timed-out primary attempt, then a
serial fallback ladder, inside one 60s request budget. Everything below
is about that tail.

## 2. Route inventory — non-LLM routes (localhost, 5 reps each)

| Route | Status | Latency range | Note |
|---|---|---|---|
| `GET /health` | 200 | 4–82ms | bimodal (see §6) |
| `GET /ready` | 200 | 90ms–**5.59s** | first call in a burst paid 5.59s |
| `GET /health/detailed` | 200 | 12–101ms | |
| `GET /status` | 200 | 4–100ms | |
| `GET /v1/models` | 200 | 5–180ms | static catalogue |
| `GET /v1/capabilities` | 200 | 5–193ms | |
| `GET /v1/friday/status` | 200 | 16–205ms | |
| `GET /v1/friday/info` | 200 | 5–183ms | |
| `GET /v1/analytics/overview` | 200 | 101–505ms | slowest read route |
| `GET /v1/analytics/providers` | 200 | 9–194ms | |

## 3. Serving map — which pool/provider actually serves each route

Controlled probes (1–3 reps each, tiny prompts, 2026-11-15 ~13:20 IST):

| Call | Served by | Latency | Tokens (prompt/completion/total) |
|---|---|---|---|
| `POST /v1/chat/completions` `model=auto`, rep 1 | groq `openai/gpt-oss-20b` (fast lane) | 0.60s | 153 / 20 / 173 |
| same, reps 2–3 (identical) | **L1 cache** (unified manager) | 0.10s, 0.01s | 0 / 0 / 173 (stored total) |
| `model=openai/gpt-oss-120b`, rep 1 | groq `openai/gpt-oss-120b` | 0.50s | 153 / 21 / 174 |
| same, rep 2 | L1 cache | 0.19s | 0 / 0 / 174 |
| `model=gemini-3.8-flash` | gemini **`gemini-3.6-flash`** (intra-provider substitution, disclosed in provenance) | 4.71s | 75 / 0 / 120 |
| `POST /v1/friday/ask` fast-lane, rep 1 | groq `openai/gpt-oss-20b` | 0.59s | total 156 |
| same, rep 2 (identical) | **L1 cache** (friday route) | 0.01s | total 156 |
| `model=openai/gpt-oss-120b`, ~9.1k-token prompt | REL-043 selection rerouted up front → gemini `gemini-3.6-flash` (`selected_as: best_suitable_for_long_context`) | 8.49s | 9,077 / 30 / 9,107 |

Verified-live catalogue (`GET /v1/models`): `gemini-3.8-flash`,
`gemini-3.6-flash`, `openai/gpt-oss-120b`, `qwen/qwen3.8-27b`,
`meta-llama/llama-3.3-70b-instruct`, `nvidia/nemotron-3.5-lightning:free`,
`auto`. Key pools observed via `/health/providers`: gemini 15 keys,
groq 15, openrouter 15, nvidia 2, all active, none quarantined at probe
time. Provider outcomes recorded by this process at probe time: only
groq — 8 calls, 87.5% success, avg 3.04s.

Response caching already exists and works on the two hottest paths
(unified-manager L1 for chat/completions, friday-route L1 + L0 grounding
for friday/ask) — identical repeats return in ~0.01–0.19s. **Caching was
therefore NOT the missing optimisation**; §5 is.

## 4. Where the time goes — failure taxonomy of one production hour

Journal of the current process, 12:17–13:17 IST. **23 primary-provider
failures entered the fallback ladder** (groq 10, nvidia 8, gemini 5):

1. **Gemini primaries time out at exactly ~36s** (5 events: 35.9, 36.0,
   36.0, 36.8, 37.0s). 36s = `REQUEST_TIMEOUT` 60s ×
   `PRIMARY_ATTEMPT_FRACTION` 0.6 — the gateway cuts the primary slice
   and escalates. Root cause is free-tier Gemini latency; the fraction
   itself is a deliberate resilience trade-off (see §7, not changed).
2. **Groq primaries are deterministically rejected with HTTP 413**
   (≥6 events): prompts of **9,876–11,207 tokens** sent to
   `openai/gpt-oss-120b`, whose free-tier cap is **8,000 tokens/minute
   per organisation** — the single request exceeds the cap, so no key
   rotation can ever make it succeed. These arrive via unified-manager
   callers (agent-role routes such as code generation); the
   chat/completions path is already protected by REL-043's up-front
   long-context selection (§3, last row), the unified path is not.
3. **NVIDIA primaries are deterministically rejected with HTTP 404**
   (≥7 events): the configured function id is "Not found for account"
   on both NVIDIA accounts. Every nvidia-primary request pays a round
   trip plus the full ladder for a route that cannot succeed today.
4. **The ladder's first rung (OpenRouter) failed ≥5 times** in the same
   hour (`OpenRouter dynamic fallback failed (GatewayError|TimeoutError)`)
   — free-tier models are themselves unreliable today, and a failed rung
   consumes the remaining budget serially before the waterfall
   (Groq→Mistral→OpenAI→Gemini; mistral/openai have no credentials and
   are skipped) finally serves, usually from Gemini.
5. One groq primary timed out at **53.9s** — a caller with a ~90s budget
   (0.6 × 90 = 54s slice), consistent with the test-generation service's
   larger budget. Test generation additionally lost ≥3 attempt-1 calls
   to the same Gemini 36s timeouts before its own ladder moved on.

Net effect: a request that enters the ladder today typically pays
`primary (≤36s) + OpenRouter discovery (~1s) + OpenRouter attempt
(seconds, often failing) + waterfall Gemini (~4–8s)` — which is exactly
the observed p95 ≈ 30s / p99 ≈ 48s.

## 5. The shipped optimisation — OpenRouter discovery re-downloaded on every fallback

The ladder's OpenRouter rung calls `get_best_free_model()` →
`fetch_available_free_models()`, which downloads the OpenRouter model
catalogue: **850,791 bytes, measured 0.59s / 1.10s / 1.00s from
Server 1**. The code carries a designed 300s cache — on the provider
*instance*. But the gateway constructs a **fresh provider instance for
every attempt** (`get_provider(name, api_key=...)` is never memoised,
`app/providers/__init__.py`), so the cache can never survive to a second
fallback. Every one of the 23 ladder entries in the profiled hour paid
the full download again, on the critical path of the slowest requests:
≈ **14–25s of pure redundant latency and ~19MB of redundant transfer
per hour** at today's failure rate.

**Fix (this PR):** the discovery cache moves to module level in
`Inference/app/providers/openrouter.py`, keyed by `base_url`, same 300s
TTL, single-flight `asyncio.Lock` (concurrent fallbacks cannot stampede
the endpoint), and only successful non-empty fetches are cached —
failures keep the exact previous semantics (static `SUPPORTED_MODELS`,
retried next call). Model *selection* behaviour is byte-for-byte
unchanged; nothing about routing policy changes.

**Before/after, isolated harness** (`Inference/scripts/bench_openrouter_discovery.py`;
gateway's exact pattern — fresh instance per fallback, stub transport at
the production-measured 0.8s fetch latency, 10 simulated fallbacks):

| | Catalogue fetches | Discovery wall time | Per fallback |
|---|---|---|---|
| Before | 10 | 8.10s | 0.81s |
| After | **1** | **0.85s** | **0.08s** |

Same model selected before and after (`nvidia/nemotron-3.5-lightning:free`
from the stub catalogue). New tests
(`Inference/tests/test_openrouter_discovery_cache.py`, 8 tests) pin:
cross-instance sharing, TTL expiry, failure/non-200 never cached,
single-flight under 5 concurrent fallbacks, per-`base_url` keying,
keyless providers never fetch, selection unchanged. Regression subset
run with them: 30 passed, 0 failed (`test_gateway_fallback_key_rotation`,
`test_providers`, `test_universal_task_and_waterfall`).

## 6. Secondary observations (measured, not fixed here)

- **Bimodal trivial-route latency** (~5ms vs ~80–190ms on the same
  endpoint, back to back): consistent with event-loop/CPU contention on
  the loaded 956MB host (1 worker, load ~5.5), not with per-route code.
  Re-profile on a quiet box before attributing further.
- **`/ready` cold cost 5.59s** on the first call of a burst (90–190ms
  warm). Readiness does live dependency checks; orchestrators polling
  `/ready` after deploys should budget for it.
- **Adapter-level 2.0s cooldown** (`OpenAICompatibleProvider.generate`
  sleeps 2.0s on 429/503 *before* raising, on top of the gateway's own
  quarantine + ≤0.5s retry sleep — the code comment itself calls it a
  "second, redundant backoff"). It fired **0 times** in the profiled
  hour (no 429/503 transients recorded), so it is a latent, not
  measured, cost today. Left untouched: its stated purpose is politeness
  toward free tiers, and changing it is a behaviour decision.
- **Prompt sizes**: the fleet's real prompts are the cost driver —
  routine small calls run 120–175 total tokens, but the failing class
  runs ~9–11k prompt tokens per call. At free-tier caps, prompt size —
  not request count — is what breaks Groq (8k TPM) first.

## 7. Recommendations (for the coordinator; deliberately NOT in this PR)

1. **Gemini primary slice (36s) vs Gemini's real latency** — the single
   largest time bucket (5 × ~36s in one hour). Whether to raise
   `PRIMARY_ATTEMPT_FRACTION`, give Gemini-backed callers a larger
   `REQUEST_TIMEOUT`, or accept the ladder cost is a resilience
   trade-off = policy. Evidence is here; the decision is not this
   crew's.
2. **Oversized-prompt guard on the unified path** — requests whose
   estimated tokens exceed a provider's hard cap (Groq 8,000 TPM) should
   skip that provider *before* dispatch, the way REL-043's selection
   already protects chat/completions. Routing-adjacent; propose as a
   follow-up task rather than folding it into a performance PR.
3. **NVIDIA catalogue entry** — the 404ing function id makes every
   nvidia-primary request pure waste. Catalogue correctness sits with
   the REL-032/043 line of work; flagged here with journal evidence.
4. **OpenRouter rung reliability** — the ladder's first rung failed ≥5
   times in an hour on free-model errors/timeouts. With discovery now
   cached, the rung's remaining cost is its generate attempt; whether
   free-model OpenRouter should stay first in the ladder is again a
   routing-policy question for REL-043/044's owners.

## 8. Five-state status

- **Implemented:** yes — module-level discovery cache + tests + harness
  + this report, on branch `claude/task-inf-004-inference-latency-cost`.
- **Tested:** yes — 8/8 new tests, 30/30 in the regression subset,
  harness before/after reproduced locally.
- **Merged:** no — awaiting coordinator review/merge.
- **Deployed:** no — production deploy only via the coordinator's
  standard path after merge.
- **Production-verified:** no — post-deploy check for the coordinator:
  after the next natural fallback, the journal should show one
  `Discovered N active free models on OpenRouter` line per 5-minute
  window instead of one per fallback.
