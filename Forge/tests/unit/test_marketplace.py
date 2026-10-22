"""
Unit and API integration tests for Template Marketplace and Smart Matcher in Project FORGE.
"""

from fastapi.testclient import TestClient

from app.agents.template_matcher import SmartTemplateMatcher
from app.analytics.templates import TemplateAnalytics
from app.main import app
from app.marketplace.models import TemplateCategory
from app.marketplace.registry import TemplateRegistry


def test_template_registry_catalog():
    registry = TemplateRegistry()

    # Verify templates in all categories
    web_templates = registry.list_templates(category=TemplateCategory.WEB_APPS)
    assert len(web_templates) >= 4

    api_templates = registry.list_templates(category=TemplateCategory.APIS)
    assert len(api_templates) >= 4

    tool_templates = registry.list_templates(category=TemplateCategory.TOOLS)
    assert len(tool_templates) >= 3

    lib_templates = registry.list_templates(category=TemplateCategory.LIBRARIES)
    assert len(lib_templates) >= 3

    # Query search
    crud = registry.list_templates(query="crud")
    assert any(t.id == "fastapi-crud" for t in crud)


def test_template_variable_rendering():
    registry = TemplateRegistry()
    files = registry.render_template(
        "portfolio-web",
        {
            "project_name": "Alice Portfolio",
            "author": "Alice Dev",
            "description": "Senior Engineer",
        },
    )
    assert "index.html" in files
    assert "Alice Portfolio" in files["index.html"]
    assert "Alice Dev" in files["index.html"]
    assert "README.md" in files
    assert "Alice Dev" in files["README.md"]


def test_template_analytics():
    analytics = TemplateAnalytics()
    analytics.record_usage("fastapi-crud", success=True, duration_seconds=10.0)
    analytics.record_usage("fastapi-crud", success=True, duration_seconds=20.0)
    analytics.record_usage(
        "fastapi-crud", success=False, duration_seconds=15.0, error_reason="Missing dependency"
    )

    stats = analytics.get_stats("fastapi-crud")
    assert stats.usage_count >= 3
    assert stats.success_rate > 50.0
    assert "Missing dependency" in stats.failure_patterns

    rec = analytics.get_recommendation("fastapi-crud", "FastAPI CRUD")
    assert "FastAPI CRUD" in rec


def test_smart_template_matcher():
    # Test blog match
    res_blog = SmartTemplateMatcher.match_goal("Build me a blog platform with markdown support")
    assert res_blog.matched_template_id == "blog-web"
    assert res_blog.confidence >= 0.80
    assert res_blog.use_hybrid_scaffold is True

    # Test API match
    res_api = SmartTemplateMatcher.match_goal("I need a REST API for users with CRUD endpoints")
    assert res_api.matched_template_id == "fastapi-crud"
    assert res_api.confidence >= 0.80

    # Test ecommerce match
    res_ecom = SmartTemplateMatcher.match_goal("Build an ecommerce store with shopping cart")
    assert res_ecom.matched_template_id == "ecommerce-web"

    # Test fallback
    res_scratch = SmartTemplateMatcher.match_goal(
        "Synthesize an esoteric quantum hypergraph compiler"
    )
    assert res_scratch.use_hybrid_scaffold is False


async def test_marketplace_api_endpoints(isolated_db_manager):
    # Building from a template writes real files via the global
    # workspace_manager singleton (app/api/marketplace.py) keyed off a fresh
    # uuid4-based task_id -- with no isolation this permanently left a
    # `workspaces/task_<hex>` directory behind in the real repo checkout on
    # every test run. isolated_db_manager (tests/conftest.py) redirects the
    # shared Settings singleton's base_dir (which workspace_manager reads)
    # into a temp directory for the duration of this test.
    client = TestClient(app)

    # 1. Browse templates
    res_list = client.get("/api/marketplace/templates")
    assert res_list.status_code == 200
    data = res_list.json()
    assert len(data) >= 10

    # 2. Template detail
    res_detail = client.get("/api/marketplace/templates/fastapi-crud")
    assert res_detail.status_code == 200
    detail_data = res_detail.json()
    assert detail_data["template"]["id"] == "fastapi-crud"
    assert "analytics" in detail_data
    assert "recommendation" in detail_data

    # 3. Build from template
    build_payload = {
        "variables": {"project_name": "My Custom Item API", "description": "Custom test service"}
    }
    res_build = client.post("/api/tasks/from-template/fastapi-crud", json=build_payload)
    assert res_build.status_code == 200
    build_data = res_build.json()
    assert build_data["template_id"] == "fastapi-crud"
    assert len(build_data["files_created"]) >= 2

    # 4. Template submission quality gate
    valid_submission = {
        "name": "Community Microservice",
        "description": "Clean microservice boilerplate",
        "category": "apis",
        "language": "python",
        "framework": "fastapi",
        "author": "OpenSourceDev",
        "files": {"app/main.py": "from fastapi import FastAPI\napp = FastAPI()\n"},
        "requirements": ["fastapi>=0.110.0"],
    }
    res_submit = client.post("/api/marketplace/templates", json=valid_submission)
    assert res_submit.status_code == 201
    assert res_submit.json()["status"] == "published"

    # 5. Template review
    review_payload = {"rating": 5.0, "review": "Excellent starter template!"}
    res_review = client.post("/api/marketplace/templates/fastapi-crud/review", json=review_payload)
    assert res_review.status_code == 200
    assert res_review.json()["success"] is True
