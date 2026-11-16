# Model servability tracking (TASK-REL-049)

**What this is:** the per-MODEL availability overlay for Inference's
routing layer, built on the measured evidence of TASK-INF-005. It
records whether each catalogue model actually *serves* when attempted,
quarantines a model that has stopped serving, probes it back on an
interval, and discloses the state in the routing metadata (response
provenance) instead of letting selection repeat a dead pick silently.

## The gap it closes (measured, TASK-INF-005, 2026-11-15)

- gemini-3.8-flash served **0 of 20 requests** across a full day on the
  production gateway (15/15 substituted in the main window, 5/5 in a
  second window hours later), each substitution costing a ~10–75s
  cascade (as-requested median ≈ 40.7s).
- The Gemini *provider* was healthy throughout — gemini-3.6-flash
  served 17 calls. The failure is at model level.
- TASK-REL-043's best-suitable selection filters availability by
  provider (`_provider_available` → `ProviderHealthTracker`), so the
  never-serving model kept its #1 chat ranking and every request paid
  the cascade again. TASK-REL-044's live acceptance hit the same wall
  from FRIDAY's side: a synthesis escalation naming gemini-3.8-flash
  received an Inference 503.
- **Still live on delivery day (2026-11-15):** the production journal
  shows the same shape hours later — repeated `Provider 'gemini' timed
  out after 36.0s (TimeoutError, model=gemini-3.8-flash). Escalating to
  the fallback ladder` warnings (e.g. 16:10–16:30 IST) and a
  `503 high demand; failing over to gemini-3.6-flash` line. The
  journal carries no structured served-model field at all (2,864 lines
  today, zero `served_by_model`/`model_used` entries) — per-model
  evidence exists only as unstructured ladder warnings that nothing
  aggregates, which is the observability gap this tracker closes at
  the layer where selection decisions are made.

## How the gateway learned outcomes before this task (the map)

Every outcome recorder in the gateway is provider-granular:

| Recorder | Key | Fed from |
|---|---|---|
| `app/providers/health.py` `ProviderHealthTracker.record_success/record_failure` | provider name | `app/providers/gateway.py` per-attempt (litellm + per-provider rungs) |
| `app/governance/circuit_breaker.py` | provider | governance layer |
| `app/optimization.py` provider stats | provider name | optimisation layer |
| `KeyPool.quarantine` (`app/providers/gateway.py`) | API key | 429/503 per key |

Per-model outcomes existed only transiently: `UnifiedExecutionResponse`
(`model_used`, `provider_used`, `degraded`, `fallback_reason`) at the
route layer, and the per-response `provenance` block. **Nothing
aggregated them** — there was no per-model serve/substitute/fail record
anywhere in the codebase (verified by search: no model-keyed stats,
health, or servability structure), which is why INF-005 had to measure
the failure from outside, from response bodies. This tracker is the
missing aggregation, fed from exactly those route-layer outcomes.

## The declared rule

Implemented in `app/providers/model_servability.py`
(`ModelServabilityTracker`, singleton `model_servability_tracker`,
the model-level counterpart of `provider_health_tracker`).

- **Outcomes** recorded per model at the non-streaming route, from the
  unified result: `served` (attempted model produced the answer),
  `substituted` (the ladder served a different model — the serving
  model is credited with a serve), `failed` (degraded result).
- **Quarantine:** **10 consecutive non-serves** (substituted or failed,
  no intervening serve). Justification: each attempt is a full,
  deadline-bound gateway execution, not a cheap ping; INF-005's model
  produced 15 in a row in one window and 20 across the day; ordinary
  flakiness cannot produce the streak because any single serve resets
  it. No time-span floor is imposed — the streak is the evidence, and
  probe-back bounds the cost of a wrong latch.
- **Probe-back:** while quarantined, a model becomes probe-eligible
  every **900s**. Selection keeps a probe-due model at its natural rank
  (half-open); one request tries it. A serve clears the quarantine
  immediately; a miss re-arms the probe clock.
- **Never a refusal:** if the overlay would empty the candidate list,
  selection returns the unfiltered pool — the same discipline as
  REL-043's provider-health filter.
- **Not a quality judgement:** `MODEL_SUITABILITY` and `MODEL_CLASSES`
  are untouched. A quarantined model keeps its REL-043 rank and
  resumes it on its next serve.
- Tuning knobs (env): `INFERENCE_MODEL_QUARANTINE_MIN_MISSES` (10),
  `INFERENCE_MODEL_QUARANTINE_WINDOW_S` (21600 — the reporting window
  for attempts/serves counts), `INFERENCE_MODEL_PROBE_INTERVAL_S`
  (900).

## Where it acts

`app/api/v1_core_routes.py`:

- `_ranked_suitable_models` applies the overlay after provider-health
  filtering (quarantined dropped, probe-due kept at rank).
- `_select_best_suitable` adds to its selection record: `servability`
  (the chosen model's state), `quarantined_alternates` (ranked models
  skipped under quarantine, with counts), `probe` (chosen model is a
  half-open trial).
- `chat_completions`:
  - a request naming a quarantined catalogue model (probe not due) is
    redirected through best-suitable selection instead of being
    executed into the cascade; the selection record gains
    `redirected_from_quarantined`;
  - every execution outcome (first attempt and the bounded REL-043
    retry) is recorded via `_record_attempt_outcome`;
  - responses carry `provenance.servability` =
    `{chosen, quarantined_alternates, probe[, redirected_from_quarantined]}`
    whenever a selection occurred.
- The `auto` path records serve observations for the serving catalogue
  model only (delegating the choice is its contract; there is no named
  model to score an attempt against).

## Recording guards and limits (stated, not hidden)

- **Cache replays record nothing.** A non-degraded result with
  prompt_tokens = 0 and completion_tokens = 0 is INF-005 finding 4's
  L1-replay signature — no live attempt happened, so no outcome is
  attributable. (TASK-INF-006's SafeResponseCache rework may change
  replay behaviour; the guard stays correct either way — it only
  *under*-records, which can delay a quarantine, never fabricate one.)
- **Streaming is not fed.** The chunk protocol never reveals which
  model actually served, so stream outcomes are not recorded; the
  overlay still *applies* to stream model selection. The measured
  failure mode (chat/escalation traffic) is non-streaming.
- **In-process state.** Like the provider health tracker, a restart
  clears the tracker; 10 fresh consecutive non-serves re-latch.
- **Flaky ≠ unservable.** A model serving intermittently never
  quarantines; per-attempt recovery remains the job of provider health
  and the bounded retry.

## Interaction with TASK-REL-044 (FRIDAY tiered routing)

REL-044 is FRIDAY-side and is not modified. Its synthesis escalation
names gemini-3.8-flash: while that model is quarantined, Inference now
answers with the best suitable available model and
`provenance.servability.redirected_from_quarantined` explaining why,
instead of the 503 REL-044's acceptance run observed. FRIDAY's
fall-back-to-own-pool behaviour is unchanged and now triggers only on
genuine gateway failure.

## Verification

`Inference/tests/test_rel049_model_servability.py`: tracker unit tests
(streak latch, serve resets, probe cycle, window pruning), route tests
(quarantined pick skipped + disclosed; same-provider sibling
unaffected; named-model redirect; probe re-entry; all-quarantined
still serves; live-route outcomes latch quarantine and stop the
cascade), and a replay of INF-005's recorded day
(`tests/fixtures/inf005_replay.json`) proving gemini-3.8-flash would
have been quarantined at its 10th consecutive non-serve — and no other
model at all.
