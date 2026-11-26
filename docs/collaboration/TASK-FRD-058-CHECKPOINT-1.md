# TASK-FRD-058 — Checkpoint 1 (scoping) — Muse TP6 — 2026-11-26 ~10:15 IST

## Claim

- Claimed 2026-11-26 ~10:15 IST, hub comment 7182957572.
- Branch `musetp6/task-frd-058-rsvp-reader` @ main `bf41a6c4` (created this run, 201).
- Board verified first-hand on main `bf41a6c4` (blob `8f96883a`): FRD-058 CLAIMED / owner muse_tp6, branch null, pr null.
- Assigned by coordinator WATCH129 (hub 7179169815): TASK-FRD-058 → Muse TP6, queue position 3. TP9 PR #1850 superseded — do not rebase it.

## Acceptance (board, main bf41a6c4)

- Source: friday package F-17 (item DcmUG0vNBEK) — RSVP (rapid serial visual presentation) speed-reading aid; no such aid exists in FRIDAY's baseline.
- Build: paste text or an article → FRIDAY presents it word by word at an adjustable words-per-minute rate in her reading surface, with pause/resume and rate control by voice or chat.
- Done = live proof: one real article read through the RSVP surface on production FRIDAY at two different rates.

## Baseline proof of absence (first-hand, GitHub code search on main bf41a6c4)

- No RSVP reader module exists on main: no `FRIDAY/src/friday/workflows/rsvp.py`, no `FRIDAY/src/friday/tools/builtin/rsvp_tools.py`, no `FRIDAY/src/friday/api/rsvp.html`.
- `rsvp` code search: exactly 1 hit — `FRIDAY/src/friday/proactive/agentic_inbox.py:93`, a phishing-phrase keyword list (`"respond by", "rsvp", "confirm your", ...`), unrelated to speed-reading.
- `rapid serial visual` code search: 3 hits, all incidental mentions (FRIDAY diary, Forge template, IntelX agent) — no implementation.
- `speed reading` code search: 19 hits, none an RSVP reader (docs mentions, motion.tsx, KDP draft, etc.).
- Board's "no such aid exists in FRIDAY's baseline" is confirmed first-hand.

## Prior attempt inventory (read-only; do not rebase)

- PR #1850 (Muse TP9, still OPEN, superseded by WATCH129): head `901265ea`, base `a759a031`. 9 files: `FRIDAY/src/friday/api/rsvp.html` (+213), `FRIDAY/src/friday/api/server.py` (+64), `FRIDAY/src/friday/tools/builtin/rsvp_tools.py` (+139), `FRIDAY/src/friday/workflows/rsvp.py` (+238), `FRIDAY/tests/test_ig_frd_058_rsvp.py` (+197), `docs/collaboration/TASK-FRD-058-BUILD-VERIFY.md` (+83), CI workflow (+1/-1), board hunk (+4/-4).
- CI on head `901265ea`: `test` job FAILURE; the other 9 runs green (incl. `contracts` success). The exact failing test is not isolated from the check summary — isolate it on the fresh branch.
- The fresh implementation follows the same shape (workflow + tools + API surface + tests + build-verify doc), written on this branch. Nothing is taken from PR #1850's branch.

## Guardrails

- No repo code executed in this run (execution-risk flag stands); scoping stayed read-only via the GitHub API. CI is the proof for the work PR.
- Free only; no credentials touched; no server moves; owner stop order (2026-11-24) still in force.

## Decision owed to Muse

- The acceptance's live leg ("one real article read through the RSVP surface on production FRIDAY at two different rates") needs production-FRIDAy access. Confirm whether the live proof runs as a gated follow-up (same shape as VYR-078 bullet-4, gated not waived) or under a clearance. Repo leg proceeds now; live leg NOT started.

## Board-text flag (no edit made here)

- FRD-058's `next_action` line names muse_tp7 / PR #1848 — that text belongs to FRD-059's record (WATCH129 re-slotted FRD-059 → Muse TP7, PR #1848 superseded). The FRD-058 owner field (muse_tp6) and its TP6 evidence line are correct. Flagged to Muse for a board-text fix.

## Next

- Checkpoint 2: fresh implementation + tests + build-verify doc on this branch, then work PR. Queue after FRD-058: VYR-087 (AVAILABLE / owner muse_tp6, queue position 2).

— Muse TP6
