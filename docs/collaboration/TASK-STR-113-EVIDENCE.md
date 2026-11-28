# TASK-STR-113 — GDP-filter scoping: classification of the non-US GDP rows

- **Filed:** 2026-11-28 ~10:20 IST, by Muse 4. **Status:** classification complete, filter scope decided. **NO live module edit in this leg** — scoping only, per acceptance.
- **Task:** classify the non-US GDP rows flagged by WATCH252 NARROW before any US-only GDP filter; decide the filter scope.
- **Claim:** hub #2045 comment 7234193649 (~10:11 IST). Branch `muse4/task-str-113-gdp-filter-scoping` @ main `7ecab6ce`.

## Sources read first-hand

- WATCH252 NARROW flag — hub #2045 comment 7233513157 (M3 completion post, 2026-11-28T03:55Z): "12 non-US GDP rows still high incl. debt-ratio substring matches — US-only GDP filter is the coordinator's call; live module NOT edited".
- M3 STR-074 checkpoint 6 evidence — branch `muse3/task-str-074-production-verify-wave1` @ `45717bf7`, blob `5365b8bb054e52d9092945bf0c40e364654575fd`: the NARROW application, exact rule, and the 12-row flag (see § "WATCH252 §D NARROW").
- M3 #2249 paired verdict — review 6095514269 (STR-107 tax-export fix, VERIFIED; the GDP flag rides in the same checkpoint, not in the verdict).
- WATCH254 §C.4 — hub #2045 comment 7233833233: "HOLD the US-only GDP filter… Follow-up task (classify the 12 rows, then filter) goes to the pool".
- WATCH255 §B — hub #2045 comment 7234035207: STR-113 drafted to restore the pool floor.
- Board record — TASK-STR-113 AVAILABLE on live main `7ecab6ce` (blob `f2504f88`).

## Method — read-only live probe (Stratex-Server, S4)

- **Live module identity:** `/opt/friday_universe/Stratex/research/economic_calendar.py` sha256 `ab1da78643b5d42f024d39600b09dda8015c73b352ac18971ab56a1ead46b310` — identical to the main-`7ecab6ce` copy. The module's own `classify_macro_impact` (substring keyword table, `"gdp"` in name → high) is the mechanism under scoping.
- **What ran:** fresh Nasdaq refresh via the live module into `/tmp/str113/calendar.jsonl` (2026-11-28 ~05:00Z), then M3's NARROW rule applied in-probe to the stored set. No live file edited, no env flip, no restart.
- **Daemon untouched (verified before/after):** MainPID 74530 at both snapshots; `Stratex/state/fill_ledger.jsonl` sha256 `5e657087099259764596059b989d66191cad0fc23d90795abdde0f5bcb910a21`, 84 lines, identical. (Note: M3 recorded PID 74531 at 03:55Z; both of my snapshots read MainPID 74530. No restart is claimed — the ledger hash is the continuity evidence.)
- **Live checkout note:** S4 checkout head is `3db55adf`, behind main `7ecab6ce` — recorded, not acted on (out of scope for this leg).

## Reproduction — M3's NARROW numbers match exactly

Same 479-event set as M3 (330 macro / 149 earnings, `last_refresh_ok` true), same window (2026-11-28 → 12-05):

| metric | M3 (checkpoint 6) | this probe |
|---|---|---|
| events stored | 479 | 479 |
| broad high | 65 (13.6%) | 65 |
| narrowed high | 32 (6.7%) | 32 |
| demoted | 38 | 38 |
| promoted | 5 | 5 (Chicago PMI; S&P Global Manufacturing PMI; ISM Non-Manufacturing PMI; S&P Global Composite PMI; S&P Global Services PMI — all US, all previously low) |

NARROW rule as applied (M3's exact statement): high only for central-bank decisions (FOMC / federal open market / interest rate decision / fed chair), NFP (nonfarm / non-farm / employment situation), GDP (unqualified), ISM manufacturing/services, US PMI majors, CPI-US (country US/blank AND no non-US region marker in the name); earnings unchanged (megacap watchlist).

## Classification — the 16 non-US GDP rows found first-hand

"Non-US GDP row" = narrowed-high macro row whose name contains `gdp` (case-insensitive substring) and whose country is not US. The probe finds **16** such rows; M3 flagged 12 (reconciled below). Every row below was high under the module's own classifier (`impact: "high"` in the stored row).

### Class A — genuine headline GDP release (9)

| # | date | name | country | previous | forecast / actual |
|---|---|---|---|---|---|
| 1 | 2026-11-28 | French GDP | France | 0.5% | actual −0.2% |
| 2 | 2026-12-01 | GDP | Canada | 1.13% | — |
| 3 | 2026-12-01 | GDP Annualized | Canada | 3.3% | — |
| 4 | 2026-12-01 | GDP Quarterly (YoY) | India | 7.8% | fcst 7.6% |
| 5 | 2026-12-02 | GDP | Australia | 2.1% | — |
| 6 | 2026-12-02 | GDP Annualized | South Africa | −0.2% | — |
| 7 | 2026-12-02 | Italian GDP | Italy | 0.8% | fcst 0.8% |
| 8 | 2026-12-03 | GDP | Brazil | 2.0% | — |
| 9 | 2026-12-03 | GDP Monthly | Russia | 0.5% | — |

Each is a real GDP print for its country. Demoting these under a US-only filter is a deliberate scope decision (they are real signals, just not US ones) — not a false-positive cleanup.

### Class B — GDP sub-component / detail row (4)

| # | date | name | country | previous | note |
|---|---|---|---|---|---|
| 10 | 2026-12-01 | GDP Implicit Price | Canada | 2.50% | GDP deflator — a price index for GDP, not a GDP growth print |
| 11 | 2026-12-02 | GDP Capital Expenditure | Australia | −0.3% | national-accounts component |
| 12 | 2026-12-02 | GDP Chain Price Index | Australia | −0.6% | price-index component |
| 13 | 2026-12-02 | GDP Final Consumption | Australia | 0.5% | national-accounts component |

Genuinely GDP-related, but detail/detail-price rows, not headline GDP releases.

### Class C — substring false-positive, NOT a GDP release (3)

| # | date | name | country | previous | note |
|---|---|---|---|---|---|
| 14 | 2026-12-01 | Gross Debt-to-GDP ratio | Brazil | 82.9% | debt statistic; GDP is only the denominator |
| 15 | 2026-12-01 | Net Debt-to-GDP ratio | Brazil | 70.0% | debt statistic; GDP is only the denominator |
| 16 | 2026-12-04 | Current Account % of GDP | South Africa | −2.60% | current-account statistic expressed as % of GDP |

These three are never GDP releases under any scope — the `gdp` substring alone put them high. Note: "Current Account % of GDP" contains GDP as a **whole word**, so a word-boundary `gdp` match does NOT exclude it; only a semantic exclusion (debt-to-GDP, % of GDP, current account) does.

**Totals: 9 genuine headline + 4 sub-component + 3 false-positive = 16.**

## Reconciliation — M3's 12 vs this probe's 16

Best fit, cross-checked against M3's own text: M3's 12 = rows 1–8 + 10 + 14–16 (8 headline + the GDP deflator + 3 false-positives). The 4 rows my reproduction adds are the 3 Australian detail rows (#11–13) and Russia GDP Monthly (#9). Supporting cross-checks: (a) M3's 12-01 advisory note counts 6 GDP rows on 12-01 — exactly rows 2, 3, 4, 5, 14, 15, i.e. including the deflator (#10); (b) M3's country list (French/Canadian/Australian/Indian/Brazilian/South African/Italian) contains no Russia — matching the exclusion of #9. The boundary is a judgment call in M3's quick count, stated here as a reconciliation, not a proven fact; all 16 rows are classified above either way, so the verdict does not depend on it.

## Scope decision — US-only GDP filter ADOPTED (scope, not code)

1. **GDP is high only for US GDP releases** (country US/blank). All 16 non-US rows above drop from high when the filter lands — 9 genuine headline + 4 sub-component rows by deliberate scope (the scan-pause advisory is US-market scoped), 3 false-positives because they were never GDP releases.
2. **The filter must be semantic, not just word-boundary:** exclude `debt-to-gdp`, `% of gdp`, and `current account` shapes explicitly — word-boundary matching alone leaves "Current Account % of GDP" high.
3. **In-window US control:** the only US GDP row in this window is `Atlanta Fed GDPNow` (United States, 2026-12-02, prev/fcst 2.9%) — a nowcast model estimate, not a BEA release; it stays high under the filter. No BEA GDP release falls in this window.
4. **Advisory impact:** the 72h advisory on 2026-12-01 fires on 7 events under the narrowed set (Chicago PMI + 6 GDP rows) and would fire on **1** (Chicago PMI only) under the US-only filter — confirming M3's checkpoint-6 note.
5. **Implementation is owed separately:** `classify_macro_impact` in `Stratex/research/economic_calendar.py` still carries the broad keyword set; changing it needs a repo edit + tests + CI + a live re-probe. **No live module was edited in this leg.** A follow-up implementation task carries that work; this evidence doc is its input, not its implementation.

## Five states

- implemented NO (classification + scope decision only; code change owed separately)
- tested YES (live re-probe on S4; M3's counts reproduced exactly)
- merged NO
- deployed n/a
- production-verified NO (scoping leg; the filter itself is unverified until implemented and re-probed live)

## What remains

- Paired verification of this evidence PR (verifier: a different chat).
- Follow-up implementation task: US-only GDP filter in `classify_macro_impact` (+ semantic exclusion per §Scope-2) with tests, CI green, and a live S4 re-probe confirming narrowed-high 32 → 16 (the 16 non-US rows demoted; Atlanta Fed GDPNow stays high).

— Muse 4
