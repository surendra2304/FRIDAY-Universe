# TASK-SEN-013 — Direct-Port Exposure: Consumer Map + Hardening Proposal (READ-ONLY)

- **Crew:** muse_ai (Sentinel lane) · **Date:** 2026-11-15
- **Follow-up to:** TASK-SEN-002 findings F-01 (FRIDAY :10000 reachable from the internet, bypassing Caddy) and F-12 (rpcbind, undocumented listeners 8081/8089/8765, Docker/Swarm surface)
- **Scope rule:** map and propose, change nothing. Every probe in this report is read-only (ss / ps / systemctl status|cat|show / journalctl reads / ufw status / docker info|ps|network listings / crontab -l / host:port-token extraction from .env files — no .env lines or secret values were read). **Production changes: ZERO.**
- **Method note on evidence labels:** every material claim is marked **VERIFIED** (with the probe that proves it) or **UNVERIFIED** (stated as such, with what would settle it). Server probes ran 2026-11-15 ~16:47–17:50 IST via the bridge; repo evidence is main @ b34e2d34 (SEN-002's fetched snapshot) plus PR #303's crew files for the phone bridge.
- **Five states:** audit IMPLEMENTED (this map + proposal) · TESTED (probes cited inline) · MERGED: no (PR awaiting coordinator) · DEPLOYED: n/a · PRODUCTION-VERIFIED: the *observations* are production-verified; no fix is claimed.

---

## 1. Headline conclusions

1. **No configured consumer anywhere uses the public path to FRIDAY :10000.** Every legitimate consumer found — in repo code, in the *live* .env files on both servers, in Caddy's live config, in systemd units/timers and cron — reaches :10000 via **127.0.0.1 (same host)** or **10.0.0.121 (VPC)** or **through Caddy's HTTPS domain**. Zero live .env files, zero code defaults, and zero units reference `140.245.208.100:10000` or a public hostname for :10000. **VERIFIED** (§2, §3).
2. The public exposure therefore serves **no identified legitimate purpose**. The only other sources in FRIDAY's access log are unidentified public IPs whose requests are **indistinguishable** from ordinary website traffic, because uvicorn logs Caddy-proxied requests under the real client IP (X-Forwarded-For from the trusted loopback peer). The split between "website visitors via Caddy" and "direct :10000 callers" is **UNVERIFIED** from available logs — Caddy has no access logging configured (§2.3). Direct reachability itself is **VERIFIED** (SEN-002 external probe, 2026-11-15 ~13:15 IST: HTTP 200 + live health JSON from outside OCI).
3. **All three undocumented listeners are now attributed** (§4): **8081** = the FRIDAY-Voice LiveKit worker's health endpoint (production component); **8089** = an **orphaned TASK-VOI-009 drill process** (not a service; deleted working directory); **8765** = the **oracle-cloud-mcp gateway** (a legacy, token-gated "full-access agent server" from the Dokploy era — *not* a Docker artifact; the ufw rule naming docker_gwbridge is stale, and that interface is DOWN).
4. **rpcbind has zero consumers on both hosts** — no exports, no mounts, no dependent units, no repo references (§5). **Docker runs nothing on both hosts** — swarm inactive, 0 containers, units disabled-but-active, only leftover images on S1 (§5). The Swarm firewall rules guard a swarm that does not exist.
5. The hardening proposal (§6) is ordered by risk-reduction vs breakage-risk. Item P1 (close public ingress to :10000) has ~zero expected breakage *because of this map*. Item P2 (rebind agents) refines SEN-002's recommendation with a correction the map surfaced: **S2's agents are configured to call S1's agents over the VPC address, so a naive loopback-only rebind on S1 would break cross-server mesh calls** — the rebind must be dual-address or VPC-address with consumer repointing.

---

## 2. Consumer map — FRIDAY :10000 (direct)

### 2.1 Configured consumers (all internal)

| # | Consumer | Address used | Class | Evidence |
|---|----------|--------------|-------|----------|
| 1 | **Caddy reverse proxy** (S1) — routes `/friday*`, `/friday/api/ws/activity`, and the root handle to FRIDAY | `127.0.0.1:10000` | Internal (it *is* the documented ingress) | Repo `deploy/Caddyfile` + **live** `/etc/caddy/Caddyfile` read on S1 — **VERIFIED** |
| 2 | **FRIDAY-Voice worker** — `brain_bridge.py` posts chat turns to FRIDAY | `http://127.0.0.1:10000/api/chat` | Internal-only | Repo code — **VERIFIED**; consistent with 213 `POST /api/chat` from 127.0.0.1 in FRIDAY's journal (§2.3) |
| 3 | **Voice preflight script** (`FRIDAY/scripts/voice_preflight.py`) | `FRIDAY_API_BASE` default `http://127.0.0.1:10000` | Internal-only | Repo code — **VERIFIED** |
| 4 | **S1 agents → FRIDAY** (Forge, Inference, Memora mesh clients; FRIDAY's own mesh) | Live .env: `127.0.0.1:10000` (7 occurrences across S1 .env files). Code defaults: `http://10.0.0.121:10000` (Forge `app/core/config.py`, Inference `app/core/config.py`, Memora `telemetry.py`) | Internal-only | Live .env host:port-token extraction on S1 + repo code — **VERIFIED** |
| 5 | **S2 agents → FRIDAY** (Cortex, Sentinel, VyralX) | Live .env: `10.0.0.121:10000` present in **each** of Cortex/.env, Sentinel/.env, VyralX/.env on S2 | Internal-only (VPC) | Live .env token extraction on S2, per-file — **VERIFIED** |
| 6 | **Health-checkers on-host** — `fleet-health-watcher` (both hosts, ~5-min timer), deploy health gates (`.github/workflows/deploy-monorepo.yml`, `fleet-live-validation.yml` — both SSH in and curl `127.0.0.1:<port>/health` on the server), VyralX `scripts/check_mesh.py`, `mesh/universe_health.py` | `127.0.0.1` (watcher, gates) / `10.0.0.121` (check_mesh, universe_health) | Internal-only | Repo code + live timer list on both hosts (watcher firing: S1 last 17:08 IST, S2 last 17:12 IST) — **VERIFIED**; FRIDAY journal shows 327 `GET /health` from 127.0.0.1 in the retention window |
| 7 | **Crew/operator probes** (this audit's predecessors, FRD/VOI crews) | `127.0.0.1` via server-side shells | Internal-only | FRIDAY journal loopback profile (§2.3) — **VERIFIED** as a class; individual attribution per probe not attempted |

### 2.2 External consumers — all go through Caddy, none direct

| Consumer | Path used | Class | Evidence |
|----------|-----------|-------|----------|
| **Website (Halo UI)** | `apiBase()` = `window.location.origin` → HTTPS via Caddy | External-legitimate **via Caddy** | Repo `FRIDAY/ui/lib/wire.ts` — **VERIFIED** |
| **Owner browsers / dashboards** | HTTPS via Caddy; FRIDAY's journal shows the UI polling signature (six status endpoints, ~300 hits each) under a Cloudflare-egress IP `104.29.200.107` — i.e. the client reached Caddy through a Cloudflare-fronted network path | External-legitimate **via Caddy** | FRIDAY journal path profile — **VERIFIED** (pattern); the human identity behind the Cloudflare egress is **UNVERIFIED** |
| **Laptop bridge client** (owner's laptop) | Default `wss://friday-universe.duckdns.org/friday/api/laptop/connect/{id}` → Caddy | External-legitimate **via Caddy** | Repo `FRIDAY/scripts/laptop_bridge_client.py` — **VERIFIED** |
| **Phone bridge** (TASK-PHONE-001, PR #303 — built, **not merged/deployed**) | Termux + Kotlin clients use `https://friday-universe.duckdns.org/friday` → `wss://…/friday/api/phone/connect/{deviceId}` → Caddy | External-legitimate **via Caddy** (future) | PR #303 crew files (`phone_agent_termux.py`, `PhoneBridgeService.kt`) — **VERIFIED** |
| **Self-heal sweep** (daily 07:30 timer, S1) | Probes all agents' /health **through the public gateway** `https://friday-universe.duckdns.org` routes | Via Caddy | Repo `scripts/friday_self_heal_sweep.py` + live timer — **VERIFIED** |
| **Bridge MCP (S2)** | — | **Not a configured consumer**: its own code directory contains zero `:10000` targets and no FRIDAY base-URL assignment; it held zero established connections to :10000 at probe time. (Its generic tools take targets as call arguments — a caller *could* ask it to fetch :10000, but that is not a configured dependency.) | Server probes on S2 — **VERIFIED** (narrow consumer question only; the bridge itself was not audited, per the owner-closed scope SEN-002 observed) |
| **OCI A1 allocator** | OCI APIs only | Not a consumer | Repo unit + code — **VERIFIED** |
| **DuckDNS updater** (S1 cron, every 5 min) | Outbound to duckdns.org | Not a consumer | Live crontab on S1 — **VERIFIED** (S2 has no ubuntu crontab) |

### 2.3 What FRIDAY's own log shows — and its limit

FRIDAY's journal (retention window 2026-11-14 18:57 IST → 2026-11-15 16:46 IST, ~21.8 h; uvicorn access-log source IPs):

- `127.0.0.1` — 637 hits: 327× `GET /health`, 213× `POST /api/chat`, 20× `GET /api/livekit/token`, 19× conversation history, mesh/laptop endpoints. The loopback consumer classes of §2.1. **VERIFIED.**
- `104.29.200.107` (Cloudflare egress) — 1,838 hits: ~300× each of the six UI polling endpoints + 14× `POST /api/chat` + page assets. The website-via-Caddy signature. **VERIFIED as a pattern.**
- ~25 further public IPs (long tail) — 92× `GET /`, 57× `POST /api/chat`, 48× voice diagnostics, 30× `GET /models`, 24× `POST /v2/chat`, UI assets; statuses 614× 200 / 52× 404 / 24× 405 / 4× 401. Includes known scanner ranges (e.g. `66.132.224.238`, Censys). **VERIFIED as log content.**
- 7 hits from `140.245.208.100` (S1's own public IP — a local process using the public address, e.g. a probe script; consumer not identified). Minor; noted for completeness.

**The limit (important):** FRIDAY's uvicorn runs with default proxy-header handling, so requests proxied by Caddy (peer 127.0.0.1, trusted) are logged under the *real client IP* from X-Forwarded-For. A public IP in this log is therefore consistent with **either** a Caddy-proxied request **or** a direct :10000 connection. Caddy itself has **no access-log directive** in its live config (its journal holds only error entries; a 24 h sample shows 9 proxied-to-FRIDAY error entries for one client, `106.66.45.138` — proof that *some* log traffic is Caddy-borne, not a census). **The direct-vs-proxied split of the long tail is UNVERIFIED** and cannot be settled from existing logs; proposal P9 (enable Caddy access logging) is what makes it settleable. What *is* settled: the port answers directly from the internet (SEN-002), and nothing legitimate is configured to use that fact (this section + §2.1/2.2).

**Established-connection snapshots** (supporting, not primary evidence): S1 at ~16:49 IST — zero established connections to :10000; only loopback pairs to :8001/:8006. S2 at ~17:22 IST — zero established connections on any agent port. Inter-agent calls are request-scoped, so snapshots undercount by nature; the map rests on configuration + logs. **VERIFIED as snapshots.**

---

## 3. The other nine agent ports — lighter map

**Addressing (VERIFIED, live .env token extraction on both hosts + repo defaults):**

- **Same-host calls use loopback.** S1 .env files: `127.0.0.1:8001–8006` ×8 each, `127.0.0.1:10000` ×7. S2 .env files: `127.0.0.1:8008/8009/8010` ×3 each.
- **Cross-host calls use VPC addresses.** S1 .env files: `10.0.0.120:8008/8009/8010` ×8 each. S2 .env files (all three agents): the full S1 set `10.0.0.121:8001–8006` + `10.0.0.121:10000`. Repo canonical mesh tables agree (FRIDAY `ecosystem/fleet_client.py`, `apps/core/universe_dispatch_bus.py`, `agent/router.py`: S1 agents at 10.0.0.121, S2 agents at 10.0.0.120; Forge's config defaults likewise). Some older FRIDAY skill modules default to `localhost:<port>` — same-host only, consistent.
- **Caddy** reaches S1 agents via 127.0.0.1 and S2 agents via 10.0.0.120 (live Caddyfile — VERIFIED).
- **No live configuration anywhere uses a public IP or the public hostname for inter-agent traffic.** (The `.env.example` templates still show Docker-era hostnames like `http://friday:10000` — stale documentation, not live config; see P10.)
- **Bind state:** every agent binds 0.0.0.0 (repo `deploy/setup_fleet.sh`; live FRIDAY unit ExecStart confirmed identical; live `ss` on both hosts confirms all ten on 0.0.0.0). **VERIFIED.**
- **Filtering:** SEN-002 verified all nine ports filtered from the internet (calibrated external probes). Host layer differs by server: on S1, ufw has no allow rules for 8001–8006 (default-deny backs the OCI list); on S2, **ufw rule 1 allows ANY port from the whole VPC (10.0.0.0/16)** — captured live this audit, closing SEN-002 §7's gap — so S2's agent ports (and every other S2 listener) are reachable from any VPC host, with the OCI list as the only internet barrier. **VERIFIED.**

**Consequence for hardening:** the mesh's internal trust zone is the VPC. Rebinding (P2) must preserve two address families per host (loopback for same-host consumers, VPC for cross-host consumers) or repoint the cross-host consumers — a loopback-only bind on S1 would break Cortex/Sentinel/VyralX → S1-agent calls, which are configured to 10.0.0.121 today.

---

## 4. Undocumented listeners — attribution (all VERIFIED by live probe, S1, 2026-11-15)

### 4.1 Port 8081 — FRIDAY-Voice LiveKit worker health endpoint · legitimate, undocumented
- Process: `/opt/friday_universe/venv/bin/python src/friday/voice/livekit_worker.py start`, PID 2564631, cgroup `FRIDAY-Voice.service`, cwd `/opt/friday_universe/FRIDAY`. Dual-stack 0.0.0.0/[::], backlog 128. This is the LiveKit agents SDK's built-in health/status HTTP server (the port literal appears nowhere in repo code — it is the framework default).
- Consumers: local only (voice diagnostics path). Zero established connections at probe time. Externally filtered (SEN-002).
- **If closed:** the worker process owns the port; "closing" means disabling the SDK health server, which would degrade local voice health/diagnostics. Firewalling it externally changes nothing (already filtered). Correct treatment: document it (P10) and optionally bind to loopback if the SDK setting allows (P7). Do **not** kill — it is the production voice worker.

### 4.2 Port 8089 — orphaned TASK-VOI-009 drill process · leftover, safe to terminate
- Process: `/opt/friday_universe/venv/bin/python /tmp/voi009/drill_launch.py`, PID 2544072, running 3 h 12 m at probe time, cwd `/tmp/voi009/drill/FRIDAY` **(deleted)**, cgroup `user.slice/user-1001.slice/session-15952.scope` — i.e. launched from an interactive session, **not** a systemd service. Dual-stack listener, backlog 128.
- **If closed/terminated:** nothing in production depends on it — it is a drill harness that outlived its drill (the VOI-009 crew's participant launcher). Termination is proposal P3. Lesson recorded in P3: drill harnesses need a cleanup step; this one survived ~3+ hours unnoticed.

### 4.3 Port 8765 — oracle-cloud-mcp gateway · legacy external tool, dormant downstreams
- Process: `/usr/bin/python3 /opt/oracle_mcp/server.py`, PID 1550481, running as **root**, unit `oracle-cloud-mcp.service`, started 2026-10-22 01:41 IST (up 24 d 15 h at probe time). Binds 0.0.0.0:8765 (backlog 5). Source in repo: `scripts/oracle_cloud_mcp.py` (`HOST = "0.0.0.0"`, `PORT = 8765`), unit in `scripts/oracle-cloud-mcp.service` ("Oracle Cloud 24/7 Full-Access Agent Server for ChatGPT").
- What it is: a consolidated MCP gateway (OCI tools, Dokploy tools, laptop-tool proxy) that **fails closed without `ORACLE_MCP_TOKEN`** (EnvironmentFile `/etc/oracle-mcp.env`). Its documented design ingress was **Traefik over HTTPS** at `…/mcp` — Traefik no longer runs (0 containers; its image is a leftover, §5), so today the only path in is the raw listener, held off the internet by OCI/ufw filtering (SEN-002 verified 8765 filtered externally). Its downstreams are dead: Dokploy API at 127.0.0.1:3000 (Dokploy gone) and a stale ngrok laptop URL. Zero established connections at probe time.
- The S1 ufw rule `8765/tcp on docker_gwbridge ALLOW IN Anywhere` is **stale twice over**: the listener is not Docker, and the docker_gwbridge interface is **DOWN** (docker0 also DOWN). The rule currently matches nothing useful.
- **If closed:** any still-configured external client of *this* gateway loses access — the coordinator should confirm dormancy with collaborators before retirement (P6). The production fleet (systemd agents, Caddy, the S2 bridge) does not depend on it. Classification: **external-legitimate by design, currently dormant; consumer liveness UNVERIFIED**.

---

## 5. rpcbind + Docker/Swarm — usage determination (VERIFIED, both hosts)

### 5.1 rpcbind (port 111, TCP+UDP, 0.0.0.0/[::], both hosts)
- State: `rpcbind.service` + `rpcbind.socket` **enabled + active** on both servers (socket-activated; pid 587 on S1, 592 on S2).
- Consumers: **none.** On both hosts: `/etc/exports` empty, no NFS entries in `/etc/fstab`, no NFS mounts, `nfs-common.service` **masked**, and `systemctl list-dependencies --reverse rpcbind.service` shows it wanted **only by multi-user.target** — no unit depends on it. Repo-wide grep: **zero** references to NFS or rpcbind in the fleet's code/docs.
- Verdict: stock Ubuntu-image residue. **If disabled: nothing in the documented or running stack breaks** (the standard caveat applies — a hypothetical non-systemd RPC client would surface immediately in testing; none exists in the fleet design). On S2 it is additionally reachable from the whole VPC under ufw rule 1 (§3).

### 5.2 Docker + Swarm (both hosts)
- State: `docker.service` + `containerd.service` **disabled but active** on both hosts (running since ~Oct 22–23 — the same install episode as oracle-cloud-mcp/Dokploy). `docker info`: **swarm = inactive**, **containers = 0** (running or stopped), networks = only the defaults (bridge/host/none). Images: S1 holds two Dokploy-era leftovers (`dokploy-mcp:latest` 311 MB, `traefik:v3.6.25` 251 MB); S2 holds none. Interfaces docker0 and docker_gwbridge exist on S1 but are **DOWN**.
- Consumers: **none.** The documented production stack is systemd + Caddy; no unit runs a container; `oracle-cloud-mcp.service` declares `After=docker.service` (ordering only — it is a plain python process, not a container).
- The Swarm firewall rules (S1 rules 6–8, S2 rules 3–5: 2377/tcp, 7946, 4789/udp from 10.0.0.0/16) guard a swarm that has never been active in this audit's evidence. **If removed: nothing breaks** (swarm inactive; no manager/worker nodes exist).

---

## 6. Hardening proposal — ordered by risk-reduction vs breakage-risk

Scope note: P1 removes the *undocumented plaintext bypass*. FRIDAY's API remains publicly reachable **by design** through Caddy HTTPS (the website needs it); the application-layer questions (which endpoints need auth) belong to the FRD-002 / OBS-003 line, not to this port map. All items below are proposals — **nothing was changed by this audit.**

### P1 — Close public ingress to S1:10000 · risk-reduction HIGH · breakage ~ZERO
- **Exact change:** delete the OCI security-list ingress rule for tcp/10000 on S1's subnet/VCN; delete S1 ufw rules 4 and 12 (`10000/tcp ALLOW IN Anywhere # FRIDAY Gateway`, v4+v6).
- **Consumer-map evidence:** §2 — every configured consumer uses loopback, VPC, or Caddy. Zero live .env/code/unit references to the public address for :10000 on either server.
- **What it could break:** an *unconfigured* consumer — something a collaborator runs by hand against `140.245.208.100:10000`. The long-tail log sources (§2.3) cannot be excluded, but their request profile matches ordinary website traffic, which keeps working via Caddy. Announce on issue #35 before executing.
- **Verification probe:** external probe (SEN-002 method, calibrated against a known-closed port) → filtered/timeout; `https://friday-universe.duckdns.org/friday` and the root site still 200; FRIDAY journal after 1 h shows loopback + XFF traffic only; mesh health (check_mesh) green.

### P2 — Rebind agents to loopback+VPC addressing · risk-reduction HIGH · breakage LOW-MEDIUM (sequencing-sensitive)
- **Exact change:** in the live systemd units **and** `deploy/setup_fleet.sh`, change agent binds from `0.0.0.0` to the host's VPC IP (S1 agents → 10.0.0.121, S2 agents → 10.0.0.120), and repoint same-host consumers that use 127.0.0.1 (Caddy upstreams for S1 agents; the S2 .env loopback entries; watcher/gate scripts) to the VPC address — host-local traffic to a host's own VPC IP never leaves the box. Where a framework supports dual bind, loopback+VPC is equally acceptable. **Correction to SEN-002's F-01 recommendation:** a loopback-*only* bind on S1 would break S2→S1 mesh calls, which are configured to 10.0.0.121 (§3) — do not apply the loopback-only variant cross-server.
- **Consumer-map evidence:** §3 (both address families in live use, per host).
- **What it could break:** any same-host consumer missed in the repoint (mitigate: grep live .env + units for `127.0.0.1:<port>` before and after; the watcher will surface a miss within 5 min). Execute per-agent with immediate health checks, not fleet-wide at once.
- **Verification probe:** `ss -tlnp` shows no agent on 0.0.0.0; from S2, `curl 10.0.0.121:10000/health` → 200; from S1, `curl 10.0.0.120:8009/health` → 200; Caddy routes for all ten agents → 200; watcher green for two consecutive cycles.
- **Companion change (S2):** narrow S2 ufw rule 1 (`Anywhere ALLOW IN from 10.0.0.0/16`) to the ports the mesh actually uses, sourced from 10.0.0.121 — today *every* S2 listener (incl. rpcbind, §5.1) is VPC-reachable.

### P3 — Terminate the orphaned VOI-009 drill process (S1:8089) · risk-reduction LOW-MED · breakage NONE
- **Exact change:** `kill 2544072` (or terminate the session-15952 scope); add a teardown step to the voice-drill runbook so harnesses cannot outlive drills.
- **Evidence:** §4.2 — deleted cwd, session scope, not a service, 3 h+ runtime at probe time.
- **What it could break:** nothing identified; the PID may already have exited by execution time (check first).
- **Verification probe:** `ss -tlnp | grep 8089` empty; FRIDAY-Voice.service (different PID) still active; voice diagnostics green.

### P4 — Disable rpcbind on both hosts · risk-reduction MEDIUM · breakage ~NONE
- **Exact change:** `systemctl disable --now rpcbind.service rpcbind.socket` + `systemctl mask rpcbind.service rpcbind.socket` on S1 and S2.
- **Evidence:** §5.1 — zero consumers by exports/fstab/mounts/reverse-dependencies/repo grep, both hosts.
- **What it could break:** nothing in the documented or running stack. (If any legacy NFS need ever appears, unmasking restores it in seconds.)
- **Verification probe:** `ss` shows no :111 listener; `systemctl is-enabled rpcbind.socket` → masked; all ten agents' /health 200; watcher green.

### P5 — Remove the Docker Swarm ufw rules on both hosts · risk-reduction LOW-MED · breakage NONE
- **Exact change:** S1: delete ufw rules 6–8 (2377/tcp, 7946/tcp+udp, 4789/udp from 10.0.0.0/16). S2: delete rules 3–5 (same set; redundant under rule 1 until P2's companion narrowing lands).
- **Evidence:** §5.2 — swarm inactive on both hosts, zero containers, zero swarm members.
- **What it could break:** nothing — there is no swarm to disconnect.
- **Verification probe:** `ufw status numbered` no longer lists 2377/7946/4789; `docker info` still reports swarm inactive; fleet health green.

### P6 — oracle-cloud-mcp (S1:8765): confirm dormancy, then bind loopback or retire · risk-reduction MEDIUM · breakage UNKNOWN until confirmed
- **Exact change (after coordinator confirmation on issue #35 that no collaborator still uses this gateway):** either set `HOST = "127.0.0.1"` in `/opt/oracle_mcp/server.py` and restart `oracle-cloud-mcp.service` (its design ingress was a local reverse proxy anyway), or retire the unit (`disable --now` + mask). In both cases delete the stale S1 ufw rule 5 (`8765/tcp on docker_gwbridge`).
- **Evidence:** §4.3 — token-gated but root-running "full-access" gateway on 0.0.0.0 whose proxy ingress (Traefik) and downstreams (Dokploy, ngrok laptop) are all gone; zero established connections.
- **What it could break:** a still-configured external client of this specific gateway (e.g. a ChatGPT connector a collaborator set up in October). That is precisely what the confirmation step exists to catch — **do not skip it.**
- **Verification probe:** `ss` shows 8765 on 127.0.0.1 only (or absent); local `curl` with the token still answers if kept; journal shows no failed external attempts post-change.

### P7 — LiveKit worker 8081: bind loopback if supported; otherwise document · risk-reduction LOW · breakage LOW
- **Exact change:** set the LiveKit agents worker HTTP bind to 127.0.0.1 via its SDK configuration in `FRIDAY-Voice.service`'s environment, if the deployed SDK version supports it; restart FRIDAY-Voice in a voice-quiet window. If unsupported, leave the listener and record it in the listener inventory (P10).
- **Evidence:** §4.1 — production voice component; the worker dials *out* to LiveKit Cloud, so no external inbound need exists; local diagnostics use loopback.
- **What it could break:** voice diagnostics if any component reaches the worker via the VPC/public address (none found — the diagnostics path goes through FRIDAY on loopback).
- **Verification probe:** `ss` shows 127.0.0.1:8081; `/api/voice/diagnostics` via Caddy green; a test voice session connects.

### P8 — Docker daemons: stop+mask, or document why they run · risk-reduction LOW · breakage NONE identified
- **Exact change:** `systemctl disable --now docker.service containerd.service` + mask on both hosts (units are already `disabled`; they were started manually in the Dokploy episode). Optionally remove S1's two leftover images in the same window. If a future need is intended, document it instead and leave them running knowingly.
- **Evidence:** §5.2 — 0 containers, 0 swarm, no unit depends on the daemon (oracle-mcp's `After=` is ordering only).
- **What it could break:** nothing running. A future Dokploy-style experiment would need an unmask first — acceptable friction.
- **Verification probe:** `systemctl is-active docker` → inactive; fleet health green; `ss` shows docker0/gwbridge listeners gone (none exist today).

### P9 — Enable Caddy access logging for the FRIDAY routes · risk-reduction: VISIBILITY · breakage LOW
- **Exact change:** add a `log` directive (file output with rotation, or journal with sampling) to the friday-universe site block in `/etc/caddy/Caddyfile` + `deploy/Caddyfile`; reload Caddy.
- **Evidence:** §2.3 — without upstream-level access logs, direct-vs-proxied attribution is impossible; this audit's one open question stays open forever otherwise.
- **What it could break:** log volume on a host with ~21 h journald retention — use file output with rotation/size caps, not raw journal.
- **Verification probe:** access entries appear with `remote_ip` + `upstream` fields; a known direct-:10000 attempt (pre-P1) or a simulated one (post-P1: from the VPC) is distinguishable from a Caddy-proxied request.

### P10 — Documentation + template hygiene · risk-reduction: AUDITABILITY · breakage NONE
- **Exact change:** add a listener inventory to the deploy docs (8081 = LiveKit worker health; 8765 = oracle-cloud-mcp, legacy; 8089-class = transient drills, must self-clean; :10000 decision from P1); correct the `.env.example` templates' Docker-era hostnames (`http://friday:10000`, `http://<agent>:8000`) to the real loopback/VPC addressing so future audits and fresh installs stop inheriting a fictional mesh.
- **Evidence:** §2–§5 — every "undocumented" item in this report was undocumented only because no inventory exists.
- **Verification probe:** the next port sweep (SEN-002 method) reconciles 1:1 against the inventory with zero unexplained listeners.

---

## 7. What was NOT verified (explicit)

1. **Direct-vs-proxied split of FRIDAY's public-IP log traffic** — impossible from existing logs (XFF trust + no Caddy access log). §2.3, P9.
2. **A fresh external probe from this sandbox** — sandbox egress cannot reach S1 directly (attempt returned no connection). External reachability evidence is SEN-002's calibrated probe series from 2026-11-15 ~13:15 IST, ~4.5 h before this audit's server probes; nothing in the live firewall state read today contradicts it (the `10000 ALLOW` ufw rules are still present — VERIFIED live).
3. **Whether any collaborator still uses the oracle-cloud-mcp gateway (8765)** — a human/process question, not a probe question; P6 sequences confirmation before any change.
4. **Per-request attribution of the 7 hits from S1's own public IP** in FRIDAY's log — consumer not identified; immaterial to the proposal (P1 does not affect host-local traffic).
5. **Live .env *values*** — deliberately never read; only `host:port` address tokens were extracted, which is all a consumer map needs.

## 8. Corrections this audit makes to the record

- SEN-002 described 8765 as an undocumented Docker-era listener: it is **not Docker** — it is the oracle-cloud-mcp python service (documented in-repo at `scripts/`, though absent from the architecture docs), and the docker_gwbridge ufw rule naming it is stale (interface DOWN).
- SEN-002's "undocumented listeners 8081/8089 (python processes)": 8081 is the **production voice worker** (do not close blindly); 8089 is a **drill leftover** (safe to terminate).
- SEN-002's rebind recommendation is refined by §3/P2: cross-server mesh calls use VPC addresses by configuration, so loopback-only binds would break them.
- SEN-002 §7's open gap (S2 ufw unread) is closed: S2 rule 1 allows any port from the whole VPC (§3).

*End of TASK-SEN-013 findings. Read-only audit — no server state was modified in producing this report.*
