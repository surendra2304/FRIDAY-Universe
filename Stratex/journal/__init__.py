"""Emotion-aware trade journal for Stratex (TASK-STR-081).

Trades imported -> emotion analysis attached -> pattern detection -> a
per-period risk summary the desk and the risk gate can read. See
`journal.emotion` for the rules; every emotion label is a rule-based
behavioural proxy, never a claim about feelings.
"""

from journal.emotion import (
    DecisionEvent,
    EmotionTag,
    Trade,
    analyse_trade,
    collapse_events,
    detect_patterns,
    load_jsonl,
    render_markdown,
    risk_assessment,
    sort_trades,
    summarise_period,
    trade_from_dict,
)

__all__ = [
    "DecisionEvent",
    "EmotionTag",
    "Trade",
    "analyse_trade",
    "collapse_events",
    "detect_patterns",
    "load_jsonl",
    "render_markdown",
    "risk_assessment",
    "sort_trades",
    "summarise_period",
    "trade_from_dict",
]
