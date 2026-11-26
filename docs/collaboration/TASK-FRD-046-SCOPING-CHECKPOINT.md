# TASK-FRD-046 — scoping checkpoint (Muse TP10, 2026-11-26 ~10:23 IST self-check)

Task: FRIDAY (laptop lane): storage-repair sequences in the pc_health guidance set.
Claimed 2026-11-26 (hub #1483 comment 7182163623), branch
`musetp10/task-frd-046` from main `7e4dea62`. Queue: FRD-046 (now) →
FRG-031 resume (PR #1921) → DB-011 pre-staged. Five states all NO.

## Acceptance (re-verified at current main)

Board record TASK-FRD-046 re-read first-hand on main `e8f50ef6`
(WORK_BOARD.yaml blob `2a4751c3`): P2, blockers [], status AVAILABLE /
owner muse_tp10 (board flip rides in the work PR). Acceptance: "Each
sequence (diskpart repartition, diskpart write-protection removal, Linux
fsck equivalent, DISM component-store cleanup) is an enumerate-first,
dry-run-by-default guided routine alongside TASK-IG-LAP-03's
pc_health/pc_cleanup." Board evidence cites GAP-LIST.md section 2 /
TASK-FRD-LAP-REPAIR (IG package F-06, F-07, F-08, F-20) as source;
GAP-LIST was not found via code search at current main (path and content
search, 2026-11-26) — the board record above is treated as the brief of
record. If a hub ruling narrows or widens scope, that text wins.

## Anchors re-verified at main e8f50ef6 (existence + blob sha)

- `FRIDAY/src/friday/tools/builtin/laptop_pc_care.py` — e16f6df3
- `FRIDAY/scripts/laptop_bridge_client.py` — 79555dc0
- `FRIDAY/src/friday/remote/laptop_bridge.py` — cfa45b2f
- `docs/PC_CARE.md` — f69a1ff9
- `FRIDAY/tests/test_laptop_pc_care.py` — 654b294d

Line-level anchors below are from the local plan verified at `f216e1b`
(stale clone); each must be re-checked at current main before editing.

## Gap analysis (from plan at f216e1b; IG-LAP-03 base present)

Already provided by IG-LAP-03 (MERGED): `pc_health`, `pc_cleanup`
(enumerate-by-default), `storage_check` (chkdsk scan / fsck -n),
`storage_repair` (chkdsk /f / fsck -y, confirm-gated, system/mounted
refusals), allowlists in parity on both bridge sides, tool registration,
tests, `docs/PC_CARE.md`.

Still missing for FRD-046:
1. diskpart repartition sequence — missing entirely.
2. diskpart write-protection removal — missing entirely.
3. Linux fsck equivalent — partial: storage_check/storage_repair exist,
   but not as an enumerate-first guided chain alongside pc_health/
   pc_cleanup. FRD-046 adds the guided wrapper + PC_CARE.md flow,
   reusing storage_repair semantics; no second fsck executor.
4. DISM component-store cleanup — missing entirely.

Safety constraint (plan, f216e1b): diskpart is blocked in four
independent guards (file_and_command blocklist, launch_application
forbidden list, computer_control regex, desktop guard). FRD-046 must NOT
route diskpart through any free-form command path and must NOT weaken
those guards. Only route: dedicated bridge commands with fixed argv
templates, validated on both sides, enumerate-first, confirm-gated,
system disk refused — the IG-LAP-03 pattern.

## Scope decisions for implementation

- Four guided routines, each: enumerate (default, read-only) → plan
  shown → apply only with explicit confirm in the same call. Fixed argv
  via `_run_capture([...])`; no shell strings, no owner free text in
  commands; disk/volume validated before use; allowlist parity on both
  sides with parity test; registration in `builtin/__init__.py` and
  `agent/mixins/tools.py`.
- Repartition apply is underspecified in the board line (shrink? create?
  delete? format?). v1 scope: enumerate + exact diskpart script preview
  as the dry-run; execution only with confirm=true + explicit disk
  number + system-disk refusal. Never guess destructive parameters.
- Write-protect: enumerate via `list disk`/`detail disk`; apply
  `attributes disk clear readonly` for the named non-system disk only,
  with before/after read-back.
- DISM: enumerate = `/AnalyzeComponentStore` (read-only dry-run); apply
  = `/StartComponentCleanup` confirm-gated.
- Non-Windows / permission failures reported honestly (`not_run` /
  unsupported detail), never as success.

## File touch list (verify each at current main before editing)

- `FRIDAY/scripts/laptop_bridge_client.py` — new handlers + allowlist.
- `FRIDAY/src/friday/remote/laptop_bridge.py` — `ALLOWED_LAPTOP_COMMANDS`.
- `FRIDAY/src/friday/tools/builtin/laptop_pc_care.py` — new Tool classes.
- `FRIDAY/src/friday/tools/builtin/__init__.py`, `FRIDAY/src/friday/agent/mixins/tools.py` — registration.
- Tests: extend `test_laptop_pc_care.py` harness or new
  `test_frd046_storage_sequences.py` (enumerate mutates nothing, apply
  refuses without confirm, system/mounted refused, exact argv asserted,
  non-Windows honest unsupported, allowlist parity).
- `docs/PC_CARE.md` — new rows + guided flows.
- `docs/collaboration/WORK_BOARD.yaml` — FRD-046 flip rides in the work
  PR, edited from the current main blob.

## States

implemented NO / tested NO / merged NO / deployed NO /
production-verified NO. Live laptop leg gated (owner's laptop not
connected; owner stop order on live legs stands) — repo-side first, one
work PR, peer merge only on green CI. Next step: implement per above on
`musetp10/task-frd-046`.

— Muse TP10
