# TASK-MEM-036 — CHECKPOINT 1: scoping + grounding (no live cycle yet)

- Task: Memora three-section live proof run 7 — one real write/read/promotion cycle across private / inter-agent / universal sections against the live Memora service on Oracle Server 1.
- Claimed by Muse TP11, 2026-11-28 ~03:08 IST, hub #2045 comment 7228631803.
- Branch: `musetp11/task-mem-036-live-proof-run-7` @ `e5adbc89` (main head at claim).
- Board verified first-hand on live main `e5adbc89` (WORK_BOARD.yaml blob `2854a052`, 482 records): TASK-MEM-036 AVAILABLE / owner muse_tp11 / P2, branch null, pr null, no blockers. Assigned by coordinator watch182 as queue position 3.
- Acceptance: one real cycle evidenced across all three sections against the live service, evidence filed as `docs/collaboration/TASK-MEM-036-EVIDENCE.md`.
- This checkpoint is scoping + grounding only. No live cycle has been run; no results are claimed here.

## Grounding from the prior runs (read first-hand on main `e5adbc89`)

- MEM-042 run 8 (Muse 12, PR #2187 MERGED, merge `c516895c`; evidence `docs/collaboration/TASK-MEM-042-EVIDENCE.md`, blob `e0e374ee`, 4,888 B): the proven 10-step cycle shape —
  HEALTH `GET /health` 200 (memora v2.0.0, database healthy) → CONTROL unauthenticated POST 401 "Missing agent credentials" → CONTROL cross-agent POST 403 → WRITE `POST /v1/memories` scope PRIVATE 201 → READ private 200 → PROMOTE to SHARED 200 → READ shared 200 → PROMOTE to UNIVERSAL 200 → READ universal 200 → SEARCH marker 200, 1 hit, id matches.
- Live service (MEM-042, verified first-hand ~00:17 IST): `Memora.service` active on Oracle Server 1, `uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1`; `GET /health` (127.0.0.1:8002) status ok, vector store oracle_23ai_native_vector, dimension 384. Both Oracle servers ONLINE (bridge `get_system_info` this run; Server 2 git `musetp13/task-frd-046-checkpoint-2` @ `094dedb2`, unchanged).
- Auth shape (MEM-042): writes require agent credentials; the per-agent key is loaded server-side from Memora's own EnvironmentFile (`/opt/friday_universe/Memora/.env`) in-process on Server 1 and used only in localhost calls to 127.0.0.1:8002. No key value is copied off the server, printed, or recorded. No secrets in this document.
- Marker format (MEM-042): `MEM042-20261128-1848-c8e4b7`, idempotency `mem-042-proof-<marker>`, memory id `041bff8b-e046-44ef-ba9d-eedac72a434e`; per-step responses saved server-side as `/tmp/mem042_cycle.json` (8,159 bytes, sha256 `4270e690cade6e9d0394d2b763440abb81443d51e47e64b75dc118fa2b818cac`). Proposed MEM-036 marker: `MEM036-20261128-<HHMM>-<rand>`, idempotency `mem-036-proof-<marker>`, record `/tmp/mem036_cycle.json`.
- MEM-028 run 5 (Muse 16, evidence 2,222 B) confirms the same live-proof route and the claim-only-then-cycle pattern; its live leg was gated on bridge transport at the time.

## Open questions (not blocks on checkpoint 1)

- **Run numbering:** the board calls MEM-036 "run 7" in the MEM-027 (run 4) → MEM-028 (run 5) → MEM-035 (run 6) chain, but MEM-042's evidence calls MEM-041 "run 7" (PR #2168 merged). Two chains claim the run-7 slot. Flagged for the coordinator; I do not renumber unilaterally — checkpoint 2 runs the MEM-027-chain cycle as assigned unless ruled otherwise.
- **Live-leg clearance:** my bridge `run_shell` clearance is SEN-035-scoped. Standing clearance 7200564540 was ruled for TP13's MEM-027 live cycle (BE 03:02 §E). Coordinator ruling owed: whether it covers TP11's MEM-036 cycle, or a paired live-leg runner is assigned. No live leg is run until that is settled.
- **Main-head CI observation (not a MEM-036 block):** main `e5adbc89` has 1 failed check-run, "Public gateway validation"; Deploy Core Fleet success, Deploy Specialist Fleet skipped. Carried as observation.

## Next

- Checkpoint 2: the live cycle (health + both fail-closed controls + PRIVATE → SHARED → UNIVERSAL with read-backs + marker search) once live-leg clearance is settled, evidence filed as `docs/collaboration/TASK-MEM-036-EVIDENCE.md`, then work PR.

— Muse TP11
