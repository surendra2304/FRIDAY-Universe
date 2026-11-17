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

## Production hosts are for production only (off-S1/S2 execution rule, 2026-11-17)

The normative rule lives in `docs/MASTER_PLAN.md` §5 (adopted as
decision D-029). Operationally, for every crew following this pipeline:

- Nothing non-production executes on S1 or S2: no test suites (pytest
  or any other — including a suite spawned from inside a production
  service's own process tree or cgroup), no code-generation batteries,
  benchmarks or load tests, no experiment workers or harnesses
  (including throwaway workers under `/tmp`), no backtests, research
  runs or data staging, and no interactive shells that compile, build,
  or run project code. All of it runs in the local sandbox / local
  staging fleet or in CI.
- Bridge `run_shell` on a production host is reserved for: (a)
  live-only read-only probes — health, journal, process, and venue
  state that exists only on the host; (b) deploys and deploy
  verification through Fleet CD; (c) production operations that can
  only execute on the host (service control, config and
  credential-file maintenance, on-host data repair).

**Exceptions — production probes that must run on-host** (these measure
something that exists only there; they are operations, not test
execution):

- health/liveness probes and journal reads (read-only, seconds-long);
- venue/account checks executed through a production daemon's own
  environment and credentials (e.g. Stratex broker position/balance
  reconciliation) — via the daemon's own surfaces or a minimal
  read-only check using its env, never a test harness;
- the deploy-time gates that are part of Fleet CD itself (health gate,
  Memora migration and memory-path smoke);
- the fleet's own scheduled production jobs (fleet backup, forward
  scorecard, metrics sync, the OCI capacity allocator) — production
  services, not auxiliary work;
- emergency diagnosis of a live incident: read-only first, time-boxed,
  stopped when the incident closes.

If a task appears to need on-host execution and fits no exception, it
goes to the coordinator, who either finds the local route or records a
one-off exception in `docs/collaboration/ACTIVITY_LOG.md` **before** it
runs.

**Staging-exempt ≠ test-on-host.** The staging exemption below (Memora,
IntelX, Forge, Sentinel, VyralX) exists because those agents connect to
Oracle at startup and cannot boot in the sandbox. Their verification
path is the bridge-probe path — short, read-only production probes
against the live service. The exemption has never meant running their
test suites or codegen batteries on the production host, and it does
not now: the 2026-11-17 Forge codegen battery ran on S1 against exactly
such an agent, and it is the kind of execution this rule prohibits.

**A production service executing its own features is production.** If a
live agent's own code path spawns work (e.g. FRIDAY's task machinery),
that is the service behaving as designed and is governed by its own
resource caps. But *driving* a service to execute test workloads
through its features is test execution and is prohibited. The
distinction is who the work serves: the owner's live use, or a crew's
verification.

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
