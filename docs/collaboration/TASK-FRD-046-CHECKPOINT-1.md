# TASK-FRD-046 — Checkpoint 1: scoping — storage-repair sequences live in `laptop_pc_care` / `PC_CARE`

- Task: FRIDAY (laptop lane): storage-repair sequences in the pc_health guidance set. P2. Claimed ~11:35 IST 2026-11-27 (hub #2045 comment 7211204803). Branch `musetp13/task-frd-046-storage-repair-sequences` @ `83d53187`.
- Acceptance (board): each sequence (diskpart repartition, diskpart write-protection removal, Linux fsck equivalent, DISM component-store cleanup) is an enumerate-first, dry-run-by-default guided routine alongside TASK-IG-LAP-03's pc_health/pc_cleanup.

## Scoping finding (verified first-hand on main `f2b0497e`)

There is no `pc_health` / `pc_cleanup` module path. The guidance set lives under different names:

- `FRIDAY/src/friday/tools/builtin/laptop_pc_care.py` (313 lines) — the pc_health/pc_cleanup tool. The enumerate-first, dry-run-by-default pattern is already established here: temp cleanup enumerates by default and with `apply=true` deletes exactly the enumerated set; disk health check runs chkdsk scan (Windows), diskutil verify (macOS), `fsck -n` (Linux), and a mounted Linux volume is honestly skipped (fsck needs it unmounted); filesystem repair is `chkdsk /f`, `fsck -y` (`:269`).
- `docs/PC_CARE.md` — the TASK-IG-LAP-03 guidance doc ("PC Care — health, cleanup, shortcuts, storage repair").
- Supporting: `FRIDAY/src/friday/remote/laptop_bridge.py`, `FRIDAY/scripts/laptop_bridge_client.py`, `FRIDAY/tests/test_laptop_pc_care.py`.

## Gap (verified by grep on main)

None of the four FRD-046 sequences exists yet in `laptop_pc_care.py` — no `diskpart` and no `DISM` matches. They are new routines to add, following the file's existing enumerate-first / dry-run-by-default pattern.

## Overlap note

The "Linux fsck equivalent" sequence overlaps the existing repair function (`chkdsk /f`, `fsck -y`, `laptop_pc_care.py:269`). Checkpoint 2 scopes whether it extends that function (e.g. an unmounted-volume fsck flow) or is a distinct sequence. No code changed in this checkpoint.

## Next

Checkpoint 2: implement the four sequences in `laptop_pc_care.py` + `PC_CARE.md` guidance, with tests in `test_laptop_pc_care.py`; live leg on the laptop lane per owner gates. This checkpoint is scoping only — no implementation, no live run.

— Muse TP13
