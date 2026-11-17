# DECLARATION ADDENDUM v1 — RD-022 (oi_surge_follow, TASK-STR-RD-022): the monthly-archive 120-bar hole — enumerated daily-archive supplementation for 11 symbols

**STATUS: FROZEN on creation, before the declared run under this
addendum and before any OOS trade is computed.** This addendum is a
delta on the frozen declaration `oi_declaration.json` (SHA-256
`6368711d5fcef1541b6af49a1d2f48f5b0caafe9b8f6f9109bdd9e7ca3aaecf8`,
PR #902, merged). The declaration file is NOT edited — not one byte.
Everything in it carries over verbatim except the single element §3
below amends: the permitted construction of the kline panel. §5
enumerates every other frozen element and states its disposition
individually. **No code ships with this addendum** (§4): the frozen
runner, loader, harness and tests stay byte-identical, and the
runner's gap abort remains in force for any panel not built exactly
per §3.

**What this addendum changes — one sentence.** For the 11 named
symbols, the kline panel may be completed with exactly the 120 bars
per symbol that Binance Vision's monthly archive itself lacks —
taken from Binance Vision's daily klines archive under
checksum admission, fully enumerated in the run record (§3) —
and nothing else changes.

---

## 1. Why the change is needed (evidence chain, all records on file)

(i) **The declaration froze monthly sourcing as a source
description, and prescribed STOP-and-report for deviations.**
Declaration, Data plan — Klines: "Binance Vision monthly klines
through the programme's verified loader — the same source and
loader as the RD panels (1h base, resampled to 4h/1d per
`rd/common.load_timeframe`)." The declaration JSON's `data_plan`
says the same ("— the same source and loader as the RD panels").
No purpose is stated for monthly granularity itself — no
anti-cherry-picking rule, no consistency-of-source rationale; the
purposes stated are verification (the verified loader, the
checksum/manifest discipline) and continuity with prior RD panels.
The panel verification gate continues: "A symbol with > 1% of its
daily metrics files missing in the span is excluded **by this
rule** and the exclusion is reported in the run record — it is not
a post-hoc choice. Any other deviation: STOP and report; never
patch, fill or substitute data." That sentence governs the run's
conduct on meeting a deviation — stop and report, never improvise
a fix — and it was obeyed exactly: panel pre-staging stopped,
reported, and built no workaround (record:
`~/workspace/runprep-rd022-staging/STAGING_STATE.md`). This
addendum is that report's outcome: the programme's amendment
route (precedent: SRS addendum v4, PR #906; RD-024 addendum v1),
decided before any run, disclosed in full, frozen narrowly. The
declaration's "never interpolated" clause (Percentile
construction: "bars failing it are silent, never interpolated")
bars synthetic values in the rank window; §3 inserts only real,
checksum-verified archive bars — nothing is interpolated,
filled with synthetic values, or substituted from another source.

(ii) **The hole is in Binance Vision's monthly archive itself —
proven, not inferred.** Panel pre-staging verified the programme
loader's cache (`~/workspace/str-rd2/cache2`, the same monthly
build any fresh `load_dataset` run reproduces) three ways per
symbol — sidecar hash, identity, and an independent gap-audit
recompute from the CSV bytes:

- 14/25 symbols are complete: 42,360 rows, `missing_bars = 0`,
  span 2022-01-01T00:00Z → 2026-10-31T23:00Z.
- 11/25 symbols — **SOLUSDT, XRPUSDT, LTCUSDT, TRXUSDT, NEARUSDT,
  FILUSDT, XLMUSDT, HBARUSDT, VETUSDT, SANDUSDT, MANAUSDT** — each
  carry 42,240 rows with exactly **120 missing bars** in the same
  two spans (sidecar `gap_audit.gap_spans`, identical in form for
  every affected symbol): 72 bars after 2022-02-25T23:00:00+00:00
  and before 2022-03-01T00:00:00+00:00 (i.e. bar open times
  2022-02-26T00:00Z → 2022-02-28T23:00Z), and 48 bars after
  2022-03-31T23:00:00+00:00 and before 2022-04-03T00:00:00+00:00
  (open times 2022-04-01T00:00Z → 2022-04-02T23:00Z). The sidecars
  record the hole honestly (`missing_bars = 120`); nothing was
  patched at staging.
- The February hole is proven **in the archive, first-hand**
  (2026-11-17, in-memory fetches admitted only on complete
  Content-Length bodies): `SOLUSDT-1h-2022-02.zip` — 25,915 B,
  SHA-256 `36b1e2ff3ffe162718e61bb23ef84a104dc2cc5591c18cd8ce4c04e96655b84c`,
  600 rows spanning Feb 1–25 only; `XRPUSDT-1h-2022-02.zip` —
  29,704 B, SHA-256 `00f9537c6a7518307e24e5ab539cab76fadca6d07550eb1e0f68de915d985d63`,
  600 rows, Feb 1–25 only. A passing symbol's archive is complete:
  `BTCUSDT-1h-2022-02.zip` — 35,964 B, SHA-256
  `b3a199287b2a8fed2c261999205d56cfd72ef9675c4b498a399601978d666228`,
  672 rows including Feb 26/27/28. The staged cache's recorded
  `zip_sha256` values (built 2026-11-14) match today's fetched
  archive bytes exactly for every probed zip, so the hole is in
  the source, not in our copy: a fresh monthly build anywhere
  produces the same `missing_bars = 120`.
- The April hole is attested by every affected symbol's sidecar
  `gap_spans` from that same 2026-11-14 archive build, whose
  provenance continuity with today's archive is proven by the
  February zips above. A direct re-fetch of
  `SOLUSDT-1h-2022-04.zip` on 2026-11-17 failed 8/8 attempts on
  egress truncation (a 28,601 B body cut at ~17 KB), so the April
  span is recorded here as sidecar-attested, not re-fetched —
  stated plainly. §3's construction rules make any error in that
  attestation surface before any backtest: supplementation is
  defined by the monthly build's actual gap audit against a
  frozen expectation, and every supplemented zip must pass
  checksum admission.

(iii) **The frozen runner's abort is correct behaviour — and, as
frozen, final.** `run_oi_surge.py` aborts (exit 2) whenever a
panel manifest's `gap_audit.missing_bars != 0`. Against the
frozen text that abort is right; its consequence is that RD-022
can never pass its own panel gate for these 11 symbols from the
declared monthly source. The missing bars do exist in Binance
Vision's **daily** klines archive: the staging crew fetched
SOLUSDT's daily zip for 2022-02-26 complete (24 bars). This
addendum — not a staging workaround, not a runner patch — is the
only route by which they may be used.

## 2. The frozen panel clauses (for reference — supplemented by §3)

Declaration, panel verification gate (verbatim): "For every
universe symbol the run verifies: every daily metrics file in the
panel span downloads and its SHA-256 matches the published
`.CHECKSUM`; a manifest of file hashes is recorded; klines load
through the programme's verified loader (`data_feed.load_dataset`,
months 2022-01..2026-10)."

Declaration, Data plan — Klines (verbatim): "Binance Vision
monthly klines through the programme's verified loader — the same
source and loader as the RD panels (1h base, resampled to 4h/1d
per `rd/common.load_timeframe`)."

§3 supplements the second clause's construction for the 11 named
symbols only. The first clause's verification discipline
(checksums, manifest, the loader) is not relaxed in any way — §3
extends the same discipline to the supplemented files.

## 3. The remedy (frozen)

**Amended kline-panel construction.** Each universe symbol's 1h
panel is built from the Binance Vision monthly archives exactly
as the programme loader builds it. Supplementation of that build
is permitted if and only if ALL of the following hold:

- (a) **Scope.** Supplementation applies only to the 11 symbols
  named in §1(ii) (SOLUSDT, XRPUSDT, LTCUSDT, TRXUSDT, NEARUSDT,
  FILUSDT, XLMUSDT, HBARUSDT, VETUSDT, SANDUSDT, MANAUSDT), only
  to bars the monthly build lacks, and only within the two spans
  of §1(ii): open times 2022-02-26T00:00Z → 2022-02-28T23:00Z
  (72 bars per symbol) and 2022-04-01T00:00Z → 2022-04-02T23:00Z
  (48 bars per symbol) — 120 bars per symbol, **1,320 bars in
  total**, sourced from 5 daily zips per symbol (dates
  2022-02-26, 2022-02-27, 2022-02-28, 2022-04-01, 2022-04-02;
  55 zips in total). NO other bar may come from the daily
  archives; monthly remains the source for everything else.
- (b) **Source.** Supplemented bars come only from Binance
  Vision's daily klines archive — the same archive family as the
  monthly klines: `https://data.binance.vision/data/futures/um/daily/klines/<SYM>/1h/<SYM>-1h-<YYYY-MM-DD>.zip`.
  No other source, mirror, exchange or vendor may supply a
  supplemented bar.
- (c) **Admission.** Every supplemented zip is admitted only when
  its body is complete (served Content-Length satisfied) AND its
  SHA-256 equals the first field of its published `.CHECKSUM`
  sidecar (`<zip URL>.CHECKSUM`) — the same admission rule the
  declaration already imposes on the metrics files. A zip that
  fails admission is not used, in whole or in part.
- (d) **Frozen expectation — STOP rule.** The monthly build's gap
  audit is expected to reproduce §1(ii) exactly: the same 11
  symbols, the same two spans, 120 missing bars each, and no
  other symbol or span short. If the actual gap audit differs in
  ANY way — a different symbol, span or count, or a daily zip
  failing (c) — STOP and report. This addendum authorizes no
  supplementation beyond the frozen expectation, and no
  discretion to extend it.
- (e) **Merge discipline.** The merged series is strictly
  timestamp-ordered with no duplicate bar: a supplemented
  timestamp that duplicates a monthly bar aborts construction
  (STOP and report, per (d)). The merged CSV keeps the loader's
  canonical format unchanged. After merging, the gap audit is
  recomputed independently over the merged series and must read
  `expected_bars = 42,360`, `actual_bars = 42,360`,
  `missing_bars = 0` for every universe symbol — the 14
  unaffected symbols reach the same figures from monthly alone,
  untouched.
- (f) **Provenance.** Supplemented panels are built into a NEW
  panel directory. The monthly-only staged panel
  (`~/workspace/runprep-rd022-staging/panel/`) is preserved
  untouched as the evidence of the declared-source build; its
  sidecars are never edited in place. Each supplemented symbol's
  new sidecar keeps the loader's fields truthful — `csv_sha256`
  of the merged CSV, `rows = 42,360`, the recomputed `gap_audit`,
  and the monthly build's `zip_sha256` map retained — and adds a
  top-level `supplementation` block recording: this addendum's
  identity (OI_ADDENDUM_V1), the daily zips used (file name, byte
  size, SHA-256 — the values admitted under (c)), and the
  supplemented bar count (120).
- (g) **Run-record enumeration.** The run's record must enumerate
  the supplemented set — every (symbol, timestamp) pair, all
  1,320 — and must state that kline provenance is monthly plus
  this addendum's enumerated daily supplementation,
  notwithstanding the runner's hardcoded `klines_source` string
  ("binance_vision_futures_um_monthly_klines via
  rigorous_backtest.data_feed.load_dataset"), which the frozen
  runner writes into `results.json` unchanged. The completion
  comment on issue #35 carries the same disclosure. A run whose
  record lacks the enumeration is non-compliant and does not
  count as the declared run.

## 4. Runner disposition

**No code change.** This addendum's PR adds this file only.
`run_oi_surge.py`, `oi_surge.py`, `metrics_feed.py`,
`data_feed.py` and `test_oi_surge.py` are not in the diff and must
remain byte-identical to the frozen pins (final gate re-check,
`~/workspace/runprep-rd022/GATE_RECHECK.md`: runner SHA-256
`7be27c6a…`, harness `7462df7a…`, metrics loader `3310b88a…`,
tests `1371f4a9…`). The declaration hash-pin is untouched: the
runner re-verifies `oi_declaration.json`'s SHA-256 from the
checkout before anything else and aborts (exit 2) on mismatch.
The gap abort also stands exactly as frozen: a panel presented to
the run that was not built per §3 — in particular any panel whose
manifest reads `missing_bars != 0`, or whose supplementation is
not recorded per §3(f) — aborts the run, and that abort is the
correct outcome.

## 5. What does NOT change (each element, individually)

- **Universe:** the 25 declared symbols (BTCUSDT, ETHUSDT,
  SOLUSDT, BNBUSDT, XRPUSDT, DOGEUSDT, ADAUSDT, LTCUSDT, LINKUSDT,
  DOTUSDT, TRXUSDT, AVAXUSDT, NEARUSDT, ATOMUSDT, UNIUSDT,
  ETCUSDT, BCHUSDT, FILUSDT, XLMUSDT, HBARUSDT, ALGOUSDT, VETUSDT,
  SANDUSDT, MANAUSDT, AAVEUSDT) and the 5 excluded by the same
  mechanical rule (OPUSDT, INJUSDT, APTUSDT, ARBUSDT, SUIUSDT) —
  unchanged; no symbol is added, dropped or substituted, and no
  symbol is excluded over the kline hole.
- **Cells:** exactly two — 4h and 1d — unchanged.
- **Panel span:** 2022-01-01 → 2026-10-31 for both klines and
  metrics — unchanged.
- **Costs:** the programme cost model (crypto 16 bps round trip)
  and the 2×-cost shadow (32 bps), both passing — unchanged.
- **Gap and missing-data semantics:** the kline abort on
  `missing_bars != 0` and `MAX_MISSING_FRACTION = 0.01` (the
  metrics leg's exclusion rule) remain exactly as frozen for
  everything outside §3's enumerated supplemented set. After §3
  supplementation the panel must be complete; any residual or
  additional gap aborts the run.
- **Judging bar:** the declaration's bar in full (per-cell pooled
  OOS expectancy_net > 0 and PF_net ≥ 1.2 strict; ≥ 200 OOS
  trades; ≥ 4 of 5 folds positive; both cost levels passing;
  `rd.common.holdout_check`; Bonferroni p < 0.05/N; the
  "insufficient OOS trades" verdict form; strict PF < 1.2 closes
  a cell, both cells failing closes the family) — unchanged.
- **Trial accounting:** exactly 2 trials (one per cell), both
  cells judged at the final N = entering programme counter + 2,
  the counter read fresh from the programme ledger at run time —
  unchanged. This addendum consumes zero trials.
- **Single evaluation:** exactly one declared run (the runner
  refuses, exit 2, if the output `RESULTS.md` already exists) —
  unchanged; nothing in this addendum previews or burns any part
  of the evaluation.
- **Signal, gates and conventions:** the exact rules, the
  percentile construction (including "never interpolated" for
  values the archive does not contain — §3 supplies only bars
  the archive DOES contain, in its daily form), the asof
  discipline, the ≥ 95% window-coverage gate, and the declared
  exclusions (no OI-collapse tail, no positioning ratios, funding
  never an input) — unchanged.
- **Metrics sourcing:** unchanged — see §6.
- **The declaration file:** byte-identical (SHA-256
  `6368711d5fcef1541b6af49a1d2f48f5b0caafe9b8f6f9109bdd9e7ca3aaecf8`).

## 6. The metrics leg (stated plainly)

No metrics cache exists locally: the staging census found no
pre-existing metrics cache in any searched location, and the
post-close workspace-wide find confirmed zero `*-metrics-*.zip`
files exist anywhere under the workspace. The run therefore
fetches metrics live via `metrics_feed`, exactly as declared —
which verifies every file against its published `.CHECKSUM` at
load time, cache hit or miss, and applies the declared > 1%
missing-files exclusion rule per symbol. **This addendum does not
change metrics sourcing in any way.** Pre-staging the metrics
cache (44,125 daily zips) remains a speed/reliability
optimisation for a later crew, per the recipe in the staging
record; it is not a gate and not part of this addendum.

## 7. Standing items not touched

The final gate re-check's documentation flag — the five excluded
symbols' first-file dates printed in the declaration's prose are
each later than the archive's true first file (OP 2022-06-01,
INJ 2022-08-17, APT 2022-10-19, ARB 2023-03-23, SUI 2023-05-03);
every true date is still after the 2022-01-01 cutoff, so no
symbol changes side — keeps its standing handling: recorded in
the run's RESULTS, the frozen declaration not edited. This
addendum does not amend it.

**Status:** the declared run remains NOT RUN and waits its turn
in the declared queue. This addendum is effective only when
merged; the run lane builds the supplemented panel per §3 at
RD-022's turn, and the trial floor is read fresh at that time.
