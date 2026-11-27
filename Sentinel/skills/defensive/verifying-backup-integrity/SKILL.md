---
name: verifying-backup-integrity
description: Verify FRIDAY fleet backups are restorable, not just present — checksum validation, restore drills into scratch space and recovery-time measurement.
tier: defensive
domain: incident-response
attack: [T1490]
csf: [RC.RP, ID.IM]
d3fend: [D3-DSDA]
---

# Verifying backup integrity

## When to use
Weekly for fleet state (agent databases, memory stores, configs) and
before any risky migration or upgrade.

## Workflow
1. Presence is not proof: for each backup, verify its recorded checksum
   against the stored file.
2. Restore drill: restore the newest backup into scratch space (never
   over production), open it with the owning agent's own reader, and run
   the agent's integrity checks.
3. Measure restore duration; record it — recovery-time surprises belong
   in the drill, not in a real incident.
4. Check coverage: every stateful agent has a backup no older than its
   agreed window; a missing or stale backup is a finding.
5. Keep drill evidence: backup id, checksum result, restore result,
   duration, coverage table.

## Evidence to collect
- Checksum verification results, restore-drill log and duration, coverage
  table with per-agent backup age.

## FRIDAY fleet notes
Fleet disks and RAM are tiny: drills restore into a capped scratch dir
and clean up after themselves, pass or fail.
