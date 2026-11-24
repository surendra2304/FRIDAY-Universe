# TASK-STR-HLT-002 — Pepperstone cTrader shakedown

- **Status:** CLAIMED (2026-11-25 ~04:40 IST, hub issue #1483 comment 7147144715 — re-slot from Muse 4)
- **Owner:** Muse 13 (`muse_13`)
- **Branch:** `muse13/task-str-hlt-002`
- **Assignment:** Muse (coordinator), watch 7146822886 (run scheduled 2026-11-25 03:57 IST, started ~04:12 IST) — re-slot as Muse 13's next head. Verifier: M8. Original assignment: assignment round 7084017188 (~00:40 IST, 2026-11-23), Muse 4.
- **Board record:** verified IN_REVIEW, owner muse_4, pr 1413, on main 8aea4275
  (board blob 28a88e4e, 969 tasks, 0 dup ids); flipped to CLAIMED in work PR #1744.
  M4 live-work check: PR #1413 CLOSED + MERGED (2026-11-22T20:08:43Z) — no live work on it.
- **Queue:** STR-HLT-002 → VOI-030 (blocked, no calm-window call) → next pool task.
  (OBS-009, the pre-authorised follow-on, is MERGED — work PR #1438, 2026-11-23.)

## Task

Pepperstone cTrader shakedown: grant, token exchange, env wiring,
stop-loss read-back + balance reconciled. Gated on the Spotware
"Stratex Demo" app (ID 49885) showing Active.

- If Active: grant demo 5376835 ONLY, exchange the token immediately
  (the code lives one minute; the refresh token rotates on every
  refresh — persist the new one each time), wire the env on the live
  host (Stratex-Server, server 4 — U1/U2 were deleted 2026-11-23 ~18:09 IST
  on the owner order; the S1 copy is the sleeping backup) plus the S1
  sleeper copy, then `Stratex/scripts/pepperstone_shakedown.py`
  must PASS fully before any engine wiring.
- If still Submitted: file the wait state; the pre-authorised follow-on
  TASK-OBS-009 is already MERGED (work PR #1438), so no follow-on is
  taken — the head stays blocked and the worker reports FREE, requesting
  work, per the blocked-head rule.

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

### Re-check 2 — Muse 13, 2026-11-25 ~04:45 IST (re-slot claim)

First-hand, via the bridge (`run_shell`, Server 1 + Server 2). Names only —
no credential value was read, printed, or stored.

- S1 `/opt/friday_universe/.env` exists, mode 0600, **517 B, 7 env names**:
  `ALPACA_API_KEY_ID`, `ALPACA_API_SECRET_KEY`, `TELEGRAM_BOT_TOKEN`,
  `TELEGRAM_CHAT_ID`, `TELEGRAM_WEBHOOK_SECRET`, `TELEGRAM_WEBHOOK_URL`,
  `TELEGRAM_ZAI_NOTIFICATION_BOT_TOKEN`. (Probe 1, 2026-11-23, saw 7,366 B /
  80 names — the S1 sleeper env has been cut down since; observation only,
  no live impact: S1 is the sleeping backup.)
- **Still zero `PEPPERSTONE_CTRADER_*` names on S1** (count 0 of 7).
  No `CTRADER_FIX_*` names either in the current 7-name file.
- `Stratex/scripts/pepperstone_shakedown.py` (14,871 B) and
  `Stratex/exchanges/pepperstone_ctrader_adapter.py` (59,949 B) present on S1.
- S1 `Stratex-Daemon.service`: **failed** (Result: timeout) since Tue
  2026-11-24 13:42:26 IST — the sleeping backup, as established in the
  STR-049 correction; the live daemon runs on Stratex-Server (server 4).
- Server-4 env check **NOT done — route failed, exact error**:
  `ssh ubuntu@13.211.78.20` from Server 2 returns
  `Permission denied (publickey)`, exit 255. No other route improvised;
  the server-4 re-check is owed when the ssh key access is restored.
  (The S2 → server-4 read-only route was proven by Muse 15 / Muse 5 and
  cleared by coordinator ruling 7138466832 §3; the key that made it work
  no longer authenticates from S2.)

### Wait state — re-filed 2026-11-25 ~04:45 IST

- **Gate still closed.** No hub/board record since the 2026-11-21 submission
  states the Spotware app Active; no `PEPPERSTONE_CTRADER_*` credential
  names exist on the reachable S1 copy; the live host (server 4) could not
  be re-checked (ssh auth, above).
- **No grant fabricated, no token exchanged, no env wired, no shakedown run.**
- Head stays blocked on the Spotware review. Next: re-check on approval;
  worker reports FREE, requesting work, per the blocked-head rule.
- Owner stop order still in force for live legs (latest watches: M17
  dep-install clearance notes the live demo-daemon leg stays gated;
  M14 VYR-073 + M12 INT-042 live legs blocked).

### STR-EXP-007 owed item — superseded

- U1/U2 were deleted 2026-11-23 ~18:09 IST on the owner order, so a U1
  live-copy confirmation is no longer possible as specified. Superseded by
  TASK-STR-049 (merged, PR #1717): the live trial counter now sits on
  Stratex-Server and trial 3989 was proven from it (full frozen bar).
  No further action on this item from this task.
