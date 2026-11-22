# TASK-SEN-021 — Live proof of Sentinel's approval path

**Task:** Sentinel: live proof of the approval path — one low-risk action auto-approved
and one high-risk action prompting on Telegram, each exactly once, with evidence.
**Owner:** Muse 9 · **Branch:** `muse9/task-sen-021-claim` · **Date:** 2026-11-22
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via
`https://friday-universe.duckdns.org/sentinel` (Caddy). Service start:
2026-11-22 13:13:26 IST, single worker, `Sentinel.service` active.
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`,
`apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical
(md5) to this repo at `origin/main` `4dacbed` — the code surveyed below is
the code that ran.

## How the approval path works (repo source)

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`.
  `classify_approval` (line 306) returns `AUTO_APPROVE` only when ALL hold:
  caller risk claim is low (`_LOW_RISK_CLAIMS`, line 123: LOW / NONE /
  MINIMAL / ROUTINE); no hard-bound pattern (`_hard_bound_category`, line
  253: live-money, line 264; owner-data deletion, line 273; credential
  change; Sentinel-policy change); and the action positively matches the
  low-risk class — read-only leading verb with no write verb later
  (line 396), internal housekeeping, or caller-attested reversible.
  Anything else is `OWNER_PROMPT`; the policy never downgrades a caller
  claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`.
  `submit_approval` (line 261) classifies first. Auto-approve: writes an
  `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger via
  `_record_auto_approval` (line 417; `event_type="APPROVAL_AUTO_APPROVED"`,
  line 428) and only then marks the request APPROVED; if the ledger write
  fails it falls back to the owner prompt. Owner prompt: `_dispatch_notifications`
  (line 556) sends the Telegram message via `_send_telegram` (line 586,
  `POST https://api.telegram.org/bot<token>/sendMessage`) and records the
  request PENDING with approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`:
  `POST /api/v1/approvals/request` (line 2145, payload `ApprovalRequestPayload`,
  line 2138) calls `submit_approval` and returns the pending record.
  `GET /api/v1/approvals/pending` (line 2156), `GET /api/v1/approvals/{token}/status`
  (line 2160). Approve/deny require an explicit POST from the confirmation
  form (lines 2193, 2230); the GET confirmation pages (lines 2167, 2205)
  never change state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals
  endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required
  (lines 267–280, `X-API-Key` header, line 260). The live calls below were
  made from Server 1 itself by a throwaway script that read the key from
  the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`,
  the same file the live service loads) and used it in-process only.
  The key value was never printed, copied, or stored anywhere; the script
  was deleted after the run. Approval **tokens** (bearer approve/deny
  credentials) are likewise never reproduced in this document — requests
  are identified by `request_id` only.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py` line 289:
  `log_file_path = "logs/audit.jsonl"` → on Server 1,
  `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of
  `submit_approval` is the API endpoint above; no production code calls
  `wait_for_decision`. A submitted action is a *request record* only —
  nothing in the fleet executes an action because its approval record
  exists. Execution would require a caller awaiting the decision, and
  there is none on this path.

## Pre-flight checks (before either leg)

- Both Oracle servers ONLINE (`get_system_info`, 2026-11-22 ~15:41 IST).
- Sentinel `/health` 200: `audit_chain_valid: true`, `audit_chain_entries: 8`,
  `kill_switch_active: false`; `/ready` 200, `READY`, database `connected`
  (Oracle). (2026-11-22 15:43 IST.)
- Telegram channel pre-check (booleans only, same credential resolution as
  the live process): bot token present = true, chat id present = true,
  Discord = false, `channel_configured` = true.
- Classifier dry-run on the exact planned actions (repo code, no live
  effect): leg 1 → `AUTO_APPROVE / read_only`; leg 2 →
  `OWNER_PROMPT / caller_risk_not_low`.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `check sentinel health status`
- **Submitted by:** `MUSE_9`, `risk_level: LOW`,
  details `{"purpose": "TASK-SEN-021 leg 1 proof", "task": "TASK-SEN-021"}`
- **Submitted:** 2026-11-22 15:46:17–15:46:31 IST (one `POST
  /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`,
  `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-22T10:16:25.504566+00:00`,
  `decided_at 2026-11-22T10:16:26.004678+00:00` (~0.5 s later)
- **Request id:** `appr_a4635461c13a`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy
  (TASK-SEN-019): read_only — Read-only action ('check ...') with a LOW
  caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`,
  exactly one entry for this request id:
  `seq 9`, `entry_id audit-appr-auto-appr_a4635461c13a`,
  `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`,
  `target MUSE_9`, `action_type "check sentinel health status"`,
  `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`,
  `timestamp 2026-11-22T10:16:25.797906+00:00`,
  `previous_hash a4f597f5d5daca59525dc2f1993d90ca6f542b5ca4101c63a152724f21a5d7cc`
  (chains onto the prior tail entry, seq 8),
  `current_hash a71153284265a5b74531b31f8930745096935c04e2ab49922fb84d082d4c3e2b`.
  Details: `policy_category read_only`, `risk_level LOW`.
- **Service journal:** `Nov 22 15:46:26 … Approval appr_a4635461c13a
  (check sentinel health status by MUSE_9) AUTO-APPROVED [read_only]`.
- **Cross-check:** `/audit` entry count 8 → 10 after the leg (seq 9 is this
  auto-approval; seq 10 is an unrelated periodic `TLS_CERT_ALERT` from the
  TLS daemon). Note: the `/audit` endpoint's `last_hash` field lags the
  file tail (it still reported the seq-7 hash); the file ledger above is
  the authoritative chain and it verifies by hash linkage.

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `deploy sentinel configuration change to production`
- **Submitted by:** `MUSE_9`, `risk_level: HIGH`,
  details `{"purpose": "TASK-SEN-021 leg 2 proof, prompt only",
  "task": "TASK-SEN-021"}`
- **Submitted:** 2026-11-22 15:47:06–15:47:09 IST (one `POST
  /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`,
  `policy_category: caller_risk_not_low`, `decided_at: null`,
  `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-22T10:17:07.810410+00:00`,
  `expires_at 2026-11-22T10:22:07.810411+00:00` (15:52:07 IST)
- **Request id:** `appr_dc8dd002eae0`
- **Recorded in the live service:** the request appears in
  `GET /api/v1/approvals/pending` (HTTP 200) with the same fields —
  it is held in the running process's pending map awaiting a decision.
- **Telegram prompt — what was sent:** `_dispatch_notifications`
  (`approval_dispatcher.py` lines 556–585) builds this message from the
  template (lines 564–571) with the live values and sends it via
  `_send_telegram` because the channel is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_9`
  > **Action:** `deploy sentinel configuration change to production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-021 leg 2 proof, prompt only", "task": "TASK-SEN-021"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: Telegram bot token + chat id resolve, `channel_configured = true`.
  - The submission ran `_dispatch_notifications` synchronously inside
    `submit_approval`; the code only skips Telegram when the channel is
    unconfigured (it was configured) and only logs on transport failure.
  - Service journal 15:46:00–15:49:00 IST contains **no**
    `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback)
    and **no** `Telegram notification dispatch error` line.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 15:47:09 IST;
    the synchronous Telegram `urlopen` (5 s timeout) completed inside that
    call with no error logged.
  - The Telegram `message_id` is **not observable** from this side:
    `_send_telegram` discards the API response and returns only a boolean,
    which is not logged on success. Delivery to Surendra's Telegram client
    is therefore asserted from the configured channel + clean dispatch
    path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 9 anywhere: no POST to
  `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction,
  no `decide()` call. At submission the record showed `decided_at: null`.
- The action was never a command: the approval request is a record only
  (see "No executor on this path"). No deploy command was issued to any
  host, no file was written, no service was restarted.
- **Post-expiry check** (2026-11-22 15:52:39 IST, after `expires_at`
  15:52:07 IST), token recovered server-side from the service journal
  (never printed or copied out):
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
    `is_expired()` check enforced by the approve/deny paths
    (`main.py` lines 2177, 2214). The 409 proves that gate is closed.
- **No-execution corroboration:** `Sentinel.service` still `active` with
  the same start timestamp (`Sun 2026-11-22 13:13:26 IST`) — no restart;
  `/opt/friday_universe` git HEAD unchanged at `e6ca8d2f` — no deploy;
  journal 15:47–15:53 IST contains zero `Telegram notification dispatch
  error` / `[SENTINEL APPROVAL QUEUED]` lines.

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
  leg 1 was verified by hash linkage (previous hash = seq-8 tail hash);
  a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty of other
  items at leg-2 check time (the list contained only `appr_dc8dd002eae0`);
  earlier pending history was not audited.
