# Per-server union locks — resolution table & proof (Python 3.12 upgrade)

Artifacts: `deploy/requirements-server1.lock` (198 packages) and
`deploy/requirements-server2.lock` (123 packages). These are the frozen
union sets the cutover windows build `venv312` from (PLAN.md §5 step 2;
plan work item W5, coordinator brief W2).

## Inputs

- Manifests (floors) at origin/main `9def8a7a` (2026-11-17) for all ten
  agents: `requirements.txt` (+ Forge `requirements-verification.txt`),
  VyralX from `pyproject.toml`. Per-agent cp311 `requirements.lock` files
  are the reference for what moved, never installed directly — they
  conflict inside a shared venv (S1: 12 pin conflicts, S2: 8, on current
  main; analysis regenerated for this work).
- **Adjustment 1 — Stratex from PR #835.** Main's Stratex manifest still
  caps `google-genai>=2.0.0,<3.0.0`; PR #835 (approved, merging ahead of
  the windows) raises it to `<4.0.0` and its lock resolves 3.3.0. This
  union uses the #835 manifest/lock for Stratex. Without it the union
  repeats the staging blocker: `livekit-plugins-google` requires
  google-genai ≥3.2.0 and FRIDAY-Voice cannot boot on 2.x (PLAN §3.1).
- **Adjustment 2 — VyralX Pillow per PR #347.** VyralX's pyproject on
  main still says `Pillow>=10.0,<12.0`; #347's spec (`>=13.0,<14.0`) is
  used, matching VyralX's own SEN-012 lock resolution (pillow==13.0.0).
  #347 is the held PR this upgrade unblocks.

## Method & proof (staging, CPython 3.12.3, sources = 9def8a7a)

Per-agent manifest chunks installed sequentially into a fresh venv per
server (the production-shaped build), then:

| Check | Server 1 | Server 2 |
|---|---|---|
| `pip check` | **clean** | **clean** |
| Import gate (REL-050 harness, ≥3.11) | **7/7 PASS, 0 stubs** | **3/3 PASS, 0 stubs** |
| Headline probes | **20/20 OK** | **15/15 OK** |
| Freeze size | 198 pkgs / 1.7 GB | 123 pkgs / 1.2 GB |

- Gate peak RSS (feeds W6): Stratex 268MB, Futuris 279MB, FRIDAY 159MB,
  Forge 144MB, Memora 114MB, IntelX 102MB, Inference 76MB; Cortex 115MB,
  VyralX 104MB, Sentinel 94MB.
- Extra S1 proof: `friday.voice.livekit_worker` imports end-to-end on
  the union venv (with a proxy-free env; the sandbox's proxy variables
  reproduce the httpx quirk documented in PLAN §3.2 — production hosts
  carry no such env).
- **Order-independence:** a single-shot `pip install --dry-run --report`
  over all manifest lines simultaneously reproduces both freezes
  **exactly** (0 differing pins). The frozen sets are the resolver's own
  highest mutually-compatible solution, not an artifact of chunk order.
- Delta vs the py311-plan staging freeze (0206c62a): S1 differs only in
  google-genai 2.34.0 → 3.3.0 (the W1 fix); S2 is identical. (Staging's
  counts of 199/124 included `pip` itself; these locks pin dependencies
  only.)

## Resolution table — every lock-pin conflict, and what bound it

"Pins" are the per-agent cp311 lock values that disagreed. "Chosen" is
the frozen union version. Binding constraints were extracted from the
built venvs' package metadata (and the manifest lines themselves), not
assumed.

### Server 1

| Package | Lock pins (agent: pin) | Chosen | Bound by |
|---|---|---|---|
| google-genai | FRIDAY 3.3.0 / Stratex 2.34.0 (pre-#835) | **3.3.0** | Conflict removed by PR #835 (Stratex cap <4.0.0); livekit-plugins-google 1.8.12 requires ≥3.2.0 |
| httpx2 | FRIDAY 2.16.0 / Stratex 2.16.2 / Forge 2.16.0 | **2.16.2** | Highest wins — the google-genai 3.3.0 dependency set |
| httpcore2 | FRIDAY 2.16.0 / Stratex 2.16.2 / Forge 2.16.0 | **2.16.2** | Same as httpx2 |
| pandas | Stratex 3.1.1 / Futuris 2.3.3 | **2.3.3** | statsforecast 2.1.1 (Futuris) requires `pandas<3.0.0`; Stratex's manifest floor is `>=2.2.0` — satisfied. Stratex's 3.1.1 pin came from its standalone resolve without statsforecast |
| redis | Memora 8.1.0 / Futuris 6.4.0 / Forge 6.4.0 | **6.4.0** | Futuris + Forge manifests cap `redis<7.0` (Memora's floor ≥5.0.3 is uncapped; its 8.1.0 is a standalone resolve). 6.4.0 also keeps the pre-RESP3 default wire protocol (PLAN §2.2) |
| python-dateutil | FRIDAY 2.9.0.post0 / Stratex 4.0.0 / Futuris 4.0.0 | **2.9.0.post0** | recurring-ical-events 3.8.2 (FRIDAY) requires `python-dateutil<3.0.0,>=2.8.1` |
| cffi | 2.1.1 (×5) / Stratex 2.0.0 | **2.0.0** | ccxt 4.5.92 (Stratex) exact-pins `cffi==2.0.0` |
| charset-normalizer | 3.5.2 / Stratex 3.4.7 | **3.4.7** | ccxt 4.5.92 exact-pins `charset-normalizer==3.4.7` |
| idna | 3.20 (×6) / Stratex 3.18 | **3.18** | ccxt 4.5.92 exact-pins `idna==3.18` |
| multidict | FRIDAY 7.2.1 / Stratex 6.9.1 | **6.9.1** | ccxt 4.5.92 exact-pins `multidict==6.9.1` |
| propcache | FRIDAY 0.5.4 / Stratex 0.5.2 | **0.5.2** | ccxt 4.5.92 exact-pins `propcache==0.5.2` |
| pycparser | 3.12 (×5) / Stratex 3.0 | **3.0** | ccxt 4.5.92 exact-pins `pycparser==3.0` |
| uvloop | 0.23.0 (×6) / Stratex 0.22.1 | **0.22.1** | ccxt 4.5.92 exact-pins `uvloop==0.22.1` (non-Windows CPython) |

Note on the ccxt rows: seven "conflicts" are one fact — ccxt ships a
fully pinned dependency set. In the per-agent locks those packages were
resolved without ccxt in the room; in the shared venv ccxt's exact pins
are the only satisfiable choice, and every affected agent's entrypoint
imports on them (gate 7/7). No agent manifest declares a floor any of
these choices violates.

### Server 2

Sentinel's manifest carries exact `==` pins; per PLAN §2.2 they satisfy
the Cortex/VyralX floors and govern the union.

| Package | Lock pins (agent: pin) | Chosen | Bound by |
|---|---|---|---|
| fastapi | Sentinel 0.161.1 / Cortex 0.163.1 / VyralX 0.163.1 | **0.161.1** | Sentinel manifest `fastapi==0.161.1` |
| pydantic | Sentinel 2.13.4 / Cortex 2.14.3 / VyralX 2.14.3 | **2.13.4** | Sentinel manifest `pydantic==2.13.4` |
| pydantic-core | Sentinel 2.46.4 / Cortex 2.50.4 / VyralX 2.50.4 | **2.46.4** | Follows pydantic 2.13.4's exact internal pin `pydantic-core==2.46.4` |
| pydantic-settings | Sentinel 2.15.0 / Cortex 2.16.3 / VyralX 2.16.3 | **2.15.0** | Sentinel manifest `pydantic-settings==2.15.0` |
| sqlalchemy | Sentinel 2.0.52 / Cortex 2.1.8 / VyralX 2.1.8 | **2.0.52** | Sentinel manifest `sqlalchemy[asyncio]==2.0.52` |
| oracledb | Sentinel 2.5.0 / Cortex 26.1.0 / VyralX 26.1.0 | **2.5.0** | Sentinel manifest `oracledb==2.5.0` (thin mode; Cortex/VyralX floors `>=2.5` satisfied) |
| alembic | Sentinel 1.19.1 / Cortex 1.20.1 | **1.19.1** | Sentinel manifest `alembic==1.19.1` |
| redis | Sentinel 6.4.0 / Cortex 7.4.1 | **6.4.0** | Sentinel manifest caps `redis<7.0` (Cortex allows <8.0.0) |

## Headline versions (both venvs)

Pillow 13.0.0 (unblocks PR #347), numpy 2.5.5, scipy 1.18.1,
pyarrow 26.0.1, statsforecast 2.1.1, xgboost 3.4.1, scikit-learn 1.9.1,
livekit-agents 1.8.12, faster-whisper 1.2.1 / ctranslate2 4.9.0 /
onnxruntime 1.32.0 / opencv-headless 5.0.0.93 / av 19.0.2,
weasyprint 70.0 (S2, imports on the system libpango chain),
cryptography 50.0.2, oracledb 26.1.0 (S1) / 2.5.0 (S2).

## Decisions & open items for the coordinator

- **nvidia-nccl-cu13==2.32.6** rides along with xgboost on S1 (~200MB
  of GPU library a CPU fleet never loads; PLAN §7). It is KEPT in the
  lock so the artifact is byte-identical to the gate-proven set.
  Dropping that single line is safe for xgboost's CPU paths but must
  re-run the xgboost probe + Stratex gate entry before the window.
- The S1 lock does not include FRIDAY's editable install; the window
  runs `pip install -e FRIDAY --no-deps` after the lock (PLAN §2.5).
- Regeneration discipline: at window build time, re-freeze on the
  host's 3.12.x and diff against these locks; any delta re-runs the
  gate before flips (PLAN §5 steps 2–3). The on-host gate run remains
  a window precondition — this staging proves the sets on CPython
  3.12.3, and import smoke is a boot-level proof, not serving traffic
  (PLAN §3.2).
