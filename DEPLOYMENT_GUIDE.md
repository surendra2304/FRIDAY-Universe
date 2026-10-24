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
- PostgreSQL (dokploy-postgres or equivalent)
- Redis (for heavy task coordination)
- FFmpeg (for VyralX video rendering)
- Node.js 18+ (for VyralX UI)

## Database Setup

Each agent has its own database. Create them all:

```bash
# Create databases
psql -U postgres -c "CREATE DATABASE friday_db;"
psql -U postgres -c "CREATE DATABASE stratex_db;"
psql -U postgres -c "CREATE DATABASE cortex_db;"
psql -U postgres -c "CREATE DATABASE futuris_db;"
psql -U postgres -c "CREATE DATABASE inference_db;"
psql -U postgres -c "CREATE DATABASE intelx_db;"
psql -U postgres -c "CREATE DATABASE memora_db;"
psql -U postgres -c "CREATE DATABASE sentinel_db;"
psql -U postgres -c "CREATE DATABASE forge_db;"
psql -U postgres -c "CREATE DATABASE vyralx_db;"

# Create users (replace passwords with strong values)
psql -U postgres -c "CREATE USER friday_user WITH PASSWORD 'STRONG_PASSWORD';"
# ... repeat for each agent ...

# Grant privileges
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE friday_db TO friday_user;"
# ... repeat for each agent ...
```

## Environment Variables

Each agent requires environment variables for database connection, API keys, and configuration. Key variables:

```bash
# Database
POSTGRES_HOST=dokploy-postgres
POSTGRES_PORT=5432

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
2. **Database connection errors**: Verify POSTGRES_HOST and credentials
3. **Module import errors**: Install missing dependencies with `pip install -r requirements.txt`
4. **CORS errors**: Ensure CORS_ORIGINS includes the frontend URL
5. **Health check failures**: Check agent logs for startup errors
