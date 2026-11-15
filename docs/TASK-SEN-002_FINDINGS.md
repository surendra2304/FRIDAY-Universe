# TASK-SEN-002 — Fleet Security Sweep (READ-ONLY)

- **Crew:** muse_ai (Sentinel lane, Wave 4) · **Date:** 2026-11-15
- **Repo snapshot audited:** main @ 5958763 (TASK-VOI-009 merge), 5,860 tracked files
- **Scope:** exposed ports/services on both servers vs documented · dependency vulnerability scan of the repo · env-file hygiene · secrets-shape scan of tracked files (counts/locations only — no secret value is printed anywhere in this report) · stale/unused credential surfaces
- **Explicitly out of scope:** the bridge (owner-closed topic) — not audited, not probed, not reported on. It was used only as a transport for read-only probes and GitHub operations.
- **Production changes:** NONE. This was a read-only audit. The only writes are this report, the fix PR, and the board entry.
- **Status (five-state):** audit IMPLEMENTED and TESTED locally as detailed per section; server-side probe section and PR/board states are recorded at the end.

---

## 1. Findings summary

| ID | Severity | Finding |
|----|----------|---------|
| F-01 | MEDIUM | FRIDAY's port 10000 is directly reachable from the internet, bypassing the Caddy TLS layer. All agents bind 0.0.0.0 (deploy/setup_fleet.sh); external filtering currently saves the other nine ports — verified live — so the fleet's port posture rests entirely on OCI security-list rules. The exposure appears deliberate at host level (S1 ufw rule 4: `10000/tcp ALLOW IN Anywhere # FRIDAY Gateway`, §5) but is documented nowhere in the repo, whose own docs describe Caddy as the single ingress. |
| F-02 | HIGH | Sentinel/requirements.txt exact pins block every current security fix for 18 unique CVEs: PyJWT==2.13.0 (14 CVEs, fixed in 2.14.0), dnspython==2.8.0 (2 CVEs, fixed in 2.9.0/2.9.2), WeasyPrint==69.0 (2 CVEs, fixed in 70.0). §5 shows the deployed venv has drifted AHEAD of the manifests (PyJWT 2.15.1 installed) — so today's exposure is low, but any rebuild/redeploy from these manifests silently REGRESSES to the vulnerable pins. Fix PR included (tested). |
| F-03 | MEDIUM | VyralX/pyproject.toml caps Pillow at <12.0, blocking fixes for 54 unique CVEs (fixes land in 12.2.0) in the agent that processes external media. (§5: the live venv already runs Pillow 12.3.0 — the cap is already being violated by the drifted runtime; a manifest-faithful rebuild would force the vulnerable line back in.) |
| F-04 | MEDIUM | Old dependency floors fleet-wide carry heavy CVE counts at the floor: pypdf>=5.0.0 (IntelX, parses untrusted PDFs — 67 unique CVEs at floor), python-multipart>=0.0.9/0.0.12 (Memora/IntelX — 7 CVEs incl. form-parsing DoS), aiohttp>=3.9.0 (Cortex apps — 46 CVEs at floor), starlette>=0.37 (requirements-ci — 7 CVEs). §5 verification: the CURRENT production venv is NOT near the floors (pypdf 6.21.2, python-multipart 0.0.32, aiohttp 3.14.5, starlette 1.7.0 installed) — the risk is manifest/rebuild drift (same disease as F-02), not today's runtime. Floors should still be raised to the audited-clean versions. |
| F-05 | MEDIUM | No lockfiles anywhere; almost all specs are open ranges. Dependabot watches pip only for /FRIDAY — the other nine agents' manifests have no automated update/vuln signal. Fix PR extends Dependabot coverage. |
| F-06 | LOW | GitHub Actions are pinned by mutable tags, not SHAs — including appleboy/ssh-action (13 uses) on the deploy and credential-sync paths. |
| F-07 | LOW | Runtime state files are tracked in the public repo (FRIDAY/.data/**: memory entries, audit log, threat-intel and security state JSONs). Shape-scanned: no credentials inside; still operational data that should not be public. |
| F-08 | INFO (positive) | No real secrets found in tracked files at HEAD. 100+ key-shaped matches were individually triaged: every one is a test fixture, scanner source code, a placeholder, or a docs example. No real .env tracked (only .env.example), no key/cert files tracked; .gitignore covers *.env*, credentials*.md, *.key. |
| F-09 | INFO | Git history leak was already remediated under TASK-SEC-002 (2026-11-10: git-filter-repo purge of 16 leaked credential literals across 667 commits, force-push, post-rewrite scan zero). Gitleaks now scans every PR/push change range. Credential rotation for the historically exposed set remains tracked under TASK-SEC-004. |
| F-10 | LOW | Stale credential copies: ~25 `.env.bak-*` files across both servers (FRIDAY 5, Stratex 6, VyralX 6, others 1–2 each; all mode 600, one root-owned) — superseded secrets retained indefinitely. Correction to my pre-probe expectation: `credentials.md.bak-*` copies = **0** on both servers. Separately: WeasyPrint and PyJWT are pinned in Sentinel's manifest but have no direct imports in Sentinel code — unused attack surface (dnspython is genuinely used by 3 modules). |
| F-11 | MEDIUM | `/opt/friday_universe/VyralX/.env` **on Server 1** is mode **664** (group-writable, world-readable) — every other live `.env` on both servers is 600. Server 1 does not run VyralX; this is a stale cross-server copy of VyralX's credentials, readable by any local account. |
| F-12 | LOW | rpcbind (port 111) listens on 0.0.0.0/[::] on BOTH servers with no evident NFS need; Server 1 also has three undocumented 0.0.0.0 listeners (8081, 8089, 8765 — all verified filtered from the internet; process identification in §5). Docker Engine + containerd run on both servers although the documented production stack is systemd + Caddy only — inventory drift worth explaining or removing. S1's ufw additionally allows the Docker Swarm control/data ports (2377/tcp, 7946, 4789/udp) from the whole VPC range 10.0.0.0/16 and 8765/tcp on the docker_gwbridge interface from anywhere, while `docker ps` returns empty — a configured-but-unused container/swarm surface. |

---

## 2. Ports & services — documented vs observed

**Documented (repo):** single public ingress = Caddy on Server 1 (deploy/Caddyfile) path-routing /friday /inference /memora /stratex /futuris /intelx /forge to localhost ports and /sentinel /cortex /vyralx to Server 2 over the private network. Agent ports: FRIDAY 10000, Inference 8001, Memora 8002, Stratex 8003, Futuris 8004, IntelX 8005, Forge 8006 (S1); Sentinel 8008, Cortex 8009, VyralX 8010 (S2). deploy/setup_fleet.sh starts every agent with `--host 0.0.0.0`.

**Observed (external TCP/HTTP probes from outside OCI, 2026-11-15 ~13:15 IST, calibrated against a known-closed port 9999 which returns the identical filtered signature):**

| Target | Result |
|---|---|
| S1 140.245.208.100:443 | OPEN — Caddy HTTPS (documented) |
| S1 :10000 | **OPEN — FRIDAY /health answered directly (HTTP 200, live health JSON). Not part of the documented ingress design.** |
| S1 :8001, 8002, 8003, 8004, 8005, 8006 | filtered (identical to known-closed control) |
| S2 140.245.243.168:8008, 8009, 8010 | filtered |
| S2 :443, :10000 | filtered (no Caddy on S2 — matches documentation) |

Server-side listening sockets and running services (ss + systemctl on both hosts, read-only): see §5.

**Assessment:** the Caddy design is sound, but because every agent binds 0.0.0.0, the OCI security list is the *only* barrier between nine agent APIs and the internet, and port 10000 shows that barrier already has one hole. Recommended (server-side change, NOT in the fix PR because live units may differ from the setup script and S2 agents must keep binding the private interface for Caddy): bind S1 agents to 127.0.0.1 and S2 agents to 10.0.0.120 in the live units and in deploy/setup_fleet.sh, and close 10000 in the OCI security list.

---

## 3. Dependency vulnerability scan

**Method:** every manifest in the repo (15 requirements files + 9 pyproject.toml files; 90 distinct packages, 177 version queries) was parsed; for each exact pin (==) and each range floor, the version's vulnerability list was pulled from PyPI's JSON API (which serves OSV data — the same database pip-audit uses; api.osv.dev itself timed out through this sandbox's proxy). A hit is decision-grade in two cases: (a) an exact pin is vulnerable — production installs exactly that; (b) a spec's ceiling excludes the fixed version — no install can ever reach the fix. Cross-check: pip-audit with full resolution completed for Inference/requirements.txt — *no known vulnerabilities found*; full-resolution pip-audit for the remaining files exceeded sandbox network timeouts and is NOT claimed. Transitive (non-manifest) dependencies are out of reach of this method and are covered only by the recommended server-side pip-audit (§6).

**Headline numbers:** 19 of 90 packages have advisories at a pinned or floor version; 237 unique CVEs across all of them (advisory rows double-count GHSA/PYSEC pairs; unique-CVE counts below are deduplicated).

### 3.1 Exact pins that block fixes — all in Sentinel/requirements.txt (F-02)

| Pin | Unique CVEs at pin | Fixed in | In fix PR |
|---|---|---|---|
| PyJWT==2.13.0 | 14 (27 of 29 advisory rows blocked) | 2.14.0 | ✅ → 2.14.0 |
| dnspython==2.8.0 | 2 (CVE-2026-114605, CVE-2026-128089) | 2.9.0 / 2.9.2 | ✅ → 2.9.2 |
| WeasyPrint==69.0 | 2 (CVE-2026-55073, CVE-2026-106443) | 70.0 | ✅ → 70.0 |

Test evidence for the bumps: the four security-relevant pins (PyJWT 2.14.0, dnspython 2.9.2, WeasyPrint 70.0, existing cryptography==50.0.0) were co-installed into a clean target dir with zero conflicts among them; functional smoke passed — JWT HS256 encode/decode round-trip, dnspython Resolver construction, WeasyPrint HTML→PDF render (2,740 bytes). Usage check: dnspython is imported by Sentinel/sentinel/integrations/scanners/dns_adapter.py, modules/dns/dns_intel.py, modules/recon/adapters.py; no direct `import jwt` or `weasyprint` exists in Sentinel code (F-10) — the bumps are still the conservative fix; removal is a valid follow-up for the Sentinel lane.

### 3.2 Ceilings that block fixes (ranges)

| Spec | Where | Blocked |
|---|---|---|
| Pillow >=10.0,<12.0 | VyralX/pyproject.toml | 74 advisory rows / fixes at 12.2.0 unreachable (54 unique CVEs at the 10.0 floor) — F-03 |
| pytest >=8.3,<9 | Forge/requirements-verification.txt | CVE-2025-71176 fixed only in 9.0.3 — test tooling only, low priority |

### 3.3 Floors with heavy CVE counts (fresh installs resolve upward; risk materialises if the deployed venv sits near the floor)

pypdf>=5.0.0 (IntelX + CI: 67 unique CVEs at floor; fixes through 6.6.0) · Pillow>=10.0.0 (FRIDAY: 54) · aiohttp>=3.9.0 (Cortex apps/api + worker: 46) · PyJWT>=2.8/2.10.1 (CI, Sentinel pyproject, Cortex apps: 14–16) · python-multipart>=0.0.9/0.0.12 (Memora/IntelX: 7) · starlette>=0.37 (CI: 7) · Jinja2>=3.1.0 (Cortex apps: 5) · cryptography>=42.0.5 (Sentinel pyproject floor: 5; note Sentinel requirements.txt already pins 50.0.0, which is clean) · flask-cors>=4 (CI floor: 5) · WeasyPrint>=61.0 (Sentinel pyproject floor: 5) · requests>=2.31 (3) · gunicorn>=21.2.0 (Stratex: 2) · pyarrow>=14.0.0 (Futuris: 2, incl. CVE-2023-47248) · qdrant-client>=1.8.0 (Memora: 1, CVE-2024-3829) · python-dotenv>=1.0.x (1) · fastapi>=0.100.0 (FRIDAY floor: 1, CVE-2024-24762) · flask>=3.0.0 (Stratex mt5 bridge: 1).

One package is declared with no version constraint at all: flask-cors (bare name in one manifest).

### 3.4 Manifest hygiene

VyralX/requirements.txt is EMPTY (0 lines) — VyralX's real spec lives in its pyproject.toml; the empty file invites a false sense of coverage. Stratex has no pyproject.toml. Dependabot (F-05): github-actions (root + FRIDAY workflows dir) and pip for /FRIDAY only.

---

## 4. Secrets & credential surfaces (repo side)

Patterns scanned across all 5,860 tracked files at HEAD (file counts; every non-test hit individually triaged by metadata + redacted context — values never printed):

| Pattern | Files | Verdict |
|---|---|---|
| Google API key shape (AIza…) | 9 | all in tests (secret-scanner fixtures) |
| OpenAI key shape (sk-…) | 41 | tests + 1 false positive in FRIDAY/src/friday/api/task_card.js (an HTML class string); placeholders "not-the-key"/"wrong-key-abc" in a research script and an ingress-probe script |
| OpenRouter shape (sk-or-v1-…) | 2 | tests only |
| Groq shape (gsk_…) | 1 | tests only |
| GitHub token shape | 5 | tests only |
| AWS key shape (AKIA…) | 16 | tests + Memora/.gitguardian.yaml (the canonical AWS *example* key in scanner config) |
| Private-key block header | 6 | tests, the pre-push guard script's own pattern, and Forge/notes/raw-findings.md quoting the phrase inside a sentence reporting a clean grep — no key material anywhere |
| JWT shape | 3 files (1 with a token) | Sentinel/sentinel/lab/app.py — a lab dummy token with an empty signature segment |
| Bearer literals | 28 files | docs example + an e2e test script header |
| Generic `key/secret/password = "…"` assignments | 145 files | non-test hits all triaged: scrubber source code, placeholders, docs, board log |
| Slack / HuggingFace token shapes | 0 | — |

Tracked-file inventory: only `.env.example` files (9) — no real `.env`; no *.pem/*.key/*.p12, no id_rsa/id_ed25519, no .oci config. `.gitignore` covers `*.env*`, `credentials.md`, `credentials*.md`, `*.key`. Gitleaks workflow scans PR + push change ranges (it does not re-scan full history; the historical purge is F-09). Tracked runtime state (F-07): FRIDAY/.data/** JSONs (memories, audit entries, threat intel, security state) — no credential-shaped content found inside them.

Credential workflows: `.github/workflows/sync-credentials.yml` (owner-directed, 2026-11-11) writes Telegram bot credentials from GitHub Secrets to credentials.md (chmod 600) on both servers over SSH and tops up TELEGRAM_* env keys without overwriting; it leaves timestamped backups (F-10). GitHub Secrets themselves are not enumerable from this audit's access.

---

## 5. Server-side verification (read-only probes, 2026-11-15 ~15:00 IST)

Probes executed on both hosts (ss, systemctl, stat, pip list, ufw/sshd config reads — nothing modified):

**Listening sockets.** S1: Caddy *:80/*:443; agents 0.0.0.0:10000, 8001–8006; rpcbind 0.0.0.0:111 + [::]:111; sshd 22; undocumented 0.0.0.0:8081, 8089, 8765 (all three verified FILTERED from the internet in §2-style probes; a later identification read attributed 8081 and 8089 to `python` processes — PIDs 2546442 and 2544072, dual-stack IPv4+IPv6, backlog 128 — but their command lines were not captured, so the exact services remain unattributed; the 8765 listener's owning process was not visible to the unprivileged probe, and S1's ufw carries a dedicated rule allowing 8765/tcp on the docker_gwbridge interface, tying it to the Docker surface in F-12); Caddy admin 127.0.0.1:2019 (loopback, correct); systemd-resolved 127.0.0.53:53. S2: agents 0.0.0.0:8008, 8009, 8010; one further listener at 8011 (present in inventory; excluded from analysis per this sweep's scope); rpcbind 111; sshd 22; **Redis 127.0.0.1:6379 + [::1]:6379 — loopback only, correct** (redis-server.service supports Cortex). Running services otherwise match the documented fleet (S1: 7 agents + FRIDAY-Voice + 3 Stratex units + allocator + caddy; S2: Sentinel/Cortex/VyralX + VyralX-Daemon + redis) — plus docker.service + containerd.service on BOTH hosts (F-12).

**Env-file hygiene.** Every live `.env` is mode 600 owner ubuntu on both servers — with ONE exception: **`/opt/friday_universe/VyralX/.env` on Server 1 is 664** (F-11; VyralX does not run on S1 — stale copy; the live S2 VyralX/.env is 600). `credentials.md` (S1) and `credentials.md` + `CREDENTIALS.md` (S2) are 600. `.env.example` files are 664/644 (no secrets). `.env.bak-*` stale copies: ~25 across both hosts, all 600 (F-10). `credentials.md.bak-*`: **0 on both hosts**.

**Installed versions (shared venv `/opt/friday_universe/venv`, identical on both servers):** aiohttp 3.14.5 · cryptography 50.0.2 · fastapi 0.161.1 · Flask 3.1.3 (S1) · Jinja2 3.1.6 · Pillow 12.3.0 · pyarrow 25.0.1 · **PyJWT 2.15.1** · pypdf 6.21.2 (S1 list) · python-dotenv 1.2.4 · python-multipart 0.0.32 · requests 2.34.2 · starlette 1.7.0 · urllib3 2.8.0 · uvicorn 0.54.0. **Every package flagged in §3 is installed at a current, fixed version — the production runtime is NOT exposed at the manifest floors/pins today.** The flip side: the venv matches NO manifest (Sentinel requirements pin fastapi 0.141.1 / uvicorn 0.52.4 / PyJWT 2.13.0; S2's venv does not contain dnspython or WeasyPrint at all) — manifests and runtime have drifted apart, and a manifest-driven rebuild would regress security-relevant versions (F-02) and break Sentinel's DNS modules (missing dnspython). Recommended: regenerate/pin manifests from the live venv under change control.

**Host firewall / SSH.** ufw is ACTIVE on both servers. S1's rule list (captured on a later read): ALLOW 22/tcp (SSH), 80/tcp, 443/tcp, **10000/tcp — commented "FRIDAY Gateway"**, 8765/tcp on docker_gwbridge, and Docker Swarm ports 2377/tcp + 7946 + 4789/udp restricted to 10.0.0.0/16 (same set mirrored for IPv6). No ufw rule allows 8001–8006/8081/8089 — ufw's default deny is a second barrier behind the OCI lists for those ports, but NOT for 10000, which both layers deliberately allow. S2's rule list was not captured (§7). sshd: `PasswordAuthentication no` (60-cloudimg-settings.conf) on both. Combined with §2's external probes, effective external posture: S1 80/443 + 10000 reachable; everything else filtered.

---

## 6. Recommendations (priority order)

1. **Merge the fix PR**: Sentinel pin bumps (F-02) + Dependabot pip coverage for all ten agent manifest dirs (F-05).
2. **Close the 10000 hole** (F-01): remove OCI ingress for 10000 on S1; rebind agents per §2 (127.0.0.1 on S1, private IP on S2) in live units and deploy/setup_fleet.sh — coordinator/owner-scheduled server change, deliberately not bundled into the repo PR.
3. **Run pip-audit inside the production venv on both servers** and raise the §3.3 floors to the audited-clean versions (pypdf, python-multipart, aiohttp first — internet-facing parsing paths).
4. Raise the VyralX Pillow ceiling to <13 after a VyralX-lane compatibility check (F-03).
5. SHA-pin GitHub Actions, starting with appleboy/ssh-action (F-06).
6. Stop tracking FRIDAY/.data/** runtime state; add it to .gitignore and purge from the tree (F-07). Prune the ~25 stale .env.bak-* copies and cap backup retention (F-10).
8. **Fix F-11 immediately** (one chmod + delete the stale copy): Server 1's VyralX/.env to 600 or remove it — VyralX runs on Server 2.
9. **Reconcile manifests with the live venv** (§5): regenerate pinned manifests from the deployed venv under change control, so a rebuild can neither regress the F-02 pins nor lose dnspython/WeasyPrint where code needs them.
10. Disable rpcbind on both hosts if no NFS consumer exists, and identify/document or close S1's 8081/8089/8765 listeners; explain or remove the Docker Engine on both hosts (F-12).
7. Drop or justify the unused Sentinel pins (WeasyPrint, PyJWT) in the Sentinel lane (F-10).

## 7. What was NOT verified

- Exact service attribution for S1's 8081/8089 listeners (both confirmed `python` processes; command lines not captured), the owning process of the 8765 listener (not visible without sudo), and Server 2's full ufw rule list (S1's was captured, §5). These are open items, not passes. External reachability of all three undocumented ports IS verified (filtered).
- Full-history secret rescan: this audit's clone is depth-limited; history state is taken from the repo's own TASK-SEC-002 record (purge executed + post-rewrite scan zero) plus the HEAD scan in §4.
- GitHub Secrets inventory, OCI security-list rules themselves, and TLS configuration — outside this audit's access; port evidence is empirical (§2) rather than from cloud console rules.
- Transitive dependencies (see §3 method note).
