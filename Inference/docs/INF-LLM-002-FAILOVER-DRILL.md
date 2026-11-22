# TASK-INF-LLM-002 — Provider failover drill under simulated outage

- Task: TASK-INF-LLM-002 (P2, owner muse_2). MASTER_PLAN §6 standing backlog (pool 2, item 8).
- Drilled: Sun 2026-11-22 ~05:46–05:48 IST, live on Oracle Server 1.
- Claim: issue #35 comment 7070382647; claim PR #1269 merged 04:26 IST (merge e396c770).
- Verdict: **PASS — the primary (groq) going down (simulated) fails over to the next
  provider (openrouter) and serves a real answer in 4.7s total, with the escalation
  recorded in the failover log.** No real provider outage was caused, no key value was
  read, printed, logged, or stored anywhere in the drill.

## Method (secret-free by construction)

1. **Baseline (read-only, bridge run_shell -> Server 1):** `Inference.service` active,
   MainPID 1884786, venv312, started 04:27:43 IST; `/health` 200 healthy, 19 specialist
   agents, providers `[groq, cerebras, openrouter, gemini, nvidia]`. S1 checkout HEAD
   `485df534` — two merges behind main `ecea58ef`, both board-only (PR #1273, #1274),
   so the live Inference code is the main code for every drill file.
2. **Simulated outage in a separate harness process (not the running service):** a
   Python harness ran on S1 in the live Inference environment
   (`/opt/friday_universe/venv312/bin/python`, cwd `/opt/friday_universe/Inference`,
   the service's own `.env`, `PYTHONPATH=/opt/friday_universe/Inference`). It imported
   the real `ModelGateway` singleton and patched only `app.providers.get_provider` so
   that **groq alone** raises `ConnectionError("Connection refused by provider host
   (SIMULATED OUTAGE ...)")` while every other provider uses its **real adapter with
   the live environment's keys**. The running `Inference.service` was never touched,
   restarted, or reconfigured; the outage existed only inside the harness process.
3. **One request:** `gateway.execute("groq", ...)` with prompt
   `"Reply with exactly the single word DRILL and nothing else."`,
   model `openai/gpt-oss-120b`, `max_tokens=16`, request timeout 30.0s, capability
   `general`, stage `task-inf-llm-002-drill`. One tiny generation on the fallback
   provider; no other quota spent.
4. Key-pool counts were recorded before/after (counts only — the audit's method from
   TASK-INF-LLM-001). The harness prints a JSON summary only; no key value appears in
   any output, log, or file.

## Results — live, Server 1, 2026-11-22 ~05:47 IST

| Step | Observed |
|---|---|
| Primary groq (simulated down) | `ConnectionError` at once; gateway logged `GATEWAY: Primary provider 'groq' failed. Initiating capability fallback for 'general'.` 05:46:56 IST |
| Failover path taken | Rung 1 — OpenRouter dynamic rung (`gateway.py:936`): discovery found 14 active free models, selected `nvidia/nemotron-3.5-lightning:free` |
| Served by | `openrouter` / `nvidia/nemotron-3.5-lightning:free`, real answer, fallback latency 1.1s |
| Total drill time | 4.7s (30s request budget; primary slice barely used — the simulated failure is instant, so the ladder got the full reserved budget) |
| Fallback provenance | `requested_provider: groq` → `actual_provider: openrouter`, `actual_model: nvidia/nemotron-3.5-lightning:free`, `fallback_reason: Connection refused by provider host (SIMULATED OUTAGE - TASK-INF-LLM-002 drill; no real outage)` |
| Failover log | 0 events before → 1 event after (`from_provider: groq`, model `openai/gpt-oss-120b`, capability `general`, stage `task-inf-llm-002-drill`, reason as above, `at_utc: 2026-11-22T00:16:56Z`) |
| Errors | None. No exception escaped; no retry storm (the simulated `ConnectionError` normalizes to a non-retryable `GatewayError`, so the primary loop broke after one attempt instead of cycling keys) |
| Key pools (counts only) | Unchanged before → after: groq 15/15 active, 0 quarantined; gemini 15, openrouter 15, nvidia 2, all others 0 — reconciles exactly with the TASK-INF-LLM-001 audit (47 keys). The harness process's pools are its own; the live service's pools were never touched |
| Live service after the drill | Still healthy: `Inference.service` active, MainPID 1884786 unchanged, `/health` 200 healthy at 05:48 IST |

## Honesty bounds — what this drill did NOT prove

- **The waterfall rung (gemini) was not exercised live.** The OpenRouter rung serves
  first by design (`gateway.py:936`), so the waterfall (`gateway.py:1102`,
  Groq → Mistral → OpenAI → Gemini) never got its turn. The waterfall's behaviour
  under failure is covered only by the in-process INF-008 drill suite
  (`Inference/tests/test_inf008_failover_drill.py`, scripted fakes). See G2.
- **The live service's own HTTP path was not failed over.** There is no external
  trigger that makes the running service's primary fail — the only live-service
  failover triggers are the REL-047 routing guards (e.g. the groq size guard, which
  INF-019 already demonstrated live). See G1.
- **The served answer did not follow the one-word instruction.** The fallback model
  returned the start of a thinking trace (`"Here's a thinking process: 1. Analyze
  User Input: The"`, truncated at `max_tokens=16`) instead of the single word DRILL.
  That is the fallback model's behaviour, not a gateway failure — failover is proven
  by the provenance, not by the wording. See G3.

## Gaps filed (exact file/line + fix or follow-up)

- **G1 — No hook exists to simulate a provider outage against the running service.**
  `Inference/app/providers/gateway.py:430` (`ModelGateway.execute`) takes only a
  provider name and a request; there is no simulate/outage/test hook anywhere in the
  gateway, and no admin endpoint exposes one. The only live-service failover triggers
  are the REL-047 routing guards in `execute()` (`gateway.py:528-592`). **Follow-up
  for the coordinator:** decide whether a guarded (auth-gated, explicitly enabled)
  admin/test hook for provider-outage simulation is wanted for future live drills.
  Until then, live drills run in a separate harness process using this doc's method —
  which is what this drill did. (Not a defect in the failover path itself.)
- **G2 — Waterfall (gemini) rung not proven live by this drill.** `Inference/app/
  providers/gateway.py:936` (OpenRouter rung) runs before `gateway.py:1102`
  (waterfall), so a groq outage is always answered by OpenRouter while it is healthy.
  The gemini rung's live behaviour is still open — and INF-019 probe A already showed
  the reroute path missing gemini's deadline 2/2 (`Request deadline exceeded for
  provider gemini after 14.7s`), with openrouter serving instead. **Follow-up:** a
  drill that forces the OpenRouter rung to fail (or a direct waterfall probe) is
  needed to prove the gemini rung live; the INF-019 gemini-deadline question stands
  for Muse either way.
- **G3 — Observation, not a defect.** The fallback model answered with a thinking
  trace instead of the exact single word requested. Prompts that need exact short
  answers should not rely on the fallback model following format instructions. No
  code change; noted so a future drill does not mistake model wording for a
  failover failure.

## Baseline note

`Inference.service` restarted at 04:27:43 IST (MainPID 1884786) — observed in the
baseline probe, not caused by this drill (the drill ran 05:46–05:48 IST and never
restarted or reconfigured the service). The drill ran against the post-restart
process.

## Files changed by this task

- This report: `Inference/docs/INF-LLM-002-FAILOVER-DRILL.md` (added).
- `docs/collaboration/WORK_BOARD.yaml`: TASK-INF-LLM-002 record -> IN_REVIEW, pr set to this PR.

— Muse 2
