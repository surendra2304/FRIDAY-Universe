# TASK-MEM-049 — Memora: live proof cycle 7

## Claim

- Claimed by Muse 12, 2026-11-28 ~16:33 IST, on coordinator assignment
  (WATCH269 §C, hub #2045 comment 7238212243; board PR #2338 record:
  status CLAIMED / owner muse_12, P1).
- Branch: `muse12/task-mem-049-live-proof-cycle-7` @ `3b5091de`.
- Hub claim: #2045 comment 7238289244.
- Sequel to MEM-048 run 11 (Muse 12, PR #2317 merged) and MEM-047 run 10
  (production-verified).

## Task

- Memora: live proof cycle 7 — one real write/read/promotion cycle across
  private / inter-agent / universal sections against the live Memora
  service (live Memora service on Oracle Server 1), with a fresh marker.
- Acceptance: one real cycle evidenced across all three sections against
  the live service, with a fresh marker and evidence filed.
- Evidence file: `docs/collaboration/TASK-MEM-049-EVIDENCE.md` (this file).

## Live service state (verified first-hand, 2026-11-28 ~16:36 IST)

- `Memora.service`: active (running) since 14:27:36 IST;
  `uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1`,
  PID 2569599, listening on 0.0.0.0:8002.
- `GET /health` (127.0.0.1:8002, observed 2026-11-28T11:05:34Z): status ok,
  service memora v2.0.0; database healthy.
- Bridge `get_system_info`: Oracle Server 1 ONLINE, Oracle Server 2 ONLINE
  (verified via live probe this run).

## The cycle — DONE, all steps evidenced (16:36 IST / 11:05 UTC)

- Marker label: `MEM049-20261128-1105-25ee82`
  (content: "MEM-049 proof entry, cycle 7, dated 2026-11-28. A fresh
  synthetic memory placed in the private section to exercise promotion
  into the inter-agent section and then the universal section. Marker
  MEM049-20261128-1105-25ee82; nonce d214de05d70e2535. Nothing here is user
  data; this record exists only to evidence the live promotion path.")
- Memory id: `20102f58-0be9-47c6-95ae-9634907729c2`
- Idempotency value: `mem-049-proof-MEM049-20261128-1105-25ee82`
- Namespace id: `1874cc3b-75b8-495c-95ec-bee7a0779f85`; owner id
  `bb20272e-3cc3-4f86-8fe2-7176629212a0`; agent `memora`.
- Created: 2026-11-28T11:05:34Z. `is_duplicate` false, similarity 0.0.
- Content sha256: `1a6d06f7b371b5034a2f6c02246ef335c099b410f0249091d064f669a500dfd2`.
- Full per-step responses saved locally as
  `~/workspace/task-mem-049/mem049_cycle.json`
  (server original: `/tmp/mem049_cycle.json` on Oracle Server 1,
  sha256 `16d53451364ac45a5983a49a8b5e2a27d38733af38ee3cd0eb8477d5ef6c7e6b`).

| Step | Call | Result |
| --- | --- | --- |
| HEALTH | GET /health | 200 — status ok, memora v2.0.0, database healthy |
| CONTROL (no auth) | POST /v1/memories, no key | 401 — "Missing agent credentials". Correct fail-closed. No record created. |
| CONTROL (cross-agent) | POST /v1/memories, agent_id muse_12, memora key | 403 — "The requested agent does not match the authenticated identity or an authorized direct sub-agent." Correct fail-closed. No record created. |
| WRITE as memora | POST /v1/memories, scope PRIVATE | 201 — id `20102f58-...`, lifecycle active, namespace `1874cc3b-...`, is_duplicate false |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, lifecycle active |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, lifecycle active |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, lifecycle active |
| SEARCH marker | GET /v1/memories/search?q=MEM049-20261128-1105-25ee82 | 200 — 1 hit, id matches |

## Attempts note (honest record)

- Single attempt, clean on the first run (16:35–16:36 IST). Content wording
  was written distinct from MEM-048 to avoid the similarity-dedup the
  MEM-048 run hit on its second attempt; the service accepted the record
  as fresh (`is_duplicate` false, similarity 0.0).

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
  `~/workspace/task-mem-049/mcall.py`, same as MEM-040/MEM-042/MEM-048)
  was used for the probes; no fleet client or bridge change was made.
- Only read tools plus the task-assigned live-proof `run_shell` calls were
  used. No service restart, no deploy, no fleet change.

## Status — LIVE CYCLE COMPLETE

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service, plus both
  fail-closed controls (401 unauthenticated, 403 cross-agent).
- Board flip TASK-MEM-049 CLAIMED → IN_REVIEW (pr TBD) rides in the
  coordinator's next board PR. Paired verification owed after this PR opens.

— Muse 12
