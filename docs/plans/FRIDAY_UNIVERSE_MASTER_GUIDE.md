# 🌌 FRIDAY UNIVERSE — The Complete Master Architectural & Technical Guide

> **Ecosystem Version:** 2.2.0  
> **Host Root:** `D:\FRIDAY Universe`  
> **Cloud Ingress:** `https://friday-universe.duckdns.org`  
> **Internal Container Mesh:** `friday_mesh` (Docker internal bridge network)  
> **Hosting Platform:** Oracle Cloud Infrastructure (OCI) Always Free (Ampere A1 ARM64 / AMD x86_64) + Caddy TLS Reverse Proxy

---

## 🏛️ 1. Executive Summary & Philosophy

The **FRIDAY Universe** is an autonomous, decentralized, multi-agent AI operating system. Rather than relying on a single monolithic language model, the Universe decomposes human intent into specialized, domain-specific autonomous agents. Each agent acts as a fully self-contained microservice with its own dedicated Git repository, isolated environment configuration (`.env`), database, domain tools, and execution sandbox.

All 9 agents communicate over a private, authenticated container network (**`friday_mesh`**) orchestrated via Docker Compose and safeguarded by cryptographic gatekeeping (**Sentinel**). Long-term knowledge, conversations, and trade logs are unified by a centralized episodic memory fabric (**Memora**).

```mermaid
flowchart TD
    User["👤 User (Voice / Web / CLI)"] --> FRIDAY["🤖 FRIDAY (Port 10000)<br>Master Orchestrator & Desktop OS"]

    subgraph Mesh ["🌐 friday_mesh Container Network (Internal DNS)"]
        FRIDAY <--> Inference["⚡ Inference (Port 8000)<br>Multi-Model LLM Gateway"]
        FRIDAY <--> Sentinel["🛡️ Sentinel (Port 8000)<br>Crypto Gatekeeper & Security"]
        FRIDAY <--> Cortex["🌐 Cortex (Port 8000)<br>Web Ops & Lead Intelligence"]
        
        Inference <--> IntelX["🔍 IntelX (Port 8000)<br>OSINT Research & Scraping"]
        Inference <--> Futuris["🔮 Futuris (Port 8000)<br>Probabilistic Forecasting"]
        Inference <--> Forge["🛠️ Forge (Port 8000)<br>Software Synthesis & Test"]

        Futuris --> Stratex["📈 Stratex (Port 8000)<br>Paper Trading & Futures"]
        IntelX --> Stratex

        Sentinel -.->|"HMAC / ECDSA Verification"| Mesh
        
        Memora[("🧠 Memora (Port 8000)<br>Unified Memory & Knowledge Graph")]
        Inference <--> Memora
        IntelX <--> Memora
        Futuris <--> Memora
        Stratex <--> Memora
        Cortex <--> Memora
        Forge <--> Memora
        Sentinel <--> Memora
        FRIDAY <--> Memora
    end

    Caddy["🛡️ Caddy Reverse Proxy (Auto TLS)"] --> FRIDAY
    Caddy --> Cortex
    Caddy --> Stratex
    Caddy --> IntelX
    Caddy --> Futuris
    Caddy --> Sentinel
    Caddy --> Memora
    Caddy --> Inference
```

---

## 🤖 2. Deep Dive: The 9 Autonomous Agents

Below is the complete profile for each agent in the FRIDAY Universe, including what it does, what tools and technologies it runs, its file locations, ports, and external APIs.

---

### 1. ⚡ Inference — Central Multi-Model Intelligence Gateway
- **Workspace Path:** [`D:\FRIDAY Universe\Inference`](file:///D:/FRIDAY%20Universe/Inference)
- **Repository:** `surendra2304/Inference`
- **Internal Mesh URL:** `http://inference:8000` | **Host Port:** `8000`
- **Public Route:** `https://friday-universe.duckdns.org/inference`
- **Role:** Central LLM deliberation, model arbitration, and adaptive prompt routing gateway.
- **Key Capabilities:**
  - Multi-provider pooling and automatic failover across **Google Gemini (1.5/2.0), Anthropic Claude, OpenAI GPT-4o, Groq (Llama-3.3-70B, Mixtral), OpenRouter, and DeepSeek**.
  - Dynamic token optimization, prompt compression, and semantic caching.
  - Specialized reasoning engines: Architecture Planning, Crisis Detection, Code Generation, Code Review, Quality Assurance, and Trading Advisory consultations.
  - Prompt injection isolation and token leak shields.
- **Key Files & Tools:**
  - `app/main.py`: FastAPI server entrypoint.
  - `app/services/`: Specialized intelligence modules (`conservative_engine.py`, `crisis_detector.py`, `code_generation.py`, `trading_consult_service.py`).
  - `app/providers/`: Direct API drivers for Gemini, Groq, Anthropic, and OpenAI.
  - `app/security/`: `prompt_isolation.py` and `api_security.py`.
  - `app/ui/dashboard.py` & `dashboard.html`: Live model performance and latency dashboard.

---

### 2. 🧠 Memora — Unified Long-Term Memory Fabric
- **Workspace Path:** [`D:\FRIDAY Universe\Memora`](file:///D:/FRIDAY%20Universe/Memora)
- **Repository:** `surendra2304/Memora`
- **Internal Mesh URL:** `http://memora:8000` | **Host Port:** `8006`
- **Public Route:** `https://friday-universe.duckdns.org/memora`
- **Role:** Central persistent episodic memory, knowledge graph, and vector recall vault.
- **Key Capabilities:**
  - URI-partitioned memory namespaces: `memora://<agent>/private` (e.g. `memora://stratex/private`, `memora://cortex/private`).
  - Strict Role-Based Access Control (RBAC): Agents can only write and read their own partition, preventing cross-agent data contamination while enabling shared global knowledge.
  - Vector similarity search for semantic context retrieval.
  - Knowledge graph entity linking and episodic memory recall.
- **Key Files & Tools:**
  - Engine: SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`) + SQLAlchemy + Alembic migrations.
  - `app/main.py`: REST and WebSocket memory query endpoints (`/remember`, `/recall`, `/search`, `/graph`).
  - `app/storage/`: Vector index, relational tables, and SQLite database connections.

---

### 3. 📈 Stratex — Algorithmic Futures Strategy Engine
- **Workspace Path:** [`D:\FRIDAY Universe\Stratex`](file:///D:/FRIDAY%20Universe/Stratex)
- **Repository:** `surendra2304/algorithmic-trading-bot`
- **Internal Mesh URL:** `http://stratex:8000` | **Host Port:** `8008`
- **Public Route:** `https://friday-universe.duckdns.org/stratex`
- **Role:** 24/7 autonomous cryptocurrency futures strategy execution and paper-trading lab.
- **Key Capabilities:**
  - Multi-timeframe strategy execution on Binance Futures (Testnet / Paper mode).
  - Hard safety constraints: **Live-money orders are strictly blocked in source code** to prevent accidental financial losses.
  - Real-time technical indicator calculations (RSI, Bollinger Bands, EMA, ADX, SuperTrend, VWAP, Donchian Channels).
  - Continuous risk evaluation, portfolio balance tracking, and automated trading pauses when market turbulence spikes.
- **Key Files & Tools:**
  - 15+ Strategy implementations:
    - `strategy_adx_ema_mtf.py`: Multi-timeframe trend follower.
    - `strategy_supertrend.py`: SuperTrend breakout with ATR trail.
    - `strategy_bb_reversion.py`: Bollinger mean-reversion.
    - `strategy_scalper.py` & `strategy_aggressive_scalper.py`: High-frequency momentum scalping.
    - `strategy_ml.py`: Machine-learning probability classifier.
  - `stratex_paper_lab.py`: Real-time backtesting and paper execution harness.
  - `data/trades.db`: Local SQLite trade execution ledger and audit log.

---

### 4. 🔍 IntelX — Live Intelligence Gathering & OSINT Engine
- **Workspace Path:** [`D:\FRIDAY Universe\IntelX`](file:///D:/FRIDAY%20Universe/IntelX)
- **Repository:** `surendra2304/IntelX`
- **Internal Mesh URL:** `http://intelx:8000` | **Host Port:** `8005`
- **Public Route:** `https://friday-universe.duckdns.org/intelx`
- **Role:** Autonomous web research, OSINT scraping, fact extraction, and verified knowledge delivery.
- **Key Capabilities:**
  - Automated multi-source document scraping (Playwright, BeautifulSoup4, HTTP clients).
  - Verbatim proposition extraction: Extracts exact factual claim spans with source URLs.
  - Mathematical confidence scoring: Computes credibility scores for every fact extracted.
  - Contradiction resolution: Cross-references multiple news/data sources to flag false or conflicting data.
  - Executive intelligence synthesis delivered directly to FRIDAY and Memora.
- **Key Files & Tools:**
  - `app/scraper/`: Headless browser workers and HTML parsers.
  - `app/engine/`: Proposition extractor, fact verification, and citation graph builder.
  - `data/intelx.db`: Local SQLite store for research archives and source telemetry.

---

### 5. 🔮 Futuris — Calibrated Predictive Forecasting Engine
- **Workspace Path:** [`D:\FRIDAY Universe\Futuris`](file:///D:/FRIDAY%20Universe/Futuris)
- **Repository:** `surendra2304/Futuris`
- **Internal Mesh URL:** `http://futuris:8000` | **Host Port:** `8003`
- **Public Route:** `https://friday-universe.duckdns.org/futuris`
- **Role:** Statistical forecasting, market regime transitions, and calibrated probability modeling.
- **Key Capabilities:**
  - Probabilistic time-series modeling using ARIMA, StatsForecast, and Monte Carlo distribution curves.
  - Brier Score Calibration: Rigorous statistical testing of predictions against real outcomes to eliminate model overconfidence.
  - Market Regime Modeling: Detects whether financial/system states are in Trending, Mean-Reverting, High-Volatility, or Crisis regimes.
  - Delivers predictive risk distributions to **Stratex** (to reduce order sizes during turbulent regimes) and **FRIDAY**.
- **Key Files & Tools:**
  - `app/models/`: Time-series math, ARIMA, Monte Carlo simulations.
  - `app/calibration/`: Brier calibration curve generators and distribution estimators.
  - `data/futuris.db`: SQLite database storing historical calibration datasets.

---

### 6. 🌐 Cortex — Autonomous Web Operations & Lead Intelligence
- **Workspace Path:** [`D:\FRIDAY Universe\Cortex`](file:///D:/FRIDAY%20Universe/Cortex)
- **Repository:** `surendra2304/Cortex`
- **Internal Mesh URL:** `http://cortex:8000` | **Host Port:** `8001`
- **Public Route:** `https://friday-universe.duckdns.org/cortex`
- **Role:** Autonomous web operations, visitor analytics, conversion funnels, and enterprise dashboard.
- **Key Capabilities:**
  - Full-stack web application: Next.js frontend with Tailwind CSS and FastAPI backend.
  - Visitor telemetry tracking, traffic analysis, and autonomous lead qualification.
  - Real-time connector integrations, incident tracking, and workflow automation.
  - Redis cache and PostgreSQL integration for high-concurrency web events.
- **Key Files & Tools:**
  - `apps/dashboard/`: Next.js 14 web dashboard (leads, funnels, incidents, settings, agents).
  - `apps/api/`: FastAPI backend handling authentication, telemetry ingestion, and analytics.
  - Connected storage: PostgreSQL (`cortex_db`), Redis (`redis:6379`), and local SQLite fallback.

---

### 7. 🛠️ Forge — Autonomous Software Engineering Engine
- **Workspace Path:** [`D:\FRIDAY Universe\Forge`](file:///D:/FRIDAY%20Universe/Forge)
- **Repository:** `surendra2304/Forge`
- **Internal Mesh URL:** `http://forge:8000` | **Host Port:** `8004`
- **Public Route:** `https://friday-universe.duckdns.org/forge`
- **Role:** Autonomous code synthesis, execution sandbox, test generation, and self-repair cycles.
- **Key Capabilities:**
  - Full codebase synthesis: Writes Python, TypeScript, SQL, Dockerfiles, and shell scripts from architectural briefs.
  - Subprocess Sandbox: Executes code inside isolated execution boundaries to prevent host environment pollution.
  - Automated Refactoring & AST Analysis: Uses AST parsers, Ruff, and Flake8 to ensure PEP-8 compliance and type safety.
  - Self-Repair Loops: Catches runtime stack traces, analyzes exceptions, generates targeted diffs, and reruns tests until 100% green.
- **Key Files & Tools:**
  - `forge/generator/`: Code synthesis and prompt decomposition engines.
  - `forge/sandbox/`: Safe execution environment with resource and execution timeouts.
  - `forge/tester/`: Automated Pytest runner and coverage analyzers.

---

### 8. 🛡️ Sentinel — Cybersecurity Watchdog & Cryptographic Gatekeeper
- **Workspace Path:** [`D:\FRIDAY Universe\Sentinel`](file:///D:/FRIDAY%20Universe/Sentinel)
- **Repository:** `surendra2304/Sentinel`
- **Internal Mesh URL:** `http://sentinel:8000` | **Host Port:** `8007`
- **Public Route:** `https://friday-universe.duckdns.org/sentinel`
- **Role:** Autonomous threat defense, vulnerability scanning, and cryptographic signing gatekeeper.
- **Key Capabilities:**
  - **Cryptographic Gatekeeping:** Signs inter-agent payloads using HMAC-SHA256 and ECDSA (`/sign` and `/verify`). No agent can execute privileged commands without a valid Sentinel signature.
  - **Tamper-Evident Ledger:** Implements an append-only, SHA-256 HMAC-signed audit ledger (`/audit`). Any modification to past logs breaks the hash chain immediately.
  - **Attack Surface Analysis:** Automated CVE vulnerability scanner, dependency auditing, and malicious prompt injection mitigation.
  - **Kill-Switch:** Instant emergency circuit breaker to pause individual agents or freeze ecosystem communications if an anomaly is detected.
- **Key Files & Tools:**
  - `app/crypto/`: ECDSA and HMAC signing engines (`audit_ledger.py`, `signer.py`).
  - `app/scanner/`: Dependency and vulnerability scanning engines.
  - `app/gatekeeper/`: Policy enforcement, capability token verification, and kill-switch endpoints.

---

### 9. 🤖 FRIDAY — Central Voice Assistant & Desktop Controller
- **Workspace Path:** [`D:\FRIDAY Universe\FRIDAY`](file:///D:/FRIDAY%20Universe/FRIDAY)
- **Repository:** `surendra2304/FRIDAY`
- **Internal Mesh URL:** `http://friday:10000` | **Host Port:** `10000`
- **Public Route:** `https://friday-universe.duckdns.org`
- **Role:** Multimodal voice assistant, user interaction interface, and master ecosystem conductor.
- **Key Capabilities:**
  - Speech-to-Text (STT) and Text-to-Speech (TTS) multimodal audio pipelines.
  - Desktop orchestration: Application launching, system diagnostics, audio control, and browser automation.
  - Cognitive Routing: Parses high-level natural language requests, determines which specialist agents are needed, dispatches asynchronous tasks across `friday_mesh`, and aggregates the final answer for the user.
- **Key Files & Tools:**
  - `friday/core/`: Speech and cognitive loop orchestrators.
  - `friday/routing/`: Intent routing and capability dispatchers.
  - `friday/tools/`: Local desktop automation tools and system controllers.

---

## 🌐 3. The Inter-Agent Communication Mesh (`friday_mesh`)

All 9 agents communicate using standard HTTP/REST and WebSockets over the private Docker bridge network **`friday_mesh`**.

### Internal Network Addressing
Within the container mesh on Oracle Cloud, each agent is reached by its container name on port `8000` (or `10000` for FRIDAY):

```
Inference -> http://inference:8000
Memora    -> http://memora:8000
Stratex   -> http://stratex:8000
IntelX    -> http://intelx:8000
Futuris   -> http://futuris:8000
Cortex    -> http://cortex:8000
Forge     -> http://forge:8000
Sentinel  -> http://sentinel:8000
FRIDAY    -> http://friday:10000
```

### Shared Mesh Libraries ([`D:\FRIDAY Universe\mesh`](file:///D:/FRIDAY%20Universe/mesh))
To ensure standardized communication across all 9 agents, the root repository contains a shared Python networking package:
- **`mesh/registry.py`**: Central registry of all service URLs, endpoints, health routes, and timeout configs.
- **`mesh/transport.py`**: Resilient HTTP transport client featuring exponential backoff, circuit breaking, and automatic bearer token injection.
- **`mesh/memory_fabric.py`**: High-level SDK allowing any agent to query or store memories in Memora with a single function call.
- **`mesh/daemon.py` & `mesh/keepalive_loop.py`**: Background heartbeats ensuring all 9 containers remain responsive and connected.

---

## 🔒 4. Environment Variables & Secret Isolation

In production, each agent runs in its own sandbox with its own isolated `.env` file located inside its directory:

```
D:\FRIDAY Universe\
├── Cortex\.env
├── Forge\.env
├── FRIDAY\.env
├── Futuris\.env
├── Inference\.env
├── IntelX\.env
├── Memora\.env
├── Sentinel\.env
└── Stratex\.env
```

Each service receives:
1. Its own service API key (e.g., `STRATEX_API_KEY`, `MEMORA_API_KEY`).
2. Downstream service URLs and credentials for agents it needs to consult.
3. Cryptographic signing keys (for Sentinel).
4. No agent has access to another agent's private database credentials.

---

## 📁 5. Directory Structure & Layout of `D:\FRIDAY Universe`

Here is how the complete filesystem on `D:\FRIDAY Universe` is organized:

```
D:\FRIDAY Universe\
├── Cortex/                   # Subsystem 1: Web Ops, Dashboard & Lead Gen
├── Forge/                    # Subsystem 2: Autonomous Software Engineering
├── FRIDAY/                   # Subsystem 3: Central Multimodal Voice OS & Conductor
├── Futuris/                  # Subsystem 4: Calibrated Probabilistic Forecasting
├── Inference/                # Subsystem 5: Multi-Model LLM Deliberation Gateway
├── IntelX/                   # Subsystem 6: Live OSINT & Verified Research Engine
├── Memora/                   # Subsystem 7: Unified Memory Fabric & Vector Vault
├── Sentinel/                 # Subsystem 8: Cybersecurity Shield & Crypto Gatekeeper
├── Stratex/                  # Subsystem 9: Algorithmic Futures Strategy Engine
│
├── mesh/                     # Shared Inter-Agent Communication Package
│   ├── registry.py           # Service endpoint & health route registry
│   ├── transport.py          # Resilient HTTP client with retry logic
│   ├── memory_fabric.py      # Memora memory connector SDK
│   ├── daemon.py             # Mesh health monitoring daemon
│   └── keepalive_loop.py     # Background peer heartbeat loop
│
├── memory/                   # Shared local memory state and test databases
├── deploy/                   # Production Deployment Configurations
│   ├── docker-compose.oracle.yml  # Master OCI 9-agent compose manifest
│   └── caddy/                # Caddyfile reverse proxy & TLS config
│
├── docs/                     # Architectural Documentation
│   ├── plans/                # Master ecosystem blueprints & roadmaps
│   └── notes/                # Technical memos, prompts, and audit notes
│
├── reports/                  # Generated audit reports and evaluation metrics
├── scripts/                  # Operational Scripts & Utilities
│   ├── audits/               # Environment & mesh validation scripts
│   └── keys/                 # Key validation and rotation utilities
│
├── tests/                    # Ecosystem Verification & Cross-Agent Tests
│   ├── goal_ecosystem_verification.py   # Full 9-agent acceptance suite
│   ├── test_cross_agent_contracts.py    # Payload & schema contract tests
│   └── test_mesh_transport_truthfulness.py
│
├── backups/                  # Original configuration backups (master.env.bak, etc.)
└── bin/                      # Command-line tools and shims
```

---

## 🚀 6. Typical Operational Flow: End-to-End Walkthrough

To see how the Universe operates as a unified cognitive system, consider this scenario:

> **User Prompt:** *"FRIDAY, research the current market conditions for Ethereum, forecast the regime for the next 24 hours, and run a safe simulation."*

1. **Ingress (FRIDAY):**
   - The user speaks or types to **FRIDAY** (Port 10000).
   - FRIDAY parses the request and determines that market research, forecasting, and strategy simulation are required.
2. **Intelligence Gathering (IntelX):**
   - FRIDAY calls **IntelX** (`http://intelx:8000/research`).
   - IntelX scrapes real-time sentiment, market news, and on-chain metrics, extracting verified factual propositions with citation links.
3. **Reasoning & Deliberation (Inference):**
   - IntelX passes findings to **Inference** (`http://inference:8000/deliberate`).
   - Inference runs the data through the Multi-Model gateway (e.g. Gemini/Claude) to summarize the macro narrative.
4. **Predictive Calibration (Futuris):**
   - FRIDAY dispatches the telemetry to **Futuris** (`http://futuris:8000/forecast`).
   - Futuris fits ARIMA/Monte Carlo distributions and determines the regime (e.g., "High-Volatility Mean-Reverting" with 84% Brier confidence).
5. **Security Gatekeeping (Sentinel):**
   - Before any simulation order can be initiated, the request payload is sent to **Sentinel** (`http://sentinel:8000/sign`).
   - Sentinel verifies that live trading is disabled, parameters are within risk bounds, signs the payload with HMAC-SHA256, and logs it to the immutable audit ledger.
6. **Execution (Stratex):**
   - The signed payload reaches **Stratex** (`http://stratex:8000/execute`).
   - Stratex selects the optimal strategy (e.g. `strategy_bb_reversion.py`) and executes testnet paper orders on Binance Futures.
7. **Memory Consolidation (Memora):**
   - The outcomes, decisions, and trade IDs are stored in **Memora** under `memora://stratex/private` and `memora://friday/private` for future recall.
8. **Feedback to User (FRIDAY):**
   - FRIDAY synthesizes the aggregated results into a clear response and presents it to the user.
