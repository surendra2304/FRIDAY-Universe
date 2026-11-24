# TASK-REL-088 — CI collects the tier-1 tests of EVERY agent

- Task: CI test job (`.github/workflows/friday-universe-ci.yml`, job `test`)
  must collect the tier-1 tests of EVERY agent (generalize REL-080 beyond
  Cortex). Owner: Muse 10. Branch:
  `muse10/task-rel-088-ci-tier1-all-agents`. Claim PR #1520 (merged
  2026-11-23 21:40 IST). Work PR: TBD (filled when opened).
- Acceptance: tier-1 suites for all 10 agents collected in CI; one
  deliberately-uncollected suite fails the gate as proof.
- Result: 21 files, 10 agents, all collected (gate 21/21, exit 0). The 9
  newly-wired agents contribute 204 tests: 195 pass locally, 9 deselected
  as pre-existing failures proven on current main (see below). Cortex was
  already wired by REL-080 (2 files, 5 deselects) and is included in the
  gate; it was not re-run here.

## Per-agent suites and local results

All runs on Server 2, python3.11, own venv per agent (REL-080 pattern),
against the merged branch head unless noted. Branch carried 0 unique
commits during the proof runs, so each run is a run on main for the
agent under test.

| Agent | Tier-1 files | Local result | Deselects |
|---|---|---|---|
| FRIDAY | tests/test_tier1_resilience_and_contracts.py, tests/e2e/test_tier1_features.py | 86 passed, 0 failed (9.11s, re-run on head 30e1103a) | 0 |
| Memora | tests/test_tier1_resilience_contracts.py | 10 passed, 2 failed (12 tests) | 2 |
| Stratex | tests/test_tier1_resilience_and_contracts.py | 18 passed, 1 failed (19 tests) | 1 |
| Forge | tests/unit/test_tier1_resilience.py, tests/unit/test_deep_upgrade_tier1.py | 21 passed, 6 failed (27 tests) | 6 |
| Cortex | tests/unit/test_e2e_tier1.py, tests/e2e/test_e2e_tier1.py | wired by REL-080, not re-run | 5 (REL-080) |
| Inference | tests/test_health_security.py, tests/test_module_importability.py, tests/test_monitoring_health_evidence.py | 12 passed, 0 failed | 0 |
| Sentinel | tests/security/test_health_readiness.py, tests/security/test_health_durability_truthfulness.py, tests/unit/test_foundation.py | 13 passed, 0 failed | 0 |
| IntelX | tests/test_intelx_health_contract.py, tests/test_health.py, tests/test_healthz_liveness.py | 22 passed, 0 failed (21.10s) | 0 |
| Futuris | tests/test_futuris_health_contract.py, tests/api/test_health.py | 8 passed, 0 failed | 0 |
| VyralX | tests/test_recovery_and_readiness.py, tests/test_obs003_health_labelling.py | 5 passed, 0 failed | 0 |

## Design decision: tier-1 for the five agents without a named suite

No tier-1-named suite exists for Inference, Sentinel, IntelX, Futuris,
VyralX (100-135 test files each under `tests/`; code search for "tier1"
finds nothing in their tests), and there is no repo-wide tier-1
definition beyond the named files. For these five, tier-1 = the agent's
health-contract + importability / resilience core files: the minimal set
proving the agent boots and honors its contracts. The five sets were
confirmed by the local runs above (all pass, 0 deselects), so they are no
longer provisional. If the team later adopts a different tier-1
definition for these agents, update the gate's fixed list and this doc
together.

## Deselect proofs (all pre-existing on main)

Per the REL-080 pattern, each deselect is a failure reproduced on main
with the exact CI recipe; the branch added nothing to the agent under
test at proof time. Node IDs are the exact `--deselect` values in the
workflow.

### Memora (2) — proof run on main 49126a41: same 2 failed, 10 passed
- `tests/test_tier1_resilience_contracts.py::test_health_probe_contract`
  — GET /health returns 503, expects 200. Open question (not resolved):
  whether the health aggregate includes vector/Qdrant health in fallback
  mode. The CI test job has no `services:` section (no Redis/Qdrant in
  CI), but the local runs had live Redis reachable, so the 10 passing
  tests may behave differently in CI; the work PR's CI run is the real
  test for that.
- `tests/test_tier1_resilience_contracts.py::test_ready_probe_contract`
  — GET /ready returns 200 but the JSON has no "wal" key (data has
  status/service/version/database).
- Env: MEMORA_ENV/ENVIRONMENT=testing, MEMORA_EMBEDDING_MODE=hashing,
  DATABASE_URL sqlite. The CI step uses a separate sqlite file
  (`memora_ci_tier1.db`) from the vector step (`memora_ci_test.db`) so
  the tier-1 run starts from a fresh DB exactly like the local proofs.

### Stratex (1) — proof run on main 0ea5accc: same 1 failed, 18 passed
- `tests/test_tier1_resilience_and_contracts.py::TestStandardizedContracts::test_health_includes_service_metadata`
  — GET /health returns 503, expects 200. Same signature as Memora's
  health failure; no live deps in the test env.

### Forge (6) — run on main 053d17fe: 6 failed, 21 passed
- `tests/unit/test_tier1_resilience.py::test_ready_probe_contract` —
  ready probe 503 (no live Oracle ADB in the test env).
- `tests/unit/test_tier1_resilience.py::test_status_diagnostics_endpoint`
  — status "unhealthy" (same cause).
- `tests/unit/test_tier1_resilience.py::test_sqlite_pragmas_and_wal_mode`
  — PRAGMA no-op expectation (wrapper returns the mock row).
- `tests/unit/test_deep_upgrade_tier1.py::test_database_manager_crud_and_row_mapping`
  — db_path TypeError (DatabaseManager takes no db_path kwarg;
  test/code mismatch).
- `tests/unit/test_deep_upgrade_tier1.py::test_async_db_connection_wrapper_features`
  — db_path TypeError (same mismatch).
- `tests/unit/test_deep_upgrade_tier1.py::test_oracle_and_postgres_url_translation`
  — postgres URL translation RuntimeError (code demands an
  oracle+oracledb:// DSN).
- The 7th failure in the first Forge run,
  `test_sentinel_client_identity_headers`, passes once respx is
  installed, so it is NOT deselected; the CI Forge step installs respx.

## CI recipes (one step per agent, after the Cortex step)

Each step builds its own venv from the agent's requirements file and
runs the tier-1 files through the REL-086 failure-summary wrapper, in
the same shape as the Cortex step (REL-080) and the Memora vector step.

- FRIDAY: `-r requirements.txt pytest pytest-asyncio`. The suite uses
  `@pytest.mark.asyncio`; requirements.txt lacks the plugin — the first
  local run failed 19 tests on exactly that, and 86 passed once the
  plugin was installed. No `-m` marker filter is needed for the e2e
  file: plain pytest passes 86/86.
- Memora: `-r requirements.txt pytest pytest-asyncio`, vector-step env,
  separate sqlite file (see above).
- Stratex: `-r requirements.txt pytest pytest-asyncio`.
- Forge: `-r requirements.txt pytest pytest-asyncio respx`.
- Inference: `-r requirements.txt pytest pytest-asyncio aiosqlite`.
  requirements.txt has fastapi + sqlalchemy but no aiosqlite; the
  importability test fails with ModuleNotFoundError without it.
- Sentinel: `-r requirements.txt pytest pytest-asyncio`.
- IntelX: `-r requirements.txt pytest pytest-asyncio aiosqlite`.
  requirements.txt has sqlalchemy[asyncio] but no aiosqlite; all 22
  tests errored on collection without it.
- Futuris: `-r requirements.txt pytest pytest-asyncio aiosqlite`, plus
  `DATABASE_URL: oracle+oracledb://dummy:dummy@localhost:1521/dummy`.
  The import-time check validates the URL scheme only; the tests use
  local SQLite fixtures, so no live Oracle is needed. Without the dummy
  URL the conftest import raises RuntimeError (DATABASE_URL not
  configured). The dummy URL is a localhost placeholder, not a secret.
- VyralX: `-r requirements.lock pytest pytest-asyncio`. VyralX has no
  requirements.txt (only pyproject.toml + the SEN-012 pinned
  requirements.lock, 84 lines) and no tests/conftest.py. NOTE: a fresh
  lock install was not proven locally (the probe venv already held the
  lock deps when the 5 tests passed); the work PR's CI run is the proof
  of that path.

## The gate (scripts/tier1_collection_gate.py)

A new script, not an extension of `scripts/ci_test_collection_audit.py`:
the REL-068 guard is diff-scoped (it only checks test files the PR
itself touches), so a PR that unwires a suite without touching a test
file would pass it. The new gate checks a FIXED list of 21 tier-1 files
(10 agents) against the pytest invocations of the test job in
`.github/workflows/friday-universe-ci.yml`; exit 1 naming the missing
suites, exit 0 when all are collected. It runs as a step in the test job
right after checkout/setup-python, before the agent steps. Line-based
parse, no third-party dependencies.

Proof (three legs, all on the merged head 30e1103a):
1. Gate on current main's workflow (b2b239c0): FAIL, 2/21 collected
   (only Cortex's 2 wired), exit 1.
2. Gate on the wired workflow: PASS, 21/21 collected, exit 0.
3. Unwire-one: VyralX `tests/test_obs003_health_labelling.py` removed
   from the workflow: FAIL, 20/21 collected, exit 1, naming exactly
   `VyralX/tests/test_obs003_health_labelling.py`.

## Work PR and CI run

- Work PR: TBD.
- CI run on the work PR: TBD (link when green).
- Never merge: only Muse merges.

## Open items (not blockers for this task)

- Memora/Stratex/Forge health-probe 503s share one signature (no live
  backing services in the test env). If the team wants those probes
  green in CI, the fix belongs in the agents (health contract vs.
  degraded mode), not in this task's deselects.
- VyralX fresh lock install is proven only by the work PR's CI run.
- The Memora vector step and the new Memora tier-1 step share the
  Memora directory in one job; the tier-1 step's separate sqlite file
  keeps them isolated.
