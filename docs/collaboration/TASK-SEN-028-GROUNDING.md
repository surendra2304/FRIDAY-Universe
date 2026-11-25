# TASK-SEN-028 — Grounding (checkpoint 1)

**Filed:** 2026-11-26 ~04:25 IST, Muse 19 hourly self-check (stall repair —
branches carried zero commits ~1h after the ~03:20 IST claim).
**Task:** Sentinel: 7-step digital-footprint cleanup as an owner checklist
tool. **Board (main `bf5a08b7`):** AVAILABLE / owner muse_19 / branch null /
pr null. P2. Board flip AVAILABLE → CLAIMED rides in the work PR
(owner rule 4). No PR with this checkpoint (owner rule 1).

## Acceptance (board, verbatim)

- Sentinel can walk the owner through the 7 steps with per-step status:
  HIBP check (reuses TASK-IG2-INT-06), JustDeleteMe, email aliases,
  Google My Activity cleanup, YourDigitalRights.org, ExifTool metadata
  stripping, EFF Cover Your Tracks.

## Verified from the repo (main `bf5a08b7`, first-hand this run)

- **Absence proof — greenfield.** Full tree at `bf5a08b7` (7,848 blob
  paths): zero hits for `footprint`, `JustDeleteMe`, `ExifTool`,
  `Cover Your Tracks`, `YourDigitalRights`, `GAP-LIST`. No existing
  footprint-cleanup tool anywhere in Sentinel or the monorepo.
- **Source-citation gap (flagged, not blocking).** Board evidence cites
  "GAP-LIST.md section 2, TASK-SEN-FOOTPRINT-CLEAN (IG package SE-05)".
  Neither `GAP-LIST.md` nor any `TASK-SEN-FOOTPRINT-CLEAN` / `SE-05`
  record exists on main. The 7-step list in the acceptance above is the
  spec; the citation does not resolve.
- **HIBP reuse target verified — real, free-only.**
  `IntelX/intelx/osint/breach_check.py`: `check_email_breaches`,
  `check_password_breach`, `parse_range_response`. Test
  `IntelX/tests/test_ig2_int06_hibp.py` (89 lines, hermetic, injected
  fetch): Pwned Passwords range check is a real k-anonymity lookup (only
  the 5-char SHA-1 prefix leaves the machine); the email check without
  an API key reports itself `unavailable` instead of fabricating
  "no breaches". Reuse = import/call this module; it lives in the
  IntelX top-level package, so Sentinel needs it vendored or imported
  cross-package (design decision at build time).
- **Host options in Sentinel (all present on main):**
  `Sentinel/sentinel/apps/cli/main.py` (CLI), `Sentinel/sentinel/apps/api/main.py`
  (API, `:8008`), `Sentinel/apps/dashboard/` (React dashboard).
  Recommendation: **CLI walkthrough first** — owner-operated, no deploy,
  fits the stop order; API route / dashboard page later.

## Design (to be built, repo-side — startable now)

- Walkthrough: one step at a time, per-step status
  `pending | done | skipped | blocked`, with evidence + timestamp per
  step, persisted to a local JSON state file (owner machine only).
- Per-step needs:
  1. **HIBP check** — reuse `breach_check.py`; email check needs the
     owner's own HIBP API key, pasted by the owner only, never stored by
     the tool; without a key the step reports unavailable, never "clean".
  2. **JustDeleteMe** — link directory / guidance; no API, owner clicks
     through in their own browser.
  3. **Email aliases** — guidance + owner-managed alias inventory; the
     tool records which aliases exist, it does not create accounts.
  4. **Google My Activity cleanup** — guidance for the owner's own
     session; no credentials handled by the tool.
  5. **YourDigitalRights.org** — request templates (GDPR erasure) the
     owner sends themselves.
  6. **ExifTool metadata stripping** — local binary check; strips only
     on owner-selected files, with a before/after listing. No upload.
  7. **EFF Cover Your Tracks** — browser test, guidance; result recorded
     as the owner reports it.
- Privacy rules (hard): never upload owner data; never store credentials
  or API keys; never create accounts; every live check is owner-initiated
  in the owner's own session.

## Blockers (live leg — nothing attempted)

- **Live runs need clearance (owner stop order, no lift in
  WATCH120–123).** Build + tests are repo-side and proceed now; any live
  walkthrough with the owner waits on clearance.
- No account created, no server run, no owner data touched.

## Next

Build the CLI walkthrough + per-step status store + tests (HIBP reuse
first, then the six guidance steps); file the single work PR with the
tool, tests, and board flip. DB-009's backup write stays frozen;
REL-094 stays parked.

— Muse 19
