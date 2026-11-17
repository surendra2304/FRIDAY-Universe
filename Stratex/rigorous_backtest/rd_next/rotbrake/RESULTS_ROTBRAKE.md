# RESULTS — Cross-Asset Rotation with Drawdown Brake (rotbrake, RD-020), TASK-STR-RD-020: declared backtest RUN

**VERDICT: FAIL — 0/4 cells pass. Per-period OOS PF 0.650–0.753 « 1.2
→ DELETE-class per the owner's standing rule (research harness only;
nothing in production to delete). The rotation-brake family is CLOSED
per the declaration's own terms.**

Run executed under the frozen declaration `declaration.json`, SHA-256
`fe9b8fbc1808fe646aa87c06cab0797d5a32945abcb94a3b7131eadd87bdd4ec`
(package at `Stratex/rigorous_backtest/rd_next/rotbrake/`, shipped by
PR #898; all five package files re-verified byte-identical to the
frozen pins at fire time against origin/main
`ff47bd06da0d5a5b49a2eff1ad67ec20fe05a32d`, and again at record time
against `95acbea70be35bec3dc92e2cf227423bd899bdca`).
This file is the run record; the machine records shipped beside it
are `synthesis.json` — a byte-identical copy of the run's
`synthesis.json` (SHA-256
`908f57cff6f48f422cdb1264e264b6675b525e8a4b3f7b52ef6ef190ee7eb30a`) —
and `verification.json` — a byte-identical copy of the run's
verification_before_trust record (SHA-256
`a11b28a0a6e47a5f4dfe985a3a468708220c3cae4626d1f6b6da9c620ecf901c`).
The run log is pinned by SHA-256
`9840e5fbda4aefa231cb0488a70af2b93d434c7fc468ad56bbada1fdebbcd73a`
(held with the run crew's record; the runner's output is the shipped
`synthesis.json` itself).

## The chain

1. **Declaration first.** The family was pre-declared and frozen
   under TASK-STR-RD-020 (supervised re-freeze; PR #898) before the
   declared run fired: RD-013's cross-asset rotation (weekly,
   long/flat, top-K of a 7-asset universe by trailing momentum) with
   a frozen_v1 drawdown brake layered on top. Four frozen cells —
   lookback 63 or 126 days × top-K 2 or 3. Judgement is PER CELL
   against eight gates: (g1) OOS compounded return > 0; (g2)
   per-period PF ≥ 1.2; (g3) ≥ 4/5 folds positive; (g4) daily-curve
   max drawdown ≤ 20% from carried-in peak; (g5) top-asset P&L
   share ≤ 50%; (g6) Bonferroni one-sided t — pass requires
   p < α/2 with α = 0.05/N_global; (g7) 2×-cost gate, evaluated
   only if a cell first reaches the mechanical pass (frozen
   conditional); (g8) ≥ 200 OOS episodes AND episode PF ≥ 1.2.
   A cell passes only if ALL applicable gates hold.
2. **Panel.** RD-013's 7-asset panel (staged at
   `~/workspace/str-rd2/cache2`), re-hashed fresh at fire time —
   7/7 == declaration-recorded:

   | asset | source | daily bars | SHA-256 |
   |---|---|---|---|
   | BTCUSDT | Binance Vision UM futures monthly klines | 1,765 | cbd726f60c714420781961a447577b43659780e66f6e94e27ee1db5a2ebc640e |
   | ETHUSDT | Binance Vision UM futures monthly klines | 1,765 | 5d861191ad4d68e922b741c33e99192d6082016b92eaf265dd76e7949d01c88c |
   | SOLUSDT | Binance Vision UM futures monthly klines | 1,760 | 281fbff59b203575c1acf24b0a15cafdb53cae6a3814df2d95c099d0de056196 |
   | BNBUSDT | Binance Vision UM futures monthly klines | 1,765 | 5461c517e9a18ffdfb0ec7fdad845fd864465a377351208c934f0cb3af745549 |
   | GOLD | Yahoo daily | 2,232 | 4933b83b0672551656e0c4c7068f9087b232274ab954e64164b9360ca3560dd4 |
   | SPX | Yahoo daily | 2,230 | ab1482ee3b03fa53fa80ffc818cd86f4c60feb8c85265b4ca808e0b60b4673bb |
   | NDX | Yahoo daily | 2,230 | 4dd2893217154491dc5732eae71883a71d4a234ff87b46d4b32cb964ed6ea581 |

3. **Gates re-verified fresh immediately before the run**
   (2026-11-17, run crew): (1) all five package files extracted
   from current origin/main `ff47bd06…` == frozen pins —
   `declaration.json` `fe9b8fbc1808fe646aa87c06cab0797d5a32945abcb94a3b7131eadd87bdd4ec`;
   `DECLARATION.md` `f7049796f87b5310a57246c187d3bceb927ffb615b2a4a0b3dbd93b25ff77bc3`;
   `harness/rotbrake.py` `efb411c5e685ebb5f2f92ac54555bd0849b5d162242a7a6bc4b4b50ea213d2db`;
   `harness/run_rotbrake.py` `be108221a677f6eaf8d34582e6889e07239ffd0f3f0325334978131dfa52963d`;
   `harness/test_rotbrake.py` `07e7d2999dc39120bb09c968902d24d1faefce6fe9558dfe769e195928bf5c9f`;
   (2) panel re-hash 7/7 PASS; (3) synthetic suite on the exact run
   bytes: 10 passed; (4) programme trial counter read fresh from
   RD-019's concluded record = **3,895** entering, so the frozen
   formula gives N_global = max(3895, 3893) + 4 = **3899** and
   Bonferroni α = 0.05/3899 = 1.2823800974608875e-05.
4. **The one declared run.** Fired 2026-11-17T18:43:29Z under the
   frozen command, exit 0, ~5 s. Exactly one run was fired; no
   re-runs, no parameter changes.

   ```
   python3 harness/run_rotbrake.py ~/workspace/str-rd2/cache2 3899
   ```

5. **verification_before_trust — PASS** (applied before any number
   was trusted; record = shipped `verification.json`):
   - Part A (independent recomputation from the declaration text):
     L63_K2's first six OOS weekly periods — picks EQUAL at all six
     rebalances; period net returns bit-exact (max |diff| = 0.0);
     total turnover cost fraction bit-exact (0.10662447460178272);
     full OOS compounded bit-exact (−0.12534346394520457).
   - Part B (control reproduction): rebalance grids identical (200
     dates); engine selections == RD-013 rotation.py selections
     EXACTLY for all 4 cells at every date (0 mismatches).
     Brake-disabled scratch run vs RD-013's judged control record:
     compounded 0.5046/0.5467/0.1792/−0.0444 vs RD-013
     0.5048/0.5468/0.1794/−0.0444; PF 1.3328/1.3752/1.1661/1.0552 vs
     1.3329/1.3752/1.1662/1.0552; folds 3/5 on all four, both sides —
     reproduction holds (residual diff = the declared
     accounting-convention change; selections/dates exact as
     required).

## Results — per cell (122 OOS periods each)

| cell | compounded | period PF | episode PF | episodes | daily max DD | folds | Bonferroni p | max asset share | brake transitions | turnover cost frac |
|---|---|---|---|---|---|---|---|---|---|---|
| L63_K2 | −0.12534346394520457 | 0.7020879197996849 | 0.7370244879411872 | 202 | −0.3967834932939496 | 1/5 | 0.8960268392228075 | 0.5783830498414126 | 301 | 0.10662447460178272 |
| L63_K3 | −0.1056714084086946 | 0.7041299129833811 | 0.7547175740418275 | 270 | −0.29174007645071987 | 1/5 | 0.8772240347881142 | 1.0 | 264 | 0.09408747173339568 |
| L126_K2 | −0.1134931167998291 | 0.7531783814483572 | 0.780516044479533 | 222 | −0.39490781766183236 | 1/5 | 0.8484499996702937 | 0.5703320133832419 | 292 | 0.10399407778727644 |
| L126_K3 | −0.13238622134301448 | 0.6503992227037486 | 0.7026409940966161 | 258 | −0.34324272885701534 | 1/5 | 0.9135559516628852 | 1.0 | 210 | 0.08056713103215646 |

Ranges: per-period PF 0.650–0.753; episode PF 0.703–0.781;
compounded −10.6%…−13.2%; daily max DD −29.2%…−39.7% against the
20% gate; folds 1/5 in every cell; Bonferroni p 0.848–0.914 against
α = 1.2824e-05. **Every cell failed all seven evaluated gates**
(g1, g2, g3, g4, g5, g6, g8). Gate g7 (2× costs) was never
evaluated — no cell reached the mechanical pass that triggers it
(the frozen conditional pattern). All four cells have ≥ 200
episodes, so none escapes as "insufficient OOS trades" — all four
are judged FAIL on the merits.

Per-fold compounded (periods per fold W1–W5: 27/26/26/26/17):

| cell | W1 | W2 | W3 | W4 | W5 |
|---|---|---|---|---|---|
| L63_K2 | −0.0032853369410177358 | +0.007756961718713207 | −0.04962430550123176 | −0.033103938390601106 | −0.0523765935041971 |
| L63_K3 | −0.02361032158942855 | +0.004025481661609209 | −0.017219593014588863 | −0.04103447534803095 | −0.032012572846288556 |
| L126_K2 | +0.022394937755729982 | −0.050927754538648395 | −0.046717232669936215 | −0.022747649507536716 | −0.019301112950908084 |
| L126_K3 | +0.03830585412593801 | −0.08428911070175105 | −0.05498976817196444 | −0.006112179206173796 | −0.028441670088251603 |

Per-asset episode contributions are recorded in full in the shipped
`synthesis.json` (`contrib_by_asset_episodes` per row); ETHUSDT is
the largest drag in three of four cells (−0.149 / −0.306 / −0.231 /
−0.404).

## Texture

The brake did not even fix its own target: daily max drawdown ran
−29%…−40% against the 20% gate on every cell, while 210–301 brake
transitions per cell charged 8.1–10.7% of equity in turnover. The
braked books finished far BELOW RD-013's unbraked controls
(+50.5/+54.7/+17.9/−4.4% compounded).

## Consequence

- Verdict FAIL, 0/4 cells. The rotation-brake hypothesis is closed
  with this verdict, per the declaration's own terms; the family is
  DELETE-class under the owner's standing PF < 1.2 rule (research
  harness only — nothing in production to delete, nothing
  forward-demo eligible).
- Trial accounting: this run consumed trials 3,896–3,899;
  **programme trial counter now 3,899**.
- The WORK_BOARD.yaml flip for TASK-STR-RD-020 is NOT in this PR —
  it rides the next board PR batch.
