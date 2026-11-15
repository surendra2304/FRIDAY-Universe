# Sentinel Security Reference — Instagram Corpus Pass (TASK-IG-SEN-04)

This document banks three reference-class ideas from the owner's
Instagram reference corpus (owner directive 2026-11-15) plus the
PentAGI repo-card notes. It is a **reference**, not a feature: the
code-bearing Sentinel ideas from the same corpus live in
TASK-IG-SEN-01 (attacker-view audits), TASK-IG-SEN-02 (device &
credential posture) and TASK-IG-SEN-03 (Telegram threat-intel watch).

**Scope rule for everything below:** Sentinel is defensive and
read-only. Every capability named here is used for monitoring and
checking the owner's own fleet, devices and accounts — never against
third-party targets.

Corpus provenance:

| Item | Source | Banked as |
|------|--------|-----------|
| DV9IyW1jCeJ (@itshahirx) | Curated cybersecurity learning resources | §1 learning reference |
| DZZ_-xxzaOR (@sanjaytechx) | OSINT/recon tool list: Shodan, Maltego, Nmap, Sherlock | §2 capability registry |
| DeU2IZOukqT (@hackingwithranjith) | Qubes OS compartmentalisation explainer | §3 isolation assessment |
| Deo925ayzJ9 → repo card `pentagi.md` | vxcontrol/pentagi, verdict **reference-only** | §4 role-design notes |

---

## 1. Curated cybersecurity learning / resource reference

The standing reading list for Sentinel's domain knowledge — what a
human analyst on this fleet should work through, and what Sentinel's
own rules and checks cite as their reference frame.

**Frameworks (the fleet's checks are expressed in these terms):**
- MITRE ATT&CK (attack.mitre.org) — tactic/technique vocabulary;
  Sentinel's cyber-skills engine already aligns to ATT&CK / NIST CSF /
  D3FEND / ATLAS.
- NIST Cybersecurity Framework — posture reporting categories.
- CISA Known Exploited Vulnerabilities catalog — already a live feed
  adapter (`CISAKEVFeedAdapter`); the prioritisation reference for
  "patch this first".
- OWASP (owasp.org) — Top 10 + ASVS for the web/API checks; the
  reference behind the api_security and web modules.

**Hands-on learning (free tiers, in study order):**
1. Networking & Linux fundamentals — the substrate of every fleet
   check in §2 (ports, services, DNS, TLS).
2. PortSwigger Web Security Academy (portswigger.net/web-security) —
   free, lab-based web security; the syllabus behind the web module's
   check design.
3. TryHackMe / Hack The Box free tiers — guided SOC and blue-team
   rooms; useful for the defender's view of the techniques ATT&CK
   names.
4. Android security — the official Android platform security model
   documentation; the reference frame for TASK-IG-SEN-02's posture
   rules (dangerous permissions, sideloading, patch currency).
5. OSINT tradecraft — read §2's ethics note first: the fleet's OSINT
   is watchlist monitoring of public sources about the owner's own
   assets, not investigation of people.

**Threat-intel reading (feeds Sentinel already consumes):** CISA KEV
and advisories, AbuseIPDB (via `AbuseIPFeedAdapter`), and — since
TASK-IG-SEN-03 — public Telegram leak channels as an early-warning
source.

## 2. OSINT / recon capability registry

The corpus's tool list (Shodan, Maltego, Nmap, Sherlock) mapped to
what Sentinel can defensively do today, what covers it, and where the
honest gaps are. "Coverage" names the adapter that does the job;
targets are always the owner's own assets or public watchlist data.

| Corpus tool | What it does | Defensive use here | Sentinel coverage today | Gap / decision |
|---|---|---|---|---|
| **Nmap** | Port & service discovery | Know what the fleet exposes before an attacker enumerates it | `NetworkExposureAdapter` (`network.exposure_analysis`), `HostDiscoveryAdapter` (`network.host_discovery`) — own-fleet, allowlist-bound; TASK-IG-SEN-01's attacker-view audit composes these into the public-ingress check (AV-EXP-001/002) | No general-purpose scanning: deliberately. Probing is restricted to configured fleet hosts; there is no free-form target parameter to abuse |
| **Shodan** | Search engine of internet-visible services | External view of the fleet's two public IPs without probing | TASK-IG-SEN-01 probes the fleet's public IPs directly (ground truth, fresher than any index) | No Shodan API adapter — deliberate non-adoption: with exactly two known public hosts, direct allowlisted probing beats a third-party index on freshness and needs no API key |
| **Maltego** | Link/graph analysis over entities | Connect IOCs, domains and infrastructure into one picture | Partial: `threat_intel` IOC extraction + correlation; IntelX owns graph-style OSINT (`/api/v1/osint/*` Maltego graph builder per repo AGENTS.md) | No graph visualisation inside Sentinel — accepted; Sentinel emits findings, IntelX owns investigative graphs |
| **Sherlock** | Username presence across sites | Detect impersonation of the owner's handles/accounts | None in Sentinel | Recorded as a **future, owner-handles-only** capability: periodic presence checks for the owner's own usernames, alerting on lookalike/new accounts. Not implemented in this pass — impersonation monitoring needs the owner's handle list and belongs with the SEN-03 watchlist pattern when scheduled |

**Existing recon/network coverage the registry builds on**
(`sentinel/modules/recon`, `sentinel/modules/network`,
`sentinel/modules/wireless`):

- `SubdomainEnumAdapter` (`recon.subdomains`) — subdomain inventory
  of the owner's domains.
- `IPIntelligenceAdapter` (`recon.ip_intel`, `recon.asn_lookup`).
- `CertificateInspectorAdapter` (`recon.certificate_inspect`) — TLS
  certificate state for fleet endpoints.
- `TechnologyFingerprintAdapter` (`recon.tech_fingerprint`).
- `OSINTAdapter` (`recon.osint`, `recon.security_txt`).
- `SegmentationAnalyzerAdapter` (`network.segmentation_check`),
  `FirewallConfigReviewAdapter` (`network.firewall_review`) — the
  checks behind the SEN-013→SEN-016 hardening arc's end-state
  (public ingress 22/80/443 only).
- `TrafficAnalysisAdapter` (`network.traffic_analysis`).
- `WirelessConfigAssessmentAdapter` — home-router/Wi-Fi posture
  (WPS, weak encryption), composed by TASK-IG-SEN-01's audit.

## 3. Compartmentalisation assessment (Qubes-style)

Qubes OS isolates activities into separate VM compartments by trust
level, so one compromise stays contained. The fleet cannot run
VM-per-agent on two ~956 MB VMs — but the *principles* map, and this
is the honest scorecard against them.

**Already compartmentalised:**
- One systemd service per agent, each with its own Oracle schema and
  its own `.env` — an agent compromise does not automatically hand
  over another agent's data store.
- Two-server split: the public-facing orchestrator tier (Server 1)
  is separated from Sentinel/Cortex/VyralX (Server 2); verified
  public ingress is 22/80/443 only (SEN-016).
- Staging isolation exists for testing (TASK-REL-046 local staging
  fleet with dummy credentials) — the "disposable qube" pattern:
  untrusted code runs against fake data first.

**Known anti-patterns (recorded, with owners):**
- A shared `GITHUB_TOKEN` readable by multiple agents (found by
  TASK-SEN-011 in Forge logs) — the opposite of per-compartment
  credentials. The decided direction (TASK-MEM-005, same shape):
  master/shared keys live only in the owning agent's env; every other
  agent holds only its own scoped key.
- One shared virtualenv for all agents on a server — a poisoned
  dependency is fleet-wide. Accepted today under the RAM budget;
  revisit when the ARM server lands.

**Adoptable principles (in force as design rules from this doc):**
1. Per-agent credentials only; a credential's blast radius is one
   agent (see also TASK-IG-SEN-02's recurring 0600/0700 checks).
2. New capabilities start read-only and allowlist-bound
   (TASK-IG-SEN-01/02/03 all follow this).
3. Untrusted content (feeds, channel posts, corpus items) is data,
   never instructions — it enters through extractors and matchers,
   not executors.
4. Anything that can act (deploy, publish, trade) sits behind an
   approval gate in a different compartment than the thing that
   proposes it (SEN-006 approval dispatch pattern).

**Not adopted:** full VM-per-agent isolation and Qubes itself —
impossible on current hardware; reassess on the ARM server.

## 4. PentAGI role-design notes (reference-only)

Per repo card `pentagi.md`: vxcontrol/pentagi is a self-hosted
autonomous penetration-testing platform (specialised agents running
20+ real security tools in Docker sandboxes; PostgreSQL/Neo4j
backend). Verdict **reference-only** — too heavy for the fleet and
offensive in remit; Sentinel is defensive. Only its **role design**
is mined:

| PentAGI role | Defensive analogue in Sentinel |
|---|---|
| Researcher (gathers target intel) | Recon adapters (§2) + threat-feed adapters — gather, never strike |
| Planner (sequences the test) | Baseline/delta evaluation: decide what changed and what matters |
| Executor (runs tools in a sandbox) | The allowlist-bound probes of TASK-IG-SEN-01 — the only "execution", read-only by construction |
| Adviser / reflector (reviews results) | AlertEngine triage + SEN-006 approval dispatch — a human-visible gate before anything acts |
| Memorist (stores findings/knowledge) | Baseline store + this reference doc series |

**Explicit non-adoptions:** no autonomous offensive execution of any
kind; no tool sandbox fleet (hardware); no engagement with targets
outside the owner's assets — PentAGI's own authorised-targets-only
EULA underlines the same line Sentinel already holds.

---

*Maintenance: when a new adapter lands, add its row to §2; when a
compartmentalisation fact changes (new server, credential split),
update §3's scorecard in the same PR. Corpus provenance for this doc:
TASK-IG-SEN-04, claim on issue #35.*
