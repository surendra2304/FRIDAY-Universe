---
name: reviewing-iam-least-privilege
description: Least-privilege review of FRIDAY's own accounts, API keys and service tokens — inventory, usage check, scope reduction and rotation hygiene. Defensive administration only.
tier: defensive
domain: iam
attack: [T1078, T1098]
csf: [PR.AA, PR.AT]
d3fend: [D3-CBAN]
---

# Reviewing IAM least privilege

## When to use
Monthly, and whenever a new key, token or account is created for any
FRIDAY agent or service.

## Workflow
1. Inventory every credential: owner agent, purpose, scope granted,
   creation date, last-used date (from provider logs where available).
2. Flag: credentials unused for 30+ days, scopes broader than the stated
   purpose, shared credentials across agents, and credentials with no
   recorded owner.
3. Reduce: narrow scopes to the operations the owning agent demonstrably
   performs; split shared credentials per agent so one leak is not a
   fleet leak.
4. Rotate on schedule and immediately on any suspicion; verify the old
   credential is dead (provider confirms rejection) — rotation without
   revocation is not rotation.
5. Record the review: inventory table, flags, actions taken, exceptions
   with reasons and expiry dates.

## Evidence to collect
- Credential inventory, per-credential flags, scope-change records,
  old-credential rejection proof.

## FRIDAY fleet notes
This skill administers FRIDAY's own credentials only. It never enumerates
or tests credentials belonging to anyone else.
