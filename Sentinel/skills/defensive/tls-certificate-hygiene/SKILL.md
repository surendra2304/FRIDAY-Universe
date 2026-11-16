---
name: tls-certificate-hygiene
description: TLS posture checks for FRIDAY's own endpoints — certificate validity and expiry, protocol/cipher floors, and HSTS on the fleet's public surfaces.
tier: defensive
domain: cloud-security
attack: [T1557]
csf: [PR.DS, ID.AM]
d3fend: [D3-TLS]
---

# TLS certificate hygiene

## When to use
Weekly checks of FRIDAY's own public endpoints (bridge, dashboards, APIs)
and after any certificate or proxy change.

## Workflow
1. For each fleet endpoint: fetch the presented certificate; record
   issuer, SANs, not-before/not-after.
2. Alert at 21 days to expiry; escalate at 7 days. A lapsed cert on the
   bridge endpoint is a high-severity finding.
3. Protocol floor: TLS 1.2+ only; flag TLS 1.0/1.1 and weak ciphers
   (RC4, 3DES, export grades) if offered.
4. SANs must match the endpoint's hostname exactly — a mismatch breaks
   clients and can hide a mis-issued or mis-deployed certificate.
5. Public web surfaces should send HSTS; record its max-age.

## Evidence to collect
- Per-endpoint certificate record, expiry countdown, protocol/cipher
  result, HSTS value.

## FRIDAY fleet notes
Checks run against FRIDAY's own endpoints only. Do not probe third-party
hosts with this skill.
