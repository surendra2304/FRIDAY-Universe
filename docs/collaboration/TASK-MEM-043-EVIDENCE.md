# TASK-MEM-043 — Memora: three-section memory live proof run 9

## Claim

- Claimed by Muse 14, 2026-11-28 ~03:32 IST, by central-pool pull
  (work-request schedule; claim is the hub #2045 comment below).
- Branch: `muse14/task-mem-043` @ `72490c60`.
- Hub claim: #2045 comment 7228971629.
- Follow-up to MEM-042 run 8 (PR #2187 merged) and MEM-041 run 7
  (Muse 14, PR #2168 merged).

## Task

- Memora: three-section memory proof run 9 — one real write/read/promotion
  cycle across private / inter-agent / universal sections against the live
  Memora service (live Memora service on Oracle Server 1).
- Acceptance: one real cycle evidenced across all three sections against
  the live service.
- Evidence file: `docs/collaboration/TASK-MEM-043-EVIDENCE.md` (this file).

## Live service state (verified first-hand, 2026-11-28 ~03:38 IST)

- `Memora.service`: loaded, active, running since 02:18:02 IST; Main PID
  2184735; `uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1`.
  (The service restarted between run 7 and run 9: run 7 saw PID 1448930
  since 03:24:06 IST on 2026-11-27; run 9 sees PID 2184735 since
  02:18:02 IST on 2026-11-28. No restart happened during this leg.)
- `GET /health` (127.0.0.1:8002, observed 22:09:07 UTC): status ok, service
  memora v2.0.0; database healthy; vector store available
  (oracle_23ai_native_vector, dimension 384).
- `get_system_info` via bridge: Oracle Server 1 ONLINE, Oracle Server 2
  ONLINE.

## The cycle — DONE, all steps evidenced (03:39 IST / 22:09 UTC)

- Marker label: `MEM043-20261127-2209-ymiu9k`
  (content: "MEM-043 live-proof marker ...: synthetic test record for the
  TASK-MEM-043 three-section write/read/promotion cycle (run 9),
  2026-11-28. No user data.")
- Memory id: `038b5f29-864a-49c6-a849-d1eceae7c649`
- Idempotency value: `mem-043-proof-MEM043-20261127-2209-ymiu9k`
- Full per-step responses saved locally as
  `~/workspace/agents/muse14/task-mem-043/mem043_cycle.json`
  (18,041 bytes; the server copy at `/tmp/mem043_cycle.json` on Oracle
  Server 1 was deleted after retrieval, per the leg's cleanup rule —
  the record itself stays in the live store, id above).

| Step | Call | Result |
| --- | --- | --- |
| HEALTH | GET /health | 200 — status ok, memora v2.0.0, database healthy, vector store available |
| WRITE as muse_14 | POST /v1/memories, agent_id muse_14, scope PRIVATE | 403 — "The requested agent does not match the authenticated identity or an authorized direct sub-agent." Correct fail-closed: authenticated as memora, ownership cannot be assigned to another agent. No record created. |
| WRITE as memora | POST /v1/memories, scope PRIVATE | 201 — id `038b5f29-...`, lifecycle active, storage oracle, durable true, is_duplicate false |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, lifecycle active |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, lifecycle active |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, lifecycle active |
| SEARCH marker | GET /v1/memories/search?q=MEM043-20261127-2209-ymiu9k | 200 — 1 hit, id matches. (Hit's namespace_path stays `memora://memora/private` — promotion changes the scope tier, not the namespace path; same as runs 4 and 7.) |

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

- Bridge `run_shell` / `get_system_info` worked first time this run
  (no RemoteDisconnected drops, unlike run 7). The same tolerant local
  MCP client (`~/workspace/agents/muse14/task-mem-041/mcall.py`) was used
  for the probes; no fleet client or bridge change was made.
- The bridge `read_file` tool reads the bridge host's filesystem, not
  Oracle Server 1; the cycle JSON was retrieved with `run_shell` `cat`
  instead (same as run 7).

## Status — LIVE CYCLE COMPLETE

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service.
- Board flip TASK-MEM-043 AVAILABLE → IN_REVIEW (pr TBD) rides in the
  coordinator's next board PR. Paired verification owed after this PR opens.

— Muse 14
