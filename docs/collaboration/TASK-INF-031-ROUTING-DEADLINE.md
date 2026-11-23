# TASK-INF-031: Inference — set the routing deadline from the INF-019 9k-token timing evidence

**Worker:** Muse 11 · **Date:** 2026-11-24 · **Branch:** `muse11/task-inf-031-routing-deadline`
**Board:** TASK-INF-031 (Inference: set the routing deadline from the INF-019 9k-token timing evidence)
**Assignment:** coordinator queue top-up, watch 7111833560 (~01:05 IST): queue pos 3 after MEM-017 (blocked) → MEM-024. Taken immediately on MEM-024 completing (work PR #1555 open, awaiting merge), per Muse's follow-up "when a task finishes, take the next immediately". **Claim:** issue #1483 comment 7113828676 (~02:29 IST).

> STATUS: CHECKPOINT 1 — claimed; INF-019 evidence read first-hand. Deadline implementation is the next work session.

## Acceptance (board)

The INF-019 evidence is read; a routing deadline is set in the router from the measured ~9k-token completion times; a probe proves slow completions route correctly and the deadline is filed with numbers.

## INF-019 evidence read first-hand

Source: `docs/verification/INF019_ROUTING_PROBES.md` (Muse 1, 2026-11-21 ~22:39–22:42 IST, live S1 Inference, `POST http://127.0.0.1:8001/v1/providers/execute`). Board record TASK-INF-019 (MERGED, PR #1241) corroborates.

- **Probe A — oversized, ~8.8k tokens** (code_generator, 35,214 chars, ~8,803 est tokens; journal ~8,880 incl. system instruction; over the 7,000-token guard). Ran twice:
  - A1 22:39:55 — HTTP 200, wall 53.3 s, gateway latency **29,802 ms**, `provider_used=openrouter`, `model_used=qwen/qwen-2.5-coder-32b-instruct`, fallback_reason "Request deadline exceeded for provider 'gemini' after **14.7s**".
  - A2 22:41:22 (repeat) — HTTP 200, wall 31.5 s, gateway latency **25,902 ms**, same provider/model/fallback.
  - Both: `status=success`, `degraded=false`, real answer served (~980 chars). Served by the openrouter fallback rung, not Gemini.
- **Probe B — under-limit control, ~43 tokens** (173 chars): HTTP 200, wall 4.63 s, latency **1,116 ms**, `provider_used=groq`, `model_used=openai/gpt-oss-120b`, `fallback_reason=null`, `degraded=false`. Real answer served.
- **Size-guard steering VERIFIED:** the oversized prompt never reached Groq — the unified path logged the TASK-INF-017 reroute warning (groq → gemini) before dispatch, both runs.
- **The intended gemini serve did NOT happen:** Gemini exceeded its 14.7 s provider deadline 2/2 on ~8.8k-token prompts.
- **Open question (INF-019, for Muse):** raise the Gemini provider deadline for the reroute path, pick a different reroute target, or accept the openrouter fallback as the working outcome for oversized prompts. No code changed in INF-019.

## Plan

1. Locate the routing deadline in the router code (`Inference/app/providers/gateway.py` — `GROQ_PROMPT_TOKEN_LIMIT = 7000`; `unified_manager.py` — reroute target `gemini/gemini-flash-latest`; find where the 14.7 s provider deadline is set and how it applies on the reroute path).
2. Set the deadline from the measured ~9k-token completion times (gateway latency 25.9–29.8 s; wall 31.5–53.3 s). The exact value is fixed in the work session from code + measurements, with the reasoning filed — a deadline that covers the measured slow path, not a guess.
3. Probe: rerun the INF-019 oversized probe (script `/tmp/inf019_probe.py` on Server 1) and prove slow completions route correctly; file the numbers.
4. No live trading, no paid services. Code change rides in the work PR; I do not merge my own PR.

## Preconditions

- Board record on main 855f2515 (board blob c217c91c): INF-031 AVAILABLE, owner muse_11, branch null, pr null. Queue: MEM-017 (blocked, 0/3) → MEM-024 (IN_REVIEW, PR #1555) → INF-031.
- MEM-024 COMPLETE this run (probe 02:21–02:22 IST, all legs green, PR #1555 head 040520d1, CI pending on the new head).

## Test data / live state

None yet — no probe calls have run in this task.

— Muse 11
