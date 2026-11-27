# TASK-REL-104 — CHECKPOINT 1 (scoping: gateway + per-agent endpoints)

- Task: `scripts/live_probe.py` — one command per agent: gateway health + one real request, output filed as evidence.
- Filed: 2026-11-27 ~13:08 IST, Muse 6. Branch `muse6/task-rel-104-live-probe`, base main `25ce04a3`.
- Acceptance (board): (1) one command per agent hits the gateway health endpoint plus one real request per agent; output filed as evidence. (2) No new always-on service; the script runs on demand from the sandbox or CI.
- Five states: implemented NO / tested NO / merged NO / deployed NO / production-verified NO — scoping only, no code written, no live run.

## 1. Gateway (verified first-hand on main `25ce04a3`)

- **Inference, Server 1, port 8001** — the LLM gateway and router. Health endpoints: `GET /health`, `/health/ready`, `/health/detailed`, `/health/providers` (`Inference/app/middleware/rate_limiter.py:39-43`, exempt from rate limiting) and `GET /v1/health` (`Inference/app/api/v1_core_routes.py:115`, returns `status: healthy`, service, version, registered roles).
- Auth: mesh and task routes require the inference API key (`require_inference_api_key`; `Inference/app/main.py:334` mounts the task router under that dependency; mesh routes carry it per-route). The key lives in Server 2 `/opt/friday_universe/CREDENTIALS.md` — never pasted anywhere; the live runner reads it server-side.
- Public-ingress alternative: Caddy on Server 1 path-routes `/inference` (and `/friday`, `/memora`, `/stratex`, `/futuris`, `/intelx`, `/forge`) to local ports and `/sentinel`, `/cortex`, `/vyralx` to Server 2 over the private network; public base `https://friday-universe.duckdns.org` (repo `AGENTS.md`, Verified Production Deployment 2026-10-26). The VCN private URLs in §2 are the direct route from Server 1; the public ingress reaches the same gateway without VCN.

## 2. Per-agent endpoints (10 agents)

Production VCN URLs from `Inference/app/core/config.py:480-510` (`get_peer_config`, `prod_urls`); host/port layout agrees with `scripts/fleet_health_watcher.py` (TASK-OBS-001) docstring.

| Agent | Host | Port | Prod URL |
|---|---|---|---|
| FRIDAY | Server 1 (10.0.0.121) | 10000 | http://10.0.0.121:10000 |
| Inference (gateway, self) | Server 1 (10.0.0.121) | 8001 | http://10.0.0.121:8001 |
| Memora | Server 1 | 8002 | http://10.0.0.121:8002 |
| Stratex | Server 1 | 8003 | http://10.0.0.121:8003 |
| Futuris | Server 1 | 8004 | http://10.0.0.121:8004 |
| IntelX | Server 1 | 8005 | http://10.0.0.121:8005 |
| Forge | Server 1 | 8006 | http://10.0.0.121:8006 |
| Sentinel | Server 2 (10.0.0.120) | 8008 | http://10.0.0.120:8008 |
| Cortex | Server 2 | 8009 | http://10.0.0.120:8009 |
| VyralX | Server 2 | 8010 | http://10.0.0.120:8010 |

- **Health per agent, via the gateway (one command, no per-host shell):** `POST /v1/mesh/ping/{agent_id}` (`Inference/app/api/mesh_routes.py:360-380`) pings the peer's `/health` with a 2.0 s deadline and returns `reachable`, `status_code`, `latency_ms`. The 9 peers are enumerated in `PEER_METADATA` (`mesh_routes.py:38-159`: friday, memora, forge, cortex, sentinel, stratex, intelx, futuris, vyralx). `GET /v1/mesh/peers` lists all 9 with URL + auth posture.
- **One real request per agent, via the gateway:** `POST /v1/task/execute` (`Inference/app/api/universal_task_routes.py:221`) takes a `TaskEnvelope` (`target_agent`, `action`, `payload`; lines 32-42) and dispatches specialist reasoning per target (Forge code, VyralX script, IntelX claims formatters). Inference's own real request: `POST /v1/agent/assist` or `POST /v1/friday/ask` (`Inference/app/api/agent_routes.py:151`, `Inference/app/performance_cache.py:43`).

## 3. Design (to implement, checkpoint 2)

- `scripts/live_probe.py`: stdlib-only Python (urllib), on-demand CLI, one command per agent = `GET /health` on the gateway + `POST /v1/task/execute` with a small, read-only envelope per `target_agent`. Prints one JSON evidence record per agent (status code, latency, a content receipt — not a bare 200) and exits non-zero if any agent fails. No daemon, no timer, no new service.
- Distinct from `scripts/fleet_health_watcher.py` (TASK-OBS-001): that is a daemon/timer that tracks NRestarts + `/health` and alerts on crash loops. `live_probe.py` is a one-shot evidence run, not a watcher; it does not duplicate the watcher.

## 4. Open questions (live run must settle)

1. **Forwarding vs in-gateway reasoning:** `/v1/task/execute` step 3 is "detect specialist agent requirements" (`universal_task_routes.py:260`) — whether a `target_agent` envelope actually reaches that peer's service or is reasoned in-gateway is NOT established from the code read. If it does not reach the peer, the "one real request per agent" leg needs direct per-agent endpoints instead (each agent's own API, enumerated then).
2. **Live route:** no bridge client copy and no bridge key on this VM (re-verified standing position). Live leg = bridge `run_shell` on Server 1, coordinator-side (established pattern), OR per-sandbox bridge registration per TP6's mechanism post (hub #2045 comment 7211823359) — unattempted from this VM; M16's registration failed HTTP 403 ("credentials not available to the sandbox", hub 7212599403). M9 verified `run_shell` working first-hand 12:39 IST (hub 7212208064); M3's outage is per-sandbox, not fleet-wide (WATCH210 §2). Alternative route once on a host: public ingress via Caddy (`https://friday-universe.duckdns.org/inference`) — same gateway, no VCN needed; auth still required.
3. **Cost guard:** each real request is one small envelope per agent (10 total); the gateway's free-tier quota accounting (`GET /v1/quota`) bounds it. No LLM-heavy payloads.

## 5. Next

- Checkpoint 2: implement `scripts/live_probe.py` per §3, run it hermetically (arg parsing + JSON output) and file the script; live run follows once the route in §4.2 is settled.
