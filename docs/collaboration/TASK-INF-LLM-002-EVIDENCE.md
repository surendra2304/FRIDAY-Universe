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

---

## Live leg — Muse 7, 2026-11-28 (re-slot completion)

Muse 15's re-drill above left the live leg owed ("production-verified: NO — live leg owed when the gate opens"). WATCH254 §C.5/§D (hub 7233833233; correction 7233848712) re-slotted TASK-INF-LLM-002 to Muse 7 as head. Muse 7 claimed on hub #2045, comment 7233895138 (2026-11-28 04:17:38Z), branch `muse7/task-inf-llm-002-failover-drill` @ `5de10dbf`. This section is the live leg; Muse 15's sandbox record above stands unchanged.

### Method (sandbox-first; service never touched)

- Harness: `/tmp/infllm002_drill_harness.py` on Oracle Server 1, run as a separate process in the live Inference environment (`PYTHONPATH=/opt/friday_universe/Inference`, venv312, cwd `/opt/friday_universe/Inference`, live checkout `797387b8`); the running Inference service was never touched, restarted, or reconfigured, and no production traffic was routed through the harness. Run window (scored run): 2026-11-28 04:21–04:23 UTC. This is the same separate-process construction as TASK-INF-049.
- Simulation, in-process only: `app.providers.get_provider` is wrapped so that, while the outage flag is on, every Gemini adapter instance raises `TemporaryUnavailableError` (503-class, retryable) instantly. The real gateway code then does what it would do in a real outage: retry across keys with 60 s quarantine, exhaust the primary, annotate `fallback_reason` (TASK-INF-045), and climb the capability fallback ladder with the reserved budget. Key pools and health state mutated by the drill belong to the harness process only.
- Trials: small prompt (21 estimated tokens, short deadline class, so the primary attempt actually runs — a large prompt would direct-skip the primary per TASK-INF-022 and would not be an outage drill), model `gemini-flash-latest`, `max_tokens=50`, `temperature=0`, explicit 60 s budget. Control ×2 (no simulation), outage ×3 (simulation on), recovery ×1 (simulation removed, after waiting out the in-process quarantine).
- Live settings read from the service's own config: `REQUEST_TIMEOUT = 60.0`, `PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0` → primary slice 15.0 s. Unchanged.
- No key value was read, printed, logged, or stored by the harness; only pool counts are reported. (The gateway's own quarantine log lines mask keys; no key fragment is reproduced here.)

### Live service state (before and after)

- Inference `/health` 200 (inference v2.0.0, providers groq/cerebras/openrouter/gemini/nvidia, 19 active specialist agents) at 2026-11-28T04:19:31Z and 04:21:29Z (before) and 04:23:43Z (after the scored run) — identical shape throughout.
- Harness-process key pools before: gemini 15/15/0, groq 15/15/0, openrouter 15/15/0, nvidia 2/2/0, others 0 (total/active/quarantined). The service process's pools are separate and were not mutated.
- Every drill request is accounted for: 6/6 routing receipts `outcome=success`, 6/6 failover-log events, 0 errors. No production traffic was dropped or rerouted by the drill (acceptance 2).

### Results

| Trial | Elapsed | Served | Ladder latency | Receipt `fallback_reason` | Provenance reason |
|-------|---------|--------|---------------|---------------------------|-------------------|
| control 1 | 17.22 s | openrouter / nvidia/nemotron-3.5-lightning:free | 1.12 s | `primary_timeout` | deadline exceeded after 15.0 s |
| control 2 | 15.83 s | openrouter / nvidia/nemotron-3.5-lightning:free | 0.82 s | `primary_timeout` | deadline exceeded after 15.0 s |
| outage 1 | 15.85 s | openrouter / nvidia/nemotron-3.5-lightning:free | 0.84 s | `primary_timeout` | deadline exceeded after 2.5 s |
| outage 2 | 15.90 s | openrouter / nvidia/nemotron-3.5-lightning:free | 0.89 s | `primary_timeout` | deadline exceeded after 0.3 s |
| outage 3 | 11.58 s | openrouter / nvidia/nemotron-3.5-lightning:free | 0.81 s | `primary_unavailable` | simulated outage (HTTP 503) |
| recovery 1 | 16.22 s | openrouter / nvidia/nemotron-3.5-lightning:free | 1.21 s | `primary_timeout` | deadline exceeded after 15.0 s |

- **Outage failover: 3/3 served end-to-end inside the 60 s budget, 0 errors** (acceptance 1 met). Simulated-503 stub calls: 10 + 3 + 2 = 15 (the full Gemini pool quarantined across the outage trials, in the harness process only).
- **Failover latency shape (observation):** under an instant-503 outage, total failover time ≈ the full 15 s primary slice + ~0.9 s ladder serve. In outage trials 1–2 the per-provider rate limiter paced the key retries, so the primary slice expired mid-retry-loop and the receipt reads `primary_timeout` (the provenance "after 2.5 s / 0.3 s" is the last attempt's remaining slice); in trial 3 the retries exhausted the remaining keys inside the slice and the receipt reads `primary_unavailable` with the simulated 503 named. Either way the ladder served with ~44 s of budget to spare. The ~0.9 s ladder latency is consistent with Muse 15's ~1.01 s sandbox ladder floor above. No mechanism beyond the limiter pacing visible in the log timestamps is claimed.
- **Control/recovery honesty:** the Gemini primary served 0/3 non-outage trials in this window — even on a 21-token prompt it hit the 15 s slice (alias 503 → in-adapter failover → hang, the INF-049 pattern). The recovery trial ran after a 20 s wait (pool back to 7/15 active) and the primary still timed out; the ladder served. This drill therefore proves the failover leg under both simulated and natural primary failure; it does **not** show primary recovery, and none is claimed.
- **Fallback serve note:** every ladder serve was the OpenRouter dynamic pick `nvidia/nemotron-3.5-lightning:free`, whose thinking trace consumed the drill's own 50-token cap (`finish_reason=length`) — the same observation as INF-049 G3, at this drill's smaller cap. The requests were served; the truncation is a property of the drill's `max_tokens=50`, recorded here so the serve is not overstated.
- A first harness run (04:19–04:21 UTC, same construction) produced consistent outage timings (15.89 / 15.88 / 11.70 s) but misattributed routing receipts due to a slicing bug in the harness (receipts are newest-first); the scored run above fixes the capture and is the evidence of record. The v1 artefacts are kept on Server 1 (`/tmp/infllm002_drill_v1.json`).

### Reproduction

Harness (kept on Server 1): `PYTHONPATH=/opt/friday_universe/Inference /opt/friday_universe/venv312/bin/python /tmp/infllm002_drill_harness.py` from `/opt/friday_universe/Inference`. Server 1 artefacts: `/tmp/infllm002_drill_harness.py` (sha256 `b5080338…`), `/tmp/infllm002_drill.json`, `/tmp/infllm002_drill.log`, plus the v1 pair.

### Five states (after live leg)

- implemented: YES — sandbox re-drill (Muse 15) + live-leg harness and run (Muse 7); no routing, deadline, or service behaviour change.
- tested: YES — sandbox 34/34 (Muse 15) + live drill 6 trials, all accounted for with receipts, provenance, and failover-log events.
- merged: NO — live-leg work PR open this run, awaiting Muse.
- deployed: N/A — nothing to deploy (drill + evidence only; the live service was not touched).
- production-verified: YES for the failover leg — under a simulated Gemini outage the live gateway failed over to the next provider and served 3/3 requests inside budget, with the production service healthy before and after. Primary recovery is explicitly not verified (see control/recovery note).

— Muse 7
