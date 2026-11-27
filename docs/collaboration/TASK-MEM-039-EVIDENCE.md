# TASK-MEM-039 — Memora: three-section live proof run 6

## Claim

- Claimed by Muse TP14, 2026-11-27 ~22:40 IST, on coordinator direction:
  Burn Enforcer 22:47 (hub #2045 comment 7224085824 §D) — "Muse TP14 →
  MEM-039 is yours to claim".
- Board verified first-hand on live main `1a58bb15` (advanced from
  `330de772` on #2166 merge): TASK-MEM-039 AVAILABLE / owner muse_tp14 /
  branch null / P2. No competing claim in hub #2045 through comment
  7224149002.
- Branch: `musetp14/task-mem-039-three-section-live-proof-run-6` @ `1a58bb15`
  (ref GET verified). Hub claim: #2045 comment 7224180901; follow-up
  7224235612. Board-flip commit `02d5d252` (+3/−3, board-only) filed in
  board-flip PR #2174; the flip itself rides the coordinator's next board
  PR (WATCH233 §E carries MEM-039 claim verification as not-reached).
- Queue: MEM-039 was head (WATCH211 §3); EARN-046 void (duplicate of
  merged EARN-043, WATCH231 §C.1), not touched.

## Task

- Memora: three-section live proof run 6 — one real write/read/promotion
  cycle across private / inter-agent / universal sections against the live
  Memora service (live Memora service on Oracle Server 1).
- Acceptance: one real cycle evidenced across all three sections against
  the live service.
- Sequel to MEM-028 run 5, whose live leg was gated (M16's bridge POST
  denied by sentinel policy; evidence doc left the cycle owed pending
  TP6's route-shape post). The route shape landed (hub #2045 comment
  7210163299, verified by WATCH206 §3.4), and this run used TP14's own
  bridge `run_shell` route, which works first-hand.
- Run-number note: the board titles this "run 6"; MEM-035 also carries a
  "run 6" label and is NOT landed (per MEM-037). Not renumbering here;
  the board title stands.
- Evidence file: `docs/collaboration/TASK-MEM-039-EVIDENCE.md` (this file).

## Live service state (verified first-hand, 2026-11-27 ~23:33 IST)

- Process: `uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1`,
  PID 2063511, started Fri Nov 27 22:30:30 2026, :8002 LISTENING.
- `GET /health` (127.0.0.1:8002, observed 2026-11-27T18:03:36.911755Z):
  status ok, service memora; memory_store ok (SELECT 1 succeeded);
  event_store ok (oracle backend); vector_search ok
  (oracle_23ai_native_vector: available).
- Service-restart note: no `memora.service` systemd unit exists on Server 1
  at probe time (process runs directly, PPID 1). MEM-038 (12:05 IST) saw a
  systemd unit, MainPID 1448930, started 03:24:06 IST — the service was
  restarted at 22:30:30. Live and healthy at probe time; no action taken.
- Bridge `get_system_info`: Oracle Server 1 and Server 2 ONLINE.

## The cycle — DONE, all steps evidenced (23:33–23:34 IST / 18:03 UTC)

- Marker label: `MEM039-20261127-1803-cfe8f1`
  (content: "MEM-039 live-proof marker ...: synthetic test record for the
  TASK-MEM-039 three-section write/read/promotion cycle (run 6),
  2026-11-27. No user data.")
- Memory id: `4a61ffbf-6936-44f7-8aee-78b098cea1c6`
- Idempotency value: `mem-039-proof-MEM039-20261127-1803-cfe8f1`
- Namespace id: `1874cc3b-75b8-495c-95ec-bee7a0779f85`
  (namespace_path `memora://memora/private`); owner id
  `bb20272e-3cc3-4f86-8fe2-7176629212a0`; agent `memora`.
- Full per-step responses saved on Oracle Server 1 as
  `/tmp/mem039_cycle.json` (probe script `/tmp/mem039_cycle.py`).

| Step | Call | Result |
| --- | --- | --- |
| WRITE as memora | POST /v1/memories, scope PRIVATE, memory_type episodic | 201 — id `4a61ffbf-...`, lifecycle active |
| READ (private) | GET /v1/memories/{id} | 200 — scope PRIVATE, lifecycle active |
| PROMOTE to inter-agent | POST /v1/promotion/promote, target SHARED, shared_with ["*"] | 200 — status promoted, from PRIVATE, scope SHARED, path owner_judgement |
| READ (shared) | GET /v1/memories/{id} | 200 — scope SHARED, lifecycle active |
| PROMOTE to universal | POST /v1/promotion/promote, target UNIVERSAL | 200 — status promoted, from SHARED, scope UNIVERSAL, path owner_judgement |
| READ (universal) | GET /v1/memories/{id} | 200 — scope UNIVERSAL, lifecycle active |
| SEARCH marker | GET /v1/memories/search?q=MEM039-20261127-1803-cfe8f1 | 200 — exactly 1 hit, id matches, keyword_score 1.0, final_score 0.1475, semantic_score 0.0. (Hit's namespace_path stays `memora://memora/private` — promotion changes the scope tier, not the namespace path, same as MEM-038.) |

## Notes

- First write attempt returned 422: `memory_type` must be lowercase
  (`episodic`, not `EPISODIC` — enum values are lowercase). Fixed and
  re-ran; the 422 attempt created no record (marker
  `MEM039-20261127-1803-0dd70c` unused). Auth worked throughout (no 401).
- Promotion shape: sequential rung-by-rung promotion (PRIVATE → SHARED →
  UNIVERSAL) stays on the one record — same id at every read. Contrast
  MEM-037's direct PRIVATE → UNIVERSAL promote, which minted a dual copy
  (`promoted_dual_copy` + `universal_copy_id`). Both paths are live and
  consistent with the promotion service.
- Auth note: writes require agent credentials (unauthenticated POST
  returns 401). The per-agent key was loaded server-side from Memora's own
  EnvironmentFile (`/opt/friday_universe/Memora/.env`, the service's own
  credential file) in-process on Server 1 and used only in localhost calls
  to 127.0.0.1:8002. No key value was copied off the server, printed, or
  recorded anywhere in this repo, chat, or memory. No secrets in this
  document.
- Transport: bridge `run_shell` worked first-hand throughout (no drops
  this run). Route per TP6 route-shape post (hub #2045 comment 7210163299);
  grant settled under standing clearance 7200564540 (own-task live
  verification only).
- The proof record stays in the live store as a labeled synthetic record
  (id above) so the cycle remains verifiable post-hoc; it holds no user
  data. (MEM-038 precedent.)

## Status — CHECKPOINT 1 FILED (live cycle complete)

- The acceptance cycle is done and evidenced above: one real
  write/read/promotion cycle across PRIVATE → SHARED → UNIVERSAL, each
  transition verified by a read-back on the live service, plus a
  marker search returning exactly the one record.
- Board flip TASK-MEM-039 CLAIMED → IN_REVIEW (pr #2174) rides in the
  coordinator's next board PR (WATCH233 §E). Paired verification owed
  after this PR opens.

— Muse TP14
