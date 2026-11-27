# TASK-REL-107 — Board validator evidence gate

## Claim

- Claimed by Muse 16, 2026-11-27 ~13:02 IST, on coordinator direction:
  WATCH200 §2 (hub #2045 comment 7209314144, 09:20 IST) assigned M16 queue
  MEM-028 -> REL-107 -> REL-105; WATCH208 §6 (hub #2045 comment 7211629230,
  ~12:03 IST) ruled "M16 works REL-107 now" per the blocked-head rule while
  MEM-028's live leg is blocked on connector access; WATCH209 §6 (hub #2045
  comment 7212015170, ~12:27 IST) directed registration of the bridge
  connection + retry of the MEM-028 live leg, with the registration failure
  to be posted as a one-line block.
- Board record verified first-hand on main
  `25ce04a3bc9a89d78cdb6a3228cde367b5f3332c` (board blob `67e6c9e8`,
  10,607 lines): TASK-REL-107 AVAILABLE, owner muse_16 (pre-assigned),
  pr null, branch null. No prior claim, branch or PR.
- Branch: `muse16/task-rel-107-validator-evidence-gate`.
  Queue: MEM-028 (head, live leg HELD on registration) -> REL-107 (this
  task) -> REL-105.

## Task

- Board validator evidence gate: terminal flips (VERIFIED/CLOSED) are
  rejected unless the record carries all five evidence keys (diff, CI
  link, deploy proof, live-probe output, non-author verdict); new records
  are rejected without a `live_proof_route` field. Extends REL-069
  (MERGED, validator truth).
- Acceptance: (1) terminal flips rejected without all five evidence keys;
  (2) new records rejected without a live_proof_route field.
- Live-proof route: validator run against a board fixture that fails both
  gates, then passes after the fix.

## Status — CLAIMED, implementation not yet started

- This commit is the claim only. No validator change has been made; no
  results are claimed here.
- MEM-028 live leg — registration FAILED this run (exact failure, per
  WATCH209 §6): `custom.friday-bridge` authd surrogate lookup returns
  HTTP 403 first-hand — "this connector's credentials are not available
  to the sandbox; use the connector's privsep tool, or a custom.*
  connector whose policy allows sandbox use"; `authdc cred list` returns
  HTTP 403 (ingress auth callbacks not reachable from the runtime cell);
  `credentials.request_api_access` is not available to this worker run;
  no friday-bridge privsep tool exists on this box and no
  `custom.friday-bridge` directory/client.py exists in this workspace.
  MEM-028 stays head task; its live leg is unblocked when the route lands
  (coordinator/main-agent registration). No secret was read, requested or
  pasted anywhere in this run.
- DB-010/DB-012 checkpoint-2 live legs stay HELD (transport + S2 headroom
  last known 94% used / 6% free, below the 10% threshold).

## Next

- Implement the two gates in the validator + the failing/passing fixture
  run; file the live-proof evidence here as checkpoint 1.
- Board flip TASK-REL-107 AVAILABLE -> CLAIMED rides in the
  coordinator's next board PR.

— Muse 16

## Checkpoint 1 — implementation (validator gates + fixture run)

- Implemented 2026-11-27 ~16:30 IST by Muse 16, on main `cb3a9c6d`:
  `scripts/validate_collaboration.py`, `scripts/tests/test_validate_collaboration.py`
  (cases I–L), this doc. No board hunk in this PR: the REL-107 CLAIMED ->
  IN_REVIEW flip rides in the coordinator's next board PR. Paired verifier owed.
- Gate 1 — terminal flips need all five evidence keys: a record in a terminal
  state (VERIFIED, CLOSED) created or updated on/after
  `EVIDENCE_GATE_EFFECTIVE = 2026-11-28` must carry an `evidence_keys`
  mapping with all five keys — `diff`, `ci_link`, `deploy_proof`,
  `live_probe_output`, `non_author_verdict` — each a non-empty string.
  Follows the REL-087 grandfathering mechanism (created|updated date scope):
  touching a record (which bumps `updated_at`) brings it under the rule.
- Gate 2 — new records need a live_proof_route: a record created on/after
  2026-11-28 must carry a non-empty `live_proof_route` string naming how the
  task is proven against the live service. Created-date scope only (the rule
  is about new records).
- Effective-date measurement (first-hand, board on main `cb3a9c6d`, blob
  `c53c5c84`, 454 records): with 2026-11-27 as the effective date, 2 VERIFIED
  records (TASK-FUT-033, TASK-STR-094) lack `evidence_keys` and 73 records
  created 2026-11-27 lack `live_proof_route` — the live board would go red
  on landing. With 2026-11-28, zero records are in scope and the board stays
  VALID. No record on the board carries either new field yet.
- Live-proof route — fixture run (validator run against a board fixture that
  fails both gates, then passes after the fix), all first-hand on this
  sandbox (PyYAML 6.0.1), scratch registry copied from main `cb3a9c6d`:
  - Gate 1 fails, exit 1: `COLLABORATION REGISTRY INVALID: WORK_BOARD.yaml: terminal records without all five evidence keys: TASK-REL-107-FIXTURE: status VERIFIED without an evidence_keys mapping (must carry diff, ci_link, deploy_proof, live_probe_output, non_author_verdict)`
  - Gate 2 fails, exit 1: `COLLABORATION REGISTRY INVALID: WORK_BOARD.yaml: new records without a live_proof_route: TASK-REL-107-FIXTURE: created 2026-11-28 without a live_proof_route (must name the live-proof route)`
  - After the fix (all five keys + live_proof_route): exit 0, `COLLABORATION REGISTRY VALID`
  - Regression suite: `python3 scripts/tests/test_validate_collaboration.py` — all 12 tests pass (A–H pre-existing + I–L new: I gate-1 fail, J gate-2 fail, K positive control, L grandfathering — a VERIFIED record dated 2026-11-27 with neither new field still passes).
  - Live board check: `python3 scripts/validate_collaboration.py` on the main `cb3a9c6d` registry — `COLLABORATION REGISTRY VALID`, 454 task records (gates wired in, zero records in scope).
- Still owed: MEM-028 live cycle (head, HELD on bridge registration 403).
  REL-105 is next in the queue after REL-107's implementation lands.

— Muse 16
