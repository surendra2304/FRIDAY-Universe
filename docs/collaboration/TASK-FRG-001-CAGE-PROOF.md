# TASK-FRG-001 — Cage proof, checkpoint 1 (code)

**Task:** Forge: prove the FRG-017 idle loop is deployed and cycling (or
switch it on) inside a hard resource cage + ship the first tool
another agent is blocked on.
**Branch:** `muse6/task-frg-001-idle-loop-proof`
**Status:** CLAIMED — checkpoint 1 (cage + driver + proof, validated in
sandbox). The live S1 cycle and the blocked-agent tool half are still
open; see "Still owed" below. Nothing here claims FRG-001 complete.

## What shipped (checkpoint 1)

| File | What it is |
| --- | --- |
| `Forge/app/deployment/forge-idle-loop-cage.service` | Separate transient one-shot unit for the idle loop only. Never enabled (no `[Install]` section); start on demand. |
| `Forge/scripts/frg001_idle_cycle_once.py` | One-shot driver: runs exactly one cycle through the loop's own entry point (`IdleExperimentLoop.start_if_enabled`) and prints the cycle report as JSON. Refuses (exit 2) unless `FORGE_IDLE_EXPERIMENTS` is explicitly `on`. `--sandbox` runs with an empty task store, a stubbed lesson writer (deliveries stay pending in the local ledger, never claimed), and a temp data dir — no production DB, no Memora call. |
| `Forge/scripts/frg001_cage_proof.py` | Static proof, stdlib only: 27 hard checks on the two unit files and the loop's gates. `systemd-analyze verify` runs as information only (see below). |
| `Forge/tests/test_frg001_cage.py` | 7 tests pinning the cage contract (tighter MemoryMax, bounded CPUQuota, driver-only ExecStart, loop armed only in the cage, hardening, gate functions, driver refusal). |

## Cage vs production

| | Production `forge.service` | Cage `forge-idle-loop-cage.service` |
| --- | --- | --- |
| Runs | uvicorn `app.main:app` :8006, always-on | One-shot cycle driver, on demand only |
| MemoryMax | 180M | **128M** |
| MemoryHigh | 150M | 96M |
| CPUQuota | none | **25%** |
| TasksMax | unset | 64 |
| `FORGE_IDLE_EXPERIMENTS` | not set (loop default off) | `on` (only place the loop is armed) |
| Hardening | — | PrivateTmp, ProtectSystem=strict, ProtectHome, NoNewPrivileges, ReadWritePaths=`/opt/friday_universe/Forge/data` only |

Server 1 carries seven agents in ~956 MB RAM; the battery spawns
pytest subprocesses, so the cage is tighter than production on purpose.

## Validation done this run (sandbox, this VM — not the production host, per D-029)

- **Proof script:** `python3 Forge/scripts/frg001_cage_proof.py` →
  **27/27 hard checks PASS, exit 0.** `systemd-analyze verify` exit 1
  with exactly one cage-relevant finding: the cage's
  `/opt/friday_universe/venv312/bin/python` does not exist on this VM
  (it exists on Server 1); the other verify lines are this VM's own
  timer noise. Verify is informational here, not a gate.
- **Tests:** `pytest tests/test_frg001_cage.py
  tests/test_frg017_idle_experiments.py tests/test_frg017_wiring_gates.py`
  → **49 passed in 3.51s** (7 new cage + 14 idle-experiment + 28
  wiring-gate). Forge requirements installed into a scratch venv for
  the run; the FRG-017 suites pass on current main `23afe6ba`.
- **Sandbox cycle:** `FORGE_IDLE_EXPERIMENTS=on python
  scripts/frg001_idle_cycle_once.py --sandbox` → the cycle was
  **refused by the C2 host-load gate, correctly**: memory available
  fraction 0.072 is below the 0.150 gate (this VM: MemAvailable
  678,676 KB / MemTotal 8,124,900 KB at run time). Exit 1, JSON
  report `status: skipped, reason: host_load_gate`. The driver, the
  flag gate, the load probe, and the refusal path all work end to
  end; the refusal itself is the gate doing its job on a
  memory-pressured host. No ledger row was written (refusals before
  the idle gate write none — by design; the refusal is in the log
  and in the driver's JSON output).

## LiveKit probe-caller question (FRG-001 analysis conclusion)

Checked in-repo: there is **no self-service LiveKit probe caller** —
`FRIDAY/src/friday/voice/livekit_worker.py` holds only the worker's
own internal key probes and greeting-path probe, and Muse 13
confirmed the same from the VOI-030 side (no self-service probe
caller in repo). The tool is missing, so per the FRG-001 analysis
note the ship vehicle is **TASK-FRG-020** (pool, P2), not FRG-001.

## Still owed

1. **Live S1 cycle:** install the cage unit on Server 1, start it in
   a low-memory-pressure window, file the ledger timestamps. This VM
   has no bridge/SSH path to the servers, so the live leg needs a
   server path (coordinator direction). **Warning, measured:** S1 is
   at 90.5–91.2% RAM with ~71 MB free (Muse 7 first-hand probe,
   2026-11-23 ~21:36 IST) — the C2 gate will refuse cycles there too
   until memory pressure eases. A live cycle needs a low-pressure
   window, not just a start command.
2. **Blocked-agent tool half:** FRG-001's acceptance needs one named
   blocked-agent tool shipped and used by that agent. The probe
   caller now belongs to FRG-020. Coordinator to name FRG-001's tool
   (or confirm the cage + cycle leg is FRG-001's code leg and the
   tool half rides elsewhere).
