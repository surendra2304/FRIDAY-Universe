# LiteLLM A/B evaluation — verdict: REJECT

**Task:** TASK-INF-040 (Inference: LiteLLM evaluation — local unified API layer A/B
against the current routing). **Measured:** 2026-11-25 on main `f6b912a6`, live on
Oracle Server 2 via the bridge (scratch clone + scratch venv; live checkout and
production venv untouched). **Worker:** Muse 13.

## Method

- Option A harness (no product-code change): `ModelGateway.execute("litellm", …)`
  vs the incumbent `ModelGateway.execute("groq", …)`, same prompt, same model,
  `temperature=0.0`, direct gateway calls (no UnifiedManager cache in play).
- Model: `openai/gpt-oss-20b` (alias `groq/openai/gpt-oss-20b`). `llama-3.1-8b-instant`
  is retired — Groq returns `model_not_found` for it on both legs; the key lists 11
  models and the live general chat models are `gpt-oss-20b`, `gpt-oss-120b`,
  `qwen/qwen3.8-27b`. (Repo `GroqProvider` already defaults to `gpt-oss-120b`.)
- Traffic: `Inference/benchmarks/testset.json` (15 items) + a failover probe with a
  nonexistent model. Fixed prompt set, not live fleet traffic — recorded as a
  limitation. Key sourced in-shell on the server from `CREDENTIALS.md`, never logged.

## Results (15 items per leg)

| | Incumbent (hand-rolled Groq) | LiteLLM (`litellm.acompletion`) |
|---|---|---|
| Success | 15/15 | 15/15 |
| Latency min / p50 / max (ms) | 161.4 / 535.6 / 2,608.6 | 387.5 / 545.4 / 15,404.3 |
| Total tokens | 3,910 | 3,910 |
| Fact checks (sum1–3) | 9/9 | **3/9** |
| First-call cold start | — | **~15–21 s per process** |

Repeat run on sum1 (×3 per leg): incumbent [1,463.9, 561.9, 648.1] ms;
litellm [20,913.9, 501.6, 544.9] ms — the litellm max in the table is the
first-call cold start; steady-state latency is a wash.

## Findings

1. **Latency: wash.** Steady-state p50 535.6 ms (incumbent) vs 545.4 ms (litellm).
   LiteLLM pays a 15–21 s cold start on its first call per process.
2. **Cost: identical.** 3,910 tokens on both legs — same Groq backend, free tier.
3. **Correctness: LiteLLM worse.** On sum2, sum3, rsn3 the litellm leg returned
   EMPTY content (0 words) with the same completion tokens as the incumbent.
   gpt-oss spends the token budget on reasoning; the incumbent
   (`OpenAICompatibleProvider.generate`) falls back to `reasoning` /
   `reasoning_content` when `content` is empty, while `LiteLLMProvider.generate`
   reads only `choice.message.content`. The model produced the answer; the
   adapter dropped it.
4. **Failover: LiteLLM worse.** Incumbent 404 → the gateway fallback ladder fires
   (openrouter rung attempted). LiteLLM failure (network 404 or local validation)
   → the error propagates immediately; the ladder never runs. Code:
   `gateway.py:663–689` raises directly, while every other primary-failure path
   in `_execute_inner` returns `await self._execute_dynamic_fallback(…)`.

## Verdict: REJECT

LiteLLM does not beat the incumbent on any measured axis, and is worse on
correctness and failover. Adopt only if it beats the incumbent — it does not.
No code or flag change follows: LiteLLM stays dark (flags default-off,
uninstallable from the deployed image, unreachable from live routes — see
legs (a)+(b) in the task evidence doc).

## Owed follow-ups (for whoever re-opens the LiteLLM question)

1. `LiteLLMProvider.generate` should fall back to `reasoning_content` /
   `reasoning` like `OpenAICompatibleProvider.generate`
   (`Inference/app/providers/openai_compatible.py:216`).
2. The litellm branch in `Inference/app/providers/gateway.py:663–689` should
   route transport failures through `_execute_dynamic_fallback` instead of
   raising outright.
3. `llama-3.1-8b-instant` references in board/docs text are stale; the live
   Groq set is gpt-oss/qwen.
