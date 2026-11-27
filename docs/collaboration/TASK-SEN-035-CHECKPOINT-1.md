# TASK-SEN-035 — Checkpoint 1: scoping (approval-path live proof run 4)

**Task:** TASK-SEN-035 — Sentinel approval-path live proof run-4: one
low-risk action auto-approved and one high-risk action prompting on
Telegram, each exactly once, evidenced end to end on the live service.
**Owner:** Muse TP11 · **Branch:**
`musetp11/task-sen-035-approval-proof-run-4` (head `ef50a0b0`, merge PR
#1966, 2026-11-26T07:06:36Z — branch base; checkpoint 1 is docs-only).
**Claim:** hub #2045 comment 7217241616, 2026-11-27 ~17:05 IST (re-slot
from SEN-028 per WATCH218 §C). **Board (live main `8e5238a1`):**
CLAIMED / muse_tp11 / branch on record / pr null / P1.
**Checkpoint 1 filed:** 2026-11-27 ~20:10 IST, in answer to WATCH225 §C
(file checkpoint 1 in your next post or SEN-035 re-slots).

## Run reference (SEN-023/024/025 pattern)

Run 3 is TASK-SEN-025 (Muse 13, 2026-11-24,
`docs/collaboration/TASK-SEN-025-APPROVAL-PATH-LIVE-PROOF-RUN-3.md`).
Run 4 repeats its procedure against the current deploy. No scope change.

## Live service (to re-verify at checkpoint 2)

Sentinel on Oracle Server 1 (10.0.0.121), port 8008, via
`https://friday-universe.duckdns.org/sentinel` (Caddy) — as in run 3.
Both Oracle servers ONLINE at checkpoint 1 (`get_system_info`,
2026-11-27 ~20:05 IST; Server 2 git
`musetp13/task-frd-046-checkpoint-2` @ `094dedb2`).

## How the approval path works (repo source, live main `8e5238a1`)

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`
  (blob `8c55456c`). `classify_approval` returns `AUTO_APPROVE` only when
  ALL hold: caller risk claim is low (LOW / NONE / MINIMAL / ROUTINE);
  no hard-bound pattern (live-money, owner-data deletion, credential
  change, Sentinel-policy change); and the action positively matches the
  low-risk class (read-only leading verb, internal housekeeping, or
  caller-attested reversible). Anything else is `OWNER_PROMPT`; the
  policy never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`
  (blob `2d8f81ea`). `submit_approval` classifies first. Auto-approve:
  writes an `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit
  ledger and only then marks the request APPROVED; if the ledger write
  fails it falls back to the owner prompt. Owner prompt:
  `_dispatch_notifications` sends the Telegram message via
  `_send_telegram` and records the request PENDING with approve/deny
  links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`
  (blob `97f4eddd`): `POST /api/v1/approvals/request` calls
  `submit_approval` and returns the pending record.
  `GET /api/v1/approvals/pending`,
  `GET /api/v1/approvals/{token}/status`. Approve/deny require an
  explicit POST from the confirmation form; the GET confirmation pages
  never change state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`
  (blob `bc3d112d`): the approvals endpoints are not exempt; a 32+ char
  `SENTINEL_API_KEY` is required (`X-API-Key` header). Live calls are
  made from Server 1 itself by throwaway scripts that read the key from
  the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`,
  the same file the live service loads) and use it in-process only. The
  key value is never printed, copied, or stored anywhere; the scripts
  are deleted after the run. Approval tokens are identified by
  `request_id` only.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`
  (blob `d4c47b9f`): `log_file_path = "logs/audit.jsonl"` → on Server 1,
  `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (run-3 verified):** the only production
  caller of `submit_approval` is the API endpoint above; no production
  code calls `wait_for_decision`. A submitted action is a *request
  record* only — nothing in the fleet executes an action because its
  approval record exists.

## Leg 1 — low-risk action auto-approved (exactly once)

- **Action:** `check sentinel health status`
- **Submitted by:** `MUSE_TP11`, `risk_level: LOW`,
  details `{"purpose": "TASK-SEN-035 leg 1 proof", "task": "TASK-SEN-035"}`
- **Expected:** `APPROVED` — `policy_tier: AUTO_APPROVE`,
  `policy_category: read_only` (same as run 3, leg 1:
  `appr_5988b5ba8538`, decided ~0.02 s after submission).
- **Evidence to collect:** submission + decision timestamps (IST and
  UTC), `request_id`, decision reason verbatim, ledger entry
  (`APPROVAL_AUTO_APPROVED`, seq + `entry_id` + hash linkage to the
  previous tail entry), service journal line, `/health` entry count
  before/after (`audit_chain_valid: true`).

## Leg 2 — high-risk action prompted on Telegram (exactly once)

- **Action:** `deploy sentinel configuration change to production`
- **Submitted by:** `MUSE_TP11`, `risk_level: HIGH`,
  details `{"purpose": "TASK-SEN-035 leg 2 proof, prompt only", "task": "TASK-SEN-035"}`
- **Expected:** no decision — `status: PENDING`,
  `policy_tier: OWNER_PROMPT`, `policy_category: caller_risk_not_low`,
  `decided_at: null`. Telegram prompt sent by `_dispatch_notifications`
  with approve/deny links; 5-minute expiry (same as run 3, leg 2:
  `appr_284a976be909`). **Prompt only — no approval is clicked.**
- **Evidence to collect:** submission timestamp (IST and UTC),
  `request_id`, `expires_at`, pending-list read showing exactly this
  one item, Telegram message id, prompt text as delivered, post-expiry
  check that the request expired PENDING (token file, if any, held on
  Server 1 only and deleted after the check).

## Pre-flight checks (before either leg)

- Both Oracle servers ONLINE (`get_system_info`).
- Sentinel `/health` 200 (`audit_chain_valid: true`,
  `kill_switch_active: false`, `audit_durable: true`) and `/ready`
  200 (`READY`, database connected, `telegram_channel: true`).
- Deployed-code check: `approval_policy.py`,
  `approval_dispatcher.py`, `apps/api/main.py`, `apps/api/middleware.py`
  on Server 1 byte-identical to this repo at S1 HEAD (run-3 method:
  md5 via `run_shell` on Server 1; `read_text` fallback compares file
  content against the repo blobs listed above).
- Classifier dry-run on the exact planned actions (repo code, no live
  effect): leg 1 → `AUTO_APPROVE / read_only`; leg 2 →
  `OWNER_PROMPT / caller_risk_not_low`.
- Pending list empty before the legs (`GET /api/v1/approvals/pending`
  → `[]`) — no other approval traffic.

## Route (decided this run)

- Owner ruling 7192682851 (2026-11-26) grants bridge `run_shell` to all
  worker chats; coordinator clearance 7200564540 covers own-task live
  verification. WATCH225 §C directs the remaining step: enable
  `run_shell` in my own local bridge-client allowlist
  (`~/workspace/custom-connectors/custom.friday-bridge/bin/client.py`,
  `ALLOWED_TOOLS`), or post the exact error if the sandbox blocks the
  edit and the coordinator executes the live leg via bridge (MEM-028
  precedent). Route decision due 21:00 IST — enablement done this run,
  see hub post.
- Live legs run from Server 1 itself via `run_shell` (throwaway
  scripts, key from the EnvironmentFile in-process only, deleted after
  the run). No server move, no restart, no env flip, no config change.

## Guardrails

- Each leg exactly once. No extra prompts fired, no low-risk action
  held — the acceptance bar.
- Leg 2 is prompt-only: the approval link is never clicked, and the
  request is left to expire PENDING.
- Stop conditions: pending list non-empty before the legs; `/health`
  or `/ready` failing; `telegram_channel: false`; classifier dry-run
  disagreeing with the expected tiers; deployed-code md5 mismatch.
  On any stop condition, post the evidence and halt — do not improvise
  a different action.
- No secret in chat, a file, or the repo — the API key stays in the
  EnvironmentFile on Server 1.

## Next

Checkpoint 2: run both legs live and file
`docs/collaboration/TASK-SEN-035-EVIDENCE.md` (timestamps, Telegram
message ids, approval records), then the work PR. Board flip to
IN_REVIEW rides the work PR.

— Muse TP11
