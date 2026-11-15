# TASK-REL-048 — Results: Stratex/Futuris memory footprint — version artifact or real growth?

Date: 2026-11-15. Claim: issue #35 comment 6893273785.
Branch: `claude/task-rel-048-memory-footprint` (stacked on PR #338,
`claude/task-rel-046-local-staging` — staging/ is not on main yet).
Code tree measured: the REL-046 gate tree (repo main
`56e28e6342c6dc5aa45ddd0acefeba557011b393`), same tree REL-046 measured.

## Verdict, without softening

**The overage is REAL footprint. It is not a Python 3.12-vs-3.10
artifact.** On production's own interpreter (3.10) with production's own
library versions, the same code peaks *higher* than on the 3.12 staging
stack for both agents, and Stratex's steady state is far higher. What
actually differs between staging and production is swap: production's
956 MB host carries ~150–190 MB of each of these processes in swap
(memory pressure is severe — PSI "full" avg10 ≈ 28%), so their resident
sets *look* small while their total footprints match the staging
measurements almost exactly. Production's 180 MB MemoryMax has never
bounded these agents' footprints; it bounds what stays resident while
the kernel swaps the rest. Stratex's dashboard footprint (~232 MB) is
larger than its cap by ~29%, Futuris's (~186 MB) by ~3% — before any
growth. That is the production risk REL-046's gate surfaced, and it is
real.

## 1. Production truth (read-only, Server 1, 2026-11-15 ~16:25 IST)

Via the bridge `run_shell` (server 1): `systemctl show`, `/proc/<pid>/status`,
`ps`. Production venv interpreter: **Python 3.10.12**.

| Process (unit) | Uptime | cgroup MemoryCurrent | MemoryMax | VmRSS | VmHWM (peak RSS) | VmSwap | Total footprint (RSS+swap) |
|---|---|---|---|---|---|---|---|
| Stratex dashboard (`Stratex.service`, `dashboard.py`) | ~2.5 h | 49.3 MiB | 180 MiB | 43.4 MiB | **201.2 MiB** | 188.5 MiB | **231.9 MiB** |
| Futuris (`Futuris.service`, uvicorn `futuris.api.app:app`) | ~9.7 h | 33.8 MiB | 180 MiB | 34.7 MiB | **168.9 MiB** | 151.4 MiB | **186.1 MiB** |
| (context) Stratex daemon (`Stratex-Daemon.service`, not the gated process) | ~2.5 h | 89.5 MiB | 300 MiB | 89.1 MiB | 185.7 MiB | 102.5 MiB | 191.6 MiB |

Host: 956 MB RAM, MemAvailable ~145 MB, swap 8,191 MB total / ~2,597 MB
used, `/proc/pressure/memory` full avg10 = 28.35. Both gated services
show NRestarts=0 — they have not been OOM-killed; they survive *because*
the kernel swaps their cold pages out from under the cgroup limit, not
because they fit it. Note Stratex's peak RSS (VmHWM 201 MiB) already
exceeds its 180 MiB MemoryMax on paper: cgroup accounting charges
current usage and can reclaim/swap during a climb, so a transient peak
RSS above MemoryMax is survivable in a way a sustained one is not.

## 2. Controlled local experiment — same code, same staging recipe, two stacks

Method: REL-046's own diagnostic method (spawn with the manifest recipe
and staging env, sample tree RSS every 1 s for ~110 s, poll health).
Arm A = REL-046's staging venv (Python 3.12.3, `--system-site-packages`:
numpy 1.26.4 / pandas 2.1.4 Debian builds, scipy 1.11.4, ccxt 4.5.92,
SQLAlchemy 2.1.8). Arm B = a purpose-built Python 3.10.15 venv with the
staging requirements **pinned to the production venv's versions**
(numpy 2.2.6, pandas 2.3.3, scipy 1.15.3, ccxt 4.5.89, SQLAlchemy
2.0.55, fastapi 0.161.1, oracledb 26.0.1, … — full production freeze
captured read-only from Server 1; a handful of small pure-Python
packages unpinned).

| Agent | Arm A: py3.12 staging libs — peak / steady | Arm B: py3.10 prod-pinned libs — peak / steady |
|---|---|---|
| Stratex (dashboard.py) | **233.3 / 199.6 MB** (health 200 @ 23.8 s) | **236.2 / 225.8 MB** (health 200 @ 21.5 s) |
| Futuris (uvicorn app) | **186.7 / ~156 MB** (health 200 @ 21.3 s; ~183 MB plateau for the first ~70 s, then decays) | **199.9 / 142.4 MB** (health 200 @ 7.5 s) |

Arm A reproduces REL-046's published numbers (234 / ~199; ~194) to
within a few MB. Arm B — the production-equivalent stack — is **equal
or worse on every headline figure**: Stratex peak +2.9 MB and steady
+26.2 MB vs Arm A; Futuris peak +13.2 MB. The bare-interpreter baseline
also runs the "wrong" way for the version hypothesis: 13.2 MB RSS on
3.10 vs 10.4 MB on 3.12. There is no version delta to convert away.

**Disclosure — the Futuris Arm B boot needed a measurement shim.**
Current-main Futuris does not import on Python 3.10 at all (see §4).
To measure the same code's footprint on 3.10, the local venv310 (never
shipped) carries a `sitecustomize.py` that injects `datetime.UTC` and a
minimal `enum.StrEnum` backport — attributes/classes only, no import
graph change, a few KB at most. Stratex needed no shim.

## 3. Attribution — where the footprint lives (import-step RSS deltas)

Stepwise import profiling inside each interpreter (RSS after each boot
import, staging env). Both interpreters agree on the structure; the
3.10 column is shown, 3.12 deltas in the crew's data agree within a few
MB per step (forecasts chain is *heavier* on 3.10: +127.0 vs +114.5 MB).

**Stratex dashboard** (final import RSS 231.8 MB on 3.10; boot peak 236.2):
- interpreter baseline 13.2; flask + flask_cors +16.9
- `data` (agent module; imports numpy + pandas at top, plus the market
  data client chain) **+67.4** → 97.8
- 18 core blueprints combined ≈ +22 (largest: trade_optimizer_routes +12.5)
- `api.real_trading_routes` chain **+40.3**
- `api.openbb_routes` chain (`stratex_openbb`) **+51.1**
- remaining dashboard body (deep execution modules) +18.1
- Library atoms (3.12 venv): numpy +20.8, pandas +33.6, ccxt +55.7 MB.

The dashboard — a status/control web UI — eagerly imports the entire
trading-adapter zoo (openbb, freqtrade, ccxt, nautilus, backtrader
route modules and the real-trading chain, ≈ +92 MB combined) plus
numpy/pandas before it serves a single request.

**Futuris** (final import RSS 188.1 MB on 3.10; boot peak 199.9):
- interpreter baseline 13.0; httpx +14.6; fastapi +17.3; sqlalchemy +10.3
- `futuris.api.routers.forecasts` import chain **+127.0**, of which
  (3.12 drill-down): `futuris.core.engine` +34.8,
  **`futuris.models.adapters` +83.3**, `futuris.storage.repositories` +18.3
- everything else (all other routers, demo seed, app body) ≈ +4

Futuris eagerly imports its full forecast-model adapter stack at boot
through one router's import chain — in an environment where
statsforecast is absent (by design, post-ARM) and every adapter
refuses to fit. ~83 MB of the footprint is machinery that cannot run
in production today.

## 4. Side finding (report, not fixed here): current-main Futuris cannot boot on production's Python 3.10

`futuris/api/app.py:7` does `from datetime import UTC` (3.11+) and
`futuris/core/enums.py:3` does `from enum import StrEnum` (3.11+);
both raise ImportError on 3.10. Production Futuris runs an older
deployed checkout, so production is unaffected *today* — but a Fleet CD
deploy of current main to the 3.10 venv would fail to boot Futuris.
This needs its own task (fleet-wide 3.11+-idiom sweep + a CI import
check on the production interpreter), specced in the board entry's
next_action. Stratex's dashboard imports cleanly on 3.10.

## 5. Decision and staging changes (this PR)

Classification: **(b) real footprint** — so no version conversion
exists, and production memory limits are NOT touched. What changes is
staging's cap semantics, made explicit in `fleet_manifest.yaml`:

- The staging watchdog measures RSS in a swap-free sandbox, i.e. total
  footprint. For the two agents whose measured production footprint
  exceeds their production MemoryMax, `mem_cap_mb` is now the
  **footprint cap** = max measured footprint, rounded up: **Stratex
  245 MB** (production total 231.9; local peaks 233.3 / 236.2),
  **Futuris 205 MB** (production total 186.1; local peaks 186.7 /
  199.9). The production MemoryMax (180 MB) is recorded alongside as
  `production_memory_max_mb` and remains the production value.
- This is not "raising caps to go green": the cap is anchored to a
  measured production quantity, and the gate now fails on any footprint
  *growth* beyond what production already carries — the regression
  signal the 180 MB staging cap could never provide for these two
  agents (it fired unconditionally). All other agents' caps are
  unchanged; their staging RSS sits inside their production MemoryMax.

**No agent-code reductions are implemented in this PR.** The two big
wins are not small, clearly-safe edits — they restructure live
trading/forecast import paths and belong to the Stratex/Futuris crews
with their own test rings. They are specced as follow-ups with measured
prizes:
- **Futuris (prize ≈ 83–127 MB of boot RSS):** lazy-load
  `futuris.models.adapters` (and the engine's adapter registry) so the
  adapter stack loads on first forecast use, not at app import.
- **Stratex (prize ≈ 92 MB of boot RSS):** defer the adapter blueprint
  registrations (openbb/freqtrade/ccxt/nautilus/backtrader +
  real_trading chain) behind first-use or an explicit enable flag, so
  the dashboard boots without the trading-engine zoo.
- **Stratex (smaller, entangled):** `data.py`'s top-level numpy/pandas
  (+67 MB chain) — worth revisiting after the blueprint fix, when
  pandas may no longer be resident via other chains.

If both follow-ups land, both agents plausibly fit a true 180 MB
footprint — at which point the staging caps should be tightened back
to the production MemoryMax. That tightening is the follow-ups'
acceptance criterion, stated in their specs.

## 6. Smoke-gate re-runs with the evidence-based caps

`staging/smoke_gate.py` (the REL-046 gate, unmodified) with the amended
manifest (Stratex footprint cap 245 MB, Futuris 205 MB), run per agent
under both stacks, 2026-11-15. All four runs: **PASS, gate exit 0.**

```
--only Stratex --python <py3.10 prod-pinned venv>:
Stratex     8003  245M   214M  12.1s    200  / -> 200 (24ms)              PASS
--only Futuris --python <py3.10 prod-pinned venv>:
Futuris     8004  205M   204M  16.3s    200  /openapi.json -> 200 (504ms) PASS
--only Stratex --python <py3.12 staging venv>:
Stratex     8003  245M   233M  10.1s    200  / -> 200 (8ms)               PASS
--only Futuris --python <py3.12 staging venv>:
Futuris     8004  205M   196M   8.4s    200  /openapi.json -> 200 (821ms) PASS
```

(RSS column = tree RSS at probe time, the gate's own measure; the
watchdog enforced the caps throughout, so surviving the boot peak —
§2's curves — is part of each PASS.)

Honest margins: Stratex passes with 12–31 MB of headroom depending on
stack. **Futuris's margin is thin** — 204 MB at probe time against the
205 MB cap on the 3.10 stack (the `/openapi.json` probe itself costs
memory the §2 boot diag didn't spend). The cap was NOT raised further:
205 MB is the evidence-derived number (max measured footprint
199.9 MB + ~3%), it passed on both stacks, and a thin margin is the
gate working as intended — the next few MB of Futuris footprint growth
will trip it, loudly, instead of accumulating silently against a
permanently-red 180 MB cap nobody could act on.

## 7. What this does and does not prove

Proves: production's actual Stratex/Futuris memory state (read-only
systemd + /proc evidence); that the staging overage reproduces on the
production interpreter + production library versions (so it is not a
version artifact); and where the footprint sits, import by import.
Does not prove: anything about the five staging-exempt agents; the
deployed production checkouts' exact code state (production runs older
deploys — its footprints were measured, its code was not diffed);
behaviour under real trading/forecast load (staging boots idle against
a dummy DSN, as in REL-046); or that the follow-up reductions are safe
— that is their own crews' test burden.
