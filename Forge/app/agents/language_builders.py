"""
Language-Specific and Framework Builders for Project FORGE.
Implements PythonBuilder, JavaScriptBuilder, TypeScriptBuilder, and FullStackBuilder.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.templates.frameworks.express import (
    EXPRESS_ERROR_HANDLER_JS,
    EXPRESS_PACKAGE_JSON,
    EXPRESS_ROUTES_API_JS,
    EXPRESS_SERVER_JS,
    EXPRESS_TEST_JS,
)
from app.templates.frameworks.nextjs import (
    NEXTJS_API_ROUTE_TS,
    NEXTJS_LAYOUT_TSX,
    NEXTJS_PACKAGE_JSON,
    NEXTJS_PAGE_TSX,
    NEXTJS_TSCONFIG_JSON,
)
from app.templates.frameworks.react import (
    REACT_COMPONENT_CSS,
    REACT_COMPONENT_TEST_TSX,
    REACT_COMPONENT_TSX,
    REACT_PACKAGE_JSON,
)

logger = get_logger("agents.language_builders")


class BuilderManifest(BaseModel):
    files_to_generate: list[str]
    verification_checks: list[str]
    template_hints: dict[str, Any] = Field(default_factory=dict)


class BaseLanguageBuilder(ABC):
    """Abstract base class for language-specific software architecture builders."""

    @abstractmethod
    def file_manifest(self, goal: str) -> BuilderManifest:
        pass

    @abstractmethod
    def scaffold_project(self, goal: str, workspace_path: Path) -> list[Path]:
        pass


class PythonBuilder(BaseLanguageBuilder):
    """Builder for Python projects (FastAPI, Flask, CLI, Scripts)."""

    def file_manifest(self, goal: str) -> BuilderManifest:
        return BuilderManifest(
            files_to_generate=[
                "app/__init__.py",
                "app/main.py",
                "app/routes.py",
                "app/models.py",
                "requirements.txt",
                "tests/__init__.py",
                "tests/test_main.py",
                "README.md",
            ],
            verification_checks=["python_ast", "pytest", "ruff_lint", "security_scan"],
            template_hints={"framework": "FastAPI", "test_runner": "pytest"},
        )

    def scaffold_project(self, goal: str, workspace_path: Path) -> list[Path]:
        workspace_path.mkdir(parents=True, exist_ok=True)
        created_files = []

        files = {
            "requirements.txt": "fastapi>=0.110.0\nuvicorn>=0.28.0\npydantic>=2.6.0\npytest>=8.0.0\nhttpx>=0.27.0\n",
            "app/__init__.py": '"""Application package."""\n',
            "app/models.py": "from pydantic import BaseModel\n\nclass Item(BaseModel):\n    id: int\n    name: str\n",
            "app/routes.py": "from fastapi import APIRouter\nfrom app.models import Item\n\nrouter = APIRouter()\n\n@router.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
            "app/main.py": "from fastapi import FastAPI\nfrom app.routes import router\n\napp = FastAPI(title='FORGE Generated API')\napp.include_router(router, prefix='/api')\n",
            "tests/__init__.py": "",
            "tests/test_main.py": "from fastapi.testclient import TestClient\nfrom app.main import app\n\nclient = TestClient(app)\n\ndef test_health():\n    res = client.get('/api/health')\n    assert res.status_code == 200\n    assert res.json()['status'] == 'ok'\n",
            "README.md": f"# {goal}\n\nGenerated autonomously by Project FORGE.\n\n## Usage\n```bash\npip install -r requirements.txt\nuvicorn app.main:app --reload\n```\n",
        }

        for rel_path, content in files.items():
            p = workspace_path / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            created_files.append(p)

        return created_files


class JavaScriptBuilder(BaseLanguageBuilder):
    """Builder for Node.js, Express.js, and Vanilla/Vue JavaScript projects."""

    def file_manifest(self, goal: str) -> BuilderManifest:
        return BuilderManifest(
            files_to_generate=[
                "package.json",
                "src/server.js",
                "src/routes/api.js",
                "src/middleware/errorHandler.js",
                "tests/api.test.js",
                ".env.example",
                "README.md",
            ],
            verification_checks=["node_syntax", "jest_tests", "npm_package_integrity"],
            template_hints={"framework": "Express.js", "runtime": "Node.js 18+"},
        )

    def scaffold_project(self, goal: str, workspace_path: Path) -> list[Path]:
        workspace_path.mkdir(parents=True, exist_ok=True)
        created_files = []

        files = {
            "package.json": EXPRESS_PACKAGE_JSON.replace(
                "{{app_name}}", "forge-express-app"
            ).replace("{{description}}", goal),
            "src/server.js": EXPRESS_SERVER_JS,
            "src/routes/api.js": EXPRESS_ROUTES_API_JS,
            "src/middleware/errorHandler.js": EXPRESS_ERROR_HANDLER_JS,
            "tests/api.test.js": EXPRESS_TEST_JS,
            ".env.example": "PORT=3000\nNODE_ENV=development\n",
            "README.md": f"# {goal}\n\nGenerated autonomously by Project FORGE.\n\n## Usage\n```bash\nnpm install\nnpm start\n```\n",
        }

        for rel_path, content in files.items():
            p = workspace_path / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            created_files.append(p)

        return created_files


class TypeScriptBuilder(BaseLanguageBuilder):
    """Builder for Next.js, React TypeScript, and strict TypeScript backend services."""

    def file_manifest(self, goal: str) -> BuilderManifest:
        return BuilderManifest(
            files_to_generate=[
                "package.json",
                "tsconfig.json",
                "app/layout.tsx",
                "app/page.tsx",
                "app/globals.css",
                "app/api/health/route.ts",
                "README.md",
            ],
            verification_checks=["typescript_tsc", "next_build", "react_testing"],
            template_hints={"framework": "Next.js App Router", "type_safety": "strict"},
        )

    def scaffold_project(self, goal: str, workspace_path: Path) -> list[Path]:
        workspace_path.mkdir(parents=True, exist_ok=True)
        created_files = []

        files = {
            "package.json": NEXTJS_PACKAGE_JSON.replace("{{app_name}}", "forge-nextjs-app"),
            "tsconfig.json": NEXTJS_TSCONFIG_JSON,
            "app/layout.tsx": NEXTJS_LAYOUT_TSX.replace("{{app_title}}", "FORGE Next App").replace(
                "{{description}}", goal
            ),
            "app/page.tsx": NEXTJS_PAGE_TSX.replace("{{app_title}}", "FORGE Next App").replace(
                "{{description}}", goal
            ),
            "app/globals.css": "body { margin: 0; font-family: sans-serif; }\n",
            "app/api/health/route.ts": NEXTJS_API_ROUTE_TS.replace("{{app_name}}", "forge-app"),
            "README.md": f"# {goal}\n\nGenerated autonomously by Project FORGE.\n\n## Usage\n```bash\nnpm install\nnpm run dev\n```\n",
        }

        for rel_path, content in files.items():
            p = workspace_path / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            created_files.append(p)

        return created_files


class FullStackBuilder(BaseLanguageBuilder):
    """Builder for composite full-stack architectures (React/Next frontend + FastAPI/Express backend)."""

    def file_manifest(self, goal: str) -> BuilderManifest:
        return BuilderManifest(
            files_to_generate=[
                "frontend/package.json",
                "frontend/src/App.tsx",
                "backend/requirements.txt",
                "backend/app/main.py",
                "contracts/api_contract.json",
                "README.md",
            ],
            verification_checks=[
                "dual_engine_verification",
                "contract_integrity",
                "browser_integration",
            ],
            template_hints={"frontend": "React", "backend": "FastAPI", "contract": "OpenAPI/JSON"},
        )

    def scaffold_project(self, goal: str, workspace_path: Path) -> list[Path]:
        workspace_path.mkdir(parents=True, exist_ok=True)
        created_files = []

        # Backend (FastAPI)
        py_builder = PythonBuilder()
        created_files.extend(py_builder.scaffold_project(goal, workspace_path / "backend"))

        # Frontend (React Component / App)
        frontend_dir = workspace_path / "frontend"
        frontend_dir.mkdir(parents=True, exist_ok=True)

        contract_json = '{\n  "version": "1.0.0",\n  "endpoints": [\n    {"path": "/api/items", "method": "GET", "response": "Item[]"}\n  ]\n}\n'
        contract_path = workspace_path / "contracts" / "api_contract.json"
        contract_path.parent.mkdir(parents=True, exist_ok=True)
        contract_path.write_text(contract_json, encoding="utf-8")
        created_files.append(contract_path)

        react_files = {
            "package.json": REACT_PACKAGE_JSON.replace("{{app_name}}", "forge-frontend"),
            "src/Counter.tsx": REACT_COMPONENT_TSX.replace("{{component_name}}", "Counter").replace(
                "{{component_name_lower}}", "counter"
            ),
            "src/Counter.css": REACT_COMPONENT_CSS.replace("{{component_name_lower}}", "counter"),
            "src/Counter.test.tsx": REACT_COMPONENT_TEST_TSX.replace(
                "{{component_name}}", "Counter"
            ),
        }

        for rel_path, content in react_files.items():
            p = frontend_dir / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            created_files.append(p)

        return created_files


class Web3DBuilder(BaseLanguageBuilder):
    """Builder for futuristic, 3D interactive, glassmorphic websites and web apps (Lovable / Bolt standard)."""

    def file_manifest(self, goal: str) -> BuilderManifest:
        return BuilderManifest(
            files_to_generate=[
                "index.html",
                "style.css",
                "app.js",
                "README.md",
            ],
            verification_checks=[
                "browser_verification",
                "webgl_canvas_check",
                "aesthetic_verification",
                "accessibility",
            ],
            template_hints={
                "engine": "ForgeWebStudio",
                "render_standard": "Three.js / 3D Canvas / Bento Glassmorphism",
                "placeholders": "strictly_forbidden",
            },
        )

    def scaffold_project(self, goal: str, workspace_path: Path) -> list[Path]:
        workspace_path.mkdir(parents=True, exist_ok=True)
        from app.templates.web_studio.generator import ForgeWebStudio

        studio_files = ForgeWebStudio.synthesize_website(goal)
        created_files = []
        for rel_path, content in studio_files.items():
            p = workspace_path / rel_path
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            created_files.append(p)
        return created_files
