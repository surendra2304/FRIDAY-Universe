---
name: defending-llm-prompt-injection
description: Defensive checks that FRIDAY's agents resist prompt injection from ingested content — untrusted-text fencing, tool-call gating and exfiltration tripwires. Defence and detection only.
tier: defensive
domain: ai-security
attack: []
atlas: [AML.T0051, AML.T0057]
csf: [PR.AC, DE.CM]
d3fend: []
---

# Defending LLM agents against prompt injection

## When to use
Reviewing any FRIDAY agent that ingests external content (web pages,
messages, documents, feeds) and can call tools or send data.

## Workflow
1. Inventory the agent's untrusted inputs and its tool surface; injection
   risk exists only where the two meet.
2. Fencing: untrusted content must reach the model clearly delimited and
   labelled as data, never concatenated into the system instruction.
3. Tool gating: state-changing tools (send, write, trade, deploy) require
   either a user-originated instruction or an approval step — instructions
   found inside ingested content never qualify.
4. Exfiltration tripwires: alert when an agent's outbound payload contains
   credential-shaped strings, env values or memory contents it was not
   asked to send.
5. Regression tests: keep a fixed corpus of injection attempts (direct,
   indirect via page text, via tool output) and run it after every prompt
   or tool-surface change; a pass requires zero unauthorised tool calls.

## Evidence to collect
- Input/tool inventory, fencing implementation reference, tripwire rules,
  injection-corpus test results per change.

## FRIDAY fleet notes
This skill is defensive: it tests FRIDAY's own agents with a fixed,
in-repo corpus. It never crafts injections against third-party systems.
