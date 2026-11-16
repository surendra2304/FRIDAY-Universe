# NON-NORMATIVE ADDENDUM — Box Theory declaration: source-fidelity labelling

**This note amends nothing.** It sits beside `BOX_THEORY_DECLARATION.md`
(TASK-IG2-STR-13) and exists only to correct the *provenance labelling*
of that declaration's prose, so that a future run report does not
inherit the mislabelling identified by the lane supervisor's round-3
audit (AUDIT-2, Claim 7, 2026-11-16) and by the slice-03 special
check in the IG package. The frozen declaration —
`box_theory_declaration.json`, SHA-256
`715b6884fb6a9abe3efec7be90c83e161cf7426aef1dc37629616b3145d013bd` —
is **not** edited by, or because of, this note, and neither is
`BOX_THEORY_DECLARATION.md`. The declaration governs all rules; if
this note and the declaration ever appear to disagree about a rule,
the declaration wins. This note governs only what may be *claimed
about the source*.

## Why this note exists

In the declaration, rule 2 (quartile zones) and rule 3 (trigger
measurements) explicitly flag themselves as the declaration's
resolutions of source ambiguity. Rules 4 and 5 carry no such flag,
although they are declaration additions of exactly the same kind —
and the Source section attributes a "performance framing" to the
video that its sources do not contain. The freeze itself is complete
and valid: every rule needed to test the family is frozen pre-run
under the full programme bar. Only the labelling is deficient.

## 1. Flagged declaration conventions (NOT source rules)

The source item `DWDUW26DYbZ` records, verbatim: "MISSING (named):
stop-loss, take-profit/target, position sizing and instrument/market
are NOT stated in any retrieved source (caption, narrative, cover
frame, page-1 or creator comments)". Against that record:

1. **Stop (declaration rule 4)** — "Stop = box low (long) / box high
   (short)". **Convention, not source.** The source states no
   stop-loss anywhere. The declaration added the box extreme as the
   stop to make the candidate testable.
2. **Targets (declaration rule 4)** — "T1 = box mid, T2 = opposite
   extreme". **Convention, not source.** The source states no
   take-profit or target anywhere. The midline itself *is* in the
   source — as a marked line to avoid trading near ("where all the
   false signals are") — but its use as profit target T1, and the
   opposite extreme as T2, are the declaration's construction (they
   are also the hypothesis's mean-reversion claim, stated as such in
   the declaration's Hypothesis section).
3. **Frequency (declaration rule 5; JSON `rules.frequency`)** —
   "at most ONE signal per day — the first qualifying extreme of the
   day; no re-entry the same day". **Convention, not source.** The
   source states no trade-frequency or re-entry rule.
4. **Day boundary (frozen JSON, `rules.timeframe`)** — "days are UTC
   calendar days". **Convention, not source.** The source says only
   "each day"; the declaration's MD does not mention a day-boundary
   convention at all. The UTC freeze stands as the operative reading
   of "day" for any run.

A future run report must cite these four as **declaration
conventions**, never as rules taught by the source.

## 2. Correction to the Source section's framing

`BOX_THEORY_DECLARATION.md` §Source states: "the video's performance
framing is an unverified claim and is treated as such: it bought
this family a pre-declared test, nothing more." The frozen JSON's
`source` field repeats the sentence.

**Correction:** the item's retrieved sources contain **no
performance, win-rate, or return claim at all** — there is no
performance framing to treat as unverified. The presenter's own
framing is that the method is "stupid simple" (with a "rewatch until
you understand" pitch for the follow-up guide), and the recorded
community response is divided, with experienced traders calling the
method simplistic or gambling. The sentence in the declaration
should be read subject to this correction: the family was
pre-declared on its recovered rule content (previous-day box,
extremes-only entries, the named "John Wick" trigger), not on any
performance claim, made or implied.

## 3. What is NOT corrected

- Rules 1 (box), 2 (zones) and 3 (trigger) and rule 6 (frozen
  parameters) stand exactly as labelled; rules 2 and 3 already carry
  their source-ambiguity flags in the declaration itself.
- Every rule the source *does* state is faithfully carried into the
  declaration: box from the previous day's high/low on a 15-minute
  chart, midline marked, trade only at the extremes (buy at the
  bottom, sell at the top), the "John Wick candlestick" entry name,
  and the avoidance of the middle.
- The evaluation bar, the status (DECLARED — not yet run), and the
  freeze's completeness are unchanged. This note changes no number,
  no rule, and no hash.

*Addendum authored 2026-11-16 by the Stratex IG implementer, per
AUDIT-2 Claim 7's recommendation, mirroring the source/convention
separation standard set by the SRS declaration (TASK-IG2-STR-14).
Docs-only; no code, no declaration file, and no board entry is
changed by the PR that ships this note.*
