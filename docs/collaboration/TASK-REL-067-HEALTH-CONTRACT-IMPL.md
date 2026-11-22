# TASK-REL-067 — Health-Capability Contract Implementation (WORK IN PROGRESS)

**Task:** Implement the health-capability contract per REL-004 section 8
(design: `docs/collaboration/TASK-REL-004-HEALTH-CONTRACT.md`, Muse 9).
**Branch:** `muse8/task-rel-067`. **Status:** Stratex slice implemented on
the branch; FRIDAY classifier + 8 agents remain. **Work PR not opened yet**
— this document grows with the work and is filed with the work PR.

## Done this run (2026-11-22 ~15:00 IST, hourly self-check)

Stratex is the reference implementation (design §5: every contract field
already exists in its `/health` body; the work is a derivation, not a probe).

- `Stratex/dashboard.py` — `_stratex_capability_report()` derives the
  §2.2 report: `capabilities.trading_engine` (required; heartbeat ≤ 90 s +
  worker RUNNING + PID alive, including the PAPER-mode and FUTURES-daemon
  alternate witnesses), `capabilities.trading_capable` (required; engine
  healthy + ≥ 1 executable strategy + evaluation fresh ≤ 900 s + no panic /
  kill-switch), `capabilities.market_data` (required; `binance_connected` +
  `websocket_connected` — **default fixed: omitted flags now report
  `unknown` with detail `MARKET_DATA_NOT_REPORTED`, never default True**),
  `dependencies.database` (required; live Oracle `SELECT 1 FROM DUAL`, the
  same probe `/ready` already ran). Top-level `status` is derived (`ok`
  iff every required capability/dependency is `ok`, else `degraded`);
  HTTP is 200 iff `ok`, else 503. `evidence_class` on `/health` is now
  `capability_report`. All pre-existing fields are kept. No secret or raw
  exception text is placed in any detail: `READ_ERROR: <exc>` is mapped to
  the stable code `ENGINE_PROBE_FAILED`; other reason codes are
  `HEARTBEAT_FILE_MISSING`, `ENGINE_OFFLINE`, `PANIC_ACTIVE`,
  `KILL_SWITCH_LOCKED`, `MARKET_DATA_DISCONNECTED`,
  `DATABASE_UNCONFIGURED`, `DATABASE_UNREACHABLE`, plus the existing
  `STALE_STRATEGY_EVALUATION` / `NO_EXECUTABLE_STRATEGY` /
  `NO_STRATEGY_EVALUATION` codes.
- `/ready` unchanged in behaviour: it now consumes the probe
  `_health_payload` already ran (design §2.5) instead of re-probing; the
  ready gate, production gate, payload fields and HTTP codes are identical.
  `/ready`'s payload additionally carries the capabilities block (additive).
- `Stratex/Dockerfile` — HEALTHCHECK moved from `/health` to `/ready`
  (design §2.5/§7: `/health` 503 means "degraded", not "dead").
- `Stratex/tests/test_engine_capability_truthfulness.py` — the old test
  asserting `/health` stays 200 for an inert engine is updated to the
  contract (503, `degraded`, `trading_capable` unavailable,
  `NO_EXECUTABLE_STRATEGY`); two tests added: the TASK-REL-003 condition
  (engine offline + stale evaluation → 503, `trading_engine` /
  `trading_capable` unavailable, `STALE_STRATEGY_EVALUATION`) and the
  capable-engine ok path (200, all capabilities `ok`, DB probe stubbed).

## Probe-routing verification (§7 prerequisite, Stratex)

- `deploy/Caddyfile`: the Stratex `reverse_proxy` block sets no
  `health_uri` — Caddy does not actively probe Stratex health. No Caddy
  change needed for Stratex.
- No `render.yaml` exists in the repo (root or `Stratex/`); the "Render
  must not kill-loop" comment in the old test is historical (service
  measured on Render 2026-10-03). The live service is the Oracle Server 1
  systemd unit; its liveness gate is `/ready` via the unit, not `/health`.
- Docker HEALTHCHECK moved to `/ready` (above).

## Verification status — read this before merging

- **Not verified locally in this run.** The hourly self-check run hit an
  execution-risk notice on the local clone, so no local pytest, import or
  build of repo code was run; the edits were verified by re-reading the
  changed regions only. **CI on the work PR is the gate**: the updated and
  new Stratex tests must pass there, plus the existing
  `test_daemon_heartbeat_health.py` (untouched; its `_health_payload`
  assertions on engine fields are unaffected) and the `/ready` tests.
- **Live-probe criteria 2–3 are NOT yet verified.** They cannot be until
  this code merges and deploys: a live probe can only observe the new
  503/degraded behaviour on a running service with the new code. Baseline
  (pre-contract, VAL-004 Fleet Live Validation run 44995483145, 2026-11-22
  12:19 IST): Stratex `/health` answered 200 with the engine offline.
  Post-merge, the verification is: deploy → probe Stratex `/health`
  (expect degraded/503 with `trading_capable` unavailable +
  `STALE_STRATEGY_EVALUATION` while the engine is offline) → probe
  FRIDAY fleet-status (expect Stratex named DEGRADED with the failing
  capability + reason; pre-contract peers labelled capability unknown).
- Note: `test_engine_capability_truthfulness.py` and
  `test_daemon_heartbeat_health.py` are not in any workflow's explicit
  file list today (checked 2026-11-22) — the same gap REL-001 closed for
  other files. The work PR must confirm which CI job runs them, or wire
  them in, so the new tests are actually exercised.

## Remaining (next runs)

1. FRIDAY classifier (§4): `_classify_health_response` reads contract
   fields first; DEGRADED carries failing capability names + detail codes;
   pre-contract peers labelled REACHABLE (capability unknown), never
   ONLINE; `fleet_status.py` summary/scope wording; `controller.py`
   "responded" split into ONLINE/DEGRADED.
2. The other eight agents' `/health` mappings per design §5 (Memora,
   Futuris, IntelX, Forge, Sentinel, Cortex, VyralX, Inference) and
   FRIDAY's own `/health` (§3: orchestration, memory_backend, peer_mesh,
   database, disk).
3. §6 open questions to resolve from source/live probe while implementing:
   FRIDAY `peers_mesh` provenance; Forge's three `/health`s (confirm by
   live probe which handler answers each path); Stratex master-control
   `/health` mount; FRIDAY `/health/deep` mount; Memora `/health`
   dependency-failure mode; Futuris `verify_schema()` liveness.
4. Criterion 5 sweep: no secret in any health payload (Futuris `/ready`
   and Cortex raw exception text are named in the design §2.2 rule 8).
5. Criterion 6: all ten `/ready` behaviours unchanged; Caddy/Docker
   probes confirmed on `/ready` per agent before its `/health` flips.

— Muse 8, TASK-REL-067, 2026-11-22 ~15:00 IST
