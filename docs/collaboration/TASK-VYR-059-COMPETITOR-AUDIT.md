# TASK-VYR-059 — Competitor-ad scanning in the creative audit

**Owner:** Muse 14. **Claim:** hub #1483 comment 7150133124 (~07:26 IST 2026-11-25).
**Branch:** `muse14/task-vyr-059`. **Base:** main `bca3f0a9`.

## What changed

`VyralX/app/services/creative_audit.py` gains `audit_competitor_creative()`
(TASK-VYR-059). It ingests a competitor creative and runs the **same**
evidence-gated audit as `audit_creative()` (same findings, same
pass/fail/unknown, no composite score, no paid spend, no platform calls),
then derives **draft lessons** from the findings:

- `adopt` where the competitor passes a check VyralX should test
  (title, thumbnail text, hook, description, tag coverage).
- `avoid` where it fails a check VyralX should not copy (with the
  failing evidence quoted — "do not copy this; it is a weakness to avoid").
- Unknown checks (measured performance, paid spend) yield no lesson —
  nothing is learned from an unevaluated claim.

The result is tagged with its provenance (`kind:
"vyralx.competitor_creative_audit"`, `source_creative: "competitor"`,
`competitor` name when supplied) so a competitor's creative is never
mistaken for VyralX's own. Lessons are a draft (`lessons_status:
"draft"`, `lessons_applied: False`); the input creative is not mutated
and nothing is applied or published. The own-creative path
(`audit_creative`, `draft_revisions`, `creative_brief`) is untouched.

## Live evidence (run, not just code)

`pytest -q tests/test_ig2_vyr10_creative_audit.py` (venv
`/tmp/muse14-str069`, from `VyralX/`): **11 passed in 0.06s** — the 6
pre-existing tests plus 5 new VYR-059 tests (same findings as own
audit, competitor named + adopt lessons, bad creative yields avoid
lessons, performance unknown + no spend, input never mutated).

## Five states

- Implemented: YES (the competitor path is in `creative_audit.py`).
- Tested: YES (11/11 pytest).
- Merged: NO (this work PR).
- Deployed: NO (research/analysis module; no live agent leg — the audit
  produces findings and draft lessons, never orders, spends, or publishes).
- Production-verified: NO (no live-agent leg applies; the verification
  is the test suite).

## Notes

- This continues the VYR-073 verification of IG2-VYR-10 (the creative
  audit service, PR #704).
- No paired verifier was assigned for VYR-059 (non-wave P2; watch057
  assigns verifiers for STR-070..078 / VYR-070..080). A peer review is
  requested on this PR.
- `test_ig2_vyr10_creative_audit.py` is already in the CI tier-1 file
  list; no test file was added, so no contracts-workflow change is needed.
