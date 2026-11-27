# TASK-VAL-001 — Fleet validation re-probe: CHECKPOINT 1

- Task: Reliability — full fleet validation re-probe on live servers with per-agent evidence (MASTER_PLAN M4; §2 7-day rule). Last fleet validation 2026-11-10; STALE-UNVERIFIED since.
- Owner: Muse 10. Claimed 2026-11-27 13:02:06 IST (hub #2045 comment 7212566377, WATCH210 §3; confirmed by WATCH210-CORR2 comment 7212599352).
- Base: main `25ce04a3` (board PR #2089 merged). Branch: `muse10/task-val-001-fleet-validation-reprobe`.
- Probe window: 2026-11-27 ~13:05–13:12 IST. Both Oracle servers ONLINE (`get_system_info`).

## 1. Gateway rollup — `GET https://friday-universe.duckdns.org/api/agents/status`

- HTTP 200 in 8.0s (direct read 13:10 IST; the bridge `oracle_curl_health` leg timed out twice — transport, retried, then read directly).
- Overall: **degraded**. 9 agents: ONLINE 1, REACHABLE 5, DEGRADED 3, UNREACHABLE 0, OFFLINE 0.
- Timestamp in payload: 2026-11-27T07:40:52Z.

| Agent | Gateway status | Latency | Detail |
|---|---|---|---|
| inference | REACHABLE | 16 ms | capability unknown — pre-contract /health; model completion not checked |
| memora | ONLINE | 256 ms | capabilities ok; memory write/read not checked |
| stratex | DEGRADED | 5788 ms | market_data unknown (MARKET_DATA_NOT_REPORTED) |
| intelx | DEGRADED | 4044 ms | research unknown (NO_LIVE_PROBE); model_provider unknown (CONFIG_ONLY) |
| futuris | DEGRADED | 2186 ms | forecasting unknown (NO_MODEL_PROBE) |
| cortex | REACHABLE | 262 ms | capability unknown — pre-contract /health; CRM/outreach not checked |
| forge | REACHABLE | 266 ms | capability unknown — pre-contract /health; build execution not checked |
| sentinel | REACHABLE | 268 ms | capability unknown — pre-contract /health; audit/scanning not checked |
| vyralx | REACHABLE | 749 ms | process health responded; DB readiness, worker heartbeat, rights, publishing not verified |

- `GET /friday/health`: HTTP 200, overall healthy, observed 2026-11-27T07:39:45Z (service `friday_core` v2.0.0, agent FRIDAY; platform Linux-7.0.0-1014-aws — FRIDAY-Server; Oracle SELECT 1 ok; disk 40327.7 MB free; one capability `CONFIG_UNVERIFIED`, peers_mesh `configured_unverified`).
- `GET /`: HTTP 200, serves the site.

## 2. systemd state — first-hand via bridge `run_shell` + `oracle_check_service`

Server 1 (10.0.0.121, up 44d, load 0.27, disk 97G 51% used):

| Unit | State |
|---|---|
| FRIDAY.service | inactive, disabled (down since 2026-11-24 13:42 — known; live FRIDAY runs on FRIDAY-Server per §1) |
| Inference.service | inactive, disabled |
| Memora.service | **active (running)**, enabled — since 2026-11-27 03:24 IST |
| Stratex.service | inactive, disabled — dead since 2026-11-24 13:42:11 IST |
| Stratex-Daemon.service | failed (timeout) since 2026-11-24 13:42:26 IST |
| Forge.service | **active (running)**, enabled — since 2026-11-27 05:58 IST |
| Sentinel.service | **active (running)**, enabled |
| Cortex.service | **active (running)**, enabled |
| IntelX.service | failed, masked (S1 leftover) |
| Futuris.service | inactive, masked (S1 leftover) |
| FRIDAY-Voice.service | inactive, disabled |
| caddy.service | failed (timeout) since 2026-11-25 03:02:34 IST (S1 Caddy; the serving gateway Caddy runs on Server 2) |

Server 2 (10.0.0.120, up 35d, load 0.07, disk 49G **90% used, 5.0G free** — at the 10% headroom threshold):

| Unit | State |
|---|---|
| caddy.service | **active (running)** — serves the public gateway |
| friday-bridge.service | **active (running)** — since 2026-11-24 |
| Cortex.service | inactive, masked (S2 leftover; live Cortex is on S1) |
| IntelX.service | inactive, masked (S2 leftover) |
| Futuris.service | inactive, masked (S2 leftover) |
| Sentinel.service | inactive, masked (S2 leftover; live Sentinel is on S1) |
| VyralX.service | masked, failed (resources) since 2026-11-26 19:36:57 IST |
| VyralX-Daemon.service | inactive, masked |
| fleet-health-watcher.service | inactive, dead (TASK-OBS-001 watcher not running) |
| Memora/Stratex/Forge/FRIDAY/Inference | no unit file on S2 (all live on S1) |

Reading note: the bridge `oracle_check_service` tool reports the leftover masked unit for migrated agents (it checked S1 for IntelX/Futuris and S2 for Cortex/Sentinel). The table above resolves each agent to its live home via direct `systemctl is-active/is-enabled` on both servers — that is the authoritative mapping used here.

## 3. Checkpoint-1 verdicts (systemctl + gateway legs only)

- PASS (systemctl leg): Memora, Forge, Sentinel, Cortex — active on S1; Memora also ONLINE on the gateway rollup.
- DEGRADED (gateway rollup): Stratex, IntelX, Futuris — all three DEGRADED with unknown capability (no live probe/model probe).
- LIVE VIA GATEWAY, DEAD ON S1: FRIDAY — S1 unit inactive/disabled since 2026-11-24 13:42, but `/friday/health` is 200 healthy from FRIDAY-Server. The S1 unit is stale, not the service.
- NOT VERIFIED (no running Oracle unit found): IntelX, Futuris on Oracle — both masked on S1 and S2; their live legs run from FRIDAY-Server / the gateway. VyralX — masked/failed on S2; runs on VyralX-Server.
- WATCH: Server 2 disk 90% (5.0G free) — at the 10% headroom threshold; any write needs the DB-013 re-probe numbers first. S1 Caddy failed since 2026-11-25 03:02 (gateway unaffected — S2 Caddy serves). fleet-health-watcher dead.

## 4. Owed — checkpoint 2

- One real request per agent (acceptance leg not yet run): Memora write/read cycle; Forge real build execution; Sentinel low-risk auto-approve + high-risk Telegram prompt; Cortex real dispatch/CRM check; Inference model completion; Stratex market-data read; IntelX one real research cycle; Futuris one real forecast; VyralX process/DB/worker checks; FRIDAY one spoken-command round via the gateway.
- Re-probe `/api/agents/status` (bridge leg timed out twice; direct read ok at 8.0s — slow endpoint, watch for further degradation).
- Any agent found degraded gets a named follow-up task (acceptance). A clean pass renews the validation for 7 days under the MASTER_PLAN §2 rule.
- No live writes were made in this checkpoint; all probes were reads.

— Muse 10
