# TASK-LAP-004 — Scope (checkpoint 0, stall repair)

- **Task:** TASK-LAP-004 — REPO-IMPLEMENT: laptop/phone repos, wave 2. P1.
- **Claim:** hub #1483 comment 7174707728 (~02:40 IST, 2026-11-26). Branch `muse8/task-lap-004`
  from main `ebba852d`. Board flip AVAILABLE → CLAIMED rides in the work PR
  (no checkpoint PRs, owner order).
- **Stall repaired this run:** branch sat at the claim base `ebba852d` with zero
  commits for ~100 min (claim ~02:40 IST, this doc 04:22 IST). This scope doc is
  the first commit; scoping is verified first-hand below, not asserted.
- **Board (main `bf5a08b7`, blob `49eaef16`, 23,298 lines, verified this run):**
  LAP-004 AVAILABLE / owner muse_8 / branch null / pr null. Queue: EARN-026
  (IN_REVIEW, pr 1897 merged; next leg owner-gated on platform accounts) →
  LAP-004 (head) → FRG-032 → DB-006.

## Sources verified first-hand this run

- Registry `IntelX/intelx/registries/scouted_repos.json`, blob `a18c2403`,
  178,227 B, 102 entries — LAP-004's three entries read in full
  (`arditbe-ultronai.md`, `abuzar-ansarii-ultron.md`, `viarotel-org-escrcpy.md`).
- Upstream API reads (2026-11-26 ~04:20 IST):
  - `arditbe/UltronAI` — pushed 2026-11-15T01:13:13Z, created 2026-11-15,
    licence **None** (API), JavaScript, 357 KB, 28 stars, 4 forks, not archived.
  - `AbuZar-Ansarii/Ultron` — pushed 2026-10-24T15:01:16Z, created 2026-10-18,
    licence **None** via API (MIT claimed in README/badge only, no LICENSE
    file), Python, 1,562 KB, 168 stars, 53 forks, not archived.
  - `viarotel-org/escrcpy` — pushed 2026-10-26T10:07:13Z, created 2023-09-15,
    licence **Apache-2.0**, JavaScript, 428,034 KB, 12,475 stars, 882 forks,
    not archived.
- Board record read in full on main `bf5a08b7` (acceptance quoted in §Legs).

## Finding 1 — Escrcpy adapt already implemented repo-side (TASK-IG2-LAP-01)

The LAP-004 board acceptance names Escrcpy (adapt). That adapt already exists
on main, delivered under TASK-IG2-LAP-01 (commit `c196d243`, 2026-11-16):

| Piece | File (blob SHA on main `bf5a08b7`) | Size |
|---|---|---|
| Integration engine | `FRIDAY/src/friday/remote/escrcpy_integration.py` (`a61d6a45`) | 11,042 B |
| Tools | `FRIDAY/src/friday/tools/builtin/escrcpy_control.py` (`4fe4a36f`) | 5,013 B |
| Tests | `FRIDAY/tests/test_ig2_lap01_escrcpy.py` (`23864f47`) | 3,393 B, 8 tests |
| Doc | `docs/ESCRCPY_INTEGRATION.md` (`812b50b3`) | 3,015 B |

Read first-hand this run (module docstring + tools + all 8 tests + doc):
validated shell-free launch-plan builder (`MirrorProfile` → `build_launch_args`),
`adb devices` parsing, declarative `AutomationScript` (tap/swipe/type/wait/
find-text) validated against the same safety gates as `friday.remote.phone_ui_agent`
and rendered to plain `adb` commands over the existing scrcpy/ADB transport —
no second control stack, no EscrcpyX (paid extension explicitly out, FREE-only
rule), no code vendored or copied (TypeScript/Electron → FRIDAY-native pattern
adaptation). Tools: `escrcpy_launch_plan` (SAFE) + `escrcpy_automation`
(SENSITIVE). Owner setup is laptop-side (realme narzo 30 Pro 5G, Escrcpy
release or `brew install --cask escrcpy`).

**Gap (REL-001 pattern): the test is NOT wired into CI.** Code search for
`test_ig2_lap01_escrcpy` finds it only in `docs/ESCRCPY_INTEGRATION.md` and the
INT-044 tracker — zero hits in `.github/workflows/`. The Escrcpy leg is
implemented but its test has no CI proof.

## Finding 2 — ULTRON reference-only legs

- **arditbe/UltronAI (reference-only): NO LICENCE** — API licence null, registry
  agrees. The code can be read, not legally copied or adapted. Local-first
  Node.js desktop assistant (continuous voice, webcam vision, screen/app
  control, Tailscale-paired iPhone app, local Ollama 4B–27B, 8 GB download,
  8–32 GB RAM). Fleet-infeasible: 956 MB servers, ~180 MB/service caps,
  Python 3.10, no GPU. Reference value only: always-listening feel,
  computer + phone in one companion, memory as plain local files.
- **AbuZar-Ansarii/Ultron (reference-only): MIT claimed in README/badge only.**
  API licence null, no LICENSE file in the root listing — the MIT claim is
  unproven; do NOT copy on the badge alone. Python desktop app (PyQt6 HUD,
  Gemini Live session engine, 51 auto-discovered tools, ADB/scrcpy bridge,
  hot-loadable tools, local SQLite knowledge graph). Fleet-infeasible:
  desktop GUI, Python 3.11+, display/webcam/mic. Reference value only:
  workspace presets, knowledge-graph memory (Memora design input),
  hot-loadable tool actions (Forge design input). Capability list is README
  assertion, untested.
- **Guardrail proof of absence (code level, verified this run):**
  `UltronAI`, `arditbe`, and `AbuZar-Ansarii` each appear in exactly 2 files —
  the registry and the INT-044 tracker. Zero code imports, zero vendored
  files. Neither ULTRON repo is in any FRIDAY production path. (The live-trial
  half of the reference-only acceptance is still owed — see Live legs.)

## Dependency — LAP-003 owns the scrcpy transport

- **TASK-LAP-003 (CLAIMED, muse_12):** AURA / ARTEMIS (adapt), **scrcpy
  (adopt)**, Browser… — the scrcpy transport adoption is LAP-003's leg, not
  LAP-004's. LAP-004's Escrcpy adapt sits on that transport; no duplicate
  transport work. Sequence after / coordinate with LAP-003.
- **TASK-LAP-002 (AVAILABLE, muse_13):** wave-2 PRODUCTION-VERIFY
  (IG-LAP-01..04 + IG2-LAP-01) — LAP-004's live legs overlap its verification
  scope; coordinate, do not duplicate.
- LAP-001 VERIFIED (muse_ai, pr 337); LAP-005 MERGED (muse_15, pr 1894);
  LAP-006 CLOSED.

## Live legs BLOCKED (not done)

Acceptance: "real device task executed via the bridge on the real laptop/phone
path + disconnect/reconnect failure case". Blocked: owner stop order in force
(WATCH109: IG-INF-01-FIX-01 deploy clearance NOT granted), fleet CD broken,
S2 disk ~86–88%. No live probe run, nothing live claimed. Live legs owed when
clearance lands, or the coordinator rules them follow-up work (STR-047
precedent).

## Legs

- **Leg 1 (repo-side, doable now):** Escrcpy verification vs the current
  escrcpy release + wire `test_ig2_lap01_escrcpy.py` into CI (friday-universe-ci.yml
  tier-1 or the contracts list, whichever owns FRIDAY tests) and prove green +
  reconcile the INT-044 tracker rows that cite the escrcpy test.
- **Leg 2 (repo-side now, live later):** ULTRON reference evidence per repo —
  absence proven above; live-trial half gated with the live legs.
- **Leg 3 (gated):** live end-to-end (real device task via the bridge) +
  disconnect/reconnect failure case on the real laptop/phone path.

## Open questions

- **Q1:** LAP-004's Escrcpy leg vs IG2-LAP-01 — the adapt is implemented; is
  LAP-004's completion the live proof + CI wiring, or does the coordinator
  want new implementation? Lean: completion = live proof + CI wiring +
  evidence doc; no re-implementation of the adapt.
- **Q2:** escrcpy release pin — the integration pins no version; record which
  release the verification checks (latest release at verification time).

## Out of scope / no-go

- No copying `arditbe/UltronAI` code (no licence). No copying AbuZar code on a
  README-only MIT claim.
- No EscrcpyX paid extension (FREE-only). No live runs without clearance.
- No repo-code execution on this VM (execution-risk check) — CI is the live
  proof for code. No checkpoint PRs — the board flip rides in the work PR.

— Muse 8, 2026-11-26 ~04:22 IST
