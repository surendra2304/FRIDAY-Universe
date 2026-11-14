"""TASK-REL-009 regression: every builtin tool schema must be valid for
Google's function-declaration subset.

Production incident 2026-11-14: with the chat brain switched to Gemini,
EVERY tool-bearing generation failed with

    400 INVALID_ARGUMENT — GenerateContentRequest.tools[0]
    .function_declarations[7].parameters.properties[severity].enum[0]:
    cannot be empty

because SentinelSecurityTool declared ``enum: ["", "critical", ...]``
(the empty string meant "any severity"). Groq/OpenRouter tolerate an
empty enum string; Google does not, and one bad schema poisoned the
whole tool list for every LLM-routed chat turn.

This test loads ALL builtin tool schemas the way the registry sees them
(class-level ``parameters`` dicts, plus the property-defined ones) and
asserts the Gemini subset rules:

* every schema node declares a valid ``type``;
* enum values are non-empty and match the declared type;
* ``required`` only names declared properties;
* no JSON-Schema keywords outside Google's supported subset
  (``additionalProperties`` and friends never reach a valid request).
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

import pytest

import friday.tools as _tools_pkg
from friday.tools.base import BaseTool

_VALID_TYPES = {"string", "number", "integer", "boolean", "array", "object", "null"}
_TYPE_MAP: dict[str, type | tuple[type, ...]] = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}
# Keywords in Google's function-declaration Schema subset are limited to
# type/format/description/nullable/enum/properties/required/items and the
# numeric/string bounds. Anything below is either rejected by Google or
# silently meaningless there, so it must not appear in a builtin schema.
_UNSUPPORTED_KEYWORDS = {
    "additionalProperties",
    "additionalItems",
    "patternProperties",
    "propertyNames",
    "contains",
    "const",
    "oneOf",
    "allOf",
    "anyOf",
    "not",
    "if",
    "then",
    "else",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "dependencies",
    "$ref",
    "$schema",
    "$defs",
    "definitions",
}


def _collect_tool_classes() -> list[type[BaseTool]]:
    """Every BaseTool subclass shipped under friday.tools, plus the tools
    re-exported through friday.tools.builtin (e.g. ScreenPredictionTool,
    whose class lives in friday.vision)."""
    for mod in pkgutil.walk_packages(_tools_pkg.__path__, prefix="friday.tools."):
        importlib.import_module(mod.name)
    import friday.tools.builtin as builtin_pkg

    found: dict[int, type[BaseTool]] = {}

    def _add(cls: Any) -> None:
        if isinstance(cls, type) and issubclass(cls, BaseTool) and cls is not BaseTool:
            found[id(cls)] = cls

    def _collect(cls: type[BaseTool]) -> None:
        for sub in cls.__subclasses__():
            _collect(sub)
            if sub.__module__.startswith("friday.tools"):
                _add(sub)

    _collect(BaseTool)
    for name in getattr(builtin_pkg, "__all__", []):
        _add(getattr(builtin_pkg, name, None))
    return sorted(found.values(), key=lambda c: f"{c.__module__}.{c.__qualname__}")


def _resolve_parameters(cls: type[BaseTool]) -> dict[str, Any]:
    """Return the parameters schema exactly as the registry consumes it."""
    raw = inspect.getattr_static(cls, "parameters")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, property):
        # Property-defined schemas (BrowserAutomationTool, MemorySearchTool)
        # return a literal dict that does not depend on __init__ state.
        bare = object.__new__(cls)
        try:
            return raw.fget(bare)  # type: ignore[union-attr]
        except AttributeError:
            pass
    if cls.__name__ == "MCPToolAdapter":
        # The adapter's schema is supplied at runtime by the external MCP
        # server; the only static schema FRIDAY owns here is the fallback
        # default, which is what we can (and do) validate.
        adapter = cls(  # type: ignore[call-arg]
            name="schema_validity_stub",
            description="stub",
            parameters_schema={"type": "object", "properties": {}},
            call_fn=lambda name, args: None,
        )
        return adapter.parameters
    raise AssertionError(f"{cls.__module__}.{cls.__qualname__}: cannot resolve parameters schema")


def _check_node(schema: Any, path: str, problems: list[str]) -> None:
    if not isinstance(schema, dict):
        problems.append(f"{path}: schema node is {type(schema).__name__}, not an object")
        return
    for key in schema:
        if key in _UNSUPPORTED_KEYWORDS:
            problems.append(f"{path}: keyword {key!r} is outside Google's function-declaration subset")
    raw_type = schema.get("type")
    if raw_type is None:
        problems.append(f"{path}: missing 'type'")
        base_types: list[str] = []
    elif isinstance(raw_type, str):
        if raw_type not in _VALID_TYPES:
            problems.append(f"{path}: invalid type {raw_type!r}")
        base_types = [raw_type]
    elif isinstance(raw_type, list):
        for entry in raw_type:
            if not isinstance(entry, str) or entry not in _VALID_TYPES:
                problems.append(f"{path}: invalid type entry {entry!r}")
        base_types = [t for t in raw_type if t != "null"]
    else:
        problems.append(f"{path}: 'type' is {type(raw_type).__name__}")
        base_types = []

    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, list) or not enum:
            problems.append(f"{path}: enum must be a non-empty list, got {enum!r}")
        else:
            for idx, value in enumerate(enum):
                if isinstance(value, str) and value == "":
                    problems.append(f"{path}: enum[{idx}] is an empty string (Google rejects empty enum values)")
                if len(base_types) == 1 and base_types[0] in _TYPE_MAP:
                    expected = _TYPE_MAP[base_types[0]]
                    if base_types[0] == "integer" and isinstance(value, bool):
                        problems.append(f"{path}: enum[{idx}]={value!r} is a bool, not an integer")
                    elif not isinstance(value, expected):
                        problems.append(
                            f"{path}: enum[{idx}]={value!r} does not match declared type {base_types[0]!r}"
                        )

    props = schema.get("properties")
    if props is not None and not isinstance(props, dict):
        problems.append(f"{path}: 'properties' is not an object")
        props = None
    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list):
            problems.append(f"{path}: 'required' is not a list")
        else:
            for entry in required:
                if not isinstance(entry, str):
                    problems.append(f"{path}: required entry {entry!r} is not a string")
                elif isinstance(props, dict) and entry not in props:
                    problems.append(f"{path}: required names undeclared property {entry!r}")
    if isinstance(props, dict):
        for prop_name, sub_schema in props.items():
            _check_node(sub_schema, f"{path}.properties.{prop_name}", problems)
    items = schema.get("items")
    if isinstance(items, dict):
        _check_node(items, f"{path}.items", problems)


TOOL_CLASSES = _collect_tool_classes()


def test_tool_schema_collection_is_complete() -> None:
    """Guard against a vacuous pass: collection must actually find the
    builtin tool set, including the tool from the 2026-11-14 incident."""
    assert len(TOOL_CLASSES) >= 90, f"only {len(TOOL_CLASSES)} tool classes collected"
    names = {f"{c.__module__}.{c.__qualname__}" for c in TOOL_CLASSES}
    assert "friday.tools.builtin.sentinel_security.SentinelSecurityTool" in names


@pytest.mark.parametrize(
    "tool_cls",
    TOOL_CLASSES,
    ids=[f"{c.__module__}.{c.__qualname__}" for c in TOOL_CLASSES],
)
def test_tool_schema_is_gemini_valid(tool_cls: type[BaseTool]) -> None:
    schema = _resolve_parameters(tool_cls)
    problems: list[str] = []
    _check_node(schema, "$", problems)
    assert not problems, (
        f"{tool_cls.__module__}.{tool_cls.__qualname__} schema is not valid "
        f"for Gemini function declarations:\n" + "\n".join(problems)
    )


def test_sentinel_security_severity_enum_regression() -> None:
    """The 2026-11-14 incident, pinned: severity must not offer "" — the
    'any severity' meaning is expressed by OMITTING the optional
    parameter (the handler still defaults severity to "" internally)."""
    from friday.tools.builtin.sentinel_security import SentinelSecurityTool

    props = SentinelSecurityTool.parameters["properties"]
    severity = props["severity"]
    assert "" not in severity["enum"]
    assert set(severity["enum"]) == {"critical", "high", "medium", "low"}
    assert "severity" not in SentinelSecurityTool.parameters.get("required", [])
