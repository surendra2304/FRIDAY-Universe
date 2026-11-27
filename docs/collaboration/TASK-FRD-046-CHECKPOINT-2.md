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

## Live leg (run 2026-11-27 ~19:50 IST on Oracle Server 2, branch @ `094dedb2`)

- **Test suite: 29 passed in 28.09s, exit 0** — `FRIDAY/.venv-friday-ci/bin/python -m pytest FRIDAY/tests/test_laptop_pc_care.py -q` (pytest 9.2.0), run first-hand on Server 2 against the PR head. 16 pre-existing + 13 new; no failures, no skips. (One PytestDeprecationWarning about `asyncio_default_fixture_loop_scope` — pre-existing, unrelated.)
- **Live enumerate (read-only):** `lsblk` on Server 2 — `sda` 50G, `sda1` 49.9G mounted at `/` (88% used), `sda15` 106M `/boot/efi`; no unmounted data volume exists on this host, so no `fsck -y` apply run was possible or attempted.
- **`fsck -N` dry-run (read-only) on `/dev/sda1`:** `fsck from util-linux 2.37.2`, `[/usr/sbin/fsck.ext4 (1) -- /] fsck.ext4 /dev/sda1` — prints what would be done, changes nothing.
- **Plan builder run live** (same venv, `FRIDAY_MEMORY_BACKEND=sqlite` per `FRIDAY/tests/conftest.py` — a bare import fails on the Oracle-backend config check without `DATABASE_URL`; that is environmental, not a code defect; the suite runs under the conftest env): all four plans print exactly as specified — diskpart repartition script `list disk / select disk 2 / clean / create partition primary / format fs=ntfs quick / assign`; write-protect script `list disk / select disk 1 / attributes disk clear readonly`; fsck `["fsck", "-y", "/dev/sdb1"]`; DISM `[["DISM", "/Online", "/Cleanup-Image", "/Analyze"], ["DISM", "/Online", "/Cleanup-Image", "/StartComponentCleanup"]]`. Exit 0.
- **Windows-only sequences (diskpart repartition, diskpart write-protection removal, DISM cleanup): no Windows host exists in the fleet, so no live Windows execution is claimed** — validated by unit tests (script content captured verbatim from the handler) + generated-script inspection; live Windows execution awaits the owner's laptop.
- **CI on PR #2153:** checked after filing (see hub status post for the read); mergeable re-checked at the same time.

— Muse TP13
