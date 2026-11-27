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

## 5. CHECKPOINT 2 — re-probe (16:08–16:11 IST) + acceptance-leg status

- Probe window: 2026-11-27 ~16:08–16:11 IST. Both Oracle servers ONLINE (`get_system_info`). Base: main `f5374e4c`. Branch re-created post-merge as `muse10/task-val-001-fleet-validation-reprobe` (checkpoint-1 branch was deleted after PR #2094 merged, per team practice).
- All probes in this checkpoint were reads. No live writes made.

### 5.1 Gateway rollup re-probe — `GET https://friday-universe.duckdns.org/api/agents/status`

- HTTP 200 in 9.2s (direct read 16:08 IST). Overall: **degraded**. 9 agents: ONLINE 1, REACHABLE 5, DEGRADED 3, UNREACHABLE 0, OFFLINE 0. Payload timestamp: 2026-11-27T10:38:09Z.
- Same counts and same three DEGRADED agents as checkpoint 1 (13:10 IST). Latencies up slightly: stratex 5788→6847 ms, intelx 4044→4580 ms, futuris 2186→2705 ms; memora ONLINE 832 ms (was 256 ms); inference REACHABLE 36 ms; cortex 805 ms; forge 815 ms; sentinel 812 ms; vyralx 1300 ms.
- `GET /friday/health`: HTTP 200 in 3.2s, overall healthy, observed 2026-11-27T10:38:11Z (service `friday_core` v2.0.0, agent FRIDAY; Oracle SELECT 1 ok; disk 40243.8 MB free; peer_mesh `CONFIG_UNVERIFIED` — unchanged).

### 5.2 systemd re-probe — first-hand via bridge `run_shell` (16:09 IST)

- Server 1 (up 44d, load 0.08, disk 97G 48% used, 51G free — was 51% at checkpoint 1): UNCHANGED — Memora/Forge/Sentinel/Cortex active (running), enabled; FRIDAY/Inference/Stratex inactive, disabled (Stratex dead since 2026-11-24 13:42:11 IST); Stratex-Daemon failed; IntelX failed, masked; Futuris inactive, masked; FRIDAY-Voice inactive, disabled; caddy failed, enabled (since 2026-11-25).
- Server 2 (up 35d, load 0.37): UNCHANGED — caddy active (serves the public gateway); friday-bridge active; Cortex/IntelX/Futuris/Sentinel inactive, masked (leftovers); VyralX failed, masked; VyralX-Daemon inactive, masked; fleet-health-watcher inactive (static — not running).

### 5.3 WATCH — Server 2 disk deteriorating (NEW)

- S2 `/`: **95% used, 2.9G free at 16:11 IST** — confirmed twice this run (94% / 3.0G at 16:09 → 95% / 2.9G at 16:11). Was 90% / 5.0G at 13:05 (checkpoint 1) and 91% / 4.9G at 15:40 (TP8, hub 7215574847). Below the 10% headroom threshold and falling.
- Largest consumers: `/tmp` 4.1G; `/opt/friday_universe` 5.0G (venv 1.8G + venv312 1.6G + FRIDAY 723M + Cortex 279M + Memora 271M); `/var/log` 432M; journals 212M.
- No cleanup done — no clearance, and `/tmp` may hold other workers' live work. Coordinator ruling owed before any S2 write.

### 5.4 Acceptance leg — one real request per agent: NOT RUN this checkpoint

- Still owed (all 10): Memora write/read cycle; Forge real build execution; Sentinel low-risk auto-approve + high-risk Telegram prompt; Cortex real dispatch/CRM check; Inference model completion; Stratex market-data read; IntelX one real research cycle; Futuris one real forecast; VyralX process/DB/worker checks; FRIDAY one spoken-command round via the gateway.
- Reason: this run is the hourly self-check; the acceptance leg is multi-hour live work, and the per-agent real-request routes are not the `/health` paths the gateway reports — each route must be resolved first. Next work run: resolve routes, then run the leg.
- The three DEGRADED agents (Stratex, IntelX, Futuris) still have unknown capability — no live probe/model probe exists for them yet.

### 5.5 Checkpoint-2 verdicts

- UNCHANGED (gateway + systemctl legs): same degraded rollup, same unit states as checkpoint 1.
- NEW ALERT: S2 disk 95% / 2.9G free and falling — coordinator ruling owed.
- Task stays IN_REVIEW; validation NOT renewed (acceptance leg outstanding; three agents still DEGRADED with unknown capability).

— Muse 10
