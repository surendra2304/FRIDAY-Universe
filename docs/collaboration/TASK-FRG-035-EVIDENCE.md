# TASK-FRG-035 — Evidence: checkpoint 1 — blocker sweep + tool identified

- Task: TASK-FRG-035 — Forge: ship the tool the highest-priority stuck task is blocked on (or next self-upgrade slice).
- Worker: Muse 18. Branch: `muse18/task-frg-035-forge-blocker-tool`.
- Filed: 2026-11-28 ~07:15 IST. Board verified first-hand on live main `55a11a60` (blob `46dd5277`, 12,469 lines).
- Claim: hub #2045 comment 7231281505 (~06:24 IST). This checkpoint is identification + plan only; no code yet.

## §1 — Blocker sweep (board + hub, first-hand)

Board BLOCKED tasks on live main `55a11a60` (10): WF-007, WF-008, WF-009, MEM-017, INT-023, EARN-005, VYR-052, FRD-048, VYR-081, DB-001. Each record read in full. None is blocked on a shippable Forge tool:

| Blocked task | Blocker | Why not a Forge tool |
|---|---|---|
| FRD-048 (TP3) | Owner gate: Fish Audio route decision before Nov 30 | Owner decision, not a tool |
| MEM-017 (TP3) | Owner gate: Halo key paste (7200182638) | Owner step, not a tool |
| INT-023 (M9, PR #1680) | INT-032 soak timer never installed; IntelX has no running home | Fleet ops install, not a Forge tool; PR #1680 is M9's |
| VYR-052 (TP5) | Machine-QA gate unachievable (VYR-056 CLOSED: yt-dlp n-challenge) | Closed as unachievable; no tool fixes it |
| VYR-081 (M9) | No permitted GTA 6 footage; no live EARN-024 brief | Footage/brief, not a tool |
| DB-001 (M6) | MySQL HeatWave production-usage verification | Owned by M6; database work, not Forge |
| EARN-005 | Owner answer owed: $19 product identity | Owner answer; inventing a product is not the work |
| WF-007/008/009 | CSV converter acceptance (old lane) | Owner-gated, not Forge |

Hub carried items checked (WATCH249 hub 7231716845 + BE 07:05 hub 7231776459, read in full):
- TP4 FRG-036 Leg B re-run owed after sandbox-deps fix + Forge restart — see §2.
- VOI-031 gated on FRD-064 deploy (TP1's task; fix ruling still owed) — not a Forge tool.
- M3 STR-107 proposal — assigned to Muse 13 in WATCH249 §B (owned now).
- TP7 (b)/(d)/(e) + live Forge host naming — ruling asks, not a tool-block.
- M15/TP2 rulings — ruling asks, not a tool-block.

**Sweep verdict: no agent is currently blocked on an unowned Forge tool — except one, §2.**

## §2 — The tool: Forge sandbox test-dependency provisioning

**Blocked task:** TASK-FRG-036 (P1, IN_REVIEW, owner Muse TP4, PR #2220 MERGED `d4dcbf7a`). Leg B ran end-to-end through the new `/v1/task/execute` route but Forge's verdict was FAILED — for an environment reason, not a build reason. Evidence: `docs/collaboration/TASK-FRG-036-EVIDENCE.md` §4 (TP4, filed ~04:35 IST, read first-hand this run):

> `ImportError while loading conftest '.../Cortex/tests/conftest.py'. ModuleNotFoundError: No module named 'aiosqlite'` — the battery collects the repo's test suite inside the sandbox, and the sandbox lacks the `aiosqlite` module.

TP4's evidence §9.2 routes the fix explicitly: "Forge sandbox dependencies (`aiosqlite` missing) + Forge HTTP wedging + Forge→Memora 401s are service-side defects for the coordinator/owner to route (**not TP4's task to fix unasked**)." TP4 owns only the Leg B re-run; the sandbox-deps fix itself is unowned. The board record agrees: "re-run owed after sandbox-deps fix + Forge restart (TP4 owns, WATCH246 section C)".

**Grounding in Forge code (read first-hand on main `55a11a60`):**
- `Forge/app/verification/engine.py` (591 lines, sha `6950f0b39771`) — the verification engine runs the battery including `TestChecker`, which collects the repo's test suite inside the task sandbox.
- `Forge/app/execution/dependency_manager.py` (427 lines, sha `7128d143935b`) — AST import extraction + PyPI name resolution already exists; it generates requirements but nothing installs them into the sandbox before the battery runs.
- `aiosqlite` is a declared repo dependency (`requirements-ci.txt`; 140 code-search hits) — the sandbox simply never provisions it.
- Sandbox security review (`docs/security/FORGE_SANDBOX_REVIEW_2026-11-10.md`, board line 663): finding F-2 — "dependency installs inherently execute setup code — acceptable with allow_network=False default". The fix must respect that: no open network installs inside the sandbox.

**The tool:** a pre-battery provisioning step in the Forge verification path — before `TestChecker` collects the suite, install the cloned project's declared test dependencies (starting with `aiosqlite` from the repo's own `requirements-ci.txt`) into the sandbox environment, fail-closed when the declared list is missing or an install fails. Verification then fails only on real test failures, never on missing environment deps. This unblocks TP4's FRG-036 Leg B re-run directly.

**Not my slice (stated so Muse 11's FRG-038 stays distinct):** the Forge HTTP wedging (single worker blocked by long sync `execute_now`) and the Forge→Memora 401s are recorded follow-ups, not this task. M11's FRG-038 must pick a different slice.

## §3 — Plan (checkpoint 2: code + tests; checkpoint 3: live proof)

1. Implement the provisioning step: hook into the verification engine before `TestChecker`; resolve the dep list from the cloned project's declared requirements (`requirements-ci.txt` at the repo root, falling back to `dependency_manager` AST extraction); install into the sandbox venv with the sandbox network policy honoured (offline wheelhouse / pinned allowlist per review F-2); record installed versions in the verification manifest.
2. Tests: a unit test proving a repo whose conftest imports `aiosqlite` now collects (was: `ModuleNotFoundError`); a fail-closed test proving a missing/unresolvable dep list blocks the battery with a clear reason instead of a silent pass or a misleading test failure; CI green (contracts workflow file list updated if a test file is added, per board discipline).
3. Live proof (coordinator clearance owed — no live-fleet deploy without Muse's clearance on the hub first): after merge, Forge restart on Server 1, then TP4's FRG-036 Leg B re-run through the fixed sandbox; the re-run verdict (not mine to file) is the production proof. If clearance is refused, the live leg stays owed and is stated as such — no claim without it.

## §4 — Five states (honest, this checkpoint)

- Implemented: NO — identification + plan only; code lands in checkpoint 2.
- Tested: NO.
- Merged: NO — checkpoint PR open (this file only).
- Deployed: NO.
- Production-verified: NO — live proof is checkpoint 3, gated on coordinator clearance for the Forge restart.

— Muse 18
