# TASK-INF-019 — Post-#1066 routing probes (live, S1 Inference)

Date: 2026-11-21 ~22:39–22:42 IST. Prober: Muse 1. Task: rerun the post-#1066
routing probes owed by the TASK-INF-018 (PR #1066) disclosure and file the
results: one oversized agent-role unified call plus one under-limit control.

## What was probed

Endpoint: `POST http://127.0.0.1:8001/v1/providers/execute` on Server 1
(`Inference.service`, active since 21:44:31 IST, Main PID 1693433,
checkout main b4837aac, which contains the PR #1066 fix — merged
2026-11-19; `GROQ_PROMPT_TOKEN_LIMIT = 7000` in
`Inference/app/providers/gateway.py`, reroute target
`gemini/gemini-flash-latest` in `unified_manager.py`).

Both calls: `provider="auto"`, `agent_role="code_generator"`
(role mapping: groq/openai/gpt-oss-120b), `no_cache=true`,
`fast_lane=false`, `speculative=false`, `max_tokens=200`,
`temperature=0`, authenticated with the S1 `INFERENCE_API_KEY`
(read from the service `.env` on the host; never copied off it).

## Probe A — oversized (ran twice: 22:39:55 and 22:41:22 IST)

Prompt: code-review task over a 400-function Python module,
35,214 chars, ~8,803 tokens by the gateway's own estimator
(chars // 4); the service journal records ~8,880 tokens including
the system instruction — over the 7,000-token guard either way.

| Run | HTTP | Wall | Latency | provider_used | model_used | fallback_reason |
|-----|------|------|---------|---------------|------------|-----------------|
| A1 22:39:55 | 200 | 53.3 s | 29,802 ms | openrouter | qwen/qwen-2.5-coder-32b-instruct | "Request deadline exceeded for provider 'gemini' after 14.7s" |
| A2 22:41:22 (repeat) | 200 | 31.5 s | 25,902 ms | openrouter | qwen/qwen-2.5-coder-32b-instruct | "Request deadline exceeded for provider 'gemini' after 14.7s" |

Both runs: `status=success`, `degraded=false`, real answer served
(~980 chars, correctly identifies the 400 duplicated `add` functions).
`served_by_provider=openrouter` on both.

Journal (S1 `Inference.service`, both runs):
`[WARNING] Unified Groq size guard: prompt ~8880 tokens > 7000 guard;
rerouting role 'code_generator' from groq/openai/gpt-oss-120b to
gemini/gemini-flash-latest before dispatch (TASK-INF-017).`

## Probe B — under-limit control (22:40 IST)

Prompt: same review task over one function, 173 chars, ~43 tokens.

HTTP 200, wall 4.63 s, latency 1,116 ms, `provider_used=groq`,
`model_used=openai/gpt-oss-120b`, `fallback_reason=null`,
`served_by_provider=null`, `degraded=false`, `finish_reason=length`
(the 200-token output cap, not a failure). Real answer served
(652 chars).

## Verdict (honest, split)

1. **Size-guard steering VERIFIED.** The oversized prompt never reached
   Groq: the unified path logged the TASK-INF-017 reroute warning and
   steered groq → gemini before dispatch, on both runs. The PR #1066
   fix does what it claims on live S1.
2. **The disclosed "gemini serve" did NOT happen.** Gemini never
   answered either oversized call: it exceeded its 14.7 s provider
   deadline 2/2, and the gateway fell back to the openrouter rung
   (qwen-2.5-coder-32b-instruct), which served a real answer. The
   end-to-end result is a success via a deliberate fallback rung —
   not the catalogue-blind ladder the guard was built to avoid — but
   it is not the intended gemini serve.
3. **Control PASSED.** The under-limit call served from Groq
   (gpt-oss-120b) with no fallback, exactly as designed.

## Open question for Muse (not a blocker for this record)

The reroute target cannot serve an ~8.8k-token prompt inside its
14.7 s deadline (2/2 failures, identical). Options: raise the Gemini
provider deadline for the reroute path, pick a different reroute
target, or accept the openrouter fallback as the working outcome for
oversized prompts. Needs a coordinator decision; no code changed
in this task.

## Reproduction

Probe script (kept on S1 as `/tmp/inf019_probe.py`, summary JSONs
`/tmp/inf019_probeA_oversized.json`, `/tmp/inf019_probeB_control.json`,
`/tmp/inf019_probeA_repeat.json`): builds the prompts, POSTs to the
unified endpoint with the host `.env` key, prints a redacted summary.
Rerun: `python3 /tmp/inf019_probe.py` on Server 1.
