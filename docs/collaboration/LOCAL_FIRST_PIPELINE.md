# Local-First Pipeline (TASK-REL-046, owner direction 2026-11-15)

The Oracle servers and their bridge are the bottleneck of this project:
two ~956 MB VMs carry the whole fleet, and every test cycle that runs
through the bridge competes with production for the same CPU, RAM and
bridge process. The owner directed on 2026-11-15 that testing moves to
Muse's side: **clone everything locally, test there, and push only
successful work to Oracle.**

## The rule

Every agent change follows this pipeline, in this order:

1. **Build and test locally** in the crew's own sandbox workspace
   (unit tests, imports, linters — the fast inner loop).
2. **Staging smoke gate** — `staging/smoke_gate.py` boots the local
   fleet replica with production boot recipes, production memory caps
   and dummy credentials, and must pass for every agent the change
   touches (see `staging/README.md`). A change that would OOM on the
   956 MB Oracle VMs should fail *here* first.
3. **PR** from a fresh-main branch, with the gate output in the PR
   description or the task's completion comment.
4. **Merge** by the coordinator after review.
5. **Fleet CD deploy** to Oracle.
6. **Production probe** — the live health/probe checks on the servers,
   which remain the only proof of "production-verified".

No step substitutes for a later one: a staging pass is not a merge
approval, and a merge is not a production verification. Status is still
reported in the five honest states (implemented / tested / merged /
deployed / production-verified).

## Gate state today (2026-11-15, first full run — `staging/RESULTS_REL046.md`)

- **Gated and passing:** Inference, Cortex, FRIDAY.
- **Gated and currently RED on footprint:** Stratex (~199 MB steady vs
  180 MB cap) and Futuris (~194 MB vs 180 MB) in the staging
  environment. Changes to these two agents are blocked at the gate
  until their footprint fits or the environment delta (Python 3.12
  staging vs 3.10 production) is closed — the coordinator decides which,
  with the measurements in hand. The caps are never silently raised.
- **Staging-exempt (bridge-probe path remains mandatory):** Memora,
  IntelX, Forge, Sentinel, VyralX — each connects to Oracle during
  startup and cannot boot without a reachable Oracle, which the sandbox
  does not have. Exempt is declared per agent in
  `staging/fleet_manifest.yaml` with its evidence. An exemption is
  never reported as a pass.

## What can NEVER be staged locally

The following cannot be reproduced in the sandbox by construction.
They still need the bridge — **batched and sparingly**, planned into as
few bridge sessions as possible, never as an interactive test loop:

- **Live demo-trading credentials and sessions** — Binance demo-fapi /
  OANDA practice keys and any live session against the exchanges.
  Staging runs Stratex's dashboard only, with dummy keys and trading
  disabled; the trading daemon is never started locally.
- **LiveKit Cloud voice with real keys** — real Gemini Live / LiveKit
  Cloud sessions, the voice worker against production keys, and any
  test whose result depends on provider quota or behaviour.
- **Production data volumes** — the Oracle Autonomous Database contents,
  production memory stores, ledgers and media. Staging uses dummy DSNs
  and empty stores; data-dependent verification is a production probe.
- **The owner's phone and laptop** — device control paths terminate on
  hardware only the owner has; local work stops at mock-device proofs.
- **Anything whose evidence is the production environment itself** —
  Fleet CD deploys, systemd state, Caddy routing, the bridge's own
  behaviour, and final production verification (step 6 above).

## Why the bridge stays in the loop at all

The bridge is the only path to the Oracle VMs. Local-first removes the
*testing* load from it; it does not remove deploys, production probes,
or the never-stageable list above. Crews batch bridge work: one session
that ships a proven change and probes it beats ten that iterate live.
