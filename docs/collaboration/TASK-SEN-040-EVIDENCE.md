# TASK-SEN-040 — Sentinel approval-path live proof run 4

**Task:** Sentinel: approval-path live proof run 4 — one low-risk action auto-approved and one high-risk action prompting on Telegram, each exactly once, with evidence.
**Owner:** Muse 14 · **Branch:** `muse14/task-sen-040`
**Claim:** hub #2045 comment 7223923337, 2026-11-27 ~22:30 IST (pool claim; no direct assignment in WATCH231 or BE 21:58). Board on main `330de772` (verified first-hand): TASK-SEN-040 AVAILABLE / owner null / branch null / pr null. No board hunk in this PR — board flips are coordinator-only.
**Live service:** Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via `https://friday-universe.duckdns.org/sentinel` (Caddy). Service start: 2026-11-27 22:30:52 IST, single worker, `Sentinel.service` active (unchanged across the run — no restart during the legs; see "No-execution corroboration").
**Prior runs:** Run 2 SEN-036 (Muse 10, work PR #1971 MERGED 0434f6df); run 3 SEN-037 (Muse 4, work PR #2065); SEN-038 (Muse TP10, work PR #2074 MERGED 83d53187) — same legs, same procedure; this run repeats it against the current deploy. Run-2 evidence: `docs/collaboration/TASK-SEN-036-APPROVAL-PATH-LIVE-PROOF-RUN-2.md`; run-3 evidence: `docs/collaboration/TASK-SEN-037-EVIDENCE.md`; SEN-038 evidence: `docs/collaboration/TASK-SEN-038-EVIDENCE.md`.
**Adopted prior work:** M19's branch `muse19/task-sen-040` @ `caf78550` (checkpoints 1–3; classifier dry-run 4/4 on live main; deployed-code md5s match run 2). M19 accepted the pool re-slot at 18:30 IST (hub 7218803086); cp3 stands for the next claimer. This run re-ran the classifier dry-run with caller MUSE_14 (4/4 as expected, exit 0 — see "Pre-flight") and re-verified the deployed-code md5s (see below).
**Deployed code check:** `approval_policy.py`, `approval_dispatcher.py`, `apps/api/main.py`, `apps/api/middleware.py` on Server 1 are byte-identical (md5) to the surveyed code — the code below is the code that ran:
- `approval_policy.py` 87ca1ed136d83a53f17dec27828fc4ba
- `approval_dispatcher.py` 92468726310f17dd6a1f12aadf6a5a83
- `main.py` b5d932aea35bf264fff8ae99206d99bd
- `middleware.py` ceffdcf2ddeadc35183842dbbb350c21

Same four md5s as SEN-024, SEN-036, SEN-037 and SEN-038 surveyed — the approval path is unchanged since run 1. Server 1 git HEAD is `12b8d78ebb89073f5138ba62f48ba56a74cb65dc` (unchanged before and after the legs).

## Clearance for the live legs (why the legs were run, not held)

- **Standing clearance 7200564540** (coordinator ruling, hub #1483, 2026-11-27 ~00:05 IST; WATCH181 §2c + WATCH182 §2d) covers own-task live verification; only server moves, live money and destructive deletes still need a ruling. The Telegram prompt leg is none of those — it is a notification, not an execution (see "No executor on this path").
- **Owner stop order** (2026-11-24) freezes server moves only. The legs change no server state beyond the two approval-path test actions themselves: no deploy, no restart, no file written, no service stopped or started.
- **WATCH201 §3** (coordinator, hub #2045 comment 7209660625, 2026-11-27 ~09:46 IST) confirmed SEN-038's legs as specified; SEN-040's legs are the same two actions with caller MUSE_14 (leg 1 `list sentinel pending approval requests`, LOW, expect AUTO_APPROVE/read_only; leg 2 `change sentinel approval policy threshold in production`, HIGH, expect OWNER_PROMPT/sentinel_policy_change). Leg 2 is a request record only — no policy is changed, no command runs, no file is written, no service is restarted.
- Legs were run exactly once each in a single no-retry batch (a retry after a dropped response could have double-fired a leg).

## How the approval path works (repo source)

Same as SEN-021 / SEN-024 / SEN-036 / SEN-037 / SEN-038 (verified unchanged in the surveyed files):

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`. `classify_approval` returns `AUTO_APPROVE` only when ALL hold: caller risk claim is low (LOW / NONE / MINIMAL / ROUTINE); no hard-bound pattern (live-money, owner-data deletion, credential change, Sentinel-policy change); and the action positively matches the low-risk class — read-only leading verb with no write verb later, internal housekeeping, or caller-attested reversible. Anything else is `OWNER_PROMPT`; the policy never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`. `submit_approval` classifies first. Auto-approve: writes an `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger and only then marks the request APPROVED; if the ledger write fails it falls back to the owner prompt. Owner prompt: `_dispatch_notifications` sends the Telegram message via `_send_telegram` and records the request PENDING with approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`: `POST /api/v1/approvals/request` calls `submit_approval` and returns the pending record. `GET /api/v1/approvals/pending`, `GET /api/v1/approvals/{token}/status`. Approve/deny require an explicit POST from the confirmation form; the GET confirmation pages never change state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required (`X-API-Key` header). The live calls below were made from Server 1 itself by throwaway scripts that read the key from the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`, the same file the live service loads) and used it in-process only. The key value was never printed, copied, or stored anywhere; the scripts were deleted after the run. Approval **tokens** are likewise never reproduced in this document — requests are identified by `request_id` only. The leg-2 token was held in a file on Server 1 only, for the post-expiry check, and deleted after it.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`: `log_file_path = "logs/audit.jsonl"` → on Server 1, `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified):** the only production caller of `submit_approval` is the API endpoint above; no production code calls `wait_for_decision`. A submitted action is a *request record* only — nothing in the fleet executes an action because its approval record exists.

## Pre-flight checks (before either leg, 2026-11-27 ~22:37 IST)

- Both Oracle servers ONLINE (`get_system_info`); Server 1 load light (load avg 0.75/1.64/1.31, 298 MB available of 956 MB).
- `Sentinel.service` active, started 2026-11-27 22:30:52 IST; port 8008 listening (`0.0.0.0:8008`). Note: the service **restarted at 22:30:52 IST** (journal: `Sentinel.service: Failed with result 'timeout'`, then stopped and started cleanly; `NRestarts=0`, Main PID 2063819, single worker). The restart happened at claim time, **before** the pre-flight and before either leg; the start timestamp 22:30:52 IST is the baseline for the no-restart corroboration below.
- Sentinel `/health` 200: `audit_chain_valid: true`, `audit_chain_entries: 50`, `kill_switch_active: false`, `audit_durable: true`, version 1.0.0, environment production.
- Sentinel `/ready` 200, `READY`, database `connected` (Oracle), `telegram_channel: true` — the SEN-022 startup self-check gate is live and passing in production. `modules_active: 13`.
- Telegram channel pre-check: `/ready` reports `telegram_channel: true`; no credential values were read, printed, or copied at any point.
- Classifier dry-run on the exact planned actions with caller MUSE_14 (deployed code on Server 1, no live effect): **4/4 as expected, exit 0** — leg 1 → `AUTO_APPROVE / read_only`, hard_bound False; leg 2 → `OWNER_PROMPT / sentinel_policy_change`, hard_bound True; both run-3 controls reproduce exactly.
- Pending list empty before the legs (`GET /api/v1/approvals/pending` → count 0) — no other approval traffic.
- Ledger baseline: `audit_chain_entries: 50` (was 45 after SEN-038 leg 1; 5 entries added since — other approval traffic or audit events). Seq 49 was MUSE_19's `check sentinel approval queue status` (`appr_54ca54c36733`, SEN-039 live leg ~20:32 IST); seq 50 was a `TLS_CERT_ALERT`.
- Journal 22:30:52–22:37:53 IST shows a clean startup (Telegram channel READY, schema ensured on Oracle with 15 tables, daemons started), a deploy-watchdog warning (server-2 deployed `12b8d78e` vs main `1a58bb15`), and a TLS check failure line for `friday-universe.duckdns.org:443`.

## LEG 1 — low-risk action auto-approved (exactly once)

- **Action:** `list sentinel pending approval requests`
- **Submitted by:** `MUSE_14`, `risk_level: LOW`, details `{"purpose": "TASK-SEN-040 leg 1 proof", "task": "TASK-SEN-040"}`
- **Submitted:** 2026-11-27 22:41:29 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** `APPROVED` — `policy_tier: AUTO_APPROVE`, `policy_category: read_only`
- **Timestamps (UTC):** `created_at 2026-11-27T17:11:29.911748+00:00`, `decided_at 2026-11-27T17:11:29.917225+00:00` (~0.006 s later)
- **Request id:** `appr_f4183cd37f03`
- **Decision reason (verbatim):** "Auto-approved by Sentinel approval policy (TASK-SEN-019): read_only — Read-only action ('list ...') with a LOW caller risk claim and no hard-bound pattern."
- **Ledger evidence** — `/opt/friday_universe/Sentinel/logs/audit.jsonl`, exactly one entry for this request id:
  `seq 51`, `entry_id audit-appr-auto-appr_f4183cd37f03`, `event_type APPROVAL_AUTO_APPROVED`, `actor sentinel-approval-policy`, `target MUSE_14`, `action_type "list sentinel pending approval requests"`, `scope_policy gatekeeper-approvals`, `decision AUTO_APPROVED`, `timestamp 2026-11-27T17:11:29.915909+00:00`, `previous_hash 6e0e403509a4b5a683b4a7dfcc45431135dfae06aca70380ae7486264916ad5b` (chains onto the seq-50 tail entry — verified: seq-50 `current_hash` equals seq-51 `previous_hash`), `current_hash deab703d85667ce8f81f14e9557f489f0ae5e432bc3674e070d13f3a53b7a054`.
  Details: `policy_category read_only`, `risk_level LOW`.
- **Service journal:** `Nov 27 22:41:29 … Approval appr_f4183cd37f03 (list sentinel pending approval requests by MUSE_14) AUTO-APPROVED [read_only]`
- **Cross-check:** `/health` audit entry count 50 → 51 after the leg (seq 51 is this auto-approval); `audit_chain_valid: true`.

## LEG 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `change sentinel approval policy threshold in production`
- **Submitted by:** `MUSE_14`, `risk_level: HIGH`, details `{"purpose": "TASK-SEN-040 leg 2 proof, prompt only", "task": "TASK-SEN-040"}`
- **Submitted:** 2026-11-27 22:41:29 IST (one `POST /api/v1/approvals/request` → HTTP 200)
- **Decision:** none made — `status: PENDING`, `policy_tier: OWNER_PROMPT`, `policy_category: sentinel_policy_change`, `decided_at: null`, `decision_reason: null`
- **Timestamps (UTC):** `created_at 2026-11-27T17:11:29.926940+00:00`, `expires_at 2026-11-27T17:16:29.926941+00:00` (22:46:29 IST)
- **Request id:** `appr_4ab9b1c56215`
- **Recorded in the live service:** the request appears in `GET /api/v1/approvals/pending` (HTTP 200) with the same fields — it is held in the running process's pending map awaiting a decision. The pending list contained exactly this one item.
- **Telegram prompt — what was sent:** `_dispatch_notifications` (`approval_dispatcher.py`) builds this message from the template with the live values and sends it via `_send_telegram` because the channel is configured:
  > 🛡️ **SENTINEL GUARDED ACTION APPROVAL**
  >
  > **Agent:** `MUSE_14`
  > **Action:** `change sentinel approval policy threshold in production`
  > **Risk Level:** HIGH
  > **Details:** `{"purpose": "TASK-SEN-040 leg 2 proof, prompt only", "task": "TASK-SEN-040"}`
  >
  > ✅ **APPROVE ACTION** (link to `/api/v1/approvals/<token>/approve`)
  > ❌ **DENY ACTION** (link to `/api/v1/approvals/<token>/deny`)
  >
  > *Expires in 5 minutes.*
- **Telegram receipt (as observable from this side):**
  - Pre-check: `/ready` reports `telegram_channel: true` (SEN-022 gate).
  - The submission ran `_dispatch_notifications` synchronously inside `submit_approval`; the code only skips Telegram when the channel is unconfigured (it was configured) and only logs on transport failure.
  - Service journal 22:41:00 IST onward contains **no** `[SENTINEL APPROVAL QUEUED]` line (the unconfigured-channel fallback) and **no** `Telegram notification dispatch error` line.
  - The `POST /api/v1/approvals/request` returned HTTP 200 at 22:41:29 IST; the synchronous Telegram `urlopen` completed inside that call with no error logged.
  - The Telegram `message_id` is **not observable** from this side: `_send_telegram` discards the API response and returns only a boolean, which is not logged on success. Delivery to Surendra's Telegram client is therefore asserted from the configured channel + clean dispatch path, not from a message id — see "What was NOT verified".

## The high-risk action did NOT execute

- No approve/deny was issued by Muse 14 anywhere: no POST to `/api/v1/approvals/{token}/approve` or `/deny`, no Telegram interaction, no `decide()` call. At submission the record showed `decided_at: null`, and the post-expiry check (below) still shows `decided_at: null` — no decision was ever recorded by anyone.
- The action was never a command: the approval request is a record only (see "No executor on this path"). No deploy command was issued to any host, no file was written, no service was restarted.
- **Post-expiry check** (after `expires_at` 22:46:29 IST) — see below.

## Post-expiry check

- **Checked:** 2026-11-27 22:46:48 IST (17:16:48 UTC), after `expires_at` 22:46:29 IST, token recovered server-side from the Server 1 file (never printed or copied out; file deleted after the check).
  - `GET /api/v1/approvals/{token}/status` → 200: record still stored as `PENDING`, `decided_at: null`, `decision_reason: null` — no decision was ever recorded.
  - `GET /api/v1/approvals/pending` → 200: `[]` — the request is gone from the actionable pending list.
  - `GET /api/v1/approvals/{token}/approve` (the read-only confirmation page, which never changes state; sent with the `X-API-Key` header) → **HTTP 409 "Approval no longer pending"** — the approve link is dead. This avoids SEN-037's 401 script error (the key was included).
  - Semantics note: the stored `status` field only transitions when `decide()` or `wait_for_decision()` runs; the live gate is the `is_expired()` check enforced by the approve/deny paths. The 409 proves that gate is closed.
- **Hash-chain linkage verified:** seq-50 `current_hash` `6e0e403509a4b5a683b4a7dfcc45431135dfae06aca70380ae7486264916ad5b` equals seq-51 `previous_hash` — CHAIN-LINKED: True.
- **No-execution corroboration:** `Sentinel.service` still `active` with the same start timestamp (`Fri 2026-11-27 22:30:52 IST`) — no restart; S1 `/opt/friday_universe` git HEAD unchanged at `12b8d78e` — no deploy; journal 22:41 IST onward contains zero `Telegram notification dispatch error` / `[SENTINEL APPROVAL QUEUED]` lines.
- **Cleanup:** the leg-2 token file and all throwaway scripts and output JSONs on Server 1 were deleted after this check (`ls /tmp/sen040*` → no such file).

## What was NOT verified

- **Telegram message id / device receipt:** the dispatcher does not log or return the Telegram `message_id`, so the exact message id and confirmation that the message rendered on Surendra's device cannot be established from the server side. The prompt's dispatch is evidenced by the configured channel, the synchronous send inside the 200-OK submission, and the absence of any dispatch-error or offline-queue log line. If Muse or Surendra eyeball the Telegram client, the message above should be visible there.
- **Ledger re-verification after the legs:** the file ledger entry for leg 1 was verified by hash linkage (seq-50 `current_hash` = seq-51 `previous_hash`); a full-chain re-verification run was not performed as part of this task.
- **No other approval traffic:** the pending list was empty before the legs and contained only the leg-2 request after it; earlier pending history was not audited.

## Open item — run numbering (coordinator question, NOT resolved here)

- SEN-038 merged as "run 4" (its evidence: "Follow-up run to SEN-037 (run 3), SEN-038 (run 4)") while SEN-040 is also titled "run 4". No ruling was found in the hub since. This is a record question for the coordinator; the live leg proceeded regardless — the numbering does not change what was run or what was verified. This run is recorded as TASK-SEN-040's live proof, with the collision stated plainly here.

## Verdict

**PASS** — both behaviours verified live as specified: one low-risk action auto-approved (leg 1, `appr_f4183cd37f03`, ledger seq 51, hash-chained) and one high-risk action prompting on Telegram (leg 2, `appr_4ab9b1c56215`, PENDING, expired undecided, approve link dead after expiry), each exactly once. No code change was needed — the approval path behaved as specified against the existing deploy.

## Five states

- implemented: YES (this evidence doc filed on branch `muse14/task-sen-040`)
- tested: YES (both live legs run exactly once against live Sentinel on Server 1, outcomes above)
- merged: NO (work PR open at filing; peer merge owed — never merge own PR)
- deployed: NO (nothing deployed; proof ran against the existing deploy, service unchanged)
- production-verified: NO (paired verification by a different chat owed before this counts)

— Muse 14
