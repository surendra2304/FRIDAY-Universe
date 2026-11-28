# TASK-INT-063 — IntelX: deploy INT-060 transport + live proof of fast-lane transport: checkpoint 1 (claim + pre-deploy state, 2026-11-28 ~10:50 IST)

**Task:** TASK-INT-063 (P1) — "IntelX: deploy INT-060 transport (endpoint 404 both lanes) + live proof of fast-lane transport".
**Worker:** Muse 10. **Claim:** hub #2045 comment 7234554674, 2026-11-28 ~10:45 IST, on assignment Burn Enforcer 10:45 §C (hub 7234528840) — INT-063 → Muse 10 as head, direct sequel to merged INT-062.
**Branch:** `muse10/task-int-063-deploy-int-060-transport-live-proof`, created from main `7ecab6ce`.
**Usage:** 4% of free weekly limit (verified this run; resets Dec 5 02:03 IST).

## Verdict

**PRE-DEPLOY STATE FILED — nothing deployed yet.** The INT-060 HTTP transport code is merged (PR #2076) and present in both Oracle checkouts, but no IntelX process serves the endpoint anywhere: S1 IntelX masked + failed since 2026-11-20, S2 has no process and no watch data; S1 FRIDAY down since 2026-11-24; gateway `GET /intelx/v1/watches/outbox` → 404; S1 FRIDAY env has no `INTELX_WATCH_OUTBOX_URL` / `INTELX_WATCH_API_KEY`. Kill switch OFF. No live change made anywhere. This is a checkpoint, not a completion.

## Producer — Server 2 (~10:47 IST, read-only)

- **No IntelX process.** `ps aux | grep -iE 'intelx|uvicorn'` returns nothing on S2.
- **Watch data still gone.** `IntelX/data/` holds only `test_intelx.db` (413,696 bytes, Nov 27 13:45) — a test artifact, not watch data. No `watches/` subdirectory, no `outbox.jsonl`, no `state.json`, no `*.jsonl` under `IntelX/` at any depth.
- **S2 disk 89% used / 5.5G free** — above the 10% headroom line (was 96% / 2.4G at 10:20 IST per M19's re-probe; headroom has recovered).
- **Route present in the S2 checkout code:** `IntelX/intelx/api/router.py:105 @root_api_router.get("/v1/watches/outbox")` — the INT-060 code is on disk, just not running.
- S2 shared checkout still on `musetp4/task-frg-036-rerun3-evidence` @ `69ff042b` (TP4's FRG-036 Leg B re-run) — read-only probes only, nothing switched.

## Consumer — Server 1 (~10:47 IST, read-only)

- **FRIDAY still down.** `FRIDAY.service` inactive (dead), loaded but disabled — down since the 2026-11-24 13:42 IST graceful shutdown. No FRIDAY uvicorn; running uvicorns are 8002 Memora, 8006 Forge, 8008 Sentinel, 8009 Cortex.
- **S1 IntelX.service masked + failed** (timeout) since 2026-11-20 23:56:31 IST (re-confirmed this run).
- **Drainer state untouched.** `FRIDAY/state/proactive_intelx_watch.json` contents unchanged from INT-062: offset 3644, instant_offset 0, same 4 delivered_keys, held [], alert_log last entry 2026-11-20 19:16 IST.
- **S1 outbox unchanged.** `IntelX/data/watches/outbox.jsonl` still 1,823 bytes, mtime Nov 23 22:03 — the same 2 digest-class envelopes (scores 4 and 5, both below the instant bar of 6). No new envelope, no instant-class alert.
- **S1 disk 55% used / 45G free** — healthy.
- **Env wiring not done.** S1 `FRIDAY/.env` has no `INTELX_WATCH_OUTBOX_URL` and no `INTELX_WATCH_API_KEY`. Route present in the S1 checkout code too (`router.py:105`).

## Gateway (~10:47 IST)

- `GET https://friday-universe.duckdns.org/intelx/v1/watches/outbox` → **404 `{"detail": "Not Found"}`** — the endpoint is not deployed.
- `GET https://friday-universe.duckdns.org/friday/health` → 200 healthy (FRIDAY-Server, AWS Linux 7.0.0-1014-aws) — not the S1 consumer that hosts the drainer.
- Both Oracle servers ONLINE (`get_system_info`, this run).

## Kill switch — OFF, verified, untouched

- `FRIDAY_PROACTIVE_INTELX_WATCH=on` at S1 `FRIDAY/.env:77`. Watch on = kill switch off. No flag, config, service, or file was changed by this run.

## Deploy plan (INT-060 evidence §Deploy steps) + clearance owed

1. Deploy IntelX (new endpoint) and FRIDAY (remote drainer source).
2. Set on FRIDAY-Server: `INTELX_WATCH_OUTBOX_URL=https://friday-universe.duckdns.org/intelx/v1/watches/outbox` and `INTELX_WATCH_API_KEY` (FRIDAY's existing IntelX API key; value stays server-side). Restart FRIDAY.
3. Then probe both lanes (main + instant) + armed-state re-probe.

**Clearance owed (coordinator):** deploy + restart authority — which host serves `/intelx` (IntelX-Server vs S2), whether the S1 FRIDAY restart is approved (G4 carried since Nov 24), and the S2 shared-checkout switch (currently on TP4's branch). No restart, env edit, or checkout switch attempted this run — standing rule: no deployments without Muse's hub clearance.

## Gates (carried from INT-062)

- **G1 — bridge run_shell clearance: STANDS.** Coordinator correction 7197725825; this run's read-only probes ran under it.
- **G2 — S1/S2 handoff gap (INT-019 edge).** The HTTP transport is the fix; deploy pending.
- **G3 — S2 producer down + watch data gone.** No IntelX process, no outbox, no state.json.
- **G4 — S1 consumer (FRIDAY) down since 2026-11-24 13:42 IST.** Restart decision is the coordinator's.

## States

- Implemented: YES (INT-060 merged PR #2076; code present on both checkouts)
- Tested: NO (no live endpoint to probe yet)
- Merged: NO (work PR this run carries checkpoint 1 only)
- Deployed: NO — endpoint 404
- Production-verified: NO

## Files

- This evidence doc: `docs/collaboration/TASK-INT-063-EVIDENCE.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-INT-063 AVAILABLE / owner null on main `7ecab6ce`; claim flip rides the coordinator board PR — no board hunk in this PR, per the coordinator-only flip rule)
- INT-060 evidence: `docs/collaboration/TASK-INT-060-EVIDENCE.md`
- INT-062 evidence: `docs/collaboration/TASK-INT-062-EVIDENCE.md`

— Muse 10, 2026-11-28 ~10:50 IST

---

## Checkpoint 2 — IntelX-Server probe (WATCH260 §F, 2026-11-28 ~12:20 IST)

**Direction:** WATCH260 §F (hub #2045 comment 7235389912, ~12:05 IST): "M10 INT-063 clearance: unchanged — M10's IntelX-Server probe first (M10 owner); #2278 verdict due ~13:00." Clearance still NOT granted; this probe is the named precondition. Both Oracle servers ONLINE (`get_system_info`, this run); usage 4% (resets Dec 5 02:03 IST).

**Finding: IntelX-Server (S6, ip-172-26-4-138) IS the IntelX host — IntelX is LIVE there, but on pre-INT-060 code.**

- **Process up.** Bare uvicorn PID 46018, `intelx.app.main:app --host 0.0.0.0 --port 8005 --workers 1`, cwd `/opt/friday_universe/IntelX`, started Fri Nov 27 05:13:15 UTC (10:43 IST). No `intelx.service` systemd unit — it is not a managed service. Port 8005 LISTEN; port 8004 is Futuris (PID 63602).
- **Endpoint NOT served.** `GET http://127.0.0.1:8005/v1/watches/outbox` → 404 `{"detail":"Not Found"}`; `/` → 307. The running app's OpenAPI route list (~200 routes) has no `watches/outbox` anywhere.
- **On-disk code predates INT-060.** `grep -rn 'watches/outbox'` over `IntelX/intelx/api/router.py` + `api/v1/` → no match. `router.py` mtime Nov 15, `app/main.py` Oct 23. INT-060 (PR #2076) merged Nov 27 06:27:46 UTC (11:57 IST) — 74 minutes AFTER this process started. `/opt/friday_universe` on S6 is a deployed copy, not a git checkout (no `.git`; holds only Futuris, IntelX, mesh, venvs).
- **Watch loop LIVE and producing.** `IntelX/data/watches/outbox.jsonl` — 6 envelopes, 5,608 bytes, mtime Nov 27 21:44 UTC (Nov 28 03:14 IST); last envelope `india_tech_regulatory` digest ("RBI Clubs 25 Card Payment Circulars Into A Single Framework"). `state.json` (1,554,808 bytes) mtime Nov 28 06:45 UTC — rewritten minutes before this probe; `alerts_by_day` 2026-11-23: 1, 2026-11-24: 1, **2026-11-28: 1**. `data/raw/` has fresh fetches Nov 28 04:00 UTC. S6 disk 13% used / 51G free — healthy.
- **Gateway unchanged.** `GET https://friday-universe.duckdns.org/intelx/v1/watches/outbox` → 404 (re-probed this run).

**Deploy shape (for the coordinator's clearance):** sync current main code to S6 + restart the bare uvicorn (PID 46018; kill + relaunch, no systemd unit to restart) → the route should then answer on localhost:8005; gateway routing to S6:8005 + FRIDAY consumer env/restart (G4) still owed. No code, process, env, or file was changed by this run — read-only probes only.

**Clearance still owed:** deploy + restart authority (S6 code sync + uvicorn restart; gateway route to S6; S1 FRIDAY restart G4; S2 shared-checkout switch still on TP4's branch @ `69ff042b` per `get_system_info` this run). No deploy performed.

## States (updated)

- Implemented: YES (INT-060 merged PR #2076)
- Tested: NO (no live endpoint to probe yet — S6 serves IntelX, but not the new route)
- Merged: NO (PR #2278 open — this checkpoint rides the same PR; head was `a62e6f4a`, CI 9/9 green before this commit)
- Deployed: NO — endpoint 404 on gateway and on S6 localhost
- Production-verified: NO

— Muse 10, 2026-11-28 ~12:20 IST


---

## Checkpoint 3 — DEPLOYED to S6 (WATCH264 §C + BE 14:00 §B, 2026-11-28 ~14:22–14:27 IST)

**Direction:** WATCH264 §C (hub #2045 comment 7236513660): "INT-063 deploy: M10, deploy to S6 now" under WATCH263 ruling D.3 (#2278 merged; target S6 per probe #1239). Adopted BE 14:00 §B (hub 7236649802): "M10 → deploy INT-063 to S6 NOW". Hub clearance granted; PR #2278 MERGED 13:42 IST (merge `38887ed5`, by Surendra). Main now `c339c31b` (#2184 merged after).
**Branch for this checkpoint:** `muse10/task-int-063-deploy-checkpoint-3`, from main `c339c31b`.

**Verdict: DEPLOYED — the INT-060 endpoint is live on IntelX-Server and on the gateway.** No gateway config change was needed: `/etc/caddy/Caddyfile:91 handle_path /intelx*` already proxies to S6:8005 (healthz 200 before and after).

**Deploy steps (executed):**
- Pre-deploy state re-verified: S6 on-disk code still pre-INT-060 (`router.py` Nov 15, no `watches/outbox`); running uvicorn PID 46018 (started Nov 27 05:13 UTC) served 404 on the route; OpenAPI had no outbox route. S6 is a deployed copy, not a git checkout.
- Sync: `git clone --depth 1` of main (`c339c31b`) to `/tmp/friday_clone` on S6, then rsync `IntelX/` → `/opt/friday_universe/IntelX/` excluding `data/`, `intelx/.data/`, `.env`, `.env.pre-int021-20261122`, `__pycache__/`, `*.pyc`, `.git`, `.ruff_cache/` — with `--delete`. Backup first: pre-deploy code tree copied to `/opt/friday_universe/IntelX-backup-20261128-int063` (5.0M, data/ excluded; `data/` untouched in place). Post-sync `diff -rq` → TREES_MATCH (only the excluded local files differ). `.env` preserved (mode 600, mtime Nov 24, 2,316 bytes — not read, not changed). `requirements.txt` content-identical to main — no pip install needed. Note: two early rsync dry-runs returned 0 files (unreliable); the itemized dry-run listed 552 lines and the post-sync diff is the ground truth.
- Import check before restart: `from intelx.app.main import app` IMPORT_OK; `root_api_router` carries `/v1/watches/outbox` GET. Note: FastAPI 0.165.0 defers sub-router inclusion (`_IncludedRouter` placeholders; `app.routes` shows 7 at import time) — the route is proven by `app.openapi()`: 186 paths including `/v1/watches/outbox` GET.
- Restart: SIGTERM to PID 46018 (gone, port 8005 free), relaunch with the exact original command (`/opt/friday_universe/venv/bin/python -m uvicorn intelx.app.main:app --host 0.0.0.0 --port 8005 --workers 1`, cwd `/opt/friday_universe/IntelX`, `PYTHONPATH=/opt/friday_universe/IntelX:/opt/friday_universe`, `setsid nohup`, log `/opt/friday_universe/IntelX/uvicorn-8005.log`). New PID 74894, started Nov 28 08:52:39 UTC (14:22 IST). Startup log: production mode, DB engine initialised, schemas/indexes initialized, API keys seeded, "IntelX standing watches started: ai_model_releases, india_tech_regulatory", "Application startup complete".
- Note: the bridge `run_shell` call that launched the restart hit its 180s timeout after all verification steps had printed; the new process survived (setsid, new session) — re-verified alive in a fresh call ~4 min later.

**Live verification (fresh calls after restart):**
- S6 localhost: `GET 127.0.0.1:8005/v1/watches/outbox` → **401** `{"detail":"Missing Friday API Key. Provide via 'Authorization: Bearer <key>' or 'X-API-Key: <key>' header."}` (was 404 — the route is mounted; 401 is the auth gate, not an error). `?lane=instant` → 401. `/openapi.json` contains `watches/outbox`. `/` → 307 (unchanged).
- Gateway: `GET https://friday-universe.duckdns.org/intelx/v1/watches/outbox` → **401** (was 404); `?lane=instant` → 401; `/intelx/healthz` → 200; `/friday/health` → 200.
- Watch loop resumed: `state.json` rewritten 08:52:52 UTC (seconds after restart); both watches ran (`ai_model_releases` fetched=2369 dup=2369, `india_tech_regulatory` fetched=64 dup=64, alerted=0 — all duplicates, no new alert). `outbox.jsonl` unchanged (sha256 `ee4b4c1c…`, 5,608 bytes, 6 envelopes) — nothing lost.
- Futuris untouched: PID 63602 on :8004 still running.

**Still owed (not in this deploy order):** authenticated live proof — `GET …/v1/watches/outbox` with the FRIDAY API key returning 200 + the 6 envelopes, both lanes — and the consumer leg (FRIDAY-Server `INTELX_WATCH_OUTBOX_URL`/`INTELX_WATCH_API_KEY` + FRIDAY restart, G4). The key value was never read, copied, or put in any command. The 401 proves the route is mounted and gated; the 200 + drainer receipt ride the consumer leg / coordinator direction.

## States (updated)

- Implemented: YES (INT-060 merged PR #2076)
- Tested: YES (live endpoint probed on S6 localhost + gateway, both lanes; watch loop resumed)
- Merged: YES (PR #2278 merged 13:42 IST, merge `38887ed5`; this checkpoint rides a new PR)
- Deployed: YES — endpoint live on S6 :8005 and gateway, 401 without key (auth gate)
- Production-verified: NO (authenticated 200 + consumer drainer receipt still owed)

— Muse 10, 2026-11-28 ~14:27 IST
