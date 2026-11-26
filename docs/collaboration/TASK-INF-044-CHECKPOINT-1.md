# TASK-INF-044 — Checkpoint 1: scoping (repo leg)

Date: 2026-11-26 ~18:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing
receipts, per-class fallback rate + deadline compliance (P1).
Assignment: coordinator WATCH156 re-slot (hub 7190339092); claimed 2026-11-26
~17:17 IST (hub 7191170240). Branch: `muse5/task-inf-044-routing-audit`
from main `992cf3b2`.

## What INF-022 built (verified first-hand on main `087e05d6`)

- INF-022 MERGED (PR #1386, Muse 7, 2026-11-22). Board record on main
  `087e05d6`: status MERGED, owner muse_7, pr 1386.
- `Inference/app/providers/gateway.py`: every `execute()` records a routing
  receipt (task class / capability, requested vs served provider/model,
  latency, deadline class, fallback use + direct flag, timeout budget,
  prompt-token estimate) in a bounded in-memory ring — **last 100,
  process-local, no persistence** (`record_routing_receipt`,
  `routing_receipts(limit)`, `routing_receipt_counts()` — read first-hand).
- `Inference/app/health.py`: `/status` gains a `routing` section
  (deadline classes, receipt counts, recent receipts).
- Deadline classes: short <= 7,000 calibrated tokens; large above
  (Groq-guard limit). Large Gemini primaries with no explicit caller
  timeout route DIRECTLY to the fallback ladder (no primary attempt).
- `Inference/tests/test_inf022_routing_receipts.py`: 8 tests (class
  boundaries, INF-019 shape, direct routing, explicit-timeout opt-out,
  primary + error receipts, store cap/counts) — passed 8/8 in the INF-022
  evidence (Server 2, 2026-11-22).

## Scoping findings (this run)

1. **Receipts do not persist.** The ring holds the last 100 only, in the
   serving process. A one-week audit therefore needs repeated live
   `/status` reads (or a collector) over the week — a single end-of-week
   read cannot recover a week of receipts. Read cadence is a live-leg
   design question, not a repo-leg one.
2. **The deployed service may not serve receipts yet.** The INF-022
   evidence (2026-11-22) states the deployed S1 service's `/status` did
   NOT show the `routing` section (old code); deployment was a separate
   step for the coordinator. Whether it has since been deployed is
   unverified — first live-leg question.
3. **`gateway.py` moved twice after INF-022.** Last commits touching it:
   `e020d882` TASK-INF-038 (needle fast-path router, 2026-11-25),
   `dc201f5b` TASK-INF-030 (APInex gateway as fallback provider,
   2026-11-24). The test file is unchanged since INF-022 (`ca2587cd`).
   The audit must confirm the receipts still record the same fields and
   the deadline-class routing still holds on current main — a repo-leg
   re-run of the 8 INF-022 tests on current main is owed in checkpoint 2
   before any live numbers are trusted.
4. **Live leg gated.** Owner stop order (~Nov 24 16:42 IST) still in force;
   live gate CLOSED (WATCH160/161). No INF-044 clearance in any watch
   through WATCH161. No live move, no probe, no dispatch this run.

## Clearance requested from Muse (carried)

- Read-only Inference `/status` receipt harvest over one week (read
  cadence to be set once the deployed code state is confirmed), plus
  confirmation whether the deployed S1 Inference service runs the
  INF-022 code. No restarts, no deploys, no env flips, no key reads.

## Five states (honest)

- Implemented: no (scoping only). Tested: no. Merged: no. Deployed: no.
  Production-verified: no.

— Muse 5
