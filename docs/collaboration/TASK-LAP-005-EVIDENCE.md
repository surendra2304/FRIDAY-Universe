# TASK-LAP-005 — Evidence

**Task:** Laptop/phone guidance additions bundle: USB TOOLS route +
recovery escalation, Autopsy mention, WinSAT probe caveat,
invisible-folder procedure, NetLimiter reference, DROIDLAB guide,
BIOS cores step, services.msc verify-first evaluation.
**Worker:** Muse 15. **Claimed:** 2026-11-26 ~02:09 IST (hub comment
7173987632, WATCH117 assignment 7173839964). **Branch:**
`muse15/task-lap-005-laptop-phone-guidance-bundle`, rebased onto main
8abf3a94 (coordinator board PR #1893 merged during this run).
**Work PR:** #1894 (open). **Type:** docs-only guidance additions;
FRIDAY behaviour change (what FRIDAY tells the owner), no code, no
deploy.

## What changed

- `docs/PC_CARE.md` — new "Guidance additions (TASK-LAP-005)"
  section: 7 PC items (recovery escalation ladder incl. USB TOOLS
  rescue route, Autopsy, WinSAT caveat, invisible-folder procedure,
  NetLimiter with price stated, BIOS cores step, services.msc
  verify-first).
- `docs/PHONE_CONTROL.md` — new "DROIDLAB" section: gesture
  shortcuts on Android (1 phone item).
- This evidence doc.

## Per-item grounding (checked first-hand this run)

Source of record for every item: the board record's acceptance
criteria (F-09…F-23), read from `docs/collaboration/WORK_BOARD.yaml`
on main 8abf3a94 after the first draft was written — see the
correction note below. Each item below is in its recorded form.

| Item | Source (board acceptance) | Grounded against | Result |
|---|---|---|---|
| USB TOOLS route + recovery escalation | F-09, item DVlGJaNEal2 — phone-only "USB TOOLS" Play Store app route for drive recovery; escalation: if nothing detects the drive, use a professional data-recovery technician | Google Play listing (USB TOOLS, MixApplications — format/wipe/partition/backup/repair over OTG, no root; recovery scans free, formatting costs tokens) + developer FAQ (mixapplications.com: "The phone has to detect the drive first"; OTG on, data cable, USB OTG mode) | Route documented as recorded: phone + OTG, recover to a different drive, professional technician if nothing detects the drive. |
| Autopsy mention | F-10, same item — Autopsy or other data-recovery tools if no new data has been written | sleuthkit.org/autopsy (free, open source, GUI front-end to The Sleuth Kit; PhotoRec carving engine; works on disk images read-only) | Mentioned as the GUI route once a disk image exists, with the no-new-data condition stated. |
| WinSAT probe caveat | F-11, item DXZ0dlzjijM — WinSAT caveat: WinSPRLevel can read 0 or 1 on capable gaming hardware, so the probe score must not be used alone to gate heavy-work assignment | Microsoft Learn (WinSAT config scores doc); itechguides/mefmobile WinSAT explainers | Recorded caveat present verbatim; generic caveats (legacy, AC-only, D3DScore not a modern benchmark, never benchmark a failing drive) kept alongside. |
| Invisible-folder procedure | F-12/F-13, item DXRt_JKjKKt — rename holding Alt+0160 for a blank name, then Properties > Customize > Change Icon to the transparent icon | Recorded procedure as filed; standard Windows behaviour | Procedure documented as recorded, labelled cosmetic privacy, not security; BitLocker/VeraCrypt for real privacy. |
| NetLimiter reference | F-14, item DXv5XxionLq — NetLimiter named as the bandwidth-limiting tool reference | netlimiter.com (Windows only, 28-day trial); independent reviews (exedepot, rottenwifi) | Price stated plainly: trial then paid yearly licence (from €19/year/PC); Restricted Mode after trial. Built-in free check (Task Manager / resmon) offered first per the FREE-ONLY rule. |
| DROIDLAB guide | F-19, item Dc_PBtEq0YM — DROIDLAB Android customisation: gesture controls, theme changes, quick settings | AppBrain Play Store listing (DroidLab: Gesture Toolkit, Light Source Labs, free, Android 8.0+); Softonic description; Facebook reel 1412796127460354 (Moonxfinds, 2026-09-19) showing the back-tap flashlight demo | Guide: Calibration Wizard first, Accessibility permission (system "danger" prompt is normal), check for a built-in gesture first, never map destructive actions; theme changes + Quick Settings covered. |
| BIOS cores step | F-23, item Dee-1i7hsRy — BIOS step: make sure all CPU cores are enabled | Standard Windows/BIOS behaviour (`msconfig` Boot > Advanced options "Number of processors"; BIOS "Active Processor Cores" / "Core Multi-Processing") | Windows check first, BIOS second, photograph-before-change warning, never touch voltage/overclock. |
| services.msc verify-first + F-16 trio verdicts | F-16, item DZ2nntDKOxe — recipe (disable SysMain, disable Connected User Experiences and Telemetry, disable Windows Search, claimed 56%→11% memory graphic) is FLAGGED CONTESTED in its own source comments; VERIFY-FIRST rule: each change tested for safety/reversibility in a sandbox first; only verified-safe changes enter guidance, the rest recorded as rejected with reasons. Done = per-service verdict for the F-16 trio | Published service documentation + independent guides (howtogeek, xda-developers, urtech.ca, geekchamp, windowsforum): SysMain disables normally via services.msc and is safe/reversible; DiagTrack safe to disable for personal use, does not break Windows Update; WSearch safe to disable for personal use, search falls back to slow unindexed scanning, caution on corporate (Outlook instant search) | Verdicts recorded in `docs/PC_CARE.md`: all three safe to disable and reversible, each with its real cost; the "56%→11% memory" graphic REJECTED (Task Manager memory % is not a valid before/after metric; SysMain preload is by design). The source comment "Windows won't even let you disable SysMain" is itself wrong and is noted as such. |

## Correction note (first draft was wrong on three items)

The first draft of this bundle was written from the task title alone,
before the board record's acceptance criteria were read. It got three
items wrong against the recorded sources and was corrected in the same
run, before the work PR was reviewed:

1. USB TOOLS was written as a bootable-USB rescue route (Ventoy +
   Hiren's BootCD PE). The recorded route is the phone-only Play Store
   app over OTG. Replaced.
2. The invisible-folder procedure was written as `attrib +h +s`.
   The recorded procedure is Alt+0160 blank name + transparent icon.
   Replaced.
3. The WinSAT caveat was generic only; the recorded caveat
   (WinSPRLevel 0/1 on capable gaming hardware; never gate heavy-work
   assignment on the score alone) was missing. Added.

Lesson recorded: read the board record's full acceptance criteria
before writing, not just the title and status.

## Grounding gaps (stated, not hidden)

1. The re-audit source package (videos/watch records) is not in this
   workspace (`~/workspace/ig-references/` does not exist here; no
   LAP-005 source doc found in the repo). Items are grounded against
   the board record's acceptance criteria plus each tool's published
   documentation. The source video IDs cited in the acceptance
   (DVlGJaNEal2, DXZ0dlzjijM, DXRt_JKjKKt, DXv5XxionLq, DZ2nntDKOxe,
   Dc_PBtEq0YM, Dee-1i7hsRy) are recorded in the table above.
2. **F-16 sandbox test not run.** The acceptance's VERIFY-FIRST rule
   asks for each F-16 change to be tested for safety and reversibility
   in a sandbox first. No Windows sandbox was available in this
   environment, so no live test was run and none is claimed. The
   verdicts rest on published service documentation and independent
   guides, which agree with each other on all three services. A live
   sandbox re-test remains owed before the owner acts on the trio on
   a machine he cares about; the guidance says Manual-first, one
   change at a time, reboot-test — the safe form of the same rule.

## Verification status

- Docs only: no code changed, no tests added (nothing executable to
  test), no deploy, no live device involved.
- The owner's laptop is **not connected** (same standing caveat as
  `docs/PC_CARE.md`), so no item was verified on a real machine.
  Every procedure is written verify-first / read-only-first so it is
  safe to follow as written.
- No paid service recommended as free: NetLimiter's price is stated;
  every other item is free or built into Windows/Android.
- Board flip: TASK-LAP-005 AVAILABLE → IN_REVIEW (pr 1894) rides in
  the work PR as a follow-up commit.

## Five states

- implemented: YES (guidance docs)
- tested: PARTIAL (docs reviewed against published sources; no live
  device to run procedures on)
- merged: NO
- deployed: N/A (docs; FRIDAY behaviour change takes effect when the
  guidance is in the repo the owner reads)
- production-verified: NO (owner live use owed)
