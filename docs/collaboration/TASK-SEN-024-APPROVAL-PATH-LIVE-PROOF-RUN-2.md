# TASK-SEN-024 — Sentinel approval-path live proof run 2

**Task:** Sentinel: approval-path live proof run 2 — one low-risk auto-approval
+ one high-risk Telegram prompt, each exactly once, with evidence.
**Owner:** Muse 13 · **Branch:** `muse13/task-sen-024-approval-path-live-proof-run-2`
**Claim:** hub #1483 comment 7117868562, 2026-11-24 ~05:45 IST, on assignment in
coordinator watch ~05:20 IST (board PR watch006 #1588).
**Claim PR:** #1593, merged bb102ac2 (CI 9/9, coordinator watch ~06:35 IST).
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via
`https://friday-universe.duckdns.org/sentinel` (Caddy). Service start:
2026-11-24 00:00:48 IST, single worker, `Sentinel.service` active.
**Run-1 reference:** TASK-SEN-021 (Muse 9, 2026-11-22) — same legs, same
procedure; this run repeats it against the current deploy.
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`,
`apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical
(md5) to this repo at S1 HEAD `45b8fbba` — the code surveyed below is the
code that ran:
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

## How the approval path works (repo source, at 45b8fbba)

Same as SEN-021 (verified unchanged in the surveyed files):

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`.
  `classify_approval` returns `AUTO_APPROVE` only when ALL hold: caller risk
  claim is low (LOW / NONE / MINIMAL / ROUTINE); no hard-bound pattern
  (live-money, owner-data deletion, credential change, Sentinel-policy
  change); and the action positively matches the low-risk class — read-only
  leading verb with no write verb later, internal housekeeping, or
  caller-attested reversible. Anything else is `OWNER_PROMPT`; the policy
  never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`.
  `submit_approval` classifies first. Auto-approve: writes an
  `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger and only
  then marks the request APPROVED; if the ledger write fails it falls back
  to the owner prompt. Owner prompt: `_dispatch_notifications` sends the
  Telegram message via `_send_telegram` and records the request PENDING with
  approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`:
  `POST /api/v1/approvals/request` calls `submit_approval` and returns the
  pending record. `GET /api/v1/approvals/pending`,
  `GET /api/v1/approvals/{token}/status`. Approve/deny require an explicit
  POST from the confirmation form; the GET confirmation pages never change
  state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals
  endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required
  (`X-API-Key` header). The live calls below were made from Server 1 itself
  by throwaway scripts that read the key from the systemd `EnvironmentFile`
  (`/opt/friday_universe/Sentinel/.env`, the same file the live service
  loads) and used it in-process only. The key value was never printed,
  copied, or stored anywhere; the scripts were deleted after the run.
  Approval **tokens** (bearer approve/deny credentials) are likewise never
  reproduced in this document — requests are identified by `request_id`
  only. The leg-2 token was held in a file on Server 1 only, for the
  post-expiry check, and deleted after it.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`:
  `log_file_path = "logs/audit.jsonl"` → on Server 1,
  `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of
  `submit_approval` is the API endpoint above; no production code calls
  `wait_for_decision`. A submitted action is a *request record* only —
  nothing in the fleet executes an action because its approval record
  exists.

## Pre-flight checks (before either leg)

- Both Oracle servers ONLINE (`get_system_info`, 2026-11-24 ~06:43 IST).
- Sentinel `/health` 200: `audit_chain_valid: true`,
  `audit_chain_entries: 26`, `kill_switch_active: false`,
  `audit_durable: true` (2026-11-24 06:43 IST).
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle),
  `telegram_channel: true` — the SEN-022 startup self-check gate is live
  and passing in production (2026-11-24 06:43 IST).
- Telegram channel pre-check: `/ready` reports `telegram_channel: true`;
  no credential values were read, printed, or copied at any point.
- Classifier dry-run on the exact planned actions (repo code at 45b8fbba,
  no live effect): leg 1 → `AUTO_APPROVE / read_only`; leg 2 →
  `OWNER_PROMPT / caller_risk_not_low`.
- Pending list empty before the legs (`GET /api/v1/approvals/pending` →
  count 0, 2026-11-24 06:55 IST) — no other approval traffic.
- **Load note (observed, not a blocker):** Server 1 was under heavy load
  during the run (load avg ~4, 69 MB free of 956 MB; a `pytest` suite run
  started 06:43 IST plus the Stratex autonomy daemon at ~45% CPU). Sentinel
  answered slowly for ~10 minutes (a `/health` took ~5 s; three calls
  timed out client-side at 10–60 s while the server still logged them 200
  OK — the service never stopped, the clients gave up first). Retrying
  with 120 s timeouts succeeded. No service restart was needed or done.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `check sentinel health status`
- **Submitted by:** `MUSE_13`, `risk_level: LOW`,
  details `{"purpose": "TASK-SEN-024 leg 1 proof", "task": "TASK-SEN-024"}`
- **Submitted:** 2026-11-24 06:55:58–06:55:59 IST (one `POST
  /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`,
  `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-24T01:25:58.811254+00:00`,
  `decided_at 2026-11-24T01:25:59.115077+00:00` (~0.3 s later)
- **Request id:** `appr_63363018106b`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy
  (TASK-SEN-019): read_only — Read-only action ('check ...') with a LOW
  caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`,
  exactly one entry for this request id:
  `seq 27`, `entry_id audit-appr-auto-appr_63363018106b`,
  `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`,
  `target MUSE_13`, `action_type "check sentinel health status"`,
  `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`,
  `timestamp 2026-11-24T01:25:58.922186+00:00`,
  `previous_hash 2cb58b5a955a938e6e8ce65769f5ae7b4ba4ea0d0985a9f90517a9c1992c6f87`
  (chains onto the seq-26 tail entry, a `TLS_CERT_ALERT`),
  `current_hash f5cc848536b8ec3fd57b4f4170e4200792551ac2d29df265fe8f0208aaf0efbb`.
  Details: `policy_category read_only`, `risk_level LOW`.
- **Service journal:** `Nov 24 06:55:59 … Approval appr_63363018106b
  (check sentinel health status by MUSE_13) AUTO-APPROVED [read_only]`
  (confirmed in the post-expiry journal read).
- **Cross-check:** `/audit` entry count 26 → 27 after the leg (seq 27 is
  this auto-approval).

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `deploy sentinel configuration change to production`
- **Submitted by:** `MUSE_13`, `risk_level: HIGH`,
  details `{"purpose": "TASK-SEN-024 leg 2 proof, prompt only",
  "task": "TASK-SEN-024"}`
- **Submitted:** 2026-11-24 06:57:20–06:57:22 IST (one `POST
  /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`,
  `policy_category: caller_risk_not_low`, `decided_at: null`,
  `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-24T01:27:20.206518+00:00`,
  `expires_at 2026-11-24T01:32:20.206519+00:00` (07:02:20 IST)
- **Request id:** `appr_675d3e155b9d`
- **Recorded in the live service:** the request appears in
  `GET /api/v1/approvals/pending` (HTTP 200) with the same fields —
  it is held in the running process's pending map awaiting a decision.
  The pending list contained exactly this one item.
- **Telegram prompt — what was sent:** `_dispatch_notifications`
  (`approval_dispatcher.py`) builds this message from the template with
  the live values and sends it via `_send_telegram` because the channel
  is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_13`
  > **Action:** `deploy sentinel configuration change to production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-024 leg 2 proof, prompt only", "task": "TASK-SEN-024"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: `/ready` reports `telegram_channel: true` (SEN-022 gate).
  - The submission ran `_dispatch_notifications` synchronously inside
    `submit_approval`; the code only skips Telegram when the channel is
    unconfigured (it was configured) and only logs on transport failure.
  - Service journal 06:56:00–07:00:00 IST contains **no**
    `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback)
    and **no** `Telegram notification dispatch error` line.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 06:57:22 IST;
    the synchronous Telegram `urlopen` completed inside that call with no
    error logged.
  - The Telegram `message_id` is **not observable** from this side:
    `_send_telegram` discards the API response and returns only a boolean,
    which is not logged on success. Delivery to Surendra's Telegram client
    is therefore asserted from the configured channel + clean dispatch
    path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 13 anywhere: no POST to
  `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction,
  no `decide()` call. At submission the record showed `decided_at: null`.
- The action was never a command: the approval request is a record only
  (see "No executor on this path"). No deploy command was issued to any
  host, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 07:02:20 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-24 07:02:56 IST, after `expires_at` 07:02:20 IST,
  token recovered server-side from the Server 1 file (never printed or
  copied out; file deleted after the check).
  - `GET /api/v1/approvals/{token}/status` → 200: record still stored as
    `PENDING`, `decided_at: null`, `decision_reason: null` — no decision
    was ever recorded.
  - `GET /api/v1/approvals/pending` → 200: `[]` — the request is gone
    from the actionable pending list.
  - `GET /api/v1/approvals/{token}/approve` (the read-only confirmation
    page, which never changes state) → **HTTP 409 "Approval no longer
    pending"** — the approve link is dead.
  - Semantics note: the stored `status` field only transitions when
    `decide()` or `wait_for_decision()` runs; the live gate is the
    `is_expired()` check enforced by the approve/deny paths. The 409
    proves that gate is closed.
- **No-execution corroboration:** `Sentinel.service` still `active` with
  the same start timestamp (`Tue 2026-11-24 00:00:48 IST`) — no restart;
  S1 `/opt/friday_universe` git HEAD unchanged at `45b8fbba` — no deploy;
  journal 06:56–07:00 IST contains zero `Telegram notification dispatch
  error` / `[SENTINEL APPROVAL QUEUED]` lines.
- **Cleanup:** the leg-2 token file and all throwaway scripts on Server 1
  were deleted after this check.

## What was NOT verified

- **Telegram message id / device receipt:** the dispatcher does not log
  or return the Telegram `message_id`, so the exact message id and
  confirmation that the message rendered on Surendra's device cannot be
  established from the server side. The prompt's dispatch is evidenced by
  the configured channel, the synchronous send inside the 200-OK
  submission, and the absence of any dispatch-error or offline-queue log
  line. If Muse or Surendra eyeball the Telegram client, the message
  above should be visible there.
- **Ledger re-verification after the legs:** the file ledger entry for
  leg 1 was verified by hash linkage (previous hash = seq-26 tail hash);
  a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the
  legs and contained only the leg-2 request after it; earlier pending
  history was not audited.

— Muse 13
