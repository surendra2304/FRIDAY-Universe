# TASK-INF-033 — Inference routing-deadline live proof

**Task:** Prove the INF-031 deadline is enforced in the live routing path.
**Owner:** Muse 1. **Branch:** `muse1/task-inf-033-routing-deadline-live-proof`.
**Probed:** 2026-11-25 ~02:05–02:17 IST (2026-11-24 20:35–20:47 UTC).
**Status:** implemented, tested (live probes below). Not merged, not deployed,
not production-verified (no live code changed; this is evidence only).

## Verdict

**The INF-031 deadline is enforced on real prompts, with timing numbers.**
Every live request below returned inside the 60 s budget, the 15.0 s primary
slice fired on the record (gateway journal), and the 150 s live client timeout
never became the binding constraint. The oversized (>7000-token) class serves
again through the live routing path — 1 of 2 client-path attempts returned a
real answer in 40.39 s; the other failed typed (HTTP 503 `provider_degraded`)
in 51.96 s, inside the budget. The failure is model availability, not the
deadline.

## The deadline, traced first-hand (main `e5a6876f` = live checkout)

| Piece | Value | Source |
|---|---|---|
| `REQUEST_TIMEOUT` (whole-request budget) | 60.0 s | `Inference/app/core/config.py:283` |
| `PRIMARY_ATTEMPT_FRACTION` | 0.6 | `Inference/app/core/config.py:450` |
| `PRIMARY_ATTEMPT_MAX_SECONDS` | 15.0 s | `Inference/app/core/config.py:462` |
| Primary slice | `min(60 x 0.6, 15)` = **15.0 s** | computed |
| Large-prompt bypass threshold | 7000 tokens (`GROQ_PROMPT_TOKEN_LIMIT`) | `Inference/app/providers/gateway.py:86`, `:145` |
| Timeout budget + `wait_for` | `_request_timeout_budget` (`:281`), budget applied `:621`, primary `wait_for` `:672`, fallback rungs `:927`, `:1089`, `:1275`, `:1392` | `Inference/app/providers/gateway.py` |
| Route deadline | `route_deadline = time.monotonic() + float(settings.REQUEST_TIMEOUT or 60.0)` | `Inference/app/api/v1_core_routes.py:1745` |
| Client timeout (main, INF-032) | 70.0 s (`INFERENCE_ROUTING_DEADLINE_S` 60.0 + 10.0 margin) | `FRIDAY/src/friday/llm/escalation.py:329-334` |
| Client timeout (LIVE) | **150.0 s** — live checkout `5b245ffd` predates INF-032; INF-032 merged (PR #1634) but **not deployed** to live FRIDAY | verified on friday-server: `_inference_timeout_s()` returns 150.0 |

Live legs verified before probing: friday-server `15.134.130.145`,
Inference.service active (MainPID 13947), FRIDAY.service active (MainPID
19731, started 2026-11-24 14:48:02 UTC); ports 8001/10000 listening.
S1:8001 is an SSH local forward to friday-server:8001. No restart, no deploy,
no live write at any point in this run — probes are read-only HTTP calls.

## Live probe results

Prompts: oversized = the 400-function module from INF-019/INF-031
(35,214 chars, ~8,803 est. tokens); mid = 175 repetitions (15,414 chars,
~3,853 tokens); control = one `add` function (173 chars, 43 tokens).
All prompts ask for a bug/style review of the same module shape.

### 1. Direct endpoint — `POST /v1/providers/execute` (S1, `no_cache=true`)

| Probe | Prompt | Result | Wall | Gateway latency | Served by | Notes |
|---|---|---|---|---|---|---|
| A oversized | 35,214 chars | HTTP 200 | **10.52 s** | 9,623.87 ms | openrouter/qwen-2.5-coder-32b-instruct | `fallback_reason`: large deadline class bypass — Gemini primary skipped, direct to fallback ladder. Real answer, 960 chars (correctly identifies the 400 identical `add` functions). |
| B control | 173 chars | HTTP 200 | **1.27 s** | 770.31 ms | groq/openai/gpt-oss-120b | `fallback_reason` null. Real answer, 652 chars. |

**Ladder recovery (the INF-032 blocker): RECOVERED on this endpoint.**
INF-032 recorded 0/6 provider-path attempts at the 9k size completing
(all HTTP 503 `provider_degraded`, ~15 h earlier). This run: 1/1 served.

### 2. Live client path — `InferenceChatProvider.generate()` → `POST /v1/chat/completions`

The live FRIDAY escalation provider, loaded from the live checkout with the
FRIDAY venv on friday-server (client timeout 150.0 s, verified in-process).
Model requested by task kind: `openai/gpt-oss-120b` for code.

| Probe | Prompt | Result | Wall | Escalation latency | Served by | Notes |
|---|---|---|---|---|---|---|
| A oversized | 35,214 chars | HTTP 503 `provider_degraded` | **51.96 s** | — (raised) | — | `LLMProviderError: INFERENCE_UNAVAILABLE: HTTP 503`. Client timeout (150 s) never fired. See journal below. |
| C mid | 15,414 chars | HTTP 200 | **1.57 s** | 1.55 s | openai/gpt-oss-120b (as requested) | Routing `complex/long_input`. Real answer, 1,974 chars (correctly flags 175 duplicate `add` defs). |
| B control | 173 chars | HTTP 200 | **0.21 s** | 0.21 s | openai/gpt-oss-120b (as requested) | Routing `complex/default_quality`. Answer `NO FINDINGS`, 11 chars. |
| Retry A oversized | 35,214 chars | HTTP 200 | **40.39 s** | 40.33 s | **gemini-3.6-flash** (requested gpt-oss-120b; REL-043 substitution) | Real answer, 358 chars (correctly flags the 400 redefinitions). The oversized class serves through the live routing path. |
| Retry direct POST | 35,214 chars | HTTP 200 | 0.01 s | — | gemini-3.6-flash | **Cache hit, not independent evidence:** identical content to Retry A, returned in 0.01 s. Recorded for honesty; the routing proof is Retry A, not this leg. |

### 3. Gateway journal — the 15.0 s primary slice, on the record

Inference.service journal, 2026-11-24 20:40–20:41 UTC (client-path probe A):

- `20:40:21` — `GATEWAY: Prompt over the Groq size guard (~12765 tokens > 7000); skipping the Groq primary and routing to the fallback ladder.`
- `20:40:36` — `Gemini model gemini-3.8-flash experienced 503 high demand; failing over to gemini-3.6-flash`
- `20:40:47` — `GATEWAY: Provider 'gemini' timed out after 15.0s (TimeoutError, model=gemini-3.8-flash). Escalating to the fallback ladder instead of failing the request.`
- `20:40:47` — `GATEWAY: Primary provider 'gemini' failed. Initiating capability fallback for 'reasoning'.`
- `20:41:13` — `POST /v1/chat/completions 503 Service Unavailable`

Reading: on the chat-completions path the bypass skips the Groq primary but
still tries a Gemini primary; that attempt is cut at exactly the 15.0 s
primary slice, then the ladder runs. The whole request returned at 51.96 s —
inside the 60 s budget. The 503 is the ladder finding no servable catalogue
model at that moment (Gemini 3.8 at 503 high demand), not a deadline breach.

## What this proves, and what it does not

Proven:

- The 60 s whole-request budget bounds real prompts on both the execute
  endpoint and the live escalation path (worst observed wall 51.96 s).
- The 15.0 s primary slice is enforced live (journal line, exact value).
- The >7000-token bypass fires live on both paths (gateway latency receipt
  on the execute endpoint; size-guard journal line on the chat path).
- Under-7000-token prompts serve fast through the live client path
  (1.57 s / 0.21 s, model as requested, real answers).
- The oversized class serves through the live routing path (Retry A,
  40.39 s, real answer) — the INF-032 outage is no longer a hard block.

Not proven / honest caveats:

- **The chat-completions ladder is flaky for the >7000 class: 1 of 2
  attempts 503'd.** It depends on Gemini availability at the moment of the
  call. The execute endpoint served 1/1. Do not read this as "the ladder is
  fixed"; read it as "recovered, still fragile on the escalation path".
- **The live client timeout is still 150 s, not 70 s.** INF-032's wiring
  (60 s deadline + 10 s margin) is merged on main but not deployed to the
  live FRIDAY. A deploy is owed; it needs Muse's hub clearance (not
  attempted here).
- No prompt was run to the 60 s budget edge, so the exact behaviour at the
  boundary (clean typed error vs. hang) is not directly observed; the
  closest data point is the 51.96 s typed 503.
- Probe scripts and raw summaries live on S1 / friday-server `/tmp`
  (`inf033_probe.py`, `inf033_probeA_oversized.json`,
  `inf033_probeB_control.json`, `inf033_client_probe.py`,
  `inf033_client_A_oversized.json`, `inf033_client_B_control.json`,
  `inf033_client_C_mid.json`, `inf033_client_retry.py`,
  `inf033_retryA.json`, `inf033_retryDirect.json`, `inf033_client_probe.log`,
  `inf033_client_retry.log`); work notes in `~/workspace/inf-033/`.

## Follow-ups (filed, not fixed here)

- **INF-032 deploy owed:** live FRIDAY still runs pre-INF-032 escalation
  code (150 s client timeout). Deploy needs Muse's hub clearance.
- **INF-032 G2 (known):** `AIUniverseClient` 45 s hard-code
  (`FRIDAY/src/friday/tools/ai_universe_client.py`, `timeout: float = 45.0`)
  — same hole class on the `/v1/friday/ask` path, opposite direction.
- **Chat-path ladder fragility:** the >7000 class on `/v1/chat/completions`
  still 503s when Gemini is at high demand; worth a gateway-side look at
  why the execute endpoint's direct-to-ladder bypass serves while the chat
  path's Gemini-primary-first route can still fail.

## Files

- `docs/collaboration/TASK-INF-033-ROUTING-DEADLINE-LIVE-PROOF.md` (this file)
- `docs/collaboration/WORK_BOARD.yaml` (INF-033 → IN_REVIEW / muse_1 / this PR)

— Muse 1
