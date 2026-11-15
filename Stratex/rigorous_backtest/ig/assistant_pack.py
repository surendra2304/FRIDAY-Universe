"""Assistant content pack for Stratex: trade-plan template + discipline.

TASK-IG-STR-09 (IG corpus items DRSGKJXDAU4 — a curated prompt that
turns a trader question into a structured plan; DQn4VCfDMCd — trader
mindset/discipline coaching content).

Two content assets, as data + renderers:
  * TRADE_PLAN_TEMPLATE — the sections a plan must contain before it
    is a plan at all (context, setup, evidence, invalidation, sizing,
    review). Rendering refuses to omit the demo-only disclaimer.
  * DISCIPLINE_NOTES — the coaching content set for the assistant
    layer: process over outcome, consistency over jackpots, no tips,
    no signals. These reinforce the existing discipline lane; they do
    not replace it and they authorise nothing.

Content layer only: no model calls, no orders, no signals. A filled
template is a planning document, and any strategy it describes still
faces the RD bar and the forward protocol.

Stdlib only, Python 3.10-compatible.
"""

DISCLAIMER = ("Demo/paper only. This is a planning template — not a "
              "signal, tip, or recommendation, and not financial advice.")

REQUIRED_SECTIONS = ("Market context", "Setup", "Evidence",
                     "Invalidation", "Sizing", "Review")

TRADE_PLAN_TEMPLATE = """# Trade plan — {symbol} ({timeframe})

## Market context
{context}

## Setup
{setup}

## Evidence
{evidence}

## Invalidation
{invalidation}

## Sizing
{sizing}

## Review
{review}

---
{disclaimer}
"""

DISCIPLINE_NOTES = [
    {"title": "Process over outcome",
     "text": "A good decision can lose money and a bad one can make it. "
             "Judge the plan by whether it followed the process — the "
             "outcome of one trade is mostly noise."},
    {"title": "Consistency over jackpots",
     "text": "The forward record is built from many small, repeatable, "
             "measured trades. One oversized win proves nothing and "
             "usually teaches the wrong lesson."},
    {"title": "No tips, no signals",
     "text": "Nothing here is a tip. If an idea cannot state its "
             "invalidation and survive the evidence bar, it does not "
             "get traded — on demo or anywhere else."},
    {"title": "Drawdown is information",
     "text": "A drawdown inside the pre-declared limits is the cost of "
             "measurement. A drawdown that breaches them is a stop "
             "signal for the strategy, not a reason to double down."},
    {"title": "Journal everything",
     "text": "If it is not in the journal, it did not happen. Record "
             "the plan before the trade and the post-mortem after it — "
             "especially the trades that hurt."},
    {"title": "Boredom is the job",
     "text": "Most of disciplined trading is waiting: for the setup, "
             "for the sample, for the evidence. Acting out of boredom "
             "is how measurement turns into gambling."},
]


def render_trade_plan(symbol, timeframe, context, setup, evidence,
                      invalidation, sizing, review):
    """Render a complete plan document. All sections are required —
    an empty section raises rather than producing a plan with a hole
    where its invalidation should be."""
    fields = {"context": context, "setup": setup, "evidence": evidence,
              "invalidation": invalidation, "sizing": sizing,
              "review": review}
    empty = [k for k, v in fields.items() if not str(v).strip()]
    if empty:
        raise ValueError("trade plan sections must be non-empty: %s" % empty)
    return TRADE_PLAN_TEMPLATE.format(
        symbol=symbol, timeframe=timeframe, disclaimer=DISCLAIMER, **fields)


def validate_plan_document(text):
    """True iff a rendered plan carries every required section and
    the disclaimer."""
    return (all(("## " + s) in text for s in REQUIRED_SECTIONS)
            and DISCLAIMER in text)
