# TASK-SEN-037 — Sentinel approval-path live proof run 3

**Task:** Sentinel: approval-path live proof run 3 — one low-risk action auto-approved + one high-risk action prompting on Telegram, each exactly once, with evidence.
**Owner:** Muse 4 · **Branch:** `muse4/task-sen-037-approval-path-live-proof-run-3`
**Claim:** hub #2045 comment 7209427563, 2026-11-27 ~09:29 IST, on assignment in coordinator WATCH200 (hub #2045 comment 7209314144, ~09:20 IST) §2: "M4 SEN-037". Board record on main still shows CLAIMED/muse_tp12 (TP12 released it, hub #2045 comment 7208104639; empty branch deleted, no commits; live leg NOT run) — board flips are coordinator-only; the AVAILABLE/owner muse_4 flip rides in coordinator board PR #2060. No board hunk in this PR.
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via `https://friday-universe.duckdns.org/sentinel` (Caddy). Service start: 2026-11-27 03:24:22 IST (restarted since run 2's 2026-11-24 18:49:12 start), single worker, `Sentinel.service` active.
**Run-2 reference:** TASK-SEN-036 (Muse 10, 2026-11-26, work PR #1971, MERGED) — same legs, same procedure; this run repeats it against the current deploy. Run-2 evidence: `docs/collaboration/TASK-SEN-036-APPROVAL-PATH-LIVE-PROOF-RUN-2.md`.
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`, `apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical (md5) to this repo on current main `cb57c8c8` — the code surveyed below is the code that ran:
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

Same four md5s as SEN-024 and SEN-036 surveyed — the approval path is unchanged since run 1. Server 1 git HEAD is `bf3c76c9`.

## Clearance for the live legs (why the legs were run, not held)

The Telegram leg prompts the owner, so the clearance question was decided explicitly before firing anything:

- **Standing clearance 7200564540** (coordinator ruling, hub #1483, 2026-11-27 ~00:05 IST): "STANDING LIVE-VERIFICATION CLEARANCE — CLEARANCE WAITING IS OVER. You no longer ask anyone before live-verifying your own task. Pre-approved fleet-wide... the live-verification run of YOUR OWN task on its agent." Only THREE things still need a ruling: moving an agent between servers, live money, destructive deletes. The Telegram prompt leg is none of those — it is a notification, not an execution (see "No executor on this path").
- **WATCH200 §4** (coordinator, 2026-11-27 ~09:20 IST) applies the clearance to live legs of this kind: "M16 DB-010/DB-012 live legs — HELD (transport + headroom), no clearance gap... Standing clearance 7200564540 already covers the legs" and "M1 VOI-029 session-1 preflight/launch: covered by standing clearance 7200564540 (own-task live verification). Proceed, no separate clearance."
- **WATCH200 §2** assigned SEN-037 to Muse 4 with the live-proof route ("live Sentinel approval path") and the acceptance line explicitly requires the Telegram-prompt leg.
- **SEN-036 precedent:** the exact same two leg actions were run by Muse 10 and the coordinator MERGED the result (work PR #1971, merge 0434f6df) knowing leg 2 sent a Telegram prompt to the owner.
- **Muse TP10's SEN-038 hold noted:** TP10's post (hub #2045 comment 7209381842, ~09:23 IST) holds the SEN-038 legs pending coordinator confirmation of the exact leg actions. That is TP10's own caution on SEN-038, not a coordinator ruling on SEN-037, and the standing clearance + WATCH200 §4 rulings above already answer the question fleet-wide ("CLEARANCE WAITING IS OVER"). No fresh confirmation was sought for SEN-037; the legs below were run under the standing clearance, each exactly once.

## How the approval path works (repo source, at cb57c8c8)

Same as SEN-021 / SEN-024 / SEN-036 (verified unchanged in the surveyed files):

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`.
  `classify_approval` returns `AUTO_APPROVE` only when ALL hold: caller risk claim is low (LOW / NONE / MINIMAL / ROUTINE); no hard-bound pattern (live-money, owner-data deletion, credential change, Sentinel-policy change); and the action positively matches the low-risk class — read-only leading verb with no write verb later, internal housekeeping, or caller-attested reversible. Anything else is `OWNER_PROMPT`; the policy never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`.
  `submit_approval` classifies first. Auto-approve: writes an `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger and only then marks the request APPROVED; if the ledger write fails it falls back to the owner prompt. Owner prompt: `_dispatch_notifications` sends the Telegram message via `_send_telegram` and records the request PENDING with approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`:
  `POST /api/v1/approvals/request` calls `submit_approval` and returns the pending record. `GET /api/v1/approvals/pending`, `GET /api/v1/approvals/{token}/status`. Approve/deny require an explicit POST from the confirmation form; the GET confirmation pages never change state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required (`X-API-Key` header). The live calls below were made from Server 1 itself by throwaway scripts that read the key from the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`, the same file the live service loads) and used it in-process only. The key value was never printed, copied, or stored anywhere; the scripts were deleted after the run. Approval **tokens** are likewise never reproduced in this document — requests are identified by `request_id` only. The leg-2 token was held in a file on Server 1 only, for the post-expiry check, and deleted after it.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`: `log_file_path = "logs/audit.jsonl"` → on Server 1, `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of `submit_approval` is the API endpoint above; no production code calls `wait_for_decision`. A submitted action is a *request record* only — nothing in the fleet executes an action because its approval record exists.

## Pre-flight checks (before either leg)

- Both Oracle servers ONLINE (`get_system_info`, 2026-11-27 ~09:34 IST).
- Sentinel `/health` 200: `audit_chain_valid: true`, `audit_chain_entries: 43`, `kill_switch_active: false`, `audit_durable: true` (2026-11-27 09:34 IST).
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle), `telegram_channel: true` — the SEN-022 startup self-check gate is live and passing in production (2026-11-27 09:34 IST).
- Telegram channel pre-check: `/ready` reports `telegram_channel: true`; no credential values were read, printed, or copied at any point.
- Classifier dry-run on the exact planned actions (repo code at cb57c8c8, md5-identical to the deployed code, no live effect): leg 1 → `AUTO_APPROVE / read_only`; leg 2 → `OWNER_PROMPT / caller_risk_not_low`.
- Pending list empty before the legs (`GET /api/v1/approvals/pending` → count 0, 2026-11-27 09:34 IST) — no other approval traffic.
- Journal (last hour before the legs) contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines.
- Server 1 load light at run time (load avg 0.01, up 43 days); no slow responses observed.
- Bridge transport note: the bridge was flaky earlier today (HTTP 406 on GET, POST initialize timeouts, per M16's 09:00 post, hub #2045 7209253630). This run's bridge calls worked first-try after deleting the stale session file and re-initializing. The legs script was run as a single no-retry call: a retry after a dropped response could have double-fired a leg.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `check sentinel health status`
- **Submitted by:** `MUSE_4`, `risk_level: LOW`, details `{"purpose": "TASK-SEN-037 leg 1 proof", "task": "TASK-SEN-037"}`
- **Submitted:** 2026-11-27 09:38:19 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`, `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-27T04:08:19.751454+00:00`, `decided_at 2026-11-27T04:08:19.799063+00:00` (~0.048 s later)
- **Request id:** `appr_38ae8f1fdc02`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy (TASK-SEN-019): read_only — Read-only action ('check ...') with a LOW caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`, exactly one entry for this request id:
  `seq 44`, `entry_id audit-appr-auto-appr_38ae8f1fdc02`, `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`, `target MUSE_4`, `action_type "check sentinel health status"`, `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`, `timestamp 2026-11-27T04:08:19.798032+00:00`, `previous_hash 9813315394101a9d9fe1f4677e3fa137f2c1ebed394065a5bedaacba4202d3b4` (chains onto the seq-43 tail entry — verified: seq-43 `current_hash` equals seq-44 `previous_hash`), `current_hash 5100084604a90475328bde4a81e532254cf808a3c2d985923939f43e411869ec`.
  Details: `policy_category read_only`, `risk_level LOW`.
- **Service journal:** `Nov 27 09:38:19 … Approval appr_38ae8f1fdc02 (check sentinel health status by MUSE_4) AUTO-APPROVED [read_only]`
- **Cross-check:** `/health` audit entry count 43 → 44 after the leg (seq 44 is this auto-approval); `audit_chain_valid: true`.

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `deploy sentinel configuration change to production`
- **Submitted by:** `MUSE_4`, `risk_level: HIGH`, details `{"purpose": "TASK-SEN-037 leg 2 proof, prompt only", "task": "TASK-SEN-037"}`
- **Submitted:** 2026-11-27 09:38:19 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`, `policy_category: caller_risk_not_low`, `decided_at: null`, `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-27T04:08:19.807298+00:00`, `expires_at 2026-11-27T04:13:19.807299+00:00` (09:43:19 IST)
- **Request id:** `appr_a16924903e2e`
- **Recorded in the live service:** the request appears in `GET /api/v1/approvals/pending` (HTTP 200) with the same fields — it is held in the running process's pending map awaiting a decision. The pending list contained exactly this one item.
- **Telegram prompt — what was sent:** `_dispatch_notifications` (`approval_dispatcher.py`) builds this message from the template with the live values and sends it via `_send_telegram` because the channel is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_4`
  > **Action:** `deploy sentinel configuration change to production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-037 leg 2 proof, prompt only", "task": "TASK-SEN-037"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: `/ready` reports `telegram_channel: true` (SEN-022 gate).
  - The submission ran `_dispatch_notifications` synchronously inside `submit_approval`; the code only skips Telegram when the channel is unconfigured (it was configured) and only logs on transport failure.
  - Service journal 09:37:00–09:41:00 IST contains **no** `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback) and **no** `Telegram notification dispatch error` line.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 09:38:19 IST; the synchronous Telegram `urlopen` completed inside that call with no error logged.
  - The Telegram `message_id` is **not observable** from this side: `_send_telegram` discards the API response and returns only a boolean, which is not logged on success. Delivery to Surendra's Telegram client is therefore asserted from the configured channel + clean dispatch path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 4 anywhere: no POST to `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction, no `decide()` call. At submission the record showed `decided_at: null`.
- The action was never a command: the approval request is a record only (see "No executor on this path"). No deploy command was issued to any host, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 09:43:19 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-27 09:44:49 IST, after `expires_at` 09:43:19 IST, token recovered server-side from the Server 1 file (never printed or copied out; file deleted after the check).
  - `GET /api/v1/approvals/{token}/status` → 200: record still stored as `PENDING`, `decided_at: null`, `decision_reason: null` — no decision was ever recorded.
  - `GET /api/v1/approvals/pending` → 200: `[]` — the request is gone from the actionable pending list. (`get_pending_list` returns only non-expired pending approvals, so the empty list is itself the expiry-gate evidence: the request is no longer actionable.)
  - `GET /api/v1/approvals/{token}/approve` (the read-only confirmation page, which never changes state) → **HTTP 401 "An API key is required"** — NOT the 409 run 2 recorded. Cause: my check script sent this one call without the `X-API-Key` header (a script error, not a service behaviour — the approvals endpoints require the key). The token file had already been deleted by the script's cleanup before a retry with auth could be run, so the 409 re-check could not be repeated and the token is unrecoverable by design (random, never printed). The expiry is still established by the empty pending list + the un-decided stored record; the 409 page check is the one step that did not complete — see "What was NOT verified".
  - Semantics note: the stored `status` field only transitions when `decide()` or `wait_for_decision()` runs; the live gate is the `is_expired()` check enforced by the approve/deny paths (and by `get_pending_list`). The code path was read first-hand in this run: the GET approve page returns 409 "Approval no longer pending" when `is_expired()` is true, and `decide()` marks an expired request EXPIRED instead of deciding it.
- **Hash-chain linkage verified:** seq-43 `current_hash` `9813315394101a9d9fe1f4677e3fa137f2c1ebed394065a5bedaacba4202d3b4` equals seq-44 `previous_hash` — CHAIN-LINKED: True.
- **No-execution corroboration:** `Sentinel.service` still `active` with the same start timestamp (`Fri 2026-11-27 03:24:22 IST`) — no restart; S1 `/opt/friday_universe` git HEAD unchanged at `bf3c76c9` — no deploy; journal 09:37–09:44 IST contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines.
- **Cleanup:** the leg-2 token file, the legs output file, and all throwaway scripts on Server 1 were deleted after this check (`ls /tmp/sen037_*` → no such file).

## What was NOT verified

- **Telegram message id / device receipt:** the dispatcher does not log or return the Telegram `message_id`, so the exact message id and confirmation that the message rendered on Surendra's device cannot be established from the server side. The prompt's dispatch is evidenced by the configured channel, the synchronous send inside the 200-OK submission, and the absence of any dispatch-error or offline-queue log line. If Muse or Surendra eyeball the Telegram client, the message above should be visible there.
- **Approve-page 409 after expiry:** the read-only GET approve-page check returned 401 (missing API key in the check script) instead of run 2's 409, and the Server-1-only token file was deleted before a retry could run, so the 409 could not be re-verified this run. Expiry is established instead by the empty pending list (`get_pending_list` returns only non-expired items) and the un-decided stored record, and the 409 branch was read first-hand in the deployed code (`is_expired()` → 409 "Approval no longer pending").
- **Ledger re-verification after the legs:** the file ledger entry for leg 1 was verified by hash linkage (seq-43 `current_hash` = seq-44 `previous_hash`); a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the legs and contained only the leg-2 request after it; earlier pending history was not audited.

— Muse 4
