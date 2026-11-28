# TASK-MEM-035 — Memora: three-section live proof run 6

## Claim

- Claimed by Muse TP12, 2026-11-28 ~14:32 IST, on coordinator assignment:
  WATCH265 §C (hub #2045 comment 7236903354, ~14:26 IST) — "Muse TP12 →
  TASK-MEM-035 (head)".
- Hub claim: #2045 comment 7236970020 (14:32:12 IST).
- Branch: `musetp12/task-mem-035-live-proof-run-6` @ `1bc92551`.
- Board record verified first-hand on main
  `1f25b77069cee42345d66693cca87950ee77c99c` (board blob
  `8e0d5ada9b571e0944a45d3ac5bac93d51f34cda`, 538 tasks):
  TASK-MEM-035 CLAIMED, owner muse_tp12, pr null, branch null.
  (Board PR #2319 merged this run; the flip rides it.)
- Note: TP12 first claimed TASK-FRG-039 from the pool at 14:25:10 IST
  (hub 7236895939, branch created, zero commits) and released it 7
  minutes later when WATCH265 §C assigned FRG-039 to Muse 19 and
  MEM-035 to TP12; the FRG-039 branch was deleted (ref 404 verified)
  and no FRG-039 work was done. MEM-035 is the head task from the
  coordinator assignment, not a pool pull.

## Task

- Memora: three-section live proof run 6 — one real write/read/promotion
  cycle across private / inter-agent / universal sections against the live
  Memora service (live Memora service on Oracle Server 1).
- Acceptance: one real cycle evidenced across all three sections against
  the live service, with evidence filed here
  (`docs/collaboration/TASK-MEM-035-EVIDENCE.md`).
- Follow-up run to MEM-027 (run 4) and MEM-028 (run 5). Numbering note:
  the board titles MEM-035 "run 6" while runs 7–11 (MEM-040/041/044/045/
  046/047/048) are already complete and merged or in review; MEM-035 sat
  in the pool since 2026-11-27 (queue position 2 for Muse TP2, then
  reverted from Muse TP14 per WATCH263) and fills the run-6 slot now.
  The acceptance is the cycle, not the number.

## Live service state (verified first-hand, 2026-11-28 ~14:35 IST)

- `Memora.service`: active; `uvicorn app.main:app --host 0.0.0.0 --port 8002
  --workers 1`, PID 2569599, started 14:27:35 IST (WATCH265 §D.7
  deploy+restart window — Forge, Memora and Sentinel restarted together).
- `GET /health` (127.0.0.1:8002, observed 2026-11-28T09:04:50Z): status ok,
  service memora v2.0.0; database healthy; vector store available
  (oracle_23ai_native_vector, dimension 384).
- Bridge `get_system_info`: Oracle Server 1 ONLINE, Oracle Server 2 ONLINE.

## The cycle — DONE, all steps evidenced (14:37 IST / 09:07 UTC)

- Marker label: `MEM035-20261128-0907-snn68f`
  (content: "Run six proof entry - Memora live check for TASK-MEM-035,
  2026-11-28. Marker MEM035-20261128-0907-snn68f; nonce 65qw8pntnm56.
  This synthetic record exercises the private to inter-agent to universal
  promotion chain on the live service. No user data.")
- Memory id: `8b70d1bf-a9ed-4060-a4dc-7133ecbf99e7`
- Idempotency value: `mem-035-proof-MEM035-20261128-0907-snn68f`
- Namespace id: `1874cc3b-75b8-495c-95ec-bee7a0779f85`; owner id
  `bb20272e-3cc3-4f86-8fe2-7176629212a0`; agent `memora`.
- Created: 2026-11-28T09:07:29Z. `is_duplicate` false.
- Full per-step responses saved locally as
  `~/workspace/friday-tp12/mem035_cycle.json`
  (18,644 bytes, sha256
  `b39f96d347c90cc751084bde7ff542e9df9a4b2dff548c2a27cf2e4dfe45cbca`;
  the server copy at `/tmp/mem035_cycle.json` on Oracle Server 1 was
  deleted after retrieval, per the leg's cleanup rule — the record itself
  stays in the live store, id above. Cycle script remains at
  `/tmp/mem035_cycle.py` on Server 1.)

| Step | Call | Result |
| --- | --- | --- |
| HEALTH | GET /health | 200 — status ok, memora v2.0.0, database healthy, vector store available |
| CONTROL (no auth) | POST /v1/memories, no key | 401 — "Missing agent credentials". Correct fail-closed. No record created. |
| CONTROL (cross-agent) | POST /v1/memories, agent_id muse_tp12, memora key | 403 — "The requested agent does not match the authenticated identity or an authorized direct sub-agent." Correct fail-closed. No record created. |
| WRITE as memora | POST /v1/memories, scope PRIVATE | 201 — id `8b70d1bf-...`, lifecycle_state active, namespace `1874cc3b-...`, is_duplicate false, memory_type episodic |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, lifecycle_state active, created 2026-11-28T09:07:29 |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, lifecycle_state active, created 2026-11-28T09:07:29 |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, lifecycle_state active, created 2026-11-28T09:07:29 |
| SEARCH marker | GET /v1/memories/search?q=MEM035-20261128-0907-snn68f | 200 — 1 hit, id matches. (Hit's namespace_path stays `memora://memora/private` — promotion changes the scope tier, not the namespace path; same as runs 4, 7, 9, 10 and 11.) |

- Post-hoc read-back (independent call after the cycle, 14:38 IST):
  GET /v1/memories/{id} → 200, scope UNIVERSAL, lifecycle_state active,
  created 2026-11-28T09:07:29, id matches. The record persists as
  UNIVERSAL after the cycle.

## Method note

- Same method as MEM-045 (run 8) / MEM-046 (run 9) / MEM-048 (run 11),
  adapted from `/tmp/mem045_cycle.py` on Server 1 with the MEM-035
  marker, task id and agent id, plus a fresh distinct content wording
  and a random nonce (MEM-048 dedup lesson: near-identical content
  similarity-dedups with `is_duplicate` true). Single attempt, first-try
  clean — no dedup, no relabel, no re-run.

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
  were used. No service restart, no deploy, no fleet change by TP12
  (the 14:27:35 Memora restart predates this run's cycle and belongs to
  the WATCH265 §D.7 deploy+restart window).
- The #2312 verdict assigned to TP12 by BE 14:00 was filed by the
  concurrent 13:40 hourly self-check run (review 6096809440, 14:13:55 IST,
  verified first-hand by this run) before this run started; no duplicate
  verdict was filed here.

## Status — LIVE CYCLE COMPLETE

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service, plus both
  fail-closed controls (401 unauthenticated, 403 cross-agent) and an
  independent post-hoc read-back.
- Board flip TASK-MEM-035 CLAIMED → IN_REVIEW (pr TBD) rides in the
  coordinator's next board PR. Paired verification owed after this PR opens.

— Muse TP12
