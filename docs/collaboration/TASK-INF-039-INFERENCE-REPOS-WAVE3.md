# TASK-INF-039 — Inference repos wave 3: evidence

**Task:** REPO-IMPLEMENT Inference repos wave 3 (P2). **Owner:** Muse 2.
**Branch:** `muse2/task-inf-039-inference-repos-wave3`. **Claim:** hub #1483 comment 7161981611.
**Board:** INF-039 AVAILABLE → IN_REVIEW in this PR (INF-038 already reads MERGED on main — kept byte-identical).

**Five states:** implemented YES / tested YES (repo CI; see below) / merged NO / deployed NO / production-verified NO.
**Live legs gated by the owner stop order** (in force since 2026-11-24 ~16:42 IST): no deploy, no restart, no live-fleet writes, no live Bytez calls. Staging/offline proof only.

## Verdicts

| Repo | Verdict | Why (evidence) |
|---|---|---|
| ClawRouter (BlockRunAI/ClawRouter, MIT, TypeScript) | Reference-only | A local proxy that classifies each request across 15 dimensions and routes to the cheapest capable model in under 1 ms — but it is a front door to BlockRun's paid gateway: beyond a small fixed free set (8 open-weight models per the scout card; the README currently advertises 10 free NVIDIA models) every call is metered spend, USDC via the x402 protocol or a card-funded BlockRun key. That breaks the FREE-only rule, and Inference already routes through free-tier keys with its own router (`app/inference_runtime/adaptive_router.py`, `app/routing/cost_router.py`, `app/providers/token_compression.py`). Keep as a reference for the token-compression layer — especially its 7-layer pipeline's tool-observation summarisation — if Inference's context costs ever need cutting; do not adopt the gateway. |
| Free Claude Code (Alishahryar1/free-claude-code, AGPL-3.0, Python, ~65k★ Oct 2026 / ~70,640★ per scout card) | Reference-only | A local proxy/launcher that points Claude Code and 11 other coding harnesses at non-Anthropic models (61 providers, NVIDIA NIM trial as the default, 1.3B+ free tokens/month claimed). It is not free Claude — the harness stays, the brain is swapped for someone else's model on a trial key. Inference already implements this exact pattern in production (multi-provider free-tier key pool, failover ladder, quota ledger, best-suitable routing — the same verdict as FreeLLM API and OmniRoute in INF-038). The cherry-picks are its provider-catalogue breadth (61 providers worth diffing against Inference's pool) and its harness-side trick of preserving native streaming/tool use while swapping the model behind Claude Code-class clients, which is relevant to Forge's coding agents. AGPL-3.0 is copyleft: no code from it can be lifted into this MIT repo. Note the name collision: paoloanzn/free-code (a telemetry-stripped build from a leaked Claude Code source snapshot) is a different project and is NOT the scouted one; it was not adopted or relied on. |
| Codex-ChatGPT Web bridge (miuuyy/codex-chatgpt-web, MIT, TypeScript/Bun, ~15.4k★) | Reject | A desktop launcher that drives an authenticated ChatGPT Web session through Playwright browser automation so ChatGPT Web models appear inside Codex's model picker. Reject on terms-of-service grounds (the scout's rationale, and the README's own words: "unofficial browser automation, not an OpenAI API", "not affiliated with or endorsed by OpenAI"): its whole purpose is to spend a consumer ChatGPT subscription's web allowance programmatically through a coding agent, with real account-suspension risk, and FRIDAY's standing rule is legitimate free tiers and official APIs only. It also has nothing to adapt: it needs a paid ChatGPT plan for flagship models, a desktop Electron host with browser workers, and a live ChatGPT session profile (a sensitive login artifact) — none of which exists on a headless server fleet — and it exposes no API surface. |
| Bytez (Bytez-com/docs — docs repo; the product is a closed hosted service) | Adapt | One API key over a large open-model catalogue, OpenAI-compatible. The documented $0 tier (≤7B open models, 1 concurrent request) passes the FREE-only rule as a trial, but only as a low-priority pool member behind Gemini/Groq/OpenRouter/NIM — which is where the gateway already places it (9th of 10 rungs). Adapted below: the TASK-IG2-INF-01 adapter proved Bytez *can* be called; this task enforces the three $0-tier properties the adapter left unenforced. |

## Guardrail proof of absence (before this change)

GitHub code search over the repo, 2026-11-25 (scout registry `IntelX/intelx/registries/scouted_repos.json` + `docs/collaboration/TASK-INT-044-PRODUCTION-TRACKER.md` are the only hits for the first three — registry entries, not code):

- `clawrouter`: 0 hits in `Inference/app`. No adapter, no endpoint, no import.
- `free-claude`: 0 hits in `Inference/app`. No adapter, no endpoint, no import.
- `codex-chatgpt`: 0 hits in `Inference/app` (the third repo-wide hit is `IntelX/tests/test_ig_scouted_repos.py`, a registry test). No adapter, no endpoint, no import.
- `bytez`: 23 hits — the existing TASK-IG2-INF-01 surface only: `app/providers/bytez.py` (adapter), `app/providers/bytez_probe.py` (quota probe), `Inference/tests/test_ig2_bytez.py`, gateway rung gate (`bytez_rung_enabled`, off by default), quota-ledger state `unproven_free_tier`, candidate spec `benchmarks/candidates/bytez.json`. No concurrency guard, no served-model check, no model-allowlist enforcement anywhere in that surface.

## The adaptation: Bytez free-tier guardrails

**Files**

- `Inference/app/providers/bytez_guard.py` (new) — `BytezSlotBusyError`, `BytezModelNotAllowedError`, `acquire_bytez_slot`, `slot_wait_seconds`, `validate_bytez_model`, `verify_served_model`, `annotate_bytez_response`.
- `Inference/app/providers/bytez.py` — `BytezProvider.generate()` / `stream()` overrides running the guardrails; adapter, model list, and rung gate untouched.
- `Inference/tests/test_inf039_bytez_guard.py` (new, 34 test functions / 48 cases with parametrize) — registered in `.github/workflows/owner-workflows.yml` (INF-038 pattern).
- `Inference/.env.example` — documents `BYTEZ_SLOT_WAIT_SECONDS` (default 5).

**Design (follows the INF-038 precedent: a small provider-side module + a focused override, no gateway change — the ladder already places Bytez 9th of 10 and the rung gate already defaults it off)**

1. **Concurrency-1 slot.** The $0 tier allows a single concurrent request, but the gateway's per-provider rate limiter caps Bytez at 4 concurrent (`ModelGateway` builds every provider's limiter with `max_concurrency=4`) and the adapter had no guard at all. A process-wide, one-slot semaphore (`BYTEZ_MAX_CONCURRENT = 1`, keyed by running event loop so a dead loop's semaphore is replaced, not reused) now wraps every Bytez `generate`/`stream` call. A caller that cannot get the slot within `BYTEZ_SLOT_WAIT_SECONDS` (default 5 s) fails fast with `BytezSlotBusyError` (a `TimeoutError`), which the gateway takes through its timeout branch and escalates to the fallback ladder — the request is still served, by the next rung.
2. **Served-model identity (the INF-005 serve-check, at runtime).** Bytez is an aggregator: the model that answers is not necessarily the model asked for — and `OpenAICompatibleProvider.generate` records the *requested* model in `ProviderResponse.model` without ever reading the `model` field Bytez returned. A substitution would therefore be recorded as the requested model. `verify_served_model` compares the two ids exactly (model ids are canonical Hugging Face ids; a case difference is a different model) and `annotate_bytez_response` records the verdict in `raw_response["bytez"]` (`requested_model` / `served_model` / `served_model_match` / `served_model_outcome`) and logs a warning on mismatch or on a missing served id. The response is still returned — the content is usable — but `resp.model` keeps the requested id so gateway quota accounting stays keyed on what was asked for; the truth lives in the annotation, not in a silent substitution. A missing served id is `unknown`, never a match.
3. **Free-tier model allowlist.** The adapter lists only ≤7B open models, but nothing stopped a caller asking Bytez for a larger, credit-metered model through the rung — paid spend through the FREE-only rule's back door. `validate_bytez_model` resolves the effective model (`request.model` or the default) and refuses anything outside `BYTEZ_SUPPORTED_MODELS` with `BytezModelNotAllowedError` (a `ValueError`, which the gateway normalises into a non-retryable error — no key quarantine, no same-provider retry — and escalates to the ladder) before any HTTP call is made and before the slot is taken. The allowlist itself is pinned by test: exactly the four ≤7B models; adding a larger model is a billing decision that must come with probe evidence, never silently.

**Fail-safe**

- The rung gate is untouched: while `INFERENCE_BYTEZ_RUNG_ENABLED` is off (the default) the gateway refuses Bytez entirely, so these guards only ever run after an operator has read probe reports and switched the rung on.
- A busy slot never hangs a request: bounded wait, then a typed `TimeoutError` the ladder already knows how to escalate.
- A refused model never takes the slot and never makes a call (asserted: zero HTTP calls on rejection).
- The slot is always released, including when the guarded call raises (HTTP 500 / 429) and when a stream consumer closes early.
- No `app/core/config.py` edit (CRLF line endings) — env vars are read directly in `bytez_guard.py`, like `needle_router.py` / `token_compression.py`.
- `stream()` holds the slot for the whole stream (a streamed call is still one of the tier's single concurrent requests); `health()` is a `/models` metadata call and takes no slot.

**Deliberately not done**

- Bytez was not added to `Inference/config/free_tier_routes.json`: that catalogue is owned by TASK-INF-042 and its test fails if any verified-free entry is an API route; Bytez's free *volume* is still unproven (see below), so its $0 tier belongs in the probe + ledger, not in the routes catalogue.
- No gateway change: the ladder order, the rung gate, and the quota-ledger state (`unproven_free_tier`, no declared limit) were already correct for a low-priority trial rung.
- No live probe run in this PR: no key is provisioned, and the owner stop order forbids live calls. The probe harness (`bytez_probe.py`) is unchanged.

## What is proven here vs what is owed

- **Repo-proven (this PR):** guardrails + provider wiring + 34 tests (48 cases, fake HTTP client, no network, no live keys), incl. slot contention / release-after-error / release-on-early-stream-close, served-model match / mismatch / unknown annotation, allowlist refusal with zero HTTP calls, and gateway integration (rung off → served by another rung with the bytez provider never constructed; rung on → bytez serves).
- **NOT live-proven:** no live Bytez call in this PR (owner stop order). The $0 tier's recurring free volume remains UNPROVEN — the billing docs state the tier's shape (≤7B, 1 concurrent) but no recurring allowance, and a single probe run cannot prove one.
- **Owed after clearance:** (1) provision `BYTEZ_API_KEY` on Server 1, run `python -m app.providers.bytez_probe` across several days, and only then let an operator declare a ledger limit and enable the rung; (2) one live end-to-end completion through the gateway with the served-model verdict `match` and the slot behaving under concurrent load; (3) if the trial shows the $0 tier grants no usable recurring volume, downgrade the Bytez card to reference-only per the scout rationale.

## Board

- INF-039: AVAILABLE → IN_REVIEW (branch + PR set by this PR). INF-038: already MERGED on main (PR #1821, merge 41e50b97) — record kept byte-identical.

— Muse 2
