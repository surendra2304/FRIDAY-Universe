"""
Project Type Specialization for Project FORGE.
Provides specialized project builders with targeted file manifests, verification requirements,
template hints, and starter scaffolds for common engineering archetypes.
"""

from abc import ABC, abstractmethod
from enum import Enum

from app.templates.catalog import (
    FASTAPI_APP_BASE,
    FASTAPI_TEST_BASE,
    PYTHON_CLI_BASE,
    PYTHON_CLI_TEST_BASE,
)
from app.templates.engine import TemplateEngine


class ProjectCategory(str, Enum):
    WEBSITE = "website"
    CLI = "cli"
    API = "api"
    SCRIPT = "script"
    FULLSTACK = "fullstack"


class BaseProjectBuilder(ABC):
    """Abstract base class for specialized project builders."""

    category: ProjectCategory

    def __init__(self, goal: str, requirements: list[str] | None = None):
        self.goal = goal
        self.requirements = requirements or []

    @abstractmethod
    def file_manifest(self) -> list[str]:
        """Return list of project files required for this architecture."""
        ...

    @abstractmethod
    def verification_requirements(self) -> list[str]:
        """Return categories of verification checks required (e.g. ['build', 'lint', 'test', 'browser'])."""
        ...

    @abstractmethod
    def template_hints(self) -> str:
        """Return guidance and instructions for AI agents synthesizing this project type."""
        ...

    @abstractmethod
    def synthesize_starter_files(self) -> dict[str, str]:
        """Generate deterministic starter code mapping relative filepath to file content."""
        ...


class WebsiteBuilder(BaseProjectBuilder):
    """Specialized builder for responsive static websites, landing pages, and dashboards."""

    category = ProjectCategory.WEBSITE

    def file_manifest(self) -> list[str]:
        return ["index.html", "style.css", "app.js", "README.md"]

    def verification_requirements(self) -> list[str]:
        return ["build", "lint", "runtime", "feature", "browser", "accessibility"]

    def template_hints(self) -> str:
        return (
            "Build a responsive, modern HTML5 website with semantic markup, mobile-friendly CSS flexbox/grid, "
            "dark mode toggle with localStorage persistence, accessible ARIA attributes, and interactive JavaScript."
        )

    def synthesize_starter_files(self) -> dict[str, str]:
        from app.templates.web_studio.generator import ForgeWebStudio

        return ForgeWebStudio.synthesize_website(self.goal, self.requirements)


class CLIBuilder(BaseProjectBuilder):
    """Specialized builder for command-line tools and utilities."""

    category = ProjectCategory.CLI

    def file_manifest(self) -> list[str]:
        return ["main.py", "test_main.py", "README.md", "requirements.txt"]

    def verification_requirements(self) -> list[str]:
        return ["build", "lint", "test", "runtime", "feature", "security"]

    def template_hints(self) -> str:
        return (
            "Build a robust Python CLI utility with argparse, --help, --version, clean exit codes, "
            "JSON file persistence, structured error handling, and comprehensive pytest unit tests."
        )

    def synthesize_starter_files(self) -> dict[str, str]:
        cli_name = "tool"
        words = [w for w in self.goal.split() if w.isalnum()]
        if words:
            cli_name = words[0].lower()

        ctx = {
            "cli_name": cli_name,
            "cli_description": self.goal,
        }
        return {
            "main.py": TemplateEngine.render(PYTHON_CLI_BASE, ctx),
            "test_main.py": TemplateEngine.render(PYTHON_CLI_TEST_BASE, ctx),
            "requirements.txt": "pytest>=7.4.0\n",
            "README.md": f"# {cli_name}\n\n{self.goal}\n\n## Usage\n```bash\npython main.py --help\n```\n",
        }


class APIBuilder(BaseProjectBuilder):
    """Specialized builder for FastAPI / REST backend services."""

    category = ProjectCategory.API

    def file_manifest(self) -> list[str]:
        return ["main.py", "test_main.py", "requirements.txt", "README.md"]

    def verification_requirements(self) -> list[str]:
        return ["build", "lint", "test", "runtime", "feature", "security"]

    def template_hints(self) -> str:
        return (
            "Build a resilient FastAPI service with Pydantic request/response models, /health endpoint, "
            "CRUD endpoints with HTTP status codes, structured error handling, and FastAPI TestClient tests."
        )

    def synthesize_starter_files(self) -> dict[str, str]:
        ctx = {
            "api_name": "forge_service",
            "api_title": self.goal,
            "api_description": f"Autonomously generated FastAPI service for {self.goal}.",
        }
        return {
            "main.py": TemplateEngine.render(FASTAPI_APP_BASE, ctx),
            "test_main.py": TemplateEngine.render(FASTAPI_TEST_BASE, ctx),
            "requirements.txt": "fastapi>=0.100.0\nuvicorn>=0.22.0\npydantic>=2.0\npytest>=7.4.0\nhttpx>=0.24.0\n",
            "README.md": f"# {self.goal}\n\nFastAPI REST service with automated OpenAPI documentation and test suite.\n",
        }


class ScriptBuilder(BaseProjectBuilder):
    """Specialized builder for single-purpose Python automation scripts."""

    category = ProjectCategory.SCRIPT

    def file_manifest(self) -> list[str]:
        return ["main.py", "test_main.py", "README.md"]

    def verification_requirements(self) -> list[str]:
        return ["build", "lint", "test", "runtime", "security"]

    def template_hints(self) -> str:
        return (
            "Build a clean Python script with logging, argparse argument handling, modular functions, "
            "defensive error handling, and pytest verification."
        )

    def synthesize_starter_files(self) -> dict[str, str]:
        script_code = (
            '"""\n'
            f"{self.goal}\n"
            "Generated by Project FORGE.\n"
            '"""\n\n'
            "import argparse\n"
            "import logging\n"
            "import sys\n\n"
            'logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")\n'
            'logger = logging.getLogger("script")\n\n\n'
            "def run_process(verbose: bool = False) -> int:\n"
            f'    logger.info("Executing task: {self.goal}")\n'
            "    if verbose:\n"
            '        logger.debug("Verbose diagnostics enabled.")\n'
            "    return 0\n\n\n"
            "def main() -> int:\n"
            '    parser = argparse.ArgumentParser(description="'
            + self.goal.replace('"', '\\"')
            + '")\n'
            '    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")\n'
            "    args = parser.parse_args()\n"
            "    return run_process(verbose=args.verbose)\n\n\n"
            'if __name__ == "__main__":\n'
            "    sys.exit(main())\n"
        )
        test_code = (
            '"""\n'
            f"Unit tests for {self.goal}.\n"
            '"""\n\n'
            "from main import run_process\n\n\n"
            "def test_run_process():\n"
            "    assert run_process() == 0\n"
        )
        return {
            "main.py": script_code,
            "test_main.py": test_code,
            "README.md": f"# {self.goal}\n\nStandalone automation script.\n",
        }


def detect_project_type(goal: str, requirements: list[str] | None = None) -> BaseProjectBuilder:
    """Classify the user goal and requirements into a specialized Project Builder."""
    combined = (goal + " " + " ".join(requirements or [])).lower()

    if any(
        k in combined
        for k in [
            "website",
            "landing page",
            "web page",
            "html",
            "portfolio",
            "css",
            "dark mode",
            "frontend",
            "dashboard",
        ]
    ):
        return WebsiteBuilder(goal, requirements)
    elif any(
        k in combined
        for k in [
            "fastapi",
            "rest api",
            "backend",
            "database",
            "sqlite",
            "service",
            "endpoint",
            "crud",
        ]
    ):
        return APIBuilder(goal, requirements)
    elif any(k in combined for k in ["cli", "command-line", "terminal tool", "todo", "argparse"]):
        return CLIBuilder(goal, requirements)
    else:
        return ScriptBuilder(goal, requirements)
