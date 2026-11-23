# TASK-REL-084 — Harden the timing-dependent F3.4 circuit sentinel

Task: harden the timing-dependent F3.4 circuit sentinel behind the REL-080
test failure. Acceptance: the F3.4 circuit sentinel no longer flakes on
timing (made deterministic, or quarantined with a filed reason) and the
test job is green on the REL-080 branch — or the sentinel is proven
innocent with evidence.

- Assignment: coordinator queues (watch 7093557479 + push 7107020017:
  Muse 8 queue REL-083 → REL-084 → MEM-025); re-slotted to Muse 8 in
  watch 7110882697 as queue position 3 (STR-047).
- Claim: issue #1483 comment 7110751050. Branch `muse8/task-rel-084`.
- Claim PR: #1546 (board-only), MERGED 2026-11-24 00:51 IST (merge
  `0ea5accc`). CI on the claim head verified first-hand: 9/9 check runs,
  7 success, 2 skipped, 0 failed.
- Status: IMPLEMENTED — see §4 for the CI verdict on the work PR head.

## 1. Triage verdict: the sentinel is NOT innocent

REL-080's fix (work PR #1458, commit `c6fd6013`, merged `054d8045`)
renamed the e2e F3.4 peer from `sentinel_f3_4` to `sentinel_f3_4_e2e`
so the e2e test gets a fresh circuit. That made the test job green,
but it only dodged this one collision — it did not harden the
sentinel. The timing dependence is still live, verified first-hand
from the code on main `0ea5accc`:

- `Cortex/packages/integrations/src/cortex_integrations/peer_transport.py`
  keeps the circuit registry module-global: `_CIRCUITS: dict[str, Any] =
  {}` with no reset path. `get_circuit_for_peer(name)` creates
  `SubsystemCircuit(name=f"peer_{name}", failure_threshold=3,
  recovery_timeout_seconds=15.0)`.
- `SubsystemCircuit._can_half_open`
  (`Cortex/packages/core/src/cortex_core/resilience.py`) returns True
  only once `time.monotonic() - opened_at >= recovery_timeout_seconds`
  (15 s). Until then `before()` returns False and the transport
  fast-fails without entering the retry loop.
- The unit file's F3.4 (`Cortex/tests/unit/test_e2e_tier1.py`,
  peer `sentinel_f3_4`) drives 3 ConnectErrors → 3× `record_failure`
  → circuit `peer_sentinel_f3_4` OPEN, and leaves it OPEN: no
  cleanup, no reset. The e2e file runs in the SAME pytest process
  afterwards (the CI step runs both tier-1 files in one invocation),
  so any later test reusing that peer name fast-fails at
  `circuit.before()` whenever the inter-file gap is under 15 s —
  exactly the REL-080 run-4 failure (`assert len(delays) == 2` failed
  with `assert 0 == 2`; the mocked `asyncio.sleep` was never awaited).
- The same pattern exists for F3.5 (`intelx_f3_5` trips its circuit
  OPEN inside its own test and leaves it OPEN), and for any future
  test that reuses a peer name. The hazard is structural, not a
  one-off name collision.

So the REL-080 fix does NOT cover it, and no re-slot applies. The
hardening below removes the timing dependence at the shared-state
level instead of renaming around it.

## 2. What was changed (4 files, this PR)

1. `Cortex/packages/integrations/src/cortex_integrations/peer_transport.py`
   (+16 lines) — new `reset_peer_circuits()`: clears the module-global
   `_CIRCUITS` registry. Documented as a test-isolation hook.
   Production code never calls it; it only discards cached breakers,
   which are recreated lazily with the same thresholds on next use.
   No production behaviour changes: the 15 s recovery timeout, the
   failure threshold of 3, the retry/backoff path, and the fast-fail
   on OPEN are all untouched.
2. `Cortex/tests/conftest.py` (+18 lines) — new autouse fixture
   `reset_peer_circuits`: resets the registry before every test.
   This follows the existing autouse pattern in the same file
   (`clear_dependency_overrides`, `no_dev_auth_bypass`). Every F3
   test now starts from a fresh circuit regardless of run order,
   file order, or the wall-clock gap between files. The REL-080
   rename (`sentinel_f3_4_e2e`) stays as belt-and-braces separation.
3. `Cortex/tests/e2e/test_e2e_tier1.py` (+31 lines) — new regression
   test `test_f3_peer_transport_backoff_after_prior_open_circuit`
   (F3.4b): deliberately reuses the unit file's peer name
   `sentinel_f3_4`. Without the conftest reset it reproduces the
   REL-080 run-4 failure deterministically (fast-fail, 0 delays);
   with the reset it gets a fresh circuit and asserts the backoff
   path (`len(delays) == 2`, `delays[1] > delays[0]`).
4. `docs/collaboration/WORK_BOARD.yaml` — TASK-REL-084 record
   CLAIMED → IN_REVIEW, pr = work PR number (this PR).

No workflow change: the regression test lives in
`tests/e2e/test_e2e_tier1.py`, already collected by the CI tier-1
step, so the REL-068 collection guard (`scripts/ci_test_collection_audit.py`,
diff-scoped) has nothing new to check. No new test file is shipped.

## 3. What was checked without running code

- All three edited Python files re-read in full after editing and
  AST-parsed (syntax clean). The diffs were re-read against the
  true base blobs on main `0ea5accc` (`peer_transport.py`
  `e8c6d986`, `conftest.py` `2ecc2739`, `test_e2e_tier1.py`
  `27b319db`).
- No other test in the two tier-1 files depends on `_CIRCUITS` state
  persisting across tests: F3.1/F3.2/F3.3/F3.5 use fresh peer names
  per test and trip/assert within their own test body. The reset
  cannot change their outcomes.
- `FRIDAY/tests/e2e/test_tier1_features.py` also contains an "F3.4"
  test, but it is a different test (peer-call coroutine returns its
  result unchanged) that does not use `sentinel_f3_4` or the Cortex
  peer transport — no cross-suite collision, verified by grep.
- No local pytest was run: the execution-risk rule from the REL-080
  doc §5 stands (no clone, no pytest on repo content). The re-run
  route is CI on the work PR head (§4), same as REL-080.

## 4. CI re-run (approved route)

To be filled from the work PR run.

## Files

- `Cortex/packages/integrations/src/cortex_integrations/peer_transport.py` — `reset_peer_circuits()` hook.
- `Cortex/tests/conftest.py` — autouse `reset_peer_circuits` fixture.
- `Cortex/tests/e2e/test_e2e_tier1.py` — F3.4b regression test.
- `docs/collaboration/TASK-REL-084-F3-SENTINEL-HARDENING.md` — this file.
- `docs/collaboration/WORK_BOARD.yaml` — TASK-REL-084 record flipped CLAIMED → IN_REVIEW (pr = work PR number).
