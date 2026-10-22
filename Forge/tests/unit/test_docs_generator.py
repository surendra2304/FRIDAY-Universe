"""
Unit tests for Documentation Generator and Quality Assessment.
"""

from pathlib import Path

from app.delivery.docs_generator import DocumentationGenerator


def test_generate_readme_cli():
    gen = DocumentationGenerator()
    readme = gen.generate_readme(
        project_name="TodoCLI",
        goal="Build a Python CLI for todo items",
        requirements=["argparse", "JSON persistence"],
        files=["main.py", "test_main.py", "requirements.txt"],
        is_cli=True,
    )
    assert "# TodoCLI" in readme
    assert "python main.py --help" in readme
    assert "pytest -v" in readme
    assert "JSON persistence" in readme


def test_generate_readme_api():
    gen = DocumentationGenerator()
    readme = gen.generate_readme(
        project_name="ExpenseAPI",
        goal="FastAPI service for expense tracking",
        requirements=["FastAPI", "CRUD endpoints"],
        files=["main.py", "test_main.py"],
        is_api=True,
    )
    assert "# ExpenseAPI" in readme
    assert "uvicorn main:app" in readme
    assert "Swagger UI" in readme


def test_assess_doc_quality(tmp_path: Path):
    gen = DocumentationGenerator()
    proj = tmp_path / "proj"
    proj.mkdir()

    # Code with comments
    code = (
        "# Module header\n"
        "# Detailed documentation\n"
        "def compute(a, b):\n"
        "    # Add numbers together\n"
        "    return a + b\n"
    )
    (proj / "main.py").write_text(code, encoding="utf-8")

    report = gen.assess_doc_quality(proj)
    assert report.total_code_lines > 0
    assert report.total_comment_lines >= 3
    assert report.comment_ratio_percentage > 20.0
    assert report.quality_status in ["EXCELLENT", "GOOD"]
