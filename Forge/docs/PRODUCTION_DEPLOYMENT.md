# Project FORGE — Production Deployment & Operations Guide

This guide provides operational instructions for deploying and running Project FORGE as a high-availability, standalone autonomous software engineering engine.

---

## 1. Deployment Models

### Model A: Docker & Container Orchestration

#### Docker Compose
Run FORGE with persistent volumes for data, workspaces, and artifacts:

```bash
docker compose up -d --build
```

Inspect container health:
```bash
docker compose ps
curl http://localhost:8000/health
```

#### Kubernetes
Deploy using the provided manifests in `app/deployment/kubernetes.yaml`:

```bash
# 1. Create secret for AI Universe reasoning API key
kubectl create secret generic forge-secrets --from-literal=ai-universe-key="<your_key>"

# 2. Apply deployment & service
kubectl apply -f app/deployment/kubernetes.yaml

# 3. Check rollouts & probes
kubectl rollout status deployment/forge-engine
```

---

### Model B: Bare-Metal / Virtual Machine (Systemd)

1. Provision Linux user and workspace directories:
   ```bash
   sudo useradd -r -s /bin/false forge
   sudo mkdir -p /opt/forge /var/lib/forge/data /var/lib/forge/workspaces /var/lib/forge/artifacts
   sudo chown -R forge:forge /opt/forge /var/lib/forge
   ```

2. Copy systemd unit file from `app/deployment/forge.service` to `/etc/systemd/system/`:
   ```bash
   sudo cp app/deployment/forge.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now forge
   sudo systemctl status forge
   ```

---

## 2. Health Probes & Monitoring

### Probes
- **Liveness Probe:** `GET /health` (Returns 200 with uptime and version).
- **Readiness Probe:** `GET /health/ready` (Validates database connectivity and workspace write access).
- **Diagnostics:** `GET /health/detailed` (Reports AI-Universe status, DB query latency, and alert conditions).

### Prometheus Metrics Exporter
Scrape Prometheus metrics on standard port:
```http
GET /metrics
```
Exported metrics:
- `forge_uptime_seconds`
- `forge_requests_total`
- `forge_errors_total`
- `forge_tasks_total{status="submitted|completed|failed"}`
- `forge_verifications_total{result="passed|failed"}`
- `forge_system_cpu_percent`
- `forge_system_memory_percent`
- `forge_system_disk_percent`

---

## 3. Security & Rate Limiting

- **API Key Requirement:** Set `API_KEY_REQUIRED=true` and `FORGE_API_KEY=<secure_token>`.
- **Headers Accepted:** `X-API-Key: <token>` or `Authorization: Bearer <token>`.
- **Rate Limiting:** Enforces a sliding-window limit (default 100 requests/hour per client).

---

## 4. Backup & Disaster Recovery

### Automated Database Snapshots
FORGE creates consistent SQLite backups via `BackupManager`:
- Snapshots are written to `data/backups/forge_backup_<timestamp>.db`.
- Backups older than 7 days are automatically pruned.

### Manual Database Restoration
To restore a snapshot:
```python
from pathlib import Path
from app.backup.recovery import backup_manager

backup_manager.restore_database(Path("data/backups/forge_backup_20260827_190000.db"))
```

---

## 5. Performance Tuning

- **SQLite WAL Mode:** PRAGMA optimizations automatically applied on startup (`journal_mode=WAL`, `synchronous=NORMAL`, 64MB cache).
- **Response Compression:** GZip middleware enabled for all payloads $> 1\text{ KB}$.
