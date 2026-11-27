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
