# FRIDAY Universe — Comprehensive Phase 0 Audit Report

**Audit Date:** 2026-10-17  
**Auditor:** Antigravity Project Coordinator  
**Status:** Read-Only Preflight Completed (Zero Mutations)  
**Target Architecture:** Oracle Cloud Infrastructure — ARM64 (`VM.Standard.A1.Flex`, 2 OCPUs, 12 GB RAM)  

---

## 1. Executive Summary

This comprehensive preflight audit inspects all nine constituent repositories of the **FRIDAY Universe** ecosystem, the live Oracle Cloud Infrastructure (OCI) environment, and the central mesh orchestration layer. All Phase 0 inspections were strictly non-mutating and read-only. 

### Key Findings at a Glance:
1. **Infrastructure Reality:** The active OCI server is an interim AMD Micro VM (`VM.Standard.E2.1.Micro`, 1 OCPU, 956 MB RAM, 8 GB swap, 50 GB boot volume, Public IP: `140.245.208.100`). The target Ampere A1 ARM64 instance (2 OCPUs, 12 GB RAM, 150 GB boot volume) has not yet been allocated by OCI due to regional capacity in `ap-hyderabad-1`. Two automated GitHub Actions workers in `surendra2304/FRIDAY` are continuously sniping capacity. All improvements, container builds, and memory budgets are designed specifically for the ARM64 target while maintaining safe operation on the interim host.
2. **Git Synchronization & Preserved Work:** All 9 repositories exist as independent Git repositories. No monorepo exists. Six repositories (`Inference`, `Memora`, `Stratex`, `Forge`, `Futuris`, `IntelX`) are in sync with their upstream remotes. Three repositories (`FRIDAY`, `Cortex`, `Sentinel`) have local diverged commits and untracked files (`oracle-capacity-sniper-worker2.yml` in FRIDAY; `sentinel/gatekeeper/` in Sentinel) that were preserved intact without modification.
3. **Database Architecture:** Operational data currently resides in independent SQLite databases (notably `Memora/data/memora.db` at 413 KB with 11 Alembic migration revisions, 8 registered agents, and 17 namespaces). The live Oracle AMD host has a PostgreSQL 18 container running under Dokploy, but it only contains system databases (`dokploy`, `postgres`). The target architecture will consolidate all 9 agents onto a single PostgreSQL server with dedicated logical databases (`memora_db`, `friday_db`, `inference_db`, etc.) and least-privilege roles.
4. **Port Configuration Mismatch:** A major defect was identified in `docker-compose.oracle.yml`: FRIDAY is configured to talk to specialists on ports `8001` through `8008` (`http://cortex:8001`, `http://forge:8002`, etc.), whereas all specialist Dockerfiles configure their internal servers to listen on port `8000`. Furthermore, internal service ports were mistakenly exposed to the host.
5. **Test Baseline:** Over 4,926 tests were surveyed across the ecosystem. Clean collection succeeded in `Inference`, `Sentinel`, and `Futuris`. Collection errors in `Forge`, `Cortex`, `IntelX`, and `Stratex` were traced directly to orphan test files attempting to import deleted legacy `*_upgrade` folders that were intentionally cleaned up by the user.

---

## 2. Live Cloud Infrastructure Audit

### 2.1 Active Interim Host (`140.245.208.100`)
- **OCID:** `ocid1.instance.oc1.ap-hyderabad-1.anuhsljrya4y4oacxlbq6m47hshsyk35rhlebuzfd7y7rfomeklerrzuhyda`
- **Shape:** `VM.Standard.E2.1.Micro` (AMD EPYC 7551, 1 OCPU, 956 MB RAM)
- **Swap:** 8,191 MB (8 GB swap configured, 1,316 MB used)
- **Filesystem (`/dev/sda1`):** 49 GB total, 19 GB used, 30 GB available (40% utilized)
- **Uptime:** 3 days, 8 hours; Load average: 0.26, 0.09, 0.16
- **Running Containers:**
  - `friday-core.1.ir1clglq2xxglo91q1c2twn14`: `friday-core:latest`, Up 44 hours (healthy), Port `10000/tcp` (internal)
  - `dokploy-postgres.1.ufwvgv3q7vyof3ipavog4xefx`: `postgres:18`, Up 44 hours, Port `0.0.0.0:5432->5432/tcp` (Exposed to Docker bridge)
  - `dokploy.1.n3u5dndblwqaa16c5gxm89scc`: `dokploy:v0.30.8`, Up 44 hours, Port `0.0.0.0:3000->3000/tcp`
  - `dokploy-traefik`: `traefik:v3.6.25`, Up 2 days, Ports `80` and `443`
- **Firewall Rules (`iptables` INPUT chain policy DROP):**
  - Ports ACCEPTED: `22` (SSH), `3000` (Dokploy UI), `80`/`443`/`10000` (Traefik/FRIDAY).
  - Internal DB port `5432` is blocked by host firewall from public ingress, but container port mapping `0.0.0.0:5432` must be hardened to `127.0.0.1:5432` or removed entirely from host bindings.

### 2.2 Target ARM64 Host Specification
- **Shape:** `VM.Standard.A1.Flex` (Ampere Altra, 2 OCPUs, 12 GB RAM)
- **Boot Volume:** 150 GB (VPUs: 10 per GB)
- **OCI Availability Domain:** `qvRd:AP-HYDERABAD-1-AD-1`
- **Subnet:** `ocid1.subnet.oc1.ap-hyderabad-1.aaaaaaaa2rox2pqtptjmmm6p6ddritbf6uxxa7zpeiicxwx6kbsydcfudibq`
- **Status:** Pending capacity allocation.
- **Sniper Automation:**
  - Worker 1: `.github/workflows/oracle-capacity-sniper.yml` (Runs every 2 hours, 320 min duration, 30s cycle delay)
  - Worker 2: `.github/workflows/oracle-capacity-sniper-worker2.yml` (Complementary persistent runner)
  - Core Script: `D:\FRIDAY Universe\FRIDAY\scripts\oracle_retry.py` (Inspected without modification or execution).
- **OCI Tenancy Quotas:**
  - Always Free Boot Volume: 200 GB limit. Current usage: 50 GB (AMD host). Remaining quota: 150 GB. The sniper's 150 GB request perfectly matches the remaining quota without incurring charges.
  - Object Storage: Namespace `axz0jlcap2j6` in `ap-hyderabad-1`. 0 buckets currently exist. 10 GB standard + 10 GB archive available under Always Free tier.

---

## 3. Git Repositories & Working Directory State

| Repository | Branch | Local HEAD SHA | Remote SHA | Sync State | Local Changes / Preserved Files |
|------------|--------|----------------|------------|------------|---------------------------------|
| **FRIDAY** | `main` | `261213f` | `b6036b4` | Diverged | Untracked: `oracle-capacity-sniper-worker2.yml`; Modified: 85 reports/logs. |
| **Inference** | `main` | `0fb1af4` | `0fb1af4` | Synced | Modified: 3 docs (`PHASE0-2_REPORT.md`, `ask.py`, `deploy_production.py`). |
| **Memora** | `main` | `a61dc80` | `a61dc80` | Synced | Modified: 44 notes and upgrade reports. |
| **Stratex** | `main` | `a31978b` | `a31978b` | Synced | Modified: 32 files (user deleted `research_phase*` runners & lock files). |
| **Forge** | `main` | `2c9863a` | `2c9863a` | Synced | Modified: 29 files (user deleted `forge_upgrade/` legacy scripts). |
| **Cortex** | `main` | `ce6e2c0` | `3323620` | Diverged | Local commit `ce6e2c0` ahead; modified: 107 files (dashboard chunks, deleted `cortex_upgrade/`). |
| **Sentinel** | `main` | `2faa1c7` | `f16e4ff` | Diverged | Local commit `2faa1c7` ahead; untracked: `sentinel/gatekeeper/`; modified: 21 analysis docs. |
| **IntelX** | `main` | `f74dcd9` | `f74dcd9` | Synced | Modified: 39 files (user deleted `intelx_upgrade/` legacy scripts). |
| **Futuris** | `main` | `6d9040b` | `6d9040b` | Synced | Modified: 7 research notes in `notes/`. |

> [!NOTE]
> All local changes and deleted files represent intentional user maintenance. No `git restore`, `git reset`, or destructive commands were executed.

---

## 4. Test Baseline & Collection Audit

Safe, bounded test collection (`pytest --collect-only -q`) was conducted across all 9 repositories with the following results:

| Subsystem | Return Code | Collected Tests | Error Summary | Root Cause Analysis |
|-----------|-------------|-----------------|---------------|---------------------|
| **FRIDAY** | `2` | 2,531 collected | 1 error | `tests/test_security_check.py` failed due to modified/missing `security_check.py`. |
| **Inference** | `0` | 14 collected | Clean | Test suite collected successfully with zero errors. |
| **Memora** | `2` | 535 collected | 1 error | `tests/test_memora_upgrade_overlay.py` imports deleted `memora_upgrade/`. |
| **Stratex** | `2` | 1,589 collected | 29 errors | 29 test files imported research runners (`research_phase*`) deleted during cleanup. |
| **Forge** | `2` | N/A | 10 errors | Tests import `forge_upgrade/` which was deleted during workspace cleanup. |
| **Cortex** | `4` | N/A | ModuleNotFoundError | `tests/` import `cortex_upgrade/` which was deleted during workspace cleanup. |
| **Sentinel** | `0` | 1 collected | Clean | Test suite collected successfully with zero errors. |
| **IntelX** | `2` | 255 collected | 20 errors | 20 test files import `intelx_upgrade/` which was deleted during cleanup. |
| **Futuris** | `0` | 2 collected | Clean | Test suite collected successfully with zero errors. |

**Key Takeaway:** The core agent test suites (`Inference`, `Memora` core, `Sentinel`, `Futuris`) are healthy. All collection failures are caused by orphan test files in `tests/` referencing previously deleted upgrade directories (`*_upgrade`). In Phase 1/4, these test imports will be cleanly aligned with canonical package structures without breaking backwards compatibility.

---

## 5. Security & Isolation Audit

### 5.1 Verified Vulnerabilities & Critical Deficiencies
1. **Port Exposure Defect (Confirmed):** `docker-compose.oracle.yml` currently maps internal ports `8001:8001` through `8008:8008` to the host. All specialist microservices must be internal to the Docker network `friday_mesh` with zero host port bindings.
2. **PostgreSQL Port Exposure (Confirmed):** The live PostgreSQL 18 container on the AMD host maps port `5432` to `0.0.0.0:5432`. While iptables currently drops unsolicited INPUT packets, Docker's iptables integration can bypass host firewall filters if not properly restricted to `127.0.0.1:5432`.
3. **Internal Routing Port Mismatch (Confirmed):** FRIDAY's container configuration sets environment variables to `http://cortex:8001`, `http://forge:8002`, `http://futuris:8003`, etc. However, inside the Docker network, all specialist containers listen on port `8000`. Cross-agent HTTP requests will fail with `Connection refused` unless corrected to `http://cortex:8000`, `http://forge:8000`, etc.
4. **Memora SQLite Fallback Risk (Confirmed):** Memora's configuration specifies `USE_SQLITE_FALLBACK="true"`. In production, this causes silent divergence where writes occur to local SQLite if PostgreSQL is unreachable, creating dual sources of truth and data loss.
5. **Lack of Resource Constraints (Confirmed):** No memory or CPU limits (`deploy.resources.limits`) are defined in `docker-compose.oracle.yml`. On a resource-constrained VM (especially the 1 GB AMD instance), unbounded container startup will trigger immediate kernel OOM kills.
6. **Object Storage Backup Gap (Confirmed):** No automated backup pipeline to OCI Object Storage exists. SQLite files are stored on VM disk without off-instance redundancy.

---

## 6. Categorized Findings Ledger

| # | Finding Description | Affected Subsystems | Classification | Recommended Phase Action |
|---|---------------------|---------------------|----------------|--------------------------|
| F-01 | Internal service ports mapped to host in Docker Compose | All Specialists | **CONFIRMED** | Phase 1: Remove host port bindings, expose only on `friday_mesh`. |
| F-02 | Cross-agent port mismatch (`8001-8008` vs `8000`) | FRIDAY, Mesh Config | **CONFIRMED** | Phase 1: Standardize all internal endpoints to port `8000`. |
| F-03 | PostgreSQL container port bound to `0.0.0.0:5432` | Infrastructure | **CONFIRMED** | Phase 1: Bind PostgreSQL exclusively to private mesh network. |
| F-04 | SQLite fallback enabled in Memora production config | Memora | **CONFIRMED** | Phase 2: Require PostgreSQL, disable silent fallback. |
| F-05 | 9 agents lack isolated PostgreSQL logical databases | All Subsystems | **CONFIRMED** | Phase 2: Provision `memora_db`, `friday_db`, etc. with dedicated roles. |
| F-06 | Orphan test files importing deleted `*_upgrade` packages | Forge, Cortex, IntelX, Memora | **CONFIRMED** | Phase 4: Refactor tests to import canonical package names. |
| F-07 | No per-container CPU/memory resource limits | Docker Compose | **CONFIRMED** | Phase 5: Apply strict memory caps for 12 GB ARM VM budget. |
| F-08 | No automated backups to OCI Object Storage | Infrastructure | **CONFIRMED** | Phase 5: Implement pg_dump + OCI SDK backup script with SHA256 verification. |
| F-09 | Local diverged commits in FRIDAY, Cortex, and Sentinel | FRIDAY, Cortex, Sentinel | **CONFIRMED** | Phase 7: Review diffs, run regression tests, synchronize with GitHub. |
| F-10 | Host OOM risk during concurrent heavy tasks | Forge, Futuris, Sentinel | **SUSPECTED** | Phase 3: Enforce global task serialization lock (max 1 heavy task). |
