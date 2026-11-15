"""
cortex_api/provenance.py — Decision provenance blocks for Cortex outputs.

TASK-COR-002. Mirrors the TASK-REL-032 pattern established for Inference:
when an output is computed partly from values the caller never supplied, or
its confidence is a heuristic rather than a measurement, the output must
DISCLOSE that — never silently substitute.

Every decision/recommendation output carries a ``provenance`` block:

    {
        "generated_at": "<ISO-8601 UTC timestamp of the decision>",
        "inputs_used": [
            {"name": ..., "value": ..., "source": "caller_supplied" |
             "engine_default" | "route_default" | "derived" | "stored_state"},
            ...
        ],
        "defaults_applied": ["<input names whose value came from a default>"],
        "confidence": <float or None>,
        "confidence_basis": "<the actual formula/rule behind the number>",
        "data_status": "complete_inputs" | "partial_inputs_defaulted" |
                       "estimated_from_inputs" | "no_data",
    }

``source`` semantics:
- ``caller_supplied`` — the value arrived in the request that produced this
  output (or in the recorded interaction the output is computed from).
- ``engine_default`` — the engine substituted its own fallback because the
  caller never supplied the value (e.g. an unscored decision-matrix cell).
- ``route_default`` — the API route filled the value from its parameter
  default because the request omitted it.
- ``derived`` — computed from supplied values by the stated formula.
- ``stored_state`` — read from state recorded earlier (e.g. a lead score
  stored by a previous call).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

CALLER_SUPPLIED = "caller_supplied"
ENGINE_DEFAULT = "engine_default"
ROUTE_DEFAULT = "route_default"
DERIVED = "derived"
STORED_STATE = "stored_state"

_DEFAULT_SOURCES = {ENGINE_DEFAULT, ROUTE_DEFAULT}


def input_record(name: str, value: Any, source: str) -> dict[str, Any]:
    """One provenance input entry."""
    return {"name": name, "value": value, "source": source}


def build_provenance(
    *,
    inputs: list[dict[str, Any]],
    confidence: float | None,
    confidence_basis: str,
    data_status: str | None = None,
) -> dict[str, Any]:
    """Assemble a provenance block.

    ``data_status`` is derived when not given: ``no_data`` when there are no
    inputs at all, ``partial_inputs_defaulted`` when any input came from a
    default, otherwise ``complete_inputs``.
    """
    defaults = [i["name"] for i in inputs if i.get("source") in _DEFAULT_SOURCES]
    if data_status is None:
        if not inputs:
            data_status = "no_data"
        elif defaults:
            data_status = "partial_inputs_defaulted"
        else:
            data_status = "complete_inputs"
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "inputs_used": inputs,
        "defaults_applied": defaults,
        "confidence": confidence,
        "confidence_basis": confidence_basis,
        "data_status": data_status,
    }
