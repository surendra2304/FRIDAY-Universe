---
name: containing-active-incident
description: Containment-first incident response for a compromised FRIDAY fleet host or agent — isolate, preserve evidence, eradicate, recover, review. Defensive response only.
tier: defensive
domain: incident-response
attack: []
csf: [RS.MA, RS.AN, RS.MI, RC.RP]
d3fend: [D3-EI, D3-NI]
---

# Containing an active incident

## When to use
A confirmed compromise or active malicious behaviour on a FRIDAY fleet
host, agent service or credential.

## Workflow
1. Declare the incident: time, scope suspected, incident lead (Sentinel),
   and a single timeline log — all later entries append to it.
2. Preserve first: snapshot volatile evidence (process list, network
   connections, relevant logs, file hashes of suspects) BEFORE changing
   anything on the host.
3. Contain: stop the affected service, revoke the affected credentials /
   tokens, block the malicious indicator at the host firewall. Prefer
   reversible containment (stop, not wipe).
4. Eradicate: identify the entry vector from evidence; close it (patch,
   config, credential rotation) before any service restarts.
5. Recover: restart from known-good code/config, watch the host with
   heightened logging for at least 24h.
6. Review: blameless post-incident note — timeline, root cause, what
   detection missed, concrete follow-up tasks.

## Evidence to collect
- Timeline log, preserved volatile evidence, revoked-credential list,
  entry-vector determination, recovery verification output.

## FRIDAY fleet notes
Real-money systems (Stratex) stay demo-only during an incident: if a
trading host is in scope, halt the agent first and reconcile positions
from the venue record before anything restarts.
