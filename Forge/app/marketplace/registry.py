"""
Curated Template Registry and Variable Interpolation Engine for Project FORGE.
"""

from app.core.logging import get_logger
from app.marketplace.models import TemplateCategory, TemplateManifest, TemplateVariable

logger = get_logger("marketplace.registry")


class TemplateRegistry:
    """In-memory and file-backed catalog of curated templates."""

    def __init__(self):
        self._templates: dict[str, TemplateManifest] = {}
        self._load_curated_templates()

    def _load_curated_templates(self):
        """Seed the registry with production starter templates across all 4 categories."""

        # 1. Web Apps
        self.register_template(
            TemplateManifest(
                id="portfolio-web",
                name="Developer Portfolio Website",
                description="Modern, responsive personal portfolio with project showcase and contact form.",
                category=TemplateCategory.WEB_APPS,
                language="html/css/js",
                framework="vanilla",
                variables=[
                    TemplateVariable(
                        name="project_name",
                        description="Name of portfolio project",
                        default="My Portfolio",
                    ),
                    TemplateVariable(name="author", description="Author name", default="Developer"),
                    TemplateVariable(
                        name="description",
                        description="Bio summary",
                        default="Software Engineer building awesome things",
                    ),
                ],
                files={
                    "index.html": "<!DOCTYPE html>\n<html lang='en'>\n<head>\n  <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n  <title>{{project_name}}</title>\n  <link rel='stylesheet' href='style.css'>\n</head>\n<body>\n  <header><h1>{{author}}</h1><p>{{description}}</p></header>\n  <main><section id='projects'><h2>Projects</h2><p>Coming soon...</p></section></main>\n</body>\n</html>",
                    "style.css": "body { font-family: system-ui, sans-serif; margin: 0; padding: 2rem; background: #f8fafc; color: #1e293b; }\nheader { text-align: center; margin-bottom: 2rem; }",
                },
                readme_content="# {{project_name}}\n\nCreated by {{author}}.\n\n{{description}}\n",
            )
        )

        self.register_template(
            TemplateManifest(
                id="blog-web",
                name="Markdown Blog Engine",
                description="Clean static blogging platform with markdown parsing and dark mode.",
                category=TemplateCategory.WEB_APPS,
                language="javascript",
                framework="react",
                variables=[
                    TemplateVariable(
                        name="project_name", description="Blog title", default="Tech Chronicles"
                    ),
                    TemplateVariable(
                        name="description",
                        description="Blog topic",
                        default="Insights on modern software engineering",
                    ),
                ],
                files={
                    "package.json": '{"name": "blog-engine", "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1"}}',
                    "src/App.jsx": "import React from 'react';\nexport function App() { return <div><h1>{{project_name}}</h1><p>{{description}}</p></div>; }",
                },
                readme_content="# {{project_name}}\n\n{{description}}\n",
            )
        )

        self.register_template(
            TemplateManifest(
                id="ecommerce-web",
                name="E-Commerce Storefront",
                description="Next.js shopping platform with product grid, cart state, and checkout UI.",
                category=TemplateCategory.WEB_APPS,
                language="typescript",
                framework="nextjs",
                variables=[
                    TemplateVariable(
                        name="project_name", description="Store name", default="Apex Goods"
                    ),
                    TemplateVariable(
                        name="description",
                        description="Store catalog description",
                        default="Curated premium apparel and gear",
                    ),
                ],
                files={
                    "package.json": '{"name": "ecommerce-app", "dependencies": {"next": "^14.2.4", "react": "^18.3.1"}}',
                    "app/page.tsx": "export default function Page() { return <main><h1>{{project_name}}</h1><p>{{description}}</p></main>; }",
                },
                readme_content="# {{project_name}}\n\n{{description}}\n",
            )
        )

        self.register_template(
            TemplateManifest(
                id="saas-landing",
                name="SaaS Product Landing Page",
                description="High-converting SaaS landing page with hero, pricing tiers, and FAQ accordion.",
                category=TemplateCategory.WEB_APPS,
                language="typescript",
                framework="react",
                variables=[
                    TemplateVariable(
                        name="project_name", description="SaaS Product Name", default="CloudFlow"
                    ),
                    TemplateVariable(
                        name="description",
                        description="Value proposition",
                        default="Automate cloud deployments with intelligent pipelines",
                    ),
                ],
                files={
                    "src/Landing.tsx": "export const Landing = () => <div><h1>{{project_name}}</h1><p>{{description}}</p></div>;",
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="admin-dashboard",
                name="Enterprise Admin Dashboard",
                description="Metrics dashboard with data tables, chart widgets, and role-based access control.",
                category=TemplateCategory.WEB_APPS,
                language="typescript",
                framework="react",
                variables=[
                    TemplateVariable(
                        name="project_name",
                        description="Dashboard title",
                        default="Operations Control",
                    ),
                ],
                files={
                    "src/Dashboard.tsx": "export const Dashboard = () => <div><h1>{{project_name}}</h1></div>;",
                },
            )
        )

        # 2. APIs
        self.register_template(
            TemplateManifest(
                id="fastapi-crud",
                name="FastAPI CRUD Service",
                description="FastAPI REST API with Pydantic v2 schemas, SQLite/SQLAlchemy ORM, and pytest suite.",
                category=TemplateCategory.APIS,
                language="python",
                framework="fastapi",
                variables=[
                    TemplateVariable(
                        name="project_name", description="Service name", default="Item Service"
                    ),
                    TemplateVariable(
                        name="description",
                        description="API purpose",
                        default="FastAPI microservice for CRUD operations",
                    ),
                ],
                files={
                    "app/main.py": "from fastapi import FastAPI\n\napp = FastAPI(title='{{project_name}}')\n\n@app.get('/health')\ndef health():\n    return {'status': 'ok'}\n",
                    "requirements.txt": "fastapi>=0.110.0\nuvicorn>=0.28.0\npydantic>=2.6.0\npytest>=8.0.0\n",
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="auth-service",
                name="JWT Authentication Service",
                description="Secure auth service with token issuance, password hashing (bcrypt), and refresh rotation.",
                category=TemplateCategory.APIS,
                language="python",
                framework="fastapi",
                variables=[
                    TemplateVariable(
                        name="project_name", description="Auth realm name", default="Auth Hub"
                    ),
                ],
                files={
                    "app/auth.py": "from fastapi import APIRouter\nrouter = APIRouter()\n@router.post('/login')\ndef login(): return {'token': 'jwt_sample'}\n",
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="webhook-handler",
                name="Asynchronous Webhook Ingestor",
                description="High-throughput webhook receiver with HMAC signature verification and background queueing.",
                category=TemplateCategory.APIS,
                language="python",
                framework="fastapi",
                variables=[
                    TemplateVariable(
                        name="project_name", description="Webhook service", default="Event Ingestor"
                    ),
                ],
                files={
                    "app/webhook.py": "from fastapi import FastAPI, Header, HTTPException\napp = FastAPI()\n@app.post('/webhook')\ndef ingest(x_signature: str = Header(None)): return {'received': True}\n",
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="graphql-api",
                name="Strawberry GraphQL Service",
                description="Type-safe GraphQL server with Strawberry, FastAPI, and query/mutation resolvers.",
                category=TemplateCategory.APIS,
                language="python",
                framework="graphql",
                files={
                    "app/schema.py": "import strawberry\n@strawberry.type\nclass Query:\n    hello: str = 'world'\n"
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="websocket-server",
                name="Realtime WebSocket Server",
                description="WebSocket broadcast server with room subscription and heartbeat ping/pong.",
                category=TemplateCategory.APIS,
                language="python",
                framework="fastapi",
                files={
                    "app/ws.py": "from fastapi import FastAPI, WebSocket\napp = FastAPI()\n@app.websocket('/ws')\nasync def ws_endpoint(ws: WebSocket): await ws.accept()\n"
                },
            )
        )

        # 3. Tools
        self.register_template(
            TemplateManifest(
                id="cli-utility",
                name="CLI Tool with Argparse",
                description="Production command-line interface with subcommands, rich terminal formatting, and tests.",
                category=TemplateCategory.TOOLS,
                language="python",
                framework="cli",
                variables=[
                    TemplateVariable(
                        name="project_name",
                        description="CLI tool command name",
                        default="forge-cli",
                    ),
                ],
                files={
                    "cli/main.py": "import argparse\n\ndef main():\n    parser = argparse.ArgumentParser(description='{{project_name}}')\n    parser.parse_args()\n",
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="scraper",
                name="Concurrent Web Scraper",
                description="Asynchronous web scraper with BeautifulSoup, rate limiting, and JSON export.",
                category=TemplateCategory.TOOLS,
                language="python",
                framework="script",
                files={
                    "scraper/main.py": "import httpx\nfrom bs4 import BeautifulSoup\nasync def fetch(url): pass\n"
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="data-processor",
                name="Batch Data Processing Pipeline",
                description="ETL pipeline for CSV/JSON ingestion, transformation, validation, and analytics export.",
                category=TemplateCategory.TOOLS,
                language="python",
                framework="script",
                files={
                    "pipeline/process.py": "import json\ndef process_batch(items): return [i for i in items if i]\n"
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="file-converter",
                name="Universal File Converter",
                description="Format converter supporting Markdown to HTML, JSON to YAML, and CSV to Parquet.",
                category=TemplateCategory.TOOLS,
                language="python",
                framework="cli",
                files={"converter/convert.py": "def convert_format(src, dst): pass\n"},
            )
        )

        # 4. Libraries
        self.register_template(
            TemplateManifest(
                id="npm-package",
                name="Modern TypeScript NPM Library",
                description="Zero-dependency TypeScript library with Rollup bundling and Vitest tests.",
                category=TemplateCategory.LIBRARIES,
                language="typescript",
                framework="npm",
                files={
                    "package.json": '{"name": "ts-lib", "main": "dist/index.js"}',
                    "src/index.ts": "export const add = (a: number, b: number) => a + b;\n",
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="python-package",
                name="PyPI Python Library",
                description="Modern Python package structure with pyproject.toml, hatchling backend, and pytest.",
                category=TemplateCategory.LIBRARIES,
                language="python",
                framework="package",
                files={
                    "pyproject.toml": '[project]\nname = "forge-pkg"\nversion = "0.1.0"\n',
                    "src/forge_pkg/__init__.py": '"""Library package."""\n',
                },
            )
        )

        self.register_template(
            TemplateManifest(
                id="typescript-types",
                name="Shared TypeScript Schema Library",
                description="Comprehensive TypeScript type definitions with Zod schemas and validation helpers.",
                category=TemplateCategory.LIBRARIES,
                language="typescript",
                framework="types",
                files={"src/types.ts": "export interface User { id: string; email: string; }\n"},
            )
        )

    def register_template(self, manifest: TemplateManifest) -> TemplateManifest:
        """Register or update a template in the catalog."""
        self._templates[manifest.id] = manifest
        return manifest

    def get_template(self, template_id: str) -> TemplateManifest | None:
        """Fetch template by ID."""
        return self._templates.get(template_id)

    def list_templates(
        self,
        category: TemplateCategory | None = None,
        language: str | None = None,
        framework: str | None = None,
        query: str | None = None,
        sort_by: str = "rating",  # rating, downloads, name
    ) -> list[TemplateManifest]:
        """Filter and sort catalog templates."""
        results = list(self._templates.values())

        if category:
            results = [t for t in results if t.category == category]
        if language:
            results = [t for t in results if language.lower() in t.language.lower()]
        if framework:
            results = [t for t in results if framework.lower() in t.framework.lower()]
        if query:
            q = query.lower()
            results = [
                t
                for t in results
                if q in t.name.lower() or q in t.description.lower() or q in t.id.lower()
            ]

        if sort_by == "downloads":
            results.sort(key=lambda t: t.downloads, reverse=True)
        elif sort_by == "rating":
            results.sort(key=lambda t: t.rating, reverse=True)
        else:
            results.sort(key=lambda t: t.name)

        return results

    def render_template(self, template_id: str, variables: dict[str, str]) -> dict[str, str]:
        """Render all files in a template with supplied variable values."""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template with ID '{template_id}' not found.")

        # Prepare substitution dictionary with defaults
        context = {}
        for var in template.variables:
            context[var.name] = variables.get(var.name, var.default or "")

        # Always include project_name and description fallbacks
        context.setdefault("project_name", variables.get("project_name", template.name))
        context.setdefault("description", variables.get("description", template.description))
        context.setdefault("author", variables.get("author", "Project FORGE"))

        rendered_files = {}
        for rel_path, raw_content in template.files.items():
            content = raw_content
            for k, v in context.items():
                content = content.replace(f"{{{{{k}}}}}", str(v))
            rendered_files[rel_path] = content

        if template.readme_content:
            readme = template.readme_content
            for k, v in context.items():
                readme = readme.replace(f"{{{{{k}}}}}", str(v))
            rendered_files["README.md"] = readme

        # Increment download/usage count
        template.downloads += 1

        return rendered_files


template_registry = TemplateRegistry()
