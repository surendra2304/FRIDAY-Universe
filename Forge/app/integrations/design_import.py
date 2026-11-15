"""TASK-IG-FRG-03: design-tool-to-agent pipeline (design spec -> build).

Corpus source: DcbDzR8yxCm — a creator connects Google Stitch to an
agentic IDE via MCP; the design is generated in Stitch, then coded and
deployed live by the agent, zero code written by hand. The pipeline
shape is: **design tool -> structured design -> agent build -> deploy**.

Forge owns the middle of that pipeline. This module is the import
half, implemented as a pattern that works today with an exported spec
and tomorrow with a live MCP source:

* :func:`parse_design_spec` validates a design-tool export (Stitch /
  Figma shape: named screens, components per screen, design tokens)
  into a :class:`DesignBrief`. Invalid specs fail closed with every
  problem named — a half-parsed design must never become a build.
* :meth:`DesignBrief.to_manifest` derives the explicit file layout
  (one page per screen, one partial per unique component, a tokens
  stylesheet) — the same explicit-manifest shape TASK-FRG-004 builds
  from goals, so a design-driven build and a goal-driven build meet
  at the same contract.
* :meth:`DesignBrief.to_goal` renders the build goal text, naming
  every manifest file, with the design's provenance attached.
* :class:`McpDesignSource` is the live-source seam: it speaks to
  whatever fetcher a deployment injects (an MCP client for Stitch /
  Figma). With no fetcher configured it raises
  :class:`DesignSourceUnavailable` — fail-closed, no silent mock
  design, no fabricated import.

Deploy stays where it already lives (Forge's delivery/deployment
layers); this module ends at a buildable brief, and says so.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class DesignSourceUnavailable(RuntimeError):
    """Raised when a live design source is requested but none is
    configured. Distinct from a parse failure: the design was never
    fetched at all, and callers must not proceed as if it had been."""


def slugify(name: str) -> str:
    """Deterministic file-safe slug for a screen/component name."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).strip().lower()).strip("-")
    return slug or "unnamed"


@dataclass
class DesignComponent:
    type: str
    name: str = ""
    props: Dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.name or self.type


@dataclass
class DesignScreen:
    name: str
    route: str = ""
    components: List[DesignComponent] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return slugify(self.name)

    @property
    def page_path(self) -> str:
        """The page file this screen maps to. The root screen (route
        '/' or the first screen) is index.html; others are named."""
        if self.route.strip() in {"", "/"}:
            return "index.html"
        return f"{self.slug}.html"


@dataclass
class ManifestEntry:
    path: str
    purpose: str
    kind: str  # page / component / style / data

    def to_dict(self) -> dict:
        return {"path": self.path, "purpose": self.purpose, "kind": self.kind}


@dataclass
class DesignBrief:
    name: str
    source_tool: str  # e.g. "stitch", "figma", "export"
    source_ref: str = ""
    screens: List[DesignScreen] = field(default_factory=list)
    tokens: Dict[str, Any] = field(default_factory=dict)

    # -- derived views --------------------------------------------------

    def unique_components(self) -> List[str]:
        seen: List[str] = []
        for screen in self.screens:
            for component in screen.components:
                label = component.label
                if label not in seen:
                    seen.append(label)
        return seen

    def to_manifest(self) -> List[ManifestEntry]:
        """The explicit file layout for this design. Deterministic:
        same brief -> same manifest, in screen order."""
        entries: List[ManifestEntry] = []
        used_paths = set()
        for index, screen in enumerate(self.screens):
            path = screen.page_path
            if index > 0 and path == "index.html":
                path = f"{screen.slug}.html"
            if path in used_paths:  # two screens, one route: disambiguate, never collide
                path = f"{screen.slug}.html"
            used_paths.add(path)
            entries.append(
                ManifestEntry(
                    path=path,
                    purpose=f"Page for screen '{screen.name}'"
                    + (f" (route {screen.route})" if screen.route else ""),
                    kind="page",
                )
            )
        for label in self.unique_components():
            entries.append(
                ManifestEntry(
                    path=f"components/{slugify(label)}.html",
                    purpose=f"Reusable component '{label}'",
                    kind="component",
                )
            )
        if self.tokens:
            entries.append(
                ManifestEntry(
                    path="assets/tokens.css",
                    purpose="Design tokens (colors, typography, spacing) as CSS variables",
                    kind="style",
                )
            )
        entries.append(
            ManifestEntry(
                path="assets/design-brief.json",
                purpose="The imported design brief (provenance + screens + tokens)",
                kind="data",
            )
        )
        return entries

    def tokens_css(self) -> str:
        """Design tokens rendered as CSS custom properties."""
        lines = [":root {"]
        colors = self.tokens.get("colors", {})
        if isinstance(colors, dict):
            for key in sorted(colors):
                lines.append(f"  --color-{slugify(key)}: {colors[key]};")
        fonts = self.tokens.get("fonts", {})
        if isinstance(fonts, dict):
            for key in sorted(fonts):
                lines.append(f"  --font-{slugify(key)}: {fonts[key]};")
        spacing = self.tokens.get("spacing", {})
        if isinstance(spacing, dict):
            for key in sorted(spacing):
                lines.append(f"  --space-{slugify(key)}: {spacing[key]};")
        lines.append("}")
        return "\n".join(lines) + "\n"

    def provenance(self) -> Dict[str, Any]:
        return {
            "source_tool": self.source_tool,
            "source_ref": self.source_ref,
            "design_name": self.name,
            "screens": [s.name for s in self.screens],
            "components": self.unique_components(),
            "token_groups": sorted(self.tokens.keys()),
        }

    def to_goal(self) -> str:
        """The Forge build goal for this design, with the explicit
        manifest embedded (FRG-004's contract shape: the build must
        produce exactly these files)."""
        manifest = self.to_manifest()
        lines = [
            f"Build the website '{self.name}' from the imported design "
            f"(source: {self.source_tool}"
            + (f", ref: {self.source_ref}" if self.source_ref else "")
            + ").",
            "",
            "Screens:",
        ]
        for screen in self.screens:
            comp_names = ", ".join(c.label for c in screen.components) or "(none)"
            lines.append(
                f"- {screen.name}"
                + (f" (route {screen.route})" if screen.route else "")
                + f": components: {comp_names}"
            )
        if self.tokens:
            lines.append("")
            lines.append(
                "Apply the design tokens from assets/tokens.css (colors, "
                "typography, spacing) — do not substitute a different palette."
            )
        lines.append("")
        lines.append("The build MUST produce exactly these files:")
        for entry in manifest:
            lines.append(f"- {entry.path} — {entry.purpose}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Parsing / validation — fail closed, every problem named
# ---------------------------------------------------------------------------


def parse_design_spec(spec: Any, source_tool: str = "export", source_ref: str = "") -> DesignBrief:
    """Validate a design-tool export into a DesignBrief.

    Raises ValueError listing *every* problem found, so a malformed
    export is rejected as a whole instead of half-imported.
    """
    problems: List[str] = []
    if not isinstance(spec, dict):
        raise ValueError(f"design spec must be an object, got {type(spec).__name__}")
    name = spec.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("spec.name is missing or empty")
        name = ""
    raw_screens = spec.get("screens")
    if not isinstance(raw_screens, list) or not raw_screens:
        problems.append("spec.screens must be a non-empty list")
        raw_screens = []
    screens: List[DesignScreen] = []
    for i, raw_screen in enumerate(raw_screens):
        if not isinstance(raw_screen, dict):
            problems.append(f"screens[{i}] is not an object")
            continue
        screen_name = raw_screen.get("name")
        if not isinstance(screen_name, str) or not screen_name.strip():
            problems.append(f"screens[{i}].name is missing or empty")
            screen_name = f"screen-{i}"
        components: List[DesignComponent] = []
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
                problems.append(
                    f"screens[{i}].components[{j}].type is missing or empty"
                )
                continue
            cname = raw_component.get("name", "")
            props = raw_component.get("props", {})
            if not isinstance(props, dict):
                problems.append(f"screens[{i}].components[{j}].props must be an object")
                props = {}
            components.append(
                DesignComponent(
                    type=ctype,
                    name=cname if isinstance(cname, str) else "",
                    props=props,
                )
            )
        route = raw_screen.get("route", "")
        screens.append(
            DesignScreen(
                name=screen_name,
                route=route if isinstance(route, str) else "",
                components=components,
            )
        )
    tokens = spec.get("tokens", {})
    if not isinstance(tokens, dict):
        problems.append("spec.tokens must be an object when present")
        tokens = {}
    if problems:
        raise ValueError("invalid design spec: " + "; ".join(problems))
    return DesignBrief(
        name=name,
        source_tool=source_tool,
        source_ref=source_ref,
        screens=screens,
        tokens=tokens,
    )


# ---------------------------------------------------------------------------
# Live-source seam (MCP) — fail closed when unconfigured
# ---------------------------------------------------------------------------

# A fetcher takes a design reference (URL / file id) and returns the
# raw spec dict. In production this is where an MCP client for the
# design tool plugs in; this module ships no network code of its own.
DesignFetcher = Callable[[str], Dict[str, Any]]


class McpDesignSource:
    """Design source backed by an injected fetcher (the MCP seam)."""

    def __init__(self, fetcher: Optional[DesignFetcher] = None, tool_name: str = "mcp"):
        self._fetcher = fetcher
        self._tool_name = tool_name

    def fetch_design(self, ref: str) -> DesignBrief:
        if self._fetcher is None:
            raise DesignSourceUnavailable(
                "no design fetcher configured: connect a design-tool MCP "
                "source (Stitch/Figma) or import an exported spec with "
                "parse_design_spec instead — refusing to fabricate a design"
            )
        if not ref or not str(ref).strip():
            raise ValueError("design ref is empty")
        raw = self._fetcher(str(ref))
        return parse_design_spec(raw, source_tool=self._tool_name, source_ref=str(ref))
