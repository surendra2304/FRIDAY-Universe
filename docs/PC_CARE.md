# PC Care — health, cleanup, shortcuts, storage repair (TASK-IG-LAP-03)

From the owner's Instagram reference corpus: the PC health/tune-up/
cleanup pack (DVQMe9GAE3b, DVhR_XQk6Ml, DemQIPwyiyJ, Dee-1i7hsRy,
DefKD7YKzol), the productivity shortcut set (DVekxHGCFWT), and the
storage-repair utilities (DVlGJaNEal2). All of it rides the LAP-001
laptop bridge — five new commands, implemented in
`FRIDAY/scripts/laptop_bridge_client.py`, with tools in
`FRIDAY/src/friday/tools/builtin/laptop_pc_care.py`.

| Tool | Class | What it does |
|---|---|---|
| `laptop_pc_health` | SAFE | Read-only report: per-disk usage, CPU/memory pressure, battery + Windows power plan, uptime, top memory processes, temp-folder size, and a tune-up checklist derived from the measured values. Sections that can't be measured say so. |
| `laptop_pc_cleanup` | SENSITIVE | Temp-file cleanup. **Default is enumerate-only**: lists candidate files (temp dirs, older than `min_age_hours`, default 24) with count/bytes/sample and deletes nothing. `apply=true` deletes exactly the enumerated files and reports freed bytes + locked-file failures. Symlinks are never followed or deleted. |
| `laptop_hotkey` | SENSITIVE | Named shortcuts (copy, paste, undo, redo, save, find, new_tab, close_tab, reopen_tab, address_bar, refresh, switch_window, show_desktop, lock, back, forward, …) or an explicit key combo. Key names are allowlist-validated on the server AND the laptop; `mod` resolves to ctrl (Windows/Linux) or command (macOS) on the laptop. A few named shortcuts are Windows-flavoured — macOS owners pass explicit keys. |
| `laptop_storage_check` | SAFE | Read-only filesystem check: `chkdsk` scan (Windows), `diskutil verifyVolume` (macOS), `fsck -n` (Linux). On Linux a **mounted** volume is reported as skipped, honestly — fsck must not run on a mounted filesystem. |
| `laptop_storage_repair` | DANGEROUS | `chkdsk /f` / `fsck -y` / `diskutil repairVolume`. Requires an explicit volume AND `confirm=true` in the same call, validated by the tool AND the laptop. The laptop refuses the system volume outright, and (outside Windows, where chkdsk manages its own lock) any mounted volume. Repair usually needs the laptop client running with administrator/root rights; a permission failure is reported as such, never as success. |

## Typical owner flow for a corrupted USB/SD card

1. Plug the card into the laptop; if it mounts, eject/unmount it (the
   files stay untouched — unmounting is not formatting).
2. Ask FRIDAY: "check the USB stick" → `laptop_storage_check` runs the
   read-only scan and reports.
3. If errors are reported, FRIDAY shows the result and asks; only then
   `laptop_storage_repair` with `confirm=true`.

## Verification status

Implemented + unit-tested (client handlers driven through monkeypatched
platform seams; tools through stubbed dispatch —
FRIDAY/tests/test_laptop_pc_care.py, 15 tests). The owner's laptop is
**not yet connected**, so no device verification is claimed. One real
bug was caught by these tests before shipping: the system-volume
refusal compared a normalised path against an un-normalised one and
would have missed `/` on Linux — fixed and covered.
