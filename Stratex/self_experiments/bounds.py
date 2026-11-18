"""Frozen bounds for Stratex's self-experiment loop (TASK-STR-EXP-001).

Everything in this module is a constant declared in code — the loop's
data directory holds none of it, so the loop can never rewrite its own
rules (Self-Upgrade DESIGN section 5: the guardrails are outside every
agent's self-change levers).

The judgement bars are the programme's frozen bars, unchanged:
- PROVEN (full bar): expectancy > 0, PF >= 1.2, >= 200 OOS trades,
  >= 4/5 positive folds, Bonferroni one-sided p < 0.05 / N_global,
  pooled holdout expectancy > 0.
- FORWARD_TEST (the owner's second tier, 2026-11-18): expectancy > 0,
  PF >= 1.05, >= 200 OOS trades, judged pre-Bonferroni.

The lane risk terms stamped onto admission records are the FWD-006
package's FORWARD_TEST lane terms (0.1% per-trade risk on venue
equity, 2% heat cap). They are COPIES used only to stamp the loop's
own admission records in the FWD-003 shape; the loop has no write path
to config_strategy.py, measurement/forward_guard.py, or any other
risk file, and these constants are not inputs — nothing the loop
observes can change them.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# The frozen judgement bars
# ---------------------------------------------------------------------------

SECOND_TIER_PF = 1.05
FULL_BAR_PF = 1.2
MIN_OOS_TRADES = 200
FULL_BAR_MIN_POSITIVE_FOLDS = 4
FOLDS_TOTAL = 5
BONFERRONI_ALPHA = 0.05

# ---------------------------------------------------------------------------
# The frozen FORWARD_TEST lane terms (FWD-006 package, FWD-003 template).
# Stamped onto admission records; never varied by the loop.
# ---------------------------------------------------------------------------

LANE_RISK_PER_TRADE_PCT = 0.001
LANE_MAX_HEAT_PCT = 0.02
LANE_MINIMUM_REQUIRED_EDGE = 0.0005
LANE_KILL_CRITERIA = (
    "kill criteria expectancy<0 or PF<1.0 after >=50 closed trades or "
    "mark-to-market drawdown >5% of venue equity"
)

# ---------------------------------------------------------------------------
# Cycle bounds
# ---------------------------------------------------------------------------

#: Experiments judged per UTC day, at most. Declared small on purpose:
#: the fleet hosts have ~1 effective core (DESIGN section 6).
DEFAULT_DAILY_CAP = 4

#: Wall-clock budget for one experiment, seconds.
DEFAULT_TIME_BOX_S = 600.0

#: The host-load gate: a cycle starts only when the 1-minute load
#: average is below this fraction of the CPU count (the FRG-017 C2
#: lesson — Forge's slice 1 shipped without this gate; Stratex's
#: includes it from the start).
LOAD_GATE_FRACTION = 0.7

DEFAULT_POLL_SECONDS = 900.0

#: The OOS era every slice-1 experiment is judged on (the RD-002
#: programme's recorded folds).
DATA_WINDOW = "RD-002 OOS folds W1-W5 (2024-07-01..2026-07-01)"

# ---------------------------------------------------------------------------
# The risk-touch guard
# ---------------------------------------------------------------------------

#: Key fragments that mark a payload as touching risk machinery. A
#: self-experiment proposal or admission payload naming any of these
#: (outside the frozen stamping the admissions module itself performs
#: from the constants above) is refused. Defence in depth: the
#: catalogue's proposal schema contains no such keys at all, so a hit
#: means something outside the catalogue tried to speak — refuse it.
FORBIDDEN_KEY_FRAGMENTS = (
    "risk",
    "sizing",
    "position_size",
    "stop",
    "heat",
    "leverage",
    "kill",
    "margin",
    "drawdown_limit",
)


class RiskTouchRefused(Exception):
    """A payload tried to name a risk parameter. Refused, always."""


def assert_no_risk_touch(payload: Any, _path: str = "payload") -> None:
    """Recursively refuse any dict key that names a risk parameter.

    Raises RiskTouchRefused with the offending key path. Strings are
    not scanned (hypothesis text may legitimately *mention* stops);
    only structural keys — the things a payload could actually set.
    """
    if isinstance(payload, dict):
        for key, value in payload.items():
            lowered = str(key).lower()
            for fragment in FORBIDDEN_KEY_FRAGMENTS:
                if fragment in lowered:
                    raise RiskTouchRefused(
                        f"risk parameter key refused at {_path}.{key}: "
                        f"self-experiments never set risk parameters"
                    )
            assert_no_risk_touch(value, f"{_path}.{key}")
    elif isinstance(payload, (list, tuple)):
        for idx, item in enumerate(payload):
            assert_no_risk_touch(item, f"{_path}[{idx}]")
