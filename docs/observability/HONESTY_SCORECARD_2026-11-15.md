# Fleet Health & Metrics Honesty Scorecard — TASK-OBS-003 (2026-11-15)

Method: for every agent, (a) the `/health` implementation was read in code and
compared against an independent live probe of the agent's real function, and
(b) every number the agent reports about itself was traced to its source.
Live probes were read-only, executed server-side via the bridge on
2026-11-15 ~13:17 IST against production (Server 1: FRIDAY/Inference/Memora/
Stratex/Futuris/IntelX/Forge; Server 2: Sentinel/Cortex/VyralX). Code state
audited: main `337a1e3f`. Note: Server 2's checkout lags main, so Server 2
live responses may reflect older code than the audited tree; where that
matters it is stated.

Grades: PASS = health and self-metrics trace to real measurements.
PASS-WITH-NOTES = honest, with labelled imperfections worth a follow-up.
DEFECT = a claim that does not trace to evidence (fixed in this PR where
safe; otherwise flagged to the owning crew).

## Per-agent results

### FRIDAY (10000) — DEFECT, fixed in this PR
- `/health` built an honest report (`friday_deep/health.py` computes
  `overall` from real import checks) and then **overwrote it**:
  `FRIDAY/src/friday/api/server.py` set `data["status"] = "healthy"`
  unconditionally and `data["peers_mesh"] = "connected"` with no probe.
- Live contradiction, same minute: `/api/mesh/status` reported history=36,
  state_counts {UNVERIFIED: 12, DEGRADED: 4, REFUSED: 4, PENDING: 4,
  COMPLETED: 12} and its own `live_verification` said
  "CONFIGURED-BUT-UNVERIFIED: …no live peer response has been observed" —
  while `/health` claimed the mesh was "connected".
- Why it matters beyond cosmetics: FRIDAY's own fleet classifier
  (`ecosystem/fleet_client.py::_classify_health_response`) maps a peer's
  `status` string onto ONLINE/DEGRADED — a hardcoded "healthy" defeats that
  vocabulary for any consumer of FRIDAY's health, including the fleet
  health watcher (TASK-OBS-001) whose HEALTH_FAIL alerts key off it.
- Fix: `status` is now the report's computed verdict; `peers_mesh` is
  derived from the mesh's recorded outcomes ("connected" only with a
  COMPLETED/SUCCESS outcome on record; "configured_unverified" when peers
  are configured but unobserved; "unavailable" when uninspectable).
  Two legacy tests that pinned the fabricated constant were updated to the
  honest contract; new tests pin the semantics
  (`FRIDAY/tests/test_obs003_health_honesty.py`, 5/5 passing).
- Observation (not fixed): `mesh.status()`'s `live_verification` string is
  a canned function of transport type and under-claims even with COMPLETED
  outcomes in the same payload. Under-claiming is the safe direction; left
  to the FRIDAY crews.

### Inference (8001) — PASS-WITH-NOTES
- `/health` is labelled `process_liveness`; `/ready` performs a real DB
  round-trip plus key-pool check; `/health/detailed` and
  `/health/providers` carry explicit `evidence_class`/`evidence_scope`.
  Live `/health/providers` reported observed traffic only (groq: 8 calls,
  87.5% success, timestamps) and key-pool counts that match the verified
  key layout exactly (Gemini 15 = 11 + 4 third-party, Groq 15 = 14 + 1,
  OpenRouter 15 = 14 + 1, NVIDIA 2).
- Note 1 (label): `active_specialist_agents` = 19 live. The count is real —
  it is the size of Inference's **internal deliberation-persona registry**
  (Requirements Analyst, System Architect, Trading Analyst, …) — but the
  field name invites a fleet reading (there are 9 fleet specialists), and
  "active" is unearned (registered ≠ measured active). Flagged for
  INF-002/coordinator as a rename/clarifier follow-up; not changed here to
  avoid colliding with the running Inference crews and field consumers.
- Note 2: `/v1/health` returns a constant `"status": "healthy"` with no
  evidence label — but in production it is auth-gated (live probe: 401),
  so the unlabelled surface is not publicly served. Same follow-up.

### Memora (8002) — PASS
- `/health` executes a real `SELECT 1`, reports the active vector backend's
  own readiness (Oracle 23ai native vector), and returns 503 when degraded
  (fixed under TASK-REL-013; verified in code and live: database healthy,
  vector available, durable).
- `/v1/metrics` counters are real process measurements (live: 172 writes,
  5,799 policy evaluations, dedup hits 124, measured latency percentiles).

### Stratex (8003) — PASS
- `api/health.py` operates under an explicit truthfulness contract
  (measured-at-request-time or labelled UNVERIFIED/NOT_CONFIGURED); the
  dashboard `/health` is labelled liveness and carries the engine's real
  heartbeat state; `/ready` is a separate, stricter gate (kill switch,
  panic, DB) — live: ready, engine online, trading capable, DEMO warning
  present.
- Note: `daemon_balance` (live 20,553.85) is the daemon heartbeat's
  `total_balance` — a real figure, but a **cross-venue aggregate**
  (Binance demo-fapi + OANDA practice), not a single account's equity.
  The payload's `environment`/`capability_warnings` fields disclose the
  venue mix, and TASK-STR-ANS-001 already labels the composite at the
  FRIDAY-answer layer. Anyone quoting this number as "the balance" without
  the venue note repeats the Phase-1 error.

### Futuris (8004) — DEFECT, fixed in this PR
- `/health` is honest (measured storage verdict), but `/status` reported
  `"status": "healthy"` as a constant and `"port": 8000` hardcoded
  (`Futuris/futuris/api/app.py`). **Live proof: the process answered on
  port 8004 while /status claimed port 8000** (the launcher binds
  `PORT` env or 8000; production sets 8004).
- Fix: `/status` now derives its verdict from the same `verify_schema()`
  measurement `/health` uses ("healthy"/"degraded"), reports the storage
  verdict, and reads the port from the `PORT` env. Existing probe tests
  stay green (test env: storage ready, no PORT → 8000); new tests pin
  PORT reflection and degraded-on-storage-failure.

### IntelX (8005) — PASS
- `/health` performs a real database check and reports `degraded` when it
  fails; `mock_mode` is disclosed in the payload (live: false, db ok).
  `/readyz` verifies DB + storage writability + provider configuration
  and says plainly that the provider check is configuration-only.

### Forge (8006) — PASS
- The routes health check performs a real DB ping plus provider health
  and folds both into its status; live `/health` reported
  `database_connected: true` with a measured uptime. Auth-gated surfaces
  answer 401 without a key, as designed.

### Sentinel (8008) — PASS-WITH-NOTES
- `/health` verifies the audit hash-chain live and reports entry count,
  vacuity and durability honestly (live: valid, 150 entries, durable).
  `/ready` labels what it does not check (`peer_connectivity:
  not_checked`).
- Note: the top-level `"status": "ok"` is constant — if the audit chain
  ever broke, `status` would still read "ok" and only `audit_chain_valid`
  would tell the truth. A consumer reading `status` alone (FRIDAY's
  classifier vocabulary does) would miss it. Flagged for SEN-002/SEN-003+
  as a one-line follow-up (fold chain validity into `status`); not changed
  here to avoid colliding with the running Sentinel crews.

### Cortex (8009) — PASS-WITH-NOTES, labelling fixed in this PR
- `/ready` is exemplary: per-dependency verdicts, `UNKNOWN: no live
  readiness probe configured` for unprobed peers, 503 unless required
  dependencies are UP (live: READY, database/schema/redis UP).
- `/status` claimed `"operational"` while measuring only uptime. The
  value is unchanged (contract), but the payload now carries
  `evidence_class: process_liveness` so the claim is scoped to what was
  measured.

### VyralX (8010) — MINOR DEFECT, fixed in this PR
- `/health` returned a bare `{"status": "ok"}` — no `evidence_class`, no
  `observed_at` — the only agent breaking the fleet's labelling
  convention. Its `/ready` is thorough and honest (DB, media warehouse
  with tables found, ffmpeg, worker heartbeat). Fix: `/health` now
  carries `evidence_class: process_liveness` + `observed_at`.
- `/api/analytics/summary` aggregates real `VideoMetric` rows (the
  REL-020 fabrication pattern stays fixed).
- Observation for SEN-002: `/ready` includes the media DB URL with the
  password masked but the username and host visible — acceptable inside
  the fleet, worth a look before any wider exposure.

## Cross-fleet conclusions
1. The fleet's honesty repairs (REL-013/018/020/030/032, SEN-001, the
   Stratex truthfulness contract) hold up under re-probe: no fabricated
   success rates, balances, or counts were found in any agent's
   self-reporting surfaces in this sweep.
2. The remaining defect class is **unlabelled or constant headline
   fields**: a truthful payload underneath with a `status`/`peers_mesh`/
   `port` on top that nobody measured. Two of the three fixed here were
   exactly that shape. The fleet convention that prevents it —
   `evidence_class` on every health/status payload — is now universal
   across all 10 agents.
3. Flagged follow-ups (not in this PR, by design): Inference
   `active_specialist_agents` rename/clarifier + `/v1/health` label
   (INF-002/coordinator); Sentinel `status` folding audit-chain validity
   (SEN-002+); FRIDAY mesh `live_verification` canned string (FRIDAY
   crews); VyralX `/ready` media-URL exposure (SEN-002).

## Test evidence for this PR
- FRIDAY: `tests/test_obs003_health_honesty.py` 5/5 passed locally;
  `test_health_endpoint_contract` and F7.1 health contract pass; the
  updated container/tier1 assertions pass where the suite's own
  environment allows (see PR body for the two sandbox-environmental
  failure classes, both pre-existing and unrelated: FastAPI `_IncludedRouter`
  route enumeration, and sqlite-backed tests under this sandbox's
  sqlite restriction — CI runs the canonical configuration).
- Futuris: handler verified by direct invocation against a stubbed
  `verify_schema` (port follows `PORT`; status follows the storage
  verdict) — the pytest suite itself needs a working sqlite, which this
  sandbox currently blocks at the syscall level for every agent's suite,
  including the pre-existing probes suite.
- VyralX/Cortex: handlers verified by direct invocation (labelled
  payloads returned); new pytest files included for CI.
- `ruff check --select F821` clean on all modified files.
