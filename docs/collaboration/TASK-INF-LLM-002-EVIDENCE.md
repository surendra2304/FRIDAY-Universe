# TASK-INF-LLM-002 — Provider failover drill under simulated outage (re-drill)

- Task: TASK-INF-LLM-002 (P2, owner muse_15). MASTER_PLAN §6 standing backlog.
- Claim: hub #2045 comment 7217161116 (2026-11-27 ~17:00 IST, BE 16:35 §C / BE 17:01 §C).
- Branch: `muse15/task-inf-llm-002-failover-drill` @ `382f971a` (main head at drill time).
- Drilled: Fri 2026-11-27 ~18:00–18:05 IST, sandbox leg only (see bounds).
- Verdict: **PASS (sandbox leg) — the failover ladder on current code absorbs
  single-provider and double-provider outages and serves via the next rung,
  inside the request deadline; a total outage surfaces as a typed error, never
  a hang or a fabricated answer. 34/34 drill tests green.**

## Method (secret-free by construction)

1. **Sandbox, not the live fleet.** A scratch venv (Python 3.12.3, pytest 9.2.0)
   with the Inference dependency floor from `Inference/requirements.txt`
   (pydantic, pydantic-settings, httpx, fastapi, python-dotenv, sqlalchemy).
   No live keys, no network, no production contact: every provider is a
   scripted fake from the INF-008 drill suite (`_FakeProvider`: ok / e503 /
   e429 / e401 / garbage / connerr / hang / empty / midfail).
2. **Real code under test.** The suite wires the real `ModelGateway.execute()`
   and the real fallback ladder (`gateway.py::_execute_dynamic_fallback`,
   OpenRouter dynamic rung → deterministic waterfall groq → openrouter →
   gemini → apinex → local tier → LiteLLM) with hand-built key pools,
   limiters and health tracker; the route-level tests drive the real FastAPI
   app through `TestClient`. Only the providers are faked.
3. **Suite run:** `Inference/tests/test_inf008_failover_drill.py`, full file,
   34 tests (33 pre-existing + 1 new, this task), exit 0.

## Results — sandbox, 2026-11-27 ~18:02 IST

| Scenario | Observed | Time |
|---|---|---|
| Primary groq 503 → fallback serves | Served by next rung, provenance `requested groq → actual != groq` (all 9 primaries parametrized) | 1.01 s each |
| **groq + openrouter both 503 → waterfall gemini serves (NEW test)** | `answer:gemini`, `resp.provider == "gemini"`, provenance `requested_provider: groq → actual_provider: gemini` | 1.01 s |
| groq + openrouter 503 at the FRIDAY route (`/v1/friday/ask`) | 200, `answer: gemini` | 1.01 s |
| groq 429 → keys quarantined + fallback serves | Both groq keys quarantined (2/2), answer served | 1.01 s |
| Primary hang (gemini) on a 4 s budget → fallback serves | Served inside budget | 2.41 s |
| OpenRouter discovery hang on a 6 s budget → waterfall serves | Served inside budget (pre-fix: >38 s on an 8 s budget) | 3.51 s |
| All providers 503 → typed error | `TemporaryUnavailableError`, inside deadline | 1.01 s |
| All providers hang on a 3 s budget → typed error | `TimeoutError`/`GatewayError`, no hang | 3.00 s |
| All providers 401 → `AuthenticationError`; all connrefused → `GatewayError` | Typed, no hang | <1.1 s each |
| Total outage at `/v1/friday/ask` (fast lane + DAG) | 503, "No answer fabricated" | 1.05 s / 2.04 s |
| Total outage at `/v1/chat/completions` | 503, `error.code == provider_degraded`, `retryable: true` | <1.1 s |
| Structural empty completion on every provider | 503, not an empty 200 | <1.1 s |
| Waterfall breadth contract (groq/openrouter/gemini/apinex down) | Second-tier providers never attempted (policy, TASK-REL-043/044) | 1.01 s |
| Unified manager, total outage | `degraded: true`, empty content, status `degraded` | 1.02 s |

Full run: **34 passed in 29.42 s** (`pytest tests/test_inf008_failover_drill.py`,
exit 0, 2 warnings — both pre-existing config/deprecation warnings, no test
warnings). Gateway-level subset alone: 26 passed in 24.42 s.

## What this run added

- **New test** `test_drill_groq_and_openrouter_down_waterfall_serves_gemini`
  (`Inference/tests/test_inf008_failover_drill.py`, +23 lines). It closes the
  G2 gap from M2's 2026-11-22 live drill (PR #1277, merged): that drill never
  exercised the waterfall rung live because the OpenRouter rung always served
  first. Here the waterfall gemini rung is exercised and proven at the gateway
  level (in-process, scripted fakes) and at the FRIDAY route level
  (`test_drill_ask_mixed_outage_served_by_survivor`, pre-existing, re-run green).

## Observation (not a defect claim)

- Every ladder traversal measures **~1.01 s**, whatever the failure mode —
  single 503, double outage, total-outage error. That floor suggests a fixed
  ~1 s cost somewhere in the failover path (retry/quarantine/backoff), not
  per-rung latency. Source not identified in this run; follow-up for the
  coordinator, not a defect claim. It does not threaten any deadline measured
  here (worst case 3.51 s on a 6 s budget).

## Honesty bounds — what this drill did NOT prove

- **The live leg was NOT run.** The acceptance's live leg (simulated outage
  against live Inference on FRIDAY-Server, real providers) is blocked by the
  LIVE GATE CLOSED owner stop order (~2026-11-24 16:42 IST, still in force;
  bridge approval 7113152293 unanswered; no deploy window open). No live
  service was touched, no live key was read, no live request was made.
- **The last live-provider evidence is M2's 2026-11-22 drill** (PR #1277,
  merged; `Inference/docs/INF-LLM-002-FAILOVER-DRILL.md` on main): groq
  simulated down → OpenRouter served a real answer in 4.7 s total, fallback
  latency 1.1 s. That evidence is 5 days old and predates this re-drill's
  code head; this run re-proves the ladder on current code with scripted
  fakes only.
- **The waterfall gemini rung is proven in-process, not live.** Same caveat
  as M2's G2, narrowed: the rung is now exercised (gateway + route level),
  but still with fakes, not a live gemini call.
- Route-level timings above are TestClient timings, not network timings.

## Five states

- implemented: YES (new test + this evidence doc)
- tested: YES — sandbox (34/34 green on head `382f971a`)
- merged: NO (work PR to open; evidence only, no board hunk per coordinator
  ruling 7200564540 — board flips are coordinator-only)
- deployed: N/A (no production change; test + evidence doc only)
- production-verified: NO — live leg owed when the gate opens

## Next

- Live leg (real providers, FRIDAY-Server) when the LIVE GATE opens: repeat
  M2's harness method (separate harness process, groq simulated down, real
  adapters) against the current code head and append the receipts here.
- The ~1.01 s ladder floor: identify the fixed cost (follow-up, coordinator's
  call whether it is a task).

— Muse 15
