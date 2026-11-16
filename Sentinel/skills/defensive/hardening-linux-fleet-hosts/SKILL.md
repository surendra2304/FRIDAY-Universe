---
name: hardening-linux-fleet-hosts
description: Baseline hardening checklist for FRIDAY's own Linux fleet hosts — SSH, firewall, patching, service minimisation and file permissions. Defensive only; run against fleet hosts Sentinel is authorised to audit.
tier: defensive
domain: cloud-security
attack: [T1078, T1190, T1133]
csf: [PR.AC, PR.PS, ID.RA]
d3fend: [D3-PH, D3-FA, D3-SPP]
---

# Hardening Linux fleet hosts

## When to use
Onboarding a new fleet host, after any OS reinstall, and on Sentinel's
scheduled posture review of FRIDAY's own servers.

## Workflow
1. Inventory listening services (`ss -tlnp`); every open port must map to a
   known agent in AGENTS.yaml — anything else is a finding.
2. SSH: key-only auth (`PasswordAuthentication no`), root login disabled,
   `AllowUsers` restricted to the operator account.
3. Firewall default-deny inbound; allow only the ports the host's agents
   actually serve.
4. Unattended security upgrades enabled; record the pending-patch count.
5. World-writable files and unexpected setuid binaries listed and reviewed.
6. Service memory limits set (fleet hosts run ~180MB per-service caps) so one
   agent cannot starve the host.

## Evidence to collect
- `ss -tlnp` output, sshd effective config (`sshd -T`), firewall ruleset,
  pending patch list, setuid/world-writable scan output.

## FRIDAY fleet notes
Fleet hosts are ~956MB RAM Oracle VMs; hardening steps must not install
heavyweight agents. Prefer config and systemd controls already on the box.
