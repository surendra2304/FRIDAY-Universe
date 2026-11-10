# Public Ingress & Engineering Bridge — Security Review (TASK-VAL-002)

**Date:** 2026-11-10 · **Reviewer:** ZAI · **Scope:** everything reachable at `https://friday-universe.duckdns.org` from a remote network, without credentials.
**Method:** read-only probes and auth-rejection checks only (`scripts/val002_ingress_probes.py`, `scripts/val002_probes_round2.py`, `scripts/validate_fleet_live.py`). No valid credential was presented; no state-changing request succeeded. Raw evidence: `docs/validation/fleet_live_validation_2026-11-10.json`, `/tmp/val002_probes.json` (reproduced in Appendix B).

## 1. Verdict

The FRIDAY control surface is now closed (TASK-SEC-005 verified live), agent key gates hold where they exist, and the TLS/base-header posture is sound. **One critical finding requires an owner decision: the engineering bridge at `/bridge/mcp` exposes a full remote-code-execution tool set to anonymous callers — D-014's "read-mostly" premise is factually wrong.** One medium finding (Stratex paper-trading surface accepts anonymous state changes) and several low findings follow.

## 2. Findings

### B-1 CRITICAL — Engineering bridge is an anonymous RCE surface (D-014 premise is wrong)

- **Evidence (2026-11-10T13:58Z):** `initialize` handshake HTTP 200 with **no authentication whatsoever**; `tools/list` then returned **33 tools**, including:
  - `run_shell`, `run_workspace_test` — command execution
  - `write_file`, `edit_file`, `github_write_file` — arbitrary file writes
  - `git_push`, `git_create_branch`, `git_commit`, `github_create_pr` — repository control
  - `oracle_restart_service`, `oracle_caddy_reload` — infrastructure control
  - `oracle_fleet_health`, `oracle_get_logs`, `read_file`, `search_code`, `github_run_logs`, … — deep introspection
- **Analysis:** D-014 accepted the bridge as an unauthenticated *read-mostly* surface. The tool inventory above grants anonymous remote callers **write and execute** powers over the production hosts and the repository. Whether each tool has hidden server-side guards is unverifiable from outside (the bridge server implementation does not live in this repository); even under the most charitable assumption, an anonymous RCE-capable surface on public DNS fails any reasonable bar.
- **Impact:** total infrastructure compromise (file writes, git push, service restart, shell) by any internet scanner.
- **Recommendation (owner decision required):** activate the already-merged fail-closed `BridgeAuthMiddleware` (PR #24, `bridge/auth.py`, parked by D-014) by setting `FRIDAY_BRIDGE_SHARED_SECRET` on Server 1 and requiring `X-FRIDAY-BRIDGE-KEY` on all bridge routes. This is a config change + one Caddy/bridge restart, not new code. **Until then, treat the bridge URL as a live intrusion path.** Rotating the Telegram/DuckDNS tokens (D-016 follow-ups) does not mitigate this; the bridge can read server env vars.
- **Interim mitigations available to the owner tonight:** Caddy `remote_ip` allow-listing of `/bridge/*` to the owner's current IP, or taking the bridge offline until the secret is set.

### B-2 MEDIUM — Stratex paper-trading API accepts anonymous state changes

- **Evidence (2026-11-10T13:57–58Z):** `POST /stratex/api/v1/trading/engines/autohedge/consensus` → **HTTP 200** to an anonymous remote caller (pure compute — request-body in, consensus out). `GET /stratex/api/live/account` → **HTTP 200** `{"total_balance": 10000.0, …}` and `GET /stratex/api/live/exchanges` → **HTTP 200** `[]` — the live-execution engine state is anonymously readable, and `POST /api/live/exchange/connect`, `POST /api/live/order`, `POST /positions/<symbol>/close` are registered in the running app (`Stratex/dashboard.py` line 46) with **no route-level auth** (`Stratex/api/live_execution_routes.py`).
- **Bounding factors (verified in code):** real-money trading is fail-closed by the merged TASK-STR-001 guard (`ALLOW_LIVE_TRADING`, default false; `Stratex/exchanges/exchange_implementations.py`), and order placement requires an exchange "connect" first. So the realistic worst case is paper/testnet-ledger pollution, engine-state mutation, and unbounded CPU on the compute routes.
- **Recommendation:** require a Stratex API key on all state-changing routes (blueprint-level `before_request`), consistent with Forge and Inference. This also fulfils the standing TASK-API-003 auth-matrix direction. Low effort, high hygiene.

### B-3 LOW — Gateway hardening gaps (Caddy)

- **No HSTS:** a one-time `header Strict-Transport-Security "max-age=31536000"` closes protocol-downgrade risk for the FRIDAY control cookie.
- **No CSP** on the dashboard origin; the FRIDAY dashboard is a known static surface, so a conservative `default-src 'self'` policy with the needed `connect-src` is cheap to add.
- **`Server: uvicorn`** leaks implementation detail (informational).
- All three are one-file changes in `deploy/Caddyfile`.

### B-4 LOW — `/api/v1/dispatch/records/report` is anonymously readable

- **Evidence:** HTTP 200 with aggregate counters (currently all zero after the last restart). Read-only, no per-task data; acceptable, but it belongs behind the same key gate as the rest of the control API if the store ever holds sensitive result payloads. Note: the in-memory store resets on restart — durability lands with the planned Oracle persistence pass.

### B-5 VERIFIED SECURE (no action)

| Surface | Probe | Result |
|---|---|---|
| TLS | handshake | TLSv1.3, Let's Encrypt, expires 2027-01-12 |
| Control-session mint, no key | `GET /friday/api/control/session` | **401** — TASK-SEC-005 live |
| Control-session mint, forged `Origin` | same + `Origin: https://evil.example.com` | **403** — origin gate live |
| Control-session mint, wrong key | same + `x-friday-api-key: wrong` | **401** |
| Chat without key (remote) | `POST /friday/api/chat` | **401** — D-023 paste-once gate live |
| FRIDAY voice speak, forged origin | `POST /friday/api/voice/speak` | **403** |
| Forge task execution, no key | `POST /forge/api/v1/task/execute` | **401** |
| Inference completions, no key | `POST /inference/v1/chat/completions` | **401** (`X-INFERENCE-API-KEY` scheme) |
| Security headers | `GET /friday/` | `nosniff`, `SAMEORIGIN`, `strict-origin-when-cross-origin` present |
| FRIDAY laptop tunnel | code audit `FRIDAY/src/friday/remote/laptop_bridge.py` | control key/token required, command allow-list, `run_shell` double-gated on `FRIDAY_LAPTOP_ALLOW_SHELL` |

## 3. Positive-control notes

- All 401/403 assertions were confirmed against a live remote vantage point (this is not a code-review inference).
- The FRIDAY dashboard flow (paste key once → `fcs1` session → chat) was verified E2E in the 551aa77 session and again today at the gate level.

## 4. Required owner decisions (in order)

1. **Bridge auth (B-1):** activate `FRIDAY_BRIDGE_SHARED_SECRET` + `X-FRIDAY-BRIDGE-KEY` (recommendation: do it; this was pre-approved code merged as PR #24 and parked only because the surface was believed read-mostly). 
2. **Stratex route auth (B-2):** approve the blueprint-level key requirement (I can implement on direction).
3. **Caddy hardening (B-3):** approve the three-line Caddyfile change (can ship with the next deploy).

## Appendix A — Probe inventory

`scripts/val002_ingress_probes.py` (round 1): TLS handshake; gateway headers; control-session no-key / forged-origin / wrong-key; chat no-key; dispatch report; bridge initialize; Forge execute; Stratex consensus; Sentinel/Inference path discovery; voice-speak forged origin.
`scripts/val002_probes_round2.py` (round 2): Inference `/v1/chat/completions` 401; Stratex `/api/live/account|exchanges` anonymous 200s; bridge MCP session-id protocol + anonymous `tools/list` (33 tools captured); unknown-route behaviour.

## Appendix B — Raw anonymous bridge tool list (2026-11-10)

```
get_system_info, list_directory, read_file, edit_file, write_file, search_code,
run_workspace_test, git_status, git_diff, git_create_branch, git_commit, git_push,
github_create_pr, github_list_prs, github_get_pr_diff, github_comment_pr,
github_list_actions, oracle_fleet_health, oracle_memory_by_process,
oracle_check_service, oracle_get_logs, oracle_restart_service, oracle_caddy_reload,
oracle_curl_health, run_shell, read_text, github_api, github_list_runs,
github_run_logs, github_read_file, github_write_file
```
