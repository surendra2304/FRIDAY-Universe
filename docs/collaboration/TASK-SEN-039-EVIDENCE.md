# TASK-SEN-039 — Sentinel approval-path live proof run 5 — EVIDENCE

**Task:** Sentinel: approval-path live proof run 5 — auto-approve low-risk, Telegram prompt high-risk.
**Owner:** Muse 19 · **Branch:** `muse19/task-sen-039`
**Claim:** hub #2045, 2026-11-27 ~18:23 IST (comment 7218803086) — SEN-040 re-slot ACCEPTED; SEN-039 claimed as queue head.
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via `http://127.0.0.1:8008` from Server 1 itself.
**Deployed code check (Server 1, read first-hand 2026-11-27 ~20:41 IST):** the four approval-path files are byte-identical (md5) to the run-2/run-3/run-4 evidence — the code surveyed in cp2/cp3 is the code that ran the legs:
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

Server 1 `/opt/friday_universe` git HEAD is `bf3c76c9` (Merge PR #2013); the approval-path files are identical across that HEAD and live main `fa7afb4c`.
**Grant / hold note:** the WATCH177 hold is lifted this run. Head Manager ruling 7192682851 (owner decision 2026-11-26 18:25 IST, full run_shell for all worker chats, approval 7113152293 CLOSED), correction 7197725825 (grant STANDS; a permissions-history lookup does not surface main-chat approvals), and burn order 7200414167 §1 ("THE run_shell GRANT IS SETTLED — THE HOLD IS OVER… starts the leg NOW, or releases the task") were all read first-hand this run. The Burn Enforcer 19:45 §E / Correction 2 §F.5 / WATCH226 §D.10 / BE 20:32 §C direction ("start the SEN-039 live legs or release SEN-039") is answered by these legs. permissions.history still shows no record for approval `7113152293` (14th check this run; newest recorded request is 2026-11-23) — recorded plainly, with the Head Manager's explanation above. The legs below are commands run for this task on Sentinel's home server; no server move, no deploy, no restart, no live-money action.
**Bridge:** `https://friday-universe.duckdns.org/bridge/mcp` — initialize 200, server FRIDAY-Cloud-Engineering-Bridge v1.30.0, tools/list 200, 31 tools incl. `run_shell` (verified first-hand this run). Live calls were made from Server 1 itself by throwaway scripts that read the key from the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`, the same file the live service loads) and used it in-process only. The key value was never printed, copied, or stored anywhere; the scripts and the leg-2 token file were deleted after the post-expiry check. Approval **tokens** are never reproduced in this document — requests are identified by `request_id` only.
**No executor on this path (verified in SEN-036):** the only production caller of `submit_approval` is the API endpoint; no production code calls `wait_for_decision`. A submitted action is a *request record* only — nothing in the fleet executes an action because its approval record exists.

## Pre-flight checks (before either leg, 2026-11-27 ~20:29 IST)

- Both Oracle servers ONLINE (`get_system_info` via bridge).
- Sentinel `/health` 200: `audit_chain_valid: true`, `audit_chain_entries: 48`, `kill_switch_active: false`, `audit_durable: true` (observed 20:29:14 IST). Ledger baseline 48 — tail seq 47/48 are `GATED_REVIEW_EVALUATED` entries from muse9-val002 (VAL-002 gate reviews, 19:58 IST); run 4's leg-1 auto-approval is seq 45.
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle), `telegram_channel: true`.
- Classifier dry-run on the exact planned actions (repo code, no live effect): 4/4 as expected (cp2, re-verified cp3 on live main `f0d575f1`).
- Pending list empty before the legs (`GET /api/v1/approvals/pending` → count 0, 20:31 IST) — no other approval traffic.
- Service journal (20 min before the legs): no `[SENTINEL APPROVAL QUEUED]` line, no `Telegram notification dispatch error` line.
- Server 1 load light at run time (load avg 1.22, 0.91, 0.92; up 44 days).

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `check sentinel approval queue status`
- **Submitted by:** `MUSE_19`, `risk_level: LOW`, details `{"purpose": "TASK-SEN-039 leg 1 proof", "task": "TASK-SEN-039"}`
- **Submitted:** 2026-11-27 20:32:21 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`, `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-27T15:02:21.819669+00:00`, `decided_at 2026-11-27T15:02:21.915190+00:00` (~0.1 s later)
- **Request id:** `appr_54ca54c36733`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy (TASK-SEN-019): read_only — Read-only action ('check ...') with a LOW caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`, exactly one entry for this request id:
  `seq 49`, `entry_id audit-appr-auto-appr_54ca54c36733`, `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`, `target MUSE_19`, `action_type "check sentinel approval queue status"`, `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`, `timestamp 2026-11-27T15:02:21.899956+00:00`, `previous_hash 45e7b6c0146037b1aa2487fed777efc391ded8f41ab3ac27df54e139afc78557` (chains onto the seq-48 tail entry — verified: seq-48 `current_hash` equals seq-49 `previous_hash`), `current_hash 206c736a315b11212ad410c564f94956c57a76db52d1790382c6dc66adb366a4`.
  Details: `policy_category read_only`, `risk_level LOW`.
- **Service journal:** `Nov 27 20:32:21 … Approval appr_54ca54c36733 (check sentinel approval queue status by MUSE_19) AUTO-APPROVED [read_only]`
- **Cross-check:** `/health` audit entry count 48 → 49 after the leg (seq 49 is this auto-approval); `audit_chain_valid: true`.

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `rotate sentinel API key in production`
- **Submitted by:** `MUSE_19`, `risk_level: HIGH`, details `{"purpose": "TASK-SEN-039 leg 2 proof, prompt only", "task": "TASK-SEN-039"}`
- **Submitted:** 2026-11-27 20:32:55 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`, `policy_category: credential_change`, `decided_at: null`, `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-27T15:02:55.606096+00:00`, `expires_at 2026-11-27T15:07:55.606097+00:00` (20:37:55 IST)
- **Request id:** `appr_61c71db433fd`
- **Recorded in the live service:** the request appears in `GET /api/v1/approvals/pending` (HTTP 200) with the same fields — it is held in the running process's pending map awaiting a decision. The pending list contained exactly this one item.
- **Telegram prompt — what was sent:** `_dispatch_notifications` (`approval_dispatcher.py`) builds this message from the template with the live values and sends it via `_send_telegram` because the channel is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_19`
  > **Action:** `rotate sentinel API key in production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-039 leg 2 proof, prompt only", "task": "TASK-SEN-039"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: `/ready` reports `telegram_channel: true` (SEN-022 gate).
  - The submission ran `_dispatch_notifications` synchronously inside `submit_approval`; the code only skips Telegram when the channel is unconfigured (it was configured) and only logs on transport failure.
  - Service journal 20:32–20:39 IST contains **no** `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback) and **no** `Telegram notification dispatch error` line.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 20:32:55 IST; the synchronous Telegram `urlopen` completed inside that call with no error logged. Uvicorn access log: `20:32:58 … "POST /api/v1/approvals/request HTTP/1.1" 200 OK`.
  - The Telegram `message_id` is **not observable** from this side: `_send_telegram` discards the API response and returns only a boolean, which is not logged on success. Delivery to Surendra's Telegram client is therefore asserted from the configured channel + clean dispatch path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 19 anywhere: no POST to `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction, no `decide()` call. At submission the record showed `decided_at: null`.
- The action was never a command: the approval request is a record only (see "No executor on this path"). No rotation was issued, no command runs, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 20:37:55 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-27 20:38:54 IST, after `expires_at` 20:37:55 IST, token recovered server-side from the Server 1 file (never printed or copied out; file deleted after the check).
  - `GET /api/v1/approvals/{token}/status` → 200: record still stored as `PENDING`, `decided_at: null`, `decision_reason: null` — no decision was ever recorded.
  - `GET /api/v1/approvals/pending` → 200: `[]` — the request is gone from the actionable pending list.
  - `GET /api/v1/approvals/{token}/approve` (the read-only confirmation page, which never changes state) → **HTTP 409 "Approval no longer pending"** — the approve link is dead.
  - Semantics note: the stored `status` field only transitions when `decide()` or `wait_for_decision()` runs; the live gate is the `is_expired()` check enforced by the approve/deny paths. The 409 proves that gate is closed.
- **No-execution corroboration:** `Sentinel.service` still `active` — no restart; S1 `/opt/friday_universe` git HEAD unchanged at `bf3c76c9` — no deploy; journal 20:32–20:39 IST contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines.
- **Cleanup:** the leg-2 token file and all throwaway scripts on Server 1 were deleted after this check (verified: both paths gone).

## What was NOT verified

- **Telegram message id / device receipt:** the dispatcher does not log or return the Telegram `message_id`, so the exact message id and confirmation that the message rendered on Surendra's device cannot be established from the server side. The prompt's dispatch is evidenced by the configured channel, the synchronous send inside the 200-OK submission, and the absence of any dispatch-error or offline-queue log line. If Muse or Surendra eyeball the Telegram client, the message above should be visible there.
- **Ledger re-verification after the legs:** the file ledger entry for leg 1 was verified by hash linkage (seq-48 `current_hash` = seq-49 `previous_hash`); a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the legs and contained only the leg-2 request after it; earlier pending history was not audited.

— Muse 19, 2026-11-27 ~20:40 IST
