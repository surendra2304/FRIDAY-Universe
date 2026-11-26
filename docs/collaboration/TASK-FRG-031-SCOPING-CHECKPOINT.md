# TASK-FRG-031 — Scoping checkpoint 1 (Muse TP10, 2026-11-26)

Claim provenance: assigned to Muse TP10 by coordinator WATCH122 (hub #1483
comment 7176443876, queue position 3; TASK-WF-002 re-slotted to the pool in
the same watch after 2h+ zero execution evidence on branch
`musetp10/task-wf-002`). Nudged to claim in WATCH123 (hub 7176656559).
Claimed in the 04:23 IST hourly self-check as stall repair. Board record on
main `bf5a08b7` still reads AVAILABLE / owner null; the board flip rides in
the coordinator's queued rebuild (board-PR blocker, WATCH122/WATCH123) — the
hub assignment is the record until then.

## Acceptance (board, TASK-FRG-031)

1. Live preview of generated web output inside Forge's build loop.
2. Record the G-04 Claude-Code-in-VS-Code setup recipe as a Forge
   dev-environment reference. Free-only caveat: the recipe spends the
   owner's own paid API key when used, so it stays a reference for
   owner-directed sessions, never an automated fleet dependency.
3. Done = live preview demonstrated on one real Forge web build + the recipe
   recorded with its cost caveat.

## Recon (read-only, this run, main bf5a08b7)

- `Forge/app/` layout confirmed via contents API: `api/`, `dashboard/`,
  `delivery/`, `execution/`, `pipeline/`, `templates/`, `verification/`,
  `main.py`, `cli.py` among others. The preview seam most likely sits at
  the delivery/dashboard boundary; exact mount point to be pinned by
  reading `Forge/app/main.py` + `Forge/app/api/` + `Forge/app/dashboard/`
  before any code change.
- `Forge/docs/` holds the reference set (ARCHITECTURE, API_REFERENCE,
  PROJECT_TYPES, ...). The G-04 recipe reference belongs alongside them
  (new `Forge/docs/DEV_ENVIRONMENT.md` or an appended section — decide
  after reading the existing docs' shape; no duplication).
- Baseline gap per board: live preview of generated web output is absent
  from Forge today. To be re-verified in code (search for preview/static
  serving of build output) before building, so the work does not duplicate
  an existing seam.

## Build plan (repo-side, one PR)

1. Pin the build-output seam: where Forge writes generated web output and
   how the dashboard/API serves artifacts today.
2. Add a minimal live-preview route that serves the latest generated web
   output for a build, with tests (no new paid dependency; stdlib/existing
   stack only).
3. Record the G-04 recipe as a dev-environment reference with the
   paid-key cost caveat verbatim from the board.
4. Demonstrate on one real Forge web build (repo-side run; live leg via
   FRIDAY chat only if the coordinator clears it — owner stop order on
   server moves still stands).

## States

implemented NO / tested NO / merged NO / deployed NO /
production-verified NO. This checkpoint is scoping only; no code changed.

— Muse TP10
