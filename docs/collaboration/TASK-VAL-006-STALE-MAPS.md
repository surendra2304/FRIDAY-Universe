# TASK-VAL-006 — Fix the stale fleet maps — 2026-11-22

Task: Fix the stale maps — repo Caddyfile, workflow server lists, FRIDAY probe
map — to the deployed layout (Futuris/IntelX on Server 2, Sentinel on Server 1,
Stratex via the 127.0.0.1:18003 tunnel to AWS U1, VyralX on AWS
16.176.9.247:8010). Worker: Muse 14. Claim: issue #35 comment 7083391060.
Assignment: coordinator watch 7083334971 (~23:35 IST, P1, pool 10). Source:
VAL-005 finding F1. Acceptance: a fresh validation run and a fresh FRIDAY
fleet-status answer show zero false down.

## Method (read-only verification first; no live writes in this PR)

1. Re-read the deployed truth myself via the engineering bridge (read-only
   `run_shell` + SSH hop to Server 1, 2026-11-22 ~23:45 IST): deployed
   `/etc/caddy/Caddyfile` (verbatim), `ss -ltn` listeners on both servers,
   deployed FRIDAY code head, deployed FRIDAY `.env` URL values (names +
   agent URLs only — no key or DB values read, printed, or stored).
2. Fresh public-gateway probe of FRIDAY `/api/agents/status` from this VM
   (~23:50 IST) for the pre-fix baseline.
3. Edited the repo maps, validated locally (py_compile, workflow YAML parse,
   AST assertion of all three mesh tables, byte-diff of the repo Caddyfile
   against the deployed file). No pytest on this VM — the mesh tests run in
   PR CI, which is the gate before merge.

## Deployed layout (verified live this run, not copied from VAL-005)

| Agent | Where it actually runs | Evidence this run |
|---|---|---|
| FRIDAY | S1 :10000 | S1 listener, unit active |
| Inference | S1 :8001 | S1 listener (pid 2365064), unit active |
| Memora | S1 :8002 | S1 listener, unit active |
| Stratex | AWS U1 via S1 SSH tunnel 127.0.0.1:18003 | S1 `127.0.0.1:18003` listener is `ssh` (pid 2263571); no :8003 on S1; S1 Stratex unit inactive (masked) |
| Futuris | S2 :8004 | S2 listener (pid 577689) |
| IntelX | S2 :8005 | S2 listener (pid 563553) |
| Forge | S1 :8006 | S1 listener, unit active |
| Sentinel | S1 :8008 | S1 listener (pid 2365819), unit active; no :8008 on S2 |
| Cortex | S2 :8009 | S2 listener (pid 584499) |
| VyralX | AWS 16.176.9.247:8010 | No :8010 on S2; VAL-005 direct curl from S1 to the AWS address returned 200 |
| Bridge | S2 :8011 | S2 listener (pid 537376) |

Deployed `/etc/caddy/Caddyfile` on S1 routes exactly this layout, plus
`/friday/api/ws/activity` (websocket upgrade to :10000) and the static
handles `/privacy-vyralx` and `/pepperstone-auth` (`/srv/friday-static`).
Deployed FRIDAY code head is `60e09844` (current main).

## Pre-fix baseline: fleet-status still shows 2 false down

Live `/api/agents/status` probe ~23:50 IST (after the 22:50 `.env` edit and
the 23:22 FRIDAY restart, which already fixed IntelX/Futuris): status
`degraded`, 7 ONLINE, 2 UNREACHABLE — Stratex `127.0.0.1:8003`
ConnectError, VyralX `10.0.0.120:8010` ConnectError. VAL-005's 5 false down
are down to 2; the remaining 2 are the stale `.env` overrides (below).

## The .env finding: env overrides beat the repo map

The deployed FRIDAY `.env` (`/opt/friday_universe/FRIDAY/.env`, mtime
2026-11-22 22:50:41 IST) carries agent URL overrides that
`fleet_client.configured_url()` checks BEFORE the canonical map, so fixing
the repo map alone does not fix the live fleet-status answer. Values found
(agent URLs only):

- Correct already: Inference/Memora/Forge `127.0.0.1:8001/8002/8006`,
  IntelX/Futuris/Cortex `10.0.0.120:8005/8004/8009`.
- STALE (3): `STRATEX_URL` + `FRIDAY_STRATEX_URL` = `127.0.0.1:8003`
  (must be `127.0.0.1:18003`); `SENTINEL_URL` + `FRIDAY_SENTINEL_URL` =
  `10.0.0.121:8008` (must be `127.0.0.1:8008`; the `.121` form happens to
  work because S1 listens on 0.0.0.0, but it is not the deployed form);
  `VYRALX_URL` + `FRIDAY_VYRALX_URL` = `10.0.0.120:8010` (must be
  `http://16.176.9.247:8010`).
- `/etc/friday/dispatch.env` carries no URL lines — no second override
  source. `ENVIRONMENT=production`, so the canonical map is the fallback.

This also explains VAL-005's snapshot: the 21:59 IST fleet-status was
probed from a FRIDAY process started before the 22:50 `.env` edit, so it
still showed IntelX/Futuris at `127.0.0.1` — the running process had the
old values. The current process (pid 2434842, started 23:22 IST) loaded
the 22:50 `.env`, which is why IntelX/Futuris are ONLINE now.

## Changes in this PR (repo only — no live writes)

1. `deploy/Caddyfile` — byte-identical to the deployed file (verified by
   diff), plus a 4-line header comment naming the deployed file as the
   source of truth. Routes fixed: Stratex `8003` → `18003`, Futuris/IntelX
   `127.0.0.1` → `10.0.0.120`, Sentinel `10.0.0.120:8008` →
   `127.0.0.1:8008`, VyralX `10.0.0.120:8010` → `16.176.9.247:8010`;
   added `/bridge`, `/mcp`, `/messages` → `10.0.0.120:8011`,
   `/friday/api/ws/activity`, and the two static handles.
2. `.github/workflows/fleet-live-validation.yml` — S1 systemctl list drops
   Stratex/Futuris/IntelX, gains Sentinel (keeps Stratex-Daemon for
   visibility); S1 local probes drop `8003/8004/8005`, gain Sentinel
   `:8008`, Stratex `:18003` (tunnel) and VyralX `16.176.9.247:8010`
   (from S1 — the runner cannot reach AWS directly); S2 systemctl list
   drops VyralX/Sentinel/VyralX-Daemon, gains Futuris/IntelX; S2 local
   probes are now Futuris `:8004`, IntelX `:8005`, Cortex `:8009`.
3. `FRIDAY/src/friday/ecosystem/fleet_client.py` —
   `CANONICAL_INTERNAL_MESH_URLS`: Stratex → `127.0.0.1:18003`, Sentinel
   → `127.0.0.1:8008`, VyralX → `16.176.9.247:8010`; comment rewritten
   to the deployed layout with the `.env`-wins warning.
4. `FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py` — same
   three defaults in `_register_default_agents` (+ layout comment).
5. `FRIDAY/src/friday/agent/router.py` — same three `canonical_mesh_url`
   values (Sentinel, Stratex, VyralX).
6. `FRIDAY/tests/test_codex_invariants_and_mesh.py` — the two canonical
   mesh tests assert the new values (docstrings updated); no other test
   asserts the old values.
7. `.github/workflows/owner-workflows.yml` — the mesh test is added to the
   contracts job's pytest invocation. The test-collection guard (REL-068)
   failed PR #1404's first CI run because the edited test file was
   collected by NO PR-triggered workflow; adding it to the invocation is
   the guard's prescribed fix (not EXCLUDED — the tests are real pytest
   tests and should run). Guard re-run locally after the edit: PASS
   (277 covered, 1 checked). Import chain checked statically: stdlib +
   httpx + pydantic + pydantic-settings + sqlalchemy only, all installed
   by the contracts job; `FRIDAY/tests/conftest.py` puts `FRIDAY/src` on
   sys.path. No pytest on this VM, so the run itself is verified by PR CI.

Deliberately NOT touched (follow-ups for Muse, §5): other agents' peer
defaults (Forge/Inference/IntelX/Memora configs, Sentinel watchdog script,
VyralX check_mesh script), `deploy-monorepo.yml` server mapping, the
`AGENTS.md` deployment table, the bridge `oracle_fleet_health` S2 label,
Cortex's stale peer list, the Stratex tunnel runbook (VAL-005 Q4),
VyralX-Daemon's current host (unknown — was inactive on S2).

## Deploy plan (needs hub clearance — NOT done in this PR)

No live change was made by this run. To reach the acceptance, after merge:

1. On S1, edit `/opt/friday_universe/FRIDAY/.env` (3 values only):
   `STRATEX_URL` + `FRIDAY_STRATEX_URL` → `http://127.0.0.1:18003`;
   `SENTINEL_URL` + `FRIDAY_SENTINEL_URL` → `http://127.0.0.1:8008`;
   `VYRALX_URL` + `FRIDAY_VYRALX_URL` → `http://16.176.9.247:8010`.
   (Names only above — no key or DB value is touched.)
2. Deploy the merged code to S1 (`git pull` in `/opt/friday_universe` to
   the merge commit) and restart FRIDAY (`systemctl restart FRIDAY`).
   The Caddyfile needs no reload — the deployed file already matches the
   repo copy after this PR; do NOT copy the repo file over it blindly, the
   deployed file is the source of truth and they are now identical.
3. Re-probe: `GET /friday/api/agents/status` must show `ok`, 9/9 ONLINE
   (per REL-004 the verdicts are reachability-only, not ONLINE capability
   — the acceptance here is zero false UNREACHABLE, not a capability
   claim), and dispatch the Fleet Live Validation workflow — all 3 jobs
   must complete with no false-down rows.
4. Rollback: the `.env` change is 3 URL values (revert to the previous
   values, restart FRIDAY); the code change is a normal PR revert.

## Verification status

- Implemented: repo maps fixed (this PR), local validation passed
  (py_compile, workflow YAML, AST map assertions, Caddyfile byte-diff,
  test-collection guard PASS after the owner-workflows.yml fix).
- Fresh validation run: **done, zero false down.** Fleet Live Validation
  run 45054456383, dispatched from branch `muse14/task-val-006` 2026-11-22
  ~23:50 IST, completed `success`, all 3 jobs green. S1 job (stamp
  18:20:09Z): FRIDAY/Inference/Memora/Forge/Sentinel active, all local
  /health 200; Stratex /health 200 via the :18003 tunnel; VyralX /health
  200 on AWS. S2 job: Futuris/IntelX/Cortex active, all local /health
  200. Public-gateway job: `SUMMARY: 10/10 agents healthy; bridge OK`.
  No `000`, no false-down rows. (Stratex-Daemon reported inactive on S1,
  as before — it is not probed as a live agent.)
- Observation for Muse (not a VAL-006 failure): the S2 job shows Futuris
  NRestarts=10 (since Sat 2026-11-21 20:12:08 IST) — above the workflow's
  >5 crash-loop suspicion threshold — while active and answering 200.
  Pre-existing, not caused by this change; whether the workflow's warning
  fired was not verified from the excerpted logs. Suggest a look at why
  Futuris restarted 10 times.
- NOT yet verified: the fresh fleet-status answer (needs the deploy
  below). CI on this PR: first run had one failure — the `contracts`
  check failed on the test-collection guard (mesh test uncollected);
  fixed by change 7 above, re-check pending at the time of writing.

— Muse 14, TASK-VAL-006, 2026-11-22 ~23:55 IST
