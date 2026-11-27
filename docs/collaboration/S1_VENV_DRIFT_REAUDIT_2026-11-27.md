# S1 venv drift re-audit — TASK-REL-063 (sweep, 2026-11-27)

**Task:** TASK-REL-063 — S1 venv drift audit (sweep re-audit of the 2026-11-21 audit).
**Auditor:** Muse 3 (worker Muse, roster `muse_3`). **Audit only — no flips, no installs, nothing restarted.**
**Date:** 2026-11-27 ~03:10–03:35 IST. **Board record:** MERGED / PR #1199 (merge `369d66a1`), owner `muse_3`.
**Claim:** hub #1483 comment 7203932637 (one-line claim, 03:09 IST).

## Bases (verified)

- **Declared side:** main `f312158d`. The S1 union lock
  (`deploy/requirements-server1.lock`, 198 entries) has **zero commits since
  2026-11-21** — byte-identical to the lock the Nov-21 audit used. All six
  current-S1 service manifests (`FRIDAY`, `Inference`, `Memora`, `Stratex`,
  `Forge`, `Sentinel` `requirements.txt`) also have **zero commits since
  2026-11-21**. The declared side is unchanged.
- **Live side:** Server 1 (`10.0.0.121`, host `friday-universe-vnic`),
  collected 2026-11-27 ~03:10–03:30 IST by Muse 3 via the bridge
  `run_shell` (server 1 and server 2, read-only: `pip freeze`, `pip check`,
  `systemctl show`, `ss`, `ps`; nothing written). Grant: standing clearance
  `7200564540`; `run_shell` verified working first-hand this run on both
  servers (`hostname` → `friday-universe-vnic` / `friday-universe-vnic-2`,
  exit 0). Raw probe outputs retained in the auditor's workspace
  (`~/workspace/muse3/task-rel-063/reaudit-2026-11-27/`).

## Finding 1 — Both S1 venvs exist; the 3.12 venv is healthy (UNCHANGED)

- `/opt/friday_universe/venv312` (Python 3.12): **199 `==` packages** (+1
  editable-install line), `pip check`: **"No broken requirements found."**
- `/opt/friday_universe/venv` (Python 3.10, retired, kept for rollback):
  **196 `==` packages** (+1 editable-install line), `pip check`: same 6
  missing for `friday-agent` as Nov 21 (`chromadb`, `duckduckgo-search`,
  `icalendar`, `pygithub`, `pytesseract`, `recurring-ical-events`) —
  expected for a retired venv.
- Counts are identical to Nov 21 (the `wc -l` counts 200/197 include the
  editable-install line each).

## Finding 2 — Live venv312 matches the S1 union lock almost exactly (UNCHANGED)

Scripted diff of the live freeze against the lock on current main:
**live = lock + exactly one package, `sse-starlette==3.4.8`. Zero version
differences; nothing in the lock is missing live.** Identical to Nov 21.
The editable install now tracks current main (`friday_agent` at `7da97be`,
was `11cbe05`).

## Finding 3 — Sentinel is still the only service whose manifest the live venv does not satisfy (UNCHANGED)

Re-evaluated all six manifests against the live freeze with
`packaging` specifier evaluation (Linux, Python 3.12 markers):

| Service | Manifest reqs | Missing live | Version violates manifest |
|---|---|---|---|
| FRIDAY | 27 (+1 editable line) | 0 | 0 |
| Inference | 10 | 0 | 0 |
| Memora | 17 | 0 | 0 |
| Stratex | 23 | 0 | 0 |
| Forge | 15 | 0 | 0 |
| **Sentinel** | **25** | **5** | **7** |

**Sentinel — 5 packages absent from live venv312 (identical to Nov 21):**
`minio==7.2.20`, `reportlab==5.0.1`, `weasyprint==70.0`,
`dnspython==2.9.2`, `dpkt==1.9.8`.

**Sentinel — 7 `==` pins violated by the live versions (identical to Nov 21):**

| Package | Live venv312 | Sentinel manifest |
|---|---|---|
| fastapi | 0.163.1 | ==0.161.1 |
| pydantic | 2.14.3 | ==2.13.4 |
| pydantic-settings | 2.16.3 | ==2.15.0 |
| SQLAlchemy | 2.1.8 | ==2.0.52 |
| oracledb | 26.1.0 | ==2.5.0 |
| alembic | 1.20.1 | ==1.19.1 |
| typer | 0.29.1 | ==0.27.1 |

The Sentinel gap is still lock-vs-manifest, not live-vs-lock: the live venv
faithfully matches the lock, and the lock itself does not satisfy Sentinel's
manifest.

## Finding 4 — The S1 union lock is still stale (UNCHANGED)

Lock header still lists agents `FRIDAY, Inference, Memora, Stratex, Futuris,
IntelX, Forge` — resolved at `origin/main 9def8a7a`, before the 6/4
migration. **Sentinel** (moved to S1) is not in it; **Futuris / IntelX**
(moved to S2) still are. The Nov-21 recommendation to regenerate the lock
is still open.

## Finding 5 — Unit repoints: four services moved to venv312 since Nov 21 (CHANGED)

Live `systemctl show` per unit (ExecStart interpreter + ActiveState +
UnitFileState), 2026-11-27 ~03:15 IST:

| Unit | ExecStart interpreter | ActiveState | UnitFileState |
|---|---|---|---|
| `FRIDAY.service` | `/opt/friday_universe/venv/bin/python` (retired 3.10) | inactive | disabled |
| `Inference.service` | `/opt/friday_universe/venv312/bin/python` | inactive | disabled |
| `Memora.service` | `/opt/friday_universe/venv312/bin/python` | active | enabled |
| `Sentinel.service` | `/opt/friday_universe/venv312/bin/python` | active | enabled |
| `Forge.service` | `/opt/friday_universe/venv312/bin/python` | active | enabled |
| `Stratex.service` | `/opt/friday_universe/venv/bin/python` (retired 3.10) | inactive | disabled |
| `Stratex-Daemon.service` | `/opt/friday_universe/venv/bin/python` (retired 3.10) | **failed** | disabled |
| `FRIDAY-Voice.service` | `/opt/friday_universe/venv/bin/python` (retired 3.10) | inactive | disabled |

Changes vs Nov 21: **Inference, Memora, Sentinel, Forge have been
repointed to venv312** (their live interpreters were unverified in the
Nov-21 probe). Memora, Sentinel and Forge are active on venv312; Inference
is repointed but inactive/disabled. FRIDAY, Stratex, Stratex-Daemon and
FRIDAY-Voice still execute on the retired 3.10 venv. FRIDAY-Voice went
from enabled (Nov 21) to **disabled + inactive**. Stratex-Daemon is
**failed** (disabled). `Futuris` / `IntelX` / `Stratex-Testnet` remain
**masked** on S1 (expected after the 6/4 move).

## Finding 6 — What is actually running on venv312 on S1 (NEW)

Live processes and listeners on S1 at probe time:

- Uvicorn on venv312: Memora (`:8002`, pid 1199110), Forge (`:8006`, pid
  1199140), Sentinel (`:8008`, pid 1199210), Cortex API
  (`apps.api.src.cortex_api.main:app`, pid 3771939).
- **No FRIDAY uvicorn process and no `:10000` listener on S1.** `:8001`
  on S1 is an SSH tunnel (pid 3678724, `ssh`), not Inference.
- Same check on Server 2: no FRIDAY uvicorn / livekit-worker / daemon
  process, no `:10000` or `:8001` listener; `FRIDAY.service` inactive
  there with no unit file.
- This audit does **not** conclude on FRIDAY's runtime location: the
  serving path was not established by these probes. **Flagged for Muse:**
  FRIDAY's API was not observed running on either server at probe time.

## Finding 7 — Sentinel serves live on venv312 despite the unresolved gaps (NEW)

Sentinel is active, enabled, listening on `:8008` (pid 1199210) on
venv312 — the Nov-21 "NOT READY" verdict (5 missing + 7 pin violations)
was overtaken by the repoint. It serves in practice on the violating
versions; the manifest gaps in Finding 3 remain unresolved and are now
more urgent, not less.

## Flip-readiness per service (updated)

- **Memora, Forge — FLIPPED and running on venv312.** Packages satisfied,
  units repointed, processes live.
- **Inference — REPOINTED, not running.** Unit points at venv312 but is
  inactive/disabled; `:8001` is served via an SSH tunnel, not the unit.
- **Sentinel — FLIPPED and running on venv312 despite NOT READY on
  packages.** The 5-missing/7-pin gaps stand; monitor for runtime failures
  on the load-bearing pins.
- **FRIDAY, Stratex, Stratex-Daemon, FRIDAY-Voice — NOT FLIPPED.** Still
  on the retired 3.10 venv; FRIDAY-Voice disabled, Stratex-Daemon failed.
  Their repoint is a server move frozen under the owner stop order
  (hub 7130069033) — no action taken here.

## Recommendations (for Muse — no action taken in this audit)

1. **Regenerate the S1 union lock** from the current-S1 manifests (drop
   Futuris/IntelX, add Sentinel, add `sse-starlette==3.4.8`); fix the stale
   header. (Carried from Nov 21, still open.)
2. **Decide Sentinel's pins** (align manifest to lock versions, or install
   pinned versions + the 5 missing packages into venv312), then re-run
   `pip check` and Sentinel's tests on venv312. Now urgent: Sentinel
   serves live on the violating versions.
3. **FRIDAY / Stratex / Daemon / Voice repoints** remain blocked by the
   owner stop order — no action until hub clearance.
4. **Check in `FRIDAY-Voice.service`** (and the other S1 units missing
   from the repo) so declared unit state matches live. (Carried from
   Nov 21, still open.)
5. **Muse: say where FRIDAY's API runs now**, and whether
   Stratex-Daemon's `failed` state and the disabled FRIDAY/Inference
   units are intended (fleet move) or a regression to repair.
6. Stale failed one-shot units observed on S1 (not chased — out of scope):
   `friday-voice-drill8`, `friday-wf015-*` acceptance units,
   `friday-deploy-watchdog-report`, `friday-forge-reverification-wf006`.

## Method and reproducibility

- Declared side: `git show origin/main:<manifest>` for all six manifests
  and the lock; `git log --since 2026-11-21` confirms zero commits to any
  of them. Scripted parse with `packaging` (canonicalized names,
  specifier evaluation, Python 3.12 markers).
- Live side: bridge `run_shell` (server 1: `pip freeze`, `pip check`,
  `systemctl show -p ExecStart,ActiveState,UnitFileState`,
  `systemctl list-unit-files`, `ss -ltnp`, `ps aux`; server 2: same
  FRIDAY checks). Read-only throughout.
- Full live freeze (199 `==` packages + editable line) and unit outputs
  retained in the auditor's workspace
  (`~/workspace/muse3/task-rel-063/reaudit-2026-11-27/`).

— Muse 3
