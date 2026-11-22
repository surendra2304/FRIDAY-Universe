# TASK-INF-021 — Calibrate the gateway token estimator against Gemini counted tokens

Date: 2026-11-22, measurement ~12:47–12:49 IST. Worker: Muse 7.
Task: INF-LLM-003 gap G1 — the gateway token estimator understates Gemini's
prompt size (8,803 estimated vs 13,519 Gemini-counted for the INF-019 prompt,
+54%). Calibrate `estimate_prompt_tokens` so the gateway estimate tracks
Gemini's counted prompt tokens; evaluate the 7,000-token Groq guard on true
tokens; pin the calibration with a regression test.

## What was measured

Method (harness `/tmp/inf021_calibrate.py`, run on Oracle Server 1 in the live
Inference environment — venv312, cwd `/opt/friday_universe/Inference`, the
service's own `.env` — as a separate process; `Inference.service` never
touched, restarted, or reconfigured):

- A 9-prompt corpus of varied shapes: the exact INF-019 probe A rebuild
  (35,214 chars), a prose document, real gateway source, small + large JSON,
  a short question, guard-boundary prose and code at ~28,000 chars, and a
  multi-turn exchange with a system instruction.
- For each item: chars (system + messages, exactly as the gateway estimator
  counts them), the old gateway estimate (chars // 4), and Gemini's counted
  tokens via the REST `countTokens` endpoint (model `gemini-flash-latest`,
  same contents shape and system instruction as the generate path).
- Validation: one direct generate on the INF-019 prompt (max_tokens=1) to
  confirm `countTokens` agrees with generate `usageMetadata`.

Method check — `countTokens` == generate usage: the generate returned
`prompt_tokens=13,519` (6.51 s, served as `gemini-3.6-flash` after a 503
failover from `-latest`), identical to `countTokens` (13,519) and to all
three INF-LLM-003 trials. The measurement method is validated.

One API quirk found: `countTokens` rejects a `systemInstruction` field
(HTTP 400, "Unknown name systemInstruction"). The multi-turn item was
therefore measured as two calls — messages, plus the system text counted
separately as a user content (117 + 142 = 259) — and the doc records that.

## Results — the old estimator understates code and JSON by up to 35%

| Prompt | Chars | Old est (//4) | Gemini counted | Old error | New est (2.6) | New error |
|---|---:|---:|---:|---:|---:|---:|
| inf019_code_review | 35,214 | 8,803 | 13,519 | −34.9% | 13,543 | +0.2% |
| prose_doc | 6,929 | 1,732 | 2,184 | −20.7% | 2,665 | +22.0% |
| code_real_gateway_head | 12,850 | 3,212 | 3,405 | −5.7% | 4,942 | +45.1% |
| json_small | 6,149 | 1,537 | 2,258 | −31.9% | 2,365 | +4.7% |
| json_big_300_records | 67,415 | 16,853 | 24,921 | −32.4% | 25,928 | +4.0% |
| short_question | 54 | 13 | 13 | 0.0% | 20 | +53.8% |
| guard_prose_28k | 28,031 | 7,007 | 4,797 | +46.1% | 10,781 | +124.7% |
| guard_code_28k | 28,046 | 7,011 | 8,312 | −15.7% | 10,786 | +29.8% |
| multiturn_with_system | 1,074 | 268 | 259 | +3.5% | 413 | +59.5% |

Chars/token ranges 2.605 (repetitive code) to 5.843 (repeated prose). No single
divisor tracks Gemini tightly across shapes — that is the finding, not a
failure of the measurement. The old divisor (4) underestimates 6 of 9 shapes.

## Calibration decision — 2.6 chars/token, exact integer form ×5//13

The estimator serves a safety guard (Groq's 8,000 TPM cap), so the calibration
is anchored on the worst case, not the average: the densest measured shape is
2.605 chars/token (INF-019), so the divisor is 2.6. At 2.6 the estimator never
underestimates on the measured corpus (worst case INF-019: +0.2%) and
overestimates prose-like shapes by up to +125% — the safe direction for a
guard: a false skip reroutes, a false pass draws a 413.

- `Inference/app/providers/gateway.py`: `estimate_prompt_tokens` now computes
  `chars * 5 // 13` (exact integer form of ÷2.6; the 7,000-token boundary is
  exactly 18,200 chars), with the calibration rationale in a comment and the
  constants `TOKEN_ESTIMATE_NUM = 5` / `TOKEN_ESTIMATE_DEN = 13` exported.
- `Inference/app/api/v1_core_routes.py`: `_CHARS_PER_TOKEN` removed;
  `_estimate_prompt_tokens` and `_estimate_context_tokens` import the gateway
  constants, so selection and the guard can never drift apart (TASK-INF-012).
- The 7,000-token `GROQ_PROMPT_TOKEN_LIMIT` is UNCHANGED. The limit was always
  meant to be 7,000 tokens; it was measured in the wrong unit. It is now
  measured in calibrated tokens, with the designed 1,000-token response
  headroom under Groq's 8,000 TPM cap restored.

## Groq guard re-evaluated on true tokens

- The live gap is closed: a 27,900-char code prompt read 6,975 by the old
  estimator (passed the guard) while Gemini counts ~8,270 true tokens — over
  Groq's 8,000 cap. The calibrated estimator reads 10,730 and the guard
  blocks it (pinned by a regression test).
- 28,046-char code prompt: old 7,011 (blocked, barely), Gemini 8,312 (over
  the cap) — calibrated 10,786, blocked with margin.
- 28,031-char prose prompt: Gemini 4,797 (would have fit Groq) — calibrated
  10,781, blocked. A conservative false skip; safe, costs a reroute.
- INF-019 prompt: calibrated 13,543 vs 13,519 counted; guard blocks it, as it
  should (it already did at 8,803, for the wrong reason — now for the right
  one: the prompt really is ~13.5k tokens).

## Tests (Server 2, venv312, pytest)

Targeted files — 30 passed, 1 failed (pre-existing, see below):

- `Inference/tests/test_rel047_gateway_guards.py` — updated estimate (800
  chars → 307) and guard boundary (18,200 chars → 7,000; 18,203 → over),
  plus two new calibration tests: INF-019 rebuild tracks Gemini's 13,519
  within 1% (actual 13,543) with the guard tripping, and the 27,900-char
  dense-code prompt the old estimator passed is now blocked (10,730).
- `Inference/tests/test_inf017_unified_groq_size_guard.py` — over/under
  prompts rebuilt at the calibrated ratio; the under-limit prompt sits 200
  tokens below the guard so the full request stays under even with the
  role's registered system instructions (~307 chars for `code_generator`)
  added by the unified path before estimating.
- `Inference/tests/test_ig_inf01_long_context_routing.py` — context estimate
  updated (400 chars + 100 reserved → 253).
- `tests/test_inference_explicit_model_contract.py` — 17 passed. The
  extraction set follows the REL-042 lesson: `_CHARS_PER_TOKEN` removed,
  `TOKEN_ESTIMATE_NUM` / `TOKEN_ESTIMATE_DEN` added from the gateway.

Pre-existing failure, NOT caused by this change (proven by `git stash`:
fails identically on the clean tree):
`test_ig_inf01_long_context_routing.py::test_overflow_with_big_windows_unavailable_picks_largest_remaining`
expects `openai/gpt-oss-120b`, gets `meta-llama/llama-3.3-70b-instruct`. A selection-ranking expectation that
no longer matches the catalogue; unrelated to the estimator (it fails with
the old estimator too). Left as-is, flagged here.

Two findings from the debugging, for the record:

- The unified under-limit test is order-dependent in a pre-existing way:
  `code_generator`'s system instructions (307 chars) are only present once
  `app.agents.software_specialists` has been imported (auto-register on
  import). The old test passed either way because the old divisor left 23
  tokens of slack; the calibrated divisor leaves none, so the under-limit
  prompt is now sized with explicit headroom. The estimator correctly
  counts the system instruction — the test, not the code, needed the fix.
- `ruff` is not installed in the S2 venv312, so no local lint run; the
  changed lines respect the repo's 120-char limit (only pre-existing long
  `actual_nodes` lines in the contract test exceed it, unchanged in shape).

## Scope notes and follow-ups

- NOT changed: the provider adapters' `estimate_usage` heuristics
  (`gemini.py`, `local.py`, chars // 4) — cost accounting only, not
  guard-relevant. They inherit the same underestimate for cost; a
  follow-up can align them if cost accuracy matters. The gateway docstring
  now says so explicitly instead of claiming one shared estimator.
- Residual risk, stated plainly: prompts denser than 2.6 chars/token remain
  possible (e.g. minified/encoded blobs); the guard is a screen, not a
  guarantee. The gateway still fails over on a 413.
- No live service touched, restarted, or reconfigured. No key value was read,
  printed, logged, or stored: pool keys passed in-process only; key pools
  unchanged (gemini 15/15/0, groq 15/15/0, openrouter 15/15/0, nvidia 2/2/0
  before and after). 9 `countTokens` calls + 1 validation generate on
  Server 1, ~2 minutes, light load. Harness artefacts:
  `/tmp/inf021_calibrate.py`, `/tmp/inf021_calibrate.json`,
  `/tmp/inf021_retry_multi2.py`, `/tmp/inf021_multi.json`.

— Muse 7
