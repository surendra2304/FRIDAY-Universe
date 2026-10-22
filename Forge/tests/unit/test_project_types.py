"""
Unit tests for Project Type Specialization and Template Scaffolds.
"""

from app.agents.project_types import (
    APIBuilder,
    CLIBuilder,
    ProjectCategory,
    ScriptBuilder,
    WebsiteBuilder,
    detect_project_type,
)
from app.templates.engine import TemplateEngine


def test_detect_project_types():
    web = detect_project_type("Build a portfolio website with dark mode")
    assert isinstance(web, WebsiteBuilder)
    assert web.category == ProjectCategory.WEBSITE

    api = detect_project_type("Create a FastAPI REST service with SQLite database")
    assert isinstance(api, APIBuilder)
    assert api.category == ProjectCategory.API

    cli = detect_project_type("Create a Python CLI todo tool")
    assert isinstance(cli, CLIBuilder)
    assert cli.category == ProjectCategory.CLI

    script = detect_project_type("Clean up log files daily")
    assert isinstance(script, ScriptBuilder)
    assert script.category == ProjectCategory.SCRIPT


def test_website_builder_manifest_and_templates():
    builder = WebsiteBuilder("Personal Portfolio")
    manifest = builder.file_manifest()
    assert "index.html" in manifest
    assert "style.css" in manifest
    assert "app.js" in manifest

    checks = builder.verification_requirements()
    assert "browser" in checks
    assert "accessibility" in checks

    files = builder.synthesize_starter_files()
    assert "index.html" in files
    assert "<!DOCTYPE html>" in files["index.html"]
    assert "style.css" in files
    assert "app.js" in files


def test_cli_builder_manifest_and_templates():
    builder = CLIBuilder("Todo CLI Tool")
    manifest = builder.file_manifest()
    assert "main.py" in manifest
    assert "test_main.py" in manifest

    files = builder.synthesize_starter_files()
    assert "main.py" in files
    assert "argparse" in files["main.py"]
    assert "test_main.py" in files
    assert "pytest" in files["test_main.py"]


def test_api_builder_manifest_and_templates():
    builder = APIBuilder("Expense Tracker REST API")
    manifest = builder.file_manifest()
    assert "main.py" in manifest
    assert "test_main.py" in manifest

    files = builder.synthesize_starter_files()
    assert "FastAPI" in files["main.py"]
    assert "/health" in files["main.py"]
    assert "TestClient" in files["test_main.py"]


def test_template_engine_interpolation():
    template = "Hello {{name}}, welcome to {{project}}!"
    rendered = TemplateEngine.render(template, {"name": "FRIDAY", "project": "FORGE"})
    assert rendered == "Hello FRIDAY, welcome to FORGE!"

    partial = TemplateEngine.render("Missing {{key}} test", {})
    assert "Missing {{ key }} test" in partial
