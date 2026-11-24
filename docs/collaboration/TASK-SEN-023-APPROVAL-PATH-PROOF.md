# TASK-SEN-023 — Sentinel approval-path live proof

**Task:** Sentinel: live approval-path proof — one low-risk action auto-approved
and one high-risk action prompting on Telegram, each exactly once, with evidence.
**Owner:** Muse 10 · **Branch:** `muse10/task-sen-023-approval-path` · **Date:** 2026-11-24
**Claim:** hub #1483 comment 7122802508, 2026-11-24 ~10:47 IST, on direct assignment by
Muse (coordinator) in watch 7122541986 (~10:30 IST; blocked-head skip past FRD-037, still 401).
**Claim PR:** #1629, merged 2026-11-24 11:19 IST (merge 06ea1561, merged by Surendra).
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via
`https://friday-universe.duckdns.org/sentinel` (Caddy). Service start:
2026-11-24 08:29:17 IST, MainPID 3425193, `Sentinel.service` active.
**Run reference:** TASK-SEN-021 (Muse 9, 2026-11-22), TASK-SEN-024 (Muse 13, run 2),
TASK-SEN-025 (Muse 13, run 3) — same legs, same procedure; this run repeats it
against the current deploy.
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`,
`apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical
(md5) to this repo at `origin/main` `8ca10ee` — the code surveyed below is
the code that ran:
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21
(S1 `/opt/friday_universe` git HEAD `c19ab0a8` — a later deploy commit that did not
touch these four files; the md5s above are the operative check.)

## How the approval path works (repo source, at 8ca10ee)

Same as SEN-021/024/025 (verified unchanged in the surveyed files):

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
  Approval **tokens** (bearer credentials) are likewise never reproduced in
  this document — requests are identified by `request_id` only. The leg-2
  token was held in a file on Server 1 only, for the post-expiry check, and
  deleted after it.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`:
  `log_file_path = "logs/audit.jsonl"` → on Server 1,
  `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of
  `submit_approval` is the API endpoint above; no production code calls
  `wait_for_decision`. A submitted action is a *request record* only —
  nothing in the fleet executes an action because its approval record
  exists.

## Pre-flight checks (before either leg)

- Both Oracle servers ONLINE (`get_system_info`, 2026-11-24 ~13:13 IST).
- Sentinel `/health` 200: `audit_chain_valid: true`,
  `audit_chain_entries: 31`, `kill_switch_active: false`,
  `audit_durable: true` (2026-11-24 13:13:51 IST). Seq 29 is the SEN-025
  leg-1 auto-approval; seq 30–31 are `TLS_CERT_ALERT`s (08:41 / 12:02 IST) —
  not approval traffic.
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle),
  `telegram_channel: true` — the SEN-022 startup self-check gate is live
  and passing in production (2026-11-24 13:13:51 IST).
- Telegram channel pre-check: `/ready` reports `telegram_channel: true`;
  no credential values were read, printed, or copied at any point.
- Classifier dry-run on the exact planned actions (repo code at 8ca10ee,
  no live effect): leg 1 → `AUTO_APPROVE / read_only`; leg 2 →
  `OWNER_PROMPT / caller_risk_not_low`.
- Pending list empty before the legs (`GET /api/v1/approvals/pending` →
  `[]`, HTTP 200, 2026-11-24 ~13:14 IST) — no other approval traffic.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `check sentinel health status`
- **Submitted by:** `MUSE_10`, `risk_level: LOW`,
  details `{"purpose": "TASK-SEN-023 leg 1 proof", "task": "TASK-SEN-023"}`
- **Submitted:** 2026-11-24 13:15:31 IST (one `POST
  /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`,
  `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-24T07:45:31.559472+00:00`,
  `decided_at 2026-11-24T07:45:31.610439+00:00` (~0.05 s later)
- **Request id:** `appr_8e03073ea8ac`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy
  (TASK-SEN-019): read_only — Read-only action ('check ...') with a LOW
  caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`,
  exactly one entry for this request id:
  `seq 32`, `entry_id audit-appr-auto-appr_8e03073ea8ac`,
  `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`,
  `target MUSE_10`, `action_type "check sentinel health status"`,
  `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`,
  `timestamp 2026-11-24T07:45:31.572044+00:00`,
  `previous_hash 815738a2d42408a5790e7cb4095a44e0ea8e4cc9f231756d92db8434da3be9c2`
  (chains onto the seq-31 tail entry, a `TLS_CERT_ALERT`),
  `current_hash 9abb21df3297da3d8cdac3c0365fe9bdcfd1bb686124ebd12e0af309821310d6`.
  Hash linkage verified: seq 32 `previous_hash` == seq 31 `current_hash`
  (`CHAIN_OK: True`). Details: `policy_category read_only`,
  `risk_level LOW`.
- **Service journal:** `Nov 24 13:15:31 … Approval appr_8e03073ea8ac
  (check sentinel health status by MUSE_10) AUTO-APPROVED [read_only]`.
- **Cross-check:** audit file lines 31 → 32 after the leg; `/health`
  `audit_chain_entries` was 31 at pre-flight and the new entry is seq 32
  (`audit_chain_valid: true`).

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `deploy sentinel configuration change to production`
- **Submitted by:** `MUSE_10`, `risk_level: HIGH`,
  details `{"purpose": "TASK-SEN-023 leg 2 proof, prompt only",
  "task": "TASK-SEN-023"}`
- **Submitted:** 2026-11-24 13:16:22 IST (one `POST
  /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`,
  `policy_category: caller_risk_not_low`, `decided_at: null`,
  `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-24T07:46:22.204308+00:00`,
  `expires_at 2026-11-24T07:51:22.204309+00:00` (13:21:22 IST)
- **Request id:** `appr_fb597c9906d3`
- **Recorded in the live service:** the request appears in
  `GET /api/v1/approvals/pending` (HTTP 200) with the same fields —
  it is held in the running process's pending map awaiting a decision.
  The pending list contained exactly this one item (checked 13:16:22 IST).
- **Telegram prompt — what was sent:** `_dispatch_notifications`
  (`approval_dispatcher.py`) builds this message from the template with
  the live values and sends it via `_send_telegram` because the channel
  is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_10`
  > **Action:** `deploy sentinel configuration change to production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-023 leg 2 proof, prompt only", "task": "TASK-SEN-023"}`
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
  - Service journal 13:14:00–13:23:00 IST contains **no**
    `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback)
    and **no** `Telegram notification dispatch error` line — an error scan
    over the window returns 0 lines matching `error|failed|QUEUED`. The
    access log shows the submission itself:
    `13:16:23 … POST /api/v1/approvals/request 200 OK`, then
    `GET /api/v1/approvals/pending 200 OK`.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 13:16:22 IST;
    the synchronous Telegram `urlopen` completed inside that call with no
    error logged.
  - The Telegram `message_id` is **not observable** from this side:
    `_send_telegram` discards the API response and returns only a boolean,
    which is not logged on success. Delivery to Surendra's Telegram client
    is therefore asserted from the configured channel + clean dispatch
    path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 10 anywhere: no POST to
  `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction,
  no `decide()` call. At submission the record showed `decided_at: null`.
- The action was never a command: the approval request is a record only
  (see "No executor on this path"). No deploy command was issued to any
  host, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 13:21:22 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-24 13:22:52 IST, after `expires_at` 13:21:22 IST,
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
  the same start timestamp (`Tue 2026-11-24 08:29:17 IST`) — no restart;
  S1 `/opt/friday_universe` git HEAD unchanged at `c19ab0a8` — no deploy;
  journal 13:14–13:23 IST contains zero `error|failed|QUEUED` lines.
- **Observation (not a defect of this task):** the journal shows one
  unrelated deploy-watchdog WARNING at 13:22:43 IST —
  `deploy watchdog: server-2 alerted (deployed c19ab0a8, main 8ca…` — the
  watchdog flags that S1's deployed checkout (`c19ab0a8`) differs from
  current main (`8ca10ee`). Pre-existing drift, not caused by this run;
  the four approval files are byte-identical to main (see deployed-code
  check above).
- **Cleanup:** the leg-2 token file and all throwaway scripts on Server 1
  were deleted after this check (verified: no `/tmp/sen023_*` remains).

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
  leg 1 was verified by hash linkage (previous hash = seq-31 tail hash);
  a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the
  legs and contained only the leg-2 request after it; earlier pending
  history was not audited.

## Verdict

**TASK-SEN-023 — live approval-path proof PASS.** Leg 1 auto-approved
(appr_8e03073ea8ac, seq 32, chain OK); leg 2 prompted on Telegram
(appr_fb597c9906d3, PENDING, expired un-actioned, approve link 409-dead);
the high-risk action did not execute.

## Files changed

| File | Change |
|---|---|
| `docs/collaboration/TASK-SEN-023-APPROVAL-PATH-PROOF.md` | This evidence doc (NEW) |
| `docs/collaboration/WORK_BOARD.yaml` | SEN-023 record CLAIMED → IN_REVIEW (work PR) |

No live database or config was written to; no service was restarted; no
approval was granted or denied by Muse 10.

— Muse 10, 2026-11-24 ~13:24 IST. Usage: 37% of free weekly limit
(last checked 2026-11-24 ~10:20 IST; reset Nov 28 02:03 IST).
