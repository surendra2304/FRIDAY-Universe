# TASK-WEB-004-FOLLOWUP-01 — owed legs evidence — 2026-11-28 — Muse 7

Claim: hub #2045 comment 7230248076 (2026-11-28 05:04 IST), per Burn
Enforcer 05:05 §B pre-stage (hub 7230217309), adopted by the WATCH246
correction (hub 7230255962). Branch:
`muse7/task-web-004-followup-01-owed-legs` from main `ff5806b2`.

Task: run the WEB-004 owed legs live on
`https://friday-universe.duckdns.org/halo` as a visitor — mobile
viewport, slow-network, reduced motion, localStorage clear,
zero-network — with per-leg pass/fail evidence. Source of the owed
legs: TASK-WEB-004 evidence (PR #2184) and Muse 17's re-verdict
(review 6093585761).

## Live run

- Browser task `browser-task:f15dd48c-b102-5d5d-a5e1-ba0a09e43e2f`,
  ran 2026-11-28 05:06–05:09 IST (harness-measured).
- Visitor only: no sign-in, no messages sent, no server changes.
- Actual viewport throughout: desktop 1919×998.

## Gate: /halo serves the Halo stage — PASS

Title "FRIDAY — Halo"; FRIDAY wordmark/orb rendered; "Everything
else" summon pill present; "Fleet at a glance" present with live
fleet status buttons. The veil opened; the Fleet sheet opened and,
after its loading state, showed "5 of 9 answering"; the
Life-in-weeks sheet opened. This was the Halo stage, not a 404,
unreachable page, or Ultron shell.

## Leg results

| Leg | Verdict | Evidence |
|---|---|---|
| Mobile viewport ~390×844 | NOT RUN | No viewport-resize / device-emulation control was available; only the desktop 1919×998 viewport was used. Mobile overflow and control reachability were not tested and are not claimed. |
| Slow-network load | NOT RUN | No network-throttling control was available; no throttling was applied and no throttled time-to-usable was measured. Normal-load renders were observed only for the gate/baseline. |
| Reduced motion | NOT RUN | No `prefers-reduced-motion` emulation control was available; emulation was not applied, so Fleet-sheet animation/stagger and showcase rotation under reduced motion were not tested. |
| localStorage clear failure case | NOT RUN | No localStorage key-inspection or origin-only clear control was available, so key names could not be recorded and storage was not cleared. Baseline only (below); the post-clear empty state remains unresolved, so PASS is not claimed. |
| Zero-network claim | NOT RUN | Network requests were not observable (no network log/clear/segment control), so sheet actions could not be verified as triggering zero requests. No network claim is made. |

### localStorage baseline (not the clear leg)

The Life-in-weeks sheet first showed an empty birth-date field.
Birth date was set to `1990-01-01`; the grid showed 1,925 weeks
lived / 41.1%. A mark "1 Jan 1990 — Probe mark" was added; after a
page reload and re-opening the sheet, the birth date and the mark
persisted. This confirms the persistence baseline only. Because the
clear step could not be run, the empty-state failure case (no birth
date, no marks, no crash, no invented birth date) is unverified.

## Verdict: BLOCKED — acceptance not met

The gate passed and the persistence baseline was observed, but none
of the five owed legs could be run: the available browser tooling
exposes no viewport emulation, network throttling, reduced-motion
emulation, network-request observation, or localStorage
inspection/clear controls. These legs need a browser harness that
exposes those controls to reach PASS/FAIL. No leg is marked verified
on the gate or baseline evidence.

## Five states (TASK-WEB-004-FOLLOWUP-01)

- implemented: N/A (verification task; this evidence doc is the
  filed artifact)
- tested: PARTIAL (gate + persistence baseline only; five owed legs
  NOT RUN)
- merged: NO (this PR)
- deployed: YES (Halo stage live on production — gate passed)
- production-verified: NO (owed legs unresolved)

— Muse 7
