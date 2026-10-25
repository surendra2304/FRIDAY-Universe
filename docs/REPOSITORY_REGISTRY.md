# FRIDAY Universe — Repository Registry

**Version:** 1.0.0  
**Audit Date:** 2026-10-17  
**Auditor:** Antigravity Project Coordinator  
**Target Architecture:** Oracle Cloud Infrastructure — ARM64 (`VM.Standard.A1.Flex`, 2 OCPUs, 12 GB RAM)  

---

## 1. Master Repository Inventory

| # | Service Name | Local Path | Branch | Upstream | Local HEAD SHA | Remote SHA | Git Sync Status | Internal Port | Entry Point | Primary DB | Target Logical DB |
|---|--------------|------------|--------|----------|----------------|------------|-----------------|---------------|-------------|------------|-------------------|
| 1 | **FRIDAY** | `FRIDAY_UNIVERSE_HOME\FRIDAY` | `main` | `origin/main` | `261213f` | `b6036b4` | Diverged / Dirty | `10000` | `friday.api.server:app` | SQLite (`friday.db`) | `friday_db` |
| 2 | **Inference** | `FRIDAY_UNIVERSE_HOME\Inference` | `main` | `origin/main` | `0fb1af4` | `0fb1af4` | Synced (Dirty docs) | `8000` | `app.main:app` | SQLite (`universe.db`) | `inference_db` |
| 3 | **Memora** | `FRIDAY_UNIVERSE_HOME\Memora` | `main` | `origin/main` | `a61dc80` | `a61dc80` | Synced (Dirty notes) | `8000` | `apps.api.main:app` | SQLite (`memora.db`) + Qdrant | `memora_db` |
| 4 | **Stratex** | `FRIDAY_UNIVERSE_HOME\Stratex` | `main` | `origin/main` | `a31978b` | `a31978b` | Synced (Dirty research) | `8000` | `scripts/supervise_services.py` | In-Memory / Redis | `stratex_db` |
| 5 | **Forge** | `FRIDAY_UNIVERSE_HOME\Forge` | `main` | `origin/main` | `2c9863a` | `2c9863a` | Synced (Dirty upgrade) | `8000` | `app.main:app` | SQLite (`forge.db`) | `forge_db` |
| 6 | **Cortex** | `FRIDAY_UNIVERSE_HOME\Cortex` | `main` | `origin/main` | `ce6e2c0` | `3323620` | Diverged / Dirty | `8000` | `cortex_api.main:app` | SQLite (`cortex.db`) | `cortex_db` |
| 7 | **Sentinel** | `FRIDAY_UNIVERSE_HOME\Sentinel` | `main` | `origin/main` | `2faa1c7` | `f16e4ff` | Diverged / Untracked | `8000` | `entrypoint.sh` | Alembic / SQLite | `sentinel_db` |
| 8 | **IntelX** | `FRIDAY_UNIVERSE_HOME\IntelX` | `main` | `origin/main` | `f74dcd9` | `f74dcd9` | Synced (Dirty upgrade) | `8000` | `intelx.cli.main:serve` | SQLite (`intelx.db`) | `intelx_db` |
| 9 | **Futuris** | `FRIDAY_UNIVERSE_HOME\Futuris` | `main` | `origin/main` | `6d9040b` | `6d9040b` | Synced (Dirty notes) | `8000` | `futuris.cli:serve` | SQLite (`futuris.db`) | `futuris_db` |

---

## 2. Detailed Subsystem Specifications

### 2.1 FRIDAY (Core Orchestrator & Gateway)
- **Path:** `FRIDAY_UNIVERSE_HOME\FRIDAY`
- **Remote:** `https://github.com/surendra2304/FRIDAY.git`
- **Role:** Central voice & text user-facing assistant, master task planner, action approval authority, and companion client gateway.
- **Runtime:** Python 3.11.9
- **Entry Point:** `friday.api.server:app` (Uvicorn, Port `10000`)
- **Key Files:**
  - Dependencies: `requirements.txt`, `pyproject.toml`
  - Docker: `Dockerfile` (Base: `python:3.11-slim`), exposes `10000`, healthcheck on `/health`
  - Workflows: `.github/workflows/ci.yml`, `oracle-capacity-sniper.yml`, `oracle-capacity-sniper-worker2.yml`
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `261213f614f590259a2a73690dea12f7bc14f027`
  - Remote SHA: `b6036b4253cc54d588b57cd376d68810da42def8`
  - Diverged commit: `261213f` contains fix for CI failures and instant issue alerts for sniper.
  - Untracked: `.github/workflows/oracle-capacity-sniper-worker2.yml`
  - Modified: Report files in `reports_and_data/` and root markdown summaries.
- **Routes & Mesh Contracts:**
  - Public Ingress: `/health`, `/ws/voice`, `/api/v1/chat`, `/api/v1/tasks`
  - Outbound Mesh: Connects to all 8 specialists over HTTP (`http://cortex:8000`, `http://forge:8000`, etc.)
- **Persistence:**
  - Current: SQLite `friday.db`, `readiness_probe.db`
  - Target: PostgreSQL `friday_db` (task runs, approval logs, tool audit traces)

---

### 2.2 Inference (Canonical Model Gateway & Reasoning Router)
- **Path:** `FRIDAY_UNIVERSE_HOME\Inference`
- **Remote:** `https://github.com/surendra2304/Inference.git`
- **Role:** Sole dynamic LLM/provider gateway, key pooler, model fallbacks, latency tracking, and token budget management.
- **Runtime:** Python 3.11.9
- **Entry Point:** `app.main:app` (Uvicorn, Port `8000`)
- **Key Files:**
  - Dependencies: `requirements.txt`, `pyproject.toml`
  - Docker: `Dockerfile`, `docker-compose.production.yml`
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `0fb1af4a26215f55ce32acaa721a7a1a6214719e` (Matches remote `origin/main`)
  - Modified: 3 docs/scripts (`PHASE0-2_REPORT.md`, `ask.py`, `deploy_production.py`)
- **Routes & Mesh Contracts:**
  - Internal Only: `/health`, `/v1/chat/completions`, `/v1/models`, `/v1/routing/deliberate`
  - External Outbound: Groq, Mistral, OpenAI, Anthropic, Google Gemini, OpenRouter
- **Persistence:**
  - Current: SQLite `universe.db`
  - Target: PostgreSQL `inference_db` (routing telemetry, token costs, evaluation benchmarks)

---

### 2.3 Memora (3-Tier Central Memory Authority)
- **Path:** `FRIDAY_UNIVERSE_HOME\Memora`
- **Remote:** `https://github.com/surendra2304/Memora.git`
- **Role:** Ecosystem memory authority enforcing Private, Shared, and Universal visibility scopes with semantic vector retrieval.
- **Runtime:** Python 3.11.9
- **Entry Point:** `apps.api.main:app` (Uvicorn, Port `8000`)
- **Key Files:**
  - Dependencies: `requirements.txt` (`sqlalchemy`, `psycopg2-binary`, `asyncpg`, `redis`, `qdrant-client`)
  - Alembic: `alembic.ini`, `migrations/` (11 migration revisions up to `f35ecb0a7c12`)
  - Data: `data/memora.db` (413 KB, 8 agents, 17 namespaces, 12 memory records, 2 relationships, 25 events, 62 audit logs)
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `a61dc80ca0c3b788ae542bdefd069b952bf4cb08` (Matches remote `origin/main`)
  - Modified: Phase notes and previous upgrade reports.
- **Routes & Mesh Contracts:**
  - Internal Only: `/health`, `/v1/memories` (GET/POST), `/v1/memories/search`, `/v1/namespaces`, `/v1/audit`
- **Persistence:**
  - Current: SQLite `data/memora.db` + Qdrant Vector DB (`memora_embeddings`) + Redis cache
  - Target: Centralized PostgreSQL `memora_db` (complete migration, disabling SQLite fallback)

---

### 2.4 Stratex (Algorithmic Trading & Execution Engine)
- **Path:** `FRIDAY_UNIVERSE_HOME\Stratex`
- **Remote:** `https://github.com/surendra2304/Stratex.git`
- **Role:** Autonomous Binance Futures execution engine with hard risk gates, order idempotency, and position reconciliation.
- **Runtime:** Python 3.11.9
- **Entry Point:** `scripts/supervise_services.py` / FastAPI server (Port `8000`)
- **Key Files:**
  - Dependencies: `requirements.txt`
  - Docker: `Dockerfile`, `docker-compose.yml`
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `a31978b7f8255691c04848d7703cdbc2ea4898fa` (Matches remote `origin/main`)
  - Modified: Research scripts cleaned up by user (`research_phase*`)
- **Routes & Mesh Contracts:**
  - Internal Only: `/health`, `/api/v1/trade/signal`, `/api/v1/positions`, `/api/v1/risk/status`
  - External Outbound: Binance Futures Testnet / Production API, CCXT
- **Persistence:**
  - Current: In-memory order books, local state ledgers
  - Target: PostgreSQL `stratex_db` (orders, executions, fills, hard risk violation log)

---

### 2.5 Forge (Autonomous Software Engineer & Sandbox Builder)
- **Path:** `FRIDAY_UNIVERSE_HOME\Forge`
- **Remote:** `https://github.com/surendra2304/Forge.git`
- **Role:** Code synthesis, AST verification, test execution runner, and 3D web application builder in bounded environments.
- **Runtime:** Python 3.11.9
- **Entry Point:** `app.main:app` (Uvicorn, Port `8000`)
- **Key Files:**
  - Dependencies: `requirements.txt`, `pyproject.toml`
  - Docker: `Dockerfile`, `docker-compose.yml`
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `2c9863a9189df302f115d866b897a53808b86e95` (Matches remote `origin/main`)
  - Modified: Deleted `forge_upgrade/` legacy scripts
- **Routes & Mesh Contracts:**
  - Internal Only: `/health`, `/api/v1/build`, `/api/v1/test`, `/api/v1/patch`, `/api/v1/artifacts`
- **Persistence:**
  - Current: SQLite `forge.db`
  - Target: PostgreSQL `forge_db` (build manifests, test run logs, patch metadata)

---

### 2.6 Cortex (Web Operations & Lead Qualification Agent)
- **Path:** `FRIDAY_UNIVERSE_HOME\Cortex`
- **Remote:** `https://github.com/surendra2304/Cortex.git`
- **Role:** Multi-tenant web operations, real-time visitor telemetry, lead qualification, and CRM sync.
- **Runtime:** Python 3.11.9 (Backend) + Next.js (Dashboard frontend in `apps/dashboard`)
- **Entry Point:** `cortex_api.main:app` (Uvicorn, Port `8000`)
- **Key Files:**
  - Dependencies: `requirements.txt`, `pyproject.toml`, `package.json`
  - Docker: `Dockerfile`, `docker-compose.yml`
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `ce6e2c05960a74a1032a050e814844ff5e6836f6`
  - Remote SHA: `33236206ce5e07a14eddb24d1d60fdf76c313ee6`
  - Diverged commit: `ce6e2c0` fixes paths and repo root resolution.
  - Modified: Dashboard static chunks and deleted `cortex_upgrade/` legacy files.
- **Routes & Mesh Contracts:**
  - Public Ingress (optional via Caddy): `/api/v1/telemetry/ingest`, `/health`
  - Internal Mesh: `/api/v1/leads`, `/api/v1/campaigns`, `/api/v1/crm`
- **Persistence:**
  - Current: SQLite `cortex.db`
  - Target: PostgreSQL `cortex_db` (tenants, visitors, lead scores, CRM action events)

---

### 2.7 Sentinel (Real-time Cyber Shield & Security Gatekeeper)
- **Path:** `FRIDAY_UNIVERSE_HOME\Sentinel`
- **Remote:** `https://github.com/surendra2304/Sentinel.git`
- **Role:** AST-based code policy gate, secret redactor, vulnerability scanner, and active security boundary auditor.
- **Runtime:** Python 3.11.9
- **Entry Point:** `/app/entrypoint.sh` -> Uvicorn (Port `8000`)
- **Key Files:**
  - Dependencies: `requirements.txt`, `pyproject.toml`
  - Docker: `Dockerfile`, `docker-compose.yml`, `docker-compose.production.yml`
  - Alembic: `alembic.ini` present
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `2faa1c773a3ea8f664054c01919fe1ad6b95ab26`
  - Remote SHA: `f16e4ffd5bd9446177cedc3369b8c4350a3d6525`
  - Untracked: `sentinel/gatekeeper/` directory
  - Modified: Analysis notes and verification markdown reports.
- **Routes & Mesh Contracts:**
  - Internal Only: `/health`, `/api/v1/scan`, `/api/v1/gate/ast`, `/api/v1/audit/log`, `/api/v1/quarantine`
- **Persistence:**
  - Current: Alembic schema migrations
  - Target: PostgreSQL `sentinel_db` (authorized scopes, scan findings, policy gate decisions)

---

### 2.8 IntelX (Deep Multi-Source Research & Evidence Engine)
- **Path:** `FRIDAY_UNIVERSE_HOME\IntelX`
- **Remote:** `https://github.com/surendra2304/IntelX.git`
- **Role:** Web crawler, citation extractor, contradiction detection, and source evidence graph builder.
- **Runtime:** Python 3.11.9
- **Entry Point:** `intelx.cli.main:serve` (Port `8000`)
- **Key Files:**
  - Dependencies: `requirements.txt`, `pyproject.toml`
  - Docker: `Dockerfile`, `docker-compose.yml`, `docker-compose.production.yml`
  - Alembic: `alembic.ini` present
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `f74dcd939af669a3a7596a28f543770a46e85b6c` (Matches remote `origin/main`)
  - Modified: Deleted `intelx_upgrade/` legacy files
- **Routes & Mesh Contracts:**
  - Internal Only: `/healthz`, `/api/v1/research/query`, `/api/v1/citations`, `/api/v1/evidence`
  - External Outbound: Web crawlers, search APIs, Tavily/SerpAPI
- **Persistence:**
  - Current: SQLite `intelx.db`
  - Target: PostgreSQL `intelx_db` (source claims, citations, crawl jobs, contradiction graph)

---

### 2.9 Futuris (Calibrated Probabilistic Forecasting Engine)
- **Path:** `FRIDAY_UNIVERSE_HOME\Futuris`
- **Remote:** `https://github.com/surendra2304/Futuris.git`
- **Role:** Probabilistic forecasts, scenario analysis, Brier score calibration, and ecosystem regime modeling.
- **Runtime:** Python 3.11.9
- **Entry Point:** `futuris.cli:serve` (Uvicorn, Port `8000`)
- **Key Files:**
  - Dependencies: `requirements.txt`, `pyproject.toml`
  - Docker: `Dockerfile`, `docker-compose.yml`
  - Alembic: `alembic.ini` present
- **Git Status:**
  - Branch: `main`
  - Local HEAD: `6d9040bf71a40ccdacc57e841e819c8b678eaa9a` (Matches remote `origin/main`)
  - Modified: Research notes in `notes/`
- **Routes & Mesh Contracts:**
  - Internal Only: `/health`, `/api/v1/forecast`, `/api/v1/scenarios`, `/api/v1/calibration`
- **Persistence:**
  - Current: SQLite `futuris.db`
  - Target: PostgreSQL `futuris_db` (forecast runs, scenarios, outcome resolutions, calibration records)

---

## 3. Port & Network Mesh Summary

| Subsystem | Container Hostname | Internal Port | Host Port Binding (Current) | Recommended Host Port Binding (Target) |
|-----------|--------------------|---------------|------------------------------|-----------------------------------------|
| FRIDAY | `friday` | `10000` | `10000:10000` | `10000:10000` (or behind Caddy/Traefik) |
| Inference | `inference` | `8000` | `8004:8004` (Misconfigured) | Private only (no host port) |
| Memora | `memora` | `8000` | `8006:8006` (Misconfigured) | Private only (no host port) |
| Stratex | `stratex` | `8000` | `8008:8008` (Misconfigured) | Private only (no host port) |
| Forge | `forge` | `8000` | `8002:8002` (Misconfigured) | Private only (no host port) |
| Cortex | `cortex` | `8000` | `8001:8001` (Misconfigured) | Private only (no host port) |
| Sentinel | `sentinel` | `8000` | `8007:8007` (Misconfigured) | Private only (no host port) |
| IntelX | `intelx` | `8000` | `8005:8005` (Misconfigured) | Private only (no host port) |
| Futuris | `futuris` | `8000` | `8003:8003` (Misconfigured) | Private only (no host port) |
| PostgreSQL | `postgres` | `5432` | `0.0.0.0:5432` (Exposed!) | `127.0.0.1:5432` or mesh internal only |
| Redis | `redis` | `6379` | `127.0.0.1:6379` | `127.0.0.1:6379` or mesh internal only |
| Qdrant | `qdrant` | `6333` | `127.0.0.1:6333` | `127.0.0.1:6333` or mesh internal only |
