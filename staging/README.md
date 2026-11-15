# FRIDAY Universe — Local Staging Fleet (TASK-REL-046)

A local replica of the 10-agent fleet that runs **on Muse's side** (the
development sandbox), so agent changes are built, booted and smoke-tested
locally and only proven work is pushed to the Oracle VMs. This implements
the owner's local-first direction (2026-11-15): the Oracle servers and
their bridge are the bottleneck; the bridge is reserved for what can never
be staged (see `docs/collaboration/LOCAL_FIRST_PIPELINE.md`).

## Quick start

```bash
# one-time setup (Python 3.12 in the Muse sandbox; production is 3.10 —
# see "Environment deltas" below)
python3 -m venv --system-site-packages staging/.venv
staging/.venv/bin/pip install -r staging/requirements-staging.txt

# THE GATE — boot the fleet, health + one read-only probe per agent,
# pass/fail table, teardown. Exit 0 only if every non-exempt agent passes.
staging/.venv/bin/python staging/smoke_gate.py

# or run the fleet interactively:
staging/.venv/bin/python staging/staging_fleet.py start   # detached + watchdog
staging/.venv/bin/python staging/staging_fleet.py status
staging/.venv/bin/python staging/staging_fleet.py stop
```

State and logs land in `staging/run/` (gitignored): per-agent logs in
`run/logs/`, the machine-readable gate report in `run/smoke_report.json`,
watchdog cap-kill flags in `run/oom_<Agent>.flag`.

## What the fleet is

`staging/fleet_manifest.yaml` is the single source of truth. Per agent it
pins: the **production boot recipe** (same module/command and PYTHONPATH
shape as `deploy/setup_fleet.sh`, including the repo root, which carries
the shared `mesh` package), the production port, the **production memory
cap** from AGENTS.yaml v3.0.0 (FRIDAY 200M, Inference 180M, Memora 200M,
Stratex 180M, Futuris 180M, IntelX 180M, Forge 180M, Sentinel 200M,
Cortex 200M, VyralX 250M), a health path and one representative read-only
probe path.

Rules that are never relaxed:

- **Dummy credentials only.** Every key in the manifest is a literal
  `staging-dummy-…` placeholder. Production secrets are never copied into
  the sandbox. Inter-agent URLs point at the staging ports on 127.0.0.1.
- **Trading never runs.** Only Stratex's `dashboard.py` is started (that
  is all production's systemd unit runs); the trading bot/daemon is never
  started in staging, and the manifest pins `STRATEX_TRADING_ENABLED=false`.
- **Uploads/publishing are disabled** for VyralX in staging.
- The Stratex paper-runner supervisor thread inside `dashboard.py` does
  start with the dashboard (observed 2026-11-15); it trades nothing in
  staging (no real keys, trading flags false) but it does write heartbeat
  files — noted here so nobody is surprised by it.

## How the caps work (and their limits)

Production enforces memory with systemd `MemoryMax` (cgroup). Staging has
no cgroups, so `staging_fleet.py`'s watchdog polls each agent's process
**tree RSS** (sum of `VmRSS` over the process and its descendants, from
`/proc`) every 2 s and SIGTERMs the tree after **2 consecutive polls**
over the cap, recording `run/oom_<Agent>.flag`. Differences that matter:

- VmRSS counts shared library pages in every process that maps them;
  a cgroup charges them once. Staging numbers are therefore a few percent
  pessimistic versus production accounting.
- A sub-2-second spike can pass between polls; a sustained excess cannot.
- Production VMs carry 8 GiB of swap, so a production process near its
  cap swaps before it dies; staging has no such cushion. The staging
  watchdog is, if anything, stricter than production — a staging OOM-kill
  is a "look here first" signal, not proof the same change dies in
  production. The reverse does not hold: passing staging does not prove
  production headroom either (see "Environment deltas").

## The two boot classes (measured 2026-11-15)

The fleet splits in two, and the split is architectural, not a staging
defect:

- **Lazy-database agents boot degraded and are fully gated** — Inference,
  Futuris, Cortex, FRIDAY (and Stratex's dashboard). Their Oracle pools
  are lazy: pointed at the dummy DSN (`oracle+oracledb://staging_dummy:…@
  127.0.0.1:1521`, dead port) they log connection warnings and serve.
  Database-backed paths fail honestly against the dummy, exactly like a
  production DB outage.
- **Eager-database agents are staging-exempt** — Memora, IntelX, Forge,
  Sentinel, VyralX. Each connects to Oracle *during application startup*
  and aborts when it is unreachable (SQLAlchemy/oracledb `DPY-6005`,
  "Application startup failed"). Memora's refusal is explicit in its own
  message: it will not open a local SQLite fallback. There is no Oracle
  instance in the Muse sandbox, so these five cannot boot here at all.
  They are declared `staging_exempt` in the manifest with the reason, are
  reported as **EXEMPT — never as passes**, and their changes still need a
  production-side probe via the bridge until a local Oracle exists (or
  the agents gain a lazy-boot mode — a code decision for their owners,
  not something staging fakes around).

The whole fleet is Oracle-only by design (repo AGENTS.md: Oracle
Autonomous Database is the only supported backend; SQLite/PostgreSQL are
deliberately not selectable). A local Oracle was considered and rejected
for this sandbox: no container runtime, a multi-GB database image, and
~1–1.5 GB of free RAM shared with every other crew.

## Gate verdicts

| Verdict | Meaning |
|---|---|
| PASS | Process alive under its cap, health = HTTP 200, probe answered HTTP < 500 (actual code and RSS printed) |
| OOM-KILLED | Watchdog killed the tree for sustained RSS over the production cap |
| BOOT-FAIL | Process exited during boot (exit code + captured log tail printed) |
| FAIL | Health or probe failed on a live process |
| EXEMPT | Declared staging-exempt in the manifest, with the reason printed |

Safety rails built into the gate: a **pre-flight port check** refuses to
run if any staging port is already bound (a leftover process answering in
a new child's place produced a false PASS during development — the gate
never kills processes it did not spawn); a **post-probe liveness
re-check** fails any agent whose process died after answering health;
**teardown verification** warns if any port is still bound at the end.
Child output is captured through pipes with an in-memory tail, because
this sandbox's overlay filesystem intermittently drops file writes —
the gate's evidence never depends on a log file having survived.

## Environment deltas (staging ≠ production, stated plainly)

- Python 3.12 (sandbox) vs 3.10 (production venv); library builds differ
  (sandbox uses `--system-site-packages`). Absolute RSS numbers are
  staging-environment measurements: on 2026-11-15 Stratex measured
  ~199 MB steady / 234 MB peak and Futuris ~194 MB against their 180 MB
  caps, while both run within caps in production. Treat an over-cap
  staging result as "footprint risk — investigate", with the version
  delta as the first suspect, not as proof of a production breach.
- The sandbox exports a `NO_PROXY` containing bracketed IPv6 literals
  that crash httpx's proxy-pattern parser at client construction
  (`httpx.InvalidURL: Invalid port ':1]'`). The manifest sanitises
  `NO_PROXY` to `localhost,127.0.0.1` for staging agents only.
- One shared sandbox VM (~1.5 CPU / ~6 GB for *all* crews): the gate
  boots agents **sequentially** (one import peak at a time) and probes
  them concurrently. Local-first relieves Oracle; it is not infinite
  capacity either.

## Files

- `fleet_manifest.yaml` — recipes, caps, health/probe paths, dummy env, exemptions
- `staging_fleet.py` — start/stop/status + watchdog + in-process spawn/cap helpers
- `smoke_gate.py` — the pre-merge gate (see `docs/collaboration/LOCAL_FIRST_PIPELINE.md`)
- `requirements-staging.txt` — the staging venv package set (mirrors the production shared venv)
- `RESULTS_REL046.md` — the first full gate run, with the real output table
