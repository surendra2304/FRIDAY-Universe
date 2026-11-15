"""TASK-IG-FRG-04: sketch-to-prompt front end (M3E Canvas pattern).

Corpus source: DejpO6SgeTK — M3E Canvas (lnkiai/m3e-canvas, MIT; repo
card verdict: **adopt**): the owner sketches an app from real Material
3 components, links screens into tap/swipe flows, and the tool emits a
concise natural-language prompt that an AI coding tool builds from.
The hosted tool is zero-cost and usable as-is; this module implements
the same emission contract *inside* Forge, so a sketch — exported from
M3E Canvas, or written by hand in the same shape — becomes a Forge
build brief without depending on any external service at build time.

Contract:

* Input: a sketch object ``{app_name, screens: [{id, name,
  components: [{type, label}], links: [{to, trigger}]}]}``.
* Structural defects (no app name, no screens, duplicate screen ids,
  a link to a screen that does not exist) fail closed with every
  problem named — a broken sketch must not silently lose a screen.
* A component whose type is outside the Material-3 vocabulary below
  is *kept* (the owner may be sketching something custom) but named
  in ``SketchBrief.warnings`` — surfaced, never silently normalised.
* Output: :meth:`SketchBrief.to_prompt` — a deterministic,
  structured prompt (same sketch -> same prompt, byte for byte) that
  names every screen, its components, and every navigation flow, and
  ends with the explicit page-per-screen file expectation Forge
  builds against.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

# The Material 3 component vocabulary M3E Canvas sketches with.
# Types outside this set are kept but warned about (see module docstring).
M3_COMPONENT_TYPES = frozenset(
    {
        "app_bar",
        "avatar",
        "badge",
        "bottom_sheet",
        "button",
        "card",
        "checkbox",
        "chip",
        "dialog",
        "divider",
        "fab",
        "icon",
        "icon_button",
        "image",
        "list",
        "list_item",
        "menu",
        "navigation_bar",
        "navigation_drawer",
        "progress",
        "radio",
        "search_bar",
        "slider",
        "snackbar",
        "switch",
        "tab_bar",
        "text",
        "text_field",
    }
)


@dataclass
class SketchComponent:
    type: str
    label: str = ""


@dataclass
class SketchLink:
    to: str  # target screen id
    trigger: str = "tap"  # what the user does: tap / swipe / a control label


@dataclass
class SketchScreen:
    id: str
    name: str
    components: List[SketchComponent] = field(default_factory=list)
    links: List[SketchLink] = field(default_factory=list)


@dataclass
class SketchBrief:
    app_name: str
    screens: List[SketchScreen] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def screen_by_id(self, screen_id: str) -> SketchScreen:
        for screen in self.screens:
            if screen.id == screen_id:
                return screen
        raise KeyError(f"unknown screen id: {screen_id}")

    def flows(self) -> List[str]:
        """Navigation flows as sentences: 'Home --tap--> Details'."""
        out: List[str] = []
        for screen in self.screens:
            for link in screen.links:
                target = self.screen_by_id(link.to)
                out.append(
                    f"{screen.name} --{link.trigger}--> {target.name}"
                )
        return out

    def to_prompt(self) -> str:
        """The deterministic build prompt for this sketch."""
        lines = [
            f"Build the app '{self.app_name}' from this screen sketch.",
            "",
            "Screens and components:",
        ]
        for screen in self.screens:
            if screen.components:
                comp_text = ", ".join(
                    f"{c.type} '{c.label}'" if c.label else c.type
                    for c in screen.components
                )
            else:
                comp_text = "(no components sketched)"
            lines.append(f"- Screen '{screen.name}' (id: {screen.id}): {comp_text}")
        flows = self.flows()
        if flows:
            lines.append("")
            lines.append("Navigation flows:")
            for flow in flows:
                lines.append(f"- {flow}")
        lines.append("")
        lines.append(
            "Build one page per screen, wire every navigation flow above, "
            "and use the sketched components as the layout for each screen "
            "— do not add screens that are not in the sketch."
        )
        if self.warnings:
            lines.append("")
            lines.append("Sketch warnings (resolve or confirm before building):")
            for warning in self.warnings:
                lines.append(f"- {warning}")
        return "\n".join(lines)


def parse_sketch(sketch: Any) -> SketchBrief:
    """Validate a sketch object into a SketchBrief.

    Structural problems raise ValueError naming every problem.
    Unknown component types do not raise — they are collected as
    named warnings on the brief.
    """
    problems: List[str] = []
    warnings: List[str] = []
    if not isinstance(sketch, dict):
        raise ValueError(f"sketch must be an object, got {type(sketch).__name__}")
    app_name = sketch.get("app_name")
    if not isinstance(app_name, str) or not app_name.strip():
        problems.append("sketch.app_name is missing or empty")
        app_name = ""
    raw_screens = sketch.get("screens")
    if not isinstance(raw_screens, list) or not raw_screens:
        problems.append("sketch.screens must be a non-empty list")
        raw_screens = []
    screens: List[SketchScreen] = []
    seen_ids = set()
    for i, raw_screen in enumerate(raw_screens):
        if not isinstance(raw_screen, dict):
            problems.append(f"screens[{i}] is not an object")
            continue
        screen_id = raw_screen.get("id")
        if not isinstance(screen_id, str) or not screen_id.strip():
            problems.append(f"screens[{i}].id is missing or empty")
            screen_id = f"screen-{i}"
        if screen_id in seen_ids:
            problems.append(f"duplicate screen id: {screen_id}")
        seen_ids.add(screen_id)
        name = raw_screen.get("name")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"screens[{i}].name is missing or empty")
            name = screen_id
        components: List[SketchComponent] = []
        raw_components = raw_screen.get("components", [])
        if not isinstance(raw_components, list):
            problems.append(f"screens[{i}].components must be a list")
            raw_components = []
        for j, raw_component in enumerate(raw_components):
            if not isinstance(raw_component, dict):
                problems.append(f"screens[{i}].components[{j}] is not an object")
                continue
            ctype = raw_component.get("type")
            if not isinstance(ctype, str) or not ctype.strip():
                problems.append(f"screens[{i}].components[{j}].type is missing")
                continue
            if ctype not in M3_COMPONENT_TYPES:
                warnings.append(
                    f"screen '{name}': component type '{ctype}' is not in the "
                    "Material 3 vocabulary — kept as a custom component"
                )
            label = raw_component.get("label", "")
            components.append(
                SketchComponent(
                    type=ctype, label=label if isinstance(label, str) else ""
                )
            )
        links: List[SketchLink] = []
        raw_links = raw_screen.get("links", [])
        if not isinstance(raw_links, list):
            problems.append(f"screens[{i}].links must be a list")
            raw_links = []
        for j, raw_link in enumerate(raw_links):
            if not isinstance(raw_link, dict):
                problems.append(f"screens[{i}].links[{j}] is not an object")
                continue
            to = raw_link.get("to")
            if not isinstance(to, str) or not to.strip():
                problems.append(f"screens[{i}].links[{j}].to is missing")
                continue
            trigger = raw_link.get("trigger", "tap")
            links.append(
                SketchLink(to=to, trigger=trigger if isinstance(trigger, str) else "tap")
            )
        screens.append(
            SketchScreen(id=screen_id, name=name, components=components, links=links)
        )
    # Second pass: links must target screens that exist.
    known_ids = {s.id for s in screens}
    for screen in screens:
        for link in screen.links:
            if link.to not in known_ids:
                problems.append(
                    f"screen '{screen.name}' links to unknown screen id '{link.to}'"
                )
    if problems:
        raise ValueError("invalid sketch: " + "; ".join(problems))
    return SketchBrief(app_name=app_name, screens=screens, warnings=warnings)


def sketch_to_prompt(sketch: Any) -> str:
    """Convenience: sketch object -> build prompt in one call."""
    return parse_sketch(sketch).to_prompt()
