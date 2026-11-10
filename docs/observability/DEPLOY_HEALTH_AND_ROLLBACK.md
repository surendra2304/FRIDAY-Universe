# Deploy Health, Crash-Loop Alerting & Rollback — Runbook (TASK-OBS-001 + TASK-OBS-002)

**Owner:** Surendra · **Implemented:** 2026-11-10, ZAI · **Status:** code + tests merged with this commit; server activation is two `systemctl enable` calls (owner action, below).

## 1. The problem this closes

Every fleet unit runs with `Restart=always`. That keeps services alive, but it also makes a **crash loop invisible**: a unit that dies every 20 seconds still shows `active (running)` in `systemctl status`. Separately, the Fleet CD workflow deploys with `git fetch origin main && git reset --hard origin/main` — one bad commit on `main` resets both servers into a broken state, and until now there was no tested rollback path.

## 2. What now exists

### 2.1 Crash-loop and health alerting (TASK-OBS-001)

| Piece | File | What it does |
|---|---|---|
| Watcher | `scripts/fleet_health_watcher.py` | Per cycle: reads `systemctl show <unit> -p NRestarts/ActiveState/SubState`, probes `http://127.0.0.1:<port>/health`, and raises four alert classes — `CRASH_LOOP` (NRestarts delta ≥ 3 in one window), `SERVICE_DOWN`, `HEALTH_FAIL`/`HEALTH_UNREACHABLE`, and `RECOVERED` (auto-closes an incident). Deduplicates within a cooldown, persists state across its own restarts, never crashes on a failed probe. |
| Systemd wiring | `deploy/fleet-health-watcher.{service,timer}` | Runs the watcher every 5 minutes. Per-server fleet map via `FLEET_WATCH_SERVICES`; optional alert forwarding via `FLEET_ALERT_COMMAND` (receives `FLEET_ALERT_TEXT`/`FLEET_ALERT_JSON`). |
| Deploy-side gate | `.github/workflows/deploy-monorepo.yml` (health-gate step) | After each deploy's restarts, probes every restarted agent over HTTP for up to 60 s, prints `NRestarts` per unit, warns on >3 restarts, and **fails the deploy job** on any unhealthy agent — a silent crash loop now turns into a red X on the commit. |
| Tests | `tests/test_fleet_health_watcher.py` | 26 unit tests over the decision logic (deltas, recovery, cooldowns, persistence, daemon units, graceful degradation). |

### 2.2 Rollback for a bad deploy (TASK-OBS-002)

| Piece | File | What it does |
|---|---|---|
| Rollback script | `scripts/rollback_deploy.sh` | On a server: validates the target commit, **refuses anything that is not an ancestor of the deployed HEAD** (rollback-only, cannot roll forward or sideways), shows the affected services from the folder diff, `git reset --hard <target>`, restarts only affected units, health-checks each for 60 s, writes an append-only JSON receipt to `/var/lib/friday-universe/rollback-receipts/`. Modes: `--dry-run`, `--yes`, `--json`; interactive confirmation by typing `rollback`. |
| One-click workflow | `.github/workflows/rollback-deploy.yml` | `workflow_dispatch` with `target_sha` + typed confirmation (`rollback`) + optional dry-run; runs the script on BOTH servers via the existing CI SSH secret, then re-probes all ten agents through the public gateway. |
| Guard tests | `tests/test_rollback_deploy.py` | 8 tests against a throwaway git fixture: rejects non-commit / same-HEAD / forward / sideways targets, accepts true ancestors, dry-run changes nothing, unconfirmed run aborts, affected-service detection from the folder diff. |

## 3. Server activation (owner action, 2 commands per server)

```bash
sudo cp deploy/fleet-health-watcher.service deploy/fleet-health-watcher.timer /etc/systemd/system/
# Server 2 only: edit the service Environment line to
#   FLEET_WATCH_SERVICES=Sentinel:8008,Cortex:8009,VyralX:8010,VyralX-Daemon:-
sudo systemctl daemon-reload && sudo systemctl enable --now fleet-health-watcher.timer
```

Optional alert forwarding (any command; example for a webhook):
`Environment=FLEET_ALERT_COMMAND=curl -s -X POST https://example/hook -d "$FLEET_ALERT_TEXT"`

## 4. Decision guide: roll back vs fix forward

| Situation | Action |
|---|---|
| Deploy health gate red, cause obvious and small (typo/test) | Fix forward — revert the commit, push; Fleet CD redeploys. |
| Deploy health gate red, cause unclear | Roll back: Actions → "Fleet Rollback (manual)" → paste the last known-good SHA from the previous green deploy run → type `rollback`. Then investigate with the fleet watcher state + `journalctl -u <unit>`. |
| One agent degraded for hours (watcher alerts) but rest fine | Do NOT roll back the whole fleet; restart/fix the single unit (`sudo systemctl restart <unit>`), check NRestarts history in the watcher state file. |
| Bad commit already merged but not yet deployed | Just push the revert — the deploy never happened; no rollback needed. |

## 5. Evidence trail

- Watcher state: `/var/lib/friday-universe/fleet-health-state.json` (per server; includes NRestarts baselines and open alerts).
- Rollback receipts: `/var/lib/friday-universe/rollback-receipts/*.json` (append-only).
- Deploy health-gate output: the Fleet CD workflow job log (with `NRestarts` per unit at deploy time).
- Live validation snapshots: "Fleet Live Validation" workflow logs + `docs/validation/`.
