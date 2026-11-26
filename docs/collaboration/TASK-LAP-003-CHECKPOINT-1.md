# TASK-LAP-003 — Checkpoint 1: upstream re-verified + three tests wired into CI

**Task:** TASK-LAP-003 (REPO-IMPLEMENT, laptop/phone repos wave 2:
AURA / aura-android-use adapt, ARTEMIS adapt, scrcpy adopt, Browser Use
adapt).
**Branch:** `muse12/task-lap-003-laptop-phone-wave2` — recreated at main
`3941405a` this checkpoint.
**Date:** 2026-11-26 ~07:1x IST. **Status:** repo leg done; live legs
BLOCKED (owner stop order, fleet CD broken).

## 1. Upstream re-verified first-hand (2026-11-26 ~07:1x IST)

| Fact | Evidence |
|---|---|
| AURA latest **v1.0.712**, published 2026-11-25T08:27:45Z | `api.github.com/repos/Dinesh210805/aura-android-use/releases/latest` → `tag_name: v1.0.712` |
| AURA licence **AGPL-3.0**, pushed 2026-11-25T09:09:02Z | `GET /repos/Dinesh210805/aura-android-use` → `license.spdx_id: AGPL-3.0` |
| ARTEMIS licence **Apache-2.0**, pushed 2026-10-01T21:37:15Z | `GET /repos/google/artemis` → `license.spdx_id: Apache-2.0`; 18,082 stars |
| ARTEMIS has **no releases** | `releases/latest` returns HTTP 404 — main-branch only, nothing to pin |
| scrcpy latest **v5.0.1**, published 2026-10-08T06:44:27Z | `api.github.com/repos/Genymobile/scrcpy/releases/latest` → `tag_name: v5.0.1` (hardware-decoding patch release) |
| scrcpy licence **Apache-2.0**, pushed 2026-11-24T20:51:39Z | `GET /repos/Genymobile/scrcpy` → `license.spdx_id: Apache-2.0`; 155,734 stars |
| browser-use latest **1.0.8**, published 2026-11-22T03:30:41Z | `api.github.com/repos/browser-use/browser-use/releases/latest` → `tag_name: 1.0.8` |
| browser-use licence **MIT**, pushed 2026-11-26T00:03:09Z | `GET /repos/browser-use/browser-use` → `license.spdx_id: MIT`; 122,079 stars |

**Pin decisions (answers scope-doc Q3 in part): pin scrcpy v5.0.1 and
browser-use 1.0.8.** Both pins constrain only which released binary /
library the owner installs laptop-side — no FRIDAY code vendors either
upstream, so the pins live in the docs, not in `requirements.txt`.
Recorded in `docs/PHONE_UI_AUTOMATION.md` ("Release pin" note, this
PR) and `docs/BROWSER_TASK.md` ("Release pin" note, this PR). Do not
follow browser-use past 1.x without a fresh check: the v1.0 rewrite
shipped Nov 2026 and the README warns to pin the version exactly.
AURA v1.0.712 is recorded, not pinned — pattern-only, no AGPL code
used. No conflict with LAP-004's escrcpy v3.3.1 pin (different product:
Electron GUI vs transport binary).

## 2. Repo-side pieces re-verified on main `3941405a`

All four registry entries already repo-side implemented (INT-044
tracker rows 13–16, main `a0a9f1ba`); this checkpoint verifies, it does
not re-implement. Blob SHAs confirmed against the contents API:

- Phone planner (ARTEMIS pattern): `FRIDAY/src/friday/remote/phone_ui_agent.py`
  (20,582 B), `FRIDAY/scripts/phone_ui_agent_adb.py` (25,983 B),
  `FRIDAY/src/friday/remote/phone_bridge.py` (30,602 B),
  `FRIDAY/src/friday/tools/builtin/phone_ui_control.py` (7,948 B).
- Browser-use pattern: `FRIDAY/src/friday/remote/laptop_browser_agent.py`
  (18,772 B), `FRIDAY/src/friday/tools/builtin/laptop_browser_control.py`
  (4,300 B), `FRIDAY/src/friday/integrations/browser_use/executor.py`
  (9,518 B), `FRIDAY/src/friday/integrations/browser_use/safety.py`
  (4,162 B), `FRIDAY/src/friday/tools/builtin/browser_tool.py` (3,043 B),
  `FRIDAY/src/friday/integrations/nextgen/browser_use.py` (1,315 B).
- Docs: `docs/PHONE_UI_AUTOMATION.md` (4,505 B),
  `docs/BROWSER_TASK.md` (2,961 B).

**Q1 answered in part:** no new implementation is needed repo-side —
the adapts already exist and match the current upstream releases
(ARTEMIS main-branch, AURA v1.0.712 pattern, scrcpy v5.0.1 transport,
browser-use 1.0.8 pattern). Completion of the repo leg = this CI wiring
+ the live proof (real end-to-end + failure case), which stays gated on
clearance.

## 3. CI wiring (this PR)

`.github/workflows/friday-universe-ci.yml`, step "Run FRIDAY tier-1
tests" (`working-directory: FRIDAY`): `tests/test_phone_ui_automation.py`,
`tests/test_browser_use_integration.py` and
`tests/test_laptop_browser_agent.py` added to the pytest invocation
alongside `tests/test_reliability.py` and
`tests/test_ig2_lap01_escrcpy.py`, with a `# TASK-LAP-003` comment
following the established pattern (LAP-004, FRD-044,
IG-FRD-006-FIX-01). All three were uncollected since IG-LAP-01 /
IG-LAP-04 landed (zero workflow hits before this change). Import check
this run: stdlib + pytest + `friday.*` only, the same family as the
other tier-1 tests; the REL-068 test-collection guard now sees all
three files collected by a PR-triggered workflow. **CI proof is the
PR's own run — no green claimed at filing; the run is pending.**

Not wired: `FRIDAY/tests/test_external_agent_orchestration.py` (also
cited by tracker row 16) — heavier imports (planner orchestrator /
router, mini-SWE executor); scope-doc Q2, follow-up decision owed.

## 4. What is still owed

- **Live legs BLOCKED, not done:** real device task via the bridge on
  the real laptop/phone path + disconnect/reconnect failure case;
  owner stop order in force (WATCH130), fleet CD broken, S2 disk
  ~86–91% (REL-100, Muse 12 queue position 4). Awaiting clearance or
  a coordinator ruling (STR-047 precedent). The owner's phone is not
  yet connected.
- **Board flip** rides in this PR: TASK-LAP-003 CLAIMED → IN_REVIEW,
  branch `muse12/task-lap-003-laptop-phone-wave2`, pr = this PR (second
  commit, once this PR number exists).
- **Open, not mine:** EARN-029 board flip (AVAILABLE / muse_12, next
  in queue) and the REL-100 branch (null — claim + branch when
  reached) are coordinator / next-run items, not this PR.

— Muse 12
