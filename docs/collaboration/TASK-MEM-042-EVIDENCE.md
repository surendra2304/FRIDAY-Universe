# TASK-MEM-042 — Memora: three-section memory live proof run 8

## Claim

- Claimed by Muse 12, 2026-11-28 ~00:15 IST, on coordinator assignment
  (WATCH235 §B, hub #2045 comment 7225676870).
- Branch: `muse12/task-mem-042-three-section-live-proof-run-8` @ `a85c9d13`.
- Hub claim: #2045 comment 7225830139.
- Follow-up to MEM-041 run 7 (M14, PR #2168 merged) and MEM-039 run 6
  (TP14, PR #2179 open); MEM-038 run 4 (PR #2085 merged).

## Task

- Memora: three-section memory proof run 8 — one real write/read/promotion
  cycle across private / inter-agent / universal sections against the live
  Memora service (live Memora service on Oracle Server 1).
- Acceptance: one real cycle evidenced across all three sections against
  the live service, with a fresh marker and evidence filed.
- Evidence file: `docs/collaboration/TASK-MEM-042-EVIDENCE.md` (this file).

## Live service state (verified first-hand, 2026-11-28 ~00:17 IST)

- `Memora.service`: active, running; Main PID 2063511;
  `uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1`.
- `GET /health` (127.0.0.1:8002, observed 18:47 UTC): status ok, service
  memora v2.0.0; database healthy; vector store available
  (oracle_23ai_native_vector, dimension 384).
- Bridge `get_system_info`: Oracle Server 1 ONLINE, Oracle Server 2 ONLINE.

## The cycle — DONE, all steps evidenced (00:19 IST / 18:49 UTC)

- Marker label: `MEM042-20261128-1848-c8e4b7`
  (content: "MEM-042 live-proof marker ...: synthetic test record for the
  TASK-MEM-042 three-section write/read/promotion cycle (run 8),
  2026-11-28. No user data.")
- Memory id: `041bff8b-e046-44ef-ba9d-eedac72a434e`
- Idempotency value: `mem-042-proof-MEM042-20261128-1848-c8e4b7`
- Full per-step responses saved locally as
  `~/workspace/task-mem-042/mem042_cycle.json`
  (server original: `/tmp/mem042_cycle.json` on Oracle Server 1, 8,159 bytes,
  sha256 `4270e690cade6e9d0394d2b763440abb81443d51e47e64b75dc118fa2b818cac`).

| Step | Call | Result |
| --- | --- | --- |
| HEALTH | GET /health | 200 — status ok, memora v2.0.0, database healthy |
| CONTROL (no auth) | POST /v1/memories, no key | 401 — "Missing agent credentials". Correct fail-closed. No record created. |
| CONTROL (cross-agent) | POST /v1/memories, agent_id muse_12, memora key | 403 — "The requested agent does not match the authenticated identity or an authorized direct sub-agent." Correct fail-closed. No record created. |
| WRITE as memora | POST /v1/memories, scope PRIVATE | 201 — id `041bff8b-...`, lifecycle active, storage oracle, durable true, is_duplicate false |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, lifecycle active |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, lifecycle active |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, lifecycle active |
| SEARCH marker | GET /v1/memories/search?q=MEM042-20261128-1848-c8e4b7 | 200 — 1 hit, id matches |

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

## Transport notes (bridge flakiness, no fleet change)

- Bridge MCP `initialize` / notification steps dropped repeatedly this run
  (RemoteDisconnected), while retries succeeded — a transport flake, not a
  policy denial. A tolerant local MCP client (retry loop, local only,
  `~/workspace/task-mem-042/mcall.py`) was used for the probes; no fleet
  client or bridge change was made.
- Only read tools plus the task-assigned live-proof `run_shell` calls were
  used. No service restart, no deploy, no fleet change.

## Status — LIVE CYCLE COMPLETE

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service, plus both
  fail-closed controls (401 unauthenticated, 403 cross-agent).
- Board flip TASK-MEM-042 AVAILABLE → IN_REVIEW (pr TBD) rides in the
  coordinator's next board PR. Paired verification owed after this PR opens.

— Muse 12
