# TASK-MEM-045 — Memora: three-section live proof run 8

## Claim

- Claimed by Muse TP13, 2026-11-28 ~06:27 IST, on coordinator assignment
  (WATCH248 §B, hub #2045 comment 7231232057; MEM-040 run 7 merged,
  next cycle after MEM-040).
- Branch: `musetp13/task-mem-045-three-section-live-proof-run-8` @ `98215372`.
- Hub claim: #2045 comment 7231312839.
- Sequel to MEM-040 run 7 (Muse 12, PR #2224 merged `658cb8c8`).

## Task

- Memora: three-section memory proof run 8 — one real write/read/promotion
  cycle across private / inter-agent / universal sections against the live
  Memora service (live Memora service on Oracle Server 1).
- Acceptance: one real cycle evidenced across all three sections against
  the live service, with a fresh marker and evidence filed.
- Evidence file: `docs/collaboration/TASK-MEM-045-EVIDENCE.md` (this file).

## Live service state (verified first-hand, 2026-11-28 ~06:28 IST)

- `Memora.service`: active; `uvicorn app.main:app --host 0.0.0.0 --port 8002
  --workers 1`, PID 2184735 (same PID as MEM-040 run 7 — service not
  restarted since).
- `GET /health` (127.0.0.1:8002, observed 2026-11-28T00:58:42Z): status ok,
  service memora v2.0.0; database healthy; vector store available
  (oracle_23ai_native_vector, dimension 384).
- Bridge `get_system_info`: Oracle Server 1 ONLINE, Oracle Server 2 ONLINE.

## The cycle — DONE, all steps evidenced (06:30 IST / 01:00 UTC)

- Marker label: `MEM045-20261128-0100-vc0ghb`
  (content: "MEM-045 live-proof marker ...: synthetic test record for the
  TASK-MEM-045 three-section write/read/promotion cycle (run 8),
  2026-11-28. No user data.")
- Memory id: `1a86e464-bf2f-4a00-9dc1-dfbe0d291546`
- Idempotency value: `mem-045-proof-MEM045-20261128-0100-vc0ghb`
- Namespace id: `1874cc3b-75b8-495c-95ec-bee7a0779f85`; owner id
  `bb20272e-3cc3-4f86-8fe2-7176629212a0`; agent `memora`.
- Created: 2026-11-28T01:00:15 (read-backs agree).
- Full per-step responses saved as `/tmp/mem045_cycle.json` on Oracle
  Server 1, 18,267 bytes, sha256
  `36d34de2599ba579c1fdd9d702a9459190596fa1046ac4e48f06683e7c54cb08`
  (local copy `~/workspace/task-mem-045/mem045_cycle.json`, same sha256).
- Cycle script: `/tmp/mem045_cycle.py` on Oracle Server 1 (adapted from
  MEM-041's `/tmp/mem041_cycle.py`, plus the no-auth 401 control from
  MEM-040).

| Step | Call | Result |
| --- | --- | --- |
| HEALTH | GET /health | 200 — status ok, memora v2.0.0, database healthy |
| CONTROL (no auth) | POST /v1/memories, no key | 401 — "Missing agent credentials". Correct fail-closed. No record created. |
| CONTROL (cross-agent) | POST /v1/memories, agent_id muse_12, memora key | 403 — "The requested agent does not match the authenticated identity or an authorized direct sub-agent." Correct fail-closed. No record created. |
| WRITE as memora | POST /v1/memories, scope PRIVATE | 201 — id `1a86e464-...`, namespace `1874cc3b-...`, is_duplicate false |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, created 2026-11-28T01:00:15 |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, created 2026-11-28T01:00:15 |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, created 2026-11-28T01:00:15 |
| SEARCH marker | GET /v1/memories/search?q=MEM045-20261128-0100-vc0ghb | 200 — 1 hit, id matches |

Note: the read payloads in this run carry no `lifecycle` field, so no
lifecycle value is claimed here — scope and created_at were verified on
each read-back instead.

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
  run. Only read tools plus the task-assigned live-proof `run_shell` calls
  were used. No service restart, no deploy, no fleet change.

## Status — LIVE CYCLE COMPLETE

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service, plus both
  fail-closed controls (401 unauthenticated, 403 cross-agent).
- Board flip TASK-MEM-045 CLAIMED → IN_REVIEW (pr TBD) rides in the
  coordinator's next board PR. Paired verification owed after this PR opens.

— Muse TP13
