# TASK-REL-046 — Results: local staging fleet + smoke gate, first runs

Date: 2026-11-15. Environment: Muse sandbox (Python 3.12 venv,
`--system-site-packages`), repo main `56e28e6342c6dc5aa45ddd0acefeba557011b393`.
Claim: issue #35 comment 6892676297. Branch: `claude/task-rel-046-local-staging`.

## The proof run (verbatim output, cap enforcement live throughout)

```
AGENT       PORT   CAP    RSS   BOOT HEALTH  PROBE                                  VERDICT
----------------------------------------------------------------------------------------------------------------------
Inference   8001  180M   108M   6.1s    200  /v1/models -> 200 (158ms)              PASS
Memora      8002  200M      —      —      —                                         EXEMPT  [requires a reachable Oracle Autonomous DB at startup (eager engine creation, fails closed, no local fallback by design); no Oracle instance exists in the Muse sandbox]
Stratex     8003  180M      —  12.0s    200                                         OOM-KILLED
Futuris     8004  180M      —   8.4s    200  /openapi.json -> None (2ms)            OOM-KILLED
IntelX      8005  180M      —      —      —                                         EXEMPT  [connects to Oracle during application startup and aborts when unreachable (DPY-6005); no Oracle instance exists in the Muse sandbox]
Forge       8006  180M      —      —      —                                         EXEMPT  [connects to Oracle during application startup and aborts when unreachable (DPY-6005); no Oracle instance exists in the Muse sandbox]
Sentinel    8008  200M      —      —      —                                         EXEMPT  [connects to Oracle during application startup and aborts when unreachable (DPY-6005); no Oracle instance exists in the Muse sandbox]
Cortex      8009  200M   124M   6.7s    200  /openapi.json -> 200 (592ms)           PASS
VyralX      8010  250M      —      —      —                                         EXEMPT  [connects to Oracle during application startup and aborts when unreachable (DPY-6005); no Oracle instance exists in the Muse sandbox]
FRIDAY     10000  200M   189M  14.0s    200  /api/tools -> 200 (10ms)               PASS
----------------------------------------------------------------------------------------------------------------------
SMOKE GATE: 3 PASS, 2 FAIL, 5 EXEMPT of 10 agents   (gate exit code 1)
```

**Headline, without softening: the gate works and the fleet is RED
against it today** — 3 PASS, 2 over-cap kills, 5 staging-exempt. The gate
exiting 1 is the correct result: it exists to catch exactly the two
footprint findings below, and the five exemptions are an architectural
fact about the fleet, now measured instead of assumed.

## Per-agent findings

- **Inference — PASS.** 108 MB of its 180 MB cap; health 200 in 6.1 s;
  `/v1/models` 200. Boots degraded against the dummy Oracle DSN (lazy
  pool; schema-init warnings logged, service up).
- **FRIDAY — PASS.** 189 MB of 200 MB — inside, but with the same thin
  margin production shows (FRIDAY.service runs at 199.9M/200M there).
  Health `/api/health` 200; `/api/tools` 200.
- **Cortex — PASS.** 125 MB of 200 MB; health and probe 200.
- **Stratex — OOM-KILLED (footprint finding).** The dashboard boots and
  answers `/api/v1/health` 200, but its RSS in this environment peaks at
  **234 MB** during boot and settles at **~199 MB** — over its 180 MB
  production cap the whole time (dedicated RSS-curve diagnostic, 2 s
  samples over 110 s). The watchdog killed it after health, before the
  probe. Production runs Stratex within cap on Python 3.10; the staging
  delta (3.12 + different library builds) is the first suspect, but the
  footprint risk is real and now visible *before* any Oracle deploy.
  Also observed: `dashboard.py` starts a paper-runner supervisor thread
  (heartbeat writes) even with trading flags false.
- **Futuris — OOM-KILLED (footprint finding).** Boots, health 200 at
  8.4 s, but measures **~194 MB** steady (194 MB and 196 MB in two runs)
  against its 180 MB cap; in the full run it was killed during the probe
  phase after sustained over-cap polls. Same environment caveat as
  Stratex. (In its solo run it completed the probe inside the watchdog's
  2-poll grace and read PASS at 196 MB — the fleet run's longer window
  is the stricter and more truthful measurement, and it is the one
  reported here.)
- **Memora, IntelX, Forge, Sentinel, VyralX — EXEMPT.** All five connect
  to Oracle *during startup* and abort when it is unreachable
  (oracledb `DPY-6005` → "Application startup failed"; Memora exit 3
  with "refusing to open a local SQLite fallback", VyralX exit 1).
  Sentinel additionally refuses to boot without an audit signing key —
  staging supplies a dummy, after which it reaches the same Oracle wall.
  No Oracle instance exists in this sandbox (no container runtime,
  multi-GB image, ~1–1.5 GB free RAM), so these agents cannot boot here
  today. Their changes keep the bridge-probe path until a local Oracle
  or a lazy-boot mode exists. Exempt means *not gated*, never *passed*.

## Method notes (what it took to make the gate trustworthy)

- Every agent was first shaken out solo through the gate; only then was
  the full run made. Two full runs were made: the first printed
  "5 PASS, exit 0" but is **invalid and is not the proof** — a race
  (main thread adding to the process dict while the watchdog iterated
  it) crashed the watchdog thread seconds in, so cap enforcement was
  dead while Stratex "passed" at 225 MB. The race is fixed (snapshot
  iteration + a watchdog that logs and continues on error) and the
  second run above is the real one. A false green was caught by reading
  the run's own stderr, which is why this paragraph exists.
- A leftover staging process on a port produced a false PASS during
  development (health answered by the old process in the new child's
  place). The gate now refuses to run when a staging port is already
  bound, re-checks liveness after each probe, and verifies teardown.
- The sandbox's overlay filesystem intermittently drops file writes
  (EPERM / silent 0-byte files), which hid one child's entire startup
  traceback when output went straight to a file. Child output is now
  pipe-captured with an in-memory tail; the gate's verdicts never
  depend on a file having survived.
- Fixes the shake-out required, all in staging config (no agent code
  changed): dummy `DATABASE_URL` for the Oracle-only fleet; sanitised
  `NO_PROXY` (sandbox value crashes httpx); PYTHONPATH mirroring
  production (`<agent>:<repo root>` — the root carries the shared
  `mesh` package Futuris and others import); FRIDAY's second src root
  (`FRIDAY/apps/core/src`); Stratex's real health path
  (`/api/v1/health`); dummy Sentinel audit signing keys.

## What this does and does not prove

Proves: the staging fleet boots the gate-able agents from a clean repo
tree with production recipes and production caps, dummy credentials
only; the gate enforces caps, health and a read-only probe per agent,
and produces a truthful pass/fail/exempt table in ~60 s. Does not
prove: production behaviour (different Python, real Oracle, real keys),
anything about the five exempt agents, or any agent's behaviour under
real load. The pipeline rule that follows from this is in
`docs/collaboration/LOCAL_FIRST_PIPELINE.md`.
