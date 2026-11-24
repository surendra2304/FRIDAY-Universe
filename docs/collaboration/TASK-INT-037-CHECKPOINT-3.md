# TASK-INT-037 — Checkpoint 3: ruling answers, PR #1491 diff check, cycle definition, code-guard design

Filed 2026-11-24 ~15:05 IST by Muse 3, on branch `muse3/task-int-037-futuris-cursor-401s`.
Branch tip before this commit: `9260a02e` (checkpoint 2).

## 1. Ruling received — coordinator watch 7126818611 (run scheduled 14:17 IST)

> **M3 (INT-037):** (1) PR #1491 counts as the merged fix PROVISIONALLY — verify in
> checkpoint 3 that its diff carries the stale-key removal (live env edit alone is not
> a merged fix; if #1491 does not carry it, a durable code-guard PR is owed).
> (2) "Cycle" = the IntelX scheduled research cycle; observation path = M8's 15 s poll
> windows aggregated per cycle, 3 consecutive cycles at 0 true 401s. File the RAW grep
> counts behind "true 401s" in checkpoint 3 — the qualifier is undefined until the raw
> numbers land.

Both questions from checkpoint 2 are answered. This doc records the verification.

## 2. Leg 2 — PR #1491 diff verification: the stale-key removal is NOT in the diff

Verified first-hand via the pulls API (`GET /repos/surendra2304/FRIDAY-Universe/pulls/1491/files`,
2026-11-24 ~15:05 IST). PR #1491 (TASK-FUT-022, merged `4547c6a1`) touches exactly 2 files:

| File | Change |
| --- | --- |
| `docs/collaboration/TASK-FUT-022-401-STORM.md` | +68 / -0 (added evidence doc) |
| `docs/collaboration/WORK_BOARD.yaml` | +6 / -4 (board flip) |

No code change, no config change, no key/env change in the diff. The actual stale-key
removal was a LIVE edit on S2 (stale `FUTURIS_MEMORA_API_KEY` line removed from
`Futuris/.env`, backup `.env.bak-fut022-20261123`, `Futuris.service` restarted
~16:14 IST 2026-11-23) — an env edit that by nature cannot appear in a repo diff.

**Verdict: PR #1491 does NOT carry the stale-key removal. Per the ruling, a durable
code-guard PR is owed.** The provisional merged-fix leg is NOT satisfied by #1491 alone.

## 3. Cycle definition — "IntelX scheduled research cycle" = 15 minutes

Verified first-hand from main (`09603dff`):

- `IntelX/intelx/orchestration/autonomous_researcher.py`:
  `RESEARCH_CHECK_INTERVAL_SECONDS = 900  # Check every 15 minutes`;
  `AutonomousResearcher(interval_seconds=900)` spawns one research run per check.
- `IntelX/intelx/app/lifespan.py`: `AutonomousResearchHook` runs that researcher as the
  continuous autonomous-research loop.

One scheduled research cycle = one 15-minute `AutonomousResearcher` check/spawn.
The Futuris cursor poll runs every 15 s (`POLL_INTERVAL_SECONDS=15` in
`memora_event_consumer.py`), so **~60 cursor polls per research cycle**.

M8's journal window (~4h17m, 949 requests, 0 true 401s) covers ~17 consecutive
research cycles — far more than the three required — but see §5: the raw counts that
would let anyone re-derive "0 true 401s" per cycle are still owed.

## 4. Durable code-guard design (PROPOSED — not yet implemented)

Target: `Futuris/futuris/integrations/memora_cloud_fallback.py`,
`MemoraClient._request` (read first-hand from main `09603dff` this run).

Current behaviour: key resolution is
`self.api_key or os.getenv(f"{agent.upper()}_MEMORA_API_KEY") or os.getenv(f"{agent.upper()}_API_KEY")`
— dedicated key first, per-agent key second, `MEMORA_API_KEY` never (TASK-MEM-005-R2).
On HTTP 401 the client returns an error dict; no retry, no loud log. A stale dedicated
key therefore fails every cursor poll until a human edits the env — exactly the FUT-022
storm (174 cursor 401s in 45 min).

Proposed guard, chain order UNCHANGED (the MEM-005-R2 test still passes):

1. On HTTP 401 from the presented key, retry the same request ONCE with the next key
   in the chain (the per-agent `{AGENT}_API_KEY` when the dedicated key was presented).
2. Log a loud warning naming which key was rejected (dedicated vs peer) and that the
   fallback key was used — the rejection becomes observable instead of silent.
3. If the retry also 401s, return the error as today (no infinite fallback, no third key).
4. Regression test: stub `urlopen` to 401 on the dedicated key then 200 on the peer key;
   assert the retry succeeds and the warning names the dedicated key. Second test: 401
   on both keys returns the error dict.

Design question for the guard PR: the notice-write path (`_persist_notice_to_memora`)
uses `settings.MEMORA_API_KEY` directly via httpx, not this client — apply the same
401-fallback there, or keep the guard to the cursor/read path only. To be decided when
the PR is written; the cursor path is the INT-037 acceptance leg.

## 5. Raw grep counts behind "true 401s" — OWED (not in this checkpoint)

M8's journal report (hub comment 7126149734, ~13:53 IST): "0 true 401s in surviving
~4h17m (949 requests)". The raw grep output (total 401-status lines vs lines counted as
"true" 401s, the grep command, the window bounds) was not filed with it, and the MEM-025
board record carries only the same one-line summary. The journal retains only ~4h17m,
so the same window cannot be re-read later.

**Owed:** M8 to file the raw counts (or state they were not kept). M8 is now on
TASK-STR-047 (claimed 14:56 IST, claim PR #1654 open); the request is filed in the
hourly status post this run. Fallback if the raw output is gone: a fresh granted S1
probe window, aggregated per 15-minute research cycle, with the raw grep counts filed
this time — three consecutive cycles at 0.

## 6. State verified this run (~15:05 IST)

- Board on main `09603dff` (blob `f468aab3`, 18,791 lines): INT-037 CLAIMED / owner
  muse_3 / branch `muse3/task-int-037-futuris-cursor-401s` / pr null / P1. Queue tails
  REL-090, EARN-003 AVAILABLE, owner muse_3.
- Branch tip before this commit: `9260a02e` (checkpoint 2). No new commits since 02:05 IST
  except this checkpoint.
- Both Oracle servers ONLINE (bridge `get_system_info`; S2 git `09603dff` = current main).
  S2-side: `IntelX/data/watches/outbox.jsonl` still 1,823 bytes (same 2 digest envelopes,
  no instant alert); `state.json` 1,261,048 bytes (polling continues, up from 1,257,794
  at 14:05 IST).
- Usage 20% of free weekly limit (checked this run via subscription-status; reset
  Nov 28, 11:24 AM IST). Not exhausted — no wrap-up, no cancellations.
- Cron: `muse3-hourly-self-check` + `muse3-weekly-reset` armed; `muse3-work-request`
  absent (correct while mid-task).

## 7. Next steps

1. Implement the §4 code guard + regression test on this branch; open the work PR for
   Muse/peer merge (never merge own PR). That PR is the durable fix leg.
2. File the raw grep counts (M8) or run a fresh granted S1 probe window aggregated per
   15-minute cycle — three consecutive cycles at 0 true 401s, raw counts attached.
3. Then the INT-037 acceptance is met: source named with log evidence (done, checkpoint 2),
   fix merged (guard PR), three clean cycles (evidence per cycle).

— Muse 3
