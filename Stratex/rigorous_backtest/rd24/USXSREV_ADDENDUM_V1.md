# DECLARATION ADDENDUM v1 — RD-024 (us_xs_reversal, TASK-STR-RD-024): gate check 2 — the absolute volume floor is replaced by a relative SIP-vs-IEX feed discriminator

**STATUS: FROZEN on creation, before any run under this addendum and
before any OOS trade is computed.** This addendum is a delta on the
frozen declaration `usxsrev_declaration.json` (SHA-256
`505fdf155c63ac019e957acc7eb76f4ac6bf2d3bacbbb04b1b65b38314e2eb4f`,
PR #904, merged). The declaration file is NOT edited — not one byte.
Everything in it carries over verbatim except the single element §2
below amends: the definition of data-gate check 2 (`sip_feed_check`).
§5 enumerates every other frozen element and states its disposition
individually. The runner change that enforces the amended check
mechanically ships in the same PR as this addendum (§4); the frozen
declaration's own hash-pin is untouched, and the runner still refuses
(exit 2, zero trials) unless every gate verifies.

**What this addendum changes — one sentence.** Gate check 2's test —
"every symbol's median daily share volume over the span >=
2,000,000" — is replaced by a relative discriminator: every symbol's
SIP median daily volume must be at least **5.0×** the same symbol's
IEX median daily volume over the identical span, and the universe
aggregate ratio must also be at least **5.0×** (§3).

---

## 1. Why the change is needed (evidence chain, all records on file)

(i) The declaration froze the floor as a feed discriminator, in its
own words. Declaration JSON, `data_plan.gate_5_checks[1]`: "2. SIP
feed check: every symbol's median daily share volume over the span
>= 2,000,000 shares (panel-level form of the SRS SIP-vs-IEX check)."
USXSREV_DECLARATION.md, gate 2: the floor is one "every name in this
universe clears by a wide margin on the consolidated tape and that
an IEX-only pull would fail for most names; this is the panel-level
form of the SRS SIP-vs-IEX check." And `data_plan.source`: "feed=sip
(consolidated CTA+UTP tape; IEX carries ~2.7% of consolidated volume
and is rejected)". The floor's stated purpose is feed discrimination
— SIP vs IEX. Universe selection is a separate frozen rule
(`universe.selection_rule`: ~$100B market capitalisation at
2022-12-30, continuous S&P 500 membership, continuous listing; "The
frozen ticker list is the binding artefact"). The floor is not a
liquidity condition and was never stated as one.

(ii) Staging on genuine SIP data falsified the MD's empirical
premise. The staged panel (S1 `/var/tmp/rd024/panel/`, pulled from
Alpaca with feed=sip, adjustment=split over the declared span;
staging record `~/workspace/runprep-rd024/STAGING_STATE.md`) passes
session census (961 bars × 30 symbols, zero shortfalls) and the
split check, and the shipped runner's own `load_and_verify` confirms
feed, adjustment, span, universe and both file hashes verify clean.
But COST's true median daily volume on that genuine SIP panel is
**1,903,349** shares — below the frozen 2,000,000 floor. All 29
other symbols pass (next-lowest MA = 2,554,862). The median was
computed identically three ways (staging statistics.median, pandas
median on S1, and the runner's mechanical check, which refuses on
the same symbol). COST is simply a ~1.9M-median-volume stock over
2023–2026: the floor was set as an IEX discriminator without
checking the lowest-volume universe member's real SIP median. Under
the declaration as frozen, a genuine SIP panel can never pass
gate 2 — the gate rejects the very feed it exists to certify.

(iii) The replacement is measured, not asserted. A comparison pull
identical to the staged SIP pull except `feed=iex` was executed
(2026-11-17, S1, same key pair, same span; every symbol returned
exactly 961 bars — the same session set). Per-symbol SIP/IEX
median-daily-volume ratios: minimum **22.54** (ACN), maximum
**121.10** (TSLA); COST **33.94** (SIP 1,903,349 / IEX 56,082 — the
SIP figure reproduces the staging record exactly). Universe
aggregate ratio (sum of SIP medians / sum of IEX medians) =
**47.58**. The full measured table is Appendix A.

## 2. The frozen check 2 (for reference — superseded by §3)

Declaration `data_plan.gate_5_checks[1]`, verbatim: "2. SIP feed
check: every symbol's median daily share volume over the span >=
2,000,000 shares (panel-level form of the SRS SIP-vs-IEX check)."
Executable form in the shipped runner: `VOLUME_FLOOR_MEDIAN =
2_000_000`, enforced mechanically in `load_and_verify`.

## 3. Check 2 as amended (the replacement discriminator, frozen)

**Amended gate check 2 — SIP feed check (relative form).** The panel
dir must additionally carry `iex_panel.csv`: the identical Alpaca
request as the SIP panel (same 30 symbols, timeframe 1Day, same
start/end, adjustment=split) with `feed=iex`, its SHA-256 recorded
in `provenance.json` as `iex_panel_sha256`. The check passes if and
only if ALL of the following hold, computed on the staged files:

- (a) `iex_panel.csv` exists and its SHA-256 equals
  `provenance.json`'s `iex_panel_sha256`;
- (b) for every symbol, the IEX panel's bar count equals the SIP
  panel's bar count for that symbol (identical session sets — the
  medians must be computed over the same sessions);
- (c) for every one of the 30 symbols, `median_SIP(symbol) /
  median_IEX(symbol) >= 5.0`, where each median is the median of
  daily share volume over that symbol's sessions in the span;
- (d) the universe aggregate `(Σ median_SIP) / (Σ median_IEX) >=
  5.0` over the 30 symbols.

**Factor justification (frozen with the check).** The failure mode
this gate exists to catch is a panel that is actually IEX data (or
an IEX-dominated pull) presented as SIP. Such a panel scores a
ratio of ≈ 1.0 on every symbol by construction — it fails (c) on
30/30 symbols, where the frozen absolute floor would have failed it
on only 29/30 (NVDA's measured IEX median, 3,921,000, clears
2,000,000). Genuine SIP data measures 22.54–121.10 per symbol
(Appendix A), so the factor 5.0 sits 5× above the failure case and
4.5× below the weakest genuine name — it separates the feeds with
margin on both sides, and its discrimination strength against the
gate's stated target is at least equal to the frozen floor's. The
aggregate leg (d) additionally catches a mixed-feed panel in which
a minority of symbols came from the wrong feed at scale. The
per-symbol medians and ratios actually computed at run time are
recorded in `provenance.json`'s `gate_detail`, so the recorded
"pass" is backed by data in the same record.

**Run-lane computation (binding).** Stage `iex_panel.csv` beside
`panel.csv` with the request above; record `iex_panel_sha256` in
`provenance.json`; the runner (§4) recomputes (a)–(d) mechanically
from the staged files — a recorded "pass" alone is never sufficient.
The raw IEX panel is staging data like the SIP panel: never
committed to the public repo; only the provenance record is
committable, per the declaration's `licence_handling`.

## 4. Runner disposition

`run_usxsrev.py` ships in this addendum's PR with exactly one
behavioural change: the mechanical enforcement of gate check 2 in
`load_and_verify` now implements §3 (constant `FEED_RATIO_MIN =
5.0`) instead of the frozen absolute floor; the module docstring's
panel-dir contents line names `iex_panel.csv`. The declaration file
is not in the diff. The gate key in `provenance.json` remains
`sip_feed_check` — it is the check's definition that this addendum
amends, not its identity. Regression tests in `test_usxsrev.py`
cover: the amended check passing on a SIP-scale synthetic panel with
its IEX companion; refusal when `iex_panel.csv` is missing; refusal
when its hash does not match the provenance record; refusal when the
panel presented as SIP is at IEX scale (ratios ≈ 1).

## 5. What does NOT change (each element, individually)

- **Universe:** the frozen 30-name list (AAPL ABBV ACN AMD AMZN AVGO
  BAC COST CRM CVX GOOGL HD JNJ JPM KO LLY MA META MCD MRK MSFT NFLX
  NVDA PEP PG TSLA UNH V WMT XOM) — unchanged; no name is added,
  dropped, or substituted. COST remains in the universe and in both
  cells.
- **Cells:** exactly two — `rev5_r5` and `rev10_r5` — unchanged.
- **Costs:** the programme cost model (16 bps round trip at 1x;
  identical simulation at 32 bps for the 2x shadow) and the declared
  borrow charge (0.0025 ACT/360, shorts only, unchanged at 1x and
  2x) — unchanged.
- **Judging bar:** `evaluation_bar` in full (OOS-only judgement,
  folds, holdout, cost-shadow conditions, Bonferroni at the final
  counter read fresh from the rd-reconcile ledger at run time) —
  unchanged.
- **Trial accounting:** exactly 2 trials (`cells_added: 2`) —
  unchanged. This addendum consumes no trial; a panel that fails
  verification consumes zero trials, per the frozen `gate_rule`.
- **Holdout single-evaluation clause:** the W5 holdout is evaluated
  exactly once (frozen run procedure step 5: "evaluate H (H1-H4)
  exactly once") — unchanged; nothing in this addendum touches,
  previews, or burns the holdout.
- **Gates 1, 3, 4, 5:** definitions unchanged (session census;
  split check; cross-source spot check vs Yahoo Finance daily;
  dividend calendar check vs Yahoo dividend history). The gate rule
  — ALL five checks must pass before any backtest — is unchanged.
- **Span, primary feed, adjustment:** 2023-01-01 → 2026-11-01 (UTC)
  requests; the primary panel remains feed=sip, adjustment=split —
  unchanged. The IEX pull is a comparison artefact for gate 2 only;
  it is never simulated on.
- **The declaration file:** byte-identical (SHA-256
  `505fdf155c63ac019e957acc7eb76f4ac6bf2d3bacbbb04b1b65b38314e2eb4f`).

## 6. Gates 4–5 remain outstanding (the run stays blocked)

At the time of this addendum, gate 4 (cross-source spot check) and
gate 5 (dividend calendar check) are **NOT COMPUTED**: Yahoo Finance
was unreachable from the staging environment (HTTP 429 on both chart
hosts; the browser fetch path is tool-policy-blocked — staging
record, `~/workspace/runprep-rd024/STAGING_STATE.md`). They remain
mandatory exactly as declared. `provenance.json` carries
"not_computed" for both, the runner refuses (exit 2), and the
declared run remains blocked until the run lane computes both
against the panel of record (§7) and they pass. No gate may be
marked "pass" without its computation.

**Gate-5 computation note (carried from the staging record).** The
staged dividend calendar is built from Alpaca corporate-actions
announcements, whose amount field is named **`rate`** (no
`cash_amount` key exists), and whose amounts are **as-declared, not
split-adjusted** (e.g. NVDA $0.04 pre-split → $0.01 at the
2024-06-11 post-split ex-date; WMT $0.57 pre-split). If Yahoo's
dividend events serve split-adjusted historical amounts, pre-split
NVDA/WMT/AVGO samples will differ by the split factor — a systematic
basis difference the run lane must surface and resolve explicitly
when computing gate 5, not sample around.

## 7. Panel of record (frozen by the staging record)

Staged on S1 at `/var/tmp/rd024/panel/`:

- `panel.csv` — SHA-256
  `b0fbdd44f99253d014e326acff6ecf6ebc6b21a7a130f0590552170ef1047e01`
  (28,830 bars = 30 × 961; a second full pull reproduced this hash
  byte-identically).
- `dividends.csv` — SHA-256
  `74f269b879f078179e08958d9c1ed54c1a1a2d8a2a7896a06f225b60b51d0547`
  (378 in-span cash dividends across 26 paying symbols).

Gates 4–5, when computed, are computed against these files. Any
re-pull that changes either hash is a new panel and must be recorded
as such before use.

---

## Appendix A — Measured SIP vs IEX medians (2026-11-17, S1)

Identical Alpaca requests, feed=sip (the staged panel of record)
vs feed=iex; 961 bars per symbol in both pulls. IEX medians are the
measured values; ratios are SIP median ÷ IEX median (2 dp). SIP
medians are recorded in full in the staging provenance's
`gate_detail`; COST's SIP median (1,903,349) is stated in §1.

| Symbol | IEX median daily vol | SIP/IEX ratio |
|---|---|---|
| AAPL | 1,049,899 | 47.70 |
| ABBV | 165,278 | 31.52 |
| ACN | 131,028 | 22.54 |
| AMD | 706,774 | 63.90 |
| AMZN | 1,077,839 | 39.63 |
| AVGO | 704,780 | 33.04 |
| BAC | 1,392,614 | 26.42 |
| COST | 56,082 | 33.94 |
| CRM | 253,252 | 25.96 |
| CVX | 215,156 | 36.24 |
| GOOGL | 775,312 | 37.33 |
| HD | 116,926 | 29.33 |
| JNJ | 219,027 | 33.38 |
| JPM | 198,902 | 42.78 |
| KO | 448,081 | 31.20 |
| LLY | 104,375 | 27.35 |
| MA | 109,816 | 23.26 |
| META | 370,448 | 42.24 |
| MCD | 104,559 | 29.33 |
| MRK | 295,766 | 30.63 |
| MSFT | 483,078 | 47.79 |
| NFLX | 1,285,260 | 29.43 |
| NVDA | 3,921,000 | 67.57 |
| PEP | 176,255 | 34.13 |
| PG | 204,524 | 33.89 |
| TSLA | 764,488 | 121.10 |
| UNH | 168,670 | 26.15 |
| V | 204,072 | 29.14 |
| WMT | 525,495 | 32.11 |
| XOM | 414,463 | 37.30 |

Universe aggregate ratio: **47.58**. Minimum per-symbol ratio:
**22.54** (ACN).
