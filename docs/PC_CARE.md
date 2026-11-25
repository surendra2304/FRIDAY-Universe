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

## Guidance additions (TASK-LAP-005)

Docs-only additions to what FRIDAY tells the owner. Same rules as the
rest of this file: read-only first, verify before changing anything,
never a destructive default. No live device was available to verify
against; see `docs/collaboration/TASK-LAP-005-EVIDENCE.md` for the
per-item grounding.

### Recovery escalation ladder for a USB stick / SD card that will not mount

Extends the "corrupted USB/SD card" flow above. When the card does not
mount at all, `laptop_storage_check` has nothing to scan — escalate in
this order, read-only first:

1. Try another port, another card reader, another machine — rules out
   the port before blaming the card.
2. `laptop_pc_health` — confirm the laptop itself is healthy (disk
   pressure, no resource exhaustion).
3. Bootable USB rescue route ("USB TOOLS" route): a rescue USB (Ventoy
   plus a free recovery ISO such as Hiren's BootCD PE) boots the laptop
   outside Windows so the card can be read without Windows mounting
   it. Never write anything to the failing card — recovery tools read
   from it and write recovered files to a *different* drive.
4. File recovery: PhotoRec / TestDisk (free, open source) carve files
   from the raw device; see Autopsy below for a GUI route.
5. If the card is physically damaged (not detected anywhere, clicking,
   heat, smell) — stop. No software recovers a dead controller; a
   professional lab is the only route, and every further attempt risks
   more loss.

### Autopsy — when recovery needs a forensic-grade look

Autopsy (sleuthkit.org/autopsy) is a free, open-source graphical
front-end to The Sleuth Kit. It reads a disk *image* (or a
write-blocked drive) without mounting it, lists deleted files, and
carves data from unallocated space with its built-in PhotoRec engine.
When to mention it: the owner already has an image of the failing
drive (`.dd` / `.E01`) and wants to browse what is recoverable before
paying anyone. Rules: always work on a copy or image, never on the
original; Autopsy is a heavyweight tool — for a single deleted file,
PhotoRec alone is faster. Only examine drives the owner owns.

### WinSAT probe — caveat before you run it

`winsat formal` (Windows System Assessment Tool, built into Windows)
is a quick, scriptable first check of CPU, memory, disk and graphics
— no download. Caveats FRIDAY must state before suggesting it:

- Legacy: Microsoft warns the WinSAT API may be altered or
  unavailable after Windows 8.1; the old Experience Index screen is
  gone, and `D3DScore` is not a modern gaming or GPU benchmark.
- It cannot run on battery power or remotely; run on AC power, close
  demanding apps, and treat one run as a rough check, not lab evidence.
- Never run the disk assessment on a drive already showing failure
  signs — read-only health first (`laptop_pc_health`,
  `laptop_storage_check`). A failing drive should be imaged, not
  benchmarked.
- Results land in `%WINDIR%\Performance\WinSAT\DataStore`; read scores
  with PowerShell `Get-CimInstance Win32_WinSAT`.

### Invisible-folder procedure — obscurity, not security

To hide a folder from casual browsing: `attrib +h +s "C:\path\folder"`
(Command Prompt) hides it even from normal hidden-file views;
`attrib -h -s` reverses it. FRIDAY must say plainly: this hides the
folder, it does not protect it — anyone who enables "show hidden
files" or knows the path can open it. For anything that must actually
stay private, use BitLocker (drive encryption) or a VeraCrypt
container, not hiding.

### NetLimiter — reference, with the price stated

NetLimiter (netlimiter.com, Windows only) shows per-app upload and
download in real time and can cap, prioritise, block, or quota each
application's traffic — the answer to "what is eating my internet".
Price honesty: 28-day full trial, then a paid yearly licence (from
€19/year per PC); after the trial it keeps monitoring and keeps
existing rules in Restricted Mode, but new rules and Stats need the
licence. FREE-ONLY rule: FRIDAY offers the built-in check first —
Task Manager > App history / Performance, and Resource Monitor
(`resmon`) > Network — and names NetLimiter only as the paid step-up,
never as free.

### BIOS cores step — check Windows before touching BIOS

If Task Manager > Performance > CPU shows fewer logical processors
than the chip should have: first check `msconfig` > Boot > Advanced
options — "Number of processors" must be unticked (a ticked, low
value caps cores in Windows). Only if Windows is uncapped and the
count is still low, reboot into BIOS/UEFI and look for "Active
Processor Cores" / "Core Multi-Processing" — enable all cores, save,
exit. Warning: BIOS/UEFI settings can stop a machine booting if
changed carelessly; change only the cores setting, photograph the
screen before changing anything, and never touch voltage or overclock
settings.

### services.msc — verify-first evaluation

Before disabling any Windows service to "speed up" the PC: open
`services.msc`, read the service's own Description and its
Dependencies tab, and check what breaks if it stops. Rules: set
Manual, never Disabled, on a first change; change one service at a
time and reboot-test; never bulk-disable from a "speed up Windows"
list — those lists are how owners break printing, Wi-Fi, and Windows
Update. If FRIDAY cannot name what a service does, it says so and
does not recommend touching it.
