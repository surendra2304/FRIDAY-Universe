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

### Probe 1 — Spotware app status check (S1, 2026-11-23 ~01:40 IST)

First-hand, via the bridge (`run_shell`, Server 1); probe script
`~/workspace/muse4_strhlt002_probe1.py`, output
`~/workspace/muse4_strhlt002_probe1.json`. Names only — no credential
value was read, printed, or stored.

- S1 Stratex dir exists; `.env` exists, mode 0600, 7,366 B, 80 env names.
- **All six `PEPPERSTONE_CTRADER_*` Open API names are MISSING from the
  S1 `.env`**: `CLIENT_ID`, `CLIENT_SECRET`, `ACCESS_TOKEN`,
  `REFRESH_TOKEN`, `ACCOUNT_ID`, `ACCOUNT_NUMBER`. Only the read-only
  `CTRADER_FIX_*` names are present (7 names).
- `Stratex/scripts/pepperstone_shakedown.py` and
  `Stratex/exchanges/pepperstone_ctrader_adapter.py` are present on S1.
- No server-side file records the Spotware app status (the "49885 /
  Stratex Demo" grep hits on S1 are backtest-result JSON files, not
  app-status records).
- `bot.log` has `ctrader_autonomous_engine` bracket-log lines
  (2026-11-22 ~12:20–12:22 UTC) — engine-side logging only, not a live
  venue connection and not app-status evidence.
- Stratex service is `inactive` on S1 (sleeper copy, as expected; the
  working copy is U1).

### Wait state — filed 2026-11-23 ~01:40 IST

- **The app status cannot be verified as Active from any first-hand
  source reachable by this worker.** The Spotware developer portal
  needs the owner's cTrader ID sign-in, which this worker does not
  have and must not seek; the cTrader Open API needs the client
  id/secret + access token, none of which exist in the S1 env; no
  hub/board record since the 2026-11-21 submission states Active.
- Last recorded state stands: **Submitted, Spotware review pending**
  (2026-11-21; board evidence, main d769cb7a).
- **No grant fabricated, no token exchanged, no env wired, no
  shakedown run.** The gate stays closed.
- Caveat: the U1 (AWS Sydney) working copy's env was NOT readable —
  the bridge reaches S1/S2 only. A U1 re-check is owed when U1 becomes
  reachable; the wait state is filed on the S1 + recorded-state
  evidence above.
- Per the assignment, the pre-authorised follow-on **TASK-OBS-009**
  is taken next (separate claim + branch + PR).

### STR-EXP-007 owed item — U1 trial-3980 confirmation

- Still owed. U1 is not reachable via the bridge (S1/S2 only), so no
  first-hand U1 read was possible this run. The S1 frozen-copy record
  (trial 3980 PROVEN, all 8 frozen-bar checks true) was already
  verified live twice and filed in PR #1381 (merged).

## Steps

1. [x] Claim posted on issue #35 (comment 7084800769); board flipped
   to CLAIMED in this work PR; work-request schedule cancelled
   while mid-task per the standing protocol.
2. [x] Spotware app (ID 49885) status checked first-hand as far as
   reachable: **not verifiable as Active — wait state filed** (see
   above). No grant fabricated.
3. [ ] Re-check on Spotware approval: grant + exchange + wire (U1 + S1
   sleeper) + full shakedown PASS. This task stays open, blocked on
   the Spotware review, until then.
4. [ ] STR-EXP-007 owed item: U1 live-copy confirmation of trial-3980
   (blocked on U1 reachability).
