# TASK-SEN-031 — Checkpoint 1: scoping + live-leg plan (PRODUCTION-VERIFY, wave 3)

**Worker:** Muse 12 · **Date:** 2026-11-25 ~19:05 IST · **Base:** main `f216e1b`
(board blob `9e87efb4`, 2,890,931 bytes)

## Claim

Queue head per WATCH093 (SEN-030 → SEN-031) and WATCH100 (queue SEN-031 →
EARN-005 → SEN-034). Board verified on main `f216e1b`: SEN-031 AVAILABLE /
owner muse_12 / branch null / pr null. Branch
`muse12/task-sen-031-production-verify-wave3` @ `f216e1b`. Hub claim in this
run's status post on issue #1483.

## Items and what exists on main (verified first-hand)

- **IG-SEN-01 — attacker-view audits (TASK-IG-SEN-01):**
  `Sentinel/sentinel/modules/attacker_view/` (`models.py`, `audit.py`,
  `__init__.py`) + `Sentinel/tests/unit/test_ig_sen_attacker_view.py`
  (GitHub code search, main). Live check: run the attacker-view audit
  against the real surface; file what ran, where, with what result,
  including the failure case.
- **IG-SEN-02 — device & credential posture (TASK-IG-SEN-02):**
  `Sentinel/sentinel/modules/endpoint/device_posture.py` — extended by
  SEN-030 (DP-012 Private DNS + DP-013 resolver hygiene, work PR #1822
  merged `a573cd36`, CI 10/10 green). Live check: run the posture
  evaluator on the live owner device through the real approval path (one
  low-risk auto-approve + one high-risk Telegram prompt, each exactly
  once, per the board acceptance).
- **IG-SEN-03 — Telegram threat-intel watch (TASK-IG-SEN-03):**
  `Sentinel/sentinel/integrations/threat_feeds/telegram_channels.py` +
  `Sentinel/tests/unit/test_ig_sen_telegram_watch.py` (GitHub code search,
  main). Live check: live threat-feed watch run against the real Telegram
  channels; approval path exercised if the item touches it.
- **IG-SEN-04 — Instagram corpus pass reference (TASK-IG-SEN-04):**
  `Sentinel/docs/SECURITY_REFERENCE_IG.md` (read in full, 13,688 bytes) —
  reference-only document, no code, no live surface of its own. Live
  check: none applicable as a live run. Honest note: this item may close
  as reference-verified rather than live-verified; if the acceptance's
  "live evidence per item" is read strictly, a ruling is owed from Muse
  on its disposition. Not marked verified here.
- **IG2-SEN-01 — defensive skills (TASK-IG2-SEN-01):**
  `Sentinel/app/services/defensive_skills.py` +
  `tests/test_ig2_sen_defensive_skills.py` (GitHub code search, main).
  Live check: run the defensive-skills service in the live agent on a
  real task.

## Block — live legs NOT run

Owner stop order still in force: no lift in any watch through WATCH100
(`7163804244`, read in full this run). WATCH099: "Live leg NOT run —
clearance owed" (SEN-032). WATCH100: fleet CD still broken, no action.
No SEN-031-specific clearance exists. No live run attempted, no Telegram
prompt sent, no approval-path exercise. Next: checkpoint 2 = the live
legs, the moment Muse clears SEN-031 (or the stop order lifts).

## Queue behind

- **EARN-005 (pos 2):** still blocked on product identity — grounding on
  main (`earning/TASK-EARN-005-GROUNDING.md`, PR #1645 merged): the $19
  product cannot be identified from board, repo, or any coordinator
  watch; owner answer owed since 2026-11-24 ~12:20 IST, none arrived
  (no owner answer in any watch through WATCH100, no answer in memory).
  No copy written — inventing a product is not the work.
- **SEN-034 (pos 3):** assigned by WATCH100; flip rides in coordinator
  board PR #1844 (open, CI running) — not flipped here.

## Status

Checkpoint 1 filed in this work PR. Board flip AVAILABLE → CLAIMED rides
in this PR.

— Muse 12
