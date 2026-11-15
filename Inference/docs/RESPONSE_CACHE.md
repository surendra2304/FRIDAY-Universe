# Safe Response Cache (TASK-INF-006)

Module: `app/inference_runtime/response_cache.py` — `SafeResponseCache`.
Wired into: `HardenedGateway` (all completions) and
`UnifiedProviderManager` (the unified execution path). Measurement:
`scripts/replay_response_cache.py`.

## Why

Inference had two caches and neither enforced the rule that matters:
**a personalised or contextual answer must never be served to the wrong
context.**

- `TenantCache` keyed by tenant only, one flat TTL, no context binding.
- `MultiLevelCache` (`app/performance_cache.py`) stores every answer
  under shared keys (any mode, any caller) and a punctuation-stripped
  key. Within a namespace, an answer produced under one caller's context
  can be served to another caller whose recorded `extra` matches, and
  distinct questions can collide after punctuation stripping.

`perf_cache` still serves the friday/agent/instant routes, whose
producers pass explicit context scopes; migrating those call sites onto
`SafeResponseCache` classes is the recommended follow-up. The unified
path — the one that mixes arbitrary caller contexts — now runs on the
safe cache, as does the runtime gateway.

## Rules

Every request is classified; a declared class is a floor and automatic
signals can only raise it:

| Class | When | Key binding | Default TTL | Stored? |
|---|---|---|---|---|
| `public` | no context, no principal, no first-person markers | request fingerprint only (shareable) | 3600s | yes |
| `contextual` | context supplied, or first-person markers in the prompt | + SHA-256 context fingerprint | 300s | yes |
| `personalised` | principal id present (argument or `user_id`/`session_id`/`conversation_id`/... in context) | + principal fingerprint | 60s | **no** (default) |

Personalised storage can be enabled (`INFERENCE_RESP_CACHE_ALLOW_PERSONALISED=true`),
but entries stay bound to the principal fingerprint and the shortest
TTL; `invalidate_principal()` deletes a principal's entries (logout /
erasure). A personalised entry can never be served to a different
principal because the lookup key itself differs.

**Exact match** — canonical fingerprint of model, messages/prompt,
sampling parameters, response schema, capabilities and extra, plus the
class binding above.

**Task-template match** — only for templates registered in advance
(`TemplateSpec`) with declared *invariant slots* (values that do not
affect the answer, e.g. a request id). The template key covers template
id + version and every non-invariant slot. Unregistered prompts never
template-match; templates never serve personalised requests. This
replaces punctuation-stripping with declared semantics.

**Stochastic requests** (temperature > 0 or top_p < 1) replay only by
exact match within the identical context fingerprint, TTL capped at
`INFERENCE_RESP_CACHE_STOCHASTIC_TTL_CAP` (300s), and never
template-match.

**Invalidation** — generation counters per namespace and per template
are embedded in every key, so `invalidate_namespace()` /
`invalidate_template()` orphan entries in O(1).
`invalidate_context(fingerprint)` and `invalidate_principal(id)` delete
by scan (the store is LRU-bounded, default 1024 entries).
`policy_version` (`INFERENCE_RESP_CACHE_POLICY_VERSION`) is embedded in
every key: bump it when the model catalogue or routing policy changes
and the whole cache orphans.

Only successful, schema-valid responses are stored (the gateway
validates before storing and re-validates on every hit, evicting
malformed entries). Errors and degraded responses are never cached.

## Configuration

`INFERENCE_RESP_CACHE_PUBLIC_TTL` (3600), `..._CONTEXTUAL_TTL` (300),
`..._PERSONALISED_TTL` (60), `..._TEMPLATE_TTL` (900),
`..._STOCHASTIC_TTL_CAP` (300), `..._MAX_ENTRIES` (1024),
`..._POLICY_VERSION` ("1"), `..._ALLOW_PERSONALISED` (false).

## Measurement

`scripts/replay_response_cache.py` replays a JSONL request log (format
in its docstring) through the cache in stream time and reports hit-rate,
latency saved, and a safety audit (personalised hits and
cross-principal violations — both must be zero). `--generate-sample`
writes the deterministic synthetic sample log built from the fleet's
caller request shapes; replay a real exported log for production
figures.
