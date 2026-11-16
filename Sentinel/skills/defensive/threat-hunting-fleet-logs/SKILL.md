---
name: threat-hunting-fleet-logs
description: Hypothesis-driven threat hunting over FRIDAY fleet logs — scheduled jobs, unusual egress, new persistence mechanisms and anomalous agent behaviour. Read-only analysis of the fleet's own telemetry.
tier: defensive
domain: threat-hunting
attack: [T1053, T1071, T1547, T1059]
csf: [DE.CM, DE.AE]
d3fend: [D3-DA, D3-NTA]
---

# Threat hunting in fleet logs

## When to use
Scheduled hunts (weekly) and after any incident, over logs from FRIDAY's
own hosts and agents only.

## Workflow
1. State a hypothesis first, e.g. "a compromised agent would add a cron
   job or systemd unit to persist" — hunts without hypotheses are noise.
2. Persistence hunt: diff cron/systemd/timers against the known-good
   inventory for each host; any new entry is a finding until explained.
3. Egress hunt: list outbound destinations per agent; destinations outside
   the agent's known provider set (LLM APIs, venues, feeds) are findings.
4. Execution hunt: shell-outs from agent processes to interpreters or
   download tools (`curl | sh` patterns) in logs.
5. Close each hunt with: hypothesis, queries run, hits, disposition of
   every hit (benign-explained / finding / needs-data). No silent drops.

## Evidence to collect
- Hunt hypothesis, exact queries, raw hits, per-hit disposition.

## FRIDAY fleet notes
Hunting is read-only. If a hunt needs to touch a third-party system, it is
out of scope for Sentinel — record the need and stop.
