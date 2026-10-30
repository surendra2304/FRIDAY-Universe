# FRIDAY Universe — Deployment Guide

## Overview

This guide covers deployment of all 10 agents in the FRIDAY Universe.

## Agent Port Assignments

| Agent | Port | Container Port | Ingress Route |
|-------|------|---------------|---------------|
| FRIDAY | 8000 | 8000 | /friday |
| Stratex | 8001 | 8000 | /stratex |
| Cortex | 8002 | 8000 | /cortex |
| Futuris | 8004 | 8000 | /futuris |
| Inference | 8005 | 8000 | /inference |
| IntelX | 8006 | 8000 | /intelx |
| Memora | 8007 | 8000 | /memora |
| Sentinel | 8008 | 8000 | /sentinel |
| Forge | 8009 | 8000 | /forge |
| VyralX | 8010 | 8000 | /vyralx |

## Prerequisites

- Python 3.11+
- Oracle Autonomous Database (FRIDAY Universe DB, plus the VyralX media DB for VyralX)
- Redis (for heavy task coordination)
- FFmpeg (for VyralX video rendering)
- Node.js 18+ (for VyralX UI)

## Database Setup

Oracle Autonomous Database only — PostgreSQL and SQLite are not supported backends.

Two ADBs are used:

- **FRIDAY Universe DB** — one login/schema per agent: `FRIDAY`, `STRATEX`, `INFERENCE`,
  `MEMORA`, `INTELX`, `FORGE`, `FUTURIS`, `SENTINEL`, `CORTEX`, `VYRALX`.
- **VyralX media DB** — the `VYRALX_MEDIA` login/schema.

Provision each login with a strong password in the Oracle console (or as `ADMIN` in SQL
Developer/DB Actions) and give it only the privileges its agent needs. Each agent creates its
own tables on first use; there is no shared database to create with `psql`.

```sql
-- Run once per agent as ADMIN. Never commit real passwords.
CREATE USER FRIDAY IDENTIFIED BY "<strong-password>";
GRANT CONNECT, RESOURCE TO FRIDAY;
ALTER USER FRIDAY QUOTA UNLIMITED ON DATA;
-- Repeat for each agent login, and VYRALX_MEDIA in the VyralX media DB.
```

## Environment Variables

Each agent requires environment variables for database connection, API keys, and configuration. Key variables:

```bash
# Database — Oracle Autonomous Database only. PostgreSQL/SQLite are not supported.
# Each agent reads its own login DSN from the environment; never hardcode it.
# Example: DATABASE_URL=oracle+oracledb://USER:password@(description=...)
# Some agents use a prefixed key (FRIDAY_DATABASE_URL, STRATEX_DATABASE_URL,
# FORGE_DATABASE_URL, SENTINEL_DATABASE_URL, INTELX_DB_URL, ORACLE_CORE_ASYNC_URL).

# API Keys (use secrets manager)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Agent-specific
FRIDAY_FLEET_SUPERVISION_INTERVAL_SECONDS=300
STRATEX_AUTOSTART_SERVICES=0
```

## Startup Commands

### FRIDAY
```bash
cd FRIDAY && python -m src.friday.api.server
```

### Stratex
```bash
cd Stratex && python dashboard.py
```

### VyralX
```bash
cd VyralX && uvicorn app.main:app --host 0.0.0.0 --port 8010
```

### Cortex
```bash
cd Cortex/apps/api && uvicorn cortex_api.main:app --host 0.0.0.0 --port 8002
```

### Inference
```bash
cd Inference && uvicorn app.main:app --host 0.0.0.0 --port 8005
```

### Forge
```bash
cd Forge && uvicorn app.main:app --host 0.0.0.0 --port 8009
```

### Memora
```bash
cd Memora/apps/api && uvicorn main:app --host 0.0.0.0 --port 8007
```

### IntelX
```bash
cd IntelX && uvicorn intelx.app.main:app --host 0.0.0.0 --port 8006
```

### Futuris
```bash
cd Futuris && uvicorn futuris.api.app:app --host 0.0.0.0 --port 8004
```

### Sentinel
```bash
cd Sentinel && uvicorn sentinel.apps.api.main:app --host 0.0.0.0 --port 8008
```

## Health Check Verification

After starting each agent, verify health:

```bash
# Check each agent
curl http://localhost:8000/api/health  # FRIDAY
curl http://localhost:8001/api/health  # Stratex
curl http://localhost:8010/api/health  # VyralX
# ... repeat for each agent ...

# Check universe health via FRIDAY gateway
curl http://localhost:8000/api/v1/gateway/health
```

## Docker Deployment

Use the provided docker-compose.oracle.yml as a template:

```bash
docker compose -f docker-compose.oracle.yml up -d
```

## Troubleshooting

1. **Port conflicts**: Ensure no other service is using the assigned ports
2. **Database connection errors**: Verify the agent's Oracle DSN and credentials
3. **Module import errors**: Install missing dependencies with `pip install -r requirements.txt`
4. **CORS errors**: Ensure CORS_ORIGINS includes the frontend URL
5. **Health check failures**: Check agent logs for startup errors
