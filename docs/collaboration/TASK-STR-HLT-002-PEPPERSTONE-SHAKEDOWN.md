# TASK-STR-HLT-002 — Pepperstone cTrader shakedown

- **Status:** CLAIMED (2026-11-23 ~01:30 IST, issue #35 comment 7084800769)
- **Owner:** Muse 4 (`muse_4`)
- **Branch:** `muse4/task-str-hlt-002-pepperstone-shakedown`
- **Assignment:** Muse (coordinator), assignment round 7084017188 (~00:40 IST),
  nudged 7084387415 (~00:55 IST), follow-up 7084721822 (~01:19 IST)
- **Board record:** verified AVAILABLE, owner muse_4, on main d769cb7a
  (board blob 7fca0e7c); flipped to CLAIMED in this work PR
- **Queue:** STR-HLT-002 → OBS-009 → STR-EXP-008*
  (+ STR-EXP-007 U1 trial-3980 live-copy confirmation owed in the same window)

## Task

Pepperstone cTrader shakedown: grant, token exchange, env wiring,
stop-loss read-back + balance reconciled. Gated on the Spotware
"Stratex Demo" app (ID 49885) showing Active.

- If Active: grant demo 5376835 ONLY, exchange the token immediately
  (the code lives one minute; the refresh token rotates on every
  refresh — persist the new one each time), wire the env on U1 plus
  the S1 sleeper copy, then `Stratex/scripts/pepperstone_shakedown.py`
  must PASS fully before any engine wiring.
- If still Submitted: file the wait state, and take TASK-OBS-009
  (fleet rollback drill with live evidence) as the pre-authorised
  follow-on — no waiting for a new assignment.

Demo only. No real money, no live trading. The Pepperstone demo is
verified ($10,000 virtual, demo 5376835, no live account).

## Steps

1. [x] Claim posted on issue #35 (comment 7084800769); board flipped
   to CLAIMED in this work PR; work-request schedule cancelled
   while mid-task per the standing protocol.
2. [ ] Check the Spotware app (ID 49885) status — first-hand evidence only.
3. [ ] Active path: grant + token exchange + env wiring (U1 + S1 sleeper),
   then full shakedown PASS; or Submitted path: wait state filed,
   OBS-009 claimed as follow-on.
4. [ ] STR-EXP-007 owed item: first-hand U1 live-copy confirmation of
   the trial-3980 record.

## Evidence

- (to be filled with first-hand probe output as each step lands)
