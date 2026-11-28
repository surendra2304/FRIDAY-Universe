# TASK-MEM-040 — Memora: three-section live proof run 7

## Claim

- Claimed by Muse 12, 2026-11-28 ~03:58 IST, on coordinator assignment
  (WATCH243 §C / BE 03:42 §C, hub #2045; MEM-042 complete, free requesting work).
- Branch: `muse12/task-mem-040-three-section-live-proof-run-7` @ `901a1114`.
- Hub claim: #2045 comment 7229359500.
- Sequel to MEM-042 run 8 (Muse 12, PR #2187 merged) and MEM-039 run 6 (TP14).

## Task

- Memora: three-section memory proof run 7 — one real write/read/promotion
  cycle across private / inter-agent / universal sections against the live
  Memora service (live Memora service on Oracle Server 1).
- Acceptance: one real cycle evidenced across all three sections against
  the live service, with a fresh marker and evidence filed.
- Evidence file: `docs/collaboration/TASK-MEM-040-EVIDENCE.md` (this file).

## Live service state (verified first-hand, 2026-11-28 ~04:58 IST)

- `Memora.service`: active; `uvicorn app.main:app --host 0.0.0.0 --port 8002
  --workers 1`, PID 2184735.
- `GET /health` (127.0.0.1:8002, observed 2026-11-27T23:28:03Z): status ok,
  service memora v2.0.0; database healthy; vector store available
  (oracle_23ai_native_vector, dimension 384).
- Bridge `get_system_info`: Oracle Server 1 ONLINE, Oracle Server 2 ONLINE.

## The cycle — DONE, all steps evidenced (04:58 IST / 23:28 UTC)

- Marker label: `MEM040-20261128-2328-fffdb5`
  (content: "MEM-040 live-proof marker ...: synthetic test record for the
  TASK-MEM-040 three-section write/read/promotion cycle (run 7),
  2026-11-28. No user data.")
- Memory id: `c1eec0dc-92ee-4f60-981a-088f836423e9`
- Idempotency value: `mem-040-proof-MEM040-20261128-2328-fffdb5`
- Namespace id: `1874cc3b-75b8-495c-95ec-bee7a0779f85`; owner id
  `bb20272e-3cc3-4f86-8fe2-7176629212a0`; agent `memora`.
- Created: 2026-11-27T23:28:55Z.
- Full per-step responses saved locally as
  `~/workspace/task-mem-040/mem040_cycle.json`
  (server original: `/tmp/mem040_cycle.json` on Oracle Server 1, 8,159 bytes,
  sha256 `bf6831d53289f3dc30f764471518103cafa5495865f1df94dfc6539fe9204d4d`).

| Step | Call | Result |
| --- | --- | --- |
| HEALTH | GET /health | 200 — status ok, memora v2.0.0, database healthy |
| CONTROL (no auth) | POST /v1/memories, no key | 401 — "Missing agent credentials". Correct fail-closed. No record created. |
| CONTROL (cross-agent) | POST /v1/memories, agent_id muse_12, memora key | 403 — "The requested agent does not match the authenticated identity or an authorized direct sub-agent." Correct fail-closed. No record created. |
| WRITE as memora | POST /v1/memories, scope PRIVATE | 201 — id `c1eec0dc-...`, lifecycle active, namespace `1874cc3b-...`, is_duplicate false |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, lifecycle active |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, lifecycle active |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, lifecycle active |
| SEARCH marker | GET /v1/memories/search?q=MEM040-20261128-2328-fffdb5 | 200 — 1 hit, id matches |

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
  run (contrast MEM-042, which saw repeated initialize drops). A tolerant
  local MCP client (retry loop, local only,
  `~/workspace/task-mem-040/mcall.py`, same as MEM-042) was used for the
  probes; no fleet client or bridge change was made.
- Only read tools plus the task-assigned live-proof `run_shell` calls were
  used. No service restart, no deploy, no fleet change.

## Status — LIVE CYCLE COMPLETE

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service, plus both
  fail-closed controls (401 unauthenticated, 403 cross-agent).
- Board flip TASK-MEM-040 CLAIMED → IN_REVIEW (pr TBD) rides in the
  coordinator's next board PR. Paired verification owed after this PR opens.

— Muse 12
