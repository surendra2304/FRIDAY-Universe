# TASK-LAP-003 — Scope (checkpoint 0, stall repair)

- **Task:** TASK-LAP-003 — REPO-IMPLEMENT: laptop/phone repos, wave 2. P1.
- **Claim:** hub #1483 comment 7175149244 (~02:53 IST, 2026-11-26).
  Double-scope claim under the usage-truth directive order 2 (28% < 50%),
  alongside TASK-REL-099 checkpoint 2. Branch
  `muse12/task-lap-003-laptop-phone-wave2` from main `489a1b3b`, recreated
  at main `a0a45bdf` in the REL-099 checkpoint-2 run.
- **Stall repaired this run:** branch sat at the claim base with zero
  commits for ~4 h (claim ~02:53 IST, this doc ~07:1x IST; REL-099
  checkpoint 2 merged 05:52 IST and LAP-003 became the current task then,
  with no work started since). This scope doc is the first commit;
  scoping is verified first-hand below, not asserted.
- **Board (main `3941405a`, blob `c18b0dae`, 2,959,675 bytes, verified
  this run):** LAP-003 CLAIMED / owner muse_12 / branch
  `muse12/task-lap-003-laptop-phone-wave2` / pr null, updated
  2026-11-26T05:11:00+05:30. Queue: LAP-003 (head) → EARN-029
  (AVAILABLE / muse_12) → REL-100 (CLAIMED / muse_12, WATCH130 queue
  position 4; branch null — claim + branch when reached) → FRG-029
  (AVAILABLE / muse_12).

## Sources verified first-hand this run

- Registry `IntelX/intelx/registries/scouted_repos.json`, blob
  `a18c2403451881ba89209b439b0126765d160c1f`, 177,539 B, 102 entries —
  LAP-003's four entries read in full (`aura-android-use.md`,
  `artemis.md`, `scrcpy.md`, `browser-use.md`).
- Upstream API reads (2026-11-26 ~07:1x IST) — see §Upstream.
- Board record read in full on main `3941405a` (acceptance quoted in
  §Legs).
- `docs/PHONE_UI_AUTOMATION.md` (blob `88a3eb45`, 4,505 B) and
  `docs/BROWSER_TASK.md` (blob `77e54d31`, 2,961 B) read in full.
- INT-044 production tracker rows 13–16
  (`docs/collaboration/TASK-INT-044-PRODUCTION-TRACKER.md`, 41,689 B).

## Finding 1 — All four repos already repo-side implemented (pattern / adopt)

The INT-044 tracker already records all four as REPO-SIDE IMPLEMENTED
(main `a0a9f1ba`); LAP-003's repo-side work is verification + CI proof,
not new implementation. Pieces on main `3941405a`:

| Repo / leg | Piece | File (blob SHA on main `3941405a`) | Size |
|---|---|---|---|
| AURA + ARTEMIS (adapt, pattern) | ADB UI executor | `FRIDAY/scripts/phone_ui_agent_adb.py` (`113ddb55`) | 25,983 B |
| AURA + ARTEMIS (adapt, pattern) | Planner loop | `FRIDAY/src/friday/remote/phone_ui_agent.py` (`20dff365`) | 20,582 B |
| AURA + ARTEMIS (adapt, pattern) | Phone bridge | `FRIDAY/src/friday/remote/phone_bridge.py` (`d527ca8f`) | 30,602 B |
| AURA + ARTEMIS (adapt, pattern) | Tools | `FRIDAY/src/friday/tools/builtin/phone_ui_control.py` (`16a70169`) | 7,948 B |
| AURA + ARTEMIS (adapt, pattern) | Tests | `FRIDAY/tests/test_phone_ui_automation.py` (`3a5a95d6`) | 16,012 B |
| AURA + ARTEMIS (adapt, pattern) | Doc | `docs/PHONE_UI_AUTOMATION.md` (`88a3eb45`) | 4,505 B |
| scrcpy (adopt, transport) | Mirror option | `--mirror` in `phone_ui_agent_adb.py` (external tool, not vendored) | — |
| scrcpy (adopt, transport) | Escrcpy adapt (GUI over the transport) | `FRIDAY/src/friday/remote/escrcpy_integration.py`, `FRIDAY/src/friday/tools/builtin/escrcpy_control.py` — LAP-004, checkpoint 1 merged via PR #1918 | — |
| Browser Use (adapt, pattern) | Laptop browser planner | `FRIDAY/src/friday/remote/laptop_browser_agent.py` (`32278b7c`) | 18,772 B |
| Browser Use (adapt, pattern) | Tool | `FRIDAY/src/friday/tools/builtin/laptop_browser_control.py` (`178c3514`) | 4,300 B |
| Browser Use (adapt, pattern) | Executor + safety | `FRIDAY/src/friday/integrations/browser_use/executor.py` (`6d551403`), `safety.py` (`9c60868e`) | 9,518 / 4,162 B |
| Browser Use (adapt, pattern) | Tool | `FRIDAY/src/friday/tools/builtin/browser_tool.py` (`89a303c1`) | 3,043 B |
| Browser Use (adapt, pattern) | Tests | `FRIDAY/tests/test_browser_use_integration.py` (`f026988e`), `FRIDAY/tests/test_laptop_browser_agent.py` (`1ec10f64`) | 2,997 / 6,959 B |
| Browser Use (adapt, pattern) | Doc | `docs/BROWSER_TASK.md` (`77e54d31`) | 2,961 B |

Read first-hand this run (docstrings + import blocks + test heads):
the phone planner is the ARTEMIS observe-hierarchy-then-act pattern
rebuilt stdlib + `adb` (ARTEMIS needs Python 3.12, fleet is 3.10);
AURA is pattern-only — no AGPL code is used, its banking/payment hard
block informed the planner's package gate; scrcpy is adopted as the
optional owner-side mirror (`--mirror`), an external tool, not vendored;
the browser-use library is NOT vendored (MIT, but Python 3.11+ vs the
fleet's 3.10) — the pattern is implemented in the laptop browser agent
and the `browser_use` executor treats the package as optional
(`has_browser_use_package` is a bool flag; Playwright likewise
optional). No code copied from any of the four upstreams.

**Gap (REL-001 pattern, same as LAP-004): three tests are NOT wired
into CI.** Code search for each filename finds it only in docs / the
INT-044 tracker — zero hits in `.github/workflows/`:

- `FRIDAY/tests/test_phone_ui_automation.py` — IG-LAP-01, hardware-free
  (fake adb runner, fake bridge, scripted decider).
- `FRIDAY/tests/test_browser_use_integration.py` — safety guard + executor
  availability, hardware-free.
- `FRIDAY/tests/test_laptop_browser_agent.py` — IG-LAP-04, hardware-free
  (injected execute callable, scripted decider + OCR).

Import check this run: all three import stdlib + pytest + `friday.*`
only (`friday.remote.*`, `friday.core.*`, `friday.planning.*`,
`friday.tools.*`, `friday.security.authorization` = stdlib + pydantic,
which the tier-1 venv installs). Same import family as the tests
already in the FRIDAY tier-1 invocation. CI proof is the PR's own run
— no green claimed at filing (LAP-004 precedent).

Not wired this checkpoint: `FRIDAY/tests/test_external_agent_orchestration.py`
(also cited by tracker row 16) — it imports
`friday.integrations.mini_swe.executor` and the planner orchestrator /
router, a heavier surface than the three above; see Q2.

## Upstream re-verified first-hand (2026-11-26 ~07:1x IST)

| Repo | Pushed | Licence (API) | Latest release | Notes |
|---|---|---|---|---|
| `Dinesh210805/aura-android-use` | 2026-11-25T09:09:02Z | AGPL-3.0 | **v1.0.712**, 2026-11-25T08:27:45Z | Active (pushed yesterday); 28 stars, 8 forks; solo-built, self-described unstable — registry caution stands |
| `google/artemis` | 2026-10-01T21:37:15Z | Apache-2.0 | **none** — `releases/latest` returns HTTP 404 | 18,082 stars, 2,011 forks; main-branch only, no release to pin |
| `Genymobile/scrcpy` | 2026-11-24T20:51:39Z | Apache-2.0 | **v5.0.1**, 2026-10-08T06:44:27Z | 155,734 stars; v5.0.1 is a hardware-decoding patch release |
| `browser-use/browser-use` | 2026-11-26T00:03:09Z | MIT | **1.0.8**, 2026-11-22T03:30:41Z | 122,079 stars; v1.0 rewrite Nov 2026; README warns to pin the version exactly |

**Pin decisions (checkpoint 1):** scrcpy **v5.0.1** (the transport binary
the owner installs laptop-side); browser-use **1.0.8** (the library
version for any laptop-side install; do not follow past 1.x without a
fresh check). AURA v1.0.712 is recorded, not pinned into code — AURA is
pattern-only, no AGPL code is used. ARTEMIS has no release to pin.
No conflict with LAP-004's escrcpy v3.3.1 pin: that is the Electron GUI
(`viarotel-org/escrcpy`), a different product from the `Genymobile/scrcpy`
transport binary.

## Live legs BLOCKED (not done)

Acceptance: "real device task executed via the bridge on the real
laptop/phone path + disconnect/reconnect failure case" and, for
adopt/adapt entries, "the adapted component must run in the target
agent's live production path, proven by one real end-to-end use filed
as evidence incl. a failure case". Blocked: owner stop order in force
(WATCH130, no lift), fleet CD broken, S2 disk ~86–91% (REL-100, now
Muse 12 queue position 4). No live probe run, nothing live claimed.
Live legs owed when clearance lands, or the coordinator rules them
follow-up work (STR-047 precedent). The owner's phone is not yet
connected (`docs/PHONE_UI_AUTOMATION.md` verification status).

## Legs

- **Leg 1 (repo-side, doable now):** upstream re-verification + pins
  (this doc) + wire the three uncollected tests into the FRIDAY tier-1
  CI invocation + evidence doc (checkpoint 1).
- **Leg 2 (repo-side now, live later):** reference-only half is
  already covered — AURA/ARTEMIS are pattern references with no
  upstream code in any production path (guardrail proof: the two repos
  appear only in the registry, the tracker, and the two docs).
- **Leg 3 (gated):** live end-to-end (real device task via the bridge
  on the real laptop/phone path) + disconnect/reconnect failure case.

## Open questions

- **Q1:** LAP-003's adapt legs vs IG-LAP-01 / IG-LAP-04 — the adapts
  already exist; is LAP-003's completion the live proof + CI wiring,
  or does the coordinator want new implementation? Lean: completion =
  live proof + CI wiring + evidence doc; no re-implementation of the
  adapts.
- **Q2:** `test_external_agent_orchestration.py` — wire into tier-1 in
  a follow-up checkpoint, or leave to its own task? It imports the
  planner orchestrator/router and the mini-SWE executor; collection
  risk is higher than the three wired here.
- **Q3:** scrcpy v5.0.1 vs the fleet's installed scrcpy — the pin
  constrains the owner-side laptop install; is there a standing check
  that the laptop's installed version matches the pin?

## Out of scope / no-go

- No copying `Dinesh210805/aura-android-use` code (AGPL-3.0).
  Pattern only.
- No browser-use paid cloud (FREE-only). No live runs without
  clearance. No repo-code execution on this VM (execution-risk check)
  — CI is the live proof for code. No checkpoint PRs — the board flip
  rides in the work PR.

— Muse 12, 2026-11-26 ~07:2x IST
