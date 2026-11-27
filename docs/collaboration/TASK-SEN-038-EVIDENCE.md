# TASK-SEN-038 — Sentinel approval-path live proof run 4

**Task:** Sentinel: approval-path live proof run 4 — one low-risk action auto-approved and one high-risk action prompting on Telegram, each exactly once, with evidence.
**Owner:** Muse TP10 · **Branch:** `musetp10/task-sen-038`
**Claim:** hub #2045 comment 7208545276, 2026-11-27 ~08:30 IST (stall repair: board CLAIMED since 07:55 IST with no worker branch/claim post). Checkpoint 1 `1dbc72f0`, checkpoint 2 `2943edeb`. Board on main `c334f212` (blob `3461901d`): TASK-SEN-038 CLAIMED / muse_tp10 / branch `musetp10/task-sen-038` / pr null; TASK-VOI-045 AVAILABLE / muse_tp10 (pre-staged second). No board hunk in this PR — board flips are coordinator-only.
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via `https://friday-universe.duckdns.org/sentinel` (Caddy). Service start: 2026-11-27 03:24:22 IST, single worker, `Sentinel.service` active (unchanged across the run — no restart).
**Run-3 reference:** TASK-SEN-037 (Muse 4, 2026-11-27, work PR #2065) — same legs, same procedure; this run repeats it against the current deploy. Run-2 evidence: `docs/collaboration/TASK-SEN-036-APPROVAL-PATH-LIVE-PROOF-RUN-2.md`.
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`, `apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical (md5) to the surveyed code — the code below is the code that ran:
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

Same four md5s as SEN-024, SEN-036 and SEN-037 surveyed — the approval path is unchanged since run 1. Server 1 git HEAD is `bf3c76c9` (unchanged before and after the legs). Repo source blobs on main `c334f212`: `approval_policy.py` `8c55456c`, `approval_dispatcher.py` `2d8f81ea`, `apps/api/main.py` `97f4eddd`.

## Clearance for the live legs (why the legs were run, not held)

The Telegram leg prompts the owner, so the clearance question was decided explicitly before firing anything:

- **Checkpoint 2 hold:** TP10 held both legs pending coordinator confirmation of the exact leg actions (hub #2045 comment 7209381842, 2026-11-27 ~09:23 IST).
- **WATCH201 §3** (coordinator, hub #2045 comment 7209660625, 2026-11-27 ~09:46 IST): "TP10 SEN-038 legs — CONFIRMED, both, as specified (hub 7209381842). Leg 1 `check sentinel health status` (LOW, expect AUTO_APPROVE/read_only) is read-only under standing clearance 7200564540. Leg 2 `deploy sentinel configuration change to production` (HIGH) fires exactly once as the designed approval-path probe: the owner is prompted on Telegram, 5-min expiry, nothing executes without his tap. If the Telegram prompt does not arrive in the window, report and stop — do not re-fire. Owner: Muse TP10, due next status post."
- **Standing clearance 7200564540** (coordinator ruling, hub #1483, 2026-11-27 ~00:05 IST) covers own-task live verification; only server moves, live money and destructive deletes still need a ruling. The Telegram prompt leg is none of those — it is a notification, not an execution (see "No executor on this path").
- Coordination post filed before any server call: hub #2045 comment 7210209558 (2026-11-27 10:25 IST). Legs were then run exactly once each in a single no-retry batch (a retry after a dropped response could have double-fired a leg).

## How the approval path works (repo source)

Same as SEN-021 / SEN-024 / SEN-036 / SEN-037 (verified unchanged in the surveyed files):

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`. `classify_approval` returns `AUTO_APPROVE` only when ALL hold: caller risk claim is low (LOW / NONE / MINIMAL / ROUTINE); no hard-bound pattern (live-money, owner-data deletion, credential change, Sentinel-policy change); and the action positively matches the low-risk class — read-only leading verb with no write verb later, internal housekeeping, or caller-attested reversible. Anything else is `OWNER_PROMPT`; the policy never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`. `submit_approval` classifies first. Auto-approve: writes an `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger and only then marks the request APPROVED; if the ledger write fails it falls back to the owner prompt. Owner prompt: `_dispatch_notifications` sends the Telegram message via `_send_telegram` and records the request PENDING with approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`: `POST /api/v1/approvals/request` calls `submit_approval` and returns the pending record. `GET /api/v1/approvals/pending`, `GET /api/v1/approvals/{token}/status`. Approve/deny require an explicit POST from the confirmation form; the GET confirmation pages never change state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required (`X-API-Key` header). The live calls below were made from Server 1 itself by throwaway scripts that read the key from the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`, the same file the live service loads) and used it in-process only. The key value was never printed, copied, or stored anywhere; the scripts were deleted after the run. Approval **tokens** are likewise never reproduced in this document — requests are identified by `request_id` only. The leg-2 token was held in a file on Server 1 only, for the post-expiry check, and deleted after it.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`: `log_file_path = "logs/audit.jsonl"` → on Server 1, `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of `submit_approval` is the API endpoint above; no production code calls `wait_for_decision`. A submitted action is a *request record* only — nothing in the fleet executes an action because its approval record exists.

## Pre-flight checks (before either leg, 2026-11-27 ~10:27 IST)

- Both Oracle servers ONLINE (`get_system_info`); Server 1 load light (load avg 0.07, 285 MB available of 956 MB).
- `Sentinel.service` active, started 2026-11-27 03:24:22 IST; port 8008 listening (`0.0.0.0:8008`).
- Sentinel `/health` 200: `audit_chain_valid: true`, `audit_chain_entries: 44`, `kill_switch_active: false`, `audit_durable: true`.
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle), `telegram_channel: true` — the SEN-022 startup self-check gate is live and passing in production.
- Telegram channel pre-check: `/ready` reports `telegram_channel: true`; no credential values were read, printed, or copied at any point.
- Classifier dry-run on the exact planned actions (deployed code on Server 1, no live effect): leg 1 → `AUTO_APPROVE / read_only`; leg 2 → `OWNER_PROMPT / caller_risk_not_low`.
- Pending list empty before the legs (`GET /api/v1/approvals/pending` → count 0) — no other approval traffic.
- Journal (last hour before the legs) contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `check sentinel health status`
- **Submitted by:** `MUSE_TP10`, `risk_level: LOW`, details `{"purpose": "TASK-SEN-038 leg 1 proof", "task": "TASK-SEN-038"}`
- **Submitted:** 2026-11-27 10:27:53 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`, `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-27T04:57:53.895943+00:00`, `decided_at 2026-11-27T04:57:53.923197+00:00` (~0.027 s later)
- **Request id:** `appr_7d1dd4bcea93`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy (TASK-SEN-019): read_only — Read-only action ('check ...') with a LOW caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`, exactly one entry for this request id:
  `seq 45`, `entry_id audit-appr-auto-appr_7d1dd4bcea93`, `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`, `target MUSE_TP10`, `action_type "check sentinel health status"`, `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`, `timestamp 2026-11-27T04:57:53.907836+00:00`, `previous_hash 5100084604a90475328bde4a81e532254cf808a3c2d985923939f43e411869ec` (chains onto the seq-44 tail entry — verified: seq-44 `current_hash` equals seq-45 `previous_hash`), `current_hash cce3429eab069b58208f935cb7c48cd8e7a17b9b64af5bf4a2754b9512a0a7f4`.
  Details: `policy_category read_only`, `risk_level LOW`.
- **Service journal:** `Nov 27 10:27:53 … Approval appr_7d1dd4bcea93 (check sentinel health status by MUSE_TP10) AUTO-APPROVED [read_only]`
- **Cross-check:** `/health` audit entry count 44 → 45 after the leg (seq 45 is this auto-approval); `audit_chain_valid: true`.

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `deploy sentinel configuration change to production`
- **Submitted by:** `MUSE_TP10`, `risk_level: HIGH`, details `{"purpose": "TASK-SEN-038 leg 2 proof, prompt only", "task": "TASK-SEN-038"}`
- **Submitted:** 2026-11-27 10:27:54 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`, `policy_category: caller_risk_not_low`, `decided_at: null`, `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-27T04:57:54.001787+00:00`, `expires_at 2026-11-27T05:02:54.001787+00:00` (10:32:54 IST)
- **Request id:** `appr_f67fa3da39c1`
- **Recorded in the live service:** the request appears in `GET /api/v1/approvals/pending` (HTTP 200) with the same fields — it is held in the running process's pending map awaiting a decision. The pending list contained exactly this one item.
- **Telegram prompt — what was sent:** `_dispatch_notifications` (`approval_dispatcher.py`) builds this message from the template with the live values and sends it via `_send_telegram` because the channel is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_TP10`
  > **Action:** `deploy sentinel configuration change to production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-038 leg 2 proof, prompt only", "task": "TASK-SEN-038"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: `/ready` reports `telegram_channel: true` (SEN-022 gate).
  - The submission ran `_dispatch_notifications` synchronously inside `submit_approval`; the code only skips Telegram when the channel is unconfigured (it was configured) and only logs on transport failure.
  - Service journal 10:27:00 IST onward contains **no** `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback) and **no** `Telegram notification dispatch error` line.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 10:27:54 IST; the synchronous Telegram `urlopen` completed inside that call with no error logged.
  - The Telegram `message_id` is **not observable** from this side: `_send_telegram` discards the API response and returns only a boolean, which is not logged on success. Delivery to Surendra's Telegram client is therefore asserted from the configured channel + clean dispatch path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse TP10 anywhere: no POST to `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction, no `decide()` call. At submission the record showed `decided_at: null`, and the post-expiry check (below) still shows `decided_at: null` — no decision was ever recorded by anyone.
- The action was never a command: the approval request is a record only (see "No executor on this path"). No deploy command was issued to any host, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 10:32:54 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-27 10:33 IST, after `expires_at` 10:32:54 IST, token recovered server-side from the Server 1 file (never printed or copied out; file deleted after the check).
  - `GET /api/v1/approvals/{token}/status` → 200: record still stored as `PENDING`, `decided_at: null`, `decision_reason: null` — no decision was ever recorded.
  - `GET /api/v1/approvals/pending` → 200: `[]` — the request is gone from the actionable pending list.
  - `GET /api/v1/approvals/{token}/approve` (the read-only confirmation page, which never changes state; sent with the `X-API-Key` header) → **HTTP 409 "Approval no longer pending"** — the approve link is dead.
  - Semantics note: the stored `status` field only transitions when `decide()` or `wait_for_decision()` runs; the live gate is the `is_expired()` check enforced by the approve/deny paths. The 409 proves that gate is closed.
- **Hash-chain linkage verified:** seq-44 `current_hash` `5100084604a90475328bde4a81e532254cf808a3c2d985923939f43e411869ec` equals seq-45 `previous_hash` — CHAIN-LINKED: True.
- **No-execution corroboration:** `Sentinel.service` still `active` with the same start timestamp (`Fri 2026-11-27 03:24:22 IST`) — no restart; S1 `/opt/friday_universe` git HEAD unchanged at `bf3c76c9` — no deploy; journal 10:27 IST onward contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines.
- **Cleanup:** the leg-2 token file and all throwaway scripts on Server 1 were deleted after this check (`ls /tmp/sen038_*` → no such file).

## What was NOT verified

- **Telegram message id / device receipt:** the dispatcher does not log or return the Telegram `message_id`, so the exact message id and confirmation that the message rendered on Surendra's device cannot be established from the server side. The prompt's dispatch is evidenced by the configured channel, the synchronous send inside the 200-OK submission, and the absence of any dispatch-error or offline-queue log line. If Muse or Surendra eyeball the Telegram client, the message above should be visible there.
- **Ledger re-verification after the legs:** the file ledger entry for leg 1 was verified by hash linkage (seq-44 `current_hash` = seq-45 `previous_hash`); a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the legs and contained only the leg-2 request after it; earlier pending history was not audited.

## Five states

- implemented: YES (this evidence doc filed on branch `musetp10/task-sen-038`)
- tested: YES (both live legs run exactly once against live Sentinel on Server 1, outcomes above)
- merged: NO (work PR open at filing; peer merge owed — never merge own PR)
- deployed: NO (nothing deployed; proof ran against the existing deploy, service unchanged)
- production-verified: NO (paired verification by a different chat owed before this counts)

Usage: 11% of free weekly limit (resets Dec 2 6:34 PM IST).

— Muse TP10
