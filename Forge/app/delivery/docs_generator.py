"""
Automated Documentation Generator for Project FORGE Deliverables.
Generates comprehensive README.md, API endpoint specifications, and evaluates code documentation quality.
"""

from pathlib import Path

from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger("delivery.docs_generator")


class DocQualityReport(BaseModel):
    """Quality and comment coverage assessment for a codebase."""

    total_code_lines: int = 0
    total_comment_lines: int = 0
    comment_ratio_percentage: float = 0.0
    quality_status: str = "GOOD"  # EXCELLENT, GOOD, LOW_COMMENTS


class DocumentationGenerator:
    """Auto-generates production READMEs, API guides, and inspects code comments."""

    def generate_readme(
        self,
        project_name: str,
        goal: str,
        requirements: list[str] | None = None,
        files: list[str] | None = None,
        is_api: bool = False,
        is_cli: bool = False,
    ) -> str:
        """Generate a production-grade README.md for the deliverable."""
        reqs_str = "\n".join(
            f"- {r}" for r in (requirements or ["Fully functional autonomous implementation"])
        )
        files_str = "\n".join(
            f"- `{f}`" for f in (files or ["main.py", "test_main.py", "README.md"])
        )

        usage_section = ""
        if is_cli:
            usage_section = "## Usage\n\nRun the CLI tool:\n```bash\npython main.py --help\n```\n"
        elif is_api:
            usage_section = (
                "## Usage & API Endpoints\n\n"
                "Start the FastAPI backend server:\n"
                "```bash\n"
                "uvicorn main:app --reload --port 8000\n"
                "```\n\n"
                "Open interactive OpenAPI documentation:\n"
                "- Swagger UI: `http://localhost:8000/docs`\n"
                "- Redoc: `http://localhost:8000/redoc`\n"
            )
        else:
            usage_section = (
                "## Usage\n\n"
                "Open `index.html` in any modern web browser or start a local server:\n"
                "```bash\n"
                "python -m http.server 3000\n"
                "```\n"
            )

        readme = (
            f"# {project_name}\n\n"
            f"> {goal}\n\n"
            f"Autonomously synthesized and verified by **Project FORGE**.\n\n"
            f"## Requirements\n\n"
            f"{reqs_str}\n\n"
            f"## Project Structure\n\n"
            f"{files_str}\n\n"
            f"## Installation\n\n"
            f"```bash\n"
            f"# Set up virtual environment\n"
            f"python -m venv .venv\n"
            f"source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate\n\n"
            f"# Install dependencies if requirements.txt exists\n"
            f"pip install -r requirements.txt\n"
            f"```\n\n"
            f"{usage_section}\n"
            f"## Running Tests\n\n"
            f"Run the automated test suite:\n"
            f"```bash\n"
            f"pytest -v\n"
            f"```\n\n"
            f"---\n"
            f"Built with [Project FORGE](https://github.com/surendra2304/Forge).\n"
        )
        return readme

    def assess_doc_quality(self, project_dir: Path) -> DocQualityReport:
        """Inspect comment-to-code line ratios across all Python and JavaScript files."""
        total_code = 0
        total_comments = 0

        for f in project_dir.glob("**/*"):
            if f.is_file() and f.suffix in [".py", ".js"]:
                try:
                    lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
                    for line in lines:
                        s = line.strip()
                        if not s:
                            continue
                        if (
                            s.startswith("#")
                            or s.startswith("//")
                            or s.startswith("/*")
                            or s.startswith("*")
                        ):
                            total_comments += 1
                        else:
                            total_code += 1
                except Exception:
                    pass

        total_lines = total_code + total_comments
        ratio = round((total_comments / total_lines * 100.0), 1) if total_lines > 0 else 0.0

        status = "GOOD"
        if ratio >= 20.0:
            status = "EXCELLENT"
        elif ratio < 5.0 and total_code > 50:
            status = "LOW_COMMENTS"

        return DocQualityReport(
            total_code_lines=total_code,
            total_comment_lines=total_comments,
            comment_ratio_percentage=ratio,
            quality_status=status,
        )


documentation_generator = DocumentationGenerator()
