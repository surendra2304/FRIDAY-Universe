---
name: detecting-ssh-brute-force
description: Detect SSH password-spraying and brute-force attempts against fleet hosts from auth logs, with thresholds tuned for FRIDAY's key-only SSH posture.
tier: defensive
domain: soc-operations
attack: [T1110, T1110.001, T1078]
csf: [DE.CM, DE.AE]
d3fend: [D3-UBA, D3-AL]
---

# Detecting SSH brute force

## When to use
Continuous detection on every fleet host's auth log; Sentinel's watchdog
runs this as a log check, never as an active probe of any host.

## Workflow
1. Parse `auth.log` / journald sshd entries for `Failed password`,
   `Invalid user` and `maximum authentication attempts exceeded`.
2. Aggregate failures per source IP over 5-minute and 1-hour windows.
3. Alert thresholds: ≥10 failures/5min from one IP, or ≥5 distinct invalid
   usernames from one IP (spray pattern), or ANY successful login following
   ≥20 failures from the same IP (possible success after brute force).
4. Because fleet SSH is key-only, any `Accepted password` event is itself a
   high-severity finding — password auth should be impossible.
5. Record the finding with first/last seen, source IP and target accounts;
   blocking is done by the operator or fail2ban, not by this skill.

## Evidence to collect
- Matching log lines with timestamps, per-IP failure counts, the list of
  targeted usernames, any post-burst success event.

## FRIDAY fleet notes
Detection is read-only log analysis on FRIDAY's own hosts. Never scan,
probe or retaliate against the source IP — it may be spoofed or shared.
