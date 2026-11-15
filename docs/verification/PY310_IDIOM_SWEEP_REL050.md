# Python 3.11+/3.12 idiom sweep — TASK-REL-050

Production runs **Python 3.10.12** (verified read-only on Server 1 by
TASK-REL-048); development and CI run 3.11/3.12. This sweep finds every
construct on `main` (at e102db0a) that needs a newer interpreter, fixes
the import-time ones with behaviour-identical compatibility forms, and
adds a CI gate (`scripts/check_py310_imports.py`, workflow
`py310-import-gate.yml`) so the drift cannot silently return.

## Headline

- **248 import-time hits fixed** (216 × `from datetime import UTC`,
  32 × `from enum import StrEnum`) in **231 application files** across
  5 agents: Cortex 74, Sentinel 66, Futuris 56, IntelX 29, Forge 23.
- Entrypoint imports under a clean Python 3.10.15 venv with the
  production-pinned dependency set, using the exact production
  entrypoints from `deploy/setup_fleet.sh`:

  | Agent | Before | After |
  |---|---|---|
  | Inference | PASS | PASS |
  | Memora | PASS | PASS |
  | Stratex | PASS | PASS |
  | Futuris | FAIL — `cannot import name 'UTC'` (futuris/api/app.py:7) | PASS |
  | IntelX | FAIL — UTC (intelx/core/auth.py:10) | PASS |
  | Forge | FAIL — UTC (app/execution/delivery.py chain) | PASS |
  | Sentinel | FAIL — UTC (sentinel/apps/api/main.py:12) | PASS |
  | Cortex | FAIL — UTC (cortex_api/main.py:18) | PASS |
  | VyralX | blocked at import-time DB DDL (see note) | PASS (dev/test config) |
  | FRIDAY | PASS | PASS |

  VyralX note: `app/main.py` executes `Base.metadata.create_all` at
  import time, and outside `APP_ENV=development` its settings require a
  real Oracle URL — so it is import-tested in its own documented
  development/test configuration (throwaway SQLite file), the same
  configuration its unit-test suite uses. The import graph exercised
  is identical. This is an import-test affordance only; SQLite is not
  a production backend for any agent.
- 178 of the 231 fixed files are in today's entrypoint import graphs;
  the other 53 were fixed with the same mechanical transform because
  they are the identical latent defect one wiring-change away from a
  boot path. After the fix, a re-scan finds **zero** unguarded
  app-scope import-time hits, and all 4,290 agent sources compile
  under Python 3.10.
- The gate FAILS on the pre-fix tree naming Futuris, IntelX, Forge,
  Sentinel and Cortex; it refuses to run under a non-3.10 interpreter.

## Method

Three independent nets over all 4,290 `.py` files in the ten agent
directories (plus `mesh/`, `scripts/`, `bridge/`, `tools/`, `deploy/`):

1. An AST scanner (run under 3.12) for: `datetime.UTC` imports,
   `enum.StrEnum`, `tomllib`, `typing.Self`/`Never`/`LiteralString`,
   `except*`, type-alias statements, `itertools.batched`,
   `asyncio.timeout`/`TaskGroup`, `ExceptionGroup`, `pathlib`
   `walk`/`glob(match_case)`, `os` additions, `dataclass(slots=True)`.
   Files are decoded as UTF-8-SIG — three repo files carry a BOM, and
   a first pass that decoded plain UTF-8 silently skipped them; one
   (Sentinel's storage `models.py`) held a real UTC import. Regex
   cross-checks confirmed scanner recall for the zero-hit constructs.
2. A `compile()` pass over every file's bytes under Python 3.10.15:
   **0 syntax failures** — no `except*`, no type aliases, no 3.12
   f-string constructs anywhere in the fleet.
3. The entrypoint import harness (above), before and after the fix.

Not covered by the sweep (stated plainly): constructs named by
strings (`getattr(x, 'UTC')`, dynamic `__import__`), regex-only
3.11 syntax inside string literals, and annotations evaluated only
via `typing.get_type_hints` at runtime. No instance of the first two
was found by the regex cross-checks.

### A construct that is NOT a defect

`dataclass(slots=True)` appears 178 times and is flagged by many
checklists as 3.10+ — it was **added in Python 3.10**, and this was
verified empirically on the 3.10.15 venv (definition + instantiation
+ `__slots__` present). It is excluded from the fix scope.

### Already safe (try-guarded, not defects)

- `Inference/app/health.py:7` — from datetime import UTC inside `try/except ImportError`.
- `Inference/app/monitoring.py:8` — from datetime import UTC inside `try/except ImportError`.

## Fixes applied (behaviour-identical)

- `from datetime import UTC` → `timezone` added to the same import
  statement and `UTC = timezone.utc` bound at module level.
  (`datetime.UTC` *is* `timezone.utc` — the same singleton object;
  verified `datetime.UTC is timezone.utc` on 3.12.) The name must
  come from the same statement: an earlier draft of this fix relied
  on a `timezone` import elsewhere in the file and broke
  `Cortex/packages/integrations/__init__.py`, whose second import
  executed later — the import harness caught it, the transform was
  corrected, and every file was re-fixed from pristine sources.
- `from enum import StrEnum` → the import is wrapped in
  `try/except ImportError`; on 3.10 a local `class StrEnum(str, Enum)`
  is defined with `__str__`/`__format__` bound to `str`'s and
  `_generate_next_value_` returning the lowercased member name —
  CPython 3.11's exact semantics. On 3.11+ the real class is used.
  Equivalence was checked on both interpreters (member values,
  `str()`, f-strings, `==` with plain strings, JSON serialisation):
  identical outputs on 3.10-with-fallback, 3.12-fixed and
  3.12-original. No fleet StrEnum uses `auto()`; the override
  covers it anyway.

## Residuals (documented, not fixed)

### R1 — `asyncio.timeout` (3.11+), runtime-only, 3 sites

The 3.10 conversion (`asyncio.wait_for`) is **not** behaviour-
identical: on 3.10 `asyncio.TimeoutError` is a different class from
the builtin `TimeoutError` that two of these sites catch, and the
multi-statement bodies would need restructuring into coroutines.
Per the task rule (fix only if trivial and identical) they are
inventoried here with exact trigger paths:

- `Inference/app/main.py:153` — lifespan **shutdown** path (after
  `yield`): wraps watchdog cancellation + HTTP pool close in a 5s
  timeout. Trigger: every Inference shutdown/restart of a build
  containing this code. On 3.10 the shutdown sequence raises
  `AttributeError: module 'asyncio' has no attribute 'timeout'`.
- `IntelX/intelx/app/lifespan.py:192` — lifespan **shutdown** path:
  wraps hook stops + engine disposal in a 5s timeout, inside
  `except (TimeoutError, Exception)` — the broad catch means on 3.10
  the hooks are skipped but shutdown completes via the fallback
  `dispose_engine()`. Degraded, not fatal.
- `IntelX/intelx/orchestration/worker.py:125` — `Worker.drain()`:
  catches only `TimeoutError`, so on 3.10 `drain()` raises
  `AttributeError` when called with a job in flight. (The embedded
  worker is gated off in production today — TASK-INT-010.)

### R2 — test-scope import-time hits (141 in 137 files + 1 at repo root)

139 × `from datetime import UTC` and 2 × `import tomllib` in test
files, plus `tests/test_gitleaks_config.py:59` (`import tomllib`) at
repo root. Production never imports tests; these break only if the
suites are run under Python 3.10 (repo CI runs 3.11+). Full list:

- `Cortex/scripts/operator_gauntlet_live_test.py` — from datetime import UTC L21
- `Cortex/scripts/operator_load_live_test.py` — from datetime import UTC L24
- `Cortex/scripts/pressure_test.py` — from datetime import UTC L41
- `Cortex/scripts/run_e2e_system_test.py` — from datetime import UTC L22
- `Cortex/tests/integration/test_full_cognitive_loop.py` — from datetime import UTC L3
- `Cortex/tests/integration/test_peer_integration_contract.py` — from datetime import UTC L438
- `Cortex/tests/integration/test_privacy_flow.py` — from datetime import UTC L14
- `Cortex/tests/test_prompt9_cortex.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_advanced_analytics.py` — from datetime import UTC L3
- `Cortex/tests/unit/test_advanced_operations_api_v2.py` — from datetime import UTC L14
- `Cortex/tests/unit/test_advanced_operations_api_v3.py` — from datetime import UTC L16
- `Cortex/tests/unit/test_advanced_operations_api_v4.py` — from datetime import UTC L25
- `Cortex/tests/unit/test_advanced_operations_router.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_attribution_engine.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_auth_and_rbac.py` — from datetime import UTC L111
- `Cortex/tests/unit/test_behavioral_churn_and_rfm.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_core_and_api.py` — from datetime import UTC L3
- `Cortex/tests/unit/test_datetime_discipline.py` — from datetime import UTC L12
- `Cortex/tests/unit/test_event_deduplication_and_priority.py` — from datetime import UTC L6
- `Cortex/tests/unit/test_events_and_webhooks.py` — from datetime import UTC L3
- `Cortex/tests/unit/test_friday_integration.py` — from datetime import UTC L25
- `Cortex/tests/unit/test_friday_universe_funnels.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_friday_universe_live_telemetry.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_identity_cross_session_journey.py` — from datetime import UTC L4
- `Cortex/tests/unit/test_identity_service.py` — from datetime import UTC L3
- `Cortex/tests/unit/test_ingestion_security.py` — from datetime import UTC L12, from datetime import UTC L326
- `Cortex/tests/unit/test_no_fabricated_data.py` — from datetime import UTC L30
- `Cortex/tests/unit/test_orchestrator_and_agents.py` — from datetime import UTC L3
- `Cortex/tests/unit/test_orchestrator_collaboration.py` — from datetime import UTC L12
- `Cortex/tests/unit/test_privacy_and_compliance.py` — from datetime import UTC L23
- `Cortex/tests/unit/test_public_gateway.py` — from datetime import UTC L3
- `Cortex/tests/unit/test_realtime_streaming.py` — from datetime import UTC L3
- `Cortex/tests/unit/test_sankey_paths_and_retention.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_sse_live_streaming.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_telemetry_anomaly_detector.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_telemetry_persistence_and_sessions.py` — from datetime import UTC L4
- `Cortex/tests/unit/test_tenant_isolation_mutations.py` — from datetime import UTC L4
- `Cortex/tests/unit/test_tenant_isolation_reads.py` — from datetime import UTC L14
- `Cortex/tests/unit/test_traffic_telemetry.py` — from datetime import UTC L9
- `Cortex/tests/unit/test_webhook_dispatcher.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_websocket_auth.py` — from datetime import UTC L5
- `Cortex/tests/unit/test_worker_orchestrator.py` — from datetime import UTC L4
- `Cortex/tests/upgrade/test_events.py` — from datetime import UTC L2
- `Forge/tests/unit/test_delegate_mode_truthfulness.py` — from datetime import UTC L25
- `Forge/tests/unit/test_delegate_schedules_execution.py` — from datetime import UTC L12
- `Forge/tests/unit/test_task_id_naming.py` — from datetime import UTC L5
- `Forge/tests/unit/test_telemetry_and_progress_wiring.py` — from datetime import UTC L15
- `Futuris/scripts/e2e_system_test.py` — from datetime import UTC L5
- `Futuris/tests/api/test_api_integration.py` — from datetime import UTC L4
- `Futuris/tests/api/test_demo_seed_guard.py` — from datetime import UTC L17
- `Futuris/tests/api/test_governance.py` — from datetime import UTC L6
- `Futuris/tests/api/test_hostile_inputs.py` — from datetime import UTC L12
- `Futuris/tests/api/test_live_fire_regressions.py` — from datetime import UTC L37
- `Futuris/tests/api/test_provenance_ui_gate.py` — from datetime import UTC L4
- `Futuris/tests/api/test_risk_endpoints.py` — from datetime import UTC L4
- `Futuris/tests/api/test_round2_hardening.py` — from datetime import UTC L24
- `Futuris/tests/api/test_session_teardown.py` — from datetime import UTC L22
- `Futuris/tests/api/test_streaming.py` — from datetime import UTC L4
- `Futuris/tests/connectors/test_provenance.py` — from datetime import UTC L9
- `Futuris/tests/connectors/test_synthetic_telemetry.py` — from datetime import UTC L3
- `Futuris/tests/connectors/test_trading_bot_ticker.py` — from datetime import UTC L3
- `Futuris/tests/connectors/test_vyralx_connector.py` — from datetime import UTC L4
- `Futuris/tests/core/test_provenance.py` — from datetime import UTC L8
- `Futuris/tests/core/test_schemas.py` — from datetime import UTC L3
- `Futuris/tests/ecosystem/test_signal_dispatch.py` — from datetime import UTC L3
- `Futuris/tests/evaluation/test_evaluation.py` — from datetime import UTC L3
- `Futuris/tests/evidence/test_snapshots.py` — from datetime import UTC L3
- `Futuris/tests/features/test_features.py` — from datetime import UTC L3
- `Futuris/tests/infra/test_scheduler_targets.py` — from datetime import UTC L42
- `Futuris/tests/infra/test_webhook_delivery.py` — from datetime import UTC L6
- `Futuris/tests/integration/test_multi_agent.py` — from datetime import UTC L18
- `Futuris/tests/integrations/test_memora_forecast_publisher.py` — from datetime import UTC L6
- `Futuris/tests/models/test_engine.py` — from datetime import UTC L3
- `Futuris/tests/models/test_statsforecast_degradation.py` — from datetime import UTC L11
- `Futuris/tests/scenarios/test_fanchart_api.py` — from datetime import UTC L4
- `Futuris/tests/storage/test_fk_flush_order.py` — from datetime import UTC L22
- `Futuris/tests/storage/test_postgres_crud.py` — from datetime import UTC L4
- `Futuris/tests/storage/test_provenance_persistence.py` — from datetime import UTC L19
- `Futuris/tests/storage/test_repositories.py` — from datetime import UTC L5
- `Futuris/tests/test_agents.py` — from datetime import UTC L3
- `Futuris/tests/test_calibration_sweep.py` — from datetime import UTC L4
- `Futuris/tests/test_drivers_and_decisions.py` — from datetime import UTC L4
- `Futuris/tests/test_forge_forecasting.py` — from datetime import UTC L3
- `Futuris/tests/test_friday_delegation.py` — from datetime import UTC L135
- `Futuris/tests/test_fut002_hardening.py` — from datetime import UTC L28
- `Futuris/tests/test_fut003_oracle_json_reads.py` — from datetime import UTC L31
- `Futuris/tests/test_governance_and_security.py` — from datetime import UTC L3
- `Futuris/tests/test_integrations.py` — from datetime import UTC L3
- `Futuris/tests/test_intelx_and_enhancements.py` — from datetime import UTC L3
- `Futuris/tests/test_memora_cloud_auth.py` — from datetime import UTC L2
- `Futuris/tests/test_memora_event_consumer.py` — from datetime import UTC L306, from datetime import UTC L362
- `Futuris/tests/test_prompt7_futuris.py` — from datetime import UTC L22
- `Futuris/tests/test_scenarios.py` — from datetime import UTC L3
- `Futuris/tests/test_scheduler_and_pipeline.py` — from datetime import UTC L3
- `Futuris/tests/test_trading_bot_forecasting.py` — from datetime import UTC L3
- `Futuris/tests/test_trading_bot_no_fallback.py` — from datetime import UTC L3
- `Futuris/tests/test_universe_refresh_pacing.py` — from datetime import UTC L20
- `Futuris/tests/upgrade/test_auth.py` — from datetime import UTC L2
- `Futuris/tests/upgrade/test_compat.py` — from datetime import UTC L2
- `Futuris/tests/upgrade/test_forecast_guard.py` — from datetime import UTC L2
- `Futuris/tests/upgrade/test_state.py` — from datetime import UTC L3
- `IntelX/tests/test_agents.py` — from datetime import UTC L41
- `IntelX/tests/test_api_router_coverage.py` — from datetime import UTC L3
- `IntelX/tests/test_api_v1_endpoints.py` — from datetime import UTC L4
- `IntelX/tests/test_artifacts.py` — from datetime import UTC L92, from datetime import UTC L147, from datetime import UTC L180
- `IntelX/tests/test_autonomous_researcher.py` — from datetime import UTC L4
- `IntelX/tests/test_cortex_api.py` — from datetime import UTC L4
- `IntelX/tests/test_ecosystem_collaboration.py` — from datetime import UTC L3
- `IntelX/tests/test_friday_api.py` — from datetime import UTC L4
- `IntelX/tests/test_friday_universe_api.py` — from datetime import UTC L4
- `IntelX/tests/test_futuris_context.py` — from datetime import UTC L3
- `IntelX/tests/test_mesh_receipt_contract.py` — from datetime import UTC L17
- `IntelX/tests/test_news_ingester.py` — from datetime import UTC L4
- `IntelX/tests/test_news_memora_broadcast.py` — from datetime import UTC L2
- `IntelX/tests/test_rel038_intelx_honesty_persistence.py` — from datetime import UTC L258
- `IntelX/tests/test_retention.py` — from datetime import UTC L1
- `IntelX/tests/test_stratex_api.py` — from datetime import UTC L4
- `IntelX/tests/test_trust.py` — from datetime import UTC L3
- `Memora/tests/test_deployment_packaging.py` — import tomllib L3
- `Sentinel/tests/integration/test_gateway_integration.py` — from datetime import UTC L2
- `Sentinel/tests/integration/test_runtime_database_wiring.py` — from datetime import UTC L9
- `Sentinel/tests/integration/test_task_submission_e2e.py` — from datetime import UTC L12
- `Sentinel/tests/security/test_explicit_scope_and_api_auth.py` — from datetime import UTC L3
- `Sentinel/tests/security/test_friday_explicit_scope.py` — from datetime import UTC L3
- `Sentinel/tests/security/test_scope_enforcement_regressions.py` — from datetime import UTC L5
- `Sentinel/tests/security/test_vyralx_publish_policy.py` — from datetime import UTC L4
- `Sentinel/tests/test_prompt5_sentinel.py` — from datetime import UTC L20
- `Sentinel/tests/unit/test_agent_coordination.py` — from datetime import UTC L3
- `Sentinel/tests/unit/test_evidence_and_orchestrator_deep.py` — from datetime import UTC L12
- `Sentinel/tests/unit/test_friday_enhancements.py` — from datetime import UTC L18
- `Sentinel/tests/unit/test_friday_integration.py` — from datetime import UTC L1
- `Sentinel/tests/unit/test_policy_and_scope_adversarial.py` — from datetime import UTC L8
- `Sentinel/tests/unit/test_policy_engine.py` — from datetime import UTC L1
- `Sentinel/tests/unit/test_scale_chaos_and_compliance.py` — from datetime import UTC L13
- `Sentinel/tests/unit/test_task_checkpoints.py` — from datetime import UTC L4
- `Sentinel/tests/unit/test_tls_dns_daemon.py` — from datetime import UTC L5
- `VyralX/tests/test_build_reproducibility.py` — import tomllib L6
- `tests/test_gitleaks_config.py` — import tomllib L59

### R3 — code-generation template

`Sentinel/scripts/append_friday.py` embeds `from datetime import UTC`
inside a **string template** it appends to generated code. It is not
an import and was not changed; if the script is run, its output
carries the idiom and would need the same one-line fix.

## Fixed inventory (248 hits, 231 files)

### Futuris (56 hits)

- `Futuris/futuris/agents/protocol.py` — from datetime import UTC L4
- `Futuris/futuris/agents/runner.py` — from datetime import UTC L2
- `Futuris/futuris/api/app.py` — from datetime import UTC L7
- `Futuris/futuris/api/routers/ecosystem.py` — from datetime import UTC L3
- `Futuris/futuris/api/routers/forecasts.py` — from datetime import UTC L4
- `Futuris/futuris/api/routers/friday.py` — from datetime import UTC L4
- `Futuris/futuris/api/routers/market.py` — from datetime import UTC L3
- `Futuris/futuris/api/routers/predictions.py` — from datetime import UTC L4
- `Futuris/futuris/api/routers/risk.py` — from datetime import UTC L7
- `Futuris/futuris/api/routers/scenarios.py` — from datetime import UTC L3
- `Futuris/futuris/api/routers/streaming.py` — from datetime import UTC L8
- `Futuris/futuris/api/routers/webhooks.py` — from datetime import UTC L5
- `Futuris/futuris/cli.py` — from datetime import UTC L5
- `Futuris/futuris/connectors/forge.py` — from datetime import UTC L3
- `Futuris/futuris/connectors/intelx_context.py` — from datetime import UTC L3
- `Futuris/futuris/connectors/nexus.py` — from datetime import UTC L3
- `Futuris/futuris/connectors/synthetic_telemetry.py` — from datetime import UTC L4
- `Futuris/futuris/connectors/trading_bot.py` — from datetime import UTC L3
- `Futuris/futuris/connectors/vyralx.py` — from datetime import UTC L6
- `Futuris/futuris/core/decision.py` — from datetime import UTC L10
- `Futuris/futuris/core/engine.py` — from datetime import UTC L3
- `Futuris/futuris/core/enums.py` — from enum import StrEnum L3
- `Futuris/futuris/core/lifecycle.py` — from datetime import UTC L4
- `Futuris/futuris/core/pipeline.py` — from datetime import UTC L5
- `Futuris/futuris/core/resolution.py` — from datetime import UTC L4
- `Futuris/futuris/core/thresholds.py` — from datetime import UTC L4
- `Futuris/futuris/core/universe_domains.py` — from enum import StrEnum L4
- `Futuris/futuris/core/universe_forecasting.py` — from datetime import UTC L11
- `Futuris/futuris/demo/seed.py` — from datetime import UTC L3
- `Futuris/futuris/ecosystem/adapters.py` — from datetime import UTC L6
- `Futuris/futuris/ecosystem/signals.py` — from datetime import UTC L5
- `Futuris/futuris/evaluation/backtest.py` — from datetime import UTC L4
- `Futuris/futuris/evaluation/drift.py` — from datetime import UTC L4
- `Futuris/futuris/evidence/snapshots.py` — from datetime import UTC L7
- `Futuris/futuris/features/contextualize.py` — from datetime import UTC L3
- `Futuris/futuris/features/normalize.py` — from datetime import UTC L3
- `Futuris/futuris/infra/audit.py` — from datetime import UTC L5
- `Futuris/futuris/infra/circuit_breaker.py` — from enum import StrEnum L7
- `Futuris/futuris/infra/events.py` — from datetime import UTC L11
- `Futuris/futuris/infra/resilience.py` — from enum import StrEnum L21
- `Futuris/futuris/infra/scheduler.py` — from datetime import UTC L5
- `Futuris/futuris/infra/self_healing.py` — from datetime import UTC L18
- `Futuris/futuris/integrations/memora_forecast_publisher.py` — from datetime import UTC L10
- `Futuris/futuris/integrations/sentinel_schema.py` — from datetime import UTC L3
- `Futuris/futuris/models/regime.py` — from enum import StrEnum L4
- `Futuris/futuris/storage/models.py` — from datetime import UTC L3
- `Futuris/futuris/storage/repositories.py` — from datetime import UTC L3
- `Futuris/futuris/upgrade/auth.py` — from datetime import UTC L8
- `Futuris/futuris/upgrade/checkpoint.py` — from datetime import UTC L7
- `Futuris/futuris/upgrade/context_firewall.py` — from enum import StrEnum L5
- `Futuris/futuris/upgrade/forecast_guard.py` — from datetime import UTC L5
- `Futuris/futuris/upgrade/models.py` — from datetime import UTC L4, from enum import StrEnum L6
- `Futuris/futuris/upgrade/scheduler.py` — from datetime import UTC L6
- `Futuris/futuris/upgrade/state.py` — from datetime import UTC L5
- `Futuris/scripts/run_journey_advisory.py` — from datetime import UTC L19

### IntelX (29 hits)

- `IntelX/intelx/agents/claim_ledger.py` — from datetime import UTC L7
- `IntelX/intelx/agents/verifier.py` — from datetime import UTC L6
- `IntelX/intelx/api/router.py` — from datetime import UTC L4
- `IntelX/intelx/api/v1/endpoints.py` — from datetime import UTC L4
- `IntelX/intelx/api/v1/friday.py` — from datetime import UTC L12
- `IntelX/intelx/api/v1/futuris.py` — from datetime import UTC L3
- `IntelX/intelx/api/v1/health.py` — from datetime import UTC L2
- `IntelX/intelx/api/v1/subscriptions.py` — from datetime import UTC L5
- `IntelX/intelx/connectors/providers.py` — from enum import StrEnum L7
- `IntelX/intelx/core/auth.py` — from datetime import UTC L10
- `IntelX/intelx/core/budget.py` — from datetime import UTC L8
- `IntelX/intelx/core/enums.py` — from enum import StrEnum L3
- `IntelX/intelx/core/logging.py` — from datetime import UTC L7
- `IntelX/intelx/core/policy.py` — from datetime import UTC L4
- `IntelX/intelx/core/report.py` — from datetime import UTC L4
- `IntelX/intelx/core/retention.py` — from datetime import UTC L7
- `IntelX/intelx/db/demo_seeder.py` — from datetime import UTC L11
- `IntelX/intelx/db/models.py` — from datetime import UTC L4
- `IntelX/intelx/db/repos.py` — from datetime import UTC L5
- `IntelX/intelx/db/retention.py` — from datetime import UTC L5
- `IntelX/intelx/ingestion/news_ingester.py` — from datetime import UTC L24
- `IntelX/intelx/integrations/cortex_context.py` — from datetime import UTC L17
- `IntelX/intelx/integrations/futuris_context.py` — from datetime import UTC L14
- `IntelX/intelx/integrations/stratex_context.py` — from datetime import UTC L8
- `IntelX/intelx/memory/normalize.py` — from datetime import UTC L26
- `IntelX/intelx/orchestration/autonomous_researcher.py` — from datetime import UTC L17
- `IntelX/intelx/orchestration/engine.py` — from datetime import UTC L6
- `IntelX/intelx/web/routes.py` — from datetime import UTC L3
- `IntelX/intelx_upgrade/models.py` — from enum import StrEnum L7

### Forge (23 hits)

- `Forge/app/api/tasks.py` — from datetime import UTC L10
- `Forge/app/api/webhooks.py` — from datetime import UTC L8
- `Forge/app/backup/recovery.py` — from datetime import UTC L10
- `Forge/app/core/events.py` — from datetime import UTC L7
- `Forge/app/core/multi_project.py` — from datetime import UTC L8
- `Forge/app/core/progress_tracker.py` — from datetime import UTC L7
- `Forge/app/execution/delivery.py` — from datetime import UTC L7
- `Forge/app/execution/process_manager.py` — from datetime import UTC L8
- `Forge/app/improvement/models.py` — from datetime import UTC L5
- `Forge/app/improvement/research_templates.py` — from datetime import UTC L7
- `Forge/app/improvement/self_improve.py` — from datetime import UTC L8
- `Forge/app/integrations/futuris_client.py` — from datetime import UTC L12
- `Forge/app/integrations/intelx_client.py` — from datetime import UTC L9
- `Forge/app/integrations/memora_outbox.py` — from datetime import UTC L28
- `Forge/app/marketplace/models.py` — from datetime import UTC L5
- `Forge/app/memory/models.py` — from datetime import UTC L5
- `Forge/app/memory/state_store.py` — from datetime import UTC L11
- `Forge/app/monitoring/audit.py` — from datetime import UTC L6
- `Forge/app/planning/tree.py` — from datetime import UTC L7
- `Forge/app/verification/advanced_battery.py` — from datetime import UTC L8
- `Forge/app/verification/checkers.py` — from datetime import UTC L11
- `Forge/app/verification/evidence.py` — from datetime import UTC L6
- `Forge/app/verification/security_scanner.py` — from datetime import UTC L15

### Sentinel (66 hits)

- `Sentinel/sentinel/api/security_audit.py` — from datetime import UTC L16
- `Sentinel/sentinel/apps/api/main.py` — from datetime import UTC L12
- `Sentinel/sentinel/apps/cli/main.py` — from datetime import UTC L8
- `Sentinel/sentinel/audit/audit_logger.py` — from datetime import UTC L14
- `Sentinel/sentinel/config/settings.py` — from enum import StrEnum L10
- `Sentinel/sentinel/core/events/bus.py` — from datetime import UTC L13
- `Sentinel/sentinel/core/gateway/models.py` — from enum import StrEnum L11
- `Sentinel/sentinel/core/incident/incident_manager.py` — from enum import StrEnum L11
- `Sentinel/sentinel/core/incident/quarantine_manager.py` — from enum import StrEnum L11
- `Sentinel/sentinel/core/intelligence/interface.py` — from enum import StrEnum L8
- `Sentinel/sentinel/core/memory/knowledge_base.py` — from datetime import UTC L11, from enum import StrEnum L12
- `Sentinel/sentinel/core/models.py` — from datetime import UTC L9, from enum import StrEnum L10
- `Sentinel/sentinel/core/orchestrator/lifecycle.py` — from datetime import UTC L9
- `Sentinel/sentinel/core/orchestrator/orchestrator.py` — from datetime import UTC L15
- `Sentinel/sentinel/core/policy/engine.py` — from datetime import UTC L20, from enum import StrEnum L21
- `Sentinel/sentinel/core/resilience/circuit_breaker.py` — from enum import StrEnum L9
- `Sentinel/sentinel/core/review/gated_reviewer.py` — from datetime import UTC L17
- `Sentinel/sentinel/core/scope/authoritative_scope.py` — from datetime import UTC L10
- `Sentinel/sentinel/core/scope/resolver.py` — from datetime import UTC L12, from enum import StrEnum L13
- `Sentinel/sentinel/core/security/crypto_gatekeeper.py` — from datetime import UTC L16
- `Sentinel/sentinel/core/tenancy.py` — from datetime import UTC L9
- `Sentinel/sentinel/core/vault/vault.py` — from datetime import UTC L4
- `Sentinel/sentinel/gatekeeper/approval_dispatcher.py` — from datetime import UTC L25, from enum import StrEnum L26
- `Sentinel/sentinel/integrations/ecosystem/stratex_bridge.py` — from datetime import UTC L12
- `Sentinel/sentinel/integrations/friday/models.py` — from datetime import UTC L11, from enum import StrEnum L12
- `Sentinel/sentinel/integrations/futuris_client.py` — from datetime import UTC L9, from enum import StrEnum L10
- `Sentinel/sentinel/integrations/intelx_client.py` — from datetime import UTC L3
- `Sentinel/sentinel/integrations/threat_feeds/feeds.py` — from datetime import UTC L10
- `Sentinel/sentinel/intelligence/reporting/compliance.py` — from datetime import UTC L3
- `Sentinel/sentinel/intelligence/reporting/generator.py` — from datetime import UTC L17, from enum import StrEnum L18
- `Sentinel/sentinel/intelligence/risk/finding_engine.py` — from datetime import UTC L8
- `Sentinel/sentinel/logging/logger.py` — from datetime import UTC L9
- `Sentinel/sentinel/modules/endpoint/models.py` — from datetime import UTC L3, from enum import StrEnum L4
- `Sentinel/sentinel/modules/forensics/adapters.py` — from datetime import UTC L13
- `Sentinel/sentinel/modules/incident_response/adapters.py` — from datetime import UTC L11, from enum import StrEnum L12
- `Sentinel/sentinel/modules/operations/alerting.py` — from datetime import UTC L11, from enum import StrEnum L12
- `Sentinel/sentinel/modules/operations/baseline.py` — from datetime import UTC L8, from enum import StrEnum L9
- `Sentinel/sentinel/modules/operations/dashboard.py` — from datetime import UTC L11
- `Sentinel/sentinel/modules/operations/scheduler.py` — from datetime import UTC L10, from enum import StrEnum L11
- `Sentinel/sentinel/modules/recon/graph.py` — from datetime import UTC L9, from enum import StrEnum L10
- `Sentinel/sentinel/modules/threat_intel/models.py` — from datetime import UTC L3, from enum import StrEnum L4
- `Sentinel/sentinel/modules/vulnerability/github_advisories.py` — from datetime import UTC L15
- `Sentinel/sentinel/monitoring/continuous.py` — from datetime import UTC L14, from enum import StrEnum L15
- `Sentinel/sentinel/monitoring/dedup.py` — from datetime import UTC L10
- `Sentinel/sentinel/monitoring/docker_telemetry.py` — from datetime import UTC L18
- `Sentinel/sentinel/monitoring/tls_dns_daemon.py` — from datetime import UTC L16
- `Sentinel/sentinel/storage/database/models.py` — from datetime import UTC L15
- `Sentinel/sentinel/storage/evidence/store.py` — from datetime import UTC L9
- `Sentinel/sentinel/storage/repositories/in_memory.py` — from datetime import UTC L4
- `Sentinel/sentinel/storage/repositories/oracle.py` — from datetime import UTC L22

### Cortex (74 hits)

- `Cortex/apps/api/src/cortex_api/advanced_operations_router.py` — from datetime import UTC L13
- `Cortex/apps/api/src/cortex_api/api_keys.py` — from datetime import UTC L20
- `Cortex/apps/api/src/cortex_api/db_models.py` — from datetime import UTC L1
- `Cortex/apps/api/src/cortex_api/events_router.py` — from datetime import UTC L20
- `Cortex/apps/api/src/cortex_api/friday_router.py` — from datetime import UTC L43
- `Cortex/apps/api/src/cortex_api/main.py` — from datetime import UTC L18
- `Cortex/apps/api/src/cortex_api/production_router.py` — from datetime import UTC L7
- `Cortex/apps/api/src/cortex_api/public_gateway.py` — from datetime import UTC L4
- `Cortex/apps/api/src/cortex_api/streaming_router.py` — from datetime import UTC L5
- `Cortex/apps/api/src/cortex_api/stripe_webhook_router.py` — from datetime import UTC L28
- `Cortex/apps/api/src/cortex_api/traffic_telemetry.py` — from datetime import UTC L30
- `Cortex/apps/api/src/cortex_api/understand_router.py` — from datetime import UTC L18
- `Cortex/apps/api/src/cortex_api/webhooks_router.py` — from datetime import UTC L25
- `Cortex/apps/worker/src/cortex_worker/main.py` — from datetime import UTC L6
- `Cortex/cortex_upgrade/approval.py` — from datetime import UTC L8
- `Cortex/cortex_upgrade/audit.py` — from datetime import UTC L4
- `Cortex/cortex_upgrade/auth.py` — from datetime import UTC L8
- `Cortex/cortex_upgrade/dlq.py` — from datetime import UTC L16
- `Cortex/cortex_upgrade/event_ingestion.py` — from datetime import UTC L7
- `Cortex/cortex_upgrade/event_stream.py` — from datetime import UTC L15
- `Cortex/cortex_upgrade/learning.py` — from datetime import UTC L4
- `Cortex/cortex_upgrade/memory.py` — from datetime import UTC L6
- `Cortex/cortex_upgrade/models.py` — from datetime import UTC L4
- `Cortex/cortex_upgrade/runtime_knobs.py` — from datetime import UTC L13
- `Cortex/packages/agents/src/cortex_agents/__init__.py` — from datetime import UTC L2
- `Cortex/packages/agents/src/cortex_agents/collaboration.py` — from datetime import UTC L33
- `Cortex/packages/agents/src/cortex_agents/compliance_agent.py` — from datetime import UTC L13
- `Cortex/packages/agents/src/cortex_agents/cro_agent.py` — from datetime import UTC L13
- `Cortex/packages/agents/src/cortex_agents/mitigation_agent.py` — from datetime import UTC L12
- `Cortex/packages/agents/src/cortex_agents/revops_agent.py` — from datetime import UTC L12
- `Cortex/packages/ai_universe_adapter/src/cortex_ai_universe_adapter/__init__.py` — from datetime import UTC L6
- `Cortex/packages/analytics/src/cortex_analytics/__init__.py` — from datetime import UTC L11
- `Cortex/packages/analytics/src/cortex_analytics/anomaly_detector.py` — from datetime import UTC L15
- `Cortex/packages/analytics/src/cortex_analytics/attribution.py` — from datetime import UTC L17
- `Cortex/packages/analytics/src/cortex_analytics/experiments.py` — from datetime import UTC L4
- `Cortex/packages/analytics/src/cortex_analytics/funnels.py` — from datetime import UTC L14
- `Cortex/packages/analytics/src/cortex_analytics/nl_query.py` — from datetime import UTC L2
- `Cortex/packages/analytics/src/cortex_analytics/outcomes.py` — from datetime import UTC L3
- `Cortex/packages/analytics/src/cortex_analytics/sankey_paths.py` — from datetime import UTC L13
- `Cortex/packages/analytics/src/cortex_analytics/security_baseline.py` — from datetime import UTC L2
- `Cortex/packages/core/src/cortex_core/canary_controller.py` — from datetime import UTC L15
- `Cortex/packages/core/src/cortex_core/compliance_ledger.py` — from datetime import UTC L17
- `Cortex/packages/core/src/cortex_core/feature_flags.py` — from datetime import UTC L12
- `Cortex/packages/core/src/cortex_core/governed_operations.py` — from datetime import UTC L7
- `Cortex/packages/core/src/cortex_core/models/__init__.py` — from datetime import UTC L1
- `Cortex/packages/core/src/cortex_core/orchestrator.py` — from datetime import UTC L6
- `Cortex/packages/core/src/cortex_core/resilience.py` — from datetime import UTC L29
- `Cortex/packages/core/src/cortex_core/self_model.py` — from datetime import UTC L28
- `Cortex/packages/core/src/cortex_core/task_manager.py` — from datetime import UTC L5
- `Cortex/packages/core/src/cortex_core/web_property.py` — from datetime import UTC L6
- `Cortex/packages/event_schema/src/cortex_event_schema/__init__.py` — from datetime import UTC L1
- `Cortex/packages/identity/src/cortex_identity/graph_stitcher.py` — from datetime import UTC L15
- `Cortex/packages/identity/src/cortex_identity/service.py` — from datetime import UTC L3
- `Cortex/packages/integrations/src/cortex_integrations/__init__.py` — from datetime import UTC L4
- `Cortex/packages/integrations/src/cortex_integrations/connector_manager.py` — from datetime import UTC L6
- `Cortex/packages/integrations/src/cortex_integrations/deployment_gate.py` — from datetime import UTC L3
- `Cortex/packages/integrations/src/cortex_integrations/futuris_client.py` — from datetime import UTC L4
- `Cortex/packages/integrations/src/cortex_integrations/intelx_client.py` — from datetime import UTC L5
- `Cortex/packages/integrations/src/cortex_integrations/sentinel_client.py` — from datetime import UTC L27
- `Cortex/packages/integrations/src/cortex_integrations/sentinel_listener.py` — from datetime import UTC L3
- `Cortex/packages/integrations/src/cortex_integrations/sync_engine.py` — from datetime import UTC L19
- `Cortex/packages/integrations/src/cortex_integrations/webhook_dispatcher.py` — from datetime import UTC L18
- `Cortex/packages/intelligence/src/cortex_intelligence/__init__.py` — from datetime import UTC L1
- `Cortex/packages/intelligence/src/cortex_intelligence/audience_segments.py` — from datetime import UTC L13
- `Cortex/packages/intelligence/src/cortex_intelligence/bandit_allocator.py` — from datetime import UTC L17
- `Cortex/packages/intelligence/src/cortex_intelligence/behavioral_churn.py` — from datetime import UTC L12
- `Cortex/packages/memory/src/cortex_memory/__init__.py` — from datetime import UTC L3
- `Cortex/packages/policy_engine/src/cortex_policy_engine/__init__.py` — from datetime import UTC L4
- `Cortex/packages/policy_engine/src/cortex_policy_engine/privacy.py` — from datetime import UTC L5
- `Cortex/packages/tool_runtime/src/cortex_tool_runtime/__init__.py` — from datetime import UTC L6
- `Cortex/packages/workflow_engine/src/cortex_workflow_engine/__init__.py` — from datetime import UTC L7
- `Cortex/packages/workflow_engine/src/cortex_workflow_engine/auto_remediation.py` — from datetime import UTC L16
- `Cortex/packages/workflow_engine/src/cortex_workflow_engine/capacity_planning.py` — from datetime import UTC L2
- `Cortex/packages/workflow_engine/src/cortex_workflow_engine/security_incident.py` — from datetime import UTC L3

## Addendum — REL-050-FIX (2026-11-15, post-ship correction)

The sweep above missed one production file, and the omission was caught
by this PR's own gate in CI (the local proof had run against a snapshot
whose import graph did not expose it):

- `Futuris/futuris/scenarios/whatif.py` carried a bare
  `from enum import StrEnum` (line 42). It is reached from the Futuris
  entrypoint via `futuris/api/routers/scenarios.py`, so the Futuris
  entrypoint failed to import under Python 3.10 and the gate run at
  PR #397's head FAILED (Futuris only; the other nine passed). Fixed
  with the same try/except StrEnum fallback as the rest of the sweep.

Two further import-time sites landed on main after the sweep snapshot
and are fixed in the same follow-up:

- `Futuris/futuris/services/forecast_tracker.py` (TASK-FUT-006) —
  `from datetime import UTC` → the `UTC = timezone.utc` alias form.
- `Cortex/packages/agents/src/cortex_agents/__init__.py` — main's
  COR-004 replacement rewrote the file and reintroduced
  `from datetime import UTC`; the merge of main into this branch
  union-resolved it (main's rewrite kept, sweep's datetime form kept).

After these fixes, an AST re-scan of the merged tree finds zero
unguarded production-scope 3.11+ import idioms, and the gate passes
10/10 under Python 3.10.
