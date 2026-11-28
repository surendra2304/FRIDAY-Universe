# TASK-MEM-046 — Memora: three-section memory live proof run 9

## Claim

- Claimed by Muse 14, 2026-11-28 ~10:27 IST, by central-pool pull
  (work-request schedule; claim is the hub #2045 comment below);
  re-claimed ~10:41 IST after a bridge outage blocked the first attempt.
- Branch: `muse14/task-mem-046-live-proof-run-9` @ `7ecab6ce`
  (re-based to current main `68790fb5` immediately before opening the PR).
- Hub claim: #2045 comment 7234368798; block: #2045 comment 7234445762
  (~10:35 IST); re-claim: #2045 comment 7234529134 (~10:41 IST).
- Follow-up to MEM-045 run 8 (merged `5533689f`) and MEM-044 run 10
  (Muse 14, PR #2215 merged) and MEM-043 run 9 (PR #2212 open) and
  MEM-041 run 7 (Muse 14, PR #2168 merged). Per WATCH256 §D numbering:
  MEM-046 is run 9, MEM-047 is run 10.

## Task

- Memora: three-section memory proof run 9 — one real write/read/promotion
  cycle across private / inter-agent / universal sections against the live
  Memora service (live Memora service on Oracle Server 1).
- Acceptance: one real cycle evidenced across all three sections against
  the live service.
- Evidence file: `docs/collaboration/TASK-MEM-046-EVIDENCE.md` (this file).

## Bridge outage before this run (blocked first attempt, ~10:29–10:34 IST)

- The first live-leg attempt (subagent, ~10:29–10:34 IST) could not start:
  the bridge (`https://friday-universe.duckdns.org/bridge/mcp`) accepted TCP
  443 and then closed the connection without any HTTP response —
  `Remote end closed connection without response`. 9 consecutive failures
  (mcall.py get_system_info ×8, raw curl POST initialize HTTP 000,
  probe.py get_system_info after a 60 s wait). The parent's own probe.py
  call failed with the same symptom. No cycle was run, no evidence filed,
  no PR opened; the block was posted on hub #2045 (comment 7234445762,
  ~10:35 IST) and MEM-046 was released to the pool.
- This is NOT M16's 403 (WATCH256 §D): M16's symptom was an HTTP 403 on
  POST /bridge/mcp. M14 never received any HTTP status at all during the
  outage — the bridge was unreachable in a different way.
- The bridge recovered ~10:41 IST: probe.py get_system_info exit 0 —
  FRIDAY-Cloud-Engineering-Bridge v1.30.0, both Oracle servers ONLINE,
  isError false (verified first-hand by the work-request run and by the
  parent). That recovery was the condition the block set for re-claim;
  MEM-046 was re-claimed ~10:41 IST (hub #2045 comment 7234529134) and
  this run proceeded. No workaround was attempted during the outage:
  no alternate route, no retry through another client, no local simulation.

## Live service state (verified first-hand, 2026-11-28 ~10:45 IST)

- `Memora.service`: loaded, active, running since 02:18:02 IST; Main PID
  2184735; `uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1`.
  (Same PID as runs 9 and 10 — no restart between run 10 and run 9's
  re-claim; the service was not restarted for this run.)
- `GET /health` (127.0.0.1:8002, observed 05:15:22 UTC): status ok, service
  memora v2.0.0; database healthy; vector store available
  (oracle_23ai_native_vector, dimension 384).
- `get_system_info` via bridge: Oracle Server 1 ONLINE, Oracle Server 2
  ONLINE.

## The cycle — DONE, all steps evidenced (10:45 IST / 05:15 UTC)

- Marker label: `MEM046-20261128-0515-ssz1j3`
  (content: "MEM-046 live-proof marker ...: synthetic test record for the
  TASK-MEM-046 three-section write/read/promotion cycle (run 9),
  2026-11-28. No user data.")
- Memory id: `62eff103-7f6b-49a6-ae64-1fb42b624f7e`
- Idempotency value: `mem-046-proof-MEM046-20261128-0515-ssz1j3`
- Full per-step responses saved locally as
  `~/workspace/agents/muse14/task-mem-046/mem046_cycle.json`
  (18,040 bytes; the server copy at `/tmp/mem046_cycle.json` on Oracle
  Server 1 was deleted after retrieval, per the leg's cleanup rule —
  the record itself stays in the live store, id above).

| Step | Call | Result |
| --- | --- | --- |
| HEALTH | GET /health | 200 — status ok, memora v2.0.0, database healthy, vector store available |
| WRITE as muse_14 | POST /v1/memories, agent_id muse_14, scope PRIVATE | 403 — "The requested agent does not match the authenticated identity or an authorized direct sub-agent." Correct fail-closed: authenticated as memora, ownership cannot be assigned to another agent. No record created. |
| WRITE as memora | POST /v1/memories, scope PRIVATE | 201 — id `62eff103-...`, lifecycle_state active, storage_backend oracle, storage_durable true, is_duplicate false |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, lifecycle_state active |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, lifecycle_state active |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, lifecycle_state active |
| SEARCH marker | GET /v1/memories/search?q=MEM046-20261128-0515-ssz1j3 | 200 — 1 hit, id matches. (Hit's namespace_path stays `memora://memora/private` — promotion changes the scope tier, not the namespace path; same as runs 4, 7, 9 and 10.) |

## Method note

- Same method as MEM-044 (run 10) with no change except the run number
  and marker. One correction to the prepared script before execution:
  the adaptation had carried over the MEM-044 marker prefix (`MEM044-`);
  it was fixed to `MEM046-` before the run so the marker, content,
  and idempotency key all name run 9.

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

## Transport notes (bridge outage, no fleet change)

- The bridge `run_shell` / `get_system_info` worked first time after the
  recovery (no RemoteDisconnected drops during this run). The same
  tolerant local MCP client (`~/workspace/agents/muse14/task-mem-041/mcall.py`)
  was used for the probes; no fleet client or bridge change was made.
- The bridge `read_file` tool reads the bridge host's filesystem, not
  Oracle Server 1; the cycle JSON was retrieved with `run_shell` `cat`
  instead (same as runs 7, 9 and 10).

## Status — LIVE CYCLE COMPLETE

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service.
- Board flip TASK-MEM-046 AVAILABLE → IN_REVIEW (pr TBD) rides in the
  coordinator's next board PR. Paired verification owed after this PR opens.

— Muse 14
