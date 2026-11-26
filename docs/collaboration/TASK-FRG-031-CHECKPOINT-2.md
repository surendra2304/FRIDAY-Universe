# TASK-FRG-031 — Checkpoint 2: live preview implemented (Muse TP10, 2026-11-26)

Claim: hub #1483 comment 7177074114 (04:23 IST hourly self-check).
Scoping checkpoint 1: `docs/collaboration/TASK-FRG-031-SCOPING-CHECKPOINT.md`
(commit 79a17c4b). This checkpoint is the repo-side implementation,
filed in the 05:23 IST hourly self-check. API-only route throughout
(contents/merges API); the local clone was not touched.

## Seam pinned (first-hand on main, this run)

- Generated output lives in the task workspace:
  `workspaces/task_<id>/project/` (`Forge/app/core/workspace.py`,
  `WorkspacePaths.project`); verification artifacts live in
  `artifacts/` (incl. `verification_report.json`, written by
  `Forge/app/execution/delivery.py`).
- Baseline gap re-verified: no `StaticFiles` mount anywhere in Forge
  (code search, 0 hits); the dashboard serves only its own HTML shell
  (`Forge/app/dashboard/routes.py`, `/` and `/dashboard`). Artifact
  download exists (`GET /{task_id}/artifacts/{filename}`,
  traversal-guarded FileResponse) but serves delivery artifacts, not
  the generated site. Nothing duplicated.
- Source spec: `Forge/docs/IG_EVALUATION_NOTES.md` section 5 —
  "a preview endpoint that serves a completed build's static files
  read-only, bound to the build's verification manifest (so what is
  previewed is exactly what was verified)".

## Implemented (this branch)

1. **Live preview route** (`Forge/app/api/tasks.py`, commit fbe43fba):
   - `GET /api/tasks/{task_id}/preview` — serves
     `project/index.html` (or `index.htm`) live from disk.
   - `GET /api/tasks/{task_id}/preview/{path}` — serves sibling
     assets (css/js/images) from the same tree.
   - Read-only, traversal-guarded with the same
     `canonical_path` + `relative_to` pattern as artifact download;
     `Cache-Control: no-store` so the preview always shows the
     latest build output; `X-Forge-Verification-Report:
     present|absent` binds the preview to the build's verification
     state — unverified output is never mistaken for verified output.
   - Inherits the existing `/api/*` production API-key middleware;
     no new auth surface.
2. **Tests** (`Forge/tests/unit/test_task_frg031_preview.py`, commit
   c7854e49): mounted-app pattern (boots `create_app()`, TASK-API-001
   precedent) over a real on-disk workspace holding a small generated
   web build — entry page + assets with content types, verification
   header present/absent, 404 without web output, traversal blocked.
   Wired into Forge tier-1 CI (commit c5cadd63).
3. **G-04 recipe recorded** (`Forge/docs/DEV_ENVIRONMENT.md`, commit
   67810cf7): Claude Code in VS Code via API-key config + the G-02
   extension set (Live Server, Quokka.js, Copilot), with the board's
   free-only caveat verbatim: the recipe spends the owner's own paid
   API key when used, so it stays a reference for owner-directed
   sessions, never an automated fleet dependency.

## Demonstration

Repo-side: the test suite demonstrates the preview on a real Forge
workspace web build (files written through `WorkspaceManager`, served
by the assembled app). Live leg (preview on the deployed Forge via
FRIDAY chat) is **gated**: owner stop order on server moves still
stands; it runs only on coordinator clearance. Filed as gated, not
run.

## Board

No board change in this PR: the FRG-031 -> muse_tp10 flip rides in
coordinator board PR #1914 (open at this checkpoint). The hub
assignment (WATCH122/WATCH123) remains the record until it lands.

## States

implemented YES (repo-side) / tested PENDING CI on the work PR /
merged NO / deployed NO / production-verified NO.

— Muse TP10
