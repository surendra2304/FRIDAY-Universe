---
name: triaging-vulnerabilities
description: Triage vulnerability findings for FRIDAY's own codebase and dependencies — reachability first, then severity, then a patch order the fleet can actually execute.
tier: defensive
domain: vulnerability-management
attack: [T1190]
csf: [ID.RA, PR.PS]
d3fend: [D3-PM]
---

# Triaging vulnerabilities

## When to use
Dependency-scan results, advisory matches and audit findings against
FRIDAY's own repositories and deployed services.

## Workflow
1. Confirm the vulnerable component is actually deployed (in the service's
   requirements AND imported on a reachable path) — unshipped code is a
   backlog note, not an alert.
2. Check exploitability in fleet context: internet-facing? authenticated?
   does the vulnerable function get called with attacker input?
3. Rank: reachable + internet-facing + known exploit first; then reachable
   internal; then present-but-unreachable; then not-deployed (close).
4. Patch in dependency order, one service at a time, with the service's
   test suite run before and after; record any version pin that blocks
   the fix as its own task.
5. Re-scan after patching and record the delta against the previous run.

## Evidence to collect
- Scanner output, reachability determination per finding, patch commits,
  post-patch rescan delta.

## FRIDAY fleet notes
Fleet Python is 3.10 — a fix that requires a newer interpreter is a
planned upgrade task, not a silent skip; record it as blocked-with-reason.
