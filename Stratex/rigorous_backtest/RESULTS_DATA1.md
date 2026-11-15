# TASK-STR-DATA-001 — OANDA instrument expansion: provenance-verified data inventory

**Verdict: the OANDA universe beyond RD-002's panels is mostly REAL and
backtestable. 55 additional instruments have provenance-verified history
in the RD-002 Stage-A cache contract — 41 FX crosses/minors/exotics, 9
index CFDs, palladium, and 4 soft commodities — each at daily depth from
2018 and hourly depth from Nov 2024. 5 categories are honestly UNCOVERED
or derived-only (CN50, bond CFDs, metal crosses, JP225Y twin, OANDA-native
candles). Two cost-model gaps (palladium, softs) must be closed before
those instruments can be judged. No strategy was designed or tested in
this task — this is the data supply for TASK-STR-RD-003's forex-native
track and any future OANDA-venue family.**

**Venue reality check (TASK-STR-FWD-003, live, twice independently,
2026-11-15): the owner's OANDA practice account lists 68 instruments,
ALL FX pairs — no commodities, metals CFDs, indices or bonds.** So the
operative expansion for RD-003 is the **41 FX crosses**; the index /
palladium / softs series below are verified *as data* (usable for
research and for any future venue that offers them) but are **not
tradeable on the owner's current OANDA account**. One open thread: the
existing `oanda_demo` engine's watchlist includes XAUUSD, which sits
oddly with an FX-only account list — the server-side account diff in
the uncovered table must resolve metals before anyone assumes them
tradeable.

## Method

- **Reference universe:** the 123-instrument OANDA fxTrade list
  (ichimoku/OANDA reference table, retrieved 2026-11-15). The owner's
  practice account's exact tradeable set is account/entity-specific and
  is *not* assumed from this list — see the OANDA_NATIVE uncovered entry
  for the server-side confirmation step.
- **Expansion definition:** every OANDA instrument not already in an
  RD-002 panel (`rd2/panels.py`: forex28, forex12, comm7, idx7) and not a
  denomination twin of a covered underlying.
- **Provenance probe (executed 2026-11-15):** each candidate was fetched
  from the Yahoo Finance chart API — the same source RD-002 Stage A used
  for all non-crypto series — at 1d (from 2018-01-01) and 1h (729-day
  window, Yahoo's depth cap), converted to the RD-002 canonical CSV
  format, and hashed. A series is VERIFIED only if the fetch returned
  ≥50 usable OHLC rows after null drops (drops counted, never filled).
  Full RD-002-format sidecars: `results_data1/manifests.json` (110
  sidecars). Structured inventory: `results_data1/inventory.json`.
  Reproduction fetcher: `rd_data1/fetch_expansion.py`.
- **OANDA-native history** (the venue's own candles: bid/ask/mid
  components, granularities S5–M, 5,000 candles per request,
  time-paginated — see `Stratex/oanda_demo/backtest.py`) is the
  authoritative source but requires the practice-account token, which
  lives only in server-side credentials. Research crews do not pull
  venue credentials (RD-003/RD-007 precedent), so native depth is
  recorded as SERVER_SIDE_ONLY, not approximated.

## Verified expansion — 55 instruments

Costs are the standing `rd2/costs2.py` model (round-trip bps). FX daily
last bar: several series carry the in-progress 2026-11-15 (Sunday) bar
from the live fetch — drop the final partial bar at load, as with any
live fetch; all completed bars hash-verify against the sidecars.

| Symbol | OANDA | Yahoo | 1d rows (range) | 1h rows (range) | Cost RT (bps) |
|---|---|---|---|---|---|
| AUDCAD | AUD_CAD | AUDCAD=X | 2311 (2018-01-01 → 2026-11-15) | 12333 (2024-11-18 → 2026-11-13) | 10.0 |
| AUDCHF | AUD_CHF | AUDCHF=X | 2311 (2018-01-01 → 2026-11-15) | 12323 (2024-11-18 → 2026-11-13) | 10.0 |
| AUDHKD | AUD_HKD | AUDHKD=X | 2311 (2018-01-01 → 2026-11-15) | 12329 (2024-11-18 → 2026-11-13) | 10.0 |
| AUDSGD | AUD_SGD | AUDSGD=X | 2310 (2018-01-01 → 2026-11-15) | 12300 (2024-11-18 → 2026-11-13) | 10.0 |
| CADCHF | CAD_CHF | CADCHF=X | 2311 (2018-01-01 → 2026-11-15) | 12289 (2024-11-18 → 2026-11-13) | 10.0 |
| CADHKD | CAD_HKD | CADHKD=X | 2311 (2018-01-01 → 2026-11-15) | 12361 (2024-11-18 → 2026-11-13) | 10.0 |
| CADSGD | CAD_SGD | CADSGD=X | 2311 (2018-01-01 → 2026-11-15) | 12296 (2024-11-18 → 2026-11-13) | 10.0 |
| CHFHKD | CHF_HKD | CHFHKD=X | 2311 (2018-01-01 → 2026-11-15) | 12284 (2024-11-18 → 2026-11-13) | 10.0 |
| CHFZAR | CHF_ZAR | CHFZAR=X | 2311 (2018-01-01 → 2026-11-15) | 12280 (2024-11-18 → 2026-11-13) | 10.0 |
| EURCAD | EUR_CAD | EURCAD=X | 2311 (2018-01-01 → 2026-11-15) | 12288 (2024-11-18 → 2026-11-13) | 10.0 |
| EURCZK | EUR_CZK | EURCZK=X | 2310 (2018-01-01 → 2026-11-13) | 12296 (2024-11-18 → 2026-11-13) | 10.0 |
| EURDKK | EUR_DKK | EURDKK=X | 2311 (2018-01-01 → 2026-11-15) | 12331 (2024-11-18 → 2026-11-13) | 10.0 |
| EURHKD | EUR_HKD | EURHKD=X | 2311 (2018-01-01 → 2026-11-15) | 12302 (2024-11-18 → 2026-11-13) | 10.0 |
| EURHUF | EUR_HUF | EURHUF=X | 2310 (2018-01-01 → 2026-11-13) | 12287 (2024-11-18 → 2026-11-13) | 10.0 |
| EURNOK | EUR_NOK | EURNOK=X | 2310 (2018-01-01 → 2026-11-13) | 12283 (2024-11-18 → 2026-11-13) | 10.0 |
| EURSEK | EUR_SEK | EURSEK=X | 2311 (2018-01-01 → 2026-11-15) | 12294 (2024-11-18 → 2026-11-13) | 10.0 |
| EURSGD | EUR_SGD | EURSGD=X | 2311 (2018-01-01 → 2026-11-15) | 12303 (2024-11-18 → 2026-11-13) | 10.0 |
| EURTRY | EUR_TRY | EURTRY=X | 2310 (2018-01-01 → 2026-11-13) | 12296 (2024-11-18 → 2026-11-13) | 10.0 |
| EURZAR | EUR_ZAR | EURZAR=X | 2311 (2018-01-01 → 2026-11-15) | 12298 (2024-11-18 → 2026-11-13) | 10.0 |
| GBPCAD | GBP_CAD | GBPCAD=X | 2311 (2018-01-01 → 2026-11-15) | 12328 (2024-11-18 → 2026-11-13) | 10.0 |
| GBPCHF | GBP_CHF | GBPCHF=X | 2311 (2018-01-01 → 2026-11-15) | 12277 (2024-11-18 → 2026-11-13) | 10.0 |
| GBPHKD | GBP_HKD | GBPHKD=X | 2311 (2018-01-01 → 2026-11-15) | 12330 (2024-11-18 → 2026-11-13) | 10.0 |
| GBPNZD | GBP_NZD | GBPNZD=X | 2311 (2018-01-01 → 2026-11-15) | 12324 (2024-11-18 → 2026-11-13) | 10.0 |
| GBPPLN | GBP_PLN | GBPPLN=X | 2310 (2018-01-01 → 2026-11-13) | 12318 (2024-11-18 → 2026-11-13) | 10.0 |
| GBPSGD | GBP_SGD | GBPSGD=X | 2311 (2018-01-01 → 2026-11-15) | 12288 (2024-11-18 → 2026-11-13) | 10.0 |
| GBPZAR | GBP_ZAR | GBPZAR=X | 2311 (2018-01-01 → 2026-11-15) | 12309 (2024-11-18 → 2026-11-13) | 10.0 |
| HKDJPY | HKD_JPY | HKDJPY=X | 2310 (2018-01-01 → 2026-11-13) | 12281 (2024-11-18 → 2026-11-13) | 10.0 |
| NZDCAD | NZD_CAD | NZDCAD=X | 2310 (2018-01-01 → 2026-11-15) | 12330 (2024-11-18 → 2026-11-13) | 10.0 |
| NZDCHF | NZD_CHF | NZDCHF=X | 2310 (2018-01-01 → 2026-11-15) | 12334 (2024-11-18 → 2026-11-13) | 10.0 |
| NZDHKD | NZD_HKD | NZDHKD=X | 2310 (2018-01-01 → 2026-11-15) | 12331 (2024-11-18 → 2026-11-13) | 10.0 |
| NZDSGD | NZD_SGD | NZDSGD=X | 2310 (2018-01-01 → 2026-11-15) | 12299 (2024-11-18 → 2026-11-13) | 10.0 |
| SGDCHF | SGD_CHF | SGDCHF=X | 2310 (2018-01-01 → 2026-11-15) | 12296 (2024-11-18 → 2026-11-13) | 10.0 |
| SGDJPY | SGD_JPY | SGDJPY=X | 2309 (2018-01-01 → 2026-11-13) | 12210 (2024-11-18 → 2026-11-13) | 10.0 |
| TRYJPY | TRY_JPY | TRYJPY=X | 2309 (2018-01-01 → 2026-11-13) | 12054 (2024-11-18 → 2026-11-13) | 10.0 |
| USDCZK | USD_CZK | USDCZK=X | 2309 (2018-01-01 → 2026-11-13) | 12302 (2024-11-18 → 2026-11-13) | 10.0 |
| USDDKK | USD_DKK | USDDKK=X | 2310 (2018-01-01 → 2026-11-15) | 12138 (2024-11-18 → 2026-11-13) | 10.0 |
| USDHUF | USD_HUF | USDHUF=X | 2309 (2018-01-01 → 2026-11-13) | 12300 (2024-11-18 → 2026-11-13) | 10.0 |
| USDNOK | USD_NOK | USDNOK=X | 2310 (2018-01-01 → 2026-11-15) | 12208 (2024-11-18 → 2026-11-13) | 10.0 |
| USDPLN | USD_PLN | USDPLN=X | 2309 (2018-01-01 → 2026-11-13) | 12331 (2024-11-18 → 2026-11-13) | 10.0 |
| USDTHB | USD_THB | USDTHB=X | 2309 (2018-01-01 → 2026-11-13) | 12128 (2024-11-18 → 2026-11-13) | 10.0 |
| ZARJPY | ZAR_JPY | ZARJPY=X | 2309 (2018-01-01 → 2026-11-13) | 12278 (2024-11-18 → 2026-11-13) | 10.0 |
| AU200 | AU200_AUD | ^AXJO | 2247 (2018-01-01 → 2026-11-13) | 3518 (2024-11-17 → 2026-11-13) | 8.0 |
| CH20 | CH20_CHF | ^SSMI | 2216 (2018-01-03 → 2026-11-13) | 4459 (2024-11-18 → 2026-11-13) | 8.0 |
| CHINAH | CHINAH_HKD | ^HSCE | 2182 (2018-01-02 → 2026-11-13) | 3394 (2024-11-18 → 2026-11-13) | 8.0 |
| ESPIX | ESPIX_EUR | ^IBEX | 2269 (2018-01-02 → 2026-11-13) | 4493 (2024-11-18 → 2026-11-13) | 8.0 |
| EU50 | EU50_EUR | ^STOXX50E | 2228 (2018-01-03 → 2026-11-13) | 4460 (2024-11-18 → 2026-11-13) | 8.0 |
| FR40 | FR40_EUR | ^FCHI | 2271 (2018-01-02 → 2026-11-13) | 4546 (2024-11-18 → 2026-11-13) | 8.0 |
| HK33 | HK33_HKD | ^HSI | 2182 (2018-01-02 → 2026-11-13) | 3394 (2024-11-18 → 2026-11-13) | 8.0 |
| NL25 | NL25_EUR | ^AEX | 2271 (2018-01-02 → 2026-11-13) | 4545 (2024-11-18 → 2026-11-13) | 8.0 |
| SG30 | SG30_SGD | ^STI | 2227 (2018-01-02 → 2026-11-13) | 3964 (2024-11-18 → 2026-11-13) | 8.0 |
| PALLADIUM | XPD_USD | PA=F | 2230 (2018-01-02 → 2026-11-13) | 11388 (2024-11-17 → 2026-11-13) | GAP — no costs2 entry |
| CORN | CORN_USD | ZC=F | 2229 (2018-01-02 → 2026-11-13) | 9269 (2024-11-18 → 2026-11-13) | GAP — no costs2 entry |
| SOYBN | SOYBN_USD | ZS=F | 2231 (2018-01-02 → 2026-11-13) | 9271 (2024-11-18 → 2026-11-13) | GAP — no costs2 entry |
| SUGAR | SUGAR_USD | SB=F | 2233 (2018-01-02 → 2026-11-13) | 4855 (2024-11-18 → 2026-11-13) | GAP — no costs2 entry |
| WHEAT | WHEAT_USD | ZW=F | 2231 (2018-01-02 → 2026-11-13) | 9266 (2024-11-18 → 2026-11-13) | GAP — no costs2 entry |

## Reading the inventory (per class)

- **FX crosses/minors/exotics (41).** Uniform depth: 1d 2,309–2,311 bars
  (2018-01-01 → 2026-11-13/15, 4–6 grid-missing bars — holidays), 1h
  12,054–12,361 bars (2024-11-18 → 2026-11-13; the 1h gap count ~5,100–
  5,300 is weekends/holidays/outages combined, per the RD-002 grid
  note). Derived 4h/1wk follow the harness resample rules. Fold
  profiles: 1d STANDARD (W1–W5), 1h/4h LATE (W2–W5). Cost: costs2
  FX_MINOR = **10 bps round trip** for every pair in this class.
  Suggested RD-003 panel: `forex_cross41` at 1d + 1h/4h — this more than
  doubles the forex universe RD-003's Stage-2B could draw on (forex28
  was daily-only beyond the 12 majors).
- **Index CFDs (9).** Cash-index tickers, the idx7 precedent. Daily
  2,182–2,271 bars from 2018-01. Hourly bars exist **only for local
  session hours** (3,394–4,546 bars) — the 1h missing count includes
  every non-session hour by construction. Daily is the primary judging
  timeframe; 1h suits session-bounded logic only (RD-008 precedent).
  Cost: costs2 INDEX = **8 bps round trip**.
- **Palladium (XPD_USD).** COMEX front-month futures proxy (PA=F), the
  comm7 precedent — futures basis and contract-roll steps are embedded
  and disclosed. Daily 2,230 bars from 2018-01-02; 1h usable but 3,124
  null rows dropped (~22%) — CAUTION at 1h. **Cost GAP:** costs2 has no
  PALLADIUM entry (platinum's 14 bps is an analogue, not adopted). No
  palladium cell may be judged until RD-003 adds a measured cost.
- **Soft commodities (CORN/SOYBN/SUGAR/WHEAT).** CBOT/ICE front-month
  futures proxies for the OANDA CFDs, same disclosure as palladium.
  Daily is clean (2,229–2,233 bars from 2018-01-02). Hourly is
  session-bound and null-heavy: CORN/SOYBN/WHEAT dropped ~5,200 null
  rows each; **SUGAR dropped 9,615 of 14,436 payload rows (~2/3) —
  daily only for sugar; 1h CAUTION for the other three.** **Cost GAP:**
  costs2 has no soft-commodity entries at all; nothing is invented here.

## Uncovered / derived-only — stated plainly

| Category | Status | Why |
|---|---|---|
| CN50_USD (China A50) | UNCOVERED | No verified Yahoo ticker for the FTSE China A50 index (`^FTSE` is the FTSE 100, already in idx7). Not approximated. OANDA-native candles are the only honest source. |
| Bond CFDs (DE10YB_EUR, UK10YB_GBP, USB02Y/05Y/10Y/30Y_USD) | UNCOVERED | Yahoo yield indices are not the CFD price series; bond-futures proxies embed roll and cheapest-to-deliver effects. No honest series from this sandbox; not recommended as a research track without a native pull. |
| Metal crosses (19: XAU_*/XAG_* crosses + XAU_XAG) | DERIVED_ONLY | No direct Yahoo spot tickers. Each cross is arithmetically implied by provenanced legs (XAU_USD/XAG_USD + the FX cross). RD-003 may construct them only with the derivation disclosed per series, or pull OANDA-native candles. Not counted as independently verified. |
| JP225Y_JPY | NOT_NEW | JPY twin of JP225_USD; the Nikkei underlying is already covered at 1d in idx7 (NIKKEI). |
| OANDA-native candles (all instruments) | ACCOUNT_CONFIRMED_FX_ONLY | TASK-STR-FWD-003 verified the owner's practice account live (twice, independently, 2026-11-15): 68 instruments, ALL FX pairs — no commodities/metals/indices/bonds. Remaining server-side steps: (1) diff the 68 against this inventory's 41 new pairs + RD-002's 28 (counts imply at most one pair differs); (2) resolve the XAUUSD thread (the `oanda_demo` engine watchlists it, which sits oddly with an FX-only list); (3) native bid/ask/mid candle history still needs the server-side practice token — research crews do not pull venue credentials. |

## What this hands to TASK-STR-RD-003

1. A ready panel definition: **forex_cross41** (41 pairs × 1d STANDARD +
   1h/4h LATE, 10 bps RT) — the forex-native track no longer needs to
   wait for data or reuse the majors.
2. A secondary panel: **idx_exp9** daily (8 bps RT) for index families
   beyond RD-008's SPX/NDX scope.
3. Two explicit preconditions before palladium/softs cells are declared:
   measured costs2 entries (from OANDA practice pricing, server-side)
   and, for sugar, daily-only judging.
4. Nothing in this inventory is a strategy claim. Trial counts are
   unaffected (0 trials run). Every series still faces the standing bar
   and live OANDA forward evidence before it can be called proven.

## Limits of this inventory

- Yahoo FX quotes are composite indicative quotes — the same caveat
  RD-002 carried for forex12/forex28; spreads are modelled (costs2),
  not measured from the venue. The server-side native pull above is
  the fix when a family survives to forward testing.
- Futures-proxy series (palladium, softs) embed roll steps; a family
  that is sensitive to single-day jumps must treat roll windows as a
  known artefact source.
- Account-specific tradeability is now partly settled: the owner's
  practice account is FX-only (68 instruments, FWD-003-verified), so
  the non-FX series here are research data, not tradeable instruments,
  until a venue offers them. Pair-level membership of the 68 vs this
  inventory is the one diff still owed server-side.
