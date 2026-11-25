# TASK-SEN-026 — Tracking-pixel / open-tracking awareness inside extortion-mail triage

- **Task:** TASK-SEN-026 (P2, Sentinel lane) — "Sentinel: tracking-pixel / open-tracking awareness inside extortion-mail triage".
- **Owner:** muse_4. **Claim:** hub #1483 comment 7175442056, 2026-11-26 ~03:15 IST (correction of an initial misclaim of SEN-027 in comment 7175425880 — SEN-027 is queue pos 3, SEN-026 is pos 2; the SEN-027 claim was withdrawn in the same correction post).
- **Branch:** muse4/task-sen-026-tracking-pixel-triage, from main 614e6b1d.
- **Board:** AVAILABLE → IN_REVIEW in this PR (owner muse_4, branch stamped; pr stamped after the PR opens). MERGED flip rides in the worker's own follow-up PR after the coordinator merges, per owner order 7143628341 rule 4.
- **Acceptance:** "Triage output carries the pixel warning when an embedded remote image is present, and the calm-response guidance tells the owner not to open/load images."

## What already existed (verified first-hand on main 614e6b1d)

The SE-01 pixel work was already in the triage module, delivered with the
extortion-mail triage itself (TASK-IG2-SEN-06):

- `Sentinel/app/services/extortion_mail_triage.py` — `_has_tracking_pixel()`
  (tiny / CSS-hidden / tracking-path remote `<img>`), `tracking_pixel_present`
  signal, `tracking_pixel` flag on the verdict and in `as_dict()`,
  "Tracking pixel" section in `to_markdown()`, and the pixel-specific
  `TRACKING_PIXEL_GUIDANCE` line appended to guidance when a pixel is present.
- `Sentinel/tests/test_ig2_sen_extortion_mail_triage.py` — SE-01 tests:
  1x1 pixel detected and explained, tracking-path image at normal size
  counts (and never manufactures an extortion verdict on its own),
  ordinary remote image is not a pixel. Baseline on main: 9 passed.

So acceptance clause 1 (pixel warning in triage output) was already met
and tested. The claim was still correct work: the board record was
AVAILABLE/owner muse_4 with no branch or PR, and clause 2 had a real gap.

## The gap (clause 2)

The base calm-response guidance (`DO_NOT_PAY_GUIDANCE`, given on every
extortion verdict) said "do not click links or open attachments" but said
nothing about opening the message again or loading its images. The only
image instruction was the pixel-specific line, appended only when a pixel
was detected AND the mail was extortion. An extortion mail whose pixel
evades detection (hidden in an attachment, or a tracking image the
heuristics miss) gave the owner no instruction about images at all.

## Change (this PR)

- `Sentinel/app/services/extortion_mail_triage.py`:
  - New standing line in `DO_NOT_PAY_GUIDANCE`: "Do not open this message
    again or load its images: each open or image load can tell the sender
    this address is live and being read. Keep remote images blocked in your
    mail client." Applies to every extortion verdict, pixel or not.
  - Docstring note recording the SEN-026 rationale.
- `Sentinel/tests/test_ig2_sen_extortion_mail_triage.py`: two new tests.
  - `test_calm_guidance_warns_against_opening_and_loading_images_without_pixel`
    — extortion mail with no pixel still carries the do-not-open /
    do-not-load-images line, and no pixel-specific line.
  - `test_pixel_mail_carries_both_warnings` — mail with a pixel carries
    both the base line and the pixel-specific line, and the markdown
    carries both the pixel warning and the new line.
- `.github/workflows/friday-universe-ci.yml`: the triage test file was
  collected by NO PR-triggered workflow (REL-068 `--full`: UNCOLLECTED),
  so the SE-01 pixel tests had never run in PR CI. Added to the Sentinel
  tier-1 list (SEN-030 precedent).

## Verification (local, first-hand)

- Triage file: **11 passed, 0 failed** (9 baseline + 2 new).
- Sentinel tier-1 list as wired (4 pre-existing files + triage file):
  **37 passed in 1.53s, 0 failed** (venv from `Sentinel/requirements.txt`
  + pytest + pytest-asyncio, mirroring the CI job).
- REL-068 collection guard: verified with `--full` — the triage test file
  no longer appears in the uncollected list (covered count 440, up from
  439); the diff-scoped check in CI will see it named in the
  PR-triggered friday-universe-ci.yml tier-1 list.
- `py_compile` clean on the edited module; workflow YAML parses
  (see below).
- No signature or behaviour change to `triage_email` besides the one
  added guidance line; existing tests untouched and passing.

## Live leg

The triage module is a library — no endpoint, no deployed surface — so
there is no live leg to run for this change. Its live behaviour on S1 was
already proven by the SEN-032 live-probe driver
(`Sentinel/scripts/sen032_live_probes.py`, which imports and runs
`triage_email` on the corpus scenario text; S1 run 2026-11-25). The added
line changes guidance text only and is verified by the unit suite above.
No fleet action was taken in this run (owner stop order in force, no
coordinator clearance sought or needed for a library-only change).

## Queue

Next in the assigned queue after SEN-026: TASK-SEN-027 (family
secret-phrase anti-impersonation practice, queue pos 3) — to be pulled in
the SEN-026 completion post per owner order 7143628341 rule 5, once this
PR merges.

— Muse 4
