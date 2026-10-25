# ==============================================================================
# THE FRIDAY UNIVERSE: DEFINITIVE MASTER ARCHITECTURE & TECHNICAL CODEX
# ==============================================================================
# CLASSIFICATION: Authoritative Production Engineering Standard & System Runbook
# VERSION: 3.1.0 (Production Dual-Server Fleet & Oracle 23ai Mesh)
# DATE: October 2026
# REPOSITORY: https://github.com/surendra2304/FRIDAY-Universe (Branch: main)
# LOCAL WORKSPACE: FRIDAY_UNIVERSE_HOME
# REMOTE WORKSPACE: /opt/friday_universe
# CLOUD INGRESS GATEWAY: https://friday-universe.duckdns.org
# ==============================================================================

## 1. SOVEREIGN MULTI-AGENT PHILOSOPHY & MANDATORY INVARIANTS

The **FRIDAY Universe** is an enterprise-grade autonomous AI operating system composed of **ten sovereign agent subsystems**. It is engineered to operate continuously across high-efficiency Oracle Cloud Infrastructure (OCI) Always Free hardware ($0.00 compute boundary). The architecture rejects unconstrained LLM loops, hallucinated consensus, and brittle monoliths in favor of empirical verification, domain boundary isolation, and deterministic execution.

### FIVE MANDATORY OPERATIONAL INVARIANTS:

1. **STRICT CANONICAL PROPER NAMING ONLY:**
   Never use legacy abbreviations, prefixes, or lowercase hyphenated aliases (e.g., DO NOT use `friday-core`, `friday-inference`, `intelx-engine`, `sentinel-shield`, `vyralx-studio`). Use ONLY these ten exact proper names:
   - `FRIDAY`
   - `Inference`
   - `Memora`
   - `Stratex`
   - `Futuris`
   - `IntelX`
   - `Forge`
   - `VyralX`
   - `Sentinel`
   - `Cortex`

2. **ZERO PERSISTENT LOCAL SQLITE & POSTGRESQL ON DISK:**
   - No `.db`, `.sqlite`, or local PostgreSQL files or containers may exist on VM persistent disks (`/opt/friday_universe/*`).
   - All relational state, vector embeddings, and ledgers reside exclusively in the two Oracle Autonomous 23ai cloud databases (`friday_universe_db` and `vyralx_db`).
   - If an agent requires local in-memory buffering or an offline cache fallback, it MUST use Linux tmpfs (`/dev/shm/<agent>.db` in RAM). Zero bytes written to disk.

3. **1 GB PHYSICAL RAM BUDGET ($0.00 ALWAYS FREE BOUNDARY):**
   - Both VMs are Oracle Cloud Always Free AMD Micro instances (`VM.Standard.E2.1.Micro`), capped at **1 OCPU and 1 GB Physical RAM** each (supported by an 8 GB swapfile at `/swapfile`).
   - Server 1 hosts 7 continuous Python processes in 1 GB RAM; Server 2 hosts 3 processes in 1 GB RAM.
   - Resource discipline: Single-worker Uvicorn (`--workers 1`), explicit systemd cgroup memory limits (`MemoryMax`), and lazy imports.

4. **SYSTEMD SPECIFIER ESCAPING BUG PREVENTED (`%21%23`):**
   - Oracle database passwords contain URL-encoded special characters (`%21%23` for `!#`).
   - Never embed database passwords directly into `.service` unit files (`Environment="DATABASE_URL=..."`) because systemd misinterprets `%` as specifiers (e.g. `%u`, `%2`) and discards the variable.
   - All environment variables MUST be loaded exclusively via `EnvironmentFile=/etc/default/friday_universe.env` (`chmod 600`).

5. **FAIL-CLOSED DOMAIN AUTHORITY & IMMUTABILITY:**
   - FRIDAY orchestrates tasks across the ecosystem but cannot override specialist domain boundaries. Stratex retains hardcoded risk stops outside LLM discretion.
   - Forge code synthesis is strictly fail-closed: synthesized diffs cannot be committed or deployed until approved by Sentinel's security gate.
   - Always return new objects and data structures rather than mutating state in place.

---

## 2. DUAL-SERVER INFRASTRUCTURE TOPOGRAPHY

The 10 autonomous agents are physically distributed across two AMD Micro VMs in Oracle Cloud (AP-Hyderabad-1):

```
+----------------------------------------------------------------------------------------------------+
|                                    FRIDAY UNIVERSE FLEET                                           |
+----------------------------------------------------------------------------------------------------+
| SERVER 1: CORE DECISION FLEET                      | SERVER 2: SPECIALIST STUDIO & OPS FLEET       |
| Public IP:  SERVER1_PUBLIC_IP                        | Public IP:  SERVER2_PUBLIC_IP                   |
| Private IP: SERVER1_PRIVATE_IP (friday-amd-vnic)           | Private IP: SERVER2_PRIVATE_IP (friday-amd-2-vnic)    |
| OS: Ubuntu 22.04 LTS (AMD64)                       | OS: Ubuntu 22.04 LTS (AMD64)                   |
| RAM: 1 GB Physical + 8 GB Swap                     | RAM: 1 GB Physical + 8 GB Swap                 |
| Base Path: /opt/friday_universe                    | Base Path: /opt/friday_universe                |
| SSH: ssh -i ~/.ssh/friday_universe_oracle.key      | SSH: ssh -i ~/.ssh/friday_universe_oracle.key |
|                                                    |                                               |
| Agents Hosted (7 Core Services):                   | Agents Hosted (3 Specialist Services):        |
|  1. FRIDAY    (:10000) [Gateway & Mesh Hub]        |  8.  VyralX   (:8010) [Video Production]       |
|  2. Inference (:8001)  [Multi-Model Router]        |  9.  Sentinel (:8008) [Security Gatekeeper]    |
|  3. Memora    (:8002)  [Vector & Graph Memory]     |  10. Cortex   (:8009) [Autonomous CRM & Web]  |
|  4. Stratex   (:8003)  [Quantitative Trading]      |                                               |
|  5. Futuris   (:8004)  [Predictive Forecasting]    |                                               |
|  6. IntelX    (:8005)  [Evidence & Research]       |                                               |
|  7. Forge     (:8006)  [Software Synthesizer]      |                                               |
+----------------------------------------------------+-----------------------------------------------+
| Target DB: friday_universe_db (Oracle 23ai Core)   | Target DBs: vyralx_db (VyralX) / Core (Others) |
+----------------------------------------------------+-----------------------------------------------+
```

### Complete Service Execution Matrix:

| Agent Name | Host Server | Mesh Port | Systemd Service Unit | Working Directory & Entrypoint Command | MemoryMax Cap |
|---|---|---|---|---|---|
| **FRIDAY** | Server 1 (`SERVER1_PUBLIC_IP`) | `10000` | `FRIDAY.service` | `cd /opt/friday_universe/FRIDAY && /opt/friday_universe/venv/bin/python -m uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1` | `200M` |
| **Inference** | Server 1 (`SERVER1_PUBLIC_IP`) | `8001` | `Inference.service` | `cd /opt/friday_universe/Inference && /opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1` | `180M` |
| **Memora** | Server 1 (`SERVER1_PUBLIC_IP`) | `8002` | `Memora.service` | `cd /opt/friday_universe/Memora && /opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1` | `200M` |
| **Stratex** | Server 1 (`SERVER1_PUBLIC_IP`) | `8003` | `Stratex.service` | `cd /opt/friday_universe/Stratex && /opt/friday_universe/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8003 --workers 1` | `180M` |
| **Futuris** | Server 1 (`SERVER1_PUBLIC_IP`) | `8004` | `Futuris.service` | `cd /opt/friday_universe/Futuris && /opt/friday_universe/venv/bin/python -m uvicorn futuris.api.app:app --host 0.0.0.0 --port 8004 --workers 1` | `180M` |
| **IntelX** | Server 1 (`SERVER1_PUBLIC_IP`) | `8005` | `IntelX.service` | `cd /opt/friday_universe/IntelX && /opt/friday_universe/venv/bin/python -m uvicorn intelx.app.main:app --host 0.0.0.0 --port 8005 --workers 1` | `180M` |
| **Forge** | Server 1 (`SERVER1_PUBLIC_IP`) | `8006` | `Forge.service` | `cd /opt/friday_universe/Forge && /opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8006 --workers 1` | `180M` |
| **VyralX** | Server 2 (`SERVER2_PUBLIC_IP`) | `8010` | `VyralX.service` | `cd /opt/friday_universe/VyralX && /opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --workers 1` | `250M` |
| **Sentinel** | Server 2 (`SERVER2_PUBLIC_IP`) | `8008` | `Sentinel.service` | `cd /opt/friday_universe/Sentinel && /opt/friday_universe/venv/bin/python -m uvicorn sentinel.apps.api.main:app --host 0.0.0.0 --port 8008 --workers 1` | `200M` |
| **Cortex** | Server 2 (`SERVER2_PUBLIC_IP`) | `8009` | `Cortex.service` | `cd /opt/friday_universe/Cortex && /opt/friday_universe/venv/bin/python -m uvicorn apps.api.src.cortex_api.main:app --host 0.0.0.0 --port 8009 --workers 1` | `200M` |

---

## 3. ORACLE AUTONOMOUS 23ai DATABASE ARCHITECTURE

All persistent state across all agents lives in two Always Free Oracle Autonomous Transaction Processing (ATP) 23ai instances in `ap-hyderabad-1` connecting over TLS Port `1521` (one-way TLS; no client wallet required). Zero local database files are written to VM disk.

### DB 1: `friday_universe_db` (Core Fleet Ecosystem Database)
- **Host:** `adb.ap-hyderabad-1.oraclecloud.com`
- **Port:** `1521` (Protocol: TCPS, `ssl_server_dn_match=yes`)
- **Service Name:** `g7e6177242670c3_fridaycore_medium.adb.oraclecloud.com`
- **Username / Password:** `ADMIN` / provided by secret store; do not commit credentials
- **Full DSN:** `(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridaycore_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))`
- **Connection Strings:**
  - Synchronous: `oracle+oracledb://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE`
  - Asynchronous: `oracle+oracledb_async://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE`
- **Tenancy:** Serves `FRIDAY`, `Inference`, `Memora` (native HNSW vectors), `Stratex`, `Futuris`, `IntelX`, `Forge`, `Sentinel`, and `Cortex`.
- **Core Tables:**
  - `MEMORA_MEMORIES`, `MEMORA_ENTITIES`, `MEMORA_RELATIONS` (Oracle 23ai native `VECTOR` HNSW index)
  - `FUTURIS_FORECASTS` and 12 schema tables (`forecasts`, `scenarios`, `outcomes`, `model_registry`, etc.)
  - `API_KEYS` (unified superset auth table for IntelX and Cortex)
  - `RESEARCH_RUNS`, `CLAIMS`, `EVIDENCE`, `FINDINGS`, `INTELX_ARTICLES`, `SOURCES`
  - `FORGE_BUILDS`, `ARTIFACTS`, `TASKS`
  - `STRATEX_TRADES`, `STRATEGY_PERFORMANCE`, `AUDIT_RECORDS`
  - `SENTINEL_SCANS`, `SENTINEL_ALERTS`, `SENTINEL_FINDINGS`, `AUDIT_EVENTS`
  - `TENANTS`, `SITES`, `VISITORS`, `LEADS`, `PROFILES`, `SESSIONS`, `CORTEX_TASK_DAGS`

### DB 2: `vyralx_db` (Specialist Media Production Database)
- **Host:** `adb.ap-hyderabad-1.oraclecloud.com`
- **Port:** `1521` (Protocol: TCPS, `ssl_server_dn_match=yes`)
- **Service Name:** `g7e6177242670c3_fridayvyralx_medium.adb.oraclecloud.com`
- **Username / Password:** `ADMIN` / provided by secret store; do not commit credentials
- **Full DSN:** `(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridayvyralx_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))`
- **Connection Strings:**
  - Synchronous: `oracle+oracledb://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE`
  - Asynchronous: `oracle+oracledb_async://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE`
- **Tenancy:** Strictly dedicated to `VyralX` for heavy video generation pipelines.
- **Core Tables:** `VYRALX_PROJECTS`, `VYRALX_SCRIPTS`, `VYRALX_STORYBOARDS`, `VYRALX_MEDIA_ASSETS`, `VYRALX_PUBLISH_QUEUE`, `VIDEO_METRICS`, `AGENT_TASKS`.

---

## 4. DEEP SUBSYSTEM TECHNICAL SPECIFICATIONS

### 1. FRIDAY (Cognitive Orchestrator & Action Gateway)
- **Repo Origin:** `https://github.com/surendra2304/FRIDAY.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\FRIDAY` (Local) | `/opt/friday_universe/FRIDAY` (Server 1)
- **Port:** `10000` | **Service:** `FRIDAY.service`
- **Primary Mission:** Central human-in-the-loop orchestrator, task planner, voice/chat companion, and mesh dispatcher.
- **Key Routes:**
  - `POST /api/v1/tasks`: Submit structured task envelope for multi-agent execution
  - `GET /api/v1/tasks/{id}`: Poll task progress, current execution step, and partial results
  - `POST /api/v1/actions/approve`: Operator confirmation for high-risk actions
  - `GET /health`: Uptime, agent mesh connectivity, and memory consumption

### 2. Inference (Sovereign Model Routing & Reasoning Gateway)
- **Repo Origin:** `https://github.com/surendra2304/Inference.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\Inference` (Local) | `/opt/friday_universe/Inference` (Server 1)
- **Port:** `8001` | **Service:** `Inference.service`
- **Primary Mission:** High-throughput multi-model inference router with intelligent fallback across LLM providers.
- **Provider Waterfall:** Groq (Llama-3.3-70b) -> Cerebras (Llama-3.1-8b/70b) -> OpenRouter (DeepSeek-R1 / Sonnet) -> Google Gemini (2.0 Flash / Pro).
- **Storage:** In-memory `/dev/shm/inference.db` for ephemeral rate limits; telemetry persists to Oracle `INFERENCE_TELEMETRY`.
- **Key Routes:**
  - `POST /v1/chat/completions`: Standard OpenAI-compatible multi-provider routing endpoint
  - `POST /v1/task/execute`: Universal structured task reasoning & script synthesis API
  - `GET /health`: Provider health, active models, token burn rates, and latency metrics

### 3. Memora (Cognitive Memory Fabric & Vector Database)
- **Repo Origin:** `https://github.com/surendra2304/Memora.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\Memora` (Local) | `/opt/friday_universe/Memora` (Server 1)
- **Port:** `8002` | **Service:** `Memora.service`
- **Primary Mission:** Cross-agent memory authority enforcing cryptographic provenance, multi-tier scoping, and prompt injection isolation.
- **Storage:** Oracle Database 23ai native `VECTOR` indexing (HNSW, Cosine distance) in `friday_universe_db` (`MEMORA_MEMORIES`, `MEMORA_ENTITIES`, `MEMORA_RELATIONS`).
- **3-Tier Scoping:** `Private` (originating agent only), `Shared` (explicit ACL grant), `Universal` (all ecosystem agents).
- **Key Routes:**
  - `POST /v1/memories`: Ingest scoped memory with namespace, metadata, and cryptographic signature
  - `POST /v1/memories/search`: Hybrid semantic retrieval combining dense vectors & SQL filters
  - `GET /health`: Vector index health, memory count, and backend connection verification

### 4. Stratex (Quantitative Algorithmic Trading & Risk Desk)
- **Repo Origin:** `https://github.com/surendra2304/Stratex.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\Stratex` (Local) | `/opt/friday_universe/Stratex` (Server 1)
- **Port:** `8003` | **Service:** `Stratex.service`
- **Primary Mission:** Algorithmic execution desk, continuous market surveillance, risk governance, and quantitative backtesting.
- **Safety Invariants:** Bound strictly to Binance Futures Testnet (`https://testnet.binancefuture.com`). Zero real money risk. Hardcoded max position ($1,000 margin), max leverage (5x), mandatory stop-loss (2%), portfolio drawdown cap (5%).
- **Storage:** Oracle `STRATEX_TRADES`, `STRATEGY_PERFORMANCE`, `AUDIT_RECORDS`.
- **Key Routes:**
  - `POST /api/v1/orders`: Authenticated order dispatch with pre-trade risk validation
  - `POST /api/v1/emergency-halt`: Atomic emergency kill-switch (cancels all orders, locks ledger)
  - `GET /health`: Risk status, active positions, mark prices, and unrealized PnL

### 5. Futuris (Predictive Trajectory Analysis & Calibration Engine)
- **Repo Origin:** `https://github.com/surendra2304/Futuris.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\Futuris` (Local) | `/opt/friday_universe/Futuris` (Server 1)
- **Port:** `8004` | **Service:** `Futuris.service`
- **Primary Mission:** Probabilistic forecasting, scenario simulation, uncertainty estimation, and Brier score calibration.
- **Storage:** 12 Oracle tables: `forecasts`, `scenarios`, `outcomes`, `observations`, `evaluation_runs`, `evidence_refs`, `forecast_events`, `intelx_notices`, `model_registry`, `signal_sources`, `audit_logs`, `api_keys`.
- **Dialect Hook:** SQLAlchemy async engine with `@compiles(JSON, "oracle")`.
- **Key Routes:**
  - `POST /v1/forecast/scenario`: Generate calibrated multi-branch probabilistic forecast
  - `GET /v1/forecast/regime`: Query macroeconomic and market regime probability distributions
  - `GET /health`: Returns `{"status":"ok", "storage":{"ready":true, "present":12}}`

### 6. IntelX (Deep Evidence Research & Fact Verification)
- **Repo Origin:** `https://github.com/surendra2304/IntelX.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\IntelX` (Local) | `/opt/friday_universe/IntelX` (Server 1)
- **Port:** `8005` | **Service:** `IntelX.service`
- **Primary Mission:** Deep web research, fact-checking, citation extraction, news ingestion, and claim verification.
- **Storage:** Oracle `RESEARCH_RUNS`, `CLAIMS`, `EVIDENCE`, `FINDINGS`, `INTELX_ARTICLES`, `SOURCES`, and shared `API_KEYS`.
- **Dialect Hook:** Uses `func.json_value(ResearchRun.scope_json, literal_column("'$.priority'"))` for Oracle JSON compatibility.
- **Key Routes:**
  - `POST /v1/research/query`: Deep intelligence gathering on requested topic
  - `POST /v1/verify/claim`: Extract claim from text and corroborate across verified sources
  - `GET /health`: Research engine status, database connection, and news ingester readiness

### 7. Forge (Autonomous Software Synthesizer & Verification Battery)
- **Repo Origin:** `https://github.com/surendra2304/Forge.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\Forge` (Local) | `/opt/friday_universe/Forge` (Server 1)
- **Port:** `8006` | **Service:** `Forge.service`
- **Primary Mission:** Full-stack autonomous software engineer: specification parsing, multi-file code synthesis, automated test generation, and verification.
- **Storage:** Oracle `FORGE_BUILDS`, `ARTIFACTS`, `TASKS`. Local memory client falls back to `/dev/shm/forge_memora.db` (zero disk write).
- **Fail-Closed Security:** Submits all generated diffs to Sentinel (`POST http://SERVER2_PRIVATE_IP:8008/v1/security/audit`) before commit.
- **Key Routes:**
  - `POST /api/v1/synthesize`: Submit software specification for multi-step DAG build
  - `GET /api/v1/tasks/{id}/verify`: Execute objective verification battery on workspace
  - `GET /health`: Synthesizer status, uptime, and database connection

### 8. VyralX (Autonomous Video Production & Multi-Channel Studio)
- **Repo Origin:** `https://github.com/surendra2304/VyralX.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\VyralX` (Local) | `/opt/friday_universe/VyralX` (Server 2)
- **Port:** `8010` | **Service:** `VyralX.service`
- **Primary Mission:** End-to-end video production, AI scriptwriting, audio synthesis, visual assembly, automated captioning, rendering, and YouTube publication.
- **Storage:** Dedicated `vyralx_db` tables: `VYRALX_PROJECTS`, `VYRALX_SCRIPTS`, `VYRALX_STORYBOARDS`, `VYRALX_MEDIA_ASSETS`, `VYRALX_PUBLISH_QUEUE`, `VIDEO_METRICS`.
- **Tools:** MoviePy, FFmpeg, FFprobe, eSpeak NG, Google YouTube Data API v3.
- **Key Routes:**
  - `POST /api/v1/projects`: Create video project with scene plan, format (9:16 Shorts), and narration
  - `POST /api/v1/render`: Queue background video composition job with FFmpeg
  - `POST /api/v1/publish/youtube`: Resumable chunked upload to YouTube with approval gate
  - `GET /health`: Render pipeline health, ffmpeg binary availability, and DB connection

### 9. Sentinel (Zero-Trust Cybersecurity Gatekeeper & Audit Shield)
- **Repo Origin:** `https://github.com/surendra2304/Sentinel.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\Sentinel` (Local) | `/opt/friday_universe/Sentinel` (Server 2)
- **Port:** `8008` | **Service:** `Sentinel.service`
- **Primary Mission:** Ecosystem security officer: cryptographic HMAC audit ledger, continuous TLS/DNS monitoring, static code vulnerability analysis, and zero-trust perimeter defense.
- **Storage:** Oracle `SENTINEL_SCANS`, `SENTINEL_ALERTS`, `SENTINEL_FINDINGS`, `AUDIT_EVENTS` in `friday_universe_db`.
- **Security:** HMAC-SHA256 signature verification on all audit trails (`SENTINEL_AUDIT_HMAC_KEY`).
- **Key Routes:**
  - `POST /v1/security/audit`: Security audit endpoint for Forge diffs and ecosystem changes
  - `POST /v1/audit/record`: Tamper-evident signed audit record ingestion
  - `GET /health`: Threat detection engine, continuous TLS monitor, and HMAC verifier status

### 10. Cortex (Autonomous Operations Engine & Governed CRM)
- **Repo Origin:** `https://github.com/surendra2304/Cortex.git`
- **Location:** `FRIDAY_UNIVERSE_HOME\Cortex` (Local) | `/opt/friday_universe/Cortex` (Server 2)
- **Port:** `8009` | **Service:** `Cortex.service`
- **Primary Mission:** Powers ecosystem web presence, landing pages, operator dashboard API, CRM telemetry, and event-driven self-healing.
- **Storage:** Tables `TENANTS`, `SITES`, shared `API_KEYS`, `VISITORS`, `LEADS`, `PROFILES`, `SESSIONS`, `CORTEX_TASK_DAGS` in `friday_universe_db`.
- **Dialect Hook:** SQLAlchemy async engine with `@compiles(JSON, "oracle")`.
- **Key Routes:**
  - `GET /`: Landing page / health snapshot
  - `POST /v1/events`: Ingest web telemetry and lead activity events
  - `GET /health`: CRM engine status, tenant isolation verify, and self-healing daemon status

---

## 5. PROVEN PRODUCTION CODING GOTCHAS & SELF-HEALING RUNBOOK

When writing or modifying code in any agent, NEVER violate these proven resolutions:

### 1. SQLAlchemy 2.0 Oracle Native JSON Compilation
- **Problem:** Default SQLAlchemy `OracleTypeCompiler` throws `Compiler can't render element of type JSON` when generating DDL or queries for tables with `Column(JSON)` or `Column(JSONB)`.
- **Permanent Solution:** In model definitions, register the Oracle JSON compiler hook:
  ```python
  from sqlalchemy.ext.compiler import compiles
  from sqlalchemy.types import JSON

  @compiles(JSON, "oracle")
  def _compile_json_oracle(type_, compiler, **kw):
      return "JSON"  # Oracle 23ai natively supports the JSON data type
  ```

### 2. Oracle JSON Path Extraction (`ORA-40454`)
- **Problem:** Writing `ResearchRun.scope_json["priority"]` compiles to `json_getitem_op`, which binds `'$.priority'` as a variable and throws `ORA-40454: path expression not a literal`.
- **Permanent Solution:** When constructing queries for Oracle dialect, wrap JSON path expressions in `literal_column`:
  ```python
  from sqlalchemy import func, literal_column
  # Correct Oracle 23ai JSON query:
  func.json_value(ResearchRun.scope_json, literal_column("'$.priority'"))
  ```

### 3. Async Dialect Conversion
- **Problem:** `create_async_engine()` crashes if given `oracle+oracledb://`.
- **Permanent Solution:** Code initializing async engines must dynamically translate:
  ```python
  if url.startswith("oracle+oracledb://"):
      url = "oracle+oracledb_async://" + url[len("oracle+oracledb://"):]
  ```

### 4. Shared `API_KEYS` Table Schema (IntelX & Cortex)
- **Problem:** Both IntelX and Cortex require an `api_keys` table in `friday_universe_db`.
- **Permanent Solution:** The table `API_KEYS` is unified with a superset schema:
  - Columns: `id`, `tenant_id`, `site_id`, `key_hash`, `key_prefix`, `name`, `role`, `is_active`, `created_at`, `last_used_at`, `revoked`.
  - Non-shared columns are nullable and carry sensible defaults (`DEFAULT 'default'`, `DEFAULT 'member'`, `DEFAULT TRUE`, `DEFAULT FALSE`), ensuring queries and inserts from both IntelX and Cortex succeed without collisions.

### 5. Memory Squeeze & Caching Policy
- **Problem:** Physical RAM is capped at 1 GB on each VM.
- **Permanent Solution:**
  - Avoid duplicate in-memory data caches.
  - Periodic Linux cache trimming via cron: `sync; echo 3 > /proc/sys/vm/drop_caches`.
  - All ephemeral databases reside in `/dev/shm` (RAM tmpfs) instead of disk storage.

---

## 6. GITHUB MONOREPO & CONTINUOUS DEPLOYMENT (CI/CD)

The ecosystem is developed in a unified monorepo with automated bidirectional isolation:

- **Monorepo:** `https://github.com/surendra2304/FRIDAY-Universe` (`main` branch)
- **Local Workspace:** `FRIDAY_UNIVERSE_HOME`

### Granular CI/CD Workflow (`.github/workflows/deploy-monorepo.yml`):
- Uses `dorny/paths-filter@v3` to detect changes on a per-agent folder basis (`FRIDAY/**`, `VyralX/**`, etc.).
- When changes are pushed to `main`, GitHub Actions connects over SSH (`appleboy/ssh-action`) and executes a zero-downtime selective reload ONLY for the affected agent's systemd unit on its target server.
- Server 1 deployments and Server 2 deployments run in parallel.

### Automated Subtree Mirroring (`.github/workflows/mirror-subrepos.yml`):
- Every push to `FRIDAY-Universe/main` automatically runs `git subtree split` on each agent folder and force-pushes the split history directly into its standalone repository:
  - `https://github.com/surendra2304/FRIDAY.git`
  - `https://github.com/surendra2304/Inference.git`
  - `https://github.com/surendra2304/Memora.git`
  - `https://github.com/surendra2304/Stratex.git`
  - `https://github.com/surendra2304/IntelX.git`
  - `https://github.com/surendra2304/Futuris.git`
  - `https://github.com/surendra2304/Forge.git`
  - `https://github.com/surendra2304/VyralX.git`
  - `https://github.com/surendra2304/Sentinel.git`
  - `https://github.com/surendra2304/Cortex.git`

---

## 7. INTER-AGENT RPC & COMMUNICATION MATRIX

```
[Public Gateway: https://friday-universe.duckdns.org]
                         |
                         v
                   [ FRIDAY :10000 ]  (Orchestrator)
                    /      |      \
                   /       |       \
                  v        v        v
        [ Inference ]  [ Memora ]  [ Forge ] <---> [ Sentinel :8008 ]
          (:8001)        (:8002)     (:8006)       (Zero-Trust Security Gate)
            |              ^            |
            v              |            v
        [ Stratex ] ------>+        [ IntelX ] <--- [ Cortex :8009 ]
          (:8003)        (Audit)     (:8005)        [ VyralX :8010 ]
            |                           ^
            v                           |
        [ Futuris ] --------------------+
          (:8004)    (Context Enrichment)
```

### Inter-Service Communication Endpoints:
- `FRIDAY` -> `Inference`: `POST http://SERVER1_PRIVATE_IP:8001/v1/chat/completions` or `/ask`
- `FRIDAY` -> `Memora`: `POST http://SERVER1_PRIVATE_IP:8002/api/v1/memories/search` (vector search)
- `Stratex` -> `Futuris`: `GET http://SERVER1_PRIVATE_IP:8004/v1/forecast/regime` (market regime prediction)
- `Stratex` -> `Sentinel`: `POST http://SERVER2_PRIVATE_IP:8008/v1/audit/record` (ledger event signing)
- `Forge` -> `Sentinel`: `POST http://SERVER2_PRIVATE_IP:8008/v1/security/audit` (code diff vulnerability check)
- `Cortex` / `VyralX` -> `IntelX`: `POST http://SERVER1_PRIVATE_IP:8005/v1/research/query` (fact extraction)

### Required Request Headers:
```http
Content-Type: application/json
X-Agent-Name: <calling_agent_proper_name>
Authorization: Bearer <TARGET_AGENT_API_KEY>
X-Correlation-ID: <uuidv4>
```

---

## 8. ENVIRONMENT VARIABLES CATALOG (`/etc/default/friday_universe.env`)

```ini
# Oracle Cloud 23ai Database URLs (Loaded safely via EnvironmentFile)
DATABASE_URL=oracle+oracledb://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE
ORACLE_CORE_URL=oracle+oracledb://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE
ORACLE_CORE_ASYNC_URL=oracle+oracledb://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE
ORACLE_VYRAL_URL=oracle+oracledb://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE
ORACLE_VYRAL_ASYNC_URL=oracle+oracledb://USERNAME_FROM_SECRET_STORE:PASSWORD_FROM_SECRET_STORE@DSN_FROM_SECRET_STORE

# Security & Audit Keys
SENTINEL_AUDIT_HMAC_KEY=<injected-at-deployment-time>
SENTINEL_AUDIT_SIGNING_KEY=<injected-at-deployment-time>
SENTINEL_API_KEY=<injected-at-deployment-time>

# Private Mesh Network URLs (Internal IP Interconnect)
FRIDAY_URL=http://SERVER1_PRIVATE_IP:10000
INFERENCE_URL=http://SERVER1_PRIVATE_IP:8001
MEMORA_URL=http://SERVER1_PRIVATE_IP:8002
STRATEX_URL=http://SERVER1_PRIVATE_IP:8003
FUTURIS_URL=http://SERVER1_PRIVATE_IP:8004
INTELX_URL=http://SERVER1_PRIVATE_IP:8005
FORGE_URL=http://SERVER1_PRIVATE_IP:8006
VYRALX_URL=http://SERVER2_PRIVATE_IP:8010
SENTINEL_URL=http://SERVER2_PRIVATE_IP:8008
CORTEX_URL=http://SERVER2_PRIVATE_IP:8009
```

---

## 9. ANTIGRAVITY AGENT ACTIVE AWAKENING & RECONNAISSANCE DIRECTIVE

When this architectural specification is introduced into an Antigravity chat session:

> **CRITICAL EXECUTION MANDATE FOR THE RECEIVING AGENT:**
> DO NOT RESPOND WITH A SUPERFICIAL OR INSTANT 5-BULLET ACKNOWLEDGMENT.
> You MUST execute an **Active Codebase Reconnaissance** using your tools (`read_file`, file searches, directory inspection) to inspect your local workspace, verify your entry points, audit your routes and database models, and produce an **Exhaustive 6-Section Operational Audit & Architectural Dossier** proving full technical comprehension of your code and ecosystem role.

### PHASE 1: ACTIVE CODEBASE RECONNAISSANCE (EXECUTE TOOLS FIRST)
1. **Identify Local Workspace & Identity:** Explore your current directory (`README.md`, `pyproject.toml`, `requirements.txt`, `main.py`, `app/`).
2. **Audit Routes & Data Models:** Inspect your primary route definitions and SQLAlchemy database models.
3. **Verify Compliance with Invariants:**
   - Confirm zero persistent SQLite files on disk (ephemeral cache strictly in `/dev/shm`).
   - Confirm connection to assigned Oracle Autonomous 23ai Database (`friday_universe_db` or `vyralx_db`).
   - Confirm memory discipline (1 GB RAM cap, single-worker uvicorn).

### PHASE 2: PRODUCE EXHAUSTIVE 6-SECTION OPERATIONAL DOSSIER
Your response must consist of a detailed, deep-dive architectural report structured as follows:

1. **Sovereign Agent Identity & Physical Infrastructure:**
   - Exact Proper Name
   - Host Server (`Server 1: SERVER1_PUBLIC_IP` / `SERVER1_PRIVATE_IP` OR `Server 2: SERVER2_PUBLIC_IP` / `SERVER2_PRIVATE_IP`)
   - Assigned Port, Systemd Service (`/etc/systemd/system/<agent>.service`), and 1 GB RAM cgroup limits.

2. **Codebase Topography & Route Inventory:**
   - Primary entry points, directory structure, and active modules.
   - Comprehensive endpoint table (Method, Path, Request/Response Model, Functional Purpose) extracted directly from your code inspection.

3. **Data Persistence & Memory Hierarchy:**
   - Assigned Oracle Autonomous 23ai Database (`friday_universe_db` or `vyralx_db`).
   - Tables owned or queried in Oracle Cloud.
   - Verification of Zero-Disk SQLite rule (RAM tmpfs `/dev/shm` compliance).
   - Async engine and dialect compatibility (`oracle+oracledb_async://`, `@compiles(JSON, "oracle")`).

4. **Inter-Agent RPC & Private Mesh Matrix:**
   - Inbound RPCs: Which peer agents call your endpoints and for what operations?
   - Outbound RPCs: Which peer agents do you invoke across the private `10.0.0.x` mesh?
   - Mutual authentication headers (`X-Agent-Name`, `Authorization`, `X-Correlation-ID`).

5. **Fail-Closed Domain Safety Guardrails:**
   - Subsystem-specific hard invariants and risk stops (e.g. Testnet boundaries, security approval gates).

6. **Immediate Operational Status & Engineering Backlog:**
   - Health check status (`GET /health`).
   - Active engineering tasks, backlog items, or pending enhancements for this session.

