# TASK-FRD-046 — Checkpoint 2: four storage-repair sequences implemented

- Task: FRIDAY (laptop lane): storage-repair sequences in the pc_health guidance set. P2. Claimed ~11:35 IST 2026-11-27 (hub #2045 comment 7211204803). Checkpoint 1 (scoping) PR #2103 MERGED 15:24 IST 2026-11-27 (merge 841bec7f, Muse 3 VERIFIED).
- Branch `musetp13/task-frd-046-checkpoint-2` from main `09691836`.
- Acceptance (board): each sequence (diskpart repartition, diskpart write-protection removal, Linux fsck equivalent, DISM component-store cleanup) is an enumerate-first, dry-run-by-default guided routine alongside TASK-IG-LAP-03's pc_health/pc_cleanup.

## What changed (6 files, implementation only — no live fleet change)

- `FRIDAY/src/friday/tools/builtin/laptop_pc_care.py` — new `STORAGE_SEQUENCES` registry + pure `build_storage_sequence_plan(sequence, target)` (no laptop, no subprocess) + `LaptopStorageSequencesTool` (`laptop_storage_sequences`, DANGEROUS, command `storage_sequences`). Dry-run by default: `apply` unset/false returns only the ordered plan (steps + exact commands) and runs nothing; `apply=true` additionally needs `confirm=true` and dispatches `{sequence, target, confirm: True}`. Disk 0 and the system volume are always refused by the plan builder.
- `FRIDAY/src/friday/remote/laptop_bridge.py` — `storage_sequences` added to `ALLOWED_LAPTOP_COMMANDS`.
- `FRIDAY/scripts/laptop_bridge_client.py` — `storage_sequences` added to `ALLOWED_COMMANDS` + `_COMMANDS`; new `_cmd_storage_sequences` handler builds every command itself from sequence + target (the server never supplies argv). Refusals in order: unknown sequence, no `confirm=true`, wrong platform, disk 0 / system volume, mounted volume (fsck leg). Diskpart scripts are written to a temp file, run as `diskpart /s <file>`, and removed afterwards. DISM runs `/Analyze` (read-only) then `/StartComponentCleanup`.
- `FRIDAY/src/friday/tools/builtin/__init__.py` — `LaptopStorageSequencesTool` imported + exported.
- `FRIDAY/tests/test_laptop_pc_care.py` — 13 new tests (29 total): registry, per-sequence plans (diskpart script lines verbatim, fsck argv, DISM argv pair), plan refusals (unknown sequence, missing target, system volume, disk 0, non-numeric diskpart target), tool preview/confirm-gate/refusals (preview never dispatches), client handler scripts + refusals + fsck/DISM argv capture.
- `docs/PC_CARE.md` — table row + "Storage-repair sequences (TASK-FRD-046)" section (per-sequence table, owner flow, platform notes).

## Overlap resolution (checkpoint 1 open note)

The "Linux fsck equivalent" sequence overlaps the existing repair function (`chkdsk /f`, `fsck -y`). Resolved as a distinct sequence, not an extension: `laptop_storage_repair` stays the single-volume repair entry point; `fsck_equivalent` is the guided routine that routes by platform (Linux `fsck -y`, macOS `diskutil repairVolume`, Windows refuses and points at `laptop_storage_repair`/`chkdsk /f`). No existing behaviour changed.

## Live leg (results pending — to be filled after the Server 2 run)

- Test suite: `FRIDAY/tests/test_laptop_pc_care.py` to be run on Oracle Server 2 against this branch (pytest, hermetic — client handlers driven through monkeypatched seams, tools through stubbed dispatch; no laptop connected).
- Live enumerate/dry-run probe on Server 2 (Linux, read-only): `lsblk` volume inventory + `fsck -N` dry-run + the plan builder run live for all four sequences.
- Windows-only sequences (diskpart repartition, diskpart write-protection removal, DISM cleanup): no Windows host exists in the fleet, so no live Windows execution is claimed — validated by unit tests + generated-script inspection; live Windows execution awaits the owner's laptop.

— Muse TP13
