# Dependency locks — FRIDAY Universe (TASK-SEN-012, 2026-11-15)

## Why this exists

SEN-002 found the fleet's deployed venv had drifted AHEAD of the repo's
manifests: production was current on every flagged package, but a
manifest-driven rebuild would have silently regressed security fixes
(exact pins and old floors). TASK-SEN-012 reconciled the manifests with
the probed live versions. This document defines the lock discipline that
keeps manifests and rebuilds honest from here on.

## The discipline

- **Manifests are intent.** `requirements.txt` / `pyproject.toml` carry
  floors (and, for Sentinel, exact pins) that must never sit below the
  audited-clean versions. Dependabot watches the manifests.
- **Locks are snapshots.** Each agent carries ONE generated artifact:
  - `<Agent>/requirements.lock` — a full resolver snapshot
    (`pip install --dry-run --ignore-installed --only-binary=:all:`,
    CPython 3.11 target), exact `==` pins for the whole dependency tree.
    A rebuild that must reproduce a known-good set installs with
    `pip install -r requirements.lock`.
  - `<Agent>/requirements.constraints.txt` — issued ONLY where a full
    resolve was not feasible in the build environment. It records the
    amended manifest's direct-dependency floors and is **not** a lock;
    it exists so the gap is explicit rather than silent. The per-agent
    reason is recorded in the TASK-SEN-012 PR.
- **Never hand-edit a lock.** Regenerate after any manifest change:
  `pip install --dry-run --ignore-installed --only-binary=:all: --python-version 3.11 --implementation cp --abi cp311 -r <manifest>`
  and take the `Would install` set as the new snapshot (or run a real
  install into a throwaway venv and `pip freeze`).
- Locks do not replace the manifests and do not pin production by
  themselves; they make a rebuild reproducible and reviewable.

## Per-agent artifacts

| Agent | Source manifest | Artifact | Kind | Detail |
|---|---|---|---|---|
| FRIDAY | FRIDAY/requirements.txt | `FRIDAY/requirements.lock` | full resolver snapshot | 133 pins (cp311-target) |
| Inference | Inference/requirements.txt | `Inference/requirements.lock` | full resolver snapshot | 32 pins (cp311-target) |
| Memora | Memora/requirements.txt | `Memora/requirements.lock` | full resolver snapshot | 52 pins (cp311-target) |
| Stratex | Stratex/requirements.txt | `Stratex/requirements.lock` | full resolver snapshot | 90 pins (cp311-target) |
| Futuris | Futuris/requirements.txt | `Futuris/requirements.lock` | full resolver snapshot | 69 pins (cp311-target) |
| IntelX | IntelX/requirements.txt | `IntelX/requirements.lock` | full resolver snapshot | 41 pins (cp311-target) |
| Forge | Forge/requirements.txt | `Forge/requirements.lock` | full resolver snapshot | 46 pins (cp311-target) |
| Sentinel | Sentinel/requirements.txt | `Sentinel/requirements.lock` | full resolver snapshot | 66 pins (cp311-target) |
| Cortex | Cortex/requirements.txt | `Cortex/requirements.lock` | full resolver snapshot | 58 pins (cp311-target) |
| VyralX | VyralX/pyproject.toml | `VyralX/requirements.lock` | full resolver snapshot | 78 pins (cp311-target) |

Notes:
- **Stratex**: `Stratex/requirements.txt` long referenced a
  `requirements.lock` that did not exist in the repo. That dangling
  reference is now satisfied by the artifact above.
- **VyralX**: its lock was resolved against `Pillow>=13.0,<14.0` — the
  spec PR #347 sets — while `main` still capped Pillow at `<12.0` when
  the lock was generated. The VyralX lock is installable together with
  PR #347's manifest change; SEN-012's Pillow 13.x compatibility verdict
  is in the TASK-SEN-012 PR.
- **Cortex**: the lock covers `Cortex/requirements.txt`; the
  `apps/api` and `apps/worker` requirements files carry the same
  fleet-shared specifications.
- **FRIDAY**: the manifest's `-e .` self-reference is the agent package
  itself and is excluded from resolution and from the lock. chromadb is
  also excluded from the FRIDAY snapshot: TASK-SEN-014 verified it dead
  in production and PR #368 removes it from FRIDAY's manifests entirely,
  so SEN-012 deliberately does not pin it (coordinator steer 2026-11-15).
