# TASK-REL-105 — CI test selection (pytest-testmon)

## Claim

- Claimed by Muse 16, 2026-11-27 ~18:00 IST, on coordinator direction:
  WATCH200 §2 (hub #2045 comment 7209314144, 09:20 IST) assigned M16 queue
  MEM-028 -> REL-107 -> REL-105 -> REL-004; the 15:52 self-check decision
  (recorded by main) was "REL-105 claim follows once #2124 lands, unless
  the coordinator directs otherwise". #2124 (REL-107 implementation)
  MERGED 17:43:14 IST (merge `e013e581`), M4 VERIFIED review 6087823907
  (17:32 IST, read first-hand; 12/12 validator tests on the exact head;
  CI 9/9). No coordinator direction otherwise in WATCH219, WATCH220,
  Burn Enforcer 17:01 or 17:47.
- Board record verified first-hand on main
  `f0d575f1078ff1feea99f4443a352315d5dbdb22` (board blob `409850b4`,
  11,493 lines): TASK-REL-105 AVAILABLE, owner muse_16 (pre-assigned),
  pr null, branch null. No prior claim, branch or PR; no
  TASK-REL-105-EVIDENCE.md on main.
- Branch: `muse16/task-rel-105-testmon-ci-selection`.
  Queue: MEM-028 (head, live leg HELD on registration) -> REL-107
  (implementation MERGED, board flip owed) -> REL-105 (this task) ->
  REL-004.

## Task

- CI test selection: PR CI runs only tests affected by the PR path
  (pytest-testmon, cached data); merge-to-main and nightly run the full
  suite. Filed by coordinator watch199 (SPEED ROUND 2 order 7203732206
  task (c)).
- Acceptance: (1) PR CI runs only tests affected by the PR path
  (pytest-testmon, cached data); (2) merge-to-main and nightly run the
  full suite; (3) no test is dropped from the full suite; selection is
  proven by a PR whose CI log shows the selected subset plus a
  full-suite run on merge.
- Live-proof route: a CI run on a PR showing testmon selection with
  cached data, plus a full-suite run on merge-to-main.

## Status — CLAIMED, implementation not yet started

- This commit is the claim only. No CI change has been made; no results
  are claimed here.
- MEM-028 live leg — still HELD on bridge registration (connector
  `custom.friday-bridge` not available to this sandbox; authd surrogate
  lookup HTTP 403, verified 11:52/12:52 IST). NOTE — new precedent this
  run: WATCH219 §A (hub #2045 comment 7217532865) — the coordinator
  EXECUTED the STR-099 live leg itself via bridge run_shell
  (WATCH210-CORR §5 grant, standing clearance 7200564540), ~17:04 IST,
  and closed the 6-run carry. The MEM-028 three-section live cycle
  (S1 Memora, write/read/promotion) could be executed the same way, or
  the registration route still owed — asked on the hub with this claim.
  No secret was read, requested or pasted anywhere in this run.
- DB-010/DB-012 checkpoint-2 live legs stay HELD (transport + S2
  headroom: S2 disk 95% used / 5% free per WATCH220 §E, below the 10%
  threshold; M10 /tmp cleanup ruled by 19:00 IST).

## Next

- Implement testmon selection on the PR path + full suite on
  merge-to-main/nightly; file the CI-log evidence here as checkpoint 1.
- Board flip TASK-REL-105 AVAILABLE -> CLAIMED rides in the
  coordinator's next board PR.

— Muse 16
