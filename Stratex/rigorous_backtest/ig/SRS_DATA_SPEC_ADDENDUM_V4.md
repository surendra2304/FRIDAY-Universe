# DATA-SPEC ADDENDUM v4 — SRS (TASK-IG2-STR-14): check-4 close leg — SIP tick official-close print (Rule R1b)

**STATUS: FROZEN — 2026-11-17, before any run under this addendum
and before any OOS trade is computed.** This addendum's SHA-256 is
stated in its freeze PR and on issue #35 (it is not embedded in this
file). It is structured as a delta on data-spec addendum v3
(SHA-256 `8ab6e2598e15e8930f7b03fefb9afd10820e3b189189d12f8d59bbd6ce255050`,
PR #883, merged): everything in v3 carries over verbatim except the
single element §2 below amends, exactly as v3 was a delta on the
frozen spec before it.

**What this addendum changes — one sentence.** In check 4 of the
5-point verification (PROVENANCE.md §3.5), the CLOSE leg's SIP-side
comparator changes from "the close of the panel session's last bar"
to "the session's official close as printed on the SIP tick tape,
identified by Rule R1b (§2)" — and the verifier that executes check
4 becomes `verify_srs_panel_v4.py` (§3), the frozen v3 verifier with
only that leg re-implemented. Nothing else — no rule, parameter,
tolerance, sample, check, or other line of verifier code — changes.
§5 enumerates every frozen element and states its disposition
individually.

**Why the change is needed (evidence chain, all records on file).**
(i) The declared run's verification gate ran on 2026-11-17 under
addendum v3 and STOPPED: checks 1, 2, 3 and 5 PASS; check 4 FAIL —
15 sampled sessions, 10 findings, **all close-only** ($0.03–$0.25);
highs and lows agreed to ≤ $0.0012 on every sampled session; no
sampled session was an early-close day (gate record:
~/workspace/srs-execution/STATE.md; issue #35 comment 6947987723).
The run did not execute; no trial was consumed; the holdout is
unburned. (ii) Root cause, proven from the tape: Yahoo's daily
close is the session's **official closing-auction print**; the
panel's session close is the close of its last (15:45) bar — the
last **pre-auction** trade. The two quantities differ by
construction whenever the closing auction moves the price, so the
v3 close leg compared two different quantities and failed on the
difference. The feed itself is not in doubt: opens, highs and lows
match the independent source essentially exactly. (iii) A first v4
attempt tried to repair the leg at bar level and correctly STOPPED
before freezing (~/workspace/srs-addendum-v4/STATE.md): across all
952 regular sessions, every mechanical bar aggregate fails the
$0.02 tolerance on a large share of sessions (panel close 663/952
beyond tolerance; 16:00-bar open 480; 16:00-bar close 903; 16:00-bar
VWAP 309) — the auction print sits inside the 16:00 bar's aggregate
and no bar field carries it. (iv) The tick probe then proved the
instrument this addendum freezes (~/workspace/srs-tick-probe/
STATE.md + results.json): on the gate's own 15 sampled sessions,
Rule R1b identifies exactly one print per session and matches
Yahoo's close **exactly (diff 0.0000) on 15/15** (Appendix A).

---

## 1. Check 4 as frozen under v3 (for reference — the parts this addendum does not touch)

Per `verify_srs_panel.py` (the executable form of PROVENANCE §3.5.4)
as amended by addendum v3:

- Input: the frozen Yahoo Finance daily file (v3 §3.2, SHA-256
  `60c5b62019901b3a8653498fff4ed1f8d2c14901a72539ab941bf21558380d64`),
  mechanically transformed per v3 §3.3, supplied via `--cross-source`.
- Sampling: deterministic — 3 evenly spaced sessions per fold
  W1–W5 drawn from the panel's sessions (`step = len(fold_days)/3`,
  indices `int(i*step)`); up to 15 sessions, ≥ 10 compared required
  for PASS.
- Tolerances: a sampled session's close differing by > **$0.02**,
  or its high or low differing by > **$0.05**, is a finding → FAIL.
  (The open difference is tabulated in the sample table but is not
  a finding under the frozen code; this addendum does not change
  that.)
- The open, high and low legs compare the panel's daily aggregates
  (first bar's open, session high, session low) against the
  cross-source file. **This addendum does not change them.**
- A sampled session absent from the cross-source file is a finding
  → FAIL. No file → NOT_RUN → overall INCOMPLETE.

## 2. The amended close leg (the ONLY operative text)

### 2.1 Rule R1b (frozen form)

For each sampled session, the SIP-side official close is the price
of the trade in the Alpaca SIP tick tape (trades, `feed=sip`) that
satisfies **all** of:

- its condition list carries **'M'** (Market Center Official
  Closing Price);
- its exchange code is **'Q'** (Nasdaq — TSLA's listing exchange);
- its ET timestamp lies in **[16:00:00, 16:01:00)** on a regular
  session. General form: on an early-close session the window is
  **[13:00:00, 13:01:00)** ET — the exchange's scheduled close plus
  one minute. (The frozen sample contains no early-close session;
  the general form is stated so the rule is complete, not because
  it is exercised by this gate.)

**Exactly one** such trade must exist. Zero, or more than one, is a
finding → the session FAILS the close leg. There is no fallback and
no substitution: no other print, aggregate, or rule may be used for
that session (the corroborating rules of Appendix A.4 are evidence
only and are **not** part of the frozen leg). The comparison is the
frozen tolerance, unchanged: **|R1b price − Yahoo daily close| ≤
$0.02**, else a finding → FAIL.

Mechanically, in the v4 verifier: a sampled session for which no
tick data can be obtained (missing file under `--ticks-dir`, or a
failed `--pull-ticks` pull, recorded in the report) scores zero
candidates and therefore fails the close leg — the same absence
discipline v3 applies to the cross-source file.

### 2.2 What the close leg verifies — stated exactly

The panel's own last-bar close is a pre-auction trade by
construction and is **not** the official close; no panel field
carries the official close. The close leg therefore verifies **the
feed** — the same Alpaca SIP source the panel was pulled from, via
its tick tape — against the cross-source on the official-close
field. It does not compare a panel field, and no record may
describe it as doing so.

The panel-identity burden of check 4 is carried jointly: the
open/high/low legs compare panel fields against Yahoo directly
(unchanged; observed agreement ≤ $0.0012 on highs/lows across the
sample), and the close leg proves the feed's official close equals
Yahoo's official close. Together with checks 1 (gap audit), 2
(consolidated volume) and 3 (split check) — all unchanged, all PASS
at the v3 gate — this is the whole of what check 4 certifies, no
more and no less.

### 2.3 The panel close is recorded, not compared

The v4 verifier's sample table carries two additional columns per
sampled session: `panel_close` (the panel session's last-bar close)
and `auction_minus_panel` (R1b price − panel close). They are the
mechanism record — on the v3 gate's findings they reproduce the
finding to the cent (Appendix A.2) — and they are never compared
against any tolerance.

## 3. The verifier

- `verify_srs_panel_v4.py`, **SHA-256
  `c4bbf80b253a4a7a1bad7fce6b39697cf89b59be0507c597bef4010b2da80049`**,
  shipped in this addendum's freeze PR beside this file so the
  freeze is reviewable as a unit.
- It is the frozen v3 verifier (`verify_srs_panel.py`, SHA-256
  `6bb5f922db281d56550429677c696536f924ecd6d432749a4ceddf2674048e11`)
  with ONLY the check-4 close leg re-implemented per §2: checks 1,
  2, 3 and 5, check 4's sampler, its open/high/low legs, all
  tolerances, the ≥ 10-compared rule and the NOT_RUN semantics
  (no cross-source file, or no tick source, ⇒ check 4 NOT_RUN ⇒
  overall INCOMPLETE) are byte-identical logic. The v3 verifier
  itself is untouched and remains the verifier of record for the
  v3 gate attempt.
- It runs with the same pinned `nyse_calendar.py` beside it
  (SHA-256 `e6722180605bebf826b8525489e3e7e3dbaaa50fb48841c2f0119fe0df252db1`).
  One deliberate subtlety: the R1b window keys off the **exchange's**
  scheduled close (16:00 ET; 13:00 ET on the calendar's
  `NYSE_EARLY_CLOSES` days), **not** off the panel's last retained
  bar — the frozen panel spec truncates early-close sessions to 10
  bars (ending 12:00 ET), but the closing auction prints at the
  real 13:00 ET close, and the leg verifies the feed.
- Pre-freeze testing was on SYNTHETIC tick fixtures only (13/13
  pass): a unique 'M'/'Q' print in the window passes; a missing
  print fails; two 'M'/'Q' prints fail; an 'M' print on the wrong
  exchange only fails; prints outside the window fail; a print
  beyond the $0.02 tolerance fails; the early-close 13:00 form
  resolves; no tick source ⇒ NOT_RUN. The verifier was **not** run
  against the real panel or the real ticks for this freeze — that
  run is the gate, and it happens once, after this addendum merges.

## 4. Tick-pull specification (gate time)

- Source: Alpaca Market Data trades endpoint for TSLA,
  `feed=sip` — the same feed family as the panel, on the installed
  SRS channel (keys read from the environment:
  `APCA_API_KEY_ID` / `APCA_API_SECRET_KEY`, or
  `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY`).
- Window per sampled session: **[scheduled close − 5 min,
  scheduled close + 10 min) ET** — for a regular session,
  [15:55, 16:10) ET. Only the sampled sessions are pulled.
- Ticks are pulled **fresh at gate time** and hash-recorded in the
  gate report (`verification_report.json`, check 4's
  `tick_provenance`: per session, the tick file's SHA-256 under
  `--ticks-dir`, or the pull record including a SHA-256 of the
  pulled trades under `--pull-ticks`). The probe's saved windows
  (~/workspace/srs-tick-probe/raw/) are **evidence, not gate
  inputs**, and must not be handed to the gate as its tick source.
- Probe-measured cost for the full 15-session sample: 577,050
  trades, ~65 MB, ~118 s total. Historical prints are facts: a
  fresh pull of the same windows reproduces the probe's prints.

## 5. What does NOT change — element by element

Every item in addendum v3's §5 is incorporated here by reference
and remains **UNCHANGED**; the items this addendum's subject touches
are restated individually:

- Addendum v3 itself — the Yahoo Finance daily instrument, the
  frozen cross-source file (SHA-256 `60c5b620…80d64`), its §3.3
  transform, §3.4 validation battery, §3.5 provenance addition and
  §3.6 adjustment equivalence: UNCHANGED, carried over verbatim.
  V4 amends only the close leg's SIP-side comparator; it does not
  re-open the instrument question.
- The frozen strategy panel: Alpaca SIP 15-minute,
  `adjustment=split`, 2023-01-01 → 2026-10-31, 961 sessions /
  24,842 bars, **SHA-256
  `5addb8cdee3f2a06d509c498a986ab23de3e8c92c5d7ff92d7a947bc716b67b1`**:
  UNCHANGED — byte-identical, never re-pulled for this amendment.
- The SRS declaration (PR #742, SHA-256 `7a805046…1525b`) and its
  recovered rule set, `TP_POINTS=10`, and declared conventions:
  UNCHANGED.
- TEMPORAL HOLDOUT v1 (SHA-256 `69d9dcef…f7e4`), H1–H5 including
  the burn clause and the judged-exactly-once procedure: UNCHANGED.
- The pooled bar (expectancy_net > 0; PF_net ≥ 1.2; ≥ 200 pooled
  OOS trades; ≥ 4 of 5 folds positive; 16 bps costs AND the 32 bps
  shadow, both passing) and the insufficient-trades rule:
  UNCHANGED.
- Checks 1, 2, 3, 5: UNCHANGED. Check 4's sampling, its ≥ 10
  requirement, its absence-is-a-finding rule, its NOT_RUN ⇒
  INCOMPLETE semantics, and its open/high/low legs: UNCHANGED.
- Tolerances: close $0.02, high/low $0.05 — UNCHANGED. This
  amendment is definitional (compare like with like), never a
  wider tolerance.
- Trial accounting: the v3 gate stop consumed no trial; the first
  (bar-level) v4 attempt froze nothing and consumed no trial; the
  programme counter entering the declared run is still **N =
  3,891**; the declared run remains exactly 1 trial (final N =
  3,892). This amendment adds 0 trials.
- The v3 gate-stop record stands as history: the run did NOT
  execute under v3, and no verdict exists under the v3 label.
- Bonferroni method (ledger entering N + 1, re-read at run time):
  UNCHANGED.
- Demo-only promotion path (Phase-3: ≥ 100 demo trades AND ≥ 8
  weeks; live trading remains owner-gated): UNCHANGED.
- Addendum v2 (Stooq): never frozen, never took effect: UNCHANGED
  disposition.

## 6. Freeze conditions (ALL held before this freeze — evidence recorded)

1. **Coordinator adjudication:** the fix is definitional — compare
   the cross-source close against the same quantity on the SIP
   side — never a wider tolerance; the strategy panel stays
   byte-identical; this addendum is frozen before any run and
   disclosed in the verdict label. The first v4 attempt's stop is
   honoured: nothing known to fail was frozen.
2. **Instrument proof before freeze:** the tick probe scored Rule
   R1b on the gate's own sample — the sampler is deterministic and
   the panel is hash-frozen, so the 15 sampled sessions are already
   known — and R1b matched Yahoo's close exactly on 15/15
   (Appendix A). The rule was not validated on a proxy sample.
3. **The verifier exists and is hash-pinned:** §3's SHA-256,
   derived from the frozen v3 verifier with only the close leg
   changed, synthetic-fixture tests 13/13 (§3). The v3 verifier is
   untouched.
4. **Freezing precedes judging:** no run has occurred under this
   addendum, no OOS trade has been computed, the holdout is
   unburned, and the panel hash (§5) is the same hash the v3 gate
   verified — no panel data was pulled or altered for this freeze.

## 7. Contingency

If at gate time any sampled session yields zero or more than one
R1b print, or a tick pull fails, check 4 FAILS under this addendum
and the run does not proceed; no fallback rule (Appendix A.4's
R1c/R2/R4 included) may be substituted at gate time. Any further
change is a new addendum, declared and frozen the same way. If the
cross-source file handed to the verifier does not hash to v3's
pinned `60c5b62019901b3a8653498fff4ed1f8d2c14901a72539ab941bf21558380d64`,
v3's §6 contingency applies unchanged: check 4 remains NOT_RUN and
the panel verdict remains INCOMPLETE.

## 8. Reporting rule

Any verdict from the declared run, in any record or message (run
PR, board entry, issue #35, owner-facing summary), must be reported
as judged under **"SRS declaration + TEMPORAL HOLDOUT v1 +
data-spec addendum v4 (check-4 cross-source: Yahoo Finance daily;
close leg: SIP tick official-close print, Rule R1b)"**. The chain
must be stated wherever the verdict is reported: the v3 gate stop
(close-convention artifact — the panel close is a pre-auction
trade, Yahoo's close is the auction print), the first v4 attempt's
stop (bar aggregates cannot recover the official close), and this
addendum's tick-founded leg (Appendix A). The run may never be
described as "run exactly as originally frozen".

---

## Appendix A — Tick-probe evidence (record: ~/workspace/srs-tick-probe/STATE.md, results.json)

### A.1 The 15 sampled sessions — R1b vs Yahoo (15/15 exact)

| Session | Panel close | Yahoo close | R1b print (ET, shares) | R1b price | R1b − Yahoo | R1b − panel | v3 close leg |
|---|---|---|---|---|---|---|---|
| 2024-07-01 | 209.8601 | 209.86 | 16:00:00.206, 3,403,752 | 209.86 | 0.0000 | −0.0001 | pass |
| 2024-08-29 | 206.27 | 206.28 | 16:00:00.142, 1,429,694 | 206.28 | 0.0000 | +0.01 | pass |
| 2024-10-30 | 257.65 | 257.55 | 16:00:00.255, 1,652,393 | 257.55 | 0.0000 | −0.10 | FINDING 0.10 |
| 2025-01-02 | 379.03 | 379.28 | 16:00:00.175, 4,463,367 | 379.28 | 0.0000 | +0.25 | FINDING 0.25 |
| 2025-03-04 | 271.99 | 272.04 | 16:00:00.177, 3,524,649 | 272.04 | 0.0000 | +0.05 | FINDING 0.05 |
| 2025-05-01 | 280.51 | 280.52 | 16:00:00.070, 4,181,884 | 280.52 | 0.0000 | +0.01 | pass |
| 2025-07-01 | 300.71 | 300.71 | 16:00:00.090, 4,293,574 | 300.71 | 0.0000 | 0.00 | pass |
| 2025-08-29 | 334.00 | 333.87 | 16:00:00.050, 4,180,796 | 333.87 | 0.0000 | −0.13 | FINDING 0.13 |
| 2025-10-30 | 440.01 | 440.10 | 16:00:00.303, 5,117,997 | 440.10 | 0.0000 | +0.09 | FINDING 0.09 |
| 2026-01-02 | 438.10 | 438.07 | 16:00:00.580, 4,086,547 | 438.07 | 0.0000 | −0.03 | FINDING 0.03 |
| 2026-03-04 | 406.06 | 405.94 | 16:00:00.107, 3,161,711 | 405.94 | 0.0000 | −0.12 | FINDING 0.12 |
| 2026-05-01 | 390.73 | 390.82 | 16:00:00.517, 2,354,260 | 390.82 | 0.0000 | +0.09 | FINDING 0.09 |
| 2026-07-01 | 425.335 | 425.30 | 16:00:00.296, 2,600,035 | 425.30 | 0.0000 | −0.035 | FINDING 0.035 |
| 2026-08-11 | 332.80 | 332.81 | 16:00:00.521, 1,609,777 | 332.81 | 0.0000 | +0.01 | pass |
| 2026-09-22 | 378.86 | 378.90 | 16:00:00.064, 1,662,324 | 378.90 | 0.0000 | +0.04 | FINDING 0.04 |

Exactly one 'M'/'Q' trade exists in the window on 15/15 sessions
(n = 1 every session), and its price equals Yahoo's close to the
cent on 15/15 — diff 0.0000, not merely within the $0.02 tolerance.

### A.2 Mechanism check

R1b price − panel close reproduces all 10 v3 findings **to the
cent, with Yahoo's sign** (+0.25, −0.13, −0.12, −0.10, +0.09,
+0.09, +0.05, +0.04, −0.035, −0.03): on finding days the auction
print is not the pre-auction trade, by exactly the finding. On the
5 v3-pass days |R1b − panel| ≤ $0.01. The mechanism prediction
holds exactly, on every session.

### A.3 Tape structure, and why the exchange restriction is definitional

The closing cross appears **twice** per session on the listing
venue (Nasdaq, 'Q'), same price and same size, ~100 ms apart: the
original cross print (conditions ['@','6','X']) and its
official-close republication (['@','M']). Exactly **2** 'M' trades
exist per session in the whole pulled window: the Nasdaq
republication (full cross size, 1.43M–5.12M shares) and a tiny NYSE
Arca ('P', 40–1,502 shares) official-close print at **Arca's own
last-sale price** — which equals the panel close on 10/15 sessions.
An exchange-blind 'M' rule therefore faces two different "official
closes" on 13/15 sessions. The 'Q' restriction is not a tuning
choice: Yahoo's daily close is the **primary listing venue's**
official close, so like is compared with like only when the print
is taken from the listing exchange. (Corroboration: the ['@','6',
'X'] original cross print matches the 'M' republication in price
AND size on 15/15 sessions.)

### A.4 Rule scoreboard (all rules scored on the same 15 sessions before any freeze)

| Rule | Score | Note |
|---|---|---|
| R1 — 'M' in [16:00, 16:01), any exchange | 2/15 | ambiguous on 13/15 (Q vs P official closes at different prices) |
| **R1b — 'M' in [16:00, 16:01), listing exchange 'Q'** | **15/15, all exact** | **the frozen rule** |
| R1c — largest 'M' trade in the minute | 15/15, all exact | corroboration only |
| R2 — largest trade in the minute | 15/15, all exact | corroboration only |
| R3 — last trade in [16:00:00, 16:00:01) | 9/15 | post-cross prints inside the first second break it (diffs to $0.41) |
| R4 — largest trade in the whole window | 15/15, all exact | corroboration only |

R1b is the frozen choice because it is a **definitional
identifier**: it names the print by what it is — the listing
venue's own official-close flag. R2/R4 reach the same print only
because the closing cross is usually the largest trade of the
window, a statistical property that can fail silently on a
quiet-cross day; R1c adds a size ranking the definition does not
need. A frozen gate leg must identify its quantity by definition,
not by a heuristic that happens to agree with it.

### A.5 Why the leg could not stay at bar level (first v4 attempt, stopped)

Panel-wide census over all 952 regular sessions, |candidate −
Yahoo close| beyond the $0.02 tolerance: panel close 663/952
(69.6%); 16:00-bar open 480/952 (50.4%); 16:00-bar close 903/952
(94.9%); 16:00-bar VWAP 309/952 (32.5%). The auction print is a
single print inside the 16:00 bar's aggregate; Alpaca's 15-minute
bars expose no field carrying it. Freezing any bar-level rule
would have replaced one failing convention with another — so none
was frozen (record: ~/workspace/srs-addendum-v4/STATE.md).

*Freeze record: frozen 2026-11-17 by the coordinator's freeze crew,
from the v3 gate-stop record, the stopped bar-level v4 attempt,
and the tick-identifiability probe record. No gate was run under
this addendum, no backtest was run, no panel data was pulled or
altered, and the holdout is unburned.*
