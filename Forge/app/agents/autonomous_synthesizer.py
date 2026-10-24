"""
app/agents/autonomous_synthesizer.py — Forge Autonomous Software Synthesizer.

Enhances Forge with:
1. Safe starter generation for Python and JavaScript
2. Syntax-only validation without running generated source
3. Test Generation: Auto-generates unit tests for synthesized code
4. Static security checks and retained output artifacts
5. Code Review Integration: Pre-delivery security and quality checks
6. Runtime checks are marked unverified until an isolated sandbox is configured
"""
from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("agents.autonomous_synthesizer")


@dataclass
class SynthesisRequest:
    """Request for autonomous software synthesis."""
    description: str
    language: str = "python"
    output_path: str = ""
    requirements: list[str] = field(default_factory=list)
    test_coverage: bool = True
    security_check: bool = True


@dataclass
class SynthesisResult:
    """Result of autonomous synthesis."""
    success: bool
    files_created: list[str] = field(default_factory=list)
    tests_created: list[str] = field(default_factory=list)
    verification_passed: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    iterations: int = 0
    static_checks_passed: bool = False
    runtime_tests_executed: bool = False
    output_directory: str = ""


class AutonomousSynthesizer:
    """Autonomous software synthesizer with iterative refinement."""

    # Only languages with safe syntax-only validation are advertised here.
    SUPPORTED_LANGUAGES = {
        "python": {"extension": ".py", "kind": "python"},
        "javascript": {"extension": ".js", "kind": "javascript"},
    }

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max(1, min(int(max_iterations), 10))

    async def synthesize(self, request: SynthesisRequest) -> SynthesisResult:
        """Synthesize software autonomously with iterative refinement."""
        logger.info(f"Synthesizing: {request.description[:80]}")

        result = SynthesisResult(success=False)
        if not isinstance(request.description, str) or not request.description.strip():
            result.errors.append("A non-empty synthesis description is required")
            return result
        if len(request.description) > 4000:
            result.errors.append("Synthesis description exceeds the 4000-character safety limit")
            return result

        language = request.language.strip().lower()
        language_config = self.SUPPORTED_LANGUAGES.get(language)
        if not language_config:
            result.errors.append(
                f"Unsupported language: {request.language}. Safe syntax validation is available for Python and JavaScript."
            )
            return result

        # Never derive filesystem paths from user-supplied descriptions.
        workspace = tempfile.mkdtemp(prefix="forge_synth_")
        output_path = Path(workspace) / "output"
        output_path.mkdir(parents=True, exist_ok=True)

        try:
            # Iterative synthesis loop
            for iteration in range(self.max_iterations):
                result.iterations = iteration + 1
                logger.info(f"Synthesis iteration {iteration + 1}/{self.max_iterations}")

                # Step 1: Generate code
                code = await self._generate_code(request, output_path, language_config)
                if not code:
                    result.errors.append("Code generation failed")
                    break

                # Step 2: Verify build
                build_ok, build_output = await self._verify_build(output_path, request.language)
                if not build_ok:
                    result.errors.append(f"Build failed: {build_output}")
                    # Try to fix
                    fixed = await self._fix_build_error(build_output, request, output_path, language_config)
                    if not fixed:
                        break
                    continue

                # Step 3: Generate tests if requested
                if request.test_coverage:
                    test_files = await self._generate_tests(request, output_path, language_config)
                    result.tests_created.extend(test_files)

                # Step 4: Run security check if requested
                if request.security_check:
                    security_ok, security_findings = await self._run_security_check(output_path)
                    if not security_ok:
                        result.errors.extend(security_findings)
                        break

                # Generated tests are artifacts only. They are never executed on
                # the Forge host; runtime execution requires a dedicated sandbox.
                if request.test_coverage:
                    if result.tests_created:
                        result.warnings.append(
                            "Generated tests were not executed: no isolated runtime sandbox is configured."
                        )
                    else:
                        result.warnings.append(
                            "No test template exists for this language; only syntax and static security checks ran."
                        )

                result.success = True
                result.static_checks_passed = True
                result.runtime_tests_executed = False
                result.verification_passed = not request.test_coverage
                # Keep results after the temporary verification workspace is removed.
                final_path = (
                    Path(request.output_path).expanduser().resolve()
                    if request.output_path
                    else Path(tempfile.mkdtemp(prefix="forge_synth_results_"))
                )
                final_path.mkdir(parents=True, exist_ok=True)
                for generated_file in sorted(output_path.iterdir()):
                    if generated_file.is_file():
                        shutil.copy2(generated_file, final_path / generated_file.name)
                result.output_directory = str(final_path)
                result.files_created = [
                    str(final_path / generated_file.name)
                    for generated_file in output_path.glob(f"*{language_config['extension']}")
                ]
                result.tests_created = [
                    str(final_path / generated_file.name)
                    for generated_file in output_path.glob("test_*.py")
                ]

                logger.info(f"Synthesis completed successfully in {iteration + 1} iterations")
                break

        except Exception as e:
            logger.error(f"Synthesis error: {e}")
            result.errors.append(str(e))
        finally:
            # Cleanup workspace (in production, keep for debugging)
            shutil.rmtree(workspace, ignore_errors=True)

        return result

    async def _generate_code(
        self,
        request: SynthesisRequest,
        output_path: Path,
        language_config: dict,
    ) -> str:
        """Create a starter implementation while treating the request as data."""
        language = request.language.strip().lower()
        extension = language_config["extension"]
        output_file = output_path / f"synthesized{extension}"

        if language == "python":
            # repr() safely quotes arbitrary request text. Do not paste it into a
            # source comment or docstring where quote termination becomes code.
            code = (
                '"""Starter generated by Forge; request content is data."""\n'
                f"REQUEST_DESCRIPTION = {request.description!r}\n\n"
                "def main() -> None:\n"
                '    """Display the request summary without executing it."""\n'
                '    print("Hello from Forge synthesized code!")\n'
                '    print("Description:", REQUEST_DESCRIPTION)\n\n'
                'if __name__ == "__main__":\n'
                "    main()\n"
            )
        else:
            description_literal = json.dumps(request.description, ensure_ascii=True)
            code = (
                "// Starter generated by Forge; request content is data.\n"
                f"const requestDescription = {description_literal};\n\n"
                "function main() {\n"
                '    console.log("Hello from Forge synthesized code!");\n'
                '    console.log("Description:", requestDescription);\n'
                "}\n\n"
                "main();\n"
            )

        output_file.write_text(code, encoding="utf-8")
        return code

    async def _verify_build(self, output_path: Path, language: str) -> tuple[bool, str]:
        """Syntax-check generated source without executing it."""
        language_config = self.SUPPORTED_LANGUAGES.get(language.strip().lower())
        if not language_config:
            return False, "Unsupported language; runtime execution is intentionally disabled."

        extension = language_config["extension"]
        files = sorted(output_path.glob(f"*{extension}"))
        if not files:
            return False, "No source files found"

        if language_config["kind"] == "python":
            command = [sys.executable, "-m", "py_compile", *(str(file) for file in files)]
        else:
            node = shutil.which("node")
            if not node:
                return False, "Node.js is required for JavaScript syntax checking; source was not executed."
            command = [node, "--check", str(files[0])]

        try:
            result = subprocess.run(
                command,
                cwd=str(output_path),
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            return result.returncode == 0, (result.stdout + result.stderr)[-8000:]
        except subprocess.TimeoutExpired:
            return False, "Syntax checker timed out after 30 seconds"
        except OSError as exc:
            return False, f"Could not start syntax checker: {type(exc).__name__}"

    async def _fix_build_error(
        self,
        error_output: str,
        request: SynthesisRequest,
        output_path: Path,
        language_config: dict,
    ) -> bool:
        """Attempt to fix a build error."""
        # In production, this would parse the error and ask LLM to fix
        # For now, return False (no automatic fix)
        logger.warning(f"Build error (no auto-fix): {error_output[:100]}")
        return False

    async def _generate_tests(
        self,
        request: SynthesisRequest,
        output_path: Path,
        language_config: dict,
    ) -> list[str]:
        """Generate tests as reviewable artifacts without running them on the host."""
        if request.language.strip().lower() != "python":
            return []

        test_code = '''"""Generated test template; run only in an isolated sandbox."""
from synthesized import main


def test_main_runs():
    main()
'''
        test_file = output_path / "test_synthesized.py"
        test_file.write_text(test_code, encoding="utf-8")
        return [str(test_file)]

    async def _run_security_check(self, output_path: Path) -> tuple[bool, list[str]]:
        """Perform a conservative static scan; never execute generated code."""
        findings: list[str] = []
        python_dangerous_calls = {"eval", "exec", "compile", "__import__"}
        dangerous_modules = {"subprocess", "socket", "ctypes"}
        for file in sorted(output_path.iterdir()):
            if not file.is_file() or file.suffix not in {".py", ".js"}:
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except OSError as exc:
                findings.append(f"Could not read {file.name}: {type(exc).__name__}")
                continue

            if file.suffix == ".py":
                try:
                    tree = ast.parse(content, filename=file.name)
                except SyntaxError as exc:
                    findings.append(f"Syntax error in {file.name}: {exc.msg}")
                    continue
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    target = node.func
                    if isinstance(target, ast.Name) and target.id in python_dangerous_calls:
                        findings.append(f"Potentially dangerous call {target.id}() in {file.name}")
                    elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
                        if target.value.id == "os" and target.attr in {"system", "popen", "spawn", "exec"}:
                            findings.append(f"Potentially dangerous call os.{target.attr}() in {file.name}")
                        if target.value.id in dangerous_modules:
                            findings.append(f"Potentially dangerous call {target.value.id}.{target.attr}() in {file.name}")
            elif re.search(r"\b(eval|Function)\s*\(", content) or re.search(r"\bprocess\.exit\s*\(", content):
                findings.append(f"Potentially dangerous JavaScript construct found in {file.name}")

        return not findings, findings

    async def _run_tests(self, output_path: Path, language: str) -> tuple[bool, str]:
        """Refuse host execution; callers must integrate a real isolated runner."""
        return (
            False,
            "Runtime tests were not executed. Configure an isolated sandbox before running generated code.",
        )

    async def _fix_test_error(
        self,
        error_output: str,
        request: SynthesisRequest,
        output_path: Path,
        language_config: dict,
    ) -> bool:
        """Attempt to fix a test error."""
        logger.warning(f"Test error (no auto-fix): {error_output[:100]}")
        return False


# Module-level singleton
autonomous_synthesizer = AutonomousSynthesizer()
