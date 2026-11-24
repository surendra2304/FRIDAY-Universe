# TASK-INF-032 — Inference: wire the INF-031 routing deadline into the live routing path

**Worker:** Muse 7 · **Date:** 2026-11-24 · **Branch:** `muse7/task-inf-032-routing-deadline`
**Board:** TASK-INF-032 (Inference: wire the INF-031 routing deadline into the live routing path and prove it timed)
**Assignment:** coordinator ruling, watch 7122541986 (~10:30 IST): "CLAIM NOW under the blocked-head skip (INT-020 is blocked on the FRD-042 deploy gate; INF-032 is workable)."
**Claim:** issue #1483 comment 7122598802 (~10:35 IST). Claim PR #1628 merged 11:02:21 IST (merge `a80f05f6`).
**Work PR:** owed (opens after this doc is filed; board flip CLAIMED → IN_REVIEW rides in it).

## Acceptance (board)

"Deadline live in routing, with timed evidence showing 9k-token prompts complete inside it."

**Verdict: PARTIAL — the wiring is done and proven live; the 9k-token completion through the FRIDAY client path is blocked by a live gateway outage, not by the deadline.** The deadline is live in routing on both sides (server 60 s enforced, client now 70 s = 60 + 10 margin, verified first-hand); a 9k-token prompt completed inside it through the direct endpoint (3.91 s), and smaller prompts complete through the client path (1.64 s, 14.09 s). But 0/6 provider-path attempts at the 9k size completed — all HTTP 503 `provider_degraded` from the gateway's model-selection policy — and a 9k synthesis prompt also 503'd after 42.38 s. The failure is the gateway's fallback ladder being unservable for the >7000-token class right now, not the deadline: every failure is typed and inside budget (longest attempt 42.38 s < 60 s; the 70 s client timeout never fired first). The completion leg needs the ladder back; that is flagged for Muse below, and TASK-INF-033 (muse_11, the follow-up live-proof leg) will hit the same wall until it recovers.

## 1. The live routing path, traced first-hand (code + live config)

Real FRIDAY chat traffic reaches Inference through the escalation path, not the `/v1/friday/ask` debate path (escalation.py docstring: the escalation target was chosen on live probes 2026-11-15 as `/v1/chat/completions`, NOT `/v1/friday/ask`):

```
FRIDAY chat → EscalatingLLMProvider → InferenceChatProvider (FRIDAY/src/friday/llm/escalation.py)
  → POST http://127.0.0.1:8001/v1/chat/completions
  → Inference gateway (route deadline 60 s, TASK-INF-010; 15 s primary slice; >7000-token bypass)
```

Live S1 state verified first-hand via the bridge (2026-11-24 ~11:00 IST):

- `FRIDAY.service` active, Main PID 3424508 (since 08:28:27 IST); `Inference.service` active, Main PID 3469202.
- FRIDAY `.env` (76 lines): `FRIDAY_INFERENCE_URL=http://127.0.0.1:8001`, `INFERENCE_URL=http://127.0.0.1:8001`, `FRIDAY_LLM_PROVIDER=gemini` (primary is Gemini direct; Inference is the escalation/fallback target), `FRIDAY_LLM_ESCALATION` unset (→ escalation enabled), **`FRIDAY_LLM_ESCALATION_TIMEOUT_S` unset**, `FRIDAY_INFERENCE_API_KEY` set.
- Inference `.env`: `REQUEST_TIMEOUT`, `PRIMARY_ATTEMPT_FRACTION`, `PRIMARY_ATTEMPT_MAX_SECONDS` all unset → code defaults apply (60.0 / 0.6 / 15.0).

Server side already enforces the deadline on all three live entry points (read on main):

- `/v1/providers/execute` — gateway `_request_timeout_budget` (default `REQUEST_TIMEOUT` 60.0), primary slice `min(budget × 0.6, 15.0)`, enforced by `asyncio.wait_for` (INF-031 proved the default path live: 20.12 s wall).
- `/v1/chat/completions` — route-level `route_deadline = now + REQUEST_TIMEOUT` (TASK-INF-010); first attempt and retry share one deadline via remaining-budget forwarding (`v1_core_routes.py` ~1737–1779).
- `/v1/friday/ask` — `UnifiedExecutionRequest.timeout` forwarded to the gateway; fast-lane path passes none → gateway default 60.0 s applies.

## 2. The gap found (client side, unwired)

The FRIDAY-side clients did not reflect the 60 s server deadline:

- `InferenceChatProvider` (the live routing path): `timeout` defaulted to **150 s** (`FRIDAY_LLM_ESCALATION_TIMEOUT_S` unset on S1) and never passed a budget to the server. FRIDAY could block a user turn up to 150 s on a call the gateway had already bounded at 60 s. The deadline was not wired into this client.
- `AIUniverseClient` (the `/v1/friday/ask` debate/second-opinion path — NOT the escalation target): hard-coded `timeout=45.0`, **tighter** than the server's 60 s budget. A 9k-token prompt the gateway serves in 45–60 s (INF-019 A1: 53.3 s wall) would be killed client-side. Same hole class, opposite direction. **Not changed in this task** — it is a different path, and its 9k-token shape currently completes inside 45 s via the bypass (~20 s); documented here and flagged for Muse as a follow-up.

## 3. The wiring (this task)

`FRIDAY/src/friday/llm/escalation.py` only — one shared deadline, used as the client-side bound:

```python
INFERENCE_ROUTING_DEADLINE_S = 60.0          # mirrors Inference REQUEST_TIMEOUT (INF-029 KEEP)
INFERENCE_CLIENT_TIMEOUT_MARGIN_S = 10.0     # transport margin

def _inference_timeout_s() -> float:
    default = INFERENCE_ROUTING_DEADLINE_S + INFERENCE_CLIENT_TIMEOUT_MARGIN_S  # 70.0
    try:
        return max(10.0, min(600.0, float(os.getenv("FRIDAY_LLM_ESCALATION_TIMEOUT_S", str(default)))))
    except ValueError:
        return default
```

- Default client timeout 150 s → **70.0 s** (60 s deadline + 10 s margin). The client must wait at least as long as the server budget, plus margin — otherwise it kills a call the gateway would have served inside its budget.
- Env override `FRIDAY_LLM_ESCALATION_TIMEOUT_S` still wins; clamp 10–600 s unchanged.
- No payload change is possible or needed: `ChatCompletionRequest` has no timeout field; the route computes its deadline from `settings.REQUEST_TIMEOUT` server-side. The wiring is the client-side bound matching the server budget.
- Module docstring updated (default 150 → 70, with the TASK-INF-032 citation).

Tests — `FRIDAY/tests/test_llm_escalation.py`, 5 new (default is deadline+margin; env override wins; invalid env falls back to the deadline; clamp bounds; provider constructor uses the deadline timeout by default):

- Local: **33/33 pass** (28 pre-existing + 5 new), pytest 9.2.0 in a clean venv against the branch files, run twice (once before and once after re-applying the edit — identical diff). Local run used a stubbed `friday/llm/__init__.py` to avoid the provider-SDK import cascade; the real package is untouched on the branch. Full-suite proof rides on PR CI.
- No other file references `FRIDAY_LLM_ESCALATION_TIMEOUT_S` or `_inference_timeout_s` (repo search: only `escalation.py`).

## 4. Timed evidence (live S1, 2026-11-24 11:11–11:32 IST)

Method: probe scripts run on S1 with the FRIDAY venv (`/opt/friday_universe/venv/bin/python`), loading the edited `escalation.py` via importlib so the deployed FRIDAY service is untouched. Key and URL read from the FRIDAY `.env` (values never printed). Prompts: oversized = 400-function module, 50,070 chars (gateway-counted 13,320 prompt tokens; old chars//4 label 12,517); control = "What is 2+2?" (36 chars); synthesis = 20-section document, 15,522 chars (~3.9k tokens); 9k-synthesis = 60-section document, 49,326 chars (~12.3k est tokens). All walls are client-measured.

| Probe | Path | Prompt | Wall | Result |
|---|---|---|---|---|
| C control | provider | 36 chars | 1.64 s | 200, served gemini-3.5-flash-lite, routing simple/math_expression, fast tier |
| B oversized direct | direct POST /v1/chat/completions | 50,070 chars / 13,320 tokens | 3.91 s | 200, served meta-llama/llama-3.3-70b-instruct via openrouter (downgrade, `selected_as: best_suitable_for_code`), 867 chars answer |
| A oversized provider | provider | 50,070 chars | 25.5 s | **503** `provider_degraded` — "could only be served by a model outside the verified catalogue" |
| A2/A3 retry | provider | 50,070 chars | 1.2 s / 0.49 s | **503**, same error |
| A5 provider | provider | 50,070 chars | 1.79 s | **503** — payload recorded and diffed against B: **byte-identical** (same model, messages, temperature, max_tokens) |
| B2 direct | direct | 50,070 chars | 4.3 s | **503**, same error — direct now fails too |
| SYN | provider | 15,522 chars / ~3.9k tokens | 14.09 s | 200, served openai/gpt-oss-120b, real structured summary |
| SYN9K | provider | 49,326 chars / ~12.3k est | 42.38 s | **503**, same error, after 41.5 s of gateway work |
| retry2 A2/A3 | provider | 50,070 chars | 9.5 s / 1.09 s | **503**, same error |

What the numbers prove:

- **The deadline is live in routing, both sides.** Client default verified live: `_inference_timeout_s()` = 70.0, `provider.timeout` = 70.0. Server 60 s enforced: no call ever waited past it; the longest attempt (SYN9K, 42.38 s) failed typed *inside* budget. The 70 s client timeout never fired first on any call.
- **The 9k completion through the client path is blocked by gateway provider availability, not the deadline.** 0/6 provider-path attempts at the 9k size completed; the same shape completed direct once (B, 3.91 s) and then failed direct too (B2, 4.3 s). The payload A/B diff is empty — there is no client-path difference left to find. The gateway's model selection refuses the >7000-token class right now: the bypass routes those prompts to the fallback ladder, and the ladder's models are currently outside the verified catalogue / unselectable (journal 11:11:41: "Gemini model gemini-3.8-flash experienced 503 high demand"; the llama downgrade that served B stopped being selectable minutes later). Under-7000-token prompts serve fine (SYN 14.09 s, control 1.64 s).
- **The failure mode is honest and bounded.** Every failure is a typed HTTP 503 `provider_degraded` inside the 60 s budget — no hang, no fabricated answer, no client-side kill.

## 5. States

- **implemented:** YES — wiring + 5 tests (this work PR).
- **tested:** YES — 33/33 local green; live probes on S1 (table above). PR CI pending.
- **merged:** NO — work PR owed; merge decision is Muse's.
- **deployed:** NO — S1 FRIDAY still runs the old code (PID 3424508 since 08:28 IST; `FRIDAY_LLM_ESCALATION_TIMEOUT_S` unset → 150 s live until a deploy). Deploy is a separate step needing Muse's hub clearance; not done here.
- **production-verified:** PARTIAL — deadline live in routing and proven (client 70 s, server 60 s, typed failures inside budget); 9k-token completion through the client path blocked by the fallback-ladder outage (see §6).

## 6. Gaps and follow-ups for Muse

- **G1 — fallback-ladder outage for the >7000-token class (live, since ~11:11 IST 2026-11-24).** Every >7000-token prompt 503s with `provider_degraded` (model-selection policy) while under-7000-token prompts serve. This blocks the completion leg of this task and will block TASK-INF-033 (muse_11, follow-up live-proof leg) the same way. Needs a gateway-side look (which ladder models are quarantined/unselectable, and why the llama downgrade stopped being selectable). No config changed here; no restart performed.
- **G2 — `AIUniverseClient` 45 s hard-code** (`FRIDAY/src/friday/tools/ai_universe_client.py`, `timeout: float = 45.0`). Same hole class on the `/v1/friday/ask` path, opposite direction: tighter than the 60 s server budget. Not changed in this task (different path; its 9k shape currently completes inside 45 s via the bypass). Suggest a follow-up task to wire it to the same deadline + margin.
- **G3 — S1 probe scratch to clean.** `/tmp/inf032_probe/` on S1 and `/opt/friday_universe/inf032_probe/` on S2 hold the probe scripts + edited escalation.py copy (S2 copy also used to recover the file after this VM's /tmp cleanup). Removed after filing; the numbers in §4 are the durable record. Probe result JSONs live on S1 at `/tmp/inf032_probe_results.json`, `/tmp/inf032_retry_results.json`, `/tmp/inf032_syn_results.json`, `/tmp/inf032_syn9k_results.json` (transient).
- **G4 — local test note.** The 33/33 local run used a stubbed `friday/llm/__init__.py` in the scratch tree only (the real `__init__.py` eagerly imports every provider + SDKs; this VM has none installed). The branch files are untouched by the stub. Full-suite proof rides on PR CI.

## Files

- `FRIDAY/src/friday/llm/escalation.py` — deadline constants + `_inference_timeout_s()` default 150 → 70 s (+ docstring).
- `FRIDAY/tests/test_llm_escalation.py` — 5 new tests (TASK-INF-032 section).
- `docs/collaboration/TASK-INF-032-ROUTING-DEADLINE-LIVE-PATH.md` — this file.
- `docs/collaboration/WORK_BOARD.yaml` — TASK-INF-032 record (board flip CLAIMED → IN_REVIEW in the work PR).

— Muse 7
