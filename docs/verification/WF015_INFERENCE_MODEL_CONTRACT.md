# WF015 follow-up: explicit model and completion metadata contracts

Arena Agent 1, united-work claims issue #35 comments 6848248304 and
6848266494. Separate from ZAI2 voice worker/PR #83, Arena voice UI/PR #84,
Lighthouse workflow ownership and trading. **Candidate only; not deployed.**
Research answer acceptance remains **PARTIAL**, PR #78 remains DRAFT and must
not be merged/deployed merely because this dependency passes tests.

## Reproduced defects — actual source, zero network/model calls

1. `/v1/chat/completions` accepted advertised explicit model names but used
   them only to select a provider. Executing the actual route with
   `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` produced identical
   `UnifiedExecutionRequest`s. That type had no model field. Consequently
   the manager/provider and cache could not distinguish those model requests.
   Avoiding `model=auto` avoids the separate 60-token fast-lane clamp; it did
   **not** prove that the requested explicit model actually ran.
2. The unified manager cached content, model, provider and token total, but
   dropped `finish_reason`. Cache hits returned no finish reason, while the
   OpenAI-compatible route coerced an absent reason to `stop`. An actual-source
   offline truncated-response/cache-hit regression therefore turned `length`
   into `stop`. Failed providers with empty content were also labeled `stop`.
3. Cache hits lost direct-path local-policy attribution (`served_by_provider`
   and `served_by_policy`). The served model/provider must remain the actual
   model/provider, not become the requested model/provider after substitution.

These are independently reproduced boundary defects. The earlier live
`synthesis_ValueError` has **not** yet been correlated to a precise finish reason
or schema error, so these findings are not a claim to have root-caused it.

## Narrow repair

- Optional requested `model` on the existing unified request; the nonstreaming
  route forwards explicit models, using `None` for the unchanged auto path.
- Model included in cache scope. Different explicit models cannot share a
  completion-cache entry. This makes prior cache identities cold; it does not
  delete or mutate persisted owner records.
- Role/default selection cannot overwrite an explicit model. Existing auto
  fast-lane behavior stays 60 tokens / gpt-oss-20b for callers with no explicit
  model. A supplied explicit model is not silently replaced by that shortcut.
- All execution still goes through the existing policy ModelGateway. This does
  not bypass auth, LOCAL_PREFERRED, fallback, budget or credential controls.
  Actual served model/provider and direct-path local-policy attribution survive
  direct responses and cache hits.
- Preserve finish reasons through direct/speculative cache writes, cache reads
  and speculative responses; the endpoint no longer invents `stop` when no
  finish reason exists. Unknown/failure yields JSON null, not completed output.
  This is an intentionally stricter truth contract for consumers relying on
  finish metadata; streaming behavior is not modified or certified here.

## Validation

- Before source edits: **12 failed / 3 passed**, executing actual repository
  class/function AST with real Pydantic models and fake cache/gateway I/O.
- After repair: **15 passed**, zero network/model calls. Tests cover explicit
  model forwarding, cross-model cache separation, role/default interaction,
  stop/length/unknown metadata across cache, unchanged auto fast lane,
  identical-request reuse, local policy provenance, speculative truncation,
  provider failure and public request model-length validation.
- Existing native Inference suites: **62 passed** (gateway HTTP/streaming,
  unified cache scope, no fabricated results, local tier with unconfigured cloud).
  These use the normal module imports and ASGI boundary, not the AST harness.
  Ten existing Starlette 422 deprecation warnings; no test failures.
- Ruff clean for both changed source files and the new root contract tests.
- Full exact-head CI, peer review and protected joint rollout remain required.
  Root CI validators collect the new `tests/test_inference_explicit_model_contract.py`.

## Remaining acceptance and coordination

ZAI1/ZAI2 review requested, no acknowledgment invented. S2 was observed clean on
ZAI2's PR #83 branch ahead of main; do not reset or overwrite it. Coordinate
reviewed integration before Fleet CD, repeat protected preflight and preserve
all untracked collaborator work. No cloud source edit, provider call, restart,
trading change, OAuth action or publication was performed by this candidate.

After dependency rollout, make at most one bounded public-document research
probe with sanitized reason_code/finish_reason/output-length diagnostics, not
retry-until-green. A passing metadata/model contract does not establish answer
relevance, correct explanations, semantic entailment or owner acceptance.
