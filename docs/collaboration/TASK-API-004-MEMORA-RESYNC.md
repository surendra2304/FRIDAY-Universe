# TASK-API-004 — Memora peer-key re-sync + restart + re-probe matrix

- **Task:** TASK-API-004 — API-003 F1: Memora peer-key re-sync + restart + re-probe matrix. **Owner:** Muse 4. **Priority:** P1.
- **Claim:** issue #35 comment 7075032771; claim PR #1325 (branch `muse4/task-api-004-memora-resync`). **Base:** main 2184af44 (board blob 2944d625, 13,811 lines).
- **Work run:** 2026-11-22 ~11:24–11:35 IST. **Rule obeyed throughout:** NAMES ONLY. No key value was read, printed, logged, stored, or posted anywhere. All comparisons and probes ran as server-side scripts holding values in memory only, printing key names + MATCH/DIFFER booleans + HTTP statuses.

## F1 recap (source: TASK-API-003_AUDIT.md §4, Muse 10)

Memora's `.env` copies of all 9 peer key names DIFFERED from the fleet copies (FRIDAY/Inference/Stratex/Forge/Sentinel `.env` files all match each other). Live consequence, verified twice by the audit: Memora rejected the fleet-standard `FRIDAY_API_KEY` and `INFERENCE_API_KEY` (401) but accepted Memora's own copies of the same names (200). Auth code is correct (`Memora/apps/api/dependencies.py:324`); the distribution was broken. Fix: re-sync Memora's `.env` peer keys to the fleet values, restart Memora, re-probe the matrix. No rotation of `MEMORA_API_KEY` itself is implied.

The 9 peer key names: `FRIDAY_API_KEY`, `INFERENCE_API_KEY`, `STRATEX_API_KEY`, `FUTURIS_API_KEY`, `INTELX_API_KEY`, `FORGE_API_KEY`, `SENTINEL_API_KEY`, `CORTEX_API_KEY`, `VYRALX_API_KEY`. Memora runs on Server 1 (10.0.0.121), port 8002; fleet `.env` files compared live on Server 1.

## 1. Baseline — F1 reproduced (2026-11-22 ~11:28 IST)

Server-side comparison script (values in memory only; output names + booleans):

- Presence: all 9 names present in all 6 Server 1 `.env` files, except `VYRALX_API_KEY` absent from FRIDAY's `.env` (as the audit recorded).
- Fleet consensus: 5/5 agreement on the 8 names present in all five fleet files; 4/4 on `VYRALX_API_KEY`.
- Memora vs fleet consensus: **DIFFER on all 9 names** — F1 reproduced exactly.

## 2. Re-sync (2026-11-22 ~11:29 IST)

- Backup written server-side only: `/opt/friday_universe/Memora/.env.bak-api004-20261122` (stays on Server 1; never read, printed, or posted).
- Rewrote Memora's `.env`, replacing only the 9 peer-key values with the fleet consensus values, preserving every other line byte-for-byte and the file mode (0600).
- Verification (same comparison script, post-sync): **all 9 names MATCH** the fleet consensus; **all non-peer keys unchanged**; `MEMORA_API_KEY` and `MEMORA_MASTER_KEY` present and untouched. Exactly 9 lines changed.

## 3. Restart (2026-11-22 11:30 IST)

- Pre-restart: `Memora.service` active (running) since 2026-11-21 22:04:19 IST, PID 1702714, `GET /health` 200.
- Restart via bridge `oracle_restart_service`. Note: the bridge reported a 25 s SSH timeout ("Active Status: activating") — the restart itself completed; verified independently below.
- Post-restart: `Memora.service` active (running) since **2026-11-22 11:30:34 IST**, new PID 2083607; `ExecStartPre` migrations exit 0, `MEMORA-MIGRATION before=c9d4e7a1b5f2 after=c9d4e7a1b5f2 status=at-head`; `GET /health` 200.

## 4. Re-probe matrix (2026-11-22 ~11:31 IST, post-restart)

Route `GET /v1/memories/search` on Memora :8002 (Server 1 loopback). First pass used a bare GET and returned 422 for every authenticated call — 422 is auth-passed per the audit's scoring (route exists, validation failed), and the cause was the missing required `q` query param (`Sentinel/sentinel/memora_cloud_fallback.py:126` shows the mesh call form `?q=...&limit=...`). Re-probed with the mesh call form `?q=api004&limit=1`:

| Probe | Result |
|---|---|
| Fleet `FRIDAY_API_KEY` as `friday` | **200** (was 401 pre-fix) |
| Fleet `INFERENCE_API_KEY` as `inference` | **200** (was 401 pre-fix) |
| Fleet `STRATEX_API_KEY` as `stratex` | **200** (519-byte search body) |
| `MEMORA_API_KEY` as `memora` (own key, untouched) | **200** |
| No key (control) | 401 |
| Random key as `friday` (control) | 401 |
| Fleet `FRIDAY_API_KEY` as `stratex` (mismatch control, bare GET) | 401 |
| `MEMORA_MASTER_KEY` as `friday` (bare GET; auth-passed 422) | 422 = auth passed |

Memora → fleet spot check: Memora's (now fleet-synced) copy of `INFERENCE_API_KEY` against Inference `GET /tasks/does-not-exist-api004` → **404** (auth passed; route does not exist). The Memora → fleet direction works with the re-synced keys.

## 5. Acceptance check

- "Memora's `.env` peer keys re-synced to the fleet values (MATCH on all 9 names, booleans only, names-only rule)" — **MET**: 9/9 MATCH post-sync, verified by the comparison script; no key value appears in this doc, in any probe output, or in any commit.
- "Memora restarted" — **MET**: restarted 11:30:34 IST, new PID 2083607, migrations at-head, `/health` 200.
- "Auth matrix re-probed showing FRIDAY-to-Memora mesh calls authenticating (200) with fleet-standard keys" — **MET**: fleet `FRIDAY_API_KEY` and `INFERENCE_API_KEY` both return 200 on the mesh search route; negative controls still 401.

## 6. Notes / follow-ups

- None owed by this task. API-003 findings F2 (Cortex `FRIDAY_API_KEY`) and F3 (Sentinel auth) are separate pool-6 items (API-005, API-006) and were not touched.
- The bridge's `oracle_restart_service` 25 s SSH timeout message is cosmetic here (the restart completed); the post-restart state was verified by a fresh `oracle_check_service` read, not by the restart call's output.

— Muse 4
