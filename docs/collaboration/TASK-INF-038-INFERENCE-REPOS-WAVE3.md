# TASK-INF-038 — Inference repos wave 3: evidence

**Task:** REPO-IMPLEMENT Inference repos wave 3 (P2). **Owner:** Muse 2.
**Branch:** `muse2/task-inf-038-inference-repos-wave3`. **Claim:** hub #1483 comment 7157989685.
**Board:** INF-038 AVAILABLE → IN_REVIEW in this PR (MEM-032 already reads MERGED on main — kept byte-identical).

**Five states:** implemented YES / tested YES (repo CI; see below) / merged NO / deployed NO / production-verified NO.
**Live legs gated by the owner stop order** (in force since 2026-11-24 ~16:42 IST): no deploy, no restart, no live-fleet writes. Staging/offline proof only.

## Verdicts

| Repo | Verdict | Why (evidence) |
|---|---|---|
| FreeLLM API (tashfeenahmed/freellmapi, 58,029★, MIT) | Reference-only | Its pattern IS Inference's native baseline (KeyPool/ModelGateway, quota ledger, failover ladder); a self-hosted instance is already consumable via TASK-IG-INF-02 custom endpoints with zero new code. Free installs get the model catalogue 30 days behind the paid live feed; README: "This project is for personal experimentation and learning, not production." |
| OmniRoute (cheaper-inference/OmniRoute, 90,204★, MIT) | Reference-only | Self-hosted gateway software (394 providers, 150+ free, 4-tier fallback). Critical advisory GHSA-hf57-cqmx-p4gr: unauthenticated RCE via custom ACP agent endpoint when requireLogin is off — do not self-host as-is. Its one transferable idea, token compression (15–95% claimed), is already implemented natively (TASK-IG2-INF-04, `Inference/app/providers/token_compression.py`). |
| Strata (Niko1221/Strata, 47,984★, MIT) | Reject | Local MoE inference engine that needs a discrete GPU: `terminal/strata_control/gpu_fit.py` requires MIN_CARD_GB 3.5 / SPLIT_MIN_VRAM_GB 8.0, NVIDIA RTX 20+ or supported AMD; iGPU ignored. Benches measured on RTX 5070 12GB / 5060 Ti 16GB / RTX 3090 24GB. The fleet has neither GPU nor RAM. 0 "Kaggle" hits in the whole repo — the reel's "run it on free Kaggle GPUs" framing is unsupported by the code. |
| needle / Cactus (cactus-compute/cactus, 14,908★, Apache-2.0) | Adapt | Needle 2 is a 45M-parameter tool-calling model, ~28 MB RAM native, fully offline. Piloted TASK-IG-INF-04 (LOCAL_INFERENCE_ASSESSMENT.md §5–§6): 6/6 command prompts routed correctly. Adapted as an optional gateway fast path (below). |

## Guardrail proof of absence (before this change)

GitHub code search over `Inference/app`, 2026-11-25, plus a provider-directory listing:

- `freellmapi`: 2 hits — docstring mentions only (`app/routers/admin_dashboard.py`: dashboard pattern; `app/providers/key_vault.py`: encrypted key-storage pattern). No adapter, no endpoint, no import.
- `omniroute`: 2 hits — `app/providers/gateway.py:644` comment + `app/providers/token_compression.py` docstring (the native implementation). No adapter.
- `strata`: 1 hit — a local variable named `strata` (dict grouping records) in `app/agents/real_advanced_reasoning.py`. The English word, not the project. No adapter.
- `cactus`: 0 hits. No `freellmapi.py` / `omniroute.py` / `strata.py` / `cactus.py` / `needle.py` module exists under `Inference/app/providers/`.
- `tool_calls` in `Inference/app`: 0 hits — no existing tool-calling flow.

## The adaptation: needle fast-path router

**Files**

- `Inference/app/providers/needle_router.py` (new) — `NeedleRouter`, `CactusNeedleEngine`, `StubNeedleEngine`, `try_fast_path`, `build_engine`, env flags.
- `Inference/app/providers/base.py` — `ProviderResponse.tool_calls` (default `None`, backwards-compatible).
- `Inference/app/providers/gateway.py` — pre-stage in `ModelGateway._execute_inner`, after token compression + deadline marking, before the litellm branch. `stream()` untouched.
- `Inference/tests/test_inf038_needle_router.py` (new, 26 tests) — registered in `.github/workflows/owner-workflows.yml` (INF-030 pattern; the tier-1 list is a fixed 4-file list, untouched).
- `Inference/.env.example` — documents `NEEDLE_FAST_PATH_ENABLED` / `NEEDLE_ENGINE`.

**Design (follows the token-compression pre-stage precedent)**

- When enabled (`NEEDLE_FAST_PATH_ENABLED=true`, default False) and the request is a single user message, the gateway tries the needle engine first. A routed command returns a tool-call `ProviderResponse` (provider `needle`, model `needle-2`, `finish_reason="tool_calls"`) and spends no cloud round trip. Anything else falls through to the normal ladder exactly as before.
- The fixed tool registry is the pilot's three FRIDAY device-safe tools: `get_weather`, `set_reminder`, `search_memory`. Adding a tool is a code change.
- The engine is used through `Cactus.complete()` (routing only), never `Cactus.run()` (which executes the tool functions itself). The gateway never executes tools; the caller executes them with its own executors.

**Pilot constraints enforced (TASK-IG-INF-04 §5–§6)**

1. Escalate-on-no-call: "What is the capital of France?" dead-ended in the pilot (no answer at all). The router escalates on no-call, unknown tool, or invalid arguments — never fabricates an answer. Regression-tested.
2. Fresh stateless session per command: "Tell me a one-line joke" re-ran the previous turn's memory search in the pilot. The router creates one session per `route()` and never reuses it; the cactus engine is constructed with `stateless=True` (resets state at the start of every call). Regression-tested, including a session-count assertion.
3. Confidence is recorded for observability only and is never a routing gate: the pilot proved it does not separate success from failure (the dead-end scored 0.60). Tested with a 0.05-confidence call that still routes.

**Fail-safe**

- The `cactus` package is imported lazily inside `CactusNeedleEngine`; importing the module never requires it (keeps `test_module_importability.py` green, which imports every module under `app/`). Missing package → `RuntimeError` with install instructions at engine-build time, caught by `try_fast_path` → falls through to the ladder.
- Any fast-path failure (engine build, routing, session) escalates to the cloud ladder; the stage is wrapped so it can never break serving.
- No `app/core/config.py` edit (CRLF line endings) — env vars are read directly in `needle_router.py`, like `token_compression.py`.

**Cactus API verified from source (cactus-compute/cactus main, 2026-11-25)**

- `Cactus(tools, system, ..., stateless=False)`; `complete(text) -> dict` envelope `{"type": "call"|"text", "function_calls": [{"name", "arguments"}], "confidence": ...}`; `run()` executes tools (not used); `reset()` / `close()` exist. Tools may be passed as dict schemas (no executables needed for `complete()`).
- First construction downloads the ~71 MB engine + weights cache (~53 s on the sandbox pilot); the engine is built lazily on first use and cached per process.

## What is proven here vs what is owed

- **Repo-proven (this PR):** router + engine binding + gateway wiring + 26 in-process tests (no network, no live keys), incl. the full 8-prompt pilot replay (6 routed, 2 escalated) and gateway integration (routed command never calls a provider; no-call / error / multi-message fall through to the ladder).
- **NOT live-proven:** no live engine run in this PR (owner stop order). The pilot's sandbox run (2026-11-15) is the only live engine evidence, and it was on the sandbox CPU, not the target device.
- **Owed after clearance:** (1) device admission gate (IG-INF-04 §6) — re-run the pilot prompt set, extended with the two failure prompts as regression cases, plus a 20-command FRIDAY-flavoured set, on the actual device, requiring ≥95% correct routing and zero dead-end turns; (2) FRIDAY client handling of `finish_reason="tool_calls"` (future consumer change — the gateway returns the tool call, the client must execute it); (3) deploy with the flag off by default, enable only after (1) passes.

## Board

- INF-038: AVAILABLE → IN_REVIEW (branch + PR set by this PR). MEM-032: already MERGED on main (PR #1793, merge f80e563d, 2026-11-25 13:41 IST) — record kept byte-identical.

— Muse 2
