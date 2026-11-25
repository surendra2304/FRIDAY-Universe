# TASK-LAP-005 — Evidence

**Task:** Laptop/phone guidance additions bundle: USB TOOLS route +
recovery escalation, Autopsy mention, WinSAT probe caveat,
invisible-folder procedure, NetLimiter reference, DROIDLAB guide,
BIOS cores step, services.msc verify-first evaluation.
**Worker:** Muse 15. **Claimed:** 2026-11-26 ~02:09 IST (hub comment
7173987632, WATCH117 assignment 7173839964). **Branch:**
`muse15/task-lap-005-laptop-phone-guidance-bundle` from main
1fa527bd. **Type:** docs-only guidance additions; FRIDAY behaviour
change (what FRIDAY tells the owner), no code, no deploy.

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

| # | Item | Grounded against | Result |
|---|---|---|---|
| 1 | USB TOOLS route + recovery escalation | Repo's existing corrupted-USB flow in `docs/PC_CARE.md`; rescue-USB pattern (Ventoy + free recovery ISO, e.g. Hiren's BootCD PE); PhotoRec/TestDisk free + open source | Route documented as an escalation ladder, read-only first, never write to the failing card. No specific source-video ID was in the board record (see gap note). |
| 2 | Autopsy mention | sleuthkit.org/autopsy (free, open source, GUI front-end to The Sleuth Kit; PhotoRec carving engine; NTFS/FAT/exFAT/ext/HFS; works on disk images read-only) | Mentioned as the GUI route once a disk image exists; heavyweight, image-only, owner-owned drives only. |
| 3 | WinSAT probe caveat | Microsoft Learn (WinSAT config scores doc); itechguides/mefmobile WinSAT explainers | Legacy tool, `winsat formal`, AC power only, not on battery, D3DScore not a modern benchmark, API may change after 8.1, never benchmark a failing drive. |
| 4 | Invisible-folder procedure | `attrib +h +s` / `-h -s` (standard Windows behaviour) | Procedure given with the honest caveat: obscurity, not security; BitLocker/VeraCrypt for real privacy. |
| 5 | NetLimiter reference | netlimiter.com (Windows only, 28-day trial); independent reviews (exedepot, rottenwifi) | Price stated plainly: trial then paid yearly licence (from €19/year/PC); Restricted Mode after trial. Built-in free check (Task Manager / resmon) offered first per the FREE-ONLY rule. |
| 6 | DROIDLAB guide | AppBrain Play Store listing (DroidLab: Gesture Toolkit, Light Source Labs, free, Android 8.0+); Softonic description; Facebook reel 1412796127460354 (Moonxfinds, 2026-09-19) showing the back-tap flashlight demo | Guide: Calibration Wizard first, Accessibility permission (system "danger" prompt is normal), check for a built-in gesture first, never map destructive actions. |
| 7 | BIOS cores step | Standard Windows/BIOS behaviour (`msconfig` Boot > Advanced options "Number of processors"; BIOS "Active Processor Cores" / "Core Multi-Processing") | Windows check first, BIOS second, photograph-before-change warning, never touch voltage/overclock. |
| 8 | services.msc verify-first | Standard Windows behaviour (services.msc Description + Dependencies tabs) | Manual-not-Disabled first, one change at a time, never bulk-disable from a list. |

## Grounding gap (stated, not hidden)

The board record's evidence says the items were "filed by Muse
(coordinator) 2026-11-25 in the Instagram adoption re-audit, batch 3"
with "source package/watch records read first-hand in the re-audit" —
but that re-audit package is not in this workspace
(`~/workspace/ig-references/` does not exist here; no LAP-005 source
doc found in the repo). Each item above is therefore grounded against
the tool's own published documentation instead of the re-audit's
source video. If the coordinator holds the source video IDs, the
evidence doc can cite them in a follow-up; nothing in the guidance
depends on a video ID.

## Verification status

- Docs only: no code changed, no tests added (nothing executable to
  test), no deploy, no live device involved.
- The owner's laptop is **not connected** (same standing caveat as
  `docs/PC_CARE.md`), so no item was verified on a real machine.
  Every procedure is written verify-first / read-only-first so it is
  safe to follow as written.
- No paid service recommended as free: NetLimiter's price is stated;
  every other item is free or built into Windows/Android.
- Board flip: TASK-LAP-005 AVAILABLE → IN_REVIEW rides in the work
  PR (pr number filled at PR open).

## Five states

- implemented: YES (guidance docs)
- tested: PARTIAL (docs reviewed against published sources; no live
  device to run procedures on)
- merged: NO
- deployed: N/A (docs; FRIDAY behaviour change takes effect when the
  guidance is in the repo the owner reads)
- production-verified: NO (owner live use owed)
