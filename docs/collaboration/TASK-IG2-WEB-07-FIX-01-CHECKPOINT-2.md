# TASK-IG2-WEB-07-FIX-01 — Checkpoint 2: serving-host identification

- **Task:** TASK-IG2-WEB-07-FIX-01 (FIX: /start serves the ULTRON stage, not the GlassStartPage component)
- **Author:** Muse 10
- **Date:** 2026-11-26 ~23:30–23:50 IST
- **Direction:** Coordinator WATCH176 (hub #1483 comment 7199655255): identify which host actually serves `friday-universe.duckdns.org` and where the deployed code lives; file the identification as evidence. No deploy, no restart, until that is on the record.
- **Board:** main `df4e261b` (board blob `50fa2a8439`); branch `muse10/task-ig2-web-07-fix-01-checkpoint-2` from main `df4e261b`.

## Verdict: serving host IDENTIFIED

The public site is served by **FRIDAY-Server — AWS Sydney EC2 `15.134.130.145`** (`ec2-15-134-130-145.ap-southeast-2.compute.amazonaws.com`), FRIDAY app on port **10000**, behind **Oracle Server 2's Caddy** as the TLS ingress.

Deployment target for the checkpoint-1 fix (`FRIDAY/src/friday/api/server.py` +16, on main since PR #2001, merge `708e4041`): **the FRIDAY app on FRIDAY-Server (15.134.130.145:10000)**. No deploy was attempted this run; coordinator clearance is still required.

## Evidence chain (all read-only probes, 2026-11-26 ~23:30–23:40 IST)

### 1. DNS points at Oracle Server 2

- `getent hosts friday-universe.duckdns.org` on Server 2: `140.245.243.168`.
- Server 2's own public IP (`curl ifconfig.me` on Server 2): `140.245.243.168` — identical. The duckdns name resolves to Server 2, so Server 2 is the ingress.
- Server 1's public IP (`curl ifconfig.me` on Server 1): `140.245.208.100` — different. Server 1 is not the ingress.

### 2. Server 2 Caddy terminates TLS and proxies FRIDAY to the AWS host

- Caddy pid `648489`, running since Nov 25 (`/usr/bin/caddy run --environ --config /etc/caddy/Caddyfile`), listens on `*:80` and `*:443` (plus admin `127.0.0.1:2019`). Caddy service: active on Server 2.
- `FRIDAY.service`: inactive on Server 2. No FRIDAY uvicorn runs on Server 2 (only the bridge python on `:8011`, pid 641785).
- `/etc/caddy/Caddyfile` (relevant handles, verbatim):
  - `handle_path /friday*` → `reverse_proxy 15.134.130.145:10000`
  - `handle` (catch-all, serves the site root incl. `/start`) → `reverse_proxy 15.134.130.145:10000`
  - `/bridge*`, `/mcp*`, `/messages*` → `127.0.0.1:8011` (the bridge on Server 2)
  - `/inference*` → `10.0.0.121:8001`, `/memora*` → `10.0.0.121:8002`, `/forge*` → `10.0.0.121:8006`, `/sentinel*` → `10.0.0.121:8008`, `/cortex*` → `10.0.0.121:8009` (all Server 1)
  - `/stratex*` → `13.211.78.20:8003`, `/futuris*` → `32.236.185.237:8004`, `/intelx*` → `32.236.185.237:8005`, `/vyralx*` → `13.211.162.71:8010`
- So every FRIDAY-app request (root, `/start`, `/friday/*`) leaves Server 2 for `15.134.130.145:10000`.

### 3. The upstream at 15.134.130.145:10000 IS the FRIDAY app

- Direct probe `curl http://15.134.130.145:10000/health` returns the identical healthy JSON as the public `https://friday-universe.duckdns.org/friday/health` (observed 2026-11-26 18:03–18:05 UTC): `service: friday_core`, `version: 2.0.0`, `platform: Linux-7.0.0-1014-aws-x86_64-with-glibc2.39`, Python 3.10.22, `friday` + `friday_deep` imported, Oracle `SELECT 1 FROM DUAL` ok.
- Direct `curl http://15.134.130.145:10000/friday/health` returns 404 (StaticFiles headers) — expected: Caddy's `handle_path` strips the `/friday` prefix, so the upstream only ever sees `/health`. This confirms the Caddy→upstream path, not a different app.
- Reverse DNS: `15.134.130.145` → `ec2-15-134-130-145.ap-southeast-2.compute.amazonaws.com`.
- Team doc corroboration — `docs/collaboration/WORKER_PROMPT.md`: "FRIDAY-Server (AWS Sydney, 15.134.130.145) — FRIDAY + FRIDAY-Voice + Inference, live."

### 4. The "AWS kernel" string explained

- Checkpoint 1 noted the public site answering from an "unidentified AWS-kernel host". The `platform` field in the health JSON is `Linux-7.0.0-1014-aws-x86_64` — that is the Ubuntu AWS kernel flavour installed on the FRIDAY-Server EC2 host. There is no second mystery host; the string was the EC2 host's own kernel name.

### 5. Server 1 ruled out as the FRIDAY host

- `FRIDAY.service`: inactive (dead) on Server 1; Caddy: failed on Server 1; no `:80`/`:443` listeners on Server 1.
- Running uvicorns on Server 1 are Memora (`:8002`), Forge (`:8006`), Sentinel (`:8008`), Cortex (`:8009`) only — no FRIDAY app, no port 10000.

## What this means for the fix

- The checkpoint-1 fix is in the repo on main (`708e4041`) but the live `/start` still renders ULTRON (checkpoint 1, real browser 22:16 IST). The live app is the FRIDAY-Server copy at `15.134.130.145:10000`, not any Oracle-server checkout — so the fix reaches users only when it is deployed to FRIDAY-Server and its `:10000` app is restarted.
- The Oracle checkouts are not the deployed code: Server 2's shared checkout sits on the deleted branch at `410f0738` (behind main `df4e261b`); Server 1's checkout state was not re-verified this run.

## Open gaps (for the coordinator)

- **G1 — live checkout sha unobservable from here.** The AWS host's checkout sha cannot be read from Server 1/Server 2 (no SSH route from this run's vantage; TASK-INF-035 already recorded the same). Whether the live `:10000` app is at/after `708e4041` is unverified; the live ULTRON render is consistent with the fix not yet deployed, but is not proof of the sha.
- **G2 — deploy mechanism unidentified.** No deploy runbook for FRIDAY-Server was verified this run. Note only: Server 1 runs `inference-aws-tunnel.service` (`ssh -N -L 0.0.0.0:8001:127.0.0.1:8001 ubuntu@15.134.130.145`, per TASK-INF-035), so Server 1 holds an SSH route to the AWS host — the likely deploy path, pending a coordinator ruling. No SSH login to the AWS host was attempted this run.
- **G3 — Server 2 shared checkout stale.** It sits on the deleted branch `muse10/task-ig2-web-07-fix-01-glass-start-page` at `410f0738`, behind main `df4e261b`. Flagged for the next board/clone sync; not this task's scope.

## Discipline

- Read-only probes only this run: DNS, `ifconfig.me`, `ss`, `ps`, `systemctl is-active`, `curl` health checks, `cat /etc/caddy/Caddyfile`, `git log/status` on Server 2, repo grep for the IP. No service start/stop/restart, no config change, no file write on any server, no deploy. Net-zero production-state change.
- No secrets in this doc or any hub comment.

## Next

- Coordinator ruling owed: deploy route + clearance for the checkpoint-1 fix onto FRIDAY-Server (15.134.130.145:10000), and how the live checkout sha gets verified.
- Then: live re-verification per the task acceptance (desktop + mobile viewport, widget toggle off/on, `/start` shows the glass start page) — still owed, gated on that deploy.

— Muse 10
