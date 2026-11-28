# TASK-FRG-027 — Forge repos wave 3 evidence

- **Task:** TASK-FRG-027 (P2) — REPO-IMPLEMENT Forge repos wave 3, target Forge.
- **Claim:** hub #2045 comment 7231225933.
- **Branch:** `muse7/task-frg-027-forge-repos-wave3`.
- **Five states:** implemented YES (repo-side) / tested YES (repo tests + CI on the work PR) / merged NO / deployed NO / production-verified NO.

## 1. Verdicts

| Repo | Verdict | What it means here |
|---|---|---|
| MausBot / OpenMausBot (`milind-soni/OpenMausBot`) | **REFERENCE-ONLY** | Unified multi-agent shell UX stays a reference for Forge's builder-environment idea. Guardrail proof (§4): no production import, dependency, or runtime reference in Forge; mentions exist only in evaluation notes. |
| JCode (`1jehuang/jcode`) | **ADAPT** | The Rust harness is not adopted. Its lean-session patterns are adapted in `Forge/forge_upgrade/jcode_harness.py`: a declared context budget that never truncates required brief parts, and a parallel-session scope ledger that refuses overlapping reservations at plan time. Both run inside `ForgeBuildRun`'s plan stage. |
| Paperclip (`paperclipai/paperclip`) | **REFERENCE-ONLY** | Org-chart/budget/approval governance mirrors FRIDAY's board model and stays a reference. Guardrail proof (§4): no production import, dependency, or runtime reference in Forge. |
| M3E Canvas (`lnkiai/m3e-canvas`) | **ADOPT** | The sketch-to-prompt contract already existed as `Forge/app/planning/sketch_prompt.py` but was tests-only (§4). `ForgeBuildRun` now accepts `spec.sketch`, parses it fail-closed at plan time, and carries the emitted prompt as required run context. |

## 2. What was built

- `Forge/forge_upgrade/jcode_harness.py` (new) — `compact_context`
  (required parts kept whole or refused; optional parts admitted
  in order while they fit) and `LeanSessionLedger` (scope
  reservations with overlap refusal and cross-session file
  checks). Stdlib-only and deterministic.
- `Forge/forge_upgrade/build_run.py` — `BuildRunSpec` gains
  `sketch`, `session_id`, `context_budget_chars`, and
  `session_ledger`. The plan stage now: parses the M3E sketch
  (a structural defect blocks the run before any code), fits the
  run context (task + assumptions + criteria + sketch prompt
  required; guidance optional) into the lean budget, and reserves
  the declared scope. The implement stage records the
  cross-session file check. Reservations release when the run
  finishes. Defaults keep FRG-028 runs unchanged.
- `Forge/tests/test_frg027_forge_repos_wave3.py` (new) — through
  the production caller: a sketched two-screen app builds end to
  end (pages written, tests run for real, sketch + lean-session
  evidence in the report); failure cases block before any code
  (dangling sketch link, required context over budget, parallel
  session scope conflict); the reference-only guardrail test
  scans every production `.py` under `Forge/app` and
  `Forge/forge_upgrade` plus `requirements.txt`/`pyproject.toml`.

## 3. Repo-side proof

Local through-caller checks (API-fetched subset, Memora writes
degrading to guarded warnings offline as designed): happy path
completed with `m3e_sketch: adopted: Kirana List, 2 screens,
2 flows, 0 warnings` and `lean context 1450/20000 chars`;
broken sketch, over-budget context, and scope conflict each
blocked before any build step ran. CI on the work PR is the
test executor of record.

## 4. Guardrail search (pre-change, branch base `98215372`)

Full-text search over every `Forge/` `.py`/`.toml`/`.txt`/`.md`
blob at the branch base:

- `sketch_prompt` / `parse_sketch`: only
  `Forge/app/planning/sketch_prompt.py` and its test — **no
  production caller** before this change.
- `design_import` / `parse_design_spec`: only its module and
  test — tests-only (not an FRG-027 verdict item; left as is).
- MausBot/OpenMausBot/Paperclip tokens: only
  `Forge/docs/IG_EVALUATION_NOTES.md` and
  `Forge/docs/IG2_EVALUATION_NOTES.md` — no production code,
  no dependency surface.
- JCode tokens: evaluation notes only, before this change.

## 5. Live leg — owed, not claimed

Production-verified is **NO**. The acceptance live leg — a real
build task for another agent executed end-to-end through the
deployed Forge with its output used in production, plus the
reference-only guardrail re-check on the live checkout — needs
coordinator merge + deploy/clearance for TASK-FRG-027. No
deploy, restart, env flip, or live build execution was
attempted under this task. On clearance, the owed proof is:
one sketched build task through the deployed `ForgeBuildRun`
path including the broken-sketch failure case, and a live
checkout search confirming the reference-only absence.

— Muse 7
