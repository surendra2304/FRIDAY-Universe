"""
Unit tests for Multi-Language and Framework Expansion in Project FORGE.
"""

from pathlib import Path

from app.agents.language_builders import (
    FullStackBuilder,
    JavaScriptBuilder,
    PythonBuilder,
    TypeScriptBuilder,
)
from app.agents.language_detector import (
    LanguageDetector,
    LanguagePromptRouter,
    TargetFramework,
    TargetLanguage,
)
from app.core.language_dependency_manager import LanguageDependencyManager
from app.verification.language_verifiers import PolyglotLanguageVerifier


def test_language_detector():
    # Python detection
    lang, framework = LanguageDetector.detect("Build a FastAPI user management service")
    assert lang == TargetLanguage.PYTHON
    assert framework == TargetFramework.FASTAPI

    # Express / Node detection
    lang, framework = LanguageDetector.detect("Build an Express.js REST API in Node.js")
    assert lang == TargetLanguage.JAVASCRIPT
    assert framework == TargetFramework.EXPRESS

    # Next.js detection
    lang, framework = LanguageDetector.detect("Build a Next.js e-commerce application")
    assert lang == TargetLanguage.TYPESCRIPT
    assert framework == TargetFramework.NEXTJS

    # React detection
    lang, framework = LanguageDetector.detect("Create a React frontend dashboard component")
    assert lang == TargetLanguage.JAVASCRIPT
    assert framework == TargetFramework.REACT

    # Fullstack detection
    lang, framework = LanguageDetector.detect(
        "Create a fullstack web app with React frontend and FastAPI backend"
    )
    assert lang == TargetLanguage.FULLSTACK


def test_language_prompt_router():
    prompt = LanguagePromptRouter.format_persona_prompt(
        TargetLanguage.TYPESCRIPT,
        TargetFramework.NEXTJS,
        "app/page.tsx",
        "Home landing page with hero banner",
    )
    assert "Typescript" in prompt
    assert "Nextjs" in prompt
    assert "app/page.tsx" in prompt


def test_python_builder(tmp_path: Path):
    builder = PythonBuilder()
    manifest = builder.file_manifest("Build a user auth service")
    assert "requirements.txt" in manifest.files_to_generate

    files = builder.scaffold_project("Build a user auth service", tmp_path)
    assert len(files) >= 5
    assert (tmp_path / "requirements.txt").exists()
    assert (tmp_path / "app" / "main.py").exists()


def test_javascript_builder(tmp_path: Path):
    builder = JavaScriptBuilder()
    manifest = builder.file_manifest("Build Express API")
    assert "package.json" in manifest.files_to_generate

    files = builder.scaffold_project("Build Express API", tmp_path)
    assert len(files) >= 5
    assert (tmp_path / "package.json").exists()
    assert (tmp_path / "src" / "server.js").exists()


def test_typescript_builder(tmp_path: Path):
    builder = TypeScriptBuilder()
    manifest = builder.file_manifest("Build Next.js app")
    assert "tsconfig.json" in manifest.files_to_generate

    files = builder.scaffold_project("Build Next.js app", tmp_path)
    assert len(files) >= 5
    assert (tmp_path / "tsconfig.json").exists()
    assert (tmp_path / "app" / "page.tsx").exists()


def test_fullstack_builder(tmp_path: Path):
    builder = FullStackBuilder()
    manifest = builder.file_manifest("Fullstack React + FastAPI application")
    assert "contracts/api_contract.json" in manifest.files_to_generate

    builder.scaffold_project("Fullstack React + FastAPI application", tmp_path)
    assert (tmp_path / "backend" / "app" / "main.py").exists()
    assert (tmp_path / "frontend" / "package.json").exists()
    assert (tmp_path / "contracts" / "api_contract.json").exists()


def test_language_dependency_manager(tmp_path: Path):
    dep_mgr = LanguageDependencyManager(tmp_path)

    # Test Python dependencies and lockfile
    req_file = tmp_path / "requirements.txt"
    req_file.write_text("fastapi>=0.110.0\nuvicorn==0.28.0\n", encoding="utf-8")
    py_res = dep_mgr.inspect_python_dependencies()
    assert py_res.is_valid
    assert "fastapi" in py_res.dependencies

    lock_file = dep_mgr.generate_lockfile("python")
    assert lock_file is not None
    assert lock_file.exists()

    # Test Node.js package.json and lockfile
    pkg_file = tmp_path / "package.json"
    pkg_file.write_text(
        '{"name": "test-pkg", "scripts": {"test": "jest"}, "dependencies": {"express": "^4.19.2"}}',
        encoding="utf-8",
    )
    node_res = dep_mgr.inspect_node_dependencies()
    assert node_res.is_valid

    npm_lock = dep_mgr.generate_lockfile("javascript")
    assert npm_lock is not None
    assert npm_lock.exists()


def test_polyglot_verifier(tmp_path: Path):
    # Setup valid JS file
    js_file = tmp_path / "server.js"
    js_file.write_text(
        "import express from 'express';\nconst app = express();\nexport default app;\n",
        encoding="utf-8",
    )

    verifier = PolyglotLanguageVerifier(tmp_path)
    res_syntax = verifier.verify_node_syntax_and_imports()
    assert res_syntax.status == "pass"

    # Invalidate syntax with unmatched braces
    bad_js = tmp_path / "broken.js"
    bad_js.write_text("function broken() { console.log('hello'); \n", encoding="utf-8")
    res_broken = verifier.verify_node_syntax_and_imports()
    assert res_broken.status == "fail"
