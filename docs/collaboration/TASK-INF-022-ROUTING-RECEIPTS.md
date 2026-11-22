# TASK-INF-022 — Per-request routing receipts + prompt-size deadline classes

Date: 2026-11-22, probe ~20:05 IST. Worker: Muse 7.
Task: INF-LLM-003 gap — adaptive routing has no live audit evidence, and
Gemini deadline misses (2/2 on ~9k-token prompts) depend silently on the
OpenRouter fallback. Add per-request routing receipts on a status endpoint
and prompt-size deadline classes from the INF-LLM-003 measurements.

## What was built

- `Inference/app/providers/gateway.py`
  - `prompt_deadline_class()`: "short" (<= 7,000 calibrated tokens) /
    "large" (above). The boundary is the Groq-guard limit (7,000), the
    codebase's existing oversized-prompt line; the INF-019 shape (13,543
    calibrated tokens) sits well above it. Classification uses the
    calibrated estimator (TASK-INF-021), so the class is the size Gemini
    actually sees.
  - Large Gemini primaries with no explicit caller timeout route DIRECTLY
    to the fallback ladder (no primary attempt). INF-LLM-003 measured the
    Gemini primary cut at 14.7 s on 3/3 gateway trials for the 13,519-token
    shape, with direct completions at 6.4 s / 67.3 s / 99.3 s / >150 s.
    An explicit caller timeout opts out (the caller asked to wait).
  - The timeout budget itself is UNCHANGED for both classes
    (INF-LLM-003 recommendation: KEEP the deadline — no sane
    primary-slice deadline covers that tail).
  - Every `execute()` records a routing receipt (task class / capability,
    requested vs served provider/model, latency, deadline class, fallback
    use + direct flag, timeout budget, prompt-token estimate) in a bounded
    in-memory ring (last 100, process-local, no persistence).
- `Inference/app/health.py`: `/status` gains a `routing` section
  (deadline classes, receipt counts, recent receipts). All existing
  fields untouched.
- `Inference/tests/test_inf022_routing_receipts.py`: 8 new tests
  (class boundaries, INF-019 shape, direct routing, explicit-timeout
  opt-out, primary + error receipts, store cap/counts).

## Live probe — both prompt classes, Server 1

Method (harness `/tmp/inf022_probe.py`, run on Oracle Server 1 in the live
Inference environment — venv312, cwd `/opt/friday_universe/Inference`, the
service's own `.env` — as a separate process against the worktree
`/tmp/inf022-worktree` at branch commit `ca2587cd`;
`Inference.service` never touched, restarted, or reconfigured).
Live settings read during the run: `REQUEST_TIMEOUT = 60.0`,
`PRIMARY_ATTEMPT_FRACTION = 0.6`, `PRIMARY_ATTEMPT_MAX_SECONDS = 15.0`,
so the primary slice is `min(60 x 0.6, 15) = 15.0 s`.
Key pools unchanged (gemini 15 total / 15 active, groq 15/15,
openrouter 15/15).

### Short prompt — class short, primary attempted, fallback served

- Prompt: "What is 2+2? Answer in one short sentence." (16 est tokens).
- Gemini primary attempted and missed (same hang behaviour INF-010
  measured from Server 1); the ladder served
  `openrouter/nvidia/nemotron-3.5-lightning:free` in 17,984.6 ms total.
- Receipt (observed 2026-11-22T14:35:05Z): capability `general`,
  provider_requested `gemini`, provider_served `openrouter`,
  model_served `nvidia/nemotron-3.5-lightning:free`, deadline_class
  `short`, timeout_budget_s 60.0, outcome `success`,
  fallback_used `true`, fallback_direct `false`.

### Large prompt — class large, primary skipped, direct to fallback

- Prompt: byte-identical INF-019 probe A rebuild (35,214 chars,
  13,543 calibrated tokens).
- Gemini primary SKIPPED (no attempt, no 14.7 s burned); the ladder
  served `openrouter/nvidia/nemotron-3.5-lightning:free` in 1,815.5 ms
  total — against the 21.39 s gateway path INF-LLM-003 measured for the
  same shape (14.7 s wasted primary + fallback).
- Receipt (observed 2026-11-22T14:35:23Z): capability `code_review`,
  provider_requested `gemini`, provider_served `openrouter`,
  model_served `nvidia/nemotron-3.5-lightning:free`, deadline_class
  `large`, timeout_budget_s 60.0, outcome `success`,
  fallback_used `true`, fallback_direct `true`,
  routing_note "large prompt: Gemini primary skipped (INF-LLM-003)".

### /status surface — receipts visible in-process

`system_status()` in the probe process returned a `routing` section:
deadline_classes short_max_tokens 7000 / large_min_tokens 7001,
receipt_counts total 2 / success 2 / error 0 / fallback_used 2 /
fallback_direct 1, and both receipts above under `recent_receipts`.
The deployed service's `/status` does NOT show this yet (it runs the
old code) — the section appears after merge + deploy, which is NOT
claimed here. No service state was changed by the probe.

## Tests (Server 2, venv312, pytest)

- `tests/test_inf022_routing_receipts.py`: 8 passed.
- Neighbours: `tests/test_rel047_gateway_guards.py` 12 passed,
  `tests/test_inf017_unified_groq_size_guard.py` 7 passed,
  `tests/test_inference_explicit_model_contract.py` 17 passed.
- `tests/test_ig_inf01_long_context_routing.py`: 1 failure, pre-existing
  (expects `openai/gpt-oss-120b`, gets `meta-llama/llama-3.3-70b-instruct`;
  documented in TASK-INF-021 as pre-existing and stash-proven there).
  Untouched by this change; left as-is.

## Safety and service state

- No key value was read, printed, logged, or stored. Key pools
  unchanged (see above).
- Live service healthy before and after (`/health` 200,
  `Inference.service` MainPID 2148054 unchanged, active throughout).
  Live `/status` baseline re-checked after the probe: unchanged shape,
  no `routing` section (old code, as expected).
- No service restarted, reconfigured, or deployed; no trading change;
  no live-trading code touched. Two live LLM calls total (one short,
  one large), same load class as the INF-LLM-003 drills.
- One unit-test bug found by the new suite and fixed in the same PR:
  `routing_receipts(limit=0)` returned everything (`[-0:]` slice);
  it now returns `[]`.

## Run notes (process, not product)

- The shared Server 2 checkout is contested: mid-run another worker's
  branch was checked out there, so the first commit landed on their
  branch and a `git stash pop` briefly conflicted on two files neither
  worker owned. Both repaired and verified: the stray commit was
  rebuilt onto this branch by plumbing (same tree, parent c3736155),
  the other branch was restored to its own tip, the two conflicted
  files were restored to HEAD, the other worker's stash entry was left
  untouched, and no other worker's file was modified. The pushed branch
  contains only this task's 3 files (+503/-1).
- Work PR: https://github.com/surendra2304/FRIDAY-Universe/pull/1386

## Decisions owed to Muse

- None for merge. Deployment of the new `/status` section (S1 service
  restart) is a separate step for the coordinator, not done here.

— Muse 7
