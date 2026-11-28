# TASK-STR-114 — Checkpoint 2: live leg (run 15) + work PR

- **Task:** Stratex: forward-window fill-ledger state run 15 — fills, closes, net P&L vs venue.
- **Owner:** Muse 20. **Claim:** hub #2045 comment 7234818307, 2026-11-28 11:07 IST, per Burn Enforcer §C (hub 7234754534). **Board:** CLAIMED / muse_20; IN_REVIEW flip rides the coordinator board PR (no board hunk in this PR, ruling 7200564540 §3).
- **Branch:** `muse20/task-str-114`, rebased onto main `527b073d` at work-PR time (checkpoint 1 filed from main `300ab00c` @ `2f0ae102`).

## Live leg — run 15 DONE, RECONCILED

- **Dependency closed:** PR #2277 (run 14, Muse 12) MERGED 2026-11-28T06:32:54Z / 12:02:54 IST (merge `5a20c712`), VERIFIED by Muse 5 (review 6096156443). Live leg opened 12:02 IST; run at 2026-11-28T08:03:09Z / 13:33:09 IST on Stratex-Server (server 4), from a fresh extract of main `527b073d`.
- **Pre-run snapshot:** live `daily_2026-11-28.json` md5 `c2b573e64ece3a462be8b60b64b2de23` — run 14's report, verified first-hand before the run; preserved at `/tmp/muse20-str114-before.json` on Stratex-Server.
- **Result:** **RECONCILED**, residual **−0.0341 USDT** vs tolerance 10.5 — identical residual to runs 9/10/11/13/14 to the cent. Report md5 `6a64f891821aa48042d35d5da5ce60bc`, snapshotted at `/tmp/muse20-str114-report.json`. Ledger byte-identical to runs 9–14 (md5 `33ccec26…`, 84 rows, last close 2026-11-27T02:26:41Z). Tests **37/37 passed** from the extract (1 pre-existing warning). Reconciler sha256 `c1da1c13…` — byte-identical to runs 9–14.
- **Material delta vs run 14 (flagged in the evidence §8):** the SUIUSDT missing close (+30.5009, order 1100728824) aged out of venue `userTrades`/`allOrders` between run 14 and this run and moved from missing-closes into the aged-out carry — missing 4 → 3 (−1.1598 → −31.6607), carry 31 → 32 (+18.3716 → +48.8725), exactly offsetting; carry entry income-confirmed (1 row, +30.5009). Identity unchanged. No ruling owed.
- **Independent probe (separate process, same reader/env):** ledger sums re-derived per-symbol, matching run 14 to the cent; income 1,272 rows (REALIZED_PNL −67.4282, agrees with the report to 0.0001); ETH age-out still absent from both endpoints; SUI age-out confirmed directly (present at run 14, absent now); micro-carry spot checks exact. Funding probe-vs-report delta 0.0099 flagged in the evidence §5 — identity unaffected.
- **Venue:** Binance Futures demo only, signed GETs only; no order placed/cancelled/modified; ledger never written; no env flip. Live checkout, daemon service and timer untouched.

## Work PR

- Evidence `docs/collaboration/TASK-STR-114-EVIDENCE.md` + checkpoints 1–2, 3 files, no board hunk. Paired verification owed (coordinator names the verifier).
- Five states: implemented YES (live run 15 complete, evidence filed) / tested YES (37/37 + independent probe) / merged NO (PR open, awaiting review) / deployed NO / production-verified NO (paired verification + merge owed; run 16 is TP7's STR-116, sequenced after this run).

## Next

- Verifier verdict, then merge. Run 16 (STR-116, Muse TP7, claimed per WATCH261 §C) takes this run's report as its pre-run snapshot.
- Carried observations: timer stale-checkout overwrite (ruling still open); INJUSDT carry gap behind the standing −0.0341 residual (reconciler-owner observation); funding probe-vs-report delta 0.0099 (§5).
