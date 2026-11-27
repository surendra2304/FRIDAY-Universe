# TASK-FUT-020 — Checkpoint 2: live-leg re-probe (G1/G2/G3)

- Task: TASK-FUT-020 (P2, owner muse_10) — Futuris: one NON-market forecast live through the scheduler — fleet capacity, weather, or tech trend — filed and scored against the outcome.
- Branch: `muse10/task-fut-020-checkpoint-2-live-leg`, base main `5fd32fdf`.
- Claim: hub #2045 comment 7208626203 (~08:30 IST), on assignment by the Burn Enforcer run ~08:25 IST (hub #2045 comment 7208489714 §B): "TASK-FUT-020 checkpoint-2 live leg is your head task now... Re-probe state first, no blind retry (your G1/G2)."
- Board: MERGED, owner muse_10, PR #1989 (checkpoint 1 filed). No board hunk in this PR — board flips are coordinator-only per ruling 7200564540.
- Work PR: (this PR).

## 1. Re-probe, first-hand, 2026-11-27 ~08:30–08:40 IST

- Fleet: both Oracle servers ONLINE (`get_system_info`): Server 1 ONLINE, Server 2 ONLINE. Server 2 workspace checkout at `38ff1e70` (board PR #2053 merge) — behind GitHub main `5fd32fdf`; stale checkout, noted, not moved.
- G1 — `Futuris.service` on Server 1: still **masked, inactive (dead)** (`oracle_check_service`, agent futuris; first call hit an MCP transport error, retry returned the state). UNCHANGED from checkpoint 1. No Futuris process is running there, so no scheduler is running there.
- G2 — `DATABASE_URL` in the Server 2 venv shell: still **not configured**. Probe: `source /opt/friday_universe/venv/bin/activate; printenv DATABASE_URL | wc -c` on Server 2 returned `0` (byte count only — the value was never read or printed). UNCHANGED from checkpoint 1.
- G3 — scheduler unit tests still cannot run in place on Server 2: `run_workspace_test` on `Futuris/tests/upgrade/test_scheduler.py` fails at conftest import with the same `RuntimeError: DATABASE_URL is not configured` (`Futuris/futuris/infra/config.py`, `validate_database_backend`). UNCHANGED from checkpoint 1.

## 2. Verdict: live leg still NOT ARMED

G1 and G2 are both unchanged since checkpoint 1 (2026-11-26 ~18:15 IST). No live scheduler run is possible until the coordinator/owner clears G1 (unmask/start Futuris.service on Server 1) and G2 (configure DATABASE_URL in the Server 2 venv). No live move was made in this run: nothing restarted, no env change, no deploy, no forecast attempted. No blind retry.

## 3. Next

- Coordinator/owner decision owed on G1 + G2 (same as checkpoint 1). Scoring follows when a live forecast runs and its 24h outcome lands (resolving cycle per FUT-017, or the 30-minute scoring job).
- Queue behind this: FRG-034 MERGED (PR #2018); CTX-009 gated; VOICE-E2E-003 do-not-execute.

— Muse 10
