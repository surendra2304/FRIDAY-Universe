# TASK-FRD-033 — FRIDAY IntelX peer URLs re-pointed to post-migration hosts

- **Task:** TASK-FRD-033 (WF-001 F1: FRIDAY IntelX peer URLs stale post-migration).
- **Worker:** Muse 2. **Date:** 2026-11-22 ~15:45 IST.
- **Claim:** issue #35 comment 7075943856; claim PR #1342 merged 13:49 IST (merge b38bacbe).
- **Work PR:** (number set on the board record when the PR opens).
- **Status:** implemented, IN_REVIEW. FRIDAY **not** restarted — the restart gate is
  closed; restart + live re-probe + WF-001 trace re-run are owed after Muse clears
  deployment on the hub.

## What was wrong

The WF-001 fresh M1 trace (PR #1333) failed its IntelX research leg on both paths
because FRIDAY's peer-URL tables still pointed at the pre-migration hosts:
`http://10.0.0.121:8005/health` → `000` (unreachable), while
`http://10.0.0.120:8005/health` → `200` and the public Caddy route
`https://friday-universe.duckdns.org/intelx/health` → `200`. The 6/4 migration
(TASK-REL-062, MERGED) moved IntelX S1 → S2 and Futuris S1 → S2, and Sentinel
S2 → S1; the Caddy routes and deploy-workflow lists were flipped, but FRIDAY's
in-code peer-URL tables were not.

## The fix

Three stale entries re-pointed in each of FRIDAY's three peer-URL tables:

| Agent | Before | After | Why |
|---|---|---|---|
| IntelX | `10.0.0.121:8005` | `10.0.0.120:8005` | REL-062: IntelX S1 → S2; live `200` at `.120:8005`, `000` at `.121:8005` (WF-001 trace) |
| Futuris | `10.0.0.121:8004` | `10.0.0.120:8004` | REL-062: Futuris S1 → S2, health `200` on S2 under venv312 |
| Sentinel | `10.0.0.120:8008` | `10.0.0.121:8008` | REL-062: Sentinel S2 → S1, health `200` on S1 (S2 unit masked) |

Files changed (same three values in each):

- `FRIDAY/src/friday/ecosystem/fleet_client.py` — `CANONICAL_INTERNAL_MESH_URLS`
  (the F1 file), plus a layout comment citing REL-062.
- `FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py` — agent defaults
  (the F1 file), plus the layout comment corrected to REL-062.
- `FRIDAY/src/friday/agent/router.py` — `SPECIALIST_CONFIGS[].canonical_mesh_url`.
  **Third copy, found by code search, not named in F1.** It is the live dispatch
  path (`SpecialistRouter.get_agent_url`, production fallback); leaving it stale
  would have left FRIDAY routing IntelX/Futuris/Sentinel at the dead hosts.

## The `.121`-block check (all nine map entries)

Checked against the REL-062 confirmed layout (S1 = `10.0.0.121`: FRIDAY,
Inference, Memora, Stratex, Forge, Sentinel; S2 = `10.0.0.120`: IntelX, Futuris,
Cortex) and `AGENTS.yaml` ports (inference 8001, memora 8002, stratex 8003,
futuris 8004, intelx 8005, forge 8006, sentinel 8008, vyralx 8010):

| Agent | Port | Map value now | Host per REL-062 | Verdict |
|---|---|---|---|---|
| inference | 8001 | `10.0.0.121:8001` | S1 | correct, unchanged |
| memora | 8002 | `10.0.0.121:8002` | S1 | correct, unchanged |
| stratex | 8003 | `10.0.0.121:8003` | S1 | correct, unchanged (see note below) |
| futuris | 8004 | `10.0.0.120:8004` | S2 | **fixed** |
| intelx | 8005 | `10.0.0.120:8005` | S2 | **fixed** (live `200` proven in WF-001) |
| forge | 8006 | `10.0.0.121:8006` | S1 | correct, unchanged |
| sentinel | 8008 | `10.0.0.121:8008` | S1 | **fixed** |
| cortex | 8009 | `10.0.0.120:8009` | S2 | correct, unchanged |
| vyralx | 8010 | `10.0.0.120:8010` | sleeper on AWS U2 | unchanged, **unverified** (no S2 listener evidence; see below) |

## Regression coverage

`FRIDAY/tests/test_codex_invariants_and_mesh.py` (existing file, extended — no new
test file, so no contracts-workflow list change is owed):

- `test_specialist_router_canonical_mesh_in_production`: sentinel assertion
  corrected `.120:8008` → `.121:8008`; intelx (`.120:8005`) and futuris
  (`.120:8004`) assertions added, with their env vars cleared so the test
  exercises the canonical fallback.
- `test_fleet_client_canonical_mesh_in_production`: `intelx_url` (`.120:8005`),
  `futuris_url` (`.120:8004`) and `sentinel_url` (`.121:8008`) assertions added,
  with env vars cleared.

## Known stale copies found by code search — out of scope, filed for follow-up

The same pre-migration values also appear outside FRIDAY's peer-URL tables.
They are other components' own configs and were **not** changed here:

- `mesh/universe_health.py:61-70` — Unified Health Check Engine probes the same
  three stale hosts (intelx/futuris `.121`, sentinel `.120`). Until fixed it
  will keep reporting those three peers against dead addresses.
- `Forge/app/core/config.py`, `Inference/app/core/config.py` — those services'
  own mesh references (`.121:8004`, `.121:8005`).
- `VyralX/scripts/check_mesh.py` — VyralX mesh check.
- `deploy/Caddyfile`, `docs/archive/MASTER_AGENT_AWAKENING_DIRECTIVE.md`,
  `scripts/generate_master_architecture_pdf.py`, `docs/TASK-SEN-013_FINDINGS.md`,
  `docs/collaboration/TASK-ORCH-011-SUPERVISION-REPROBE.md` — docs / generated /
  deploy references (Caddy routes themselves were flipped per REL-062).

## Open items / honesty bounds

- **Stratex engine vs dashboard:** the WF-001 trace noted the live bus value
  `127.0.0.1:8003` reaches the Stratex dashboard on S1, not the engine. The map
  keeps `10.0.0.121:8003` because REL-062 puts Stratex on S1 and `AGENTS.yaml`
  gives Stratex port 8003 — but which process answers the bus dispatch on
  `8003` is **not** proven from the repo. Re-probe item for the post-restart
  verification (dispatch a Stratex task through the bus and confirm an engine
  answer, not a dashboard page).
- **VyralX `.120:8010` unverified:** REL-062 says the VyralX sleeper "works on
  AWS U2", with no S2 listener evidence either way. Left unchanged; do not treat
  the map value as verified.
- **No live verification yet in this PR:** the code fix lands first; FRIDAY runs
  the old checkout until it is redeployed and restarted under coordinator
  clearance. Live `200`s on both paths (chat FleetClient + dispatch bus) and
  the WF-001 trace re-run are owed after the restart.
- **No secret or key value was read, printed, logged, or stored.** No live
  service was restarted and no live config was changed by this PR.
- **Local tests were not run** on the fetched content (execution-risk rule);
  verification rests on repo CI on the PR head.

## Board / PR

- Board: `TASK-FRD-033` CLAIMED → IN_REVIEW in the work PR (this PR).
- Work PR merge-base: current main at filing (stated in the PR body).
- Next: Muse reviews/merges; then FRIDAY restart only on Muse's hub clearance,
  live re-probe of both IntelX paths, and the WF-001 trace re-run.

— Muse 2
