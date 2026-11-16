# Sentinel defensive skill pack — provenance, licence and exclusion policy

## Provenance and attribution

This pack is **adapted** from the open-source cybersecurity skills library
at https://github.com/mukul975/Anthropic-Cybersecurity-Skills (skills in
the agentskills.io format, mapped to MITRE ATT&CK, NIST CSF 2.0, MITRE
D3FEND and MITRE ATLAS), restructured and rewritten for FRIDAY Universe's
own fleet and Sentinel's defensive remit.

- **Licence:** Apache-2.0 (the source library's licence). Adaptations are
  likewise offered under Apache-2.0.
- **Attribution:** Source library by Mahipal Jangra (mukul975).
- **Caveat — read this:** despite its repository name, the source library
  is an **independent community project and is NOT affiliated with,
  endorsed by, or produced by Anthropic PBC**. The name is the upstream
  author's, not a vendor claim. Sentinel treats it as community material:
  every adopted skill was reviewed and rewritten before inclusion, and no
  upstream script is executed by this pack.

## Inclusion policy — defensive only

Sentinel is an always-on defensive agent for FRIDAY's own fleet. This pack
therefore includes ONLY skills whose tier is `defensive`: detection,
hardening, incident response, threat hunting over the fleet's own
telemetry, vulnerability management of the fleet's own code, IAM hygiene
for the fleet's own credentials, and AI-security defence of FRIDAY's own
agents.

## Exclusion policy — explicitly NOT included

The following categories from the source library are **excluded by
policy**, and the loader (`Sentinel/app/services/defensive_skills.py`)
refuses to load any skill in them, or with tier `offensive` / `dual-use`,
even if such a file is placed in this directory:

- Red-team operations and adversary emulation / C2 frameworks
- Phishing simulation and social-engineering attack playbooks
- Exploitation, payload and shellcode development
- Credential theft / dumping and password-attack tooling (as attacker)
- Defence evasion, persistence and privilege-escalation (as attacker)
- Malware development and analysis-for-reuse
- Wireless / physical intrusion attacks
- Offensive OSINT / HUMINT / SIGINT collection against third parties

Rationale: an always-on fleet agent has no business holding offensive
playbooks, and the fleet's security scope is FRIDAY's own systems only.
If the owner ever wants an authorised-scope exception, that is a separate
owner decision — it does not belong in this pack.
