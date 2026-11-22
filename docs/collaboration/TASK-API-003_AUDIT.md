# TASK-API-003 — Authentication matrix test (names only)

- **Task:** TASK-API-003 — Authentication matrix test: each agent accepts only its configured keys — MASTER_PLAN §6, standing backlog, pool 2 item 6.
- **Owner:** Muse 10. **Claim:** issue #35 comment 7072358568; claim PR #1287 merged 254c2df1.
- **Audit run:** 2026-11-22 ~08:15–09:00 IST. **Base:** main 21fb6106 (board blob acc8de96, 13,592 lines). Branch rebased onto main 21fb6106 before any work (merge-base exactly main).
- **Rule obeyed throughout:** NAMES ONLY. No key value was read, printed, logged, stored, or posted anywhere. Every live probe was a read-only GET; response bodies were discarded and only HTTP statuses were recorded. Keys were held in server memory only, loaded from the services' own `.env` files, and are never reproduced here.

## Verdict in one paragraph

Per-agent isolation **does not hold fleet-wide**. 3 of 10 agents isolate cleanly live (Futuris, Stratex, Memora's auth logic). 4 accept other agents' keys **by design** (Inference: 8 peer keys; IntelX: 7 peer keys as MEMBER; Forge and VyralX: FRIDAY's key). 1 enforces **nothing** live (Sentinel: every key, no key, and a random key all return 200). And 2 agents' **credential values have drifted** from the fleet copies, so the mesh itself is broken at those points even though their auth code is correct (Memora: all 9 peer-key values differ from the fleet copies; Cortex: its `FRIDAY_API_KEY` value is the `CORTEX_API_KEY` value, not the fleet FRIDAY value). Findings F1–F10 below.

## Method and scope

- Code review (main 21fb6106) of the inbound auth module of all 10 agents, plus the mesh transport and the Caddy routing table. 17 auth files on the live servers were hashed (git-blob SHA-1) and **all 17 match main** — live behaviour is the reviewed code.
- Live probes: ~140 read-only GET requests against the 9 running agents (VyralX is not running; see §6). Each agent was probed on a protected GET route with: its own key, every other agent's key, no key, and a random 24-byte key. Statuses only: 401/403 = REJECT, 200/404/422 = ACCEPT (auth passed; 404 = route exists, id does not), 429 = rate-limited, 503 = not configured.
- Key inventory: 18 key names tracked (10 per-agent `<AGENT>_API_KEY` names, `FRIDAY_UNIVERSE_API_KEY`, `MEMORA_MASTER_KEY`, `BOT_API_KEY`, `TRADING_BOT_API_KEY_READ`, `TRADING_BOT_API_KEY_CONTROL`, `API_KEY_FRIDAY`, `API_KEY_CONTROL`, `API_KEY_READONLY`). Presence only: every agent's `.env` holds the full peer-key set except where noted in §1. `AI_UNIVERSE_API_KEY` is absent from every `.env` on both servers.
- Scope is the live fleet on 2026-11-22. No POST/mutating probe was issued. No key value was compared by sight — value equality was tested only as in-memory MATCH/DIFFER booleans on the server.

## 1. Key names present per agent (names only)

Every agent's `.env` holds its own key plus the peer keys it needs for mesh calls. Exceptions:

| Key name | Where it is set |
|---|---|
| `FRIDAY_API_KEY`, `INFERENCE_API_KEY`, `STRATEX_API_KEY`, `FUTURIS_API_KEY`, `INTELX_API_KEY`, `FORGE_API_KEY`, `SENTINEL_API_KEY`, `CORTEX_API_KEY` | All 9 running agents' `.env` files |
| `VYRALX_API_KEY` | All except FRIDAY's `.env` |
| `FRIDAY_UNIVERSE_API_KEY` | Only FRIDAY's `.env` |
| `MEMORA_API_KEY`, `MEMORA_MASTER_KEY` | Only Memora's `.env` |
| `BOT_API_KEY`, `TRADING_BOT_API_KEY_READ`, `TRADING_BOT_API_KEY_CONTROL`, `API_KEY_FRIDAY` | Only Stratex's `.env` |
| `API_KEY_CONTROL`, `API_KEY_READONLY` | Absent from every `.env` on both servers |
| `AI_UNIVERSE_API_KEY` | Absent from every `.env` on both servers |

Auth-mode flags live: `APP_ENV=production` (or `ENVIRONMENT=production`) on all 9 running services; `RENDER` unset everywhere; `FORGE_ENV=production`; `API_KEYS_ENABLED=true` (Futuris); `SENTINEL_API_AUTH_REQUIRED` unset; `CORTEX_DEV_AUTH_BYPASS` unset; `MEMORA_ALLOW_ANONYMOUS_DEV` unset; `INSECURE_DEV_AUTH` unset.

## 2. Live matrix (per agent)

`A` = accepted, `R` = rejected (401/403). "Own" is the agent's own key name. "Peers" counts distinct other-agent keys actually probed.

| Agent (port, route probed) | Own | Peers accepted | Peers rejected | No key | Random key |
|---|---|---|---|---|---|
| FRIDAY (10000, `GET /api/doctor`) | A (200) | 0 of 9 | 9 of 9 (401) | R (401, remote + public) / **A (200, loopback only)** | R (401) |
| Inference (8001, `GET /tasks/<nonexistent>`) | A (404) | **8 of 8** (404) | 0; `FRIDAY_UNIVERSE_API_KEY` + `MEMORA_API_KEY` R (403, not configured in Inference env) | R (401) | R (403) |
| Memora (8002, `GET /v1/memories/search`) | A (200) | 0 of 9 with fleet copies; **see F1** — with Memora's own copies, friday + inference A (200) | 9 of 9 with fleet copies (401) | R (401) | R (401) |
| Stratex (8003, `GET /api/v1/portfolio/snapshot`) | A (200); `BOT_API_KEY` A (200) | 0 of 4 probed (subset; see §5) | 4 of 4 (401) | R (401) | R (401) |
| Forge (8006, `GET /api/v1/tasks`) | A (200) | **1 of 9** — `FRIDAY_API_KEY` A (200) | 8 of 9 (403) | R (401) | R (403) |
| Sentinel (8008, `GET /api/v1/tasks`) | A (200) | **9 of 9** (200) | 0 | **A (200)** | **A (200)** |
| Futuris (8004, `GET /v1/market-data/providers`) | A (200) | 0 of 8 (`MEMORA_API_KEY` skipped: absent on Server 2) | 8 of 8 (401) | R (403, anonymous viewer) | R (401) |
| IntelX (8005, `GET /v1/research/live`) | A (200) | **7 of 9** (200) | `INFERENCE_API_KEY` R (401); `MEMORA_API_KEY` skipped (absent on Server 2; not seeded per code) | R (401) | R (401) |
| Cortex (8009, `GET /api/v1/cortex/budgets`) | A (200) with Cortex's own copy of `FRIDAY_API_KEY`; fleet copy R (403) | 0 of 8 | 8 of 8 (403) | R (401) | R (403) |
| Cortex admin (8009, `GET /v1/api-keys`) | — (JWT `CORTEX_ADMIN` only) | FRIDAY credential R (401) | — | R (401) | — |
| VyralX | **Not running — not probed live** (unit masked on Server 2; Caddy routes `/vyralx` to AWS 16.176.9.247:8010 sleeper). Code only; see §6. | | | | |

Counts: 9 of 10 agents probed live (~140 requests, incl. 12 on a superseded wrong Futuris path and 3 retried first-probe timeouts). 18 key names tracked; 10 per-agent names + 8 auxiliary names.

## 3. Per-agent auth surface (code, main 21fb6106)

- **FRIDAY** — `FRIDAY/src/friday/api/server.py:916` `_require_control_access`: control endpoints require `FRIDAY_API_KEY` (fallback `FRIDAY_UNIVERSE_API_KEY` only when `FRIDAY_API_KEY` is unset, `:841-854`), via `X-Friday-Api-Key` or Bearer, or a minted control token. Key required **only for non-loopback callers** (or when `require_api_key_on_loopback` is set and the method is not idempotent). Chat surface is keyless by owner decision (origin gate only, `:896`). **Live note:** the public probe returned 401 and the journal shows the real client IP reaching the gate, but no proxy-headers middleware was found in `server.py` or repo-wide — see F8.
- **Inference** — `Inference/app/core/security.py:79-96` `_configured_keys()`: accepts 11 env names (`INFERENCE_API_KEY`, `FRIDAY_API_KEY`, `STRATEX_API_KEY`, `FUTURIS_API_KEY`, `INTELX_API_KEY`, `FORGE_API_KEY`, `SENTINEL_API_KEY`, `CORTEX_API_KEY`, `VYRALX_API_KEY`, `MEMORA_API_KEY`, `FRIDAY_UNIVERSE_API_KEY`); any of them authenticates. Router-wide `require_inference_api_key` (`Inference/app/main.py:325-363`). No key → 401; wrong key → 403; none configured → 503.
- **Memora** — `Memora/apps/api/dependencies.py:15-27,301-363` `authenticate_agent`: `X-Agent-Name` + `X-API-Key` (or Bearer), expected value = that agent's `<AGENT>_API_KEY`; `MEMORA_MASTER_KEY` authenticates as any agent (by design). No key → 401; unknown agent / unconfigured key → 503; anonymous only with `MEMORA_ALLOW_ANONYMOUS_DEV=1` (unset live).
- **Stratex** — the running dashboard (`Stratex/dashboard.py`, Flask) enforces `Stratex/security_hardening.py:229-256,430-586` `get_configured_api_keys()` / `require_api_scope`: accepted names are `BOT_API_KEY` (admin), `API_KEY_CONTROL`, `API_KEY_READONLY`, `API_KEY_FRIDAY`, `STRATEX_API_KEY` (read + friday scopes only). `Stratex/api/auth.py` (`TRADING_BOT_API_KEY_READ` / `TRADING_BOT_API_KEY_CONTROL`) is **not wired into the running dashboard**.
- **Forge** — `Forge/app/main.py:245-305` `require_production_api_key` middleware: when `api_key_required` (defaults true in production), accepts `FORGE_API_KEY` **or** `FRIDAY_API_KEY` (≥32 chars) on all non-exempt paths; else 401 (no key) / 403 (wrong key) / 503 (key unconfigured or placeholder). `Forge/app/security/api_keys.py` `verify_api_key` is unused by any route (the middleware is the live gate).
- **Sentinel** — `Sentinel/sentinel/apps/api/middleware.py:226-289` `APIKeyAuthMiddleware`: enforces `SENTINEL_API_KEY` **only when** `RENDER=1` or `SENTINEL_API_AUTH_REQUIRED=1` or `settings.api_auth_required`; otherwise non-exempt paths are only rate-limited + replay-checked. Default `api_auth_required: False` (`Sentinel/sentinel/config/settings.py:335`).
- **Futuris** — `Futuris/futuris/infra/auth.py` `get_current_user`: master `FUTURIS_API_KEY` (constant-time compare) or a DB-issued key (SHA-256 hash lookup); no key → anonymous viewer (reads allowed, mutating routes 403); wrong key → 401. `API_KEYS_ENABLED=true` live; production refuses `API_KEYS_ENABLED=false`.
- **IntelX** — `IntelX/intelx/core/auth.py` `seed_api_keys_from_settings`: seeds `INTELX_API_KEY` (admin) plus the service keys `FRIDAY_API_KEY`, `FUTURIS_API_KEY`, `STRATEX_API_KEY`, `CORTEX_API_KEY`, `SENTINEL_API_KEY`, `FORGE_API_KEY`, `VYRALX_API_KEY` as MEMBER into the key table; `get_current_api_key` / `get_friday_api_key` accept any seeded key. `INFERENCE_API_KEY` and `MEMORA_API_KEY` are **not** in the seeded set.
- **Cortex** — `Cortex/apps/api/src/cortex_api/auth.py` `verify_friday_token`: FRIDAY-integration routes accept only `FRIDAY_API_KEY` (fallback `FRIDAY_UNIVERSE_API_KEY`) via `X-Friday-Api-Key`; wrong key → 403, no key → 401, unconfigured in production → 503. User routes use JWT (`verify_jwt_token`); `GET /v1/api-keys` requires JWT `CORTEX_ADMIN` (`Cortex/apps/api/src/cortex_api/main.py:570`). `CORTEX_API_KEY` itself is not an accepted credential on any route in this module.
- **VyralX** (code only) — `VyralX/app/security.py` `require_api_key`: accepts `api_key` / `vyralx_api_key` / `friday_api_key` (so FRIDAY's key is accepted by design); in `development`/`test` env with no headers at all it allows the request.
- **Mesh** — `mesh/transport.py:30-42,183-199`: each agent has its own `<AGENT>_API_KEY`; mesh calls present the **target's** key as Bearer. The shared-secret-per-service model is why every agent's `.env` holds the peer keys.

## 4. Findings (file/line + fix or follow-up)

- **F1 — Memora's peer-key values have drifted from the fleet (HIGH).** Cross-file comparison (MATCH/DIFFER booleans only): Memora's `.env` copies of all 9 peer key names DIFFER from the copies in FRIDAY/Inference/Stratex/Forge/Sentinel `.env` files, which all match each other. Live consequence, verified twice: Memora rejects the fleet-standard `FRIDAY_API_KEY` and `INFERENCE_API_KEY` (401) but accepts Memora's own copies of the same names (200). So FRIDAY→Memora (and Memora→fleet) mesh calls fail authentication. Auth code is correct (`Memora/apps/api/dependencies.py:324`); the distribution is broken. Follow-up: re-sync Memora's `.env` peer keys to the fleet values (or rotate fleet-wide and redistribute), then restart Memora. No rotation of `MEMORA_API_KEY` itself is implied.
- **F2 — Cortex's `FRIDAY_API_KEY` value is the `CORTEX_API_KEY` value (HIGH).** Equality check (booleans only): Cortex's `.env` `FRIDAY_API_KEY` == fleet `CORTEX_API_KEY` (and == Cortex's own `CORTEX_API_KEY`), ≠ fleet `FRIDAY_API_KEY`. Live consequence: FRIDAY calling Cortex with the fleet key gets 403, and presenting `CORTEX_API_KEY` as `X-Friday-Api-Key` gets 200 with the `FRIDAY_SYSTEM` role (which includes admin in `Cortex/apps/api/src/cortex_api/auth.py` role hierarchy). Follow-up: set Cortex's `FRIDAY_API_KEY` to the fleet value and restart Cortex; consider rotating `CORTEX_API_KEY` since it has served as the FRIDAY credential. Code: `Cortex/apps/api/src/cortex_api/auth.py` `verify_friday_token`.
- **F3 — Sentinel enforces no authentication live (HIGH).** `APIKeyAuthMiddleware` is opt-in and all three opt-ins are off (`RENDER` unset, `SENTINEL_API_AUTH_REQUIRED` unset, `api_auth_required` defaults False). Live: own key, all 9 peer keys, no key, and a random key all return 200 on `GET /api/v1/tasks`. Follow-up: set `SENTINEL_API_AUTH_REQUIRED=true` (and confirm `SENTINEL_API_KEY` is set, ≥32 chars) and restart Sentinel; re-run this matrix afterwards. Code: `Sentinel/sentinel/apps/api/middleware.py:226-289`, `Sentinel/sentinel/config/settings.py:332-335`.
- **F4 — Inference accepts 8 other agents' keys by design (MEDIUM; coordinator decision).** `_configured_keys()` (`Inference/app/core/security.py:79-96`) lists 11 accepted names; live, 8 peer keys pass. If the board's "only its own key" is the requirement, Inference fails it — but the shared-mesh model in `mesh/transport.py` treats peer keys as legitimate caller credentials. Follow-up: coordinator decision — either narrow Inference to its own key(s) or amend TASK-API-003's acceptance to the mesh model. Same design question covers IntelX (F5), Forge/VyralX (FRIDAY key accepted).
- **F5 — IntelX seeds 7 peer keys but not INFERENCE's or MEMORA's (LOW).** `seed_api_keys_from_settings` (`IntelX/intelx/core/auth.py`) omits `INFERENCE_API_KEY` and `MEMORA_API_KEY` from the service-keys set; live, `INFERENCE_API_KEY` → 401 while the other 7 peers → 200. Follow-up: add the two missing names to the seeded set (or document that Inference/Memora must present the target `INTELX_API_KEY`). Note peer keys get MEMBER role; admin-only routes would still reject them (not probed).
- **F6 — `FRIDAY_UNIVERSE_API_KEY` is a dead credential live (LOW).** Accepted nowhere as a credential in its own right: FRIDAY's `_control_secret()` returns `FRIDAY_API_KEY` first so the fallback is never reached while that key is set (`FRIDAY/src/friday/api/server.py:841-854`, live 401); Inference does not have it configured (live 403); Cortex's fallback is unreachable while its `FRIDAY_API_KEY` is set. Follow-up: either configure it everywhere it is listed as accepted, or remove it from the accepted lists (`Inference/app/core/security.py`, `Cortex/apps/api/src/cortex_api/auth.py`, FRIDAY `server.py`).
- **F7 — Stratex has two auth implementations; only one is live (LOW).** `Stratex/api/auth.py` (`TRADING_BOT_API_KEY_READ`/`CONTROL`, role-based) is not imported by the running `dashboard.py`; live enforcement is `Stratex/security_hardening.py`. The `TRADING_BOT_*` keys are configured in Stratex's `.env` but rejected live (401). Follow-up: reconcile — wire `api/auth.py` in or remove the `TRADING_BOT_*` names from the env/docs so operators stop provisioning dead keys.
- **F8 — FRIDAY control endpoints are keyless from the loopback interface (MEDIUM).** `_require_control_access` (`FRIDAY/src/friday/api/server.py:916-991`) returns early for loopback callers unless `require_api_key_on_loopback` is set; live, loopback `GET /api/doctor` with no key → 200, while the same request from a private IP or the public ingress → 401. Remote callers are correctly gated. Follow-up (coordinator decision): set `require_api_key_on_loopback=true` if on-host unauthenticated control access is not intended. Open question: the journal proves uvicorn sees the real client IP for public requests (`57.141.12.18:0` → 401), yet no proxy-headers middleware was found in `server.py` or repo-wide — the trust path for `X-Forwarded-For` was not located; behaviour is verified, mechanism is not.
- **F9 — VyralX was not probed live (gap, not a code finding).** Service masked on Server 2 since 2026-11-19; Caddy routes `/vyralx` to AWS 16.176.9.247:8010 (sleeper). Code (`VyralX/app/security.py`) accepts FRIDAY's key by design and allows unauthenticated requests when `app_env` is `development`/`test` with no headers. Follow-up: probe VyralX when it is running again (or against the AWS sleeper with owner direction); confirm its live `app_env`.
- **F10 — Bridge MCP endpoint has no authentication (observation, out of scope).** The 24/7 bridge at `https://friday-universe.duckdns.org/bridge/mcp` accepts unauthenticated requests by design (connector doc `custom.friday-universe`); it is not a per-agent key surface, so it is not scored here, but it is adjacent: anyone with the URL can call the same read/write tools this audit used. Follow-up: coordinator decision on bridge auth (no action taken here).

## 5. Hygiene verified (guards already in place)

- All 9 running services run with `APP_ENV`/`ENVIRONMENT=production`; no `INSECURE_DEV_AUTH`, no `CORTEX_DEV_AUTH_BYPASS`, no `MEMORA_ALLOW_ANONYMOUS_DEV`, no `RENDER` in any process environment or `.env`.
- Memora fails closed (401, never anonymous) without its dev opt-in; Futuris refuses `API_KEYS_ENABLED=false` in production; Forge fails closed with 503 when its key is unconfigured/placeholder; Inference fails closed with 503 when no key is configured.
- No key value appears in this document, in any probe output, or in any commit — only key names, counts, and HTTP statuses. The probe scripts held values in server memory only and printed names + statuses; the equality checks printed MATCH/DIFFER booleans only.
- Live services confirmed: FRIDAY :10000, Inference :8001, Memora :8002, Stratex :8003, Forge :8006, Sentinel :8008 on Server 1; Futuris :8004, IntelX :8005, Cortex :8009, bridge :8011 on Server 2; VyralX :8010 not listening anywhere on the Oracle fleet.
- Deployed auth code == main on all 17 files hashed (see §Method).

## 6. Limitations and open items

- VyralX not probed live (F9). Memora's key not probed against Futuris/IntelX/Cortex (absent from Server 2 `.env` files; code path is unambiguous — only the service's own master key + DB keys are accepted — and 8 other peer keys all returned 401).
- Stratex other-key probes used a 4-key subset (FRIDAY, INFERENCE, FORGE, MEMORA) to stay under the 10-failures/300s IP abuse block (`Stratex/security_hardening.py`); the accepted-key list is a closed 5-name map in code, so the subset + code is the evidence.
- No POST/mutating probe was issued; the FRIDAY loopback bypass for non-idempotent methods is code-derived, not live-tested.
- Bridge transport flaked 4 times during the run (`MCP request did not complete` / `IncompleteRead`); each affected call was retried and no probe was double-counted. Three first-probe timeouts (FRIDAY/Forge/Sentinel own keys, 10s limit) were retried at 30s and returned 200.
- The first Futuris probe used a wrong path (`/v1/market-data`, all 404) and was discarded; the valid re-probe used `/v1/market-data/providers`.

## 7. Acceptance check

- "Authentication matrix tested for every agent" — **PARTIAL**: 9 of 10 agents tested live with per-key verdicts; VyralX code-reviewed only (not running). F1/F2 are live mesh breaks, F3 is a live enforcement gap, F4/F5 are design deviations.
- "No key value is read, printed, logged, stored, or posted anywhere" — **HOLDS**. Names/counts/statuses only, throughout.
- "Gaps filed with the exact file/line and the fix or follow-up" — **HOLDS**: F1–F10 above.

— Muse 10
