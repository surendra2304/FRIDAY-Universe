# The FRIDAY Universe: Definitive Master Architecture & Technical Codex

> **Document Version:** 2.5.0  
> **Classification:** Internal System Architecture & Engineering Standard  
> **Master PDF Specification:** [`FRIDAY_UNIVERSE_MASTER_ARCHITECTURE.pdf`](file:///D:/FRIDAY%20Universe/FRIDAY_UNIVERSE_MASTER_ARCHITECTURE.pdf) | [`README.pdf`](file:///D:/FRIDAY%20Universe/README.pdf)  
> **Master Credentials & Access:** [`CREDENTIALS.md`](file:///D:/FRIDAY%20Universe/CREDENTIALS.md) | [`CREDENTIALS.pdf`](file:///D:/FRIDAY%20Universe/CREDENTIALS.pdf)  
> **Ecosystem Repositories:** [FRIDAY](file:///D:/FRIDAY%20Universe/FRIDAY) | [Inference](file:///D:/FRIDAY%20Universe/Inference) | [Memora](file:///D:/FRIDAY%20Universe/Memora) | [Stratex](file:///D:/FRIDAY%20Universe/Stratex) | [Forge](file:///D:/FRIDAY%20Universe/Forge) | [Cortex](file:///D:/FRIDAY%20Universe/Cortex) | [Sentinel](file:///D:/FRIDAY%20Universe/Sentinel) | [IntelX](file:///D:/FRIDAY%20Universe/IntelX) | [Futuris](file:///D:/FRIDAY%20Universe/Futuris) | [VyralX](file:///D:/FRIDAY%20Universe/VyralX)  
> **Local Workspace Root:** `D:\FRIDAY Universe`  
> **Cloud Ingress Gateway:** `https://friday-universe.duckdns.org`  
> **Dokploy PaaS Portal:** `https://dokploy.friday-universe.duckdns.org`  
> **Unified MCP Gateway:** `https://friday-universe.duckdns.org/mcp`  

---

## 1. Executive Summary & Sovereign Multi-Agent Philosophy

**The FRIDAY Universe** is an autonomous, sovereign multi-agent cognitive architecture comprising **ten specialized subsystems** designed to operate cohesively as an intelligent personal operating system, autonomous software synthesizer, algorithmic trading desk, threat-hunting security operations center, deep research analyst, predictive forecasting engine, and autonomous video production & multi-channel distribution studio.

Unlike naive multi-agent architectures that rely on unconstrained LLM loops, hallucinated consensus, or brittle monoliths, the FRIDAY Universe adheres to five non-negotiable core engineering tenets:

1. **Evidence Over Model Confidence:** Agreement between AI models does not constitute ground truth. All decisions, code executions, trade entries, and security disclosures require verifiable, empirical evidence (AST parsing, unit test executions, cryptographic signatures, HTTP receipts, or exchange ledger balances).
2. **Domain Authority & Non-Bypassable Safety Gates:** FRIDAY orchestrates tasks across the ecosystem but cannot override specialist domain boundaries. Stratex retains independent hard risk limits outside LLM discretion. Forge executes inside isolated sandboxes with strict path traversal confinement. Sentinel maintains pre-delivery code review veto power.
3. **Decoupled 3-Tier Memory Authority:** Memory is never scattered across ad-hoc files or mirrored indiscriminately. **Memora** is the sole long-term cross-agent memory authority, enforcing strict server-side scoping (`Private`, `Shared`, `Universal`), cryptographic provenance, and prompt-injection separation between untrusted external data and executable directives.
4. **Zero-Trust Network Mesh:** Services communicate over a private, non-routable Docker container bridge (`friday_mesh`). No database (PostgreSQL, Redis, Qdrant) or internal specialist API port is exposed to the public internet. Only the reverse proxy (Traefik) binds to external ports `80` and `443`.
5. **Deterministic Sovereign Hosting:** All workloads run on dedicated, sovereign Oracle Cloud Infrastructure (OCI). No third-party PaaS black boxes (Kubernetes, Vercel, Render) are permitted. All deployments are managed by Dokploy GitOps synchronized with official GitHub repositories.

```mermaid
flowchart TD
    subgraph ExternalAccess["External Ingress Layer (Traefik v3)"]
        User["User / Mobile / ChatGPT Companion"] -->|HTTPS / WSS (Ports 80 / 443)| Ingress["Traefik Reverse Proxy (Let's Encrypt TLS)"]
        Ingress -->|Forward :10000| FRIDAY["FRIDAY Core (Cognitive Orchestrator)"]
        Ingress -->|Forward :8765| MCP["Cloud MCP Gateway (/mcp)"]
        Ingress -->|Forward :3000| Dokploy["Dokploy PaaS Dashboard (dokploy.friday-universe...)"]
    end

    subgraph CoreMesh["Private Service Mesh (friday_mesh: :8000)"]
        FRIDAY -->|Task Envelope| Inference["Inference (Model & Reasoning Gateway)"]
        FRIDAY -->|Task Envelope| Memora["Memora (Central Memory Authority)"]
        FRIDAY -->|Task Envelope| Stratex["Stratex (Quantitative Trading & Risk Desk)"]
        FRIDAY -->|Task Envelope| Forge["Forge (Autonomous Software Synthesizer)"]
        FRIDAY -->|Task Envelope| Cortex["Cortex (Web Operations & Governed CRM)"]
        FRIDAY -->|Task Envelope| Sentinel["Sentinel (Zero-Trust Security & Gatekeeper)"]
        FRIDAY -->|Task Envelope| IntelX["IntelX (Deep Research & Fact Verification)"]
        FRIDAY -->|Task Envelope| Futuris["Futuris (Predictive Forecasting Engine)"]
        FRIDAY -->|Task Envelope| VyralX["VyralX (Autonomous Video Studio & Distribution)"]

        %% Specialist Cross-Interactions
        Forge == Pre-Delivery Audit ==> Sentinel
        Stratex == Risk & Anomaly Audit ==> Sentinel
        VyralX == Publish Policy Audit ==> Sentinel
        Cortex -.->|Extract Facts| IntelX
        VyralX -.->|Topic Research Context| IntelX
        Stratex -.->|Market Trajectory| Futuris
        AllSpecialists["All 9 Specialists"] -.->|Route LLM Inquiries| Inference
        AllSpecialists -.->|Read/Write Scoped Memory| Memora
    end

    subgraph DataMesh["Shared Unified Storage Layer (PostgreSQL 18)"]
        Postgres[("PostgreSQL 18 Cluster\n(10 Distinct Logical Databases)")]
        Redis[("Redis 7\n(Shared Pub/Sub & Caching)")]
        Qdrant[("Qdrant Vector DB\n(Semantic Memory Index)")]
        TursoCloud[("Turso LibSQL Cloud\n(Memora & IntelX AWS Mumbai)")]

        Memora --> Postgres
        Memora --> Redis
        Memora --> Qdrant
        Memora -.-> TursoCloud
        IntelX -.-> TursoCloud
        FRIDAY --> Postgres
        Inference --> Postgres
        Stratex --> Postgres
        Forge --> Postgres
        Cortex --> Postgres
        Sentinel --> Postgres
        IntelX --> Postgres
        Futuris --> Postgres
        VyralX --> Postgres
    end

    subgraph CloudBackup["Cloud Protection Layer"]
        Postgres -.->|Nightly Encrypted Backup (GPG AES-256)| OCIObjectStorage["OCI Private Object Storage (axz0jlcap2j6)"]
    end
```

---

## 2. Infrastructure Topology: Current Interim vs. Target Production State

| Dimension | Current Interim State (Present) | Target Production Architecture (Final Goal) | Operational Invariant |
| :--- | :--- | :--- | :--- |
| **Compute Hardware** | Interim AMD VM (`VM.Standard.E2.1.Micro`), 1 OCPU, 956 MB RAM, 8 GB swapfile. Host: `140.245.208.100`. | Oracle ARM VM (`VM.Standard.A1.Flex`), 2 OCPUs, 12 GB RAM, Ampere Altra. 150–200 GB NVMe Boot Volume. | Ampere Capacity Sniper runs continuously until ARM instance allocation is secured. |
| **Agent Workloads** | All 10 agent microservices scaled to **0/0 running replicas** (standby). Only Core Gateway & Dokploy active. | All 10 agent containers run simultaneously with strict RAM resource caps (~8.5 GB total, preserving OS/DB headroom on the 12 GB instance). | Strict memory preservation: 1 GB AMD host must never exceed 800 MB active RAM to prevent OOM crash. |
| **Storage Architecture** | Disparate local SQLite files + PostgreSQL 18 on `dokploy-postgres` container. | Single unified PostgreSQL 18 cluster with **10 isolated logical databases** and least-privilege service roles. | Zero cross-database SQL queries; inter-agent memory sharing flows exclusively through Memora REST API. |
| **Local Repositories** | 10 independent Git repositories under `D:\FRIDAY Universe`, all clean on `main`. | Same 10 distinct Git repositories synced with GitHub remotes and Dokploy autoDeploy. | Never merge into a monorepo; preserve discrete Git commit histories and PR verification flows. |
| **Service Ports & Mesh** | Public HTTPS 443 via Traefik; internal ports `8001–8010`, FRIDAY Core on `10000`. | Internal standardization: all 9 specialist APIs bind container port `:8000` inside `friday_mesh`. | Port 80 permanently 301-redirects to HTTPS; Dokploy dashboard isolated on sub-domain. |
| **Backup & DR** | Manual snapshots + local SQL dumps in `/root/state_backups`. | Automated, GPG-encrypted (AES-256) nightly dumps to private OCI Object Storage bucket (`axz0jlcap2j6`). | Weekly automated scratch container restores to verify database integrity and row consistency. |

---

## 3. Deep Technical Specification: The Ten Sovereign Subsystems

### 3.1 FRIDAY Core — Cognitive Orchestrator & Action Gateway
- **Repository Path:** `D:\FRIDAY Universe\FRIDAY`
- **GitHub Origin:** `https://github.com/surendra2304/FRIDAY.git`
- **Mesh & Public Port:** Port `10000` (Public Route: `/friday`)
- **Service Entrypoint:** `friday.api.server:app` (Uvicorn ASGI)
- **Database & Models:** `friday_db` (`tasks`, `task_steps`, `approval_requests`, `tool_invocations`, `audit_records`)
- **Framework Stack:** `FastAPI`, `Pydantic v2`, `Uvicorn`, `httpx`, `asyncio`, `WebSockets`, `Windows UI Automation`
- **Primary Mission:** Acts as the primary user-facing orchestrator, voice and multimodal companion, central task planner, action approval authority, and external webhook receiver.
- **Safety Invariants:**
  - Non-Bypassable Specialist Gates: Orchestrates tasks across specialist agents via task envelopes but cannot override specialist security, financial, or verification checks.
  - Decoupled Long-Term Memory: Retains short-lived task checkpoints; all durable long-term memory must be committed to Memora.
  - Desktop Companion Isolation: Native Windows automation (audio, input, screen capture) runs natively on Windows 11; does not mix Windows-specific code into Linux containers.
- **Key API Endpoints:**
  - `POST /api/v1/tasks`: Submit structured task envelope for multi-agent execution
  - `GET /api/v1/tasks/{id}`: Poll task progress, current execution step, and partial results
  - `POST /api/v1/actions/approve`: Approve critical actions requiring human confirmation
  - `WS /ws/audio`: Full-duplex real-time audio and companion interaction stream

---

### 3.2 Inference — Universal Model Routing & Reasoning Gateway
- **Repository Path:** `D:\FRIDAY Universe\Inference`
- **GitHub Origin:** `https://github.com/surendra2304/Inference.git`
- **Mesh & Public Port:** Port `8005` (Container: `:8000`, Public Route: `/inference`)
- **Service Entrypoint:** `inference.main:app` (Uvicorn ASGI)
- **Database & Models:** `inference_db` (`routing_policies`, `provider_quotas`, `token_burn_logs`, `latency_metrics`)
- **Framework Stack:** `FastAPI`, `Groq SDK`, `Mistral SDK`, `OpenAI SDK`, `Google GenAI SDK`, `Redis Token Bucket`
- **Primary Mission:** Centralized, high-throughput LLM, vision, and embedding inference router providing token budgeting, intelligent multi-provider failover, and prompt governance.
- **Safety Invariants:**
  - Canonical Naming: The official system name is **Inference** (never 'AI Universe').
  - Strict Provider Failover Waterfall: Groq (Llama-3.3-70b, ultra-low latency) → Mistral (Codestral/Large) → OpenAI (GPT-4o) → Google Gemini (Gemini-2.0-Flash/Pro).
  - Token Quota Enforcement: Calling specialists are assigned per-minute token buckets managed in Redis to prevent API quota exhaustion or rogue recursive LLM loops.
- **Key API Endpoints:**
  - `POST /v1/chat/completions`: Standard OpenAI-compatible multi-provider routing endpoint
  - `POST /v1/task/execute`: Universal structured task reasoning & script synthesis API
  - `POST /v1/embeddings`: Batch text embedding generation for semantic vectors (1536-dim)
  - `GET /v1/providers/health`: Real-time provider health, token burn rates, and latency metrics

---

### 3.3 Memora — Hierarchical Vector Memory Authority
- **Repository Path:** `D:\FRIDAY Universe\Memora`
- **GitHub Origin:** `https://github.com/surendra2304/Memora.git`
- **Mesh & Public Port:** Port `8007` (Container: `:8000`, Public Route: `/memora`)
- **Service Entrypoint:** `memora.service.api:app` (Uvicorn ASGI)
- **Database & Models:** `memora_db` (`memories`, `memory_namespaces`, `access_grants`, `vector_checkpoints`, `audit_records`)
- **Framework Stack:** `FastAPI`, `SQLAlchemy 2.0 (Async)`, `asyncpg`, `Qdrant Client`, `Redis 7`, `LibSQL/Turso`
- **Primary Mission:** Sole sovereign long-term memory authority for the entire ecosystem, enforcing cryptographic provenance, multi-tier scoping, and prompt injection isolation.
- **Safety Invariants:**
  - 3-Tier Scoping: **Private** (accessible only to originating specialist), **Shared** (explicit ACL grant), **Universal** (all ecosystem agents).
  - Prompt Injection Isolation: Untrusted external facts/crawls are stored with strict data tags and never interpolated directly into executable system directives.
  - Cryptographic Provenance: Every stored memory record carries an HMAC-SHA256 signature calculated with the service master key to prevent database tampering.
- **Key API Endpoints:**
  - `POST /v1/memories`: Ingest scoped memory with namespace, metadata, and cryptographic signature
  - `POST /v1/memories/search`: Hybrid semantic retrieval combining Qdrant dense vectors & relational SQL filters
  - `GET /v1/memories/{id}`: Retrieve verified memory record with signature check
  - `POST /v1/memories/purge`: Governed TTL expiration and privacy-compliant purging

---

### 3.4 Stratex — Quantitative Algorithmic Trading & Risk Desk
- **Repository Path:** `D:\FRIDAY Universe\Stratex`
- **GitHub Origin:** `https://github.com/surendra2304/Stratex.git`
- **Mesh & Public Port:** Port `8009` (Container: `:8000`, Public Route: `/stratex`)
- **Service Entrypoint:** `stratex.main:app` (Uvicorn ASGI)
- **Database & Models:** `stratex_db` (`orders`, `positions`, `risk_rules`, `trade_audits`, `venue_states`, `pnl_snapshots`)
- **Framework Stack:** `FastAPI`, `pandas`, `numpy`, `ccxt`, `Binance Futures SDK`, `Pydantic v2`
- **Primary Mission:** Algorithmic execution desk, continuous market surveillance, risk governance, and quantitative backtesting harness.
- **Safety Invariants:**
  - **ZERO LIVE-MONEY INVARIANT:** Bound strictly to Binance Futures Testnet (`https://testnet.binancefuture.com`); real capital executions are disabled.
  - Hard Immutable Risk Stops: Max position size ($1,000 testnet margin), max leverage (5x), mandatory stop-loss (2%), and portfolio drawdown cap (5%) are hardcoded.
  - Atomic Emergency Halt: `POST /api/v1/emergency-halt` instantly issues cancel-all across testnet venues and transitions order state machine to LOCKED.
- **Key API Endpoints:**
  - `POST /api/v1/orders`: Authenticated order dispatch with pre-trade risk validation
  - `GET /api/v1/positions`: Real-time open positions, mark prices & unrealized PnL
  - `POST /api/v1/emergency-halt`: Master emergency kill-switch (cancel all open orders)
  - `GET /api/v1/risk/status`: Live margin utilization, leverage & drawdown audit

---

### 3.5 Forge — Autonomous Software Synthesizer & Verification Battery
- **Repository Path:** `D:\FRIDAY Universe\Forge`
- **GitHub Origin:** `https://github.com/surendra2304/Forge.git`
- **Mesh & Public Port:** Port `8003` (Container: `:8000`, Public Route: `/forge`)
- **Service Entrypoint:** `forge.api.server:app` (Uvicorn ASGI)
- **Database & Models:** `forge_db` (`build_tasks`, `dag_nodes`, `verification_runs`, `artifact_manifests`, `patch_history`)
- **Framework Stack:** `FastAPI`, `tree-sitter`, `ast`, `pytest`, `Docker SDK`, `httpx`, `Alembic`
- **Primary Mission:** Full-stack autonomous software engineer: specification parsing, multi-file code synthesis, automated test generation, and objective quality verification.
- **Safety Invariants:**
  - **Strict Sandbox Confinement:** All edits restricted to `workspaces/task_{id}`; path traversal attempts raise fatal `SandboxViolationError`.
  - Command Execution Blacklist: Blocks dangerous system commands (`sudo`, `rm -rf /`, raw block redirection) at policy layer.
  - **10-Point Objective Verification:** BuildChecker, LintChecker, TestChecker, SecurityChecker, BrowserChecker must all return exit code 0 before task completion.
- **Key API Endpoints:**
  - `POST /api/v1/synthesize`: Submit software specification for multi-step DAG build
  - `GET /api/v1/tasks/{id}/verify`: Execute 10-point verification battery on workspace
  - `POST /api/v1/patches/apply`: Apply unified diff inside isolated task sandbox
  - `GET /api/v1/artifacts/{id}`: Download verified release bundle and test report

---

### 3.6 Cortex — Multi-Tenant Web Engine & Governed CRM
- **Repository Path:** `D:\FRIDAY Universe\Cortex`
- **GitHub Origin:** `https://github.com/surendra2304/Cortex.git`
- **Mesh & Public Port:** Port `8002` (Container: `:8000`, Public Route: `/cortex`)
- **Service Entrypoint:** `cortex_api.main:app` (Uvicorn ASGI)
- **Database & Models:** `cortex_db` (`tenants`, `sites`, `api_keys`, `visitors`, `leads`, `events`, `webhooks`, `action_audits`)
- **Framework Stack:** `FastAPI`, `Next.js` (Exported SPA in `apps/dashboard/out`), `SQLAlchemy 2.0`, `jose JWT`, `Redis`
- **Primary Mission:** Powers ecosystem web presence, landing pages, interactive operator dashboards, lead capture, CRM telemetry, and governed website optimizations.
- **Safety Invariants:**
  - **Strict Multi-Tenant Scoping:** Every single query across visitors, leads, sessions, and events enforces `tenant_id` at database layer; cross-tenant reads return 404.
  - Zero Dev Auth Bypass: Development auth bypass (`CORTEX_DEV_AUTH_BYPASS`) is strictly disabled in production.
  - Cryptographic JWT Verification: All API keys and admin JWTs are verified against RSA-256 public keys on all routes.
- **Key API Endpoints:**
  - `GET /api/v1/sites`: Enumerate hosted sovereign web properties and domains
  - `POST /api/v1/leads`: Ingest and score public inbound business leads
  - `GET /api/v1/dashboard/metrics`: Real-time visitor analytics, conversion & CRM status
  - `POST /api/v1/webhooks/incoming`: Receive verified external webhook events

---

### 3.7 Sentinel — Zero-Trust Security Operations & Gatekeeper
- **Repository Path:** `D:\FRIDAY Universe\Sentinel`
- **GitHub Origin:** `https://github.com/surendra2304/Sentinel.git`
- **Mesh & Public Port:** Port `8008` (Container: `:8000`, Public Route: `/sentinel`)
- **Service Entrypoint:** `sentinel/main.py` (Uvicorn ASGI)
- **Database & Models:** `sentinel_db` (`assessments`, `scans`, `vulnerabilities`, `policy_rules`, `audit_records`)
- **Framework Stack:** `FastAPI`, `safety`, `pip-audit`, `bandit`, `cryptography`, `OpenSSL`, `Pydantic`
- **Primary Mission:** Ecosystem security officer, continuous vulnerability scanner, dependency auditor, AST policy enforcer, and gatekeeper for all external and cross-service operations.
- **Safety Invariants:**
  - **Pre-Delivery Code Gate:** Inspects artifacts from Forge before merge; vetoes delivery if unauthorized network calls, hardcoded secrets, or high-severity CVEs exist.
  - **Zero-Trust Token Governance:** Periodically scans git hygiene across all 10 repositories to verify no `.env` files, API keys, or private SSH keys are staged.
  - **Fail-Closed Security Posture:** If Sentinel is unreachable or reports an indeterminate scan, downstream deliveries and external publishings are unconditionally halted.
- **Key API Endpoints:**
  - `POST /v1/security/audit`: Perform comprehensive AST and CVE scan on artifact diff
  - `POST /v1/secrets/scan`: Scan text or repository tree for exposed secrets/keys
  - `GET /v1/posture/report`: Ecosystem-wide zero-trust compliance & CVE posture
  - `POST /v1/policy/evaluate`: Evaluate action payload against mandatory security rules

---

### 3.8 IntelX — Deep Web Research & Fact Verification Specialist
- **Repository Path:** `D:\FRIDAY Universe\IntelX`
- **GitHub Origin:** `https://github.com/surendra2304/IntelX.git`
- **Mesh & Public Port:** Port `8006` (Container: `:8000`, Public Route: `/intelx`)
- **Service Entrypoint:** `intelx.cli.main:serve` (Uvicorn ASGI)
- **Database & Models:** `intelx_db` (`sources`, `documents`, `claims`, `evidence_links`, `contradictions`, `research_runs`)
- **Framework Stack:** `FastAPI`, `httpx`, `BeautifulSoup4`, `readability-lxml`, `SQLAlchemy 2.0`, `DuckDuckGo / SearXNG`
- **Primary Mission:** Autonomous web research, multi-source intelligence gathering, claim extraction, evidence linking, contradiction detection, and citation provenance.
- **Safety Invariants:**
  - **Rigorous SSRF Defenses:** Blocks crawler requests to loopback (`127.0.0.1`), private RFC1918 subnets, and cloud metadata endpoints (`169.254.169.254`).
  - **Separation of Evidence from Inference:** Raw source facts are cryptographically cited and never conflated with model-generated syntheses.
  - **Cloud Redundancy:** Research summaries and verified claims are mirrored to Turso LibSQL cloud database in AWS Mumbai (`ap-south-1`).
- **Key API Endpoints:**
  - `POST /v1/research/query`: Initiate multi-source deep intelligence gathering on topic
  - `POST /v1/verify/claim`: Extract claim from statement and corroborate across verified sources
  - `GET /v1/research/runs/{id}`: Poll research brief status, cited URLs & confidence scores
  - `POST /v1/crawl/extract`: Safely fetch, parse and extract clean readable text from URL

---

### 3.9 Futuris — Predictive Trajectory Analysis & Calibration Engine
- **Repository Path:** `D:\FRIDAY Universe\Futuris`
- **GitHub Origin:** `https://github.com/surendra2304/Futuris.git`
- **Mesh & Public Port:** Port `8004` (Container: `:8000`, Public Route: `/futuris`)
- **Service Entrypoint:** `futuris.cli:serve` (Uvicorn ASGI)
- **Database & Models:** `futuris_db` (`forecasts`, `scenarios`, `outcomes`, `calibration_scores`, `model_versions`)
- **Framework Stack:** `FastAPI`, `numpy`, `scipy`, `statsmodels`, `aiosqlite`, `asyncpg`, `Pydantic v2`
- **Primary Mission:** Scenario forecasting, probabilistic modeling, uncertainty estimation, Brier score calibration, and long-term predictive trajectory tracking.
- **Safety Invariants:**
  - **Strict Advisory Invariant:** Forecasts are probabilistic advisory insights only; never trigger financial executions or infrastructure mutations directly.
  - **Worker Resource Bounds:** Expensive mathematical simulations and Monte Carlo projections offloaded to bounded worker pools to prevent CPU starvation.
  - **Brier Score Calibration:** Tracks historical probabilistic calibration against realized real-world outcomes to systematically penalize overconfidence.
- **Key API Endpoints:**
  - `POST /v1/forecast/scenario`: Generate calibrated multi-branch probabilistic forecast
  - `GET /v1/forecast/regime`: Query macroeconomic or market regime probability distributions
  - `POST /v1/calibration/evaluate`: Resolve completed real-world event and score forecast accuracy
  - `GET /v1/metrics/brier`: Retrieve rolling historical Brier calibration reliability metrics

---

### 3.10 VyralX — Autonomous Video Production & Distribution Studio
- **Repository Path:** `D:\FRIDAY Universe\VyralX`
- **GitHub Origin:** `https://github.com/surendra2304/VyralX.git`
- **Mesh & Public Port:** Port `8010` (Container: `:8000`, Public Route: `/vyralx`)
- **Service Entrypoint:** `app.main:app` (API) & `app.worker` (Dedicated Background Worker)
- **Database & Models:** `vyralx_db` (`tasks`, `projects`, `scenes`, `media_assets`, `render_jobs`, `channels`, `upload_checkpoints`, `metrics`)
- **Framework Stack:** `FastAPI`, `moviepy`, `ffmpeg`, `ffprobe`, `google-api-python-client`, `httpx`, `eSpeak NG`
- **Primary Mission:** Autonomous end-to-end video production, AI scriptwriting, audio synthesis, visual assembly, automated captioning, rendering, and multi-channel publication.
- **Safety Invariants:**
  - **Resumable Upload Checkpoints:** Interrupted uploads enter an `uncertain` state and are never blindly repeated, preventing duplicate video publication or API quota depletion.
  - **Source Rights & Verification Gate:** Stock media from Pexels requires verified license confirmation and FFprobe inspection before inclusion; leads remain unverified until imported.
  - **Sentinel Pre-Publish Audit:** Video assets must pass fail-closed Sentinel policy and loudness QA (-14 LUFS standard) before dispatch.
- **Key API Endpoints:**
  - `POST /api/v1/tasks`: Standard FRIDAY task envelope dispatch for video projects
  - `POST /api/v1/projects`: Create video project with scene plan, format (9:16 Shorts), and narration
  - `POST /api/v1/render`: Queue background video composition job with FFmpeg presets
  - `POST /api/v1/publish/youtube`: Resumable chunked upload to YouTube Data API v3 with approval gate

---

## 4. Storage Topology & Database Governance

### 4.1 Unified PostgreSQL 18 Engine Architecture
Rather than running multiple database instances, the FRIDAY Universe consolidates relational data into a single, high-performance PostgreSQL 18 cluster running inside Docker container `dokploy-postgres` on the `dokploy-network`.

```
[PostgreSQL 18 Cluster (dokploy-postgres)]
 ├── friday_db    (Role: friday_user   — Restricted to FRIDAY Core)
 ├── inference_db (Role: inference_user— Restricted to Inference)
 ├── memora_db    (Role: memora_user   — Restricted to Memora)
 ├── stratex_db   (Role: stratex_user  — Restricted to Stratex)
 ├── forge_db     (Role: forge_user    — Restricted to Forge)
 ├── cortex_db    (Role: cortex_user   — Restricted to Cortex)
 ├── sentinel_db  (Role: sentinel_user — Restricted to Sentinel)
 ├── intelx_db    (Role: intelx_user   — Restricted to IntelX)
 ├── futuris_db   (Role: futuris_user  — Restricted to Futuris)
 └── vyralx_db   (Role: vyralx_user   — Restricted to VyralX)
```

### 4.2 Database Security Rules
1. **Least Privilege Enforcement:** Each agent authenticates using its own non-superuser role. No microservice role possesses `GRANT` or `SELECT` privileges on another agent's database.
2. **Memora Rest Law:** Direct cross-database joins and multi-database queries are physically prohibited. The only legal method for cross-agent memory retrieval is through Memora's authorized REST API.
3. **Internal Network Confinement:** PostgreSQL port `5432` and Redis port `6379` are bound exclusively to the private Docker bridge and are never published to public host interfaces.

---

## 5. Networking, Reverse Proxy & Cloud Ingress Architecture

Traefik v3 acts as the edge reverse proxy, terminating TLS/SSL certificates dynamically issued by Let's Encrypt for the `*.friday-universe.duckdns.org` domain, enforcing permanent HTTP-to-HTTPS redirects, and routing incoming traffic based on host and path prefixes.

| Domain / Route | Target Service | Container / Port | SSL / TLS Certificate | Access & Security Policy |
| :--- | :--- | :--- | :--- | :--- |
| `https://friday-universe.duckdns.org/` | Root Ecosystem Portal | Host: 8765 | Let's Encrypt Wildcard | Public JSON status describing 10 sovereign agents. |
| `https://friday-universe.duckdns.org/mcp` | Cloud MCP Gateway | Host: 8765 | Let's Encrypt Wildcard | Strict Bearer token authentication for tool calls. |
| `https://friday-universe.duckdns.org/mcp/health` | MCP Health Endpoint | Host: 8765 | Let's Encrypt Wildcard | Public HTTP 200 health probe for monitoring. |
| `https://dokploy.friday-universe.duckdns.org` | Dokploy PaaS Dashboard | Container: 3000 | Let's Encrypt Wildcard | Isolated admin sub-domain. Web session authentication. |
| `https://friday-universe.duckdns.org/friday` | FRIDAY Core | Container: 10000 | Let's Encrypt Wildcard | Agent standby metadata / API gateway. |
| `https://friday-universe.duckdns.org/cortex` | Cortex Engine | Container: 8002 | Let's Encrypt Wildcard | Agent standby metadata / Web dashboard API. |
| `https://friday-universe.duckdns.org/forge` | Forge Synthesizer | Container: 8003 | Let's Encrypt Wildcard | Agent standby metadata / Synthesizer API. |
| `https://friday-universe.duckdns.org/futuris` | Futuris Engine | Container: 8004 | Let's Encrypt Wildcard | Agent standby metadata / Forecasting API. |
| `https://friday-universe.duckdns.org/inference` | Inference Router | Container: 8005 | Let's Encrypt Wildcard | Agent standby metadata / Reasoning API. |
| `https://friday-universe.duckdns.org/intelx` | IntelX Research | Container: 8006 | Let's Encrypt Wildcard | Agent standby metadata / Research API. |
| `https://friday-universe.duckdns.org/memora` | Memora Vector DB | Container: 8007 | Let's Encrypt Wildcard | Agent standby metadata / Memory API. |
| `https://friday-universe.duckdns.org/sentinel` | Sentinel Gatekeeper | Container: 8008 | Let's Encrypt Wildcard | Agent standby metadata / Security API. |
| `https://friday-universe.duckdns.org/stratex` | Stratex Trading Desk | Container: 8009 | Let's Encrypt Wildcard | Agent standby metadata / Trading API. |
| `https://friday-universe.duckdns.org/vyralx` | VyralX Video Studio | Container: 8010 | Let's Encrypt Wildcard | Agent standby metadata / Video API. |

---

## 6. Unified MCP Gateway & Hybrid Control Architecture

The FRIDAY Universe operates a **Consolidated Cloud & Laptop MCP Gateway** providing 15 high-privilege tools across Oracle Cloud Infrastructure, Dokploy PaaS, and Windows 11 laptop automation.

```
                    ┌────────────────────────────────────────────────────────┐
                    │               ChatGPT / Antigravity Clients            │
                    └───────────────────────────┬────────────────────────────┘
                                                │ (HTTPS JSON-RPC 2.0 + Bearer Token)
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│              Oracle Cloud MCP Gateway (https://friday-universe.duckdns.org/mcp)                 │
├────────────────────────────────┬────────────────────────────────┬───────────────────────────────┤
│    OCI Infrastructure Tools    │      Dokploy PaaS Tools        │   Workstation Proxy Tools     │
│   • oci_check_auth             │     • dokploy_check_health     │    • laptop_system_info       │
│   • oci_list_instances         │     • dokploy_list_apps        │    • laptop_list_workspace   │
│   • oci_get_instance_details   │     • dokploy_get_app_details  │    • laptop_read_file         │
│   • get_cloud_vm_status        │     • dokploy_deploy_app       │    • laptop_git_status        │
│   • ssh_run_diagnostic         │       (confirmation=True guard)│                               │
│   • postgres_read_diagnostic   │                                │                               │
└────────────────────────────────┴────────────────────────────────┴───────────────┬───────────────┘
                                                                                  │ (Reverse Tunnel)
                                                                                  ▼
                                       ┌──────────────────────────────────────────────────────────┐
                                       │    Windows 11 Workstation Bridge (FastMCP via ngrok)     │
                                       │       https://kite-trouble-decency.ngrok-free.dev/mcp    │
                                       ├──────────────────────────────────────────────────────────┤
                                       │ • Drives C: & D: File System Access                      │
                                       │ • Win32 Foreground Window Activation                     │
                                       │ • 10-Repository Git Status & Branch Tracking             │
                                       │ • Process Inspection & Native Automation                 │
                                       └──────────────────────────────────────────────────────────┘
```

---

## 7. Cross-Subsystem Interaction Matrix & Inter-Agent Contracts

| Initiating Subsystem | Receiving Subsystem | Primary Workflow & Protocol | Authentication & Payload Details | Circuit Breaker / Failure Mode |
| :--- | :--- | :--- | :--- | :--- |
| **`FRIDAY Core`** | All 9 Specialists | Task Dispatch & Job Lifecycle (`HTTP POST /api/v1/tasks`) | Bearer Token (`*_API_KEY`), Correlation ID, task JSON envelope. | 30s timeout; retry with exponential backoff; graceful user error report. |
| **Specialists** | **`Inference`** | Model Reasoning & Token Generation (`HTTP POST /v1/chat/completions`) | Bearer Token (`INFERENCE_API_KEY`), model requirements, prompt, token budget. | Failover pool: Groq → Mistral → OpenAI → Gemini. |
| **Specialists** | **`Memora`** | Memory Ingestion & Query (`HTTP POST /v1/memories/search`) | Bearer Token (`MEMORA_API_KEY`), namespace, scope (`Private`/`Shared`/`Universal`). | 3s timeout; log warning; fall back to local transient memory. |
| **`Forge`** | **`Sentinel`** | Pre-Delivery Security Audit (`HTTP POST /v1/security/audit`) | Bearer Token (`SENTINEL_API_KEY`), workspace path, diff, artifact manifest. | **Strict Fail-Closed:** Delivery blocked if Sentinel reports violations. |
| **`FRIDAY Core`** | **`Stratex`** | Order Status & Kill-Switch (`HTTP POST /api/v1/emergency-halt`) | Bearer Token (`STRATEX_API_KEY`), explicit admin secret. | Idempotent cancel-all; immediate atomic ledger state lock. |
| **`Cortex`** | **`IntelX`** | Competitor & Market Fact Check (`HTTP POST /v1/research/query`) | Bearer Token (`INTELX_API_KEY`), topic query, citation limit. | Asynchronous poll; reports confidence level. |
| **`Stratex`** | **`Futuris`** | Market Regime Probabilities (`HTTP GET /v1/forecast/regime`) | Bearer Token (`FUTURIS_API_KEY`), asset pair, timeframe window. | Fall back to neutral technical indicators if unavailable. |
| **`VyralX`** | **`Inference`** | Original Script & Scene Plan (`HTTP POST /v1/task/execute`) | Bearer Token (`INFERENCE_API_KEY`), topic prompt, scene structure. | Graceful fallback; cached draft preservation. |
| **`VyralX`** | **`IntelX`** | Bounded Research Context (`HTTP POST /v1/research/query`) | Bearer Token (`INTELX_API_KEY`), search keywords, citation limit. | Graceful degradation; marked unverified. |
| **`VyralX`** | **`Sentinel`** | Pre-Publish Rights & Policy Audit (`HTTP POST /v1/security/audit`) | Bearer Token (`SENTINEL_API_KEY`), media metadata, license manifest. | **Fail-Closed:** Publishing blocked on violation. |
| **`VyralX`** | **`Memora`** | Long-Term Engagement & Video Provenance (`HTTP POST /v1/memories`) | Bearer Token (`MEMORA_API_KEY`), namespace, channel metrics. | 3s timeout; log warning; fall back to transient store. |

---

## 8. Master Git Workspace & Repository Inventory

| # | Repository Name | Local Filesystem Path | Remote GitHub Origin | Branch | Working Tree State |
| :-: | :--- | :--- | :--- | :-: | :--- |
| **1** | **FRIDAY** | `D:\FRIDAY Universe\FRIDAY` | `https://github.com/surendra2304/FRIDAY` | `main` | Clean (aligned with origin/main) |
| **2** | **Inference** | `D:\FRIDAY Universe\Inference` | `https://github.com/surendra2304/Inference` | `main` | Clean (aligned with origin/main) |
| **3** | **Memora** | `D:\FRIDAY Universe\Memora` | `https://github.com/surendra2304/Memora` | `main` | Clean (aligned with origin/main) |
| **4** | **Stratex** | `D:\FRIDAY Universe\Stratex` | `https://github.com/surendra2304/Stratex` | `main` | Clean (aligned with origin/main) |
| **5** | **Forge** | `D:\FRIDAY Universe\Forge` | `https://github.com/surendra2304/Forge` | `main` | Clean (aligned with origin/main) |
| **6** | **Cortex** | `D:\FRIDAY Universe\Cortex` | `https://github.com/surendra2304/Cortex` | `main` | Clean (aligned with origin/main) |
| **7** | **Sentinel** | `D:\FRIDAY Universe\Sentinel` | `https://github.com/surendra2304/Sentinel` | `main` | Clean (aligned with origin/main) |
| **8** | **IntelX** | `D:\FRIDAY Universe\IntelX` | `https://github.com/surendra2304/IntelX` | `main` | Clean (aligned with origin/main) |
| **9** | **Futuris** | `D:\FRIDAY Universe\Futuris` | `https://github.com/surendra2304/Futuris` | `main` | Clean (aligned with origin/main) |
| **10** | **VyralX** | `D:\FRIDAY Universe\VyralX` | `https://github.com/surendra2304/VyralX` | `main` | Clean (aligned with origin/main) |

---

## 9. Disaster Recovery, Backups & Security Protocols

### 9.1 Automated OCI Object Storage Backup Standard
1. **Encrypted Nightly Streaming Dumps:** PostgreSQL database cluster is exported via `pg_dumpall`, compressed with `gzip`, and encrypted using GPG AES-256 before transit.
2. **Private Bucket Streaming:** Dumps are streamed to private OCI Object Storage bucket `axz0jlcap2j6` in region `ap-mumbai-1`.
3. **Retention & Lifecycle Rules:** 30-day rolling expiration for daily snapshots; 365-day archive for monthly milestones.
4. **Verification Restoration Battery:** Weekly automated restore into an isolated scratch container confirms schema consistency, relational integrity, and row count matches.

### 9.2 Zero-Leak Credential & Secret Management Policy
1. **Zero Hardcoded Secrets:** No API keys, database passwords, or private keys are ever stored in source repositories or committed to Git.
2. **Automated Diagnostic Scrubbing:** Regex sanitizers scrub JWTs, GitHub PATs, private keys, and UUID tokens from all MCP diagnostic outputs and logs.
3. **Immediate Key Rotation Protocol:** Any compromised credential is immediately revoked, rotated, and synchronized across Dokploy and the gateway without restarting live containers.

---

## 10. Implementation Roadmap & Ecosystem Milestones

- [x] **Phase 0: Workspace & Git Integrity Audit** — All 10 local repositories verified, lint-cleared, and synchronized on `main` with 0 uncommitted changes.
- [x] **Phase 1: Dokploy GitOps & Sovereign Routing** — All 10 apps registered in Dokploy; Traefik v3 routing established; all 10 public agent routes return HTTP 200 OK.
- [x] **Phase 2: Unified MCP Gateway & Workstation Bridge** — Single consolidated MCP endpoint at `https://friday-universe.duckdns.org/mcp` with strict dual-layer bearer auth and write confirmation guards.
- [x] **Phase 3: PostgreSQL 18 Schema Migration** — Successfully provisioned all 10 isolated logical databases with dedicated service roles, public connect revocation, and Dokploy DATABASE_URL synchronization.
- [ ] **Phase 4: Oracle Cloud ARM64 Production Cutover** — Claim 2-OCPU, 12 GB RAM A1 Flex instance via capacity sniper; scale all 10 microservices to 1/1 replicas.

---
*Authored and certified by Antigravity Project Coordinator for the FRIDAY Universe.*
