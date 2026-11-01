# FRIDAY Universe — Operations Runbook

## Monitoring

### Health Checks
- Universe health: `GET /api/v1/gateway/health` (FRIDAY)
- Per-agent health: `GET /api/v1/{agent}/health`
- Universe metrics: `GET /api/v1/metrics/universe`
- Prometheus metrics: `GET /api/v1/metrics/prometheus`

### Alert Thresholds
- Error rate > 5% → warning
- p95 latency > 10s → warning
- Health score < 70 → critical

### Key Metrics to Watch
- Total requests per agent
- Error count per agent
- Average latency per agent
- Health score per agent
- Universe overall health score

## Common Failure Modes

### Agent Down
1. Check agent logs
2. Verify database connectivity
3. Check memory/CPU usage
4. Restart agent if needed

### High Latency
1. Check if database is slow
2. Check if external APIs are slow
3. Review recent changes
4. Consider scaling

### Database Issues
1. Check connection pool
2. Verify disk space
3. Check for long-running queries
4. Consider read replicas

### Cross-Agent Failures
1. Check FRIDAY gateway health
2. Verify agent endpoints are reachable
3. Check circuit breaker status
4. Review network connectivity

## Backup and Recovery

### Database Backups
- All persistence lives in Oracle Autonomous Database, which takes automated daily
  backups and retains them per the ADB backup policy. There is no self-managed
  database server to dump.
- Manual logical export (per agent schema, using that agent's own login):
  `expdp <agent_user>/<password>@<service_name> schemas=<AGENT_SCHEMA> directory=DATA_PUMP_DIR dumpfile=<agent>_$(date +%F).dmp`
- Recovery is an ADB restore/point-in-time recovery, or an `impdp` of the dumpfile
  into a fresh schema. Never restore one agent's schema over another's.

### Configuration Backups
- Version control all configuration in Git
- Environment variables in secrets manager
- Database schemas in migrations/

## Scaling Considerations

### Horizontal Scaling
- Each agent can run multiple instances behind a load balancer
- Use Redis for session management
- Consider read replicas for databases

### Vertical Scaling
- Increase CPU/RAM for compute-intensive agents (VyralX, Stratex)
- Increase disk I/O for data-heavy agents (Memora, Cortex)

## Security Incident Response

1. **Isolate**: Use Sentinel emergency halt to isolate affected agent
2. **Assess**: Check Sentinel security posture and audit logs
3. **Investigate**: Review IntelX threat intel and correlation engine
4. **Remediate**: Apply patches, rotate credentials, update rules
5. **Recover**: Restart affected agents, verify health
6. **Review**: Post-incident review, update runbook

## Day-2 Operations Checklist

- [ ] Daily health check of all agents
- [ ] Review error rates and alert thresholds
- [ ] Verify backup completion
- [ ] Check disk space usage
- [ ] Review security audit logs
- [ ] Update threat intel feeds
- [ ] Monitor API rate limits
- [ ] Review agent performance trends
