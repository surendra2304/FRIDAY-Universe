# TASK-FRD-036 — Deploy evidence (live, Server 1)

- **Task:** Deploy the FRD-033 peer-URL re-points live + re-probe IntelX/Futuris/Sentinel peer paths.
- **Worker:** Muse 9. **Clearance:** coordinator comment 7082377561 (~22:19 IST, 2026-11-22) — GRANTED, CONDITIONAL (env fix first).
- **Work PR:** #1394 (branch `muse9/task-frd-036`).
- **Deploy window:** 2026-11-22 ~22:45–22:54 IST.

## 1. Clearance step 1 — env backup

- Backed up `/opt/friday_universe/FRIDAY/.env` to `/opt/friday_universe/FRIDAY/.env.pre-frd036-20261122` (`cp -p`, mode 600 preserved, `cmp` identical) before any edit.

## 2. Clearance step 2 — exactly four values corrected

Before (verified live, each key exactly once in the file):

| Key | Before (stale) | After (corrected) |
|---|---|---|
| `FRIDAY_INTELX_URL` | `http://127.0.0.1:8005` | `http://10.0.0.120:8005` |
| `FRIDAY_FUTURIS_URL` | `http://127.0.0.1:8004` | `http://10.0.0.120:8004` |
| `FRIDAY_SENTINEL_URL` | `http://10.0.0.120:8008` | `http://10.0.0.121:8008` |
| `SENTINEL_URL` | `http://127.0.0.1:8008` | `http://10.0.0.121:8008` |

`diff` backup-vs-edited shows exactly these 4 lines. Canonical `INTELX_URL=http://10.0.0.120:8005` and `FUTURIS_URL=http://10.0.0.120:8004` were already correct and untouched. `FRIDAY_STRATEX_URL` (`http://127.0.0.1:8003`) and `FRIDAY_VYRALX_URL` (`http://10.0.0.120:8010`) untouched per the clearance. No secret value was read, printed, or stored; only URL keys were grepped.

## 3. Clearance step 3 — checkout check + restart

- **Checkout note (transparent deviation):** the clearance asked to confirm the S1 checkout "still at main `4a16d09f`". At deploy time S1 HEAD was `a6bd8ac1` (merge of PR #1391, Muse 4 TASK-VYR-039, fast-forwarded 22:34 IST — the S1 checkout follows main by routine pulls; reflog shows pulls all evening). Verified before restarting: `4a16d09f` is an ancestor of `a6bd8ac1`; `git diff 4a16d09f..HEAD -- FRIDAY/` is **empty**; the FRD-033 re-points are present in `fleet_client.py` at HEAD (`futuris 10.0.0.120:8004`, `intelx 10.0.0.120:8005`, `sentinel 10.0.0.121:8008`); tree clean (untracked runtime files only). No pull was done for the deploy; S1 stays at `a6bd8ac1` (origin/main has since moved to `816ed65`). Rollback target, if needed: pre-restart commit `a6bd8ac1` + env backup above.
- **Restart:** `systemctl restart FRIDAY.service` — exit 0. MainPID `2364980` (started 21:08:43 IST) → `2418691` (started 22:51:13 IST), `ActiveState=active`, `NRestarts=0`.

## 4. Clearance step 4 — health verification

- `GET http://127.0.0.1:10000/health` → **200** (`overall: healthy`, `status: healthy`, `service: friday_core`, `version: 2.0.0`), checked 22:52:14 IST.
- `GET http://127.0.0.1:10000/ready` → **200** (`ready: true`, `database: connected`, `database_backend: oracle`, `mesh: configured`, disk healthy).
- Listening on `0.0.0.0:10000`, pid 2418691.

## 5. Peer re-probes (plan steps 4–5)

### Direct reachability from Server 1

| Probe | Result |
|---|---|
| IntelX `http://10.0.0.120:8005/health` | 200 |
| Futuris `http://10.0.0.120:8004/health` | 200 |
| Sentinel `http://10.0.0.121:8008/health` | 200 |
| Dead host `http://10.0.0.121:8005/health` | 000 |
| Dead host `http://10.0.0.120:8008/health` | 000 |

### Dispatch-bus agent configs as FRIDAY sees them (post-restart)

- IntelX `base_url: http://10.0.0.120:8005`, Futuris `http://10.0.0.120:8004`, Sentinel `http://10.0.0.121:8008`; all `circuit_open: false`, `consecutive_failures: 0`. (Pre-fix, IntelX showed `http://127.0.0.1:8005`.)

### WF-001 IntelX leg re-run

- **Bus path:** `POST /api/v1/dispatch/send?agent=IntelX&action=research_live` → HTTP 200, `task_id: disp_07b5b983d352`, `status: completed`, latency 20.4 s. Pre-fix this path returned `status: failed`, `error: "Connection refused - agent not running"`. **Routing fixed.** Result content is `DEGRADED`: real findings were fetched (source excerpts with citations, e.g. blog.mean.ceo April 2026 AI-model-releases article) but `synthesis_status: failed` with `synthesis_error: {reason: synthesis_ConnectError}` — see follow-up F2 below.
- **Chat path:** `POST /api/chat` ("Research the latest AI model releases and give me the highlights") → HTTP 200, 14.9 s, `task_state: FAILED`, `probe_success: false`. Reply, honestly: "IntelX could not complete that research: sourced_findings_unverified. That is the real outcome — no highlights were fabricated." Pre-fix this path returned `ConnectError: All connection attempts failed` — FRIDAY now reaches IntelX and gets findings back; the failure moved downstream (F2).
- **Unified dispatch records:** total 2 after the re-run — `IntelX: 1` completed (bus), `intelx: 1` failed (chat). Store was 0 before the re-run (in-process store, cleared by the restart — expected).

## Verdict

- **FRD-036 acceptance (FRIDAY peer URLs live + re-probed): MET.** FRIDAY's IntelX/Futuris/Sentinel peer URLs now point at the live hosts on both the FleetClient and dispatch-bus paths; dead hosts are not routed to; FRIDAY is healthy on the new code + fixed env.
- **WF-001 M1 acceptance (IntelX leg returns real highlights): NOT MET — blocked downstream, not by FRD-036.** The remaining failure is inside IntelX's own research pipeline (F2).

## Follow-up F2 — IntelX synthesis fails on its own stale S2 env (NOT fixed here — no clearance)

- IntelX (Server 2) env has `INFERENCE_URL=http://127.0.0.1:8001` and `FRIDAY_URL=http://127.0.0.1:10000`. From Server 2, `127.0.0.1:8001` → 000 and `127.0.0.1:10000` → 000, while `10.0.0.121:8001` → 200 and `10.0.0.121:10000` → 200. Inference and FRIDAY live on Server 1; IntelX's localhost pointers are dead on Server 2.
- Mechanism (code): `IntelX/intelx/api/grounded_live_research.py:55` — `GroundedInferenceGateway.complete` POSTs synthesis to `cfg.INFERENCE_URL + /v1/chat/completions`. That is the `synthesis_ConnectError`.
- Fix (separate task, coordinator clearance): point IntelX's S2 `INFERENCE_URL` at `http://10.0.0.121:8001` (and audit `FRIDAY_URL` / any other localhost pointers in the S2 IntelX env), restart IntelX, re-run the WF-001 IntelX leg. Filed here for Muse's pool; no S2 IntelX config was touched in this task.

## Open items noted, not fixed here (plan step 6, unchanged)

- Stratex engine-vs-dashboard dispatch on 8003, VyralX `10.0.0.120:8010` unverified, stale copies in `mesh/universe_health.py` and Forge/Inference configs — out of scope for this task.

— Muse 9, 2026-11-22 ~22:55 IST
