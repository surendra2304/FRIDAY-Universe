# TASK-REL-004 — Reliability: health-endpoint honesty

## Claim

- Claimed by Muse 16, 2026-11-28 ~02:52 IST, hub #2045 comment
  7228479791 (02:58:44 IST), answering Burn Enforcer 02:38 §C (hub #2045
  comment 7228172325): "Muse 16 — post state + claim next. #2193 merged
  02:17; INT-881 done."
- Trigger: INT-881 COMPLETE — armed-state evidence PR #2193 VERIFIED by
  Muse 18 (review 6093185667, 02:14:21 IST, ~46 min early of the ~03:00
  due, WATCH238 §D) and MERGED `99cbcbf7` at 02:17:30 IST by Surendra.
  CI 9/9 on head `8c895a4a` (7 success + 2 skipped, 0 fail).
- Board record verified first-hand on main
  `e5adbc8920846f7abc90bd6d3a158d9965ee57e4` (board blob `2854a052`,
  11,984 lines) at claim time: TASK-REL-004 AVAILABLE, owner muse_16
  (pre-assigned), pr null, branch null, priority P2, blockers []. No
  prior claim, branch or PR; no TASK-REL-004-EVIDENCE.md on main.
- Branch: `muse16/task-rel-004-health-endpoint-honesty` @ `e5adbc89`
  (created + verified via GitHub Data API ref-create + ref-verify, both
  return `e5adbc8920846f7abc90bd6d3a158d9965ee57e4`).
- Board flip AVAILABLE -> CLAIMED already landed via the coordinator's
  WATCH244 board PR — verified first-hand on main `7238520d6354`
  (board blob `35b6b1ef`, 12,153 lines, record updated
  2026-11-28T03:39:03+05:30; evidence note "watch244: claimed by Muse
  16 (hub 7228479791); branch verified via ls-remote").
- Queue at claim: REL-004 (head) -> REL-105 IN_REVIEW / pr 2138 (claim
  only, held). Update this run: REL-105's claim PR #2138 MERGED
  2026-11-27 19:07:13 IST (merge `7ae846b9`, verified first-hand from
  the PR object); Muse 2 VERIFIED review 6088713036 (~18:45 IST, due
  ~19:00, WATCH221 §B); CI 9/9 on head `a9636efa`; diff 1 file
  `docs/collaboration/TASK-REL-105-EVIDENCE.md` +63/-0. Board flipped
  to MERGED 2026-11-28T03:39:03+05:30 (verified first-hand on main
  `7238520d`). REL-004 is now the only live M16 head; no next task
  assigned yet — the coordinator assigns from the pool (10 AVAILABLE
  owner-null at the floor per WATCH243/BE 03:42).

## Task

- Reliability: health-endpoint honesty — agents report capability
  state, not just process liveness (MASTER_PLAN M5). Filed by Muse
  (coordinator) watch210 (2026-11-27, hub #2045): design task; health
  is liveness-only per the 2026-11-14 snapshot.
- Acceptance: (1) fleet-wide capability contract defined (each agent
  health reports its real capability state, e.g. Stratex
  engine/engine_healthy) and implemented on at least three agents;
  (2) live probe through the gateway shows a degraded agent presenting
  as degraded, not simply ok; evidence filed as
  `docs/collaboration/TASK-REL-004-EVIDENCE.md`.
- Live-proof route: public gateway health endpoints on the live fleet.

## Status — CLAIMED, implementation not yet started

- This commit is the claim only. No contract has been defined, no
  implementation has been made, no results are claimed here.
- Five states: implemented NO / tested NO / merged NO / deployed N/A /
  production-verified NO.
- Live leg is coordinator-gated: bridge connector
  `custom.friday-bridge` is unavailable to this sandbox (authd surrogate
  lookup HTTP 403, verified 11:52/12:52 IST 2026-11-27; carried, not
  re-run), so no live probe is possible from here. S2 copy status per
  BE 03:42 §E (from TP6 post 7228881818, read first-hand): FRIDAY
  :10000 000, Inference :8001 000; S2 disk 85% / 7.4G free. Server moves
  stay frozen — the coordinator's call, not a worker task. The repo-side
  leg (contract definition + implementation on >=3 agents) proceeds from
  the repo checkout; the live probe waits on the gateway route.
- No secret was read, requested or pasted anywhere in this run.

## Next

- Define the fleet-wide capability contract; implement it on at least
  three agents; live-probe via the public gateway health endpoints;
  file the evidence here as checkpoints.
- Paired verifier owed on this claim PR (coordinator names).

— Muse 16
