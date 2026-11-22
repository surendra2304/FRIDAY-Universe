# TASK-API-006 — Sentinel API auth enable + restart + re-probe matrix

- **Task:** TASK-API-006 — API-003 F3: Sentinel API auth enable + restart + re-probe matrix (P1).
- **Owner:** Muse 10. **Claim:** issue #35 comment 7075505639; claim PR #1335 merged 46e17b1c.
- **Implementation run:** 2026-11-22 ~13:10–13:25 IST. **Base:** main 12d7c0cc (board blob ae637d70, 14,043 lines). Branch rebased onto main 12d7c0cc before the work PR (the claim commit efc8e5c2 is already in main via the merged claim PR #1335; main moved f3dab30e → 12d7c0cc, merge of PR #1341, during the run, so the doc commit was re-created on the new main head).
- **Rule obeyed throughout:** NAMES ONLY. No key value was read, printed, logged, stored, or posted anywhere. Probes were read-only GETs; response bodies were discarded and only HTTP statuses were recorded. Keys were held in server memory only, loaded from the services' own `.env` files.

## Verdict in one paragraph

F3 is **FIXED live**. Sentinel now enforces API-key authentication on `GET /api/v1/tasks`: no key → 401, wrong/random/peer keys → 403, the fleet `SENTINEL_API_KEY` → 200.

## Baseline (before the change, ~13:10 IST)

- Live env inventory (names only): `SENTINEL_API_KEY` set, length ≥32 (true); `SENTINEL_API_AUTH_REQUIRED` unset; `RENDER` unset. All 9 peer key names are present in Sentinel's `.env` except `MEMORA_API_KEY` (sourced from Memora's `.env` for the probe).
- All 12 probes returned 200 (no key, random key, own key, all 9 peer keys) — F3 reproduced live, unchanged since the API-003 audit.
- Deployed code == main: git blob hashes of `Sentinel/sentinel/apps/api/middleware.py` (`bc3d112d…`) and `Sentinel/sentinel/config/settings.py` (`d4c47b9f…`) match main f3dab30e exactly. The middleware (lines 264–269) enables auth when `RENDER` or `SENTINEL_API_AUTH_REQUIRED` is truthy (`"1"`/`"true"`/`"yes"`) or `settings.api_auth_required`; `settings.py:335` defaults `api_auth_required` to False. `.env.example` line 20 already documents `SENTINEL_API_AUTH_REQUIRED=true`.

## Change made

- One line appended to the live config `/opt/friday_universe/Sentinel/.env` on Oracle Server 1 (the systemd `EnvironmentFile` for the `Sentinel.service` unit): `SENTINEL_API_AUTH_REQUIRED=true` (line 52; verified exactly one occurrence). No key value was created, changed, or printed — `SENTINEL_API_KEY` was already set and ≥32 chars, so no key change was needed. Pre-change backup copied to `/tmp/sentinel-env.bak-20261122-api006` (mode 600 preserved).
- No repo file was changed for the fix itself: the `.env` is server-local live config, not tracked in the repo.

## Restart evidence

- Sentinel runs on Oracle Server 1 as systemd unit `Sentinel.service` (`uvicorn sentinel.apps.api.main:app`, port 8008; `EnvironmentFile=/opt/friday_universe/Sentinel/.env`). Server 2's `Sentinel.service` unit is masked/inactive — Sentinel runs only on Server 1.
- Restart: `sudo systemctl restart Sentinel` on Server 1 at 13:13:26 IST. Old process PID 1684086 (running since 2026-11-21 21:27:22 IST) shut down gracefully (13:13:22–13:13:26); new process PID 2131119 started 13:13:26, "Application startup complete" 13:14:10, "Uvicorn running on http://0.0.0.0:8008" 13:14:12. Port 8008 listening, owned by PID 2131119. Journal: "Zero-trust startup configuration validation passed successfully". `GET /health` → 200.
- Note: the first health poll right after the restart returned 000 (connection refused) — the service takes ~45 s from process start to listening (DB schema ensure + daemon startup). The retry then returned 200. Not a defect.
- Bridge transport dropped 3 calls mid-run (`IncompleteRead` / "MCP request did not complete"); each was retried or followed by a state check. The restart call itself dropped at the MCP layer but the restart had completed — verified by the PID change + journal before proceeding. No action was double-applied (the `.env` edit was verified exactly-once).

## Re-probe matrix (after restart, ~13:17 IST)

Route: `GET /api/v1/tasks` on `127.0.0.1:8008` (Server 1 loopback). Header `X-API-Key`. Statuses only.

| Case | Key presented | Status | Verdict |
|---|---|---|---|
| No key | — | 401 | REJECT ✓ |
| Random key | random 24-byte hex | 403 | REJECT ✓ |
| Own key | `SENTINEL_API_KEY` | 200 | ACCEPT ✓ |
| Peer | `FRIDAY_API_KEY` | 403 | REJECT ✓ |
| Peer | `INFERENCE_API_KEY` | 403 | REJECT ✓ |
| Peer | `STRATEX_API_KEY` | 403 | REJECT ✓ |
| Peer | `FUTURIS_API_KEY` | 403 | REJECT ✓ |
| Peer | `INTELX_API_KEY` | 403 | REJECT ✓ |
| Peer | `FORGE_API_KEY` | 403 | REJECT ✓ |
| Peer | `CORTEX_API_KEY` | 403 | REJECT ✓ |
| Peer | `VYRALX_API_KEY` | 403 | REJECT ✓ |
| Peer | `MEMORA_API_KEY` (from Memora's `.env`) | 403 | REJECT ✓ |
| Health | `GET /health` (exempt path) | 200 | — |

All 12 cases match the acceptance: unauthenticated/wrong-key → 401/403; fleet key → 200.

## Residual gaps / notes

- **G1 — mesh callers must present the target key.** `mesh/transport.py` already presents the target's key, so compliant callers are unaffected by design; any caller that was relying on Sentinel's previously open endpoint with its own key will now get 403 until it presents Sentinel's key. No mesh-caller check was made in this run.
- **G2 — loopback probe only.** The acceptance probed the loopback interface (same as API-003's Sentinel probes). The public-ingress path (Caddy → :8008) was not re-probed; the middleware is interface-independent, so the loopback verdict covers the gate, but a public-ingress confirmation is a one-line follow-up if the coordinator wants it.
- **G3 — TLS daemon warning at startup.** One journal line at 13:14:11 IST: TLS check failed for `friday-universe.duckdns.org:443` (Sentinel's TLS & DNS drift daemon). Unrelated to the auth change and not investigated here; flagging for the coordinator.

— Muse 10
