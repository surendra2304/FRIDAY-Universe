# TASK-INF-005 — Inference model quality benchmark

**What this is:** the measured evidence table for the best-suitable-model
policy (TASK-REL-043). A fixed test set was run against the **live**
Inference gateway on Server 1, and every answer was scored by the model
that actually **served** it (the gateway substitutes models when a route
degrades, and says so in the response — this benchmark attributes scores
to the server, not the request).

**Run:** 2026-11-15, against production `POST /v1/chat/completions`
(localhost, Server 1). 90 calls = 6 verified-catalogue models × 15 items.
Every call returned HTTP 200 — there were no 503s in this run; the
gateway's degradation behaviour showed up as *substitution* and
*truncation* instead. The fleet was under Wave-5 load (dozens of crews,
two ~956MB hosts) — latencies are honest for those conditions, and
relative comparisons are more robust than absolute numbers.

**Method (reproducible):**
- Fixed set `inf005-bench-v1` (`testset.json`): 15 items, 3 per task
  type — summarise, reason, code, extract, chat. Each item has a
  **deterministic programmatic checker** (fact-group coverage + length
  caps for summarise; exact/contains checks for reason and chat; JSON
  field equality for extract; the returned code is **executed** against
  unit tests for code). No LLM judge.
- Fixed system prompt, temperature 0, per-item `max_tokens` 50–400.
- `run_benchmark.py` (deployed server-side, calls the gateway on
  localhost) records wall latency, HTTP status, served model,
  provenance, token usage and the raw answer for every call.
  `score.py` re-scores the recorded answers deterministically.
- **Cost:** every catalogue route runs on free-tier keys, so cost is
  reported as *measured token consumption* (the quota actually spent),
  never as invented dollar prices.

## Headline table — as-served (the model that answered gets the score)

| model (as served) | summarise | reason | code | extract | chat | **overall** | median latency | calls | tokens in/out |
|---|---|---|---|---|---|---|---|---|---|
| openai/gpt-oss-120b (Groq) | 0.93 | 1.00 | 1.00 | 1.00 | 1.00 | **0.988** | see latency pass¹ | 28 | 3515 / 1129 |
| qwen/qwen3.8-27b (Groq) | 1.00 | 0.67 | 1.00 | 1.00 | 1.00 | **0.933** | **0.302s** | 15 | 2199 / 358 |
| meta-llama/llama-3.3-70b-instruct (OpenRouter) | 1.00 | 0.33 | 1.00 | 1.00 | 1.00 | **0.867** | 1.181s | 15 | 2108 / 288 |
| gemini-3.6-flash (Gemini) | 0.33 | 1.00 | 0.33 | 0.00 | 0.75 | **0.490** | 7.702s | 17 | 2179 / 110 |
| nvidia/nemotron-3.5-lightning:free (OpenRouter) | 0.50² | 0.00 | 0.00 | 0.00 | 0.00 | **0.100** | 1.506s | 15 | 2181 / 2900 |
| gemini-3.8-flash (Gemini) | — | — | — | — | — | **never served** | — | 0 | 0 / 0 |

¹ gpt-oss-120b's main-run latencies are unusable in both directions (see
finding 4): its live generations in this run were substitutions carrying
a failed Gemini attempt first (10.6–75.5s), and its direct calls were
mostly cache replays (≤0.65s). Its clean measure is the cache-busted
latency pass below: **median 0.698s live**.
² nemotron's summarise 0.50 is fact-presence credit inside its truncated
reasoning trace — the summaries were never actually delivered (finding 3).

## As-requested view (what a caller naming that model experienced)

| requested model | served as requested | answers' mean score | median latency |
|---|---|---|---|
| gemini-3.8-flash | **0 / 15** | 0.956 (substitutes answered well) | 40.699s |
| gemini-3.6-flash | 15 / 15 | 0.467 | 6.204s |
| openai/gpt-oss-120b | 15 / 15 | 0.978 | 0.093s (mostly cache replays) |
| qwen/qwen3.8-27b | 15 / 15 | 0.933 | 0.302s |
| meta-llama/llama-3.3-70b-instruct | 15 / 15 | 0.867 | 1.181s |
| nvidia/nemotron-3.5-lightning:free | 15 / 15 | 0.100 | 1.506s |

## Findings

1. **gemini-3.8-flash was unservable for the entire run window.**
   All 15 requests naming it were substituted (13× by gpt-oss-120b,
   2× by gemini-3.6-flash) after ~10–75s of cascade — and the latency
   pass re-test in a later window made it **0 served of 20 requests**
   across the day. Its own quality is
   **unmeasured** — it never produced an answer. The Gemini *provider*
   was healthy throughout (3.6 served 17 calls): the failure is at
   model level, and REL-043's availability filtering is provider-level
   (`_provider_available`), so it cannot see this failure mode.
   → Follow-up: model-level servability tracking in model selection.

2. **gemini-3.6-flash answers are truncated by the route, not by the
   model.** 14 of its 17 served calls ended `finish_reason=MAX_TOKENS`
   with 0–15 *visible* completion tokens while `total_tokens` ran
   330–518 — e.g. prompt 215 + completion 4 = total 411. Roughly
   100–380 hidden (reasoning) tokens are burned per call before the
   visible answer starts, so answers are cut mid-sentence
   ("In a six-week study of", "Meridian has approved"), extraction
   returns scaffolding text instead of JSON (extract 0.00), and one
   chat answer came back **empty**. Short factual answers survive
   (reason 1.00 — the correct number fits in 2 visible tokens).
   Until the Gemini route's token accounting is fixed, 3.6 is
   unsuitable for summarise/code/extract regardless of the underlying
   model's ability. (Scope note: this is Inference's Gemini route;
   FRIDAY's direct Gemini calls are a different path.)

3. **nemotron-3.5-lightning:free returns its chain-of-thought as the
   answer.** All 15 responses begin "Here's a thinking process:…",
   end `finish_reason=length`, and never reach a final answer — yet
   are served as HTTP 200 successes. Overall 0.100, and it burned the
   most output tokens of any model (2,900) doing it. As the catalogue's
   economy last-resort it is currently unusable at these token
   budgets; serving a truncated reasoning trace as a 200 is also an
   honesty defect in the response contract.

4. **The gateway's L1 response cache replays identical requests —
   proven, with a signature.** 11 of gpt-oss-120b's 15 direct calls
   report `prompt_tokens=0` **and** `completion_tokens=0` (impossible
   for a live call) with byte-identical content to its own earlier
   substituted generations, at 0.007–0.104s. Mechanism (code-verified):
   `unified_manager` consults `performance_cache` before executing;
   the fingerprint includes prompt, provider, model, max_tokens and
   temperature, and `/v1/chat/completions` never sets `no_cache`.
   Implications: (a) quota/cost accounting must treat 0/0-usage
   responses as zero provider cost; (b) any benchmark or latency SLO
   must cache-bust — the latency pass below does (per-model nonce in
   the system prompt changes the fingerprint). Note: this describes
   the cache as deployed at measurement time; TASK-INF-006 (PR #333)
   has since reworked the response cache with context-fingerprinted
   keys — re-measurement after that lands is the way to confirm the
   replay behaviour is gone.

5. **Quality slips are concrete, not vibes.** qwen3.8-27b missed one
   arithmetic item ("12" for a correct 22; reason 0.67).
   llama-3.3-70b missed two (29 and 39 for 22 and 38; reason 0.33).
   gpt-oss-120b made no measured error across 28 served answers.

## What this means for the REL-043 rankings

REL-043's `MODEL_SUITABILITY` vs this measurement (benchmark task types
map: reason→reasoning, code→code, chat→chat, summarise/extract have no
REL-043 type and fall back to its chat ranking):

- **reasoning** — REL-043: gpt-oss #1, gemini-3.8 #2, qwen #3.
  Measured: gpt-oss 1.00 ✓, qwen 0.67, llama 0.33, gemini-3.6 1.00
  (short answers survive truncation), gemini-3.8 unmeasured.
  **Ranking confirmed for #1.**
- **code** — REL-043: gpt-oss #1, qwen #2, gemini-3.8 #3.
  Measured: gpt-oss 1.00, qwen 1.00 (and ~100× faster in this run),
  llama 1.00, gemini-3.6 0.33. **Confirmed; qwen is the
  quality-per-latency winner.**
- **chat** — REL-043: gemini-3.8 #1, gpt-oss #2, qwen #3,
  gemini-3.6 #4. Measured chat scores: gpt-oss 1.00, qwen 1.00,
  llama 1.00, gemini-3.6 0.75, gemini-3.8 never served.
  **Not confirmed — the #1 pick was unavailable for the whole
  window.** On this evidence, chat should lead with qwen or llama
  (fast, correct) and use gpt-oss where quality matters most.
- **extract** (no REL-043 type): qwen, gpt-oss and llama all 1.00;
  gemini-3.6 and nemotron 0.00. Safe defaults: qwen/gpt-oss.
- **nemotron** is ranked last by REL-043 everywhere — consistent with
  measurement, but note even as last resort it returned unusable
  output in 15/15 calls (finding 3).

## Cache-busted latency pass (live latency, second window)

A second pass re-ran 5 items (one per task type) per model with a
per-model random nonce in the system prompt, defeating the L1 cache
fingerprint, so every call is a genuine live generation. It also
re-tests gemini-3.8-flash servability in a later window.

| model | served as requested | median live latency | notes |
|---|---|---|---|
| qwen/qwen3.8-27b | 5/5 | **0.196s** | fastest in both windows; its rsn1 error ("12") reproduced exactly — a deterministic slip |
| openai/gpt-oss-120b | 5/5 | **0.698s** | all 5 answers correct; the 8.011s summarise call is the outlier |
| meta-llama/llama-3.3-70b-instruct | 5/5 | 1.376s | — |
| nvidia/nemotron-3.5-lightning:free | 5/5 | 2.204s | 5/5 truncated thinking traces again (finish=length) |
| gemini-3.6-flash | 5/5 | 7.520s | MAX_TOKENS on 4/5 again |
| gemini-3.8-flash | **0/5** | 40.724s (as-requested, substitution cascade) | substituted by gpt-oss-120b 5/5 — **0/20 across both windows** |

Second-window verdicts: every main-run finding reproduced — gemini-3.8
unservable, gemini-3.6 truncating, nemotron leaking truncated
chain-of-thought, qwen's arithmetic slip. And the open latency question
is closed: **gpt-oss-120b's genuine live latency is ~0.7s median** —
the quality leader is also fast; its main-run numbers were cache
artefacts in one direction and cascade artefacts in the other.

## Limits

- One main window (~35 min) plus the latency-pass window, under
  Wave-5 load. Gemini servability and the truncation behaviour may
  vary with free-tier quota state (resets midnight Pacific).
- 3 items per type is a smoke-grade sample: it separates the measured
  tiers decisively (0.99 / 0.93 / 0.87 / 0.49 / 0.10) but cannot rank
  near-ties. The harness re-runs in one command for a bigger sample.
- long_context and vision (REL-043 types) are not covered by this set.
- Raw records: `results_inf005/scores.json` (per call: requested vs
  served model, latency, usage, score, answer excerpt),
  `results_inf005/summary.json`, `results_inf005/latency_pass.json`.
