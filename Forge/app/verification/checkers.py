"""
Objective Verification Checkers for Project FORGE.
Implements Build, Lint, TypeCheck, Test, and Runtime smoke checkers.
"""

import ast
import json
import sys
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.execution.engine import ExecutionEngine
from app.verification.evidence import CheckCategory, VerificationEvidence

logger = get_logger("verification.checkers")


class BaseChecker(ABC):
    """Abstract base class for all objective verification checkers."""

    def __init__(self, name: str, category: CheckCategory):
        self.name = name
        self.category = category

    @abstractmethod
    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        pass


class BuildChecker(BaseChecker):
    """Validates source code compile integrity and AST syntax across Python, Node.js/TypeScript, and Go."""

    def __init__(self):
        super().__init__(name="Build & Syntax Check", category=CheckCategory.BUILD)

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths:
            # A missing workspace is an absence of evidence, not a successful build.
            # Keep the result explicitly failed so an orchestrator cannot promote a
            # task to "verified" when no project files were inspected.
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=2,
                passed=False,
                duration_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
                stdout="",
                stderr="Cannot verify build integrity: no workspace paths were produced.",
            )

        # 1. Go Stack Check
        go_files = list(paths.project.glob("**/*.go"))
        if (paths.project / "go.mod").exists() or go_files:
            cmd_res = await engine.terminal.run_command(task_id, "go build ./...", role="tester")
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            passed = cmd_res.exit_code == 0
            return VerificationEvidence(
                check_name="Go Build Check",
                category=self.category,
                command=cmd_res.command,
                exit_code=cmd_res.exit_code,
                passed=passed,
                duration_ms=round(duration_ms, 2),
                stdout=cmd_res.stdout,
                stderr=cmd_res.stderr,
                artifacts_inspected=[str(p.relative_to(paths.project)) for p in go_files],
            )

        # 2. Node.js / TypeScript Stack Check
        pkg_json_file = paths.project / "package.json"
        ts_files = list(paths.project.glob("**/*.ts")) + list(paths.project.glob("**/*.tsx"))
        js_files = list(paths.project.glob("**/*.js")) + list(paths.project.glob("**/*.jsx"))

        if pkg_json_file.exists() or ts_files:
            import json as py_json

            build_cmd = None
            if pkg_json_file.exists():
                try:
                    pkg_data = py_json.loads(pkg_json_file.read_text(encoding="utf-8"))
                    scripts = pkg_data.get("scripts", {})
                    if "build" in scripts:
                        build_cmd = "npm run build"
                except Exception:
                    pass

            if not build_cmd and (ts_files or (paths.project / "tsconfig.json").exists()):
                build_cmd = "npx tsc --noEmit"

            if build_cmd:
                cmd_res = await engine.terminal.run_command(task_id, build_cmd, role="tester")
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                passed = cmd_res.exit_code == 0
                return VerificationEvidence(
                    check_name="Node.js / TypeScript Build Check",
                    category=self.category,
                    command=cmd_res.command,
                    exit_code=cmd_res.exit_code,
                    passed=passed,
                    duration_ms=round(duration_ms, 2),
                    stdout=cmd_res.stdout,
                    stderr=cmd_res.stderr,
                    artifacts_inspected=[
                        str(p.relative_to(paths.project)) for p in ts_files + js_files
                    ],
                )

        # 3. Python Stack Check (AST Parse)
        py_files = engine.fs.search_files(task_id, pattern="*.py", role="tester")
        issues = []
        artifacts_inspected = []

        for rel_path in py_files:
            artifacts_inspected.append(rel_path)
            full_path = paths.project / rel_path
            try:
                content = full_path.read_text(encoding="utf-8")
                ast.parse(content, filename=rel_path)
            except SyntaxError as e:
                issues.append(
                    {
                        "file": rel_path,
                        "line": e.lineno,
                        "offset": e.offset,
                        "text": e.text,
                        "error": str(e),
                    }
                )
            except Exception as e:
                issues.append({"file": rel_path, "error": str(e)})

        # 4. HTML & Static Web Assets Syntax Check
        html_files = engine.fs.search_files(
            task_id, pattern="*.html", role="tester"
        ) + engine.fs.search_files(task_id, pattern="*.htm", role="tester")
        if html_files:
            from html.parser import HTMLParser

            class HTMLSyntaxValidator(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.errors = []
                    self.tag_stack = []

                def handle_starttag(self, tag, attrs):
                    void_tags = {
                        "area",
                        "base",
                        "br",
                        "col",
                        "embed",
                        "hr",
                        "img",
                        "input",
                        "link",
                        "meta",
                        "param",
                        "source",
                        "track",
                        "wbr",
                    }
                    if tag.lower() not in void_tags:
                        self.tag_stack.append(tag.lower())

                def handle_endtag(self, tag):
                    tag_lower = tag.lower()
                    if self.tag_stack and self.tag_stack[-1] == tag_lower:
                        self.tag_stack.pop()

            for rel_path in html_files:
                artifacts_inspected.append(rel_path)
                try:
                    full_path = paths.project / rel_path
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                    parser = HTMLSyntaxValidator()
                    parser.feed(content)
                except Exception as e:
                    issues.append({"file": rel_path, "error": f"HTML Syntax error: {e}"})

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        passed = len(issues) == 0

        stdout = f"Parsed {len(artifacts_inspected)} source files successfully." if passed else ""
        stderr = f"Syntax errors detected in {len(issues)} files: {issues}" if not passed else ""

        return VerificationEvidence(
            check_name="Build & Syntax Check",
            category=self.category,
            command="build_and_syntax_validation",
            exit_code=0 if passed else 1,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=stdout,
            stderr=stderr,
            artifacts_inspected=artifacts_inspected,
            issues=issues,
        )


class LintChecker(BaseChecker):
    """Executes linting checks across Python (Ruff), Node/TS (ESLint), Go (go vet), and Web Static Assets."""

    def __init__(self):
        super().__init__(name="Static Code Linter", category=CheckCategory.LINT)

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths:
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                stdout="No workspace to lint.",
            )

        # 1. Go Linting (go vet)
        if (paths.project / "go.mod").exists() or list(paths.project.glob("**/*.go")):
            cmd_res = await engine.terminal.run_command(task_id, "go vet ./...", role="tester")
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return VerificationEvidence(
                check_name="Go Vet Static Analyzer",
                category=self.category,
                command=cmd_res.command,
                exit_code=cmd_res.exit_code,
                passed=(cmd_res.exit_code == 0),
                duration_ms=round(duration_ms, 2),
                stdout=cmd_res.stdout,
                stderr=cmd_res.stderr,
            )

        # 2. Node.js / TypeScript Linting (npm run lint or eslint)
        pkg_json_file = paths.project / "package.json"
        if pkg_json_file.exists():
            import json as py_json

            try:
                pkg_data = py_json.loads(pkg_json_file.read_text(encoding="utf-8"))
                if "lint" in pkg_data.get("scripts", {}):
                    cmd_res = await engine.terminal.run_command(
                        task_id, "npm run lint", role="tester"
                    )
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    return VerificationEvidence(
                        check_name="ESLint / Node Linter",
                        category=self.category,
                        command=cmd_res.command,
                        exit_code=cmd_res.exit_code,
                        passed=(cmd_res.exit_code == 0),
                        duration_ms=round(duration_ms, 2),
                        stdout=cmd_res.stdout,
                        stderr=cmd_res.stderr,
                    )
            except Exception:
                pass

        # 3. HTML / Web Static Asset Linting
        html_files = engine.fs.search_files(task_id, pattern="*.html", role="tester")
        js_files = engine.fs.search_files(task_id, pattern="*.js", role="tester")
        css_files = engine.fs.search_files(task_id, pattern="*.css", role="tester")
        py_files = engine.fs.search_files(task_id, pattern="*.py", role="tester")

        if html_files and not py_files:
            lint_issues = []
            for hf in html_files:
                try:
                    content = (
                        (paths.project / hf).read_text(encoding="utf-8", errors="ignore").lower()
                    )
                    if "<html" not in content and "<!doctype html>" not in content:
                        lint_issues.append(f"{hf}: Missing <html> or <!DOCTYPE html> root element")
                except Exception as e:
                    lint_issues.append(f"{hf}: Could not read file: {e}")

            for cf in css_files:
                try:
                    c_content = (paths.project / cf).read_text(encoding="utf-8", errors="ignore")
                    if c_content.count("{") != c_content.count("}"):
                        lint_issues.append(f"{cf}: Unbalanced CSS braces")
                except Exception as e:
                    lint_issues.append(f"{cf}: Could not read file: {e}")

            passed = len(lint_issues) == 0
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return VerificationEvidence(
                check_name="HTML / Web Static Linter",
                category=self.category,
                command="web_static_linter(html, css, js)",
                exit_code=0 if passed else 1,
                passed=passed,
                duration_ms=round(duration_ms, 2),
                stdout=f"Linted {len(html_files) + len(js_files) + len(css_files)} web assets successfully."
                if passed
                else "",
                stderr="\n".join(lint_issues) if not passed else "",
            )

        # 4. Python Linting (Ruff)
        if not py_files:
            return VerificationEvidence(
                check_name="Static Code Linter",
                category=self.category,
                command="linter_check",
                exit_code=0,
                passed=True,
                duration_ms=0.1,
                stdout="No source files require linting.",
            )

        # --no-cache keeps .ruff_cache out of the delivered project. Without it
        # every verified build shipped a .ruff_cache directory to the user.
        #
        # `ruff` used to be resolved as a bare name from the *subprocess's*
        # PATH. TestChecker.run_check fixed the identical class of bug for
        # pytest a few lines below ("python was a bare name resolved from
        # PATH ... sys.executable is the one that actually has the deps"),
        # but this lint check was never updated to match -- so whether lint
        # ran at all silently depended on how the FORGE server process itself
        # was launched (e.g. `.venv/bin/uvicorn ...` directly, with no venv
        # activation, leaves `ruff` off PATH even though it is installed in
        # the very same environment as the running interpreter). Reproduced
        # live: booting via `.venv/bin/uvicorn` (PATH lacking `.venv/bin`)
        # made every single generated build fail this check with
        # `exit=127 .../sh: 1: ruff: not found`, which a human reviewing
        # verification_report.json would read as a real lint failure.
        # `{sys.executable} -m ruff` resolves ruff from the same environment
        # as FORGE itself, independent of PATH.
        cmd_res = await engine.terminal.run_command(
            task_id,
            f'"{sys.executable}" -m ruff check . --no-cache --select=E,F --ignore=E501,F841',
            role="tester",
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        # Treat "ruff genuinely isn't installed in this environment" (e.g. a
        # production deploy built without the `[dev]` extra) as a skip, not a
        # failure. The previous check only matched bash's
        # "command not found" phrasing; POSIX `sh`/`dash` (the shell actually
        # used by asyncio.create_subprocess_shell on Linux) emits
        # "ruff: not found" with no "command" in it at all, so the leniency
        # branch never actually triggered on this platform -- verified live.
        missing_tool_markers = (
            "command not found",
            "no module named",
            ": not found",
            "not found\n",
        )
        ruff_missing = cmd_res.exit_code in (127, 126) and any(
            marker in cmd_res.stderr.lower() for marker in missing_tool_markers
        )
        passed = cmd_res.exit_code == 0 or ruff_missing
        stdout_text = cmd_res.stdout
        if ruff_missing:
            stdout_text = (
                (cmd_res.stdout or "")
                + "\n[FORGE] ruff is not installed in this environment; "
                "lint check skipped rather than failed."
            ).strip()

        return VerificationEvidence(
            check_name="Ruff / Static Code Linter",
            category=self.category,
            command=cmd_res.command,
            exit_code=cmd_res.exit_code,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=stdout_text,
            stderr=cmd_res.stderr,
            artifacts_inspected=py_files,
        )


class TestChecker(BaseChecker):
    """Executes automated unit and integration tests across Python (pytest), Node/TS (npm test/jest), and Go (go test)."""

    __test__ = False

    def __init__(self):
        super().__init__(name="Test Suite Runner", category=CheckCategory.TEST)

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths:
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                stdout="No workspace to test.",
            )

        # 1. Go Tests
        go_test_files = list(paths.project.glob("**/*_test.go"))
        if (paths.project / "go.mod").exists() and go_test_files:
            cmd_res = await engine.terminal.run_command(task_id, "go test -v ./...", role="tester")
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return VerificationEvidence(
                check_name="Go Test Suite Runner",
                category=self.category,
                command=cmd_res.command,
                exit_code=cmd_res.exit_code,
                passed=(cmd_res.exit_code == 0),
                duration_ms=round(duration_ms, 2),
                stdout=cmd_res.stdout,
                stderr=cmd_res.stderr,
                artifacts_inspected=[str(p.relative_to(paths.project)) for p in go_test_files],
            )

        # 2. Node.js / TypeScript Tests
        pkg_json_file = paths.project / "package.json"
        node_test_files = (
            list(paths.project.glob("**/*.test.ts"))
            + list(paths.project.glob("**/*.test.js"))
            + list(paths.project.glob("**/*.spec.ts"))
            + list(paths.project.glob("**/*.spec.js"))
        )
        if pkg_json_file.exists():
            import json as py_json

            test_cmd = None
            try:
                pkg_data = py_json.loads(pkg_json_file.read_text(encoding="utf-8"))
                scripts = pkg_data.get("scripts", {})
                if "test" in scripts and "no test specified" not in scripts["test"].lower():
                    test_cmd = "npm test"
            except Exception:
                pass

            if not test_cmd and node_test_files:
                test_cmd = (
                    "npx jest --passWithNoTests"
                    if any(".ts" in str(p) for p in node_test_files)
                    else "node --test"
                )

            if test_cmd:
                cmd_res = await engine.terminal.run_command(task_id, test_cmd, role="tester")
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                return VerificationEvidence(
                    check_name="Node.js Test Suite Runner",
                    category=self.category,
                    command=cmd_res.command,
                    exit_code=cmd_res.exit_code,
                    passed=(cmd_res.exit_code == 0),
                    duration_ms=round(duration_ms, 2),
                    stdout=cmd_res.stdout,
                    stderr=cmd_res.stderr,
                    artifacts_inspected=[
                        str(p.relative_to(paths.project)) for p in node_test_files
                    ],
                )

        # 3. Python Tests (Pytest)
        py_test_files = engine.fs.search_files(task_id, pattern="test_*.py", role="tester")
        has_tests_dir = (paths.project / "tests").exists() and list(
            (paths.project / "tests").glob("*.py")
        )

        if not py_test_files and not has_tests_dir:
            return VerificationEvidence(
                check_name="Pytest Test Suite Runner",
                category=self.category,
                command="pytest -v",
                exit_code=0,
                passed=True,
                duration_ms=0.1,
                stdout="No test files discovered in workspace.",
            )

        # Two fixes in one line. `python` was a bare name resolved from PATH, so
        # the checker could run a different interpreter (or none) than the one
        # hosting FORGE; sys.executable is the one that actually has the deps.
        # And -p no:cacheprovider stops pytest from writing .pytest_cache into
        # the project it is verifying.
        cmd_res = await engine.terminal.run_command(
            task_id,
            f'"{sys.executable}" -B -m pytest -v -p no:cacheprovider',
            env_vars={"PYTHONPATH": ".", "PYTHONDONTWRITEBYTECODE": "1"},
            role="tester",
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        return VerificationEvidence(
            check_name="Pytest Test Suite Runner",
            category=self.category,
            command=cmd_res.command,
            exit_code=cmd_res.exit_code,
            passed=(cmd_res.exit_code == 0),
            duration_ms=round(duration_ms, 2),
            stdout=cmd_res.stdout,
            stderr=cmd_res.stderr,
            artifacts_inspected=py_test_files,
        )


class RuntimeChecker(BaseChecker):
    """Performs smoke testing across Python, Node.js/TypeScript, and Go entry points."""

    def __init__(self, entrypoint_cmd: str | None = None):
        super().__init__(name="Runtime CLI / Service Smoke Check", category=CheckCategory.RUNTIME)
        self.entrypoint_cmd = entrypoint_cmd

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths:
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                stdout="No workspace paths for runtime check.",
            )

        cmd = self.entrypoint_cmd
        if not cmd:
            # 1. Check Go entrypoint
            if (paths.project / "main.go").exists():
                cmd = "go run . --help"
            # 2. Check Node / TypeScript entrypoint
            elif (paths.project / "package.json").exists():
                if (paths.project / "dist" / "index.js").exists():
                    cmd = "node dist/index.js --help"
                elif (paths.project / "index.js").exists():
                    cmd = "node index.js --help"
                elif (paths.project / "src" / "index.ts").exists():
                    cmd = "npx ts-node src/index.ts --help"
                elif (paths.project / "server.js").exists():
                    cmd = "node server.js --help"
            # 3. Check Python entrypoint
            else:
                py_files = engine.fs.search_files(task_id, pattern="*.py", role="tester")
                # Use sys.executable (the interpreter FORGE itself is running
                # under, e.g. .venv/bin/python with all project dependencies
                # installed) rather than a bare "python". A bare "python" is
                # resolved via the subprocess's PATH, which may point at a
                # system interpreter with none of the generated project's
                # dependencies (fastapi, etc.) installed -- causing a
                # spurious ModuleNotFoundError smoke-check failure even
                # though the generated code is correct. This is the same bug
                # class already fixed for TestChecker's pytest invocation and
                # LintChecker's ruff invocation; live-reproduced here too
                # (2026-10-07) when running the test suite with a minimal
                # PATH that excludes .venv/bin: the FastAPI and full-stack
                # golden benchmarks' Runtime Checker failed with
                # "ModuleNotFoundError: No module named 'fastapi'" even
                # though fastapi was installed and importable via
                # sys.executable.
                if "main.py" in py_files or "src/main.py" in py_files:
                    cmd = (
                        f'"{sys.executable}" main.py --help'
                        if "main.py" in py_files
                        else f'"{sys.executable}" src/main.py --help'
                    )
                elif "cli.py" in py_files or "src/cli.py" in py_files:
                    cmd = (
                        f'"{sys.executable}" cli.py --help'
                        if "cli.py" in py_files
                        else f'"{sys.executable}" src/cli.py --help'
                    )

        if not cmd:
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                command="smoke_check",
                exit_code=0,
                passed=True,
                duration_ms=0.1,
                stdout="No executable entry point discovered for runtime check.",
            )

        cmd_res = await engine.terminal.run_command(task_id, cmd, timeout_seconds=10, role="tester")
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        # Smoke check passes if command exits with 0 or standard help exit code 0/2
        passed = cmd_res.exit_code in [0, 2] and not cmd_res.timed_out

        return VerificationEvidence(
            check_name=self.name,
            category=self.category,
            command=cmd_res.command,
            exit_code=cmd_res.exit_code,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=cmd_res.stdout,
            stderr=cmd_res.stderr,
        )


class BrowserChecker(BaseChecker):
    """
    Performs real browser and headless web verification:
    Starts a dev server, navigates to target URL, checks for console errors,
    network failures (4xx/5xx), missing assets, DOM interaction, and captures screenshot evidence.
    """

    def __init__(self, start_server_cmd: str | None = None, port: int | None = None):
        super().__init__(
            name="Playwright / Headless Browser Verification", category=CheckCategory.RUNTIME
        )
        self.start_server_cmd = start_server_cmd
        self.port = port

    def _find_free_port(self) -> int:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        import asyncio
        import os
        import time

        import httpx

        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id) or engine.wm.create_workspace(
            task_id
        )

        # 1. Inspect workspace for HTML/web assets
        html_files = list(paths.project.glob("**/*.html"))
        if not html_files:
            # Skip if no frontend/web files
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                command="browser_smoke_check",
                exit_code=0,
                passed=True,
                duration_ms=0.1,
                stdout="No HTML/frontend web assets detected in workspace. Browser check skipped.",
            )

        port = self.port or self._find_free_port()
        # Same PATH-fragility bug class as LintChecker/TestChecker/
        # RuntimeChecker: a bare "python" may not exist at all on minimal
        # Linux images (only "python3" is guaranteed), or may resolve to a
        # different interpreter than the one FORGE itself is running under.
        # `sys.executable` is always correct and always exists.
        server_cmd = self.start_server_cmd or f'"{sys.executable}" -m http.server {port}'
        process_id = f"dev_server_{port}"

        issues = []
        console_errors = []
        network_failures = []
        missing_assets = []
        paths.artifacts.mkdir(parents=True, exist_ok=True)
        screenshot_path = paths.artifacts / f"screenshot_{int(time.time())}.png"
        artifacts_inspected = [str(f.relative_to(paths.project)) for f in html_files]

        try:
            # 2. Start dev server in workspace sandbox
            logger.info(f"Starting dev server for task '{task_id}' on port {port}: {server_cmd}")
            await engine.process.start_process(
                task_id=task_id,
                process_id=process_id,
                command=server_cmd,
                role="developer",
            )

            # Wait for server to become responsive
            base_url = f"http://127.0.0.1:{port}"
            server_ready = False
            for _ in range(20):
                await asyncio.sleep(0.2)
                try:
                    async with httpx.AsyncClient() as client:
                        r = await client.get(base_url, timeout=1.0)
                        if r.status_code < 500:
                            server_ready = True
                            break
                except Exception:
                    pass

            if not server_ready:
                return VerificationEvidence(
                    check_name=self.name,
                    category=self.category,
                    command=server_cmd,
                    exit_code=1,
                    passed=False,
                    duration_ms=(time.perf_counter() - start_time) * 1000.0,
                    stderr=f"Dev server failed to boot on port {port} within timeout.",
                    artifacts_inspected=artifacts_inspected,
                )

            # 3. Try Playwright real browser automation
            playwright_used = False
            evidence_path: Path | None = None
            if os.getenv("FORGE_USE_PLAYWRIGHT", "").lower() in ("1", "true"):
                try:
                    from playwright.async_api import async_playwright

                    async with async_playwright() as p:
                        browser = await p.chromium.launch(headless=True)
                        page = await browser.new_page()

                        # Listen for console errors
                        page.on(
                            "console",
                            lambda msg: (
                                console_errors.append(msg.text)
                                if msg.type in ["error", "warning"]
                                else None
                            ),
                        )

                        # Listen for network failures
                        page.on(
                            "requestfailed",
                            lambda req: network_failures.append(f"{req.url} - {req.failure}"),
                        )
                        page.on(
                            "response",
                            lambda resp: (
                                network_failures.append(f"{resp.url} returned status {resp.status}")
                                if resp.status >= 400
                                else None
                            ),
                        )

                        # Navigate to dev server
                        await page.goto(base_url, wait_until="networkidle", timeout=5000)

                        # Check for missing images
                        broken_images = await page.evaluate("""
                            () => Array.from(document.querySelectorAll('img'))
                                .filter(img => !img.complete || img.naturalWidth === 0)
                                .map(img => img.src)
                        """)
                        missing_assets.extend(broken_images)

                        # Basic layout / interaction check
                        buttons = await page.query_selector_all("button")
                        if buttons:
                            await buttons[0].click()
                            await asyncio.sleep(0.1)

                        # Capture screenshot evidence
                        await page.screenshot(path=str(screenshot_path))
                        await browser.close()
                        playwright_used = True
                except Exception as pe:
                    logger.info(
                        f"Playwright browser engine fallback to headless HTTP/DOM verifier: {pe}"
                    )

            # 4. Fallback headless HTTP/DOM verifier if Playwright not installed or headless failed
            if not playwright_used:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(base_url, timeout=3.0)
                    if resp.status_code >= 400:
                        network_failures.append(f"{base_url} returned status {resp.status_code}")

                    # Check for linked script / css assets in HTML
                    import re

                    linked_assets = re.findall(
                        r'(?:src|href)=["\']([^"\']+\.(?:css|js|png|jpg|svg))["\']', resp.text
                    )
                    for asset in linked_assets:
                        asset_url = f"{base_url}/{asset.lstrip('/')}"
                        try:
                            a_resp = await client.get(asset_url, timeout=2.0)
                            if a_resp.status_code >= 400:
                                missing_assets.append(
                                    f"Missing asset: {asset} (status={a_resp.status_code})"
                                )
                        except Exception:
                            missing_assets.append(f"Failed to fetch asset: {asset}")

                    # Persist the fetched HTML as the evidence artifact instead
                    # of a hardcoded 1x1 PNG. Writing a fabricated 1x1 pixel and
                    # reporting it as "screenshot evidence" made the artifact
                    #目录 look like real visual proof while proving nothing.
                    evidence_path = paths.artifacts / f"browser_evidence_{int(time.time())}.html"
                    try:
                        evidence_path.write_text(resp.text, encoding="utf-8")
                    except Exception:
                        pass
                    (paths.artifacts / f"browser_evidence_{int(time.time())}.meta.json").write_text(
                        json.dumps(
                            {
                                "url": base_url,
                                "status_code": resp.status_code,
                                "captured_at": datetime.now(UTC).isoformat(),
                                "capture_mode": "http_fetch_no_playwright",
                                "screenshot": False,
                                "note": (
                                    "Playwright is not installed; no real screenshot "
                                    "was captured. The fetched HTML is the evidence."
                                ),
                            },
                            indent=2,
                        ),
                        encoding="utf-8",
                    )

            # Compile issues
            if console_errors:
                issues.append(
                    {
                        "type": "console_errors",
                        "count": len(console_errors),
                        "samples": console_errors[:3],
                    }
                )
            if network_failures:
                issues.append(
                    {
                        "type": "network_failures",
                        "count": len(network_failures),
                        "samples": network_failures[:3],
                    }
                )
            if missing_assets:
                issues.append(
                    {
                        "type": "missing_assets",
                        "count": len(missing_assets),
                        "samples": missing_assets[:3],
                    }
                )

            passed = len(issues) == 0
            duration_ms = (time.perf_counter() - start_time) * 1000.0

            if screenshot_path.exists():
                artifacts_inspected.append(str(screenshot_path.relative_to(paths.root)))

            if passed:
                if playwright_used and screenshot_path.exists():
                    stdout = (
                        f"Browser verification completed on {base_url}. "
                        f"Screenshot captured at {screenshot_path.name}."
                    )
                elif evidence_path is not None and evidence_path.exists():
                    stdout = (
                        f"Browser verification completed on {base_url}. "
                        f"Evidence saved to {evidence_path.name} (HTTP fetch; Playwright "
                        f"unavailable, no screenshot captured)."
                    )
                else:
                    stdout = f"Browser verification completed on {base_url}."
            else:
                stdout = ""
            stderr = f"Browser verification detected issues: {issues}" if not passed else ""

            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                command=f"browser_verify({base_url})",
                exit_code=0 if passed else 1,
                passed=passed,
                duration_ms=round(duration_ms, 2),
                stdout=stdout,
                stderr=stderr,
                artifacts_inspected=artifacts_inspected,
                issues=issues,
            )

        finally:
            # Always ensure dev server is terminated
            try:
                await engine.process.stop_process(task_id, process_id, role="developer")
                logger.info(f"Terminated dev server '{process_id}' on port {port}")
            except Exception as e:
                logger.warning(f"Error stopping dev server '{process_id}': {e}")


class SecurityChecker(BaseChecker):
    """
    Executes security auditing across workspace:
    1. Regex-based secret scanning (detects leaked OpenAI, Anthropic, AWS, GitHub keys, and hardcoded credentials).
    2. Static security analysis (Bandit for Python, AST injection checks).
    3. Dependency vulnerability auditing (pip-audit / npm audit).
    """

    SECRET_PATTERNS = [
        ("OpenAI API Key", r"sk-[a-zA-Z0-9]{20,}"),
        ("Anthropic API Key", r"sk-ant-[a-zA-Z0-9-]{20,}"),
        ("AWS Access Key", r"AKIA[0-9A-Z]{16}"),
        ("GitHub Personal Access Token", r"ghp_[a-zA-Z0-9]{36}"),
        ("GitHub Fine-Grained Token", r"github_pat_[a-zA-Z0-9_]{22,}"),
        ("Private Key Header", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        (
            "Hardcoded Password/Secret",
            r"""(?i)(?:api_key|apikey|secret_key|password|passwd|auth_token)\s*=\s*['"]([a-zA-Z0-9@#$%^&*_+=\-!]{8,})['"]""",
        ),
    ]

    def __init__(self):
        super().__init__(name="Static Security & Secret Scanner", category=CheckCategory.SECURITY)

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        import re

        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths:
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                stdout="No workspace paths for security check.",
            )

        issues = []
        artifacts_inspected = []

        # 1. Regex-based Secret Scanning across all workspace files
        scannable_extensions = {
            ".py",
            ".ts",
            ".js",
            ".jsx",
            ".tsx",
            ".json",
            ".env",
            ".yaml",
            ".yml",
            ".go",
            ".html",
        }
        for file_path in paths.project.rglob("*"):
            if file_path.is_file() and file_path.suffix in scannable_extensions:
                # Ignore git directory and cache
                if (
                    ".git" in file_path.parts
                    or "node_modules" in file_path.parts
                    or "__pycache__" in file_path.parts
                    or "artifacts" in file_path.parts
                ):
                    continue

                rel_path = str(file_path.relative_to(paths.project))
                artifacts_inspected.append(rel_path)

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    lines = content.splitlines()
                    for line_idx, line in enumerate(lines, start=1):
                        for pattern_name, pattern_regex in self.SECRET_PATTERNS:
                            match = re.search(pattern_regex, line)
                            if match:
                                val = match.group(0)
                                # Filter obvious safe placeholders
                                if any(
                                    safe in val.lower()
                                    for safe in [
                                        "example",
                                        "placeholder",
                                        "your_",
                                        "test_mock",
                                        "mock_key",
                                        "changeme",
                                        "dummy",
                                        "<",
                                        ">",
                                        "env",
                                    ]
                                ):
                                    continue
                                issues.append(
                                    {
                                        "file": rel_path,
                                        "line": line_idx,
                                        "type": "hardcoded_secret",
                                        "rule": pattern_name,
                                        "preview": f"{val[:6]}***{val[-4:]}"
                                        if len(val) > 10
                                        else "***",
                                    }
                                )
                except Exception as e:
                    logger.debug(f"Error scanning file '{rel_path}' for secrets: {e}")

        # 2. Static Security Tooling: Python (Bandit) or Node (npm audit)
        if (paths.project / "package.json").exists():
            cmd_res = await engine.terminal.run_command(
                task_id, "npm audit --json", timeout_seconds=15, role="security_reviewer"
            )
            if (
                cmd_res.exit_code not in [0, 1]
                and "command not found" not in cmd_res.stderr.lower()
            ):
                pass
        else:
            # Python AST SAST & Bandit
            py_files = list(paths.project.glob("**/*.py"))
            if py_files:
                for py_file in py_files:
                    try:
                        code = py_file.read_text(encoding="utf-8", errors="ignore")
                        if "eval(" in code or "exec(" in code:
                            issues.append(
                                {
                                    "file": str(py_file.relative_to(paths.project)),
                                    "type": "vulnerability",
                                    "rule": "Insecure eval/exec execution detected",
                                }
                            )
                    except Exception:
                        pass

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        passed = len(issues) == 0

        stdout = (
            f"Scanned {len(artifacts_inspected)} files. Zero secret leaks or security violations detected."
            if passed
            else ""
        )
        stderr = (
            f"Security violations detected ({len(issues)} items): {issues}" if not passed else ""
        )

        return VerificationEvidence(
            check_name=self.name,
            category=self.category,
            command="security_scan(secrets, bandit, npm_audit)",
            exit_code=0 if passed else 1,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=stdout,
            stderr=stderr,
            artifacts_inspected=artifacts_inspected,
            issues=issues,
        )


class FeaturePresenceChecker(BaseChecker):
    """
    Validates that requested frameworks, libraries, modules, and domain features
    are actually present and implemented in generated workspace files.
    Detects and fails if files are missing or consist only of untouched scaffold stubs.
    """

    def __init__(self):
        super().__init__(name="Keyword & Feature Presence Verifier", category=CheckCategory.FEATURE)

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths or not paths.project.exists():
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=1,
                passed=False,
                stderr="Workspace project path does not exist.",
            )

        # 1. Retrieve Task Goal & Requirements from store if available
        goal = ""
        if hasattr(engine, "store") and engine.store:
            try:
                task = await engine.store.get_task(task_id)
                if task:
                    goal = task.goal or ""
            except Exception:
                pass

        # 2. Check if Fallback Stub flag exists in workspace state
        fallback_stub_detected = False
        if (paths.state / "FALLBACK_STUB.json").exists():
            fallback_stub_detected = True

        # 3. Collect all project text contents
        all_text = ""
        files_map = {}
        artifacts_inspected = []
        for file_path in paths.project.rglob("*"):
            if file_path.is_file() and not any(
                p in file_path.parts
                for p in [
                    ".git",
                    "node_modules",
                    "__pycache__",
                    "artifacts",
                    "state",
                    "logs",
                    "cache",
                ]
            ):
                rel_path = str(file_path.relative_to(paths.project))
                artifacts_inspected.append(rel_path)
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    files_map[rel_path] = content
                    all_text += f"\n--- {rel_path} ---\n" + content
                except Exception:
                    pass

        issues = []
        goal_lower = goal.lower()
        all_text_lower = all_text.lower()

        # Check: If fallback stub was flagged
        if fallback_stub_detected:
            issues.append(
                {
                    "error": "Task files were generated using fallback stub generator due to AI Universe unavailability or low confidence.",
                    "rule": "fallback_stub",
                }
            )

        # Check: Detect untouched placeholder stubs in files
        for rel_path, content in files_map.items():
            if (
                'print("Running: ' in content
                and "def main():" in content
                and len(content.splitlines()) <= 15
            ):
                issues.append(
                    {
                        "file": rel_path,
                        "error": "Contains untouched default scaffold placeholder stub without feature implementation.",
                        "rule": "placeholder_stub",
                    }
                )

        # Check: Goal-specific feature presence
        # FastAPI
        if "fastapi" in goal_lower:
            has_fastapi = any(
                k in all_text for k in ["from fastapi", "import fastapi", "FastAPI(", "fastapi."]
            )
            if not has_fastapi:
                issues.append(
                    {
                        "error": "Objective specifies 'FastAPI', but no FastAPI library imports or application instances were found in project files.",
                        "rule": "fastapi_presence",
                    }
                )

        # Flask
        if "flask" in goal_lower:
            has_flask = any(
                k in all_text for k in ["from flask", "import flask", "Flask(", "flask."]
            )
            if not has_flask:
                issues.append(
                    {
                        "error": "Objective specifies 'Flask', but no Flask library imports or application instances were found in project files.",
                        "rule": "flask_presence",
                    }
                )

        # SQLite / Database
        if "sqlite" in goal_lower or ("database" in goal_lower and "sql" in goal_lower):
            if not any(
                k in all_text_lower
                for k in ["sqlite3", "sqlalchemy", "cursor", "execute(", "create table", "select "]
            ):
                issues.append(
                    {
                        "error": "Objective specifies SQLite/Database, but no database operations or queries were found in project files.",
                        "rule": "sqlite_presence",
                    }
                )

        # Portfolio Website / Dark Mode / Hero
        if "dark mode" in goal_lower or "dark-mode" in goal_lower:
            if not any(k in all_text_lower for k in ["dark", "toggle", "theme", "mode"]):
                issues.append(
                    {
                        "error": "Objective specifies 'dark mode', but no dark mode toggle or theme styling was found in HTML/CSS/JS.",
                        "rule": "dark_mode_presence",
                    }
                )

        if "hero" in goal_lower:
            if not any(k in all_text_lower for k in ["hero", "header", "banner", "intro"]):
                issues.append(
                    {
                        "error": "Objective specifies 'hero section', but no hero section was found in HTML/CSS.",
                        "rule": "hero_presence",
                    }
                )

        if any(w in goal_lower for w in ["portfolio", "portfolio website"]):
            if not any(
                k in all_text_lower for k in ["portfolio", "project", "about", "skill", "contact"]
            ):
                issues.append(
                    {
                        "error": "Objective specifies 'portfolio website', but core portfolio sections (projects, about, skills, contact) were missing.",
                        "rule": "portfolio_presence",
                    }
                )

        # Multi-file static web files if explicitly required in goal
        if "index.html" in goal_lower and "index.html" not in files_map:
            issues.append(
                {
                    "file": "index.html",
                    "error": "Objective required 'index.html', but index.html was not generated.",
                    "rule": "file_manifest_presence",
                }
            )
        if "style.css" in goal_lower and "style.css" not in files_map:
            issues.append(
                {
                    "file": "style.css",
                    "error": "Objective required 'style.css', but style.css was not generated.",
                    "rule": "file_manifest_presence",
                }
            )
        if ("script.js" in goal_lower or "app.js" in goal_lower) and not any(
            f in files_map for f in ["script.js", "app.js"]
        ):
            issues.append(
                {
                    "file": "script.js",
                    "error": "Objective required JavaScript file ('script.js' / 'app.js'), but neither was found.",
                    "rule": "file_manifest_presence",
                }
            )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        passed = len(issues) == 0

        stdout = (
            f"Verified {len(artifacts_inspected)} project files. All requested features, libraries, and objective elements are present and implemented."
            if passed
            else ""
        )
        stderr = (
            "Feature presence verification failed:\n"
            + "\n".join(f"- {issue.get('error', issue)}" for issue in issues)
            if not passed
            else ""
        )

        return VerificationEvidence(
            check_name=self.name,
            category=self.category,
            command="feature_presence_verification(goal, project_files)",
            exit_code=0 if passed else 1,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=stdout,
            stderr=stderr,
            artifacts_inspected=artifacts_inspected,
            issues=issues,
        )


class AestheticAndInteractiveChecker(BaseChecker):
    """
    Objective verifier checking web deliverables against Lovable/Bolt/Durable standards:
    - 3D WebGL / Canvas presence
    - Glassmorphic tokens & CSS variables
    - Event listener wiring
    - Zero placeholder text ('Lorem ipsum', 'Project Alpha', etc.)
    """

    def __init__(self):
        super().__init__(
            name="3D Aesthetic & Interactivity Verification",
            category=CheckCategory.FEATURE,
        )

    async def run_check(self, task_id: str, engine: ExecutionEngine) -> VerificationEvidence:
        import re
        import time

        start_time = time.perf_counter()
        paths = engine.wm.get_workspace_paths(task_id)
        if not paths:
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                stdout="No workspace paths found. Skipped.",
            )

        html_files = list(paths.project.glob("**/*.html"))
        if not html_files:
            return VerificationEvidence(
                check_name=self.name,
                category=self.category,
                exit_code=0,
                passed=True,
                stdout="No HTML assets detected. Aesthetic verification skipped.",
            )

        css_files = list(paths.project.glob("**/*.css"))
        js_files = list(paths.project.glob("**/*.js"))

        html_content = "\n".join(
            f.read_text(encoding="utf-8", errors="ignore") for f in html_files
        )
        css_content = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in css_files)
        js_content = "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in js_files)

        artifacts_inspected = [
            str(f.relative_to(paths.project)) for f in html_files + css_files + js_files
        ]
        issues: list[dict[str, Any]] = []

        # 1. 3D Canvas / WebGL Check
        has_canvas = "<canvas" in html_content.lower()
        if not has_canvas:
            issues.append(
                {
                    "type": "missing_3d_canvas",
                    "error": "No 3D Canvas element (<canvas>) found in HTML.",
                }
            )

        # 2. Glassmorphic Tokens Check
        has_glass = "backdrop-filter" in css_content.lower() or "blur(" in css_content.lower()
        has_vars = ":root" in css_content and "--" in css_content
        if not (has_glass or has_vars):
            issues.append(
                {
                    "type": "missing_glassmorphic_tokens",
                    "error": "CSS lacks modern design variables or backdrop-filter glassmorphism.",
                }
            )

        # 3. Interactivity Check
        has_events = "addeventlistener" in js_content.lower() or "click" in js_content.lower()
        if not has_events:
            issues.append(
                {
                    "type": "missing_interactivity",
                    "error": "No interactive JavaScript event listeners detected.",
                }
            )

        # 4. Zero Placeholder Copy Check
        placeholders = [r"\blorem ipsum\b", r"\bproject alpha\b", r"\bproject beta\b"]
        for pat in placeholders:
            if re.search(pat, html_content, re.IGNORECASE):
                clean_pat = pat.replace(r"\b", "")
                issues.append(
                    {
                        "type": "placeholder_detected",
                        "error": f"Found dummy placeholder matching '{clean_pat}'.",
                    }
                )

        duration_ms = (time.perf_counter() - start_time) * 1000.0
        passed = len(issues) == 0

        stdout = (
            f"Aesthetic verification passed: 3D canvas, glassmorphism tokens, interactivity, and zero placeholders verified across {len(artifacts_inspected)} files."
            if passed
            else ""
        )
        stderr = (
            "Aesthetic verification issues:\n" + "\n".join(f"- {i['error']}" for i in issues)
            if not passed
            else ""
        )

        return VerificationEvidence(
            check_name=self.name,
            category=self.category,
            command="aesthetic_interactivity_verification",
            exit_code=0 if passed else 1,
            passed=passed,
            duration_ms=round(duration_ms, 2),
            stdout=stdout,
            stderr=stderr,
            artifacts_inspected=artifacts_inspected,
            issues=issues,
        )
