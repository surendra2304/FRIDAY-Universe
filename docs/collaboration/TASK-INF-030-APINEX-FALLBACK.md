# TASK-INF-030 — APInex gateway fallback: evidence

**Task:** Inference — wire the APInex gateway as a free fallback provider behind the router, with a failover proof.
**Status:** Implemented + tested (repo CI, see PR). **Not merged, not deployed, not production-verified.**
**Work PR:** #1620, branch `muse2/task-inf-030-apinex-gateway-fallback`, head `dc201f5b` (code) + evidence/board commit (see PR).
**Claim:** hub #1483 comment 7119147638, 2026-11-24 ~07:00 IST. Claim PR #1611 merged by Surendra 07:59 IST.

## 1. What APInex is (docs research, 2026-11-24)

- Unified AI API gateway at **`https://api.apinex.bond/v1`**, OpenAI-compatible Chat Completions (`/v1/chat/completions`) plus a native Anthropic Messages wire (`/v1/messages`, not used here). One key, format `sk-apx-...`, env var `APINEX_API_KEY`.
- Catalogue: 44 model ids (live `/v1/models`, see §3), 22 with the `free/` prefix at `$0.00/1M`.
- Published free tier: **~20–25M tokens/day shared across the free models, 15 requests/minute per account**, resets every 24h. Sources disagree on activation: one guide says the free quota needs a one-time $5 deposit and a daily dashboard check-in; another (tested 2026-09-11) says no credit card required. The live probe (§3) settles it for this account: several `free/*` models answer at $0 with no deposit made.
- Operator went public mid-October 2026, **no published SLA**. It is a fallback rung by design — never a primary. That is why it sits last in the waterfall (§4).

## 2. Key provenance (names only — no values anywhere in this repo)

- S2 `/opt/friday_universe/CREDENTIALS.md`, section `## APInex (owner-provided 2026-11-23)`: base URL `https://api.apinex.bond/v1` and one API key (bare value, no env-var name recorded there). The code reads the standard `APINEX_API_KEY` / `APINEX_API_KEYS` variables per the repo convention; the operator sets them from the credentials file at deploy time.
- No key value was copied, printed, or committed at any point. Probe scripts read the key on Server 2 only and printed statuses/latencies/model ids.

## 3. Live probe from Server 2 (bridge `run_shell`, 2026-11-24 ~09:05 IST)

Unauthenticated `GET /v1/models` → **403 in 0.82s** (DNS/TLS/egress to `api.apinex.bond` work; auth required, as expected).

Authenticated (key read on-server, never printed):

| Call | Result |
|---|---|
| `GET /v1/models` | **200, 0.86s, 44 models, 22 `free/*` ids** |
| `POST /v1/chat/completions` `free/qwen-3.8-max` | **200, 1.11s, content `OK`, `cost_tokens` 0** |
| `POST /v1/chat/completions` `free/gpt-6-luna` | **200, 3.93s, content `OK`, `cost_tokens` 0** |
| `POST /v1/chat/completions` `free/deepseek-v4.1-flash` | **200, 9.47s, content `OK`, `cost_tokens` 0** |
| `POST /v1/chat/completions` `free/gemini-3.8-flash` | **402 `billing_error`: "available only with a subscription"** |
| `POST /v1/chat/completions` `free/glm-5.3` | **402 `billing_error`: "available only with a subscription"** |

Free ids listed live (22): `free/claude-opus-4.6`, `free/claude-sonnet-4.6`, `free/deepseek-v4-flash-0731`, `free/deepseek-v4-pro-0813`, `free/deepseek-v4.1-flash`, `free/gemini-3.1-pro`, `free/gemini-3.8-flash`, `free/gemini-4-hydrogen`, `free/glm-5.3`, `free/glm-5.3-flash`, `free/glm-5.3-flashx`, `free/gpt-6-luna`, `free/hy4`, `free/hy4-flash`, `free/kimi-k2.8`, `free/kimi-k3`, `free/mimo-v2.6-flash`, `free/mimo-v2.6-pro`, `free/minimax-m3`, `free/minimax-m3.1-flash`, `free/muse-spark-1.3`, `free/qwen-3.8-max`.

**Consequences (the honest core of this task):**
- The `free/` prefix does **not** mean "will answer": `free/gemini-3.8-flash` and `free/glm-5.3` are subscription-gated (402) on this account. The catalogue cannot distinguish gated from working — only a completion attempt can.
- Therefore the provider's static model list contains **only the three ids verified answering live** (`free/qwen-3.8-max`, `free/gpt-6-luna`, `free/deepseek-v4.1-flash`), the default is the fastest verified one (`free/qwen-3.8-max`, 1.11s), and capability selection searches the verified list before the discovered catalogue. A gated id is never a default or a capability fallback.
- Only 5 of the 22 free ids were completion-tested (the three working + two gated). The other 17 are listed, not verified; the provider never selects them unless discovery returns them and no verified model matches a capability keyword (second pass only).
- Oddity, recorded not explained: the provider reports ~396–400 prompt tokens for a one-line prompt (usage `prompt_tokens` 396–400, `cost_tokens` 0). At ~400 tokens/call the 20–25M daily allowance still covers ~50k calls/day, so this is not a quota risk; it is noted for the next person who reads usage numbers.

## 4. What was built (PR #1620, commit `dc201f5b`)

- **New `Inference/app/providers/apinex.py`** — `ApinexProvider(OpenAICompatibleProvider)`, base `https://api.apinex.bond/v1`, default `free/qwen-3.8-max`, verified-only `SUPPORTED_MODELS`, capability keywords that never match gated ids, `fetch_available_free_models` with the module-level 5-minute cache + single-flight lock (TASK-INF-004 pattern from `openrouter.py`), `find_model_by_capability` (verified-first), `generate_with_capability`.
- **`Inference/app/providers/__init__.py`** — `"apinex": ApinexProvider` in `_PROVIDER_MAP`.
- **`Inference/app/core/config.py`** — `APINEX_API_KEY` / `APINEX_API_KEYS` fields; `get_provider_keys("apinex")` works via the existing `getattr` mechanism; `"apinex"` added to `validate_environment()`.
- **`Inference/app/core/policies.py`** — `("apinex", "free/qwen-3.8-max")` appended to `DETERMINISTIC_WATERFALL_ORDER` (last cloud rung, after gemini); `PROVIDER_FALLBACK_MATRIX` gains `apinex -> groq`.
- **`Inference/app/providers/gateway.py`** — `"apinex"` added to `_initialize_pools` `all_providers` (pool + rate limiter); limiter 10 RPM — under the published 15 RPM free-tier cap; waterfall comment updated.
- **`Inference/app/inference_runtime/model_registry.py`** — apinex rung in `WATERFALL_MODELS` (`free/qwen-3.8-max`, 1M context, chat/stream/json/tools/vision) and in `get_waterfall_sequence`.
- **`Inference/app/core/key_inventory.py`** — `"APINEX"` in the provider list.
- **Tests** — new `Inference/tests/test_inf030_apinex_fallback.py` (registration, config keys, wire contract with fake transport, discovery cache, verified-first capability selection incl. never-picks-gated, waterfall placement + cycling, gateway pools, registry rung, gateway failover drill with scripted providers). Updated the pinned-boundary tests to the deliberate new boundary: `test_inf008_failover_drill.py` (PROVIDERS += apinex; waterfall trio → **quartet**), `test_rel047_gateway_guards.py` (nvidia/oversized-groq tests fail apinex too; waterfall-groq-skip test now asserts apinex serves), `test_universal_task_and_waterfall.py` (order + cycling + registry + resolve_fallback gemini → apinex), `test_key_inventory_report.py` (`APINEX: 0`).
- **CI list** — `test_inf030_apinex_fallback.py` added to the Inference test list in `.github/workflows/owner-workflows.yml`.

## 5. Staging failover proof (Server 2, 2026-11-24 ~09:15 IST)

Harness (separate from the running service; live Inference untouched): the branch code at `dc201f5b` was extracted to `~/inf030-staging` on Server 2; a python3.12 venv with `Inference/requirements.txt` was created there; the harness read the APInex key from S2 CREDENTIALS.md on-server, gave groq/openrouter/gemini **dummy** keys (so the gateway attempts them instead of skipping at the credential gate), and forced all three down (`get_provider` raises 503 for them). One real request through the real `ModelGateway.execute("groq", ...)`:

```
KEY POOL: Quarantining key 'stag...-key' on provider 'groq' for 60s
GATEWAY: Primary provider 'groq' failed. Initiating capability fallback
OpenRouter dynamic fallback failed (TemporaryUnavailableError)
PROVIDER SWITCH EVENT: Switching from 'groq' to 'openrouter' ...
Waterfall fallback provider 'openrouter' failed: 503 ... simulated down
Waterfall fallback provider 'gemini' failed: 503 ... simulated down
RESULT provider: apinex
RESULT model: free/qwen-3.8-max
RESULT latency_s: 3.23
RESULT content: 'OK'
RESULT provenance: {'requested_provider': 'groq', 'requested_model': 'openai/gpt-oss-120b',
  'actual_provider': 'apinex', 'actual_model': 'free/qwen-3.8-max', 'capability': 'general',
  'fallback_reason': '503 Service Unavailable: groq simulated down (TASK-INF-030 staging drill)'}
RESULT apinex_pool_keys: 1
DRILL PASS: primary groq forced down, APInex rung served
```

Staging cleaned up afterwards (`~/inf030-staging`, venv, harness, requirements copy all removed; `/opt/friday_universe` checkout untouched).

## 6. Verification status

- **Implemented:** code + tests + evidence doc + board flip in PR #1620.
- **Tested:** repo CI on the PR head (see PR checks). Staging failover proof above (live, real gateway, real key, real completion).
- **CI fix (2026-11-24 ~09:25 IST):** first CI run failed the `contracts` job on the TASK-REL-068 collection guard — not on the new test (it was collected), but on the three pre-existing test files this PR modifies (`test_inf008_failover_drill.py`, `test_key_inventory_report.py`, `test_universal_task_and_waterfall.py`), which no PR-triggered workflow collected. Fixed by adding all three to the Inference pytest list in `owner-workflows.yml` (same job as the other Inference tests), so CI now runs them; re-verified with the audit script locally (5/5 covered, 0 stale) before pushing.
- **Not merged:** only Muse merges. **Not deployed:** the running Inference service is untouched; live-copy wiring needs coordinator clearance on hub #1483. **Not production-verified:** no live traffic has used the rung yet.

## 7. Honesty bounds / follow-ups for Muse

1. **Free list moves.** APInex controls which models carry the `free/` prefix; an id free today may go paid or subscription-gated tomorrow (two already are). The verified-only static list + discovery cache mitigate this, but the default should be re-probed if the rung starts 402ing — the servability tracker will show it (rung failures are recorded).
2. **Only 5 of 22 free ids completion-tested.** The other 17 may also be gated or slow; the provider never prefers them, but a capability keyword could select one on the second pass if no verified model matches. The keywords are deliberately narrow (qwen/deepseek/gpt) to keep that path on verified ids.
3. **DeepSeek is slow** (9.47s for a 2-token completion) — it is the reasoning fallback only, never the default.
4. **Prompt-token counting looks inflated** (~400 tokens for a one-line prompt). Not a quota risk at the published allowance, but worth one look if usage numbers ever look wrong.
5. **No env-var name for the key exists in CREDENTIALS.md** (bare value under the APInex section). The deploy step must set `APINEX_API_KEY` from that value; nothing in this PR touches live config.
6. **Operator risk:** 3-week-old operator, no SLA, resold models with unpublished serving details. Late rung by design; if APInex ever degrades the fleet, the rung fails over to the local tier exactly like any other cloud rung.

### Merge repair (2026-11-24 ~09:47 IST)

PR went dirty after main moved to ec78a623 (Forge/tests/test_frg001_cage.py added to the workflow list; other workers' board records landed). Repaired by merge commit only — no force-push, no rebase. The workflow list keeps both additions; the INF-030 board flip is re-applied onto main's board. CI to be re-verified on the merged head.

— Muse 2
