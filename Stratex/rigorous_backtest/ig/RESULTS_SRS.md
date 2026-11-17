# RESULTS — SRS (School Run Strategy), TASK-IG2-STR-14: declared backtest RUN

**VERDICT: FAIL — the family is CLOSED per the declaration.**

Judged under **SRS declaration + TEMPORAL HOLDOUT v1 + data-spec
addendum v4 (check-4 cross-source: Yahoo Finance daily; close leg:
SIP tick official-close print, Rule R1b)**.

Run executed **once**, 2026-11-17, after the verification gate
passed under addendum v4. This file is the run record; the machine
records shipped beside it are `srs_results.json` (the full run
report, including the complete pooled OOS trade list),
`srs_provenance.json` (the gate's provenance record) and
`srs_verification_report.json` (the gate's five-check report).

## The chain (addendum v4 §8 — stated wherever the verdict is reported)

1. **2026-11-17, addendum v3 gate — STOP.** Checks 1/2/3/5 PASS;
   check 4 FAIL on the close leg only (10 findings, $0.03–$0.25;
   highs/lows agreed ≤ $0.0012). Root cause: Yahoo's daily close is
   the official closing-auction print; the panel's session close is
   its last (15:45) bar's close — the last pre-auction trade. Two
   different quantities; the run did not execute and no trial was
   consumed (issue #35 comment 6947987723).
2. **First addendum-v4 attempt — STOPPED before freezing.** No
   mechanical bar aggregate recovers the official close (panel-wide
   census: panel close beyond the $0.02 tolerance on 663/952
   regular sessions; 16:00-bar open 480; close 903; VWAP 309).
3. **Addendum v4 (PR #906, merged → main 314e5158…)** re-founded
   the close leg on the SIP tick tape: Rule R1b — the trade
   carrying condition 'M' (Market Center Official Closing Price)
   on the listing exchange 'Q' in [16:00:00, 16:01:00) ET; exactly
   one such print must exist; tolerance unchanged at $0.02. The
   tick probe had scored R1b exact (diff 0.0000) on 15/15 sampled
   sessions before the freeze.
4. **2026-11-17, addendum v4 gate — PASS (all five checks).** The
   run below followed. The run may never be described as "run
   exactly as originally frozen".

## Gate record (v4 verifier, single run)

- Verifier `verify_srs_panel_v4.py` SHA-256
  `c4bbf80b253a4a7a1bad7fce6b39697cf89b59be0507c597bef4010b2da80049`;
  addendum v4 SHA-256
  `c8a3c8be546519d7ed200234f80a6ce0097cce598fc56cffd8579c2765898a19`;
  pinned `nyse_calendar.py` SHA-256
  `e6722180605bebf826b8525489e3e7e3dbaaa50fb48841c2f0119fe0df252db1`.
- Panel: Alpaca SIP 15-minute, `adjustment=split`,
  2023-01-01 → 2026-10-31, 961 sessions / 24,842 bars, SHA-256
  `5addb8cdee3f2a06d509c498a986ab23de3e8c92c5d7ff92d7a947bc716b67b1`
  (byte-identical to the v3 gate's panel; never re-pulled).
- Check 1 gap audit PASS · Check 2 feed/volume PASS (median daily
  volume 83,246,742 ≥ 10M — consolidated SIP scale) · Check 3 split
  PASS · Check 4 cross-source PASS — 15/15 sampled sessions, zero
  findings: open/high/low legs vs Yahoo ≤ $0.0012; close leg (R1b,
  ticks pulled **fresh at gate time** per v4 §4, provenance
  hash-recorded in the report) — exactly one 'M'/'Q' print per
  session and **close_diff = 0.0000 on all 15** · Check 5 freeze
  PASS (panel hash == download-draft hash).
- Cross-source: Yahoo Finance daily, raw file SHA-256
  `60c5b62019901b3a8653498fff4ed1f8d2c14901a72539ab941bf21558380d64`,
  transformed per v3 §3.3 (transformed SHA-256
  `cce9d8366ed77e427ddedafbc26b12a5bae3e157f09bd022d23a46d96592d592`).

## Run record

- Harness: the frozen workspace harness, `srs_signal.py` SHA-256
  `829cd8ee8c8f57c1fd6cac993e94cbe312822d83332d47d3721b68fea58f6d46`
  (synthetic-only unit tests 14/14 re-run immediately before the
  execution; no real data was touched before the gate passed).
- Rules as declared: first-two-candles (09:30 + 09:45 ET) range;
  first later candle closing beyond the range enters at its close
  (qualifying candle must close by 15:45 ET); stop = opposite range
  end; target = entry ± 10 points; SL/TP from the next bar onward,
  stop-before-target within a bar; one trade per session; exit at
  session close if neither level triggers.
- **Trade list SHA-256:
  `5c752da64c8a500e318a96c2fb46f5af730378a596b6c1bfb98b7fcac39fccf5`**
  (849 trades generated over the full panel; 512 pooled OOS).
- Trial accounting: entering N = **3,891** (re-read fresh at run
  time — census + addendum v4 §5 + main's results tree agree; no
  declared run had executed since the census) → this run is trial
  **3,892**; Bonferroni α = 0.05 / 3892 ≈ 1.2847e-05. Programme
  counter after this run: **3,892**.

### Headline numbers (pooled OOS, W1–W5, entry-time attribution)

| Basis | Trades | Win rate | Expectancy_net | PF_net | Total net |
|---|---|---|---|---|---|
| 1× costs (16 bps RT) | 512 | 45.1% | **−0.000575** | **0.919** | −29.4% |
| 2× shadow (32 bps RT) | 512 | 41.4% | −0.002174 | 0.728 | −111.3% |

### Per-fold (1× costs)

| Fold | Trades | Expectancy_net | PF_net | Total net |
|---|---|---|---|---|
| W1 | 108 | −0.000328 | 0.960 | −3.5% |
| W2 | 113 | −0.000260 | 0.971 | −2.9% |
| W3 | 110 | −0.001181 | 0.815 | −13.0% |
| W4 | 110 | **+0.000348** | 1.062 | +3.8% |
| W5 | 71 | −0.001943 | 0.653 | −13.8% |

Positive folds: **1 of 5** (bar: ≥ 4 of 5).

### TEMPORAL HOLDOUT v1 (H = W5, D = W1–W4; judged exactly once)

- H1 — |H| ≥ 20: **PASS** (|H| = 71).
- H2 — expectancy_net(H) > 0: **FAIL** (−0.001943, PF 0.653).
- H3 — expectancy_net(D) > 0: **FAIL** (D = 441 trades,
  expectancy −0.000355, PF 0.952).
- H4 — max fold profit share ≤ 0.80: **FAIL** (1.0 — W4 is the only
  positive fold, so it holds all positive profit).
- H5 — judged exactly once, in this single declared run, per the
  §2.3 order of operations (gate first, one execution, no prior
  OOS inspection): satisfied procedurally. The holdout is now
  spent for this declaration; no re-run is permitted under it.

### Bar

| Element | Result |
|---|---|
| ≥ 200 pooled OOS trades | PASS (512) |
| expectancy_net > 0 at 1× | **FAIL** (−0.000575) |
| expectancy_net > 0 at 2× shadow | **FAIL** (−0.002174) |
| PF_net ≥ 1.2 | **FAIL** (0.919) |
| ≥ 4/5 folds positive | **FAIL** (1/5) |
| TEMPORAL HOLDOUT H1–H4 | **FAIL** (H2, H3, H4) |
| Bonferroni p < α at final N = 3,892 | **FAIL** (p = 0.7765 vs α = 1.2847e-05) |

This is not an insufficiency verdict — the sample is ample (512
pooled OOS trades, 71 in the holdout). The strategy loses money
under the programme cost model, gross of any rescue: only one fold
of five is positive, and the holdout fold is the worst of the five.

## Disclosures

- **Early-close truncation (frozen panel property).** The pinned
  calendar keeps only the first 10 bar-starts (09:30–11:45 ET) of
  the 9 early-close sessions in the panel, although SIP serves 14
  genuine regular-session bars on those days (the 13:00 ET closing
  auction included). Adjudicated before the v3 gate: the run
  proceeds as frozen; the 12:00–13:00 ET bars of those 9 sessions
  are excluded. Disclosed here as a limitation of the judged panel,
  uniformly applied.
- **Cost model.** The programme cost model (`simulator.Costs()` —
  5 bps fee + 3 bps slippage per side, 16 bps round trip; 32 bps
  shadow) is a futures-venue model applied to an equity, per the
  declaration and the holdout addendum §6 recorded reading. It is
  not generous to the strategy; no equity-specific model was
  substituted.

## Consequence

FAIL ⇒ SRS is **not** eligible for the Phase-3 forward demo, and
the family is **closed** under this declaration: no variant,
re-run, or second exit rule is authorised by this record. A future
SRS variant would require a **new** pre-declaration at the
then-current trial floor (3,892 after this run). Nothing was
promoted, nothing trades.

*Records: gate + run executed by the coordinator's SRS-resume crew,
2026-11-17. Panel and tick data are never committed (SIP licence);
only these provenance-bearing records are.*
