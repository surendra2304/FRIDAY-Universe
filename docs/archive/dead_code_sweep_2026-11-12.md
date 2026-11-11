# Dead-Code Sweep Report — Checklist I6

**Date:** 2026-11-12 (batch 9b, ZAI Agent 1)
**Method:** `scripts/dead_module_scan.py` (repo-wide importer analysis, including
relative imports, test imports, dynamic string references in code/config/docs) +
manual triage of every candidate + vulture high-confidence pass.
**Scope:** 1,065 package files across the nine agent packages.

## Removed (24 files — verified dead: no importer incl. tests, no registration, no doc/config reference)

### Inference `inference_runtime` — 14 unwired duplicates of live gateway modules
Each duplicated a capability the HardenedGateway already has via a wired module:

| Removed | Live counterpart (wired) |
|---|---|
| `autoscale.py` (AutoscalePlanner) | n/a — replica scaling not applicable to the single-process gateway |
| `cache_policy.py` (CachePolicy) | `cache.py` (TenantCache) |
| `circuit_pool.py` (CircuitPool) | `circuit.py` (CircuitBreaker) |
| `circuit_retry.py` (ProviderState) | `retry.py` + `circuit.py` |
| `completion_cache_key.py` | `cache.py` key logic |
| `configuration_snapshot.py` | `config.py` (RuntimeConfig) |
| `endpoint_health.py` (EndpointHealth) | `health.py` (ProviderHealth) |
| `health_decay.py` (HealthDecay) | `health.py` |
| `health_service.py` (HealthService) | `health.py` + `health_probe.py` |
| `load_shedding.py` (LoadShedder) | `admission.py` + `backpressure.py` |
| `openai_errors.py` (APIError) | `errors.py` |
| `providers_registry.py` (TransportRegistry) | `config.py` |
| `request_limits.py` (RequestLimits) | `admission.py` + `rate_limit.py` |
| `request_normalizer.py` (RequestNormalizer) | `contracts.py` (CompletionRequest) |

### Stratex — 10 legacy orphans
- `api/real_root_engines_routes.py` — Flask blueprint **never registered** in
  `dashboard.py`'s blueprint list (dead since the original monorepo init)
- `paper_engine/pairs_simulator.py` — no importer anywhere (the paper engine's
  live path is `simulator.py`)
- `update_cloud_env.py` — superseded ops script; zero references
- `stratex_upgrade/adapters/{hummingbot,nautilus,vectorbt}_ideas.py` — design-note
  adapters never loaded by anything (the live adapters `freqtrade_ideas` /
  `quantconnect_ideas` are test-covered and untouched)
- `research_phase6/risk_filters.py`, `research_phase7/research_signal_engine.py`,
  `research_phase9/{maker_simulator,paper_trading_engine}.py` — legacy
  pre-restructure research orphans; the registry's evidence lives in
  `optimization_results/` artifacts, not in these modules

## Kept (verified alive — scanner false-positives or policy keeps)

- `inference_runtime/model_policy.py`, `paper_engine/funding_simulator.py`,
  `research/regime_classifier.py` — imported by test suites (alive)
- `research_phase*/phase*_runner.py`, `VyralX channel_watcher.py` /
  `viral_repurposer.py`, `Stratex/scripts/update_cloud_demo_env.py` — manual
  `__main__` entrypoints (runnable ops/research tools; policy: keep)
- All `__init__.py` package markers

## Verification (0 new failures)

- Inference affected suites (`test_hardened_gateway`, `test_hardened_runtime_resources`,
  `test_gateway_fallback_key_rotation`, `test_health_security`): **61 errors
  before AND after removals — identical** (all the known sandbox
  `DatabaseConfigurationError: no Oracle database` pre-existing class, also
  fails identically on the clean tree)
- Stratex affected suites (`test_deep_upgrade_adapters`, `test_nautilus_simulator_hardening`,
  `test_paper_lifecycle`, `test_research_leakage_and_causality`): **40/40 passed**
- CI's seven engine suites (coverage baseline run): **194 passed**
- `vulture --min-confidence 90` on friday_core: only 4 trivial findings, all
  inside live modules (left as-is; too minor to churn core files)

## Result

Dead-module candidates: 35 → 11 (all remaining are documented keeps above).
Re-run anytime: `python3 scripts/dead_module_scan.py`
