"""
Gradio instant-UI delivery layer for Forge one-prompt internal tools.

TASK-FRG-030: Forge's one-prompt remit gains a Gradio delivery layer for
instant interactive UIs (sliders, inputs, live outputs) for internal tools
where a full app is overkill, with a recorded rule for when Gradio vs a full
app is used.

Free-only: ``gradio`` is a free PyPI package. Launches default to
``share=False`` (local only — no hosted share link, no paid tier).

Design notes
------------
- ``gradio`` is imported lazily inside :func:`build_interface`, so importing
  this module never requires the UI dependency; a clear error is raised when
  a UI is actually built without it installed.
- A tool is described by a :class:`ToolSpec`: a plain function plus declared
  inputs/outputs. The layer turns the declaration into a ``gr.Interface`` —
  nothing about the tool's own logic lives here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("delivery.gradio_layer")

#: Recorded rule (TASK-FRG-030 acceptance): when Gradio vs a full app.
GRADIO_RULE = (
    "Use Gradio when the tool is single-purpose, internal-only, needs no auth, "
    "no multi-user state and no persistent DB, and the UI is under a day of work. "
    "Build a full app when it is multi-user, public-facing, needs auth or "
    "persistent state, or needs a custom frontend."
)

#: Input kinds the layer knows how to render. ``slider`` maps to gr.Slider,
#: ``dropdown`` to gr.Dropdown, ``textbox`` to gr.Textbox, ``number`` to gr.Number.
INPUT_KINDS = ("textbox", "dropdown", "slider", "number")

#: Output kinds. ``markdown`` maps to gr.Markdown, ``textbox`` to gr.Textbox.
OUTPUT_KINDS = ("markdown", "textbox")


@dataclass
class ToolSpec:
    """A one-prompt-built internal tool, as the delivery layer sees it."""

    name: str
    description: str
    fn: Callable[..., str]
    inputs: list[dict[str, Any]] = field(default_factory=list)
    outputs: list[dict[str, Any]] = field(default_factory=lambda: [{"kind": "markdown"}])
    examples: list[list[Any]] = field(default_factory=list)


def _build_component(gr: Any, spec: dict[str, Any], *, is_output: bool = False) -> Any:
    """Turn one declared input/output spec into a Gradio component."""
    kind = spec.get("kind", "textbox")
    label = spec.get("label")
    if is_output:
        if kind not in OUTPUT_KINDS:
            raise ValueError(f"unknown output kind: {kind!r} (expected one of {OUTPUT_KINDS})")
        if kind == "markdown":
            return gr.Markdown(label=label)
        return gr.Textbox(label=label, lines=10)
    if kind not in INPUT_KINDS:
        raise ValueError(f"unknown input kind: {kind!r} (expected one of {INPUT_KINDS})")
    if kind == "textbox":
        return gr.Textbox(
            label=label,
            value=spec.get("default", ""),
            placeholder=spec.get("placeholder", ""),
            lines=spec.get("lines", 1),
        )
    if kind == "dropdown":
        choices = spec.get("choices") or []
        return gr.Dropdown(label=label, choices=choices, value=spec.get("default", choices[0] if choices else None))
    if kind == "slider":
        return gr.Slider(
            label=label,
            minimum=spec.get("minimum", 1),
            maximum=spec.get("maximum", 10),
            step=spec.get("step", 1),
            value=spec.get("default", spec.get("minimum", 1)),
        )
    return gr.Number(label=label, value=spec.get("default", 0))


def build_interface(spec: ToolSpec) -> Any:
    """Build a ``gr.Interface`` for a tool spec. Does not launch anything."""
    try:
        import gradio as gr
    except ImportError as exc:  # pragma: no cover - environment without gradio
        raise RuntimeError(
            "gradio is not installed; add it with `pip install gradio` "
            "(free, PyPI) or `pip install -r Forge/requirements.txt`."
        ) from exc
    inputs = [_build_component(gr, s) for s in spec.inputs]
    outputs = [_build_component(gr, s, is_output=True) for s in spec.outputs]
    return gr.Interface(
        fn=spec.fn,
        inputs=inputs,
        outputs=outputs,
        title=spec.name,
        description=spec.description,
        examples=spec.examples or None,
    )


def launch_tool(spec: ToolSpec, *, server_port: int = 7860, **launch_kwargs: Any) -> Any:
    """Build and launch a tool's Gradio UI locally (share=False always)."""
    launch_kwargs.setdefault("share", False)
    launch_kwargs.setdefault("server_port", server_port)
    iface = build_interface(spec)
    logger.info("launching Gradio UI for %s on port %s", spec.name, server_port)
    return iface.launch(**launch_kwargs)


def front_one_prompt_flow(default_output_root: str = "created_agents") -> Any:
    """Demo surface: the one-prompt flow itself, fronted by Gradio.

    Prompt textbox + output-root textbox -> :func:`create_agent` summary.
    The import is lazy so this module stays importable without the template
    package; the call is honest about failure (returns the error as text).
    """
    from app.templates.agent_creation import create_agent

    def _run(prompt: str, output_root: str) -> str:
        try:
            result = create_agent(prompt, Path(output_root or default_output_root))
        except Exception as exc:  # noqa: BLE001 - surfaced verbatim to the UI
            return f"FAILED: {type(exc).__name__}: {exc}"
        return str(result)

    spec = ToolSpec(
        name="Forge one-prompt agent builder",
        description=(
            "One plain-language prompt becomes a configured single-file agent "
            "(template one-prompt-agent). Demo surface for the Gradio delivery layer."
        ),
        fn=_run,
        inputs=[
            {"kind": "textbox", "label": "Prompt", "lines": 4,
             "placeholder": "Build a one-prompt agent that ..."},
            {"kind": "textbox", "label": "Output root", "default": default_output_root},
        ],
        outputs=[{"kind": "textbox", "label": "Result"}],
    )
    return build_interface(spec)
