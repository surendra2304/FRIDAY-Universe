# FRIDAY Universe — Dependency Map

**Version:** 1.0.0  
**Audit Date:** 2026-10-17  
**Auditor:** Antigravity Project Coordinator  

---

## 1. Ecosystem Topology

```mermaid
flowchart TD
    subgraph Ingress["External Ingress Layer"]
        User["User / Mobile / Companion / Voice Client"] -->|HTTPS / WSS| Traefik["Traefik / Caddy Reverse Proxy (Ports 80 / 443)"]
        Traefik -->|Internal HTTP| FRIDAY["FRIDAY Orchestrator (Port 10000)"]
    end

    subgraph ServiceMesh["Private Docker Mesh (friday_mesh)"]
        direction TB
        FRIDAY -->|Task Dispatch| Inference["Inference (Port 8000)"]
        FRIDAY -->|Task Dispatch| Memora["Memora (Port 8000)"]
        FRIDAY -->|Task Dispatch| Stratex["Stratex (Port 8000)"]
        FRIDAY -->|Task Dispatch| Forge["Forge (Port 8000)"]
        FRIDAY -->|Task Dispatch| Cortex["Cortex (Port 8000)"]
        FRIDAY -->|Task Dispatch| Sentinel["Sentinel (Port 8000)"]
        FRIDAY -->|Task Dispatch| IntelX["IntelX (Port 8000)"]
        FRIDAY -->|Task Dispatch| Futuris["Futuris (Port 8000)"]

        %% Specialist to Memora cross-calls
        Inference -.->|Store Lesson| Memora
        Stratex -.->|Risk Context| Memora
        Forge -.->|Code Pattern| Memora
        Cortex -.->|Visitor Trends| Memora
        Sentinel -.->|Threat Signatures| Memora
        IntelX -.->|Verified Facts| Memora
        Futuris -.->|Forecast Accuracy| Memora

        %% Specialist to Inference cross-calls
        Cortex -.->|Lead Synthesis| Inference
        Forge -.->|Code Generation| Inference
        IntelX -.->|Contradiction Analysis| Inference
        Futuris -.->|Scenario Expansion| Inference
        Sentinel -.->|Vulnerability Explanations| Inference

        %% Sentinel Security Gate
        Sentinel == Security Policy Audit ==> Forge
        Sentinel == Security Policy Audit ==> Stratex
    end

    subgraph Infrastructure["Shared Data & Storage Mesh"]
        Memora --> Postgres[("PostgreSQL 18 Cluster\n(Logical DBs: memora_db, friday_db, etc.)")]
        FRIDAY --> Postgres
        Inference --> Postgres
        Stratex --> Postgres
        Forge --> Postgres
        Cortex --> Postgres
        Sentinel --> Postgres
        IntelX --> Postgres
        Futuris --> Postgres

        Memora --> Redis[("Redis 7 (Cache & Event Stream)")]
        Memora --> Qdrant[("Qdrant (Vector Embeddings)")]
    end

    subgraph ExternalProviders["External Cloud & API Services"]
        Inference --> AIProviders["AI Model APIs (Groq, Mistral, OpenAI, Anthropic, Gemini)"]
        Stratex --> Binance["Binance Futures API"]
        IntelX --> WebSearch["Public Web & Search APIs"]
        Postgres -.->|Nightly Encrypted Dumps| OCIBackup["OCI Object Storage (Private Bucket: axz0jlcap2j6)"]
    end
```

---

## 2. Cross-Service Interaction Matrix

| Calling Service | Target Service | Interaction Type | Protocol | Auth Mechanism | Payload Description | Failover / Circuit Breaker Policy |
|-----------------|----------------|------------------|----------|----------------|---------------------|-----------------------------------|
| **FRIDAY** | All Specialists | Task Dispatch | HTTP REST | Bearer Token / API Key | Structured task envelope with correlation ID | Timeout 30s; retry with backoff; fallback gracefully |
| **Specialists** | **Memora** | Memory Ingest / Query | HTTP REST | Bearer Token (`MEMORA_API_KEY`) | Memory record (Private, Shared, Universal scopes) | 3s timeout; log warning; do not block primary workflow |
| **Specialists** | **Inference** | LLM Prompt / Completion | HTTP REST | Bearer Token (`INFERENCE_API_KEY`) | Model routing request with latency/cost budget | Failover to alternate model (e.g. Groq -> Mistral -> OpenAI) |
| **Forge** | **Sentinel** | Security Gate | HTTP REST | Bearer Token (`SENTINEL_API_KEY`) | AST policy check, shell safety inspection | Strict block: if Sentinel rejects, code is quarantined |
| **FRIDAY** | **Stratex** | Trade Signal / Query | HTTP REST | Bearer Token (`STRATEX_API_KEY`) | Position check, risk parameters, manual kill-switch | Independent hard risk limits outside LLM discretion |

---

## 3. Database & Storage Dependency Model

```mermaid
erDiagram
    POSTGRESQL-SERVER ||--o{ MEMORA-DB : hosts
    POSTGRESQL-SERVER ||--o{ FRIDAY-DB : hosts
    POSTGRESQL-SERVER ||--o{ INFERENCE-DB : hosts
    POSTGRESQL-SERVER ||--o{ STRATEX-DB : hosts
    POSTGRESQL-SERVER ||--o{ FORGE-DB : hosts
    POSTGRESQL-SERVER ||--o{ CORTEX-DB : hosts
    POSTGRESQL-SERVER ||--o{ SENTINEL-DB : hosts
    POSTGRESQL-SERVER ||--o{ INTELX-DB : hosts
    POSTGRESQL-SERVER ||--o{ FUTURIS-DB : hosts

    MEMORA-DB {
        uuid id PK
        string agent_id
        string namespace
        string scope "Private, Shared, Universal"
        string content
        jsonb metadata
        timestamp created_at
        timestamp expires_at
    }

    FRIDAY-DB {
        uuid task_id PK
        string workflow_type
        jsonb approval_status
        jsonb tool_trace
        timestamp timestamp
    }

    STRATEX-DB {
        uuid order_id PK
        string client_order_id UK
        string symbol
        numeric quantity
        string status
        jsonb risk_evaluation
    }
```

### Shared Storage Rules
1. **Zero Cross-Database Queries:** No service user or agent connection string may access another service's database.
2. **Dedicated Least-Privilege Roles:** Each logical database has its own user (e.g., `memora_user` for `memora_db`, `friday_user` for `friday_db`).
3. **Connection Pooling Budget:** Each service pool is capped at `5 - 10` connections to prevent exhaustion on the target 12 GB ARM instance (and especially the 1 GB AMD interim host).
4. **Memora as Sole Gateway:** All cross-agent knowledge sharing must occur via Memora's authorized REST API.

---

## 4. Hardware & Resource Budget Allocation

### Target: Oracle Ampere A1 (2 OCPUs, 12 GB RAM)

| Subsystem / Service | Reserved RAM | Max Memory Limit | CPU Reservation | Max CPU Limit | Concurrency Rules |
|---------------------|--------------|------------------|-----------------|---------------|-------------------|
| **OS & Docker Daemon** | 1024 MB | 1536 MB | 0.20 OCPU | 0.50 OCPU | System Priority |
| **PostgreSQL 18** | 1024 MB | 2048 MB | 0.25 OCPU | 1.00 OCPU | Shared DB Server |
| **Redis 7** | 256 MB | 512 MB | 0.05 OCPU | 0.25 OCPU | In-memory cache |
| **Qdrant Vector DB** | 512 MB | 1024 MB | 0.10 OCPU | 0.50 OCPU | Vector embeddings |
| **FRIDAY Core** | 512 MB | 1024 MB | 0.20 OCPU | 0.75 OCPU | Master Orchestrator |
| **Inference Router** | 384 MB | 768 MB | 0.15 OCPU | 0.50 OCPU | Async Gateway |
| **Memora API** | 512 MB | 1024 MB | 0.15 OCPU | 0.50 OCPU | Memory API |
| **Stratex Engine** | 384 MB | 768 MB | 0.10 OCPU | 0.50 OCPU | 24/7 Algorithmic loop |
| **Forge Worker** | 512 MB | 1536 MB | 0.20 OCPU | 1.00 OCPU | **Serialized Heavy Task** |
| **Cortex Engine** | 384 MB | 768 MB | 0.10 OCPU | 0.50 OCPU | Async WebOps |
| **Sentinel Guard** | 384 MB | 768 MB | 0.10 OCPU | 0.75 OCPU | **Serialized Heavy Task** |
| **IntelX Crawler** | 384 MB | 768 MB | 0.10 OCPU | 0.50 OCPU | Bounded I/O |
| **Futuris Engine** | 384 MB | 1024 MB | 0.15 OCPU | 1.00 OCPU | **Serialized Heavy Task** |
| **TOTALS** | **~6.7 GB** | **~12.5 GB** | **~1.85 OCPU** | **Burst Allowed** | Max 1 heavy task active |

> [!IMPORTANT]
> **Heavy Task Serialization Rule:** Forge builds/tests, Futuris ARIMA/Monte Carlo model fits, and Sentinel full-codebase vulnerability scans MUST NOT run concurrently. Antigravity will enforce a distributed lock / queue check across these 3 subsystems.
