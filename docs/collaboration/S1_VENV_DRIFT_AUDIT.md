# S1 venv drift audit — TASK-REL-063

**Task:** TASK-REL-063 — S1 venv drift audit ahead of the remaining Python 3.12 flips.
**Auditor:** Muse 3 (worker Muse, roster `muse_3`). **Audit only — no flips, no installs.**
**Date:** 2026-11-21. **Board record:** CLAIMED, branch `muse3/task-rel-063-s1-venv-drift-audit`, claim PR #1198 merged (53c1b46b).

## Bases (verified)

- **Declared side:** main `11cbe05` — S1 union lock `deploy/requirements-server1.lock`
  (198 entries) and the six current-S1 service manifests (`FRIDAY`, `Inference`,
  `Memora`, `Stratex`, `Forge`, `Sentinel` `requirements.txt`). Re-verified
  2026-11-21 ~15:05 IST: the lock is byte-identical on current main `53c1b46b`,
  and all six manifests are byte-identical by blob sha — so the declared side
  below holds on current main.
- **Live side:** Server 1 (`10.0.0.121`, host `friday-universe-vnic`), collected
  2026-11-21 ~14:50 IST by Muse (Head Manager) via S2 bridge `run_shell` →
  SSH to S1, read-only (`pip freeze`, `pip check`, `ls`, `systemctl cat`;
  nothing written). Full live data: issue #35 comment 7060448797 (both freezes
  and the three unit files in full). The auditor's bridge client cannot run
  `run_shell` and the bridge host is S2, so no live S1 collection was possible
  from the auditor side; the ruling was requested in issue #35 comment
  7060386031 and granted in 7060448797.

## Finding 1 — The two S1 venvs exist; the 3.12 venv is healthy

- `/opt/friday_universe/venv312` (Python 3.12): **199 packages**, `pip check`:
  **"No broken requirements found."**
- `/opt/friday_universe/venv` (Python 3.10, retired, kept for rollback): **196
  packages**, `pip check`: 6 missing for `friday-agent` (`chromadb`,
  `duckduckgo-search`, `icalendar`, `pygithub`, `pytesseract`,
  `recurring-ical-events`) — expected for a retired venv.

## Finding 2 — Live venv312 matches the S1 union lock almost exactly

Live `venv312` vs the lock: **live = lock + exactly one package**,
`sse-starlette==3.4.8`. Zero version differences; nothing in the lock is
missing live.

Correction to the ruling's parenthetical: `beautifulsoup4==4.15.0` and
`prometheus_client==0.26.0` **are** in the lock at the live versions — only
`sse-starlette` is omitted from the lock. (Verified by direct grep of the lock
and by the scripted diff.)

## Finding 3 — Sentinel is the only service whose manifest the live venv does not satisfy

| Service | Manifest reqs | Missing live | Version violates manifest |
|---|---|---|---|
| FRIDAY | 28 | 0* | 0 |
| Inference | 10 | 0 | 0 |
| Memora | 17 | 0 | 0 |
| Stratex | 23 | 0 | 0 |
| Forge | 15 | 0 | 0 |
| **Sentinel** | **25** | **5** | **7** |

\* FRIDAY's `requirements.txt` line 43 is `-e .` (editable install directive,
not a package) — the parser flags it unparseable; the editable install **is**
present live (`-e git+https://github.com/surendra2304/FRIDAY-Universe.git@11cbe05…#egg=friday_agent&subdirectory=FRIDAY`).

**Sentinel — 5 packages absent from live venv312:**

- `minio==7.2.20`, `reportlab==5.0.1`, `weasyprint==70.0`,
  `dnspython==2.9.2`, `dpkt==1.9.8`

**Sentinel — 7 `==` pins violated by the live versions:**

| Package | Live venv312 | Sentinel manifest |
|---|---|---|
| fastapi | 0.163.1 | ==0.161.1 |
| pydantic | 2.14.3 | ==2.13.4 |
| pydantic-settings | 2.16.3 | ==2.15.0 |
| SQLAlchemy | 2.1.8 | ==2.0.52 |
| oracledb | 26.1.0 | ==2.5.0 |
| alembic | 1.20.1 | ==1.19.1 |
| typer | 0.29.1 | ==0.27.1 |

These are the **same 12 gaps** the declared-side check found (lock vs
manifest). The Sentinel gap is lock-vs-manifest, **not** live-vs-lock: the
live venv faithfully matches the lock, and the lock itself does not satisfy
Sentinel's manifest.

## Finding 4 — The S1 union lock is stale (pre-migration)

- Lock header still lists agents `FRIDAY, Inference, Memora, Stratex, Futuris,
  IntelX, Forge` — resolved at `origin/main 9def8a7a`, before the 6/4
  migration. **Sentinel** (moved to S1 in REL-062) is not in it; **Futuris /
  IntelX** (moved to S2) still are.
- **141 lock entries** are not required by any current-S1 manifest — mostly
  transitive deps, plus the moved Futuris/IntelX direct set (`statsforecast`
  2.1.1, `coreforecast`, `utilsforecast`, `formulaic`, `fugue`, `patsy`,
  `triad`, …), plus dev tools (`pytest`, `ruff`, `twine`) and
  `nvidia-nccl-cu13` (documented deliberate keep).

## Finding 5 — The 3.12 venv is installed but not yet serving: units still point at the retired venv

Live `systemctl cat` (from the ruling):

| Unit | Live state | ExecStart interpreter |
|---|---|---|
| `Stratex-Daemon.service` | enabled | `/opt/friday_universe/venv/bin/python` (retired 3.10) |
| `FRIDAY-Voice.service` | enabled | `/opt/friday_universe/venv/bin/python` (retired 3.10) |
| `Stratex.service` | enabled | `/opt/friday_universe/venv/bin/python` (retired 3.10) |

- `FRIDAY-Voice.service` **exists and is enabled live** — it is only missing
  from the repo, not from S1.
- The checked-in unit files agree: `deploy/Stratex-Daemon.service`,
  `Stratex/deployment/friday-stratex.service`, and
  `Forge/app/deployment/forge.service` all `ExecStart
  /opt/friday_universe/venv/bin/python` (retired venv).
- `Futuris` / `IntelX` / `Stratex-Testnet` are **masked** on S1 (expected
  after the 6/4 move).

**Not verified live:** the `ExecStart` interpreters for `FRIDAY`,
`Inference`, `Memora`, `Sentinel`, and `Forge` units were listed as enabled
but not catted in this probe. No checked-in unit files exist for FRIDAY,
Inference, Memora, Sentinel, or FRIDAY-Voice.

## Flip-readiness per service

- **FRIDAY, Inference, Memora, Stratex, Forge — READY on packages:** their
  manifests are fully satisfied by live venv312, and venv312 passes
  `pip check`. Their flip is blocked only by the unit repointing (Finding 5),
  not by packages. (For FRIDAY, Inference, Memora, Sentinel, Forge the live
  unit interpreter is still unverified — see above.)
- **Sentinel — NOT READY:** 5 missing packages + 7 pin violations (Finding 3).
  Repointing Sentinel's unit to venv312 before resolving these risks runtime
  failures if the `==` pins are load-bearing. Resolve first: either install
  the pinned versions / missing packages into venv312, or relax Sentinel's
  manifest to the lock's versions and re-verify.
- **Stratex-Daemon / FRIDAY-Voice / Stratex units — NOT FLIPPED:** still
  executing on the retired 3.10 venv today. The 3.12 venv exists and is
  healthy, but no service has been observed running on it yet.

## Recommendations (for Muse — no action taken in this audit)

1. **Regenerate the S1 union lock** from the current-S1 manifests (drop
   Futuris/IntelX, add Sentinel, add `sse-starlette==3.4.8`); fix the stale
   header.
2. **Decide Sentinel's pins** (align manifest to lock versions, or install
   pinned versions + the 5 missing packages into venv312), then re-run
   `pip check` and Sentinel's tests on venv312.
3. **Repoint units to venv312** only after (2), service by service, starting
   with the package-ready ones; keep the retired venv for rollback.
4. **Check in `FRIDAY-Voice.service`** (and the other S1 units missing from
   the repo) so declared unit state matches live.
5. **Verify the remaining live unit interpreters** (FRIDAY, Inference,
   Memora, Sentinel, Forge) with a follow-up `systemctl cat` probe.

## Method and reproducibility

- Declared-side comparison: scripted parse of the lock and manifests with
  `packaging` specifier evaluation (Linux, Python 3.12 markers).
- Live-vs-declared comparison: same parser applied to the live freezes
  transcribed verbatim from the ruling comment (counts verified: 199 and 196
  `==` lines, plus one editable-install line each).
- Evidence retained in the auditor's workspace
  (`~/workspace/muse3/task-rel-063/`, `live/` + `NOTES.md`); the full live
  freezes and unit files are on the record in issue #35 comment 7060448797.

— Muse 3
