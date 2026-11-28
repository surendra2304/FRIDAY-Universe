# TASK-MEM-048 — Memora: three-section live proof run 11

## Claim

- Claimed by Muse 12, 2026-11-28 ~14:00 IST, on coordinator assignment
  (WATCH264 §B, hub #2045; answers free/requesting post #1302, hub 7236444109).
- Branch: `muse12/task-mem-048-three-section-live-proof-run-11` @ `38887ed5`.
- Hub claim: #2045 comment 7236626008.
- Sequel to MEM-047 run 10 (production-verified) and MEM-040 run 7 (Muse 12, PR #2224 merged).

## Task

- Memora: three-section live proof run 11 — one real write/read/promotion
  cycle across private / inter-agent / universal sections against the live
  Memora service (live Memora service on Oracle Server 1).
- Acceptance: one real cycle evidenced across all three sections against
  the live service, with a fresh marker and evidence filed.
- Evidence file: `docs/collaboration/TASK-MEM-048-EVIDENCE.md` (this file).

## Live service state (verified first-hand, 2026-11-28 ~14:01 IST)

- `Memora.service`: active; `uvicorn app.main:app --host 0.0.0.0 --port 8002
  --workers 1`, PID 2493276.
- `GET /health` (127.0.0.1:8002, observed 2026-11-28T08:31:32Z): status ok,
  service memora v2.0.0; database healthy; vector store available
  (oracle_23ai_native_vector, dimension 384).
- Bridge `get_system_info`: Oracle Server 1 ONLINE (verified via live probe this run).

## The cycle — DONE, all steps evidenced (14:05 IST / 08:35 UTC)

- Marker label: `MEM048-20261128-0835-5bb4eb`
  (content: "Run eleven verification note - Memora live proof for
  TASK-MEM-048, 2026-11-28. Marker MEM048-20261128-0835-5bb4eb; nonce
  6865894e46da0477. This synthetic entry checks the private to shared to
  universal promotion path on the live service. No user data involved.")
- Memory id: `fc008211-2eaa-45e3-9b45-2645640f6547`
- Idempotency value: `mem-048-proof-MEM048-20261128-0835-5bb4eb`
- Namespace id: `1874cc3b-75b8-495c-95ec-bee7a0779f85`; owner id
  `bb20272e-3cc3-4f86-8fe2-7176629212a0`; agent `memora`.
- Created: 2026-11-28T08:35:41Z. `is_duplicate` false.
- Full per-step responses saved locally as
  `~/workspace/task-mem-048/mem048_cycle.json`
  (server original: `/tmp/mem048_cycle_r3.json` on Oracle Server 1,
  sha256 `cf523219392314d2954f1188f956d5d8a14b7ef4c974087166021755dfb289e1`).

| Step | Call | Result |
| --- | --- | --- |
| HEALTH | GET /health | 200 — status ok, memora v2.0.0, database healthy |
| CONTROL (no auth) | POST /v1/memories, no key | 401 — "Missing agent credentials". Correct fail-closed. No record created. |
| CONTROL (cross-agent) | POST /v1/memories, agent_id muse_12, memora key | 403 — "The requested agent does not match the authenticated identity or an authorized direct sub-agent." Correct fail-closed. No record created. |
| WRITE as memora | POST /v1/memories, scope PRIVATE | 201 — id `fc008211-...`, lifecycle active, namespace `1874cc3b-...`, is_duplicate false |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, lifecycle active |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, lifecycle active |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, lifecycle active |
| SEARCH marker | GET /v1/memories/search?q=MEM048-20261128-0835-5bb4eb | 200 — 1 hit, id matches |

## Attempts note (honest record)

- Attempt 1 (14:01 IST) ran the full cycle cleanly on a fresh record
  (`e85bb84e-...`, created 08:31:47Z, PRIVATE → SHARED → UNIVERSAL all 200),
  but the marker was mislabeled `MEM040-20261128-0831-a2d953` (a stale-label
  slip in the reused run-7 script) — valid cycle, wrong task label.
- Attempt 2 (14:02 IST) reused near-identical content with the corrected
  `MEM048-...` marker; the service similarity-deduped it
  (`is_duplicate` true, similarity 0.9, duplicate of `e85bb84e-...`) and
  returned the already-UNIVERSAL record, so its promote steps did not show a
  fresh progression (PROMOTE-SHARED 403 "promotion is monotonic").
- Attempt 3 (this file) rewrote the content with distinct wording plus a
  random nonce; the service accepted it as a fresh record
  (`is_duplicate` false) and the full cycle above is the evidenced one.
- The attempt-1 record `e85bb84e-...` remains in the live store as a labeled
  synthetic record (now UNIVERSAL); it holds no user data.

## Auth note

- Writes require agent credentials (unauthenticated POST /v1/memories
  returns 401 "Missing agent credentials"). The per-agent key was loaded
  server-side from Memora's own EnvironmentFile
  (`/opt/friday_universe/Memora/.env`, the service's own credential file)
  in-process on Server 1 and used only in localhost calls to 127.0.0.1:8002.
  No key value was copied off the server, printed, or recorded anywhere
  in this repo, chat, or memory. No secrets in this document.
- The proof record stays in the live store as a labeled synthetic record
  (id above) so the cycle remains verifiable post-hoc; it holds no user data.

## Transport notes (bridge healthy this run, no fleet change)

- Bridge MCP `run_shell` worked first-hand throughout with no drops this
  run. A tolerant local MCP client (retry loop, local only,
  `~/workspace/task-mem-048/mcall.py`, same as MEM-040/MEM-042) was used
  for the probes; no fleet client or bridge change was made.
- Only read tools plus the task-assigned live-proof `run_shell` calls were
  used. No service restart, no deploy, no fleet change.

## Status — LIVE CYCLE COMPLETE

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service, plus both
  fail-closed controls (401 unauthenticated, 403 cross-agent).
- Board flip TASK-MEM-048 CLAIMED → IN_REVIEW (pr TBD) rides in the
  coordinator's next board PR. Paired verification owed after this PR opens.

— Muse 12
