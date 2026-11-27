# TASK-SEN-039 — Sentinel approval-path live proof run 5 — checkpoint 1: grounding

**Task:** Sentinel: approval-path live proof run 5 — auto-approve low-risk, Telegram prompt high-risk.
**Owner:** Muse 19 · **Branch:** `muse19/task-sen-039` (from main `091bc349`)
**Claim:** hub #2045, 2026-11-27 ~09:30 IST — SEN-028 released to the pool (Burn Enforcer 09:15 §D.2, carried by WATCH200 §6/§7.2); SEN-039 claimed as queue head. Queue: REL-094 (parked) → SEN-039 (head) → top-up owed after the WATCH200 §7.2 flips land.
**Acceptance (board, main `091bc349`):** one low-risk action auto-approved and one high-risk action prompting on Telegram, each exactly once, with evidence. Follow-up run to SEN-037 (run 3), SEN-038 (run 4).
**Live-proof route (board):** live Sentinel on Oracle Server 1 + Telegram prompt receipt; file both outcomes as `docs/collaboration/TASK-SEN-039-EVIDENCE.md`.

## Prior runs (grounded first-hand this run)

- **Run 2 — TASK-SEN-036 (Muse 10), MERGED** (work PR #1971, merge `0434f6df`; evidence doc `docs/collaboration/TASK-SEN-036-APPROVAL-PATH-LIVE-PROOF-RUN-2.md`, read in full this run). Leg 1 `check sentinel health status` (MUSE_10, LOW) → AUTO_APPROVED, `appr_e52f0b36f25d`, ledger seq 38, hash-chained. Leg 2 `deploy sentinel configuration change to production` (HIGH) → OWNER_PROMPT, `appr_1bc482b7b1c0`, Telegram dispatched, no decision, expired 13:17:44 IST, approve link 409 after expiry. This run repeats the same procedure against the current deploy, with distinct actions (below).
- **Run 3 — TASK-SEN-037 (Muse TP12), CLAIMED** (branch `musetp12/task-sen-037-approval-path-live-proof-run-3`; no PR yet; implementation next). Run 5 must not duplicate run 3's legs; the run-3 evidence doc does not exist on main yet.
- **Run 4 — TASK-SEN-038 (Muse TP10), CLAIMED** (no branch yet; implementation next). Same non-duplication note as run 3.
- **Run 1 — TASK-SEN-024 (Muse 13, 2026-11-24)** and SEN-021/SEN-023 proof docs exist on main; the approval path is unchanged since run 1 (same four md5s surveyed in SEN-036).

## How the approval path works (repo source, grounded in the SEN-036 evidence doc)

- **Classifier** — `Sentinel/sentinel/gatekeeper/approval_policy.py`, `classify_approval`: AUTO_APPROVE only when ALL hold — caller risk claim low (LOW / NONE / MINIMAL / ROUTINE); no hard-bound pattern (live-money, owner-data deletion, credential change, Sentinel-policy change); and the action positively matches the low-risk class (read-only leading verb with no write verb later, internal housekeeping, or caller-attested reversible). Anything else is OWNER_PROMPT; the policy never downgrades a caller claim and never raises (fail-closed).
- **Dispatcher** — `Sentinel/sentinel/gatekeeper/approval_dispatcher.py`, `submit_approval`: classifies first. Auto-approve writes an `APPROVAL_AUTO_APPROVED` entry to the tamper-evident audit ledger and only then marks the request APPROVED; if the ledger write fails it falls back to the owner prompt. Owner prompt: `_dispatch_notifications` sends the Telegram message via `_send_telegram` and records the request PENDING with approve/deny links.
- **HTTP entry point** — `Sentinel/sentinel/apps/api/main.py`: `POST /api/v1/approvals/request` calls `submit_approval` and returns the pending record. `GET /api/v1/approvals/pending`, `GET /api/v1/approvals/{token}/status`. Approve/deny require an explicit POST from the confirmation form; the GET confirmation pages never change state.
- **Auth** — `Sentinel/sentinel/apps/api/middleware.py`: the approvals endpoints are not exempt; a 32+ char `SENTINEL_API_KEY` is required (`X-API-Key` header). Live calls are made from Server 1 itself by throwaway scripts that read the key from the systemd `EnvironmentFile` (`/opt/friday_universe/Sentinel/.env`) and use it in-process only. The key value is never printed, copied, or stored anywhere; scripts are deleted after the run. Approval tokens are never reproduced in any document — requests are identified by `request_id` only.
- **Audit ledger** — `Sentinel/sentinel/config/settings.py`: `log_file_path = "logs/audit.jsonl"` → on Server 1, `/opt/friday_universe/Sentinel/logs/audit.jsonl`.
- **No executor on this path (verified in SEN-036):** the only production caller of `submit_approval` is the API endpoint above; no production code calls `wait_for_decision`. A submitted action is a request record only — nothing in the fleet executes an action because its approval record exists.

## Proposed run-5 legs (distinct from run 2; final choice at live-leg time)

- **Leg 1 — low-risk, expect AUTO_APPROVE:** `check sentinel approval queue status` (caller MUSE_19, risk LOW). Read-only leading verb, no write verb, no hard-bound pattern. Expected: `policy_tier AUTO_APPROVE`, `policy_category read_only`, ledger `APPROVAL_AUTO_APPROVED` entry chaining onto the current tail seq.
- **Leg 2 — high-risk, expect OWNER_PROMPT + Telegram:** `rotate sentinel API key in production` (caller MUSE_19, risk HIGH). Hard-bound pattern (credential change) → OWNER_PROMPT by policy. Expected: PENDING, 5-minute expiry, Telegram prompt dispatched, no decision, approve link 409 after expiry. This is a request record only — no rotation is issued, no command runs, no file is written, no service is restarted.
- **Pre-flight (from the SEN-036 procedure):** both Oracle servers ONLINE; Sentinel `/health` 200 (`audit_chain_valid: true`, record entry count as the ledger baseline); `/ready` 200 (`telegram_channel: true`); pending list empty before the legs; classifier dry-run on the exact planned actions (repo code, no live effect); service journal checked for dispatch-error / offline-queue lines after the legs; throwaway scripts + leg-2 token file deleted after the post-expiry check.
- **Evidence to file:** `docs/collaboration/TASK-SEN-039-EVIDENCE.md` with both request ids, ledger seq + hash linkage for leg 1, pending-record fields + Telegram dispatch evidence for leg 2, and the post-expiry 409 check. Telegram `message_id` is not observable server-side (the dispatcher discards the API response) — delivery is asserted from the configured channel + clean dispatch path, as in run 2.

## Blockers — live legs QUEUED, not runnable this run

- **WATCH177 hold stands.** The run_shell grant is disputed (permissions.history: no record for approval `7113152293`; Surendra's own word on the 18:25:56 IST tap still unanswered in any source I can see). The hold text stands as posted in hub #1483 comment 7204123548. No live leg is run and no server move is attempted under the hold.
- **Bridge transport degraded (new this window).** Muse 16's DB-010/DB-012 live-leg retry failed on transport (bridge POST 403, hub #2045 comment 7208998461); WATCH200 §4 rules those legs HELD on transport + S2 headroom (6% free < 10% threshold). A run-5 live leg would need a working bridge route (or the TP6 VYR-087 client route) even after the hold lifts.
- **Runs 3 and 4 are ahead in the chain.** SEN-037 (TP12) and SEN-038 (TP10) are CLAIMED and unmerged; run 5's ledger baseline and pending-list state depend on what they append. The live leg waits for the hold + a clear run order, not just for this checkpoint.

## Checkpoint 1 status

Grounding complete from first-hand reads this run: board record (main `091bc349`), SEN-036 evidence doc (full), repo tree (approval-path files present on main), SEN-037/SEN-038 board records. No code changed; no board hunk in this commit (flip rides in the coordinator board PR). Next: live legs, queued under the blockers above.

— Muse 19, 2026-11-27 ~09:30 IST
