from __future__ import annotations

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent


def _ensure_vyralx_app():
    to_remove = [k for k in list(sys.modules.keys()) if k == "app" or k.startswith("app.")]
    for k in to_remove:
        sys.modules.pop(k, None)
    vyralx_path = str(ROOT / "VyralX")
    if vyralx_path in sys.path:
        sys.path.remove(vyralx_path)
    sys.path.insert(0, vyralx_path)


def test_content_generators_produce_valid_explainer_diagram():
    _ensure_vyralx_app()
    from app.services.content import (
        generate_post,
        generate_thread,
        generate_explainer,
        generate_newsletter,
    )

    generators = [
        ("post", generate_post),
        ("thread", generate_thread),
        ("explainer", generate_explainer),
        ("newsletter", generate_newsletter),
    ]

    for name, gen in generators:
        pack = gen("Autonomous AI agents")
        assert pack is not None, f"{name} returned None"
        diag = pack.get("diagram") or pack.get("explainer_diagram")
        assert diag is not None, f"{name} pack must include a diagram"
        assert "error" not in diag, f"{name} diagram failed: {diag.get('error')}"
        assert diag.get("nodes", 0) >= 3, f"{name} diagram must have >= 3 nodes, got {diag.get('nodes')}"
        assert len(diag.get("html", "")) > 500, f"{name} diagram html must be > 500 chars, got {len(diag.get('html', ''))}"
        assert "<svg" in diag.get("html", ""), f"{name} diagram html must contain svg"
        assert diag.get("validation", {}).get("passed") is True, f"{name} validation failed"


def test_brand_palette_contrast_enforcement():
    _ensure_vyralx_app()
    from app.services.diagram_service import DiagramService

    service = DiagramService()

    # Named palette and custom hex seeds
    for seed in ["ocean", "forest", "#2563eb", "#bf4520", "#16a34a"]:
        pal = service.palette(seed)
        assert pal["contrast_ink_paper"] >= 4.5, f"Seed {seed} failed WCAG AA: {pal['contrast_ink_paper']}"
        assert len(pal["tints"]) >= 4


def test_roundtrip_mermaid_and_brief_preserves_node_and_edge_count():
    _ensure_vyralx_app()
    from app.services.diagram_service import DiagramService

    service = DiagramService()

    # 1. Mermaid roundtrip
    mermaid_src = "graph TD\n A[Step 1] --> B[Step 2]\n B --> C[Step 3]\n C --> D[Step 4]"
    m = service.from_mermaid(mermaid_src, title="Workflow")
    orig_nodes = m["nodes"]
    orig_edges = m["edges"]
    assert orig_nodes == 4
    assert orig_edges == 3

    restyled_m = service.restyle(m["diagram_id"], "forest")
    assert restyled_m["nodes"] == orig_nodes, "Restyled nodes must match original"
    assert restyled_m["edges"] == orig_edges, "Restyled edges must match original"

    # Restyle with brand dict
    restyled_m2 = service.restyle(m["diagram_id"], {"primary": "#7c3aed"})
    assert restyled_m2["nodes"] == orig_nodes
    assert restyled_m2["edges"] == orig_edges

    # 2. Brief roundtrip
    b = service.from_brief(
        "Architecture overview",
        nodes=[{"id": "c1", "label": "Client"}, {"id": "c2", "label": "Gateway"}, {"id": "c3", "label": "Worker"}],
        edges=[{"source": "c1", "target": "c2"}, {"source": "c2", "target": "c3"}],
    )
    b_nodes = b["nodes"]
    b_edges = b["edges"]
    assert b_nodes == 3
    assert b_edges == 2

    restyled_b = service.restyle(b["diagram_id"], "sunset")
    assert restyled_b["nodes"] == b_nodes
    assert restyled_b["edges"] == b_edges


def test_http_surface_endpoints():
    _ensure_vyralx_app()
    from app.services.diagram_service import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)

    # 1. /catalogue
    res = client.get("/api/v1/diagrams/catalogue")
    assert res.status_code == 200
    assert res.json()["types"] >= 46

    # 2. /render (brief)
    res = client.post("/api/v1/diagrams/render", json={
        "brief": "microservice pipeline",
        "nodes": [{"id": "n1", "label": "Service A"}, {"id": "n2", "label": "Service B"}],
        "edges": [{"source": "n1", "target": "n2"}],
    })
    assert res.status_code == 200
    data = res.json()
    assert data["nodes"] == 2
    diag_id = data["diagram_id"]

    # 3. /from-brief alias
    res = client.post("/api/v1/diagrams/from-brief", json={
        "brief": "microservice pipeline",
        "nodes": [{"id": "n1", "label": "Service A"}, {"id": "n2", "label": "Service B"}],
        "edges": [{"source": "n1", "target": "n2"}],
    })
    assert res.status_code == 200
    assert res.json()["nodes"] == 2

    # 4. /mermaid and /from-mermaid
    m_body = {"source": "graph TD\n X-->Y\n Y-->Z"}
    res = client.post("/api/v1/diagrams/mermaid", json=m_body)
    assert res.status_code == 200
    assert res.json()["nodes"] == 3

    res = client.post("/api/v1/diagrams/from-mermaid", json=m_body)
    assert res.status_code == 200
    assert res.json()["nodes"] == 3

    # 5. /restyle
    res = client.post("/api/v1/diagrams/restyle", json={
        "diagram_id": diag_id,
        "seed": "ocean",
    })
    assert res.status_code == 200
    assert res.json()["nodes"] == 2
