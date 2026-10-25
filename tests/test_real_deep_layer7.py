"""
Real Deep Layer 7 Tests — Diagram Design → VyralX.

Real functional tests for VyralX/app/agents/real_diagram_design.py:
colour maths and WCAG contrast, palette derivation, text measurement and
wrapping, diagram type selection, every layout engine, SVG/HTML rendering,
Mermaid import, validation findings and the studio facade.
"""

import importlib.util
import math
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "VyralX", "app", "agents", "real_diagram_design.py",
)


def _load():
    spec = importlib.util.spec_from_file_location("real_diagram_design", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules["real_diagram_design"] = module
    spec.loader.exec_module(module)
    return module


dd = _load()


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def studio():
    return dd.DiagramStudio()


def _flow_spec():
    nodes = [
        dd.DiagramNode("collect", "Collect request", "step"),
        dd.DiagramNode("check", "Token valid?", "decision"),
        dd.DiagramNode("refresh", "Refresh token", "step"),
        dd.DiagramNode("forward", "Forward request", "step"),
    ]
    edges = [
        dd.DiagramEdge("collect", "check"),
        dd.DiagramEdge("check", "refresh", label="no"),
        dd.DiagramEdge("check", "forward", label="yes"),
        dd.DiagramEdge("refresh", "forward"),
    ]
    return dd.DiagramSpec(title="Auth flow", diagram_type="flowchart", nodes=nodes, edges=edges)


def _sequence_spec():
    nodes = [dd.DiagramNode(name.lower(), name, "actor") for name in ("Client", "API", "Auth")]
    edges = [
        dd.DiagramEdge("client", "api", label="GET /me"),
        dd.DiagramEdge("api", "auth", label="refresh"),
        dd.DiagramEdge("auth", "api", label="token"),
        dd.DiagramEdge("api", "client", label="200 OK"),
    ]
    return dd.DiagramSpec(title="Token refresh", diagram_type="sequence", nodes=nodes, edges=edges)


# ── Colour ────────────────────────────────────────────────────────────────

class TestColour:
    def test_hex_roundtrip(self):
        assert dd.hex_to_rgb("#bf4520").as_tuple() == (191, 69, 32)
        assert dd.hex_to_rgb("bf4520").hex() == "#bf4520"
        assert dd.hex_to_rgb("#fff").hex() == "#ffffff"
        with pytest.raises(ValueError):
            dd.hex_to_rgb("#12345")
        with pytest.raises(ValueError):
            dd.hex_to_rgb("not-a-colour")

    def test_hsl_roundtrip(self):
        for seed in ("#bf4520", "#2f6f4f", "#1a1a1a", "#ffffff"):
            hue, sat, light = dd.rgb_to_hsl(dd.hex_to_rgb(seed))
            assert dd.hsl_to_rgb(hue, sat, light).hex() == seed
        hue, sat, light = dd.rgb_to_hsl(dd.hex_to_rgb("#808080"))
        assert sat == 0.0
        assert dd.hsl_to_rgb(0, 0, 1).hex() == "#ffffff"
        assert dd.hsl_to_rgb(0, 0, 0).hex() == "#000000"

    def test_contrast_ratio_bounds(self):
        assert dd.contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
        assert dd.contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0)
        assert dd.contrast_ratio("#777777", "#ffffff") < 4.5
        assert dd.contrast_ratio("#767676", "#ffffff") > 4.0

    def test_relative_luminance_ordering(self):
        assert dd.relative_luminance("#ffffff") == pytest.approx(1.0, abs=1e-3)
        assert dd.relative_luminance("#000000") == pytest.approx(0.0, abs=1e-3)
        assert dd.relative_luminance("#eeeeee") > dd.relative_luminance("#888888")

    def test_mix_lighten_darken(self):
        assert dd.mix("#000000", "#ffffff", 0.5) == "#808080"
        assert dd.mix("#000000", "#ffffff", 0) == "#000000"
        assert dd.mix("#000000", "#ffffff", 1) == "#ffffff"
        assert dd.relative_luminance(dd.lighten("#333333", 0.2)) > dd.relative_luminance("#333333")
        assert dd.relative_luminance(dd.darken("#cccccc", 0.2)) < dd.relative_luminance("#cccccc")

    def test_hue_rotation_keeps_identity(self):
        rotated = dd.rotate_hue("#bf4520", 180)
        assert rotated != "#bf4520"
        assert dd.contrast_ratio(rotated, "#ffffff") > 1.0

    def test_text_selection_and_contrast_repair(self):
        assert dd.readable_text_on("#101010") == "#fdfbf7"
        assert dd.readable_text_on("#fefefe") == "#161412"
        repaired = dd.ensure_contrast("#777777", "#ffffff", minimum=4.5)
        assert dd.contrast_ratio(repaired, "#ffffff") >= 4.5
        # Already-good colours are returned untouched.
        assert dd.ensure_contrast("#000000", "#ffffff") == "#000000"


class TestBrandPalette:
    def test_palette_is_contrast_safe(self):
        palette = dd.BrandPalette.from_seed("#bf4520")
        assert dd.contrast_ratio(palette.ink, palette.paper) > 12
        assert dd.contrast_ratio(palette.muted, palette.paper) >= 4.5
        assert palette.seed.startswith("#") and len(palette.seed) == 7
        assert set(palette.as_dict()) == {"seed", "ink", "paper", "muted", "line", "accent", "surface"}

    def test_tints_and_categorical_series(self):
        palette = dd.BrandPalette.from_seed("#2f6f4f")
        tints = palette.tints(4)
        assert len(tints) == 4
        assert len(set(tints)) == 4
        categorical = palette.categorical(6)
        assert len(set(categorical)) == 6
        assert all(dd.contrast_ratio(c, palette.paper) >= 3.0 for c in categorical)

    def test_seed_without_hash_and_custom_paper(self):
        palette = dd.BrandPalette.from_seed("bf4520", name="acme", paper="#ffffff")
        assert palette.name == "acme"
        assert palette.paper == "#ffffff"


class TestTheme:
    def test_css_contains_tokens(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        css = theme.css()
        assert "--ink:" in css and "--brand:#bf4520" in css
        assert "font-family" in css
        assert "h1" in css
        assert theme.esc().startswith("<style>")

    def test_defaults(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#123456"))
        assert theme.base_size > 10
        assert theme.radius > 0
        assert theme.stroke > 0


# ── Text ──────────────────────────────────────────────────────────────────

class TestTextMeasurer:
    measurer = dd.TextMeasurer()

    def test_width_scales_with_size(self):
        narrow = self.measurer.width("iiii", 14)
        wide = self.measurer.width("MMMM", 14)
        assert wide > narrow
        assert self.measurer.width("abc", 28) == pytest.approx(
            self.measurer.width("abc", 14) * 2)

    def test_wrap_respects_width(self):
        lines = self.measurer.wrap("the quick brown fox jumps over the lazy dog", 90, 14)
        assert len(lines) > 1
        assert " ".join(lines).split() == "the quick brown fox jumps over the lazy dog".split()
        assert all(self.measurer.width(line, 14) <= 90 or " " not in line for line in lines)

    def test_wrap_edge_cases(self):
        assert self.measurer.wrap("", 100, 14) == [""]
        assert self.measurer.wrap("single", 500, 14) == ["single"]


# ── Catalogue and selection ───────────────────────────────────────────────

class TestDiagramCatalogue:
    def test_catalogue_size_and_uniqueness(self):
        assert len(dd.DIAGRAM_TYPES) >= 45
        ids = [t.type_id for t in dd.DIAGRAM_TYPES]
        assert len(ids) == len(set(ids))
        assert len(dd.TYPE_INDEX) == len(ids)

    def test_every_type_has_a_layout_engine(self):
        for diagram_type in dd.DIAGRAM_TYPES:
            assert diagram_type.layout in dd.LAYOUT_ENGINES, diagram_type.type_id
            assert diagram_type.keywords
            assert diagram_type.category

    def test_at_least_seven_categories(self):
        assert len({t.category for t in dd.DIAGRAM_TYPES}) >= 7


class TestDiagramSelector:
    def test_selects_matching_types(self):
        selector = dd.DiagramSelector()
        assert selector.select("sequence of a bearer call with token refresh on 401").type_id == "sequence"
        assert selector.select("quadrant showing projects by impact vs effort").type_id == "quadrant"
        assert selector.select("architecture diagram frontend backend database redis cache").type_id == "architecture"
        assert selector.select("org chart of the engineering team").type_id == "org-chart"

    def test_fallback(self):
        selector = dd.DiagramSelector()
        fallback = selector.select("zzzz qqqq")
        assert fallback.type_id == "flowchart"

    def test_rank_is_ordered(self):
        ranked = dd.DiagramSelector().rank("funnel conversion dropoff stages")
        assert ranked
        assert ranked[0][0].type_id == "funnel"
        scores = [score for _t, score in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_explain(self):
        info = dd.DiagramSelector().explain("timeline of milestones and dates")
        assert info["type"] == "timeline"
        assert info["category"] == "time"
        assert isinstance(info["alternatives"], list)


# ── Layout ────────────────────────────────────────────────────────────────

class TestLayeredLayout:
    def test_layers_follow_edges(self, studio):
        artifact = studio.build(_flow_spec())
        boxes = artifact.layout.boxes
        assert boxes["collect"].y < boxes["check"].y < boxes["forward"].y
        assert artifact.layout.routes
        assert all(len(route.points) >= 2 for route in artifact.layout.routes)

    def test_no_overlaps(self, studio):
        artifact = studio.build(_flow_spec())
        assert artifact.layout.overlaps() == []
        assert artifact.report.passed

    def test_cycle_removal_marks_back_edges(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        nodes = [dd.DiagramNode(n, n.title()) for n in ("a", "b", "c")]
        edges = [dd.DiagramEdge("a", "b"), dd.DiagramEdge("b", "c"), dd.DiagramEdge("c", "a")]
        layout = dd.LayeredLayout(theme).layout(
            dd.DiagramSpec("Cycle", "flowchart", nodes=nodes, edges=edges))
        assert len(layout.boxes) == 3
        assert any(route.reversed for route in layout.routes)

    def test_left_to_right_direction(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        nodes = [dd.DiagramNode(n, n.title()) for n in ("a", "b")]
        layout = dd.LayeredLayout(theme, direction="LR").layout(
            dd.DiagramSpec("LR", "flowchart", nodes=nodes,
                           edges=[dd.DiagramEdge("a", "b")]))
        assert layout.boxes["a"].x < layout.boxes["b"].x
        assert layout.extras["direction"] == "LR"

    def test_empty_spec(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        layout = dd.LayeredLayout(theme).layout(dd.DiagramSpec("Empty", "flowchart"))
        assert layout.boxes == {}
        assert layout.extras.get("empty") is True


class TestTreeLayout:
    def test_parent_centred_over_children(self, studio):
        nodes = [
            dd.DiagramNode("ceo", "CEO"), dd.DiagramNode("cto", "CTO"),
            dd.DiagramNode("cfo", "CFO"), dd.DiagramNode("eng", "Engineering"),
        ]
        edges = [dd.DiagramEdge("ceo", "cto"), dd.DiagramEdge("ceo", "cfo"),
                 dd.DiagramEdge("cto", "eng")]
        artifact = studio.build(dd.DiagramSpec("Org", "org-chart", nodes=nodes, edges=edges))
        boxes = artifact.layout.boxes
        assert boxes["ceo"].y < boxes["cto"].y < boxes["eng"].y
        assert boxes["cto"].y == boxes["cfo"].y
        child_center = (boxes["cto"].center[0] + boxes["cfo"].center[0]) / 2
        assert boxes["ceo"].center[0] == pytest.approx(child_center, abs=1.0)
        assert artifact.report.passed

    def test_disconnected_nodes_are_placed(self, studio):
        nodes = [dd.DiagramNode("a", "A"), dd.DiagramNode("b", "B"), dd.DiagramNode("lonely", "Lonely")]
        artifact = studio.build(dd.DiagramSpec("Tree", "hierarchy", nodes=nodes,
                                              edges=[dd.DiagramEdge("a", "b")]))
        assert "lonely" in artifact.layout.boxes

    def test_cycles_do_not_hang(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        nodes = [dd.DiagramNode(n, n) for n in ("a", "b")]
        layout = dd.TreeLayout(theme).layout(dd.DiagramSpec(
            "Cycle", "tree", nodes=nodes,
            edges=[dd.DiagramEdge("a", "b"), dd.DiagramEdge("b", "a")]))
        assert len(layout.boxes) == 2


class TestSequenceLayout:
    def test_participants_and_message_order(self, studio):
        artifact = studio.build(_sequence_spec())
        layout = artifact.layout
        centers = [layout.boxes[n].center[0] for n in ("client", "api", "auth")]
        assert centers == sorted(centers)
        assert len(layout.routes) == 4
        ys = [route.points[0][1] for route in layout.routes]
        assert ys == sorted(ys)
        assert len(layout.extras["lifelines"]) == 3
        assert artifact.report.passed

    def test_self_message_routes_around(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        nodes = [dd.DiagramNode("a", "A"), dd.DiagramNode("b", "B")]
        layout = dd.SequenceLayout(theme).layout(dd.DiagramSpec(
            "Self", "sequence", nodes=nodes,
            edges=[dd.DiagramEdge("a", "a", label="retry")]))
        route = layout.routes[0]
        assert len(route.points) == 4
        assert route.points[1][0] > route.points[0][0]


class TestQuadrantLayout:
    def test_positions_follow_meta(self, studio):
        nodes = [
            dd.DiagramNode("hi", "High impact", meta={"x": 0.9, "y": 0.9}),
            dd.DiagramNode("lo", "Low impact", meta={"x": 0.1, "y": 0.1}),
        ]
        artifact = studio.build(dd.DiagramSpec(
            "Impact vs effort", "quadrant", nodes=nodes,
            meta={"x_label": "effort", "y_label": "impact",
                  "quadrant_labels": ["QUICK WINS", "BIG BETS", "FILL-INS", "THANKLESS"]},
        ))
        boxes = artifact.layout.boxes
        assert boxes["hi"].x > boxes["lo"].x
        assert boxes["hi"].y < boxes["lo"].y
        assert len(artifact.layout.extras["quadrants"]) == 4
        assert artifact.layout.extras["axis_labels"]
        assert artifact.report.passed

    def test_positions_are_clamped(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        layout = dd.QuadrantLayout(theme).layout(dd.DiagramSpec(
            "Clamp", "quadrant",
            nodes=[dd.DiagramNode("far", "Far", meta={"x": 9, "y": -4})]))
        box = layout.boxes["far"]
        assert box.x >= 0 and box.y >= 0
        assert box.right <= layout.width


class TestOtherLayouts:
    def test_matrix_grid(self, studio):
        nodes = [dd.DiagramNode(f"n{i}", f"Cell {i}", meta={"row": i // 2, "col": i % 2})
                 for i in range(4)]
        artifact = studio.build(dd.DiagramSpec("Grid", "kanban", nodes=nodes))
        boxes = artifact.layout.boxes
        assert boxes["n0"].y == boxes["n1"].y
        assert boxes["n0"].x < boxes["n1"].x
        assert artifact.layout.extras["columns"] == 2

    def test_timeline_alternates(self, studio):
        nodes = [dd.DiagramNode(f"e{i}", f"Event {i}", meta={"order": i}) for i in range(3)]
        artifact = studio.build(dd.DiagramSpec("History", "timeline", nodes=nodes))
        boxes = artifact.layout.boxes
        assert boxes["e0"].y < boxes["e1"].y          # first above the axis
        assert boxes["e0"].y == boxes["e2"].y         # every other event returns above
        assert artifact.layout.extras["axis"]["y"] > boxes["e0"].y
        assert artifact.layout.extras["timeline_nodes"][1]["above"] is False

    def test_funnel_narrows(self, studio):
        nodes = [dd.DiagramNode(f"s{i}", f"Stage {i}") for i in range(4)]
        artifact = studio.build(dd.DiagramSpec("Signup", "funnel", nodes=nodes))
        bands = artifact.layout.extras["funnel_bands"]
        assert bands[0]["top"] > bands[-1]["top"]
        assert artifact.layout.boxes["s0"].y < artifact.layout.boxes["s3"].y

    def test_pyramid_widens(self, studio):
        nodes = [dd.DiagramNode(f"s{i}", f"Level {i}") for i in range(3)]
        artifact = studio.build(dd.DiagramSpec("Needs", "pyramid", nodes=nodes))
        bands = artifact.layout.extras["funnel_bands"]
        # Apex at the top, foundation at the bottom: widths grow downwards.
        assert bands[-1]["top"] > bands[0]["top"]
        assert bands[0]["top"] < bands[0]["bottom"]
        assert artifact.layout.boxes["s0"].y < artifact.layout.boxes["s2"].y

    def test_venn_has_circles(self, studio):
        nodes = [dd.DiagramNode(n, n.title()) for n in ("alpha", "beta", "gamma")]
        artifact = studio.build(dd.DiagramSpec("Overlap", "venn", nodes=nodes))
        circles = artifact.layout.extras["circles"]
        assert len(circles) == 3
        assert all(c["r"] > 0 for c in circles)
        assert artifact.report.passed

    def test_radial_places_hub_centred(self, studio):
        nodes = [dd.DiagramNode("hub", "Hub")] + [
            dd.DiagramNode(f"s{i}", f"Spoke {i}") for i in range(4)
        ]
        edges = [dd.DiagramEdge("hub", f"s{i}") for i in range(4)]
        artifact = studio.build(dd.DiagramSpec("Network", "network-topology",
                                               nodes=nodes, edges=edges))
        hub = artifact.layout.boxes["hub"]
        for i in range(4):
            assert hub.center != artifact.layout.boxes[f"s{i}"].center
        assert artifact.layout.extras["hub"] == "hub"


# ── Rendering ─────────────────────────────────────────────────────────────

class TestSvgRenderer:
    def test_svg_structure(self, studio):
        artifact = studio.build(_flow_spec(), subtitle="bearer plus refresh")
        svg = artifact.svg
        assert svg.startswith("<svg")
        assert 'xmlns="http://www.w3.org/2000/svg"' in svg
        assert 'role="img"' in svg
        assert "Auth flow" in svg
        assert "bearer plus refresh" in svg
        assert "<defs>" in svg and "marker" in svg
        assert svg.count("<rect") >= len(_flow_spec().nodes)
        assert svg.endswith("</svg>")
        assert 'stroke-width="0"' not in svg

    def test_labels_are_escaped(self, studio):
        nodes = [dd.DiagramNode("a", "Tom & Jerry <script>", "step")]
        artifact = studio.build(dd.DiagramSpec("Escapes", "flowchart", nodes=nodes))
        assert "&amp;" in artifact.svg
        assert "&lt;script&gt;" in artifact.svg
        assert "<script>" not in artifact.svg

    def test_svg_has_no_external_refs_or_shadows(self, studio):
        svg = studio.build(_flow_spec()).svg
        assert "http" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
        assert "filter=" not in svg
        assert "box-shadow" not in svg
        assert "drop-shadow" not in svg

    def test_html_document_is_self_contained(self, studio):
        artifact = studio.build(_flow_spec())
        html = artifact.html
        assert html.startswith("<!DOCTYPE html>")
        assert "<style>" in html
        assert "<h1>Auth flow</h1>" in html
        assert dd.DiagramDocument.self_contained(html) is True
        assert "http://" not in html.replace('xmlns="http://www.w3.org/2000/svg"', "")
        assert dd.DiagramDocument.self_contained(
            '<html><script src="https://evil.test/x.js"></script></html>') is False
        assert dd.DiagramDocument.self_contained(
            '<html><style>@import url(https://x.test/a.css)</style></html>') is False

    def test_legend_rendered_for_mixed_kinds(self, studio):
        artifact = studio.build(_flow_spec())    # step + decision kinds
        assert 'font-size="11"' in artifact.svg
        assert artifact.svg.count("step") >= 1
        single = studio.build(dd.DiagramSpec(
            "One kind", "flowchart", nodes=[dd.DiagramNode("a", "Only")]))
        assert single.svg.count("legend") == 0

    def test_edges_and_labels(self, studio):
        artifact = studio.build(_flow_spec())
        assert artifact.svg.count("marker-end") == 4
        assert ">yes<" in artifact.svg and ">no<" in artifact.svg
        assert 'stroke-dasharray' not in artifact.svg    # all solid in this spec


# ── Import ────────────────────────────────────────────────────────────────

class TestMermaidImporter:
    def test_flowchart_import(self, studio):
        source = (
            "flowchart TD\n"
            "  A[Start] --> B{Token cached?}\n"
            "  B -->|yes| C[Use token]\n"
            "  B -->|no| D[Refresh token]\n"
            "  D --> C\n"
        )
        spec = dd.MermaidImporter().parse(source, title="Imported")
        assert spec.diagram_type == "flowchart"
        assert len(spec.nodes) == 4
        assert len(spec.edges) == 4
        node_b = spec.node("B")
        assert node_b.label == "Token cached?"
        assert node_b.kind == "decision"
        assert spec.meta["direction"] == "TD"
        assert any(edge.style == "solid" for edge in spec.edges)
        artifact = studio.build(spec)
        assert artifact.report.passed

    def test_sequence_import(self, studio):
        source = (
            "sequenceDiagram\n"
            "  participant C as Client\n"
            "  participant A as API\n"
            "  C->>A: GET /me\n"
            "  A->>A: validate\n"
            "  A-->>C: 200 OK\n"
        )
        spec = dd.MermaidImporter().parse(source, title="Seq")
        assert spec.diagram_type == "sequence"
        assert [n.node_id for n in spec.nodes] == ["C", "A"]
        assert spec.node("C").label == "Client"
        assert len(spec.edges) == 3
        assert spec.edges[-1].style == "dashed"
        artifact = studio.build(spec)
        assert artifact.report.passed

    def test_lr_direction(self):
        spec = dd.MermaidImporter().parse("flowchart LR\n A --> B\n", title="LR")
        assert spec.meta["direction"] == "LR"
        assert len(spec.nodes) == 2

    def test_comments_and_blank_lines(self):
        spec = dd.MermaidImporter().parse(
            "flowchart TD\n%% comment\n\n A[Alpha] --> B[Beta]\n", title="t")
        assert len(spec.nodes) == 2

    def test_studio_from_mermaid(self, studio):
        artifact = studio.from_mermaid("flowchart TD\n A --> B\n", title="Quick")
        assert artifact.spec.title == "Quick"
        assert artifact.summary()["nodes"] == 2


# ── Validation ────────────────────────────────────────────────────────────

class TestDiagramValidator:
    def test_clean_diagram_scores_full(self, studio):
        report = studio.build(_flow_spec()).report
        assert report.passed
        assert report.score == pytest.approx(1.0)
        assert report.checks >= 5
        assert report.as_dict()["errors"] == []

    def test_overlap_detected(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        spec = dd.DiagramSpec("Overlap", "flowchart",
                              nodes=[dd.DiagramNode("a", "A"), dd.DiagramNode("b", "B")])
        layout = dd.LayoutResult(
            boxes={"a": dd.Box(0, 0, 100, 40), "b": dd.Box(50, 20, 100, 40)},
            routes=[], width=400, height=300,
        )
        report = dd.DiagramValidator(theme).validate(spec, layout)
        assert not report.passed
        assert any(issue.code == "overlap" for issue in report.errors)
        assert report.score < 1.0

    def test_structure_errors(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        spec = dd.DiagramSpec("Bad", "flowchart", nodes=[dd.DiagramNode("a", "A")],
                              edges=[dd.DiagramEdge("a", "ghost")])
        assert spec.validate_structure() == ["edge target missing: ghost"]
        layout = dd.LayoutResult({}, [], 100, 100)
        report = dd.DiagramValidator(theme).validate(spec, layout)
        assert {issue.code for issue in report.errors} >= {"structure", "missing_box"}

    def test_canvas_overflow(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        spec = dd.DiagramSpec("Overflow", "flowchart", nodes=[dd.DiagramNode("a", "A")])
        layout = dd.LayoutResult({"a": dd.Box(0, 0, 500, 40)}, [], 200, 100)
        report = dd.DiagramValidator(theme).validate(spec, layout)
        assert any(issue.code == "bounds" and issue.severity == "error" for issue in report.issues)

    def test_crossing_count(self):
        a = dd.DiagramEdge("a", "b")
        b = dd.DiagramEdge("c", "d")
        layout = dd.LayoutResult({}, [
            dd.EdgeRoute(a, [(0, 0), (100, 100)]),
            dd.EdgeRoute(b, [(0, 100), (100, 0)]),
        ], 200, 200)
        assert dd.DiagramValidator.count_crossings(layout) == 1
        layout_parallel = dd.LayoutResult({}, [
            dd.EdgeRoute(a, [(0, 0), (100, 0)]),
            dd.EdgeRoute(b, [(0, 50), (100, 50)]),
        ], 200, 200)
        assert dd.DiagramValidator.count_crossings(layout_parallel) == 0

    def test_orphan_information(self):
        theme = dd.Theme(palette=dd.BrandPalette.from_seed("#bf4520"))
        spec = dd.DiagramSpec("Orphans", "flowchart",
                              nodes=[dd.DiagramNode("a", "A"), dd.DiagramNode("b", "B")],
                              edges=[dd.DiagramEdge("a", "b")])
        layout = dd.LayoutResult({"a": dd.Box(0, 0, 10, 10), "b": dd.Box(20, 0, 10, 10)},
                                 [], 100, 100)
        spec.nodes.append(dd.DiagramNode("c", "C"))
        layout.boxes["c"] = dd.Box(40, 0, 10, 10)
        report = dd.DiagramValidator(theme).validate(spec, layout)
        assert any(issue.code == "orphans" for issue in report.issues)


# ── Studio ────────────────────────────────────────────────────────────────

class TestDiagramStudio:
    def test_build_returns_artifact(self, studio):
        artifact = studio.build(_flow_spec())
        summary = artifact.summary()
        assert summary["type"] == "flowchart"
        assert summary["nodes"] == 4
        assert summary["edges"] == 4
        assert summary["self_contained"] is True
        assert summary["width"] > 0 and summary["height"] > 0
        assert artifact.width == round(artifact.layout.width, 1)

    def test_from_request_picks_type(self, studio):
        nodes = [dd.DiagramNode(p.lower(), p, "actor") for p in ("Client", "API")]
        artifact = studio.from_request(
            "sequence diagram of the client calling the api with a token refresh",
            nodes=nodes, edges=[dd.DiagramEdge("client", "api", label="GET")],
        )
        assert artifact.spec.diagram_type == "sequence"
        assert artifact.report.passed

    def test_restyle_keeps_layout_intent(self, studio):
        original = studio.build(_flow_spec())
        restyled = studio.restyle(original, "#2f6f4f")
        assert restyled.spec.title == original.spec.title
        assert restyled.theme.palette.seed != studio.theme.palette.seed
        assert restyled.report.passed
        assert len(restyled.layout.boxes) == len(original.layout.boxes)

    def test_layout_for_dispatch(self, studio):
        spec = dd.DiagramSpec("S", "sequence",
                              nodes=[dd.DiagramNode("a", "A"), dd.DiagramNode("b", "B")],
                              edges=[dd.DiagramEdge("a", "b")])
        layout = studio.layout_for(spec)
        assert isinstance(layout, dd.LayoutResult)
        assert "lifelines" in layout.extras

    def test_empty_diagram_reports_error(self, studio):
        artifact = studio.build(dd.DiagramSpec("Nothing", "flowchart"))
        assert artifact.report.passed is False
        assert any(issue.code == "structure" for issue in artifact.report.errors)


class TestDiagramDesignEngine:
    def test_catalogue(self):
        info = dd.engine.catalogue()
        assert info["types"] >= 45
        assert "process" in info["categories"]
        assert len(info["categories"]) >= 7

    def test_choose_and_palette(self):
        choice = dd.engine.choose("roadmap of quarters and releases")
        assert choice["type"] == "roadmap"
        palette = dd.engine.palette_for("#bf4520")
        assert palette["contrast_ink_paper"] > 7
        assert len(palette["tints"]) == 4
        assert len(palette["categorical"]) == 4

    def test_render_flowchart(self):
        result = dd.engine.render_flowchart("Deploy", ["Build", "Test", "Ship"])
        assert result["nodes"] == 3
        assert result["edges"] == 2
        assert result["svg"].startswith("<svg")
        assert "<html" in result["html"]
        assert result["validation"]["passed"]

    def test_render_sequence(self):
        result = dd.engine.render_sequence(
            "Handshake", ["Client", "Server"],
            [("Client", "Server", "SYN"), ("Server", "Client", "SYN-ACK")],
        )
        assert result["type"] == "sequence"
        assert result["edges"] == 2
        assert result["validation"]["passed"]
