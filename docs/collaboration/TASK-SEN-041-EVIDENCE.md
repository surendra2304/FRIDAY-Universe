# TASK-SEN-041 — Sentinel approval-path live proof run 5

**Task:** Sentinel: approval-path live proof run 5 (follow-up SEN-040 run 4) — one low-risk action auto-approved and one high-risk action prompting on Telegram, each exactly once, with evidence.
**Owner:** Muse 4 · **Branch:** `muse4/task-sen-041-approval-path-live-proof-run-5`
**Claim:** hub #2045 comment 7228704063, 2026-11-28 ~03:14 IST, on assignment in coordinator Burn Enforcer 01:35 (hub #2045 comment 7227081892) §B ("Muse 4 → TASK-SEN-041 as head — CLAIM NOW") + WATCH240 (hub #2045 comment 7227517100) §D, adopted WATCH239 §D. Board record on main `f15516b0` (verified first-hand): TASK-SEN-041 CLAIMED / owner muse_4 / P1, updated 2026-11-28T01:53:47+05:30. Board flips are coordinator-only; no board hunk in this PR.
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via `https://friday-universe.duckdns.org/sentinel` (Caddy). Service start: 2026-11-28 02:47:41 IST (baseline — see "No-execution corroboration"), single worker, `Sentinel.service` active.
**Prior runs:** Run 2 SEN-036 (Muse 10, work PR #1971 MERGED 0434f6df); run 3 SEN-037 (Muse 4, work PR #2065); SEN-038 (Muse TP10, work PR #2074 MERGED 83d53187); run 4 SEN-040 (Muse 14) — same legs, same procedure; this run repeats it against the current deploy. Run-4 evidence: `docs/collaboration/TASK-SEN-040-EVIDENCE.md`; run-3 evidence: `docs/collaboration/TASK-SEN-037-EVIDENCE.md`.
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`, `apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical (md5) to this repo on current main — the code surveyed below is the code that ran:
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

Same four md5s as SEN-024, SEN-036, SEN-037, SEN-038 and SEN-040 surveyed — the approval path is unchanged since run 1. Server 1 git HEAD is `e5adbc8920846f7abc90bd6d3a158d9965ee57e4` (baseline, unchanged before and after the legs — see below).

## Clearance for the live legs (why the legs were run, not held)

The Telegram leg prompts the owner, so the clearance question was decided explicitly before firing anything:

- **Standing clearance 7200564540** (coordinator ruling, hub #1483, 2026-11-27 ~00:05 IST; WATCH181 §2c + WATCH182 §2d) covers own-task live verification; only server moves, live money and destructive deletes still need a ruling. The Telegram prompt leg is none of those — it is a notification, not an execution (see "No executor on this path").
- **Burn Enforcer 01:35 §B** (coordinator, hub #2045 comment 7227081892, 2026-11-28 ~01:35 IST) assigned SEN-041 to Muse 4 as head: "Sentinel approval-path live proof run 5 (follow-up SEN-040 run 4). Fits your REL-119 live-probe work. Claim via hub + branch push, one-line record."
- **WATCH240 §D** (coordinator, hub #2045 comment 7227517100, 2026-11-28 ~01:45–02:00 IST) adopted the assignment: "Muse 4 → TASK-SEN-041 as head (BE 01:35 §B, adopted WATCH239 §D; flips ride #2200). Claim via hub + branch push."
- **Board record** for SEN-041 states the live-proof route explicitly: "Live-proof route: live Sentinel service on Oracle Server 1; Telegram prompt to the owner fires once for the high-risk leg."
- **Burn Enforcer 03:02 §C** (hub #2045 comment 7228540362, ~03:02 IST) directed Muse 4 to "post state + start SEN-041".
- **Precedent:** the exact same two leg actions were run by Muse 14 (SEN-040, run 4) and Muse 4 (SEN-037, run 3, same pair as controls) and the coordinator MERGED the results knowing leg 2 sent a Telegram prompt to the owner. No fresh confirmation was sought for SEN-041; the legs below were run under the standing clearance + the BE/WATCH assignment above, each exactly once.

## How the approval path works (repo source, at main)

Same as SEN-021 / SEN-024 / SEN-036 / SEN-037 / SEN-038 / SEN-040 (verified unchanged in the surveyed files):

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`.
  `classify_approval` returns `AUTO_APPROVE` only when ALL hold: caller risk claim is low (LOW / NONE / MINIMAL / ROUTINE); no hard-bound pattern (live-money, owner-data deletion, credential change, Sentinel-policy change); and the action positively matches the low-risk class — read-only leading verb with no write verb later, internal housekeeping, or caller-attested reversible. Anything else is `OWNER_PROMPT`; the policy never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`.
  `submit_approval` classifies first. Auto-approve: writes an `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger and only then marks the request APPROVED; if the ledger write fails it falls back to the owner prompt. Owner prompt: `_dispatch_notifications` sends the Telegram message via `_send_telegram` and records the request PENDING with approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`:
  `POST /api/v1/approvals/request` calls `submit_approval` and returns the pending record. `GET /api/v1/approvals/pending`, `GET /api/v1/approvals/{token}/status`. Approve/deny require an explicit POST from the confirmation form; the GET confirmation pages never change state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required (`X-API-Key` header). The live calls below were made from Server 1 itself by throwaway scripts that read the key from the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`, the same file the live service loads) and used it in-process only. The key value was never printed, copied, or stored anywhere; the scripts were deleted after the run. Approval **tokens** are likewise never reproduced in this document — requests are identified by `request_id` only. The leg-2 token was held in a file on Server 1 only, for the post-expiry check, and deleted after it.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`: `log_file_path = "logs/audit.jsonl"` → on Server 1, `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of `submit_approval` is the API endpoint above; no production code calls `wait_for_decision`. A submitted action is a *request record* only — nothing in the fleet executes an action because its approval record exists.

## Pre-flight checks (before either leg, 2026-11-28 ~03:20 IST)

- Both Oracle servers ONLINE (`get_system_info`, 2026-11-28 ~03:19 IST).
- `Sentinel.service` active, running, started 2026-11-28 02:47:41 IST; port 8008 listening. Server 1 load light (load avg 0.34/0.33/0.50, up 44 days); no slow responses observed.
- Sentinel `/health` 200: `audit_chain_valid: true`, `audit_chain_entries: 53`, `kill_switch_active: false`, `audit_durable: true`, version 1.0.0, environment production (2026-11-28 03:20:13 IST).
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle), `telegram_channel: true` — the SEN-022 startup self-check gate is live and passing in production (2026-11-28 03:20:13 IST). `modules_active: 13`.
- Telegram channel pre-check: `/ready` reports `telegram_channel: true`; no credential values were read, printed, or copied at any point.
- Classifier dry-run on the exact planned actions with caller MUSE_4 (deployed code on Server 1, no live effect): **4/4 as expected, exit 0** — leg 1 → `AUTO_APPROVE / read_only`, hard_bound False; leg 2 → `OWNER_PROMPT / sentinel_policy_change`, hard_bound True; both run-3 controls reproduce exactly (`check sentinel health status` → `AUTO_APPROVE / read_only`; `deploy sentinel configuration change to production` → `OWNER_PROMPT / caller_risk_not_low`).
- Pending list empty before the legs (`GET /api/v1/approvals/pending` → count 0, 2026-11-28 ~03:20 IST) — no other approval traffic.
- Ledger baseline: `audit_chain_entries: 53` (was 51 after SEN-040 leg 1; 2 entries added since — other approval traffic or audit events; seq 53 was a `TLS_CERT_ALERT`).
- Journal (last hour before the legs, 65 lines) contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines.
- Bridge transport note: one `run_shell` call died with `http.client.IncompleteRead` during pre-flight (known bridge flakiness); retried with a fresh session via the str094 retry wrapper. The legs themselves were run as a single no-retry call: a retry after a dropped response could have double-fired a leg.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `list sentinel pending approval requests`
- **Submitted by:** `MUSE_4`, `risk_level: LOW`, details `{"purpose": "TASK-SEN-041 leg 1 proof", "task": "TASK-SEN-041"}`
- **Submitted:** 2026-11-28 03:22:30 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`, `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-27T21:52:30.842755+00:00`, `decided_at 2026-11-27T21:52:30.895678+00:00` (~0.053 s later)
- **Request id:** `appr_b6411b6976b8`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy (TASK-SEN-019): read_only — Read-only action ('list ...') with a LOW caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`, exactly one entry for this request id:
  `seq 54`, `entry_id audit-appr-auto-appr_b6411b6976b8`, `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`, `target MUSE_4`, `action_type "list sentinel pending approval requests"`, `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`, `timestamp 2026-11-27T21:52:30.845494+00:00`, `previous_hash 5d504ff37a2621430533d5dbf9e0be2b870b5728d07f48ca173bae2a68088bfa` (chains onto the seq-53 tail entry — verified: seq-53 `current_hash` equals seq-54 `previous_hash`), `current_hash c1c7ff668bc4f66c751632d7f23e7dea1b3bf37583c427a324e02b1bf875a27c`.
  Details: `policy_category read_only`, `risk_level LOW`.
- **Service journal:** `Nov 28 03:22:30 … Approval appr_b6411b6976b8 (list sentinel pending approval requests by MUSE_4) AUTO-APPROVED [read_only]`
- **Cross-check:** `/health` audit entry count 53 → 54 after the leg (seq 54 is this auto-approval); `audit_chain_valid: true`.

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `change sentinel approval policy threshold in production`
- **Submitted by:** `MUSE_4`, `risk_level: HIGH`, details `{"purpose": "TASK-SEN-041 leg 2 proof, prompt only", "task": "TASK-SEN-041"}`
- **Submitted:** 2026-11-28 03:22:30 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`, `policy_category: sentinel_policy_change`, `decided_at: null`, `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-27T21:52:30.905276+00:00`, `expires_at 2026-11-27T21:57:30.905276+00:00` (03:27:30 IST)
- **Request id:** `appr_6ca9a1617835`
- **Recorded in the live service:** the request appears in `GET /api/v1/approvals/pending` (HTTP 200) with the same fields — it is held in the running process's pending map awaiting a decision. The pending list contained exactly this one item (checked ~03:22:51 IST).
- **Telegram prompt — what was sent:** `_dispatch_notifications` (`approval_dispatcher.py`) builds this message from the template with the live values and sends it via `_send_telegram` because the channel is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_4`
  > **Action:** `change sentinel approval policy threshold in production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-041 leg 2 proof, prompt only", "task": "TASK-SEN-041"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: `/ready` reports `telegram_channel: true` (SEN-022 gate).
  - The submission ran `_dispatch_notifications` synchronously inside `submit_approval`; the code only skips Telegram when the channel is unconfigured (it was configured) and only logs on transport failure.
  - Service journal 03:22:00 IST onward contains **no** `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback) and **no** `Telegram notification dispatch error` line.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 03:22:30 IST; the synchronous Telegram `urlopen` completed inside that call with no error logged.
  - The Telegram `message_id` is **not observable** from this side: `_send_telegram` discards the API response and returns only a boolean, which is not logged on success. Delivery to Surendra's Telegram client is therefore asserted from the configured channel + clean dispatch path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 4 anywhere: no POST to `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction, no `decide()` call. At submission the record showed `decided_at: null`.
- The action was never a command: the approval request is a record only (see "No executor on this path"). No deploy command was issued to any host, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 03:27:30 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-28 ~03:29 IST, after `expires_at` 03:27:30 IST, token recovered server-side from the Server 1 journal access log (never printed or copied out; the recovery script deleted itself after the check).
  - `GET /api/v1/approvals/{token}/status` → 200: record still stored as `PENDING`, `decided_at: null`, `decision_reason: null` — no decision was ever recorded.
  - `GET /api/v1/approvals/pending` → 200: `[]` — the request is gone from the actionable pending list. (`get_pending_list` returns only non-expired pending approvals, so the empty list is itself the expiry-gate evidence: the request is no longer actionable.) The list was re-checked independently at 03:27:52 IST (22 s past expiry) with the same empty result.
  - `GET /api/v1/approvals/{token}/approve` (the read-only confirmation page, which never changes state; sent with the `X-API-Key` header) → **HTTP 409 "Approval no longer pending"** — the approve link is dead. This avoids SEN-037's 401 script error (the key was included).
  - Semantics note: the stored `status` field only transitions when `decide()` or `wait_for_decision()` runs; the live gate is the `is_expired()` check enforced by the approve/deny paths (and by `get_pending_list`). The code path was read first-hand in this run: the GET approve page returns 409 "Approval no longer pending" when `is_expired()` is true, and `decide()` marks an expired request EXPIRED instead of deciding it.
- **Timing note (honest record):** the first post-expiry script ran ~4 s before expiry (a sleep miscalculation on my side) and its output was lost to a bridge `IncompleteRead`; its own approve-page check at 03:27:29 IST returned 200 (correct — the request was still pending 1 s before expiry, confirmed in the journal access log). The checks above were re-run past expiry with the token recovered server-side from that journal line, and the 409 is first-hand from the re-run. The token was never printed, copied out, or stored anywhere outside Server 1.
- **Hash-chain linkage verified:** seq-53 `current_hash` `5d504ff37a2621430533d5dbf9e0be2b870b5728d07f48ca173bae2a68088bfa` equals seq-54 `previous_hash` — CHAIN-LINKED: True.
- **No-execution corroboration:** `Sentinel.service` still `active` with the same start timestamp (`Sat 2026-11-28 02:47:41 IST`) — no restart; S1 `/opt/friday_universe` git HEAD unchanged at `e5adbc8920846f7abc90bd6d3a158d9965ee57e4` — no deploy; journal 03:22 IST onward contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines; `/health` audit entry count still 54 (leg 2 wrote no ledger entry).
- **Cleanup:** the leg-2 token file, the legs output file, and all throwaway scripts on Server 1 were deleted after this check (`ls /tmp/sen041_*` → no such file).

## What was NOT verified

- **Telegram message id / device receipt:** the dispatcher does not log or return the Telegram `message_id`, so the exact message id and confirmation that the message rendered on Surendra's device cannot be established from the server side. The prompt's dispatch is evidenced by the configured channel, the synchronous send inside the 200-OK submission, and the absence of any dispatch-error or offline-queue log line. If Muse or Surendra eyeball the Telegram client, the message above should be visible there.
- **Ledger re-verification after the legs:** the file ledger entry for leg 1 was verified by hash linkage (seq-53 `current_hash` = seq-54 `previous_hash`); a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the legs and contained only the leg-2 request after it; earlier pending history was not audited.

## Verdict

**PASS** — both behaviours verified live as specified: one low-risk action auto-approved (leg 1, `appr_b6411b6976b8`, ledger seq 54, hash-chained) and one high-risk action prompting on Telegram (leg 2, `appr_6ca9a1617835`, PENDING, expired undecided, approve link dead after expiry), each exactly once. No code change was needed — the approval path behaved as specified against the existing deploy.

## Five states

- implemented: YES (this evidence doc filed on branch `muse4/task-sen-041-approval-path-live-proof-run-5`)
- tested: YES (both live legs run exactly once against live Sentinel on Server 1, outcomes above)
- merged: NO (work PR open at filing; peer merge owed — never merge own PR)
- deployed: NO (nothing deployed; proof ran against the existing deploy, service unchanged)
- production-verified: NO (paired verification by a different chat owed before this counts)

— Muse 4
