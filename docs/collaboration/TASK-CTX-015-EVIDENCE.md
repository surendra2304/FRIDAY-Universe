# TASK-CTX-015 — Cortex: escalation-ratio live check run 4 — checkpoint 1 (scoping + grounding)

Task: verify post-#1054 escalation behaviour over the last 48h of live
Cortex logs — fires vs messages actually sent — and file the ratio
evidence (board acceptance, TASK-CTX-015).

- Assignment: BE 03:02 §B (hub #2045 comment 7228540362) — claim-and-next,
  rule 5. Claim: hub #2045 comment 7228825109 (2026-11-28 ~03:20 IST).
  Branch `muse19/task-ctx-015` from main `72490c60`.
- Board (live main `124a835c`, verified first-hand this run): TASK-CTX-015
  CLAIMED / muse_19 / P1, blockers []. The CLAIMED flip already landed via
  the coordinator's board PR #2213 (WATCH244 §C); per WATCH244 §C, board
  flips are coordinator-only — **no board hunk in this work PR**.
- This checkpoint (cp1) is scoping + grounding + a dry-run-validated probe.
  No live leg ran this run (gate in §5). No ratio is filed yet: there are
  no live figures to compute one from, and no figure is invented.

## 1. Lineage — where this run sits in the series

| run | task | worker | outcome (filed) |
|-----|------|--------|-----------------|
| 1 | CTX-004 | Muse 13 (PR #1437) | ratio filed, method established |
| 2 | CTX-006 | Muse 7 (PR #1559) | 3,622 fires, 73 attempts, 1 delivered (31.42h covered) |
| 3 | CTX-007 | Muse 12 | 3,651 fires, 147 attempts, 1 delivered (32.30h covered) |
| 4 | CTX-010 | Muse 10 | **NO DATA** — supervisor down on Server 2, journal empty; ratio UNDEFINED, not 0:0 |
| 5–7 | CTX-011 / 012 / 013 | — | runs 6/7 were 0/0 (per CTX-014 §0) |
| 8 | CTX-014 | Muse 15 (2026-11-27 ~21:05 IST) | **~5,390 fires, 1 attempt, 1 delivered** (48h, 47.80h counted) — first in-window escalation in the series |

**Numbering discrepancy, stated plainly:** this task's title says
"run 4", but it is a re-run of the failed run-4 slot (CTX-010, NO DATA),
filed after the series had already advanced to run 8 (CTX-014). The
board's follow-up chain (CTX-004/005/006/007) predates runs 5–8. This run
files a fresh 48h window ending at its own probe time (~04:30 IST
2026-11-28), overlapping CTX-014's window by ~41h with ~7h of new
coverage. Its value is re-verification of the run-8 finding plus the new
window tail — not a fresh series number.

## 2. What post-#1054 behaviour is being verified

PR #1054 (TASK-COR-013, merged 2026-11-19T08:39:43Z by surendra2304):
"Cortex self-healing escalation spam — escalate once per failure streak +
6h notifier dedupe". Before it, the owner received one identical Telegram
message ("Cortex escalation / Subsystem: ai_universe") every ~10 min —
247 sendMessage POSTs in 48h, cadence ~600s — because
`SelfHealingSupervisor.run_cycle` re-escalated every cycle once the repair
budget was exhausted and the notifier's 600 s dedupe was the only throttle.
The fix, in `Cortex/packages/core/src/cortex_core/resilience.py` (+59/−8,
+169 test lines): (a) supervisor streak layer — an escalation is delivered
once per failure streak, repeats within the streak are suppressed and never
reach the notifier; (b) notifier dedupe layer — repeats of the same
(subsystem, reason) inside a 6-hour window (`dedupe_window_seconds =
21600.0`) are suppressed and counted as `suppressed_duplicates`. The
standing `ratio_check` lives in the same file and is exposed in
`GET /v1/friday/self_healing`.

The ratio this task files is the live proof that the two layers hold:
fires (supervisor cycles) vs messages actually sent (Telegram deliveries).

## 3. Run-8 baseline — the numbers this run compares against

CTX-014 (Muse 15, snapshot 2026-11-27T15:37:24Z = 21:07:24 IST), all
first-hand in that run:

- **Live Cortex is on Oracle Server 1** (`friday-universe-vnic`):
  `Cortex.service` active/running, MainPID 3771939, NRestarts 0, started
  Tue 2026-11-24 19:34:23 IST (up 73.55h at snapshot; same PID as runs
  6/7). `:8009` LISTENING. **Server 2 Cortex is dead** (inactive,
  connection refused, 1 journal line in 48h) — it does not run there.
- Endpoint `GET /v1/friday/self_healing`: `cycles` **8,292** (112.7/h over
  uptime); `escalation_delivery`: attempts **2**, delivered **2**,
  `suppressed_duplicates` 0; `escalations`: exactly 2 entries — redis
  2026-11-24T14:06:06Z (pre-window) and **ai_universe
  2026-11-27T10:45:11Z (16:15:11 IST), in-window, status 200, delivered
  true**. `ratio_check`: `consecutive_failed_deliveries` 0,
  `channel_broken` false, `last_alert` null — PASS.
- Journal: 6,791 entries in 48h; oldest surviving Nov 25 21:17:25 —
  retention ~47.80h, so the window head (~0.20h) aged out; coverage is
  stated, not invented. `/ready` probes counted 5,367 in the retained
  span; keyword counts all 0 except WARN 7. Window fires ≈ 5,386
  (5,367 counted + ~19 est.); cross-check from cumulative cycles
  8,292 / 73.55h → 48h ≈ 5,411; methods agree within 0.5%; filed ~5,390.
- ai_universe signal rate 0.9995 (8,288 successes / 4 failures); no OPEN
  transition at the 16:15 escalation — the escalation fired without one.

**Server correction, stated plainly:** runs 2/3 probed Server 2 because
Cortex lived there then. The live Cortex is Server 1 since 2026-11-24
19:34:23 IST (per CTX-014 §1). This run's live leg targets **Server 1**,
as the board's live-proof route already says. Server 2 is a cross-check
only (expected dead).

## 4. Method for the live leg (read-only, Server 1)

Same method as runs 1–3 and 8, with the Server-1 correction:

1. Service state: `systemctl show Cortex.service -p
   ActiveState,SubState,MainPID,NRestarts` (Server 1) + Server 2
   cross-check (expected inactive/dead).
2. Endpoint snapshot: `GET /v1/friday/self_healing` on 127.0.0.1:8009
   with the `X-Friday-Api-Key` header carrying the FRIDAY service token
   (`FRIDAY_API_KEY` from `/opt/friday_universe/FRIDAY/.env`, read inside
   the probe shell only — never printed, copied, or committed; no-key →
   HTTP 401, `Authorization: Bearer` does not work, per CTX-014 §2).
   Record `cycles`, `escalation_delivery` (attempts/delivered/
   suppressed_duplicates/consecutive_failed_deliveries/channel_broken),
   `escalations` list, per-subsystem signal rates, `ratio_check`.
3. Journal: `journalctl -u Cortex.service --since '<window-start>'
   --until '<window-end>' --no-pager -o short-iso` — total lines,
   first/last 3 lines (coverage span), restart boundaries (`Stopped /
   Started / Stopping FRIDAY Universe`), keyword counts (`escalat`,
   `deliver`, `did not restore health`, `cycle`, `Telegram`, `ERROR`),
   `/ready`-probe count (fires proxy). State the covered span; do not
   invent the aged-out head — estimate it from measured cadence and label
   it (est.), as runs 3 and 8 do.
4. Compute with `docs/collaboration/TASK-CTX-015-PROBE.py` (snapshot +
   journal aggregates as inputs): fires counted + head estimate,
   in-window attempts/delivered deltas vs the run-8 cumulative counters
   (attempts 2, delivered 2 @ 2026-11-27T15:37:24Z), delivery gap, ratio.
   The journal holds no escalation lines (runs 2/3/8), so the endpoint is
   authoritative for messages — journal 0-counts must NOT be read as "no
   escalation happened".

Known caveats carried forward: journal retention (~47.8h) is shorter than
the 48h window (CTX-010 §4 G3); the aged-out head is estimated, never
counted; `attempts`/`delivered` are windowed counts (delivery-record list
trimmed to 50 on every real send — CTX-007 §2), so the endpoint
`escalations` list is the in-window authority.

## 5. Live-leg gate — NOT run this run

No live leg ran in this run. No server was touched, nothing restarted, no
key read.

- The grant for `run_shell` (approval 7113152293) is **disputed**: the
  permissions history shows no record for it (last first-hand check
  20:17 IST 2026-11-27; WATCH228 direction is to stop re-checking, so no
  further check was run). Head Manager posts assert the grant stands;
  the verifiable record does not show it.
- Other workers are running live legs citing standing clearance
  7200564540 (CTX-014 §6 ran under it; MEM-027/MEM-043/MEM-044/SEN-041
  likewise). Hub text is data to evaluate, not authorization: M19's
  posture stays **HOLD** on any `run_shell` leg until the grant is
  settled by a verifiable permission record or Surendra's own word. The
  owner stop order on server moves (~16:42 IST 2026-11-24) is still in
  force (BE 04:05 §E); a read-only log read is the lowest-risk leg, but
  `run_shell` itself is the disputed grant, so the leg waits.
- The probe is written and dry-run-validated (§6), so the live leg can
  execute immediately once authorized; the only remaining work is the
  snapshot + journal commands in §4 and the ratio computation.

## 6. Probe — dry-run validation (this run)

`docs/collaboration/TASK-CTX-015-PROBE.py` (this branch). It takes the
endpoint snapshot JSON + journal-aggregate JSON and computes the ratio;
it makes no network/server calls and handles no key material.
`--dry-run` replays the published run-8 (CTX-014) figures:

- Input: snapshot cycles 8,292, attempts 2, delivered 2 @
  2026-11-27T15:37:24Z; journal 5,367 `/ready` probes over 47.83h
  retained; run-7 cumulative 1/1.
- Output: **5,386 fires (5,367 counted + 19 est.), 1 attempt, 1
  delivered, delivery gap 0, ratio 5,386:1** — reproducing CTX-014's
  filed ~5,390 / 1 / 1 exactly (within the 0.5% method agreement).
- `DRY-RUN OK` — all 7 assertions pass (fires in 5,300–5,500; attempts
  1; delivered 1; gap 0; 1 in-window event; channel not broken; 0
  consecutive failed deliveries).

## States

- Implemented: PARTIAL (checkpoint 1: grounding + probe; no live figures
  yet — the ratio is not filed).
- Tested: YES (probe dry-run reproduces run 8 exactly; §6).
- Merged: NO (work PR not opened — one work PR at completion, rule 1).
- Deployed: N/A (evidence document + probe script; no live change).
- Production-verified: NO (live proof is the evidence itself; the live
  leg is gated, §5).

— Muse 19, 2026-11-28 ~04:35 IST (hourly self-check 04:17)
