# TASK-INT-052 — FotoForensics ELA image check in the IntelX OSINT source kit

- **Worker:** Muse 7
- **Claim:** hub #2045 comment 7236489612 (2026-11-28 ~13:48 IST), branch
  `muse7/task-int-052-fotoforensics-ela`
- **Assignment:** WATCH263 §C (hub 7236357595) + BE 13:45 §B (hub 7236383505),
  adopted in WATCH264 (hub 7236513660). Execution route ruled in the WATCH264
  addendum (hub 7236522800): author the check, open the work PR, and let CI
  run the tests — the CI run is the test leg.

## Task (board record, main `610eccaa`)

- Source: intelx package X-09 (the FotoForensics image-forensics reference,
  item DaXwbFrDEuX, inside the awareness-only OSINT set) — the set's one
  defensive, adoptable item: error-level analysis for checking whether an
  image has been edited. The rest of X-09 (dark-web OSINT carousels and
  attack-technique items) is NOT adopted.
- Build: add FotoForensics ELA as a named check in IntelX's OSINT source kit,
  with a recorded reading guide (what ELA can and cannot prove).
- Done = one real image checked through the kit with its ELA verdict recorded.

## What shipped in this PR

- `IntelX/intelx/osint/image_ela.py` — the named check `fotoforensics_ela`:
  - `check_image_ela(data)` / `check_image_file_ela(path)` re-save the JPEG
    at quality 90, measure per-block (16px) mean absolute error, and flag
    blocks whose error is an outlier against the image's own distribution
    (> mean + 3σ and ≥ 2× mean).
  - Verdicts: `consistent` / `suspicious_regions` /
    `whole_image_heterogeneous` / `inconclusive` (non-JPEG, flat, or
    < 64px input) / `unavailable` (Pillow missing, `checked=False` — never
    reported as a clean image). Undecodable input raises `ValueError`.
  - `READING_GUIDE` is recorded in the module and carried in every result's
    `to_dict()`: what ELA measures, what it can show, what it cannot prove
    (not proof of editing; a consistent verdict is not proof of
    authenticity), how to read hot blocks, and the verdict meanings.
- `IntelX/intelx/osint/__init__.py` — exports `ImageElaResult`,
  `check_image_ela`, `check_image_file_ela`, `ela_reading_guide`.
- `IntelX/tests/test_int052_image_ela.py` — 8 hermetic tests. The done
  criterion is exercised directly: one real JPEG file (256×256 textured
  base, seed 7, with a never-JPEG-compressed checkerboard patch spliced at
  96,96) is written to disk and checked through `check_image_file_ela`;
  its recorded verdict is `suspicious_regions` with hot blocks overlapping
  the spliced region. A uniform-history JPEG of the same base records
  `consistent` with no hot blocks. PNG, flat, and 32px inputs record
  `inconclusive`; undecodable/empty input raises.
- `IntelX/requirements.txt` + `IntelX/pyproject.toml` — `Pillow>=12.3.0`
  (fleet floor per `FRIDAY/requirements.txt`), imported lazily so IntelX
  still starts on a host without it.
- `.github/workflows/friday-universe-ci.yml` — the new test file joins the
  IntelX tier-1 list, so CI collects it (the uncollected-test failure mode
  of FUT-030 / PR-936 does not recur).

## Test leg

Per the WATCH264 addendum ruling, CI is the test leg for this task: the
IntelX tier-1 job installs `IntelX/requirements.txt` (now including
Pillow) and runs `tests/test_int052_image_ela.py`. The CI outcome on this
PR's head is the test evidence; it is recorded on the hub completion post
and in this file's PR thread once the run finishes. No local test run is
claimed.

## Five states

- implemented: YES (this PR)
- tested: CI tier-1 run on this PR (see test leg above)
- merged: NO (coordinator merges)
- deployed: NO
- production-verified: NO — no live IntelX leg is claimed; the kit check
  is verified by its CI test leg, and production verification requires
  the merged code running on IntelX-Server, which is post-merge work.
