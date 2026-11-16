---
name: triaging-soc-alerts
description: Structured triage of Sentinel's own alerts — deduplicate, enrich with fleet context, score severity, and route to response or watch status without alert fatigue.
tier: defensive
domain: soc-operations
attack: []
csf: [DE.AE, RS.AN]
d3fend: [D3-AL]
---

# Triaging SOC alerts

## When to use
Every alert Sentinel raises about FRIDAY's own fleet, before it reaches
the owner. The goal is verified signal, not volume.

## Workflow
1. Deduplicate: same rule + same host + same indicator within 1 hour is one
   alert with a count, not N alerts.
2. Enrich: attach host role (from AGENTS.yaml), the service affected, and
   whether the indicator was seen before (baseline diff if available).
3. Verify before escalating: re-check the underlying evidence (log line,
   file hash, config value) independently — an alert that cannot be
   re-verified is downgraded to watch status, never escalated as fact.
4. Score severity from impact on the fleet: internet-facing + confirmed >
   internal + unconfirmed.
5. Route: confirmed high/critical → incident-response skill; everything
   else → daily digest with counts.

## Evidence to collect
- Original alert payload, enrichment context, the re-verification result,
  final severity and routing decision with reason.

## FRIDAY fleet notes
The owner has a standing rule: unverified claims are worse than no claim.
Triage output must state plainly what was verified and what was not.
