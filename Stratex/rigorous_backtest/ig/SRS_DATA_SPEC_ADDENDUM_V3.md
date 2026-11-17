# DATA-SPEC ADDENDUM v3 — SRS (TASK-IG2-STR-14): check-4 cross-source instrument

**STATUS: FROZEN — 2026-11-17, before the panel is downloaded and
before any OOS trade is computed.** This addendum's SHA-256 is stated
in its freeze PR and on issue #35 (it is not embedded in this file).
It takes effect under the discipline the TEMPORAL HOLDOUT v1 addendum
followed: declared and hash-frozen before any data is judged. The
frozen cross-source file it names exists, is hash-pinned in §3.2, and
passed the §3.4 validation battery before this freeze (§4 records each
freeze condition and its evidence).

**What this addendum changes — one sentence.** In the 5-point
verification of PROVENANCE.md §3.5, check 4's cross-source *instrument*
(the reference daily file the panel's sampled sessions are compared
against) changes from "Massive daily aggregates with adjusted=true" to
"Yahoo Finance daily bars for TSLA, retrieved and pinned as specified
in §3 below". Nothing else — no rule, parameter, tolerance, sample,
check, or line of verifier code — changes. §5 enumerates every frozen
element and states its disposition individually.

**Why the change is needed (evidence: ADJUDICATION.md, 2026-11-17).**
(i) No Massive key exists anywhere on the fleet (srs-keyprobe swept
~65 files across both servers: ABSENT). (ii) Creating a free Massive
key today would not cure it: Massive Stocks Basic's rolling 2-year
window reaches back only to ≈2024-11-17, while check 4's deterministic
W1 samples fall in Jul–Oct 2024 — those sessions would be absent from
the file, which the verifier records as findings → check 4 FAIL.
(iii) Waiting only amputates more W1 coverage. The Alpaca leg of the
frozen panel spec is unblocked (adjudication Q3: Basic serves the full
historical SIP panel; confirmed empirically by the run crew's probe,
§4 condition 4). The block is solely the cross-source instrument.

**Why this is v3, not v2 (the Stooq closure, complete).** Data-spec
addendum v2 (drafted 2026-11-17) named Stooq daily as the substitute
instrument. It was never frozen: its pre-freeze retrievability
condition failed, and the amendment lapsed per its own §6 contingency
(v2 freeze record, ~/workspace/srs-addendum-freeze/STATE.md). Stooq
has since been refused on **every** ranked retrieval route, and this
addendum records the closure in full so no future crew re-attempts it:
(a) server-side HTTPS GET from fleet server S1 → Stooq's JavaScript
proof-of-work challenge page (HTTP 200, 796 bytes — a challenge page,
not data); (b) the same GET from fleet server S2 → the same challenge
page; (c) a real coordinator browser session → Stooq's homepage and
historical-data page loaded normally (4,122 rows visible), but the
CSV download endpoint returned a 13-byte file whose entire contents,
read first-hand, are: "Access denied". The gate is at Stooq's edge,
not at any one client. This v3 proceeds under the v2 draft's own §6,
which pre-declared that a different instrument would require "a
data-spec addendum v3, declared and frozen the same way".

---

## 1. Check 4 as frozen (for reference — not modified by this addendum)

Per `verify_srs_panel.py` (the executable form of PROVENANCE §3.5.4):

- Input: a CSV with columns `date,open,high,low,close` supplied via
  `--cross-source`.
- Sampling: deterministic — 3 evenly spaced sessions per fold W1–W5
  drawn from the panel's sessions (`step = len(fold_days)/3`, indices
  `int(i*step)`); up to 15 sessions, ≥ 10 compared required for PASS.
- Tolerances: a sampled session's close differing by > **$0.02**, or
  its high or low differing by > **$0.05**, is a finding → FAIL. (The
  open difference is tabulated in the sample table but is not a
  finding under the frozen code; this addendum does not change that.)
- A sampled session absent from the cross-source file is a finding
  → FAIL. No file → NOT_RUN → overall INCOMPLETE.

## 2. The substitution

| | Frozen (v1) | Amended (v3, this addendum) |
|---|---|---|
| Cross-source vendor | Massive (formerly Polygon.io) | **Yahoo Finance** (chart API) |
| Independence from panel source | Independent of Alpaca | Independent of Alpaca (unrelated vendor, own data collection) |
| Series | TSLA daily aggregates, `adjusted=true` | TSLA daily bars, chart API `interval=1d` |
| Span available | Rolling 2 years (≈2024-11-17 → today) — **cannot cover W1 samples** | Full listing history — the retrieved file covers 2023-01-03 → 2026-10-30, all 961 panel sessions |
| Cost / account | $0 tier, but requires an account + API key the fleet does not have | $0, no account, no key (keyless endpoint, browser User-Agent) |
| File format | CSV `date,open,high,low,close` | Retrieved CSV `Date,Open,High,Low,Close,Volume`, hash-pinned (§3.2), mechanically transformed per §3.3 to the frozen column set |

Yahoo was evaluated in PROVENANCE §5.1 and rejected **as a panel
source** — its intraday history is capped (≈60 days at 15-minute),
and §5.1 blessed it only as a cross-check for recent sessions. That
judgement stands and is not revisited: the panel remains Alpaca SIP
15-minute, untouched. §5.1 did not evaluate Yahoo's **daily** series
in the cross-source role across the full span; the daily chart
endpoint serves the complete history (the probe retrieved all 961
sessions of the panel span in one request). This addendum uses Yahoo
only in the daily cross-source role, where the intraday-depth
objection does not apply.

## 3. The amended check-4 instrument (the ONLY operative text)

### 3.1 Source
Yahoo Finance chart API (v8) daily bars for TSLA:
`https://query1.finance.yahoo.com/v8/finance/chart/TSLA?period1=1672531200&period2=1793491200&interval=1d`
(the `query2` host behaves identically). Keyless; a browser
User-Agent suffices; no crumb/cookie flow is required (probe-verified
2026-11-17: HTTP 200, full history served directly).

### 3.2 The frozen cross-source file (retrieval record)
The file was retrieved on 2026-11-17 by the cross-source probe
(~/workspace/xsource-probe/STATE.md) via the §3.1 endpoint, keyless,
from the coordinator sandbox, and verified from disk after assembly:
962 lines = header `Date,Open,High,Low,Close,Volume` + **961 rows**,
2023-01-03 → 2026-10-30 (2026-10-31 is a Saturday; 2026-10-30 is the
last session of the panel span). Its Aug-2024 rows — a W1-sample
month — were sighted in the API response and re-read from the saved
file, identical. **SHA-256 of the retrieved file:**
`60c5b62019901b3a8653498fff4ed1f8d2c14901a72539ab941bf21558380d64`.
This file, identified by that hash, is the frozen cross-source
artefact. It is retained outside git (like the panel); only the
provenance record (§3.5) is committable. A retrieval that produces
any other hash has produced a different file, which is **not** this
addendum's instrument (§6).

*Independent corroboration (recorded, not gated):* the Nasdaq
official historical API (keyless, browser-like headers) returned the
same span and its sampled Aug-2024 closes matched this file **to the
cent on all seven sessions** 2024-08-01…2024-08-09 (216.86 / 207.67 /
198.88 / 200.64 / 191.76 / 198.84 / 200.00), opens/highs/lows
likewise; only trivial volume differences on two days, immaterial to
a close/high/low cross-check.

### 3.3 File preparation (mechanical transform only)
The retrieved Yahoo CSV is transformed into the verifier's input
format by a named script retained with the run record:
- rename columns `Date,Open,High,Low,Close` → `date,open,high,low,close`;
- drop the `Volume` column;
- restrict rows to 2023-01-01 → 2026-10-31 (the retrieved file already
  lies entirely inside this range; the restriction is a no-op guard);
- sort ascending by date (already ascending as retrieved).
No price value may be altered, rounded, or interpolated. Yahoo's raw
values carry float32 artefacts (e.g. 216.86000061035156 for 216.86);
they are preserved exactly as served — the artefacts are ~1e-6,
immaterial against the $0.02/$0.05 tolerances. The transform script
must assert: output row count equals the count of in-range rows in
the raw file, and every output value is byte-identical to its raw
source field. Both the raw file and the transformed file are retained
outside git and hash-pinned (§3.5).

### 3.4 Validation battery (run on the retrieved file BEFORE this
freeze; any failure would have rejected the file and left check 4
NOT_RUN)
**Run 2026-11-17 on the §3.2 file — ALL ITEMS PASS:**
1. **Coverage:** 961 rows — exactly the panel's expected session
   count — every date inside 2023-01-01 → 2026-10-31, sorted, unique,
   zero weekend rows, maximum consecutive gap 4 days (holiday
   weekends), no gap > 4 days. The file therefore contains a row for
   every session the verifier's deterministic sampler can draw.
2. **No in-window split-band ratios:** computed on the file itself,
   no overnight close/prev-close or open/prev-close ratio falls in
   the frozen split bands [2.70, 3.30] or [0.303, 0.367] — zero hits
   across all 961 rows (mirrors check 3, applied to the reference
   file). OHLC internal consistency also verified (high ≥ max(open,
   close), low ≤ min(open, close) on every row).
3. **Split-window characterisation (recorded, not gated):** not
   applicable in-file — the file's span begins 2023-01-03, after the
   2022-08-25 3:1 split, so no split window exists inside the file
   to inspect. The adjustment equivalence therefore rests on §3.6's
   instrument fact, guarded empirically by item 2 above and by the
   panel's own check 3.

### 3.5 Provenance of the cross-source file (reporting addition)
The run's `data_provenance.json` (produced by check 5, whose logic is
unchanged) must additionally record, alongside the frozen fields:
`cross_source: {vendor: "Yahoo Finance", instrument: "chart API v8,
interval=1d", symbol: "TSLA", retrieval_method: "keyless HTTPS GET,
browser User-Agent, coordinator sandbox, 2026-11-17",
retrieved_at_utc: <ts>, raw_file_sha256:
"60c5b62019901b3a8653498fff4ed1f8d2c14901a72539ab941bf21558380d64",
transformed_file_sha256: <…>, validation_battery: <§3.4 results>,
corroboration: "Nasdaq API matched sampled Aug-2024 closes to the
cent"}`. Like the panel, the cross-source files themselves are
**never committed**; only this record is committable.

### 3.6 Adjustment convention — why the frozen `adjusted=true`
requirement is satisfied in substance for this panel
The frozen instrument specified Massive `adjusted=true` (split +
dividend adjustment). Yahoo's chart `quote` OHLC is **unadjusted**,
so equivalence cannot rest on the vendor's methodology. It rests
instead on a verifiable fact about the instrument: **TSLA has had no
split since 2022-08-25 (3:1) and has never paid a dividend**
(verified against multiple independent corporate-action listings,
and re-verifiable by the run crew in minutes). Inside the panel span
2023-01-01 → 2026-10-31 there are therefore **zero** split or dividend
events, so raw, split-adjusted, and split+dividend-adjusted daily
prices are **identical numbers** in-window for any vendor — Yahoo's
unadjusted daily prices equal the split-adjusted values the frozen
spec asked for. The adjustment convention of the cross-source file
cannot move any sampled value for this panel; §3.4(2) exists to catch
the contrary case empirically rather than trust this argument. If a
future TSLA corporate action were announced with an ex-date inside
the panel span, this addendum must not be relied on (and the run
must not proceed) until the convention question is re-examined —
stated here so the condition is pre-declared, not improvised.

## 4. Freeze conditions (ALL held before this freeze — evidence recorded)
1. **Owner approval of the amendment:** the owner approved the
   check-4 instrument substitution (option 1A, 2026-11-17 10:26 IST).
   This v3 substitutes the instrument a second time only because
   v2's instrument proved unreachable by every route (see the Stooq
   closure above), under the v2 draft's own §6 contingency, which
   pre-declared this exact path.
2. **Retrievability proof:** the §3.1 retrieval produced the actual
   TSLA daily file and its Aug-2024 rows were sighted and recorded —
   by the probe crew, re-verified by the coordinator, and re-verified
   again by this freeze crew from the file itself (§3.2). HELD.
3. **The §3.4 validation battery passes on that file:** run
   2026-11-17 — PASS, all items (§3.4). HELD.
4. **The Alpaca SIP probe has confirmed the panel leg:** run crew
   probes 2026-11-17 ~10:17–10:21 IST — AUTH VERIFIED (account
   ACTIVE); SIP probe served 317 bars at consolidated scale
   (~235M shares over the sample window, ≈47M/day); IEX probe
   ~2.7% of SIP, confirming the IEX rejection. HELD.
5. **Freezing happens before the panel download and before any OOS
   trade computation:** no panel exists; the holdout is unburned;
   H5 burn-clause hygiene applies to the whole run, unchanged. HELD.

## 5. What does NOT change — element by element
Each item below was checked against the declaration (PR #742, SHA-256
`7a805046…1525b`), the TEMPORAL HOLDOUT v1 addendum (SHA-256
`69d9dcef…f7e4`), and PROVENANCE.md §3.5; disposition for every one:
**UNCHANGED**, except the single instrument substitution in §2–§3.

- Strategy rules 1–6 and the recovered SRS rule set (first-two-candles
  range, breakout-close entry, SL at opposite range end, TP 10
  points): UNCHANGED.
- `TP_POINTS=10`: UNCHANGED.
- Declared conventions (fleet-standard FWD-006 sizing; one trade per
  session; exit at 16:00 ET close; entry window closes at the 15:45 ET
  candle; TSLA-only v1 scope; ES reading out of scope): UNCHANGED.
- Pooled bar (expectancy_net > 0; PF_net ≥ 1.2; ≥ 200 pooled OOS
  trades; ≥ 4 of 5 folds positive; programme costs 16 bps round trip
  AND the 2× 32 bps shadow, both passing): UNCHANGED.
- Insufficient-trades rule (OOS < 200 ⇒ verdict "insufficient OOS
  trades", never padded): UNCHANGED.
- TEMPORAL HOLDOUT v1, H1–H5 including the burn clause and the
  judged-exactly-once procedure (§2.3 order of operations):
  UNCHANGED.
- Bonferroni method (ledger entering N + 1, re-read at run time;
  this amendment adds 0 trials; the declared run remains 1 trial):
  UNCHANGED.
- Panel spec (Alpaca Market Data Basic, `feed=sip`,
  `adjustment=split`, 2023-01-01 → 2026-10-31; 961 sessions / 24,842
  expected bars; panel never committed; provenance record
  committable): UNCHANGED.
- Check 1 (gap audit): UNCHANGED. Check 2 (feed/volume check, median
  ≥ 10M): UNCHANGED. Check 3 (split check): UNCHANGED. Check 5
  (SHA-256 freeze + provenance record; a changed panel is a FAIL, not
  a re-pin): UNCHANGED.
- Check 4's sampling (deterministic, 3 per fold W1–W5, ≥ 10 required),
  tolerances (close $0.02; high/low $0.05), absence-is-a-finding rule,
  and NOT_RUN ⇒ INCOMPLETE semantics: UNCHANGED.
- Verifier code (`verify_srs_panel.py`): UNCHANGED — byte-identical.
  This amendment changes only which file is handed to its existing
  `--cross-source` argument and how that file was obtained.
- Demo-only promotion path (Phase-3: ≥ 100 demo trades AND ≥ 8 weeks;
  live trading remains owner-gated): UNCHANGED.
- Addendum v2 (Stooq): NEVER FROZEN, never took effect, nothing was
  judged under it; it is superseded by this v3 before any use.

## 6. Contingency
If the §3.2 file is lost, or the file handed to the verifier does not
hash to `60c5b62019901b3a8653498fff4ed1f8d2c14901a72539ab941bf21558380d64`,
check 4 remains NOT_RUN, the panel verdict remains INCOMPLETE, and
the run waits: a changed cross-source file is a FAIL of this freeze,
not a re-pin — the same discipline check 5 applies to the panel. A
re-retrieval yielding a different hash (e.g. a vendor revision) is a
new instrument and would require a data-spec addendum v4, declared
and frozen the same way. Sampling is never redefined under this
addendum: narrowing the sample set to sessions a partial source
covers was considered in the adjudication and is **not** adopted
here, because it would change what check 4 examines, not merely what
it examines against.

## 7. Reporting rule
Any verdict from the declared run, in any record or message (run PR,
board entry, issue #35, owner-facing summary), must be reported as
judged under **"SRS declaration + TEMPORAL HOLDOUT v1 + data-spec
addendum v3 (check-4 cross-source: Yahoo Finance daily)"**. The
substitution chain and its reasons (no Massive key on the fleet;
Massive free's rolling 2-year window cannot cover the W1 sample
sessions; addendum v2's Stooq unreachable on every retrieval route —
server proof-of-work gate on both fleet servers and "Access denied"
to a real browser session) must be stated wherever the verdict is
reported. The run may never be described as "run exactly as
originally frozen".

*Freeze record: frozen 2026-11-17 by the coordinator's freeze crew,
from the frozen record, the spec adjudication, the lapsed v2 draft
and its freeze record, and the cross-source probe record. No panel
data was pulled for this freeze, no backtest was run, and the
holdout is unburned.*
