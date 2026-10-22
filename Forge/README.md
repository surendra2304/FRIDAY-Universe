# 🛠️ FORGE: Autonomous Software Engineering Engine

[![CI/CD Pipeline](https://github.com/surendra2304/Forge/actions/workflows/ci.yml/badge.svg)](https://github.com/surendra2304/Forge/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](Dockerfile)
[![Mesh: friday__mesh](https://img.shields.io/badge/network-friday__mesh-orange.svg)](#network--infrastructure-topology)

**Forge** is the autonomous code synthesis, execution sandbox, linting, and automated self-repair engine of the **FRIDAY Universe**. Operating both as an independent CLI tool and as a networked specialist microservice, Forge ingests natural language requirements, synthesizes complete multi-file software projects, executes them in isolated process sandboxes, verifies them against a 10-check quality battery, and autonomously repairs defects using AST transformations and LLM-guided patches.

---

## 🏛️ Network & Infrastructure Topology

Forge is deployed as a hardened container on **Oracle Cloud Always Free** under the unified private container mesh (`friday_mesh`), reverse-proxied with automated TLS via Caddy.

| Parameter | Configuration |
| :--- | :--- |
| **Service Identity** | `forge` (Specialist Software Engineering Agent) |
| **Public Gateway URL** | `https://friday-universe.duckdns.org/forge/*` |
| **Private Mesh URL** | `http://forge:8000` |
| **Internal Container Port** | `8000` |
| **Host Port Mapping** | `8002:8000` |
| **Container Network** | `friday_mesh` (External Docker Bridge Network) |
| **Gateway Routing** | FRIDAY Core at `http://friday:10000` |
| **Host Target** | Oracle Cloud Always Free (Ampere A1 ARM64 / AMD x86_64, 12 GB RAM) |

### FRIDAY Universe Peer Mesh Connections

Within `friday_mesh`, Forge communicates over authenticated HTTP/WebSocket protocols with its peer agents:
- **FRIDAY Core (Gateway)**: `http://friday:10000`
- **Inference (Reasoning Gateway)**: `http://inference:8000`
- **Memora (Persistent Memory)**: `http://memora:8000`
- **IntelX (Technical Research)**: `http://intelx:8000`
- **Futuris (Predictive Forecasting)**: `http://futuris:8000`
- **Cortex (Web Operations)**: `http://cortex:8000`
- **Sentinel (Security Defense)**: `http://sentinel:8000`
- **Stratex (Quantitative Execution)**: `http://stratex:8000`

---

## 🚀 Core Capabilities

1. **Deterministic Multi-File Code Synthesis**
   - Generates production-ready applications across Python (FastAPI, CLI, scripts), Node.js / TypeScript (Express, React), and Go.
   - Employs domain-specific architecture templates and the Web Studio engine for responsive, modern web applications.
2. **Strict Verification Battery (10 Automated Checks)**
   - AST syntax tree validation and structural integrity.
   - Code formatting and linting via Ruff (`--no-cache`).
   - Automated test suite execution (`pytest`, `jest`, `go test`).
   - Runtime smoke testing of CLI commands and web service entrypoints.
   - Static web assets, HTML semantics, and CSS balance validation.
   - Automated headless browser validation and screenshot capture.
   - Security scanning against CVE pattern databases and credential leaks.
3. **Anti-Loop Self-Repair Engine**
   - Failure classification across syntax, runtime, dependency, and logic errors.
   - SHA-256 deduplicated patch loops capped at 3 attempts (`LoopGuard`).
   - Deterministic AST syntax repair combined with LLM patch synthesis.
4. **Isolated Ephemeral Workspaces**
   - Every build runs in an isolated workspace (`workspaces/<task_id>/`).
   - Complete filesystem, terminal, and background process isolation.

---

## 🔒 Sandbox Safety & Execution Constraints

Forge enforces defense-in-depth isolation for all generated code:

- **Process Group Isolation**:
  - On Linux/Unix, subprocesses are spawned in independent sessions (`start_new_session=True`).
  - On Windows, subprocesses use `subprocess.CREATE_NEW_PROCESS_GROUP`.
  - Timeouts and termination signals (`SIGTERM`/`SIGKILL`) only target the child's process tree and can never leak to the host Forge server or pytest runner.
- **Environment Allowlisting (`SAFE_HOST_ENV_ALLOWLIST`)**:
  - Sandboxed commands do not inherit arbitrary host environment variables.
  - Secrets, tokens, and database passwords are withheld by default; only essential runtime variables (`PATH`, `LANG`, `TMPDIR`, `PYTHONPATH`, Windows system variables) are exposed.
- **Output Bounds & Secret Redaction**:
  - Output streams are truncated at 200,000 characters to prevent memory exhaustion from runaway loops.
  - All logs and command outputs pass through automated regex redaction to purge exposed API keys, bearer tokens, and private credentials.
- **Graceful Shutdown**:
  - Traps `SIGTERM` and `SIGINT` signals.
  - On container shutdown, all active background tasks, development servers, and in-flight sandboxes are cleanly halted within a strict 5-second grace period.

---

## 📡 API Specification

All endpoints support authentication via the `X-API-Key` or `Authorization: Bearer <TOKEN>` header.

### 1. Health Check (`GET /health`)
Reports service liveness and database connectivity evidence.

**Request:**
```bash
curl -X GET "https://friday-universe.duckdns.org/forge/health"
```

**Response (`HTTP 200 OK`):**
```json
{
  "status": "ok",
  "service": "forge",
  "version": "0.1.0",
  "uptime_seconds": 142.8,
  "database_connected": true,
  "evidence_class": "process_liveness",
  "observed_at": "2026-10-14T16:25:27.297488+00:00"
}
```

### 2. Readiness Check (`GET /ready` or `GET /health/ready`)
Verifies database connectivity and workspace filesystem write capabilities.

**Response (`HTTP 200 OK`):**
```json
{
  "status": "ready",
  "service": "forge",
  "version": "0.1.0",
  "database_connected": true,
  "workspaces_writable": true,
  "evidence_class": "dependency_readiness",
  "observed_at": "2026-10-14T16:25:27.297488+00:00"
}
```

### 3. Service Diagnostics & Telemetry (`GET /status` or `GET /health/detailed`)
Exposes detailed diagnostic health, database metrics, external mesh connectivity, and monitor alerts.

### 4. Prometheus Metrics Exporter (`GET /metrics`)
Exposes Prometheus-formatted telemetry (e.g., `forge_uptime_seconds`, `forge_requests_total`, `forge_tasks_total`).

---

### 5. Autonomous Code Synthesis (`POST /generate`)
Synthesizes a complete project architecture, initializes an isolated workspace, and generates an 8-stage execution plan.

**Request:**
```bash
curl -X POST "https://friday-universe.duckdns.org/forge/generate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_forge_api_key" \
  -d '{
    "goal": "Build a FastAPI REST service with SQLite task tracking and pytest tests",
    "requirements": ["FastAPI", "SQLite", "Pydantic v2", "Pytest"],
    "mode": "autonomous",
    "max_budget": 10.0
  }'
```

**Response (`HTTP 201 Created`):**
```json
{
  "task_id": "task_4f8b91c2a015",
  "goal": "Build a FastAPI REST service with SQLite task tracking and pytest tests",
  "state": "READY",
  "workspace_path": "workspaces/task_4f8b91c2a015",
  "progress_percentage": 0.0,
  "created_at": "2026-10-14T16:30:00.000000Z"
}
```

---

### 3. Sandboxed Command Execution (`POST /execute`)
Executes an arbitrary command inside a task workspace under process sandboxing and resource constraints.

**Request:**
```bash
curl -X POST "https://friday-universe.duckdns.org/forge/execute" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_forge_api_key" \
  -d '{
    "task_id": "task_4f8b91c2a015",
    "command": "python -m pytest tests/ -v",
    "timeout_seconds": 60,
    "role": "tester"
  }'
```

**Response (`HTTP 200 OK`):**
```json
{
  "task_id": "task_4f8b91c2a015",
  "command": "python -m pytest tests/ -v",
  "exit_code": 0,
  "stdout": "================ 3 passed in 0.42s ================",
  "stderr": "",
  "duration_ms": 450.2,
  "timed_out": false
}
```

---

### 4. Automated Code Refactoring (`POST /refactor`)
Applies structural refactoring, code quality updates, or security hardening to files within an active workspace.

**Request:**
```bash
curl -X POST "https://friday-universe.duckdns.org/forge/refactor" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_forge_api_key" \
  -d '{
    "task_id": "task_4f8b91c2a015",
    "goal": "Refactor database queries to use parameterized queries and async sessions",
    "files": ["main.py", "db.py"],
    "instructions": "Prevent SQL injection and modernize async connection management"
  }'
```

**Response (`HTTP 200 OK`):**
```json
{
  "task_id": "task_4f8b91c2a015",
  "status": "COMPLETED",
  "summary": "Refactoring processed for: Refactor database queries to use parameterized queries and async sessions",
  "modified_files": ["main.py", "db.py"]
}
```

---

### 5. FRIDAY Universe Peer Delegation (`POST /api/v1/forge/delegate`)
Full agent-to-agent delegation interface complying with the FRIDAY Universe envelope contract.

**Request:**
```bash
curl -X POST "https://friday-universe.duckdns.org/forge/api/v1/forge/delegate" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_forge_api_key" \
  -d '{
    "task_id": "task_del_98213",
    "source_agent": "friday",
    "target_agent": "forge",
    "action": "build",
    "payload": {
      "goal": "Synthesize microservice and verify test battery"
    }
  }'
```

---

## ⚙️ Environment Configuration

| Variable | Description | Production Default |
| :--- | :--- | :--- |
| `FORGE_ENV` | Runtime environment (`development`, `staging`, `production`) | `production` |
| `PORT` | HTTP server listening port | `8000` |
| `FORGE_HOST` | Host address to bind Uvicorn | `0.0.0.0` |
| `FORGE_API_KEY` | Secret API key for authenticating incoming requests | *Required in production* |
| `FRIDAY_API_KEY` | FRIDAY Core gateway credential for peer agent delegation | *Required in production* |
| `API_KEY_REQUIRED` | Whether authentication is enforced on API routes | `true` (in production) |
| `RATE_LIMIT_ENABLED` | Sliding-window request rate limiter toggle | `true` (in production) |
| `DEFAULT_RATE_LIMIT`| Hourly request quota per API key | `100` |
| `CORS_ORIGINS` | Comma-separated CORS whitelist | `https://friday-universe.duckdns.org,http://localhost:8000,...` |
| `INFERENCE_URL` | Base URL for the Inference AI Reasoning Gateway | `http://inference:8000` |
| `MEMORA_URL` | Base URL for the Memora Persistent Memory Fabric | `http://memora:8000` |
| `INTELX_URL` | Base URL for the IntelX Technical Research Service | `http://intelx:8000` |
| `FUTURIS_URL` | Base URL for the Futuris Predictive Intelligence Engine | `http://futuris:8000` |
| `CORTEX_URL` | Base URL for the Cortex Autonomous Web Operations Service | `http://cortex:8000` |
| `SENTINEL_URL` | Base URL for the Sentinel Cybersecurity Defense Shield | `http://sentinel:8000` |
| `STRATEX_URL` | Base URL for the Stratex Algorithmic Trading Platform | `http://stratex:8000` |
| `FRIDAY_URL` | Base URL for the FRIDAY Core Central Gateway | `http://friday:10000` |
| `DEFAULT_PROVIDER`| Default model provider (`direct`, `openai`, `anthropic`, `mock`) | `direct` |
| `DEFAULT_MODEL` | Default model identifier | `direct-default` |

---

## 💻 Local Development & Testing

### 1. Local Setup
```bash
# Clone repository
git clone https://github.com/surendra2304/Forge.git
cd Forge

# Create Python 3.11 virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -e ".[dev]"
```

### 2. Run Tests
```bash
# Execute the full pytest test suite
pytest tests/ -v
```

### 3. Run Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 🐳 Docker Deployment

### 1. Build and Run Container
```bash
# Build production image
docker build -t forge:latest .

# Run container on port 8000 (host port 8002)
docker run -d \
  --name forge \
  --restart unless-stopped \
  -p 8002:8000 \
  -e FORGE_ENV=production \
  -e FORGE_API_KEY="your_secret_key" \
  forge:latest
```

### 2. Run via Docker Compose on `friday_mesh`
```bash
docker compose up -d
```

---

## 📄 License

Project Forge is open-source software licensed under the [MIT License](LICENSE).
