"""
Polyglot Dependency and Lock File Manager for Project FORGE.
Supports Python (pip/requirements.txt), Node.js/JavaScript (npm/package.json), and TypeScript (tsconfig.json).
"""

import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.logging import get_logger

logger = get_logger("core.language_dependency_manager")


class DependencyCheckResult(BaseModel):
    is_valid: bool
    language: str
    manifest_file: str
    dependencies: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    install_command: str = ""


class LanguageDependencyManager:
    """Manages language manifest parsing, version lockfile generation, and package validation."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def inspect_python_dependencies(self) -> DependencyCheckResult:
        """Inspect and parse Python requirements.txt."""
        req_file = self.workspace_path / "requirements.txt"
        if not req_file.exists():
            return DependencyCheckResult(
                is_valid=False,
                language="python",
                manifest_file="requirements.txt",
                warnings=["requirements.txt not found in workspace."],
            )

        deps: dict[str, str] = {}
        warnings: list[str] = []

        for line in req_file.read_text(encoding="utf-8").splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            parts = cleaned.split("==")
            if len(parts) == 2:
                deps[parts[0].strip()] = parts[1].strip()
            elif ">=" in cleaned:
                p = cleaned.split(">=")
                deps[p[0].strip()] = f">={p[1].strip()}"
            else:
                deps[cleaned] = "latest"
                warnings.append(f"Unpinned dependency: '{cleaned}'.")

        return DependencyCheckResult(
            is_valid=True,
            language="python",
            manifest_file="requirements.txt",
            dependencies=deps,
            warnings=warnings,
            install_command="pip install -r requirements.txt",
        )

    def inspect_node_dependencies(self, subdir: str | None = None) -> DependencyCheckResult:
        """Inspect and parse Node.js package.json."""
        target_dir = (self.workspace_path / subdir) if subdir else self.workspace_path
        pkg_file = target_dir / "package.json"

        if not pkg_file.exists():
            return DependencyCheckResult(
                is_valid=False,
                language="javascript/typescript",
                manifest_file="package.json",
                warnings=["package.json not found in target workspace directory."],
            )

        try:
            data = json.loads(pkg_file.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            warnings: list[str] = []

            if not data.get("name"):
                warnings.append("package.json is missing 'name' field.")
            if not data.get("scripts"):
                warnings.append("package.json defines no 'scripts'.")

            return DependencyCheckResult(
                is_valid=True,
                language="javascript/typescript",
                manifest_file="package.json",
                dependencies=deps,
                warnings=warnings,
                install_command="npm install",
            )
        except json.JSONDecodeError as e:
            return DependencyCheckResult(
                is_valid=False,
                language="javascript/typescript",
                manifest_file="package.json",
                warnings=[f"Malformed package.json: {e}"],
            )

    def remediate_vulnerabilities(self) -> list[str]:
        """Scan and automatically upgrade vulnerable dependencies to safe patched versions."""
        from app.verification.security_scanner import OutputSecurityScanner

        scanner = OutputSecurityScanner(self.workspace_path)
        return scanner.remediate_vulnerable_dependencies()

    def generate_lockfile(self, language: str) -> Path | None:
        """Generate simulated deterministic lockfile for dependency reproducibility."""
        if language == "python":
            req_res = self.inspect_python_dependencies()
            if not req_res.is_valid:
                return None
            lock_path = self.workspace_path / "requirements.lock"
            lines = [
                f"{pkg}=={ver.replace('>=', '') if '>=' in ver else (ver if ver != 'latest' else '1.0.0')}"
                for pkg, ver in req_res.dependencies.items()
            ]
            lock_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return lock_path

        elif language in ["javascript", "typescript"]:
            node_res = self.inspect_node_dependencies()
            if not node_res.is_valid:
                return None
            lock_path = self.workspace_path / "package-lock.json"
            lock_payload = {
                "name": "forge-generated-app",
                "lockfileVersion": 3,
                "requires": True,
                "packages": {"": {"dependencies": node_res.dependencies}},
            }
            lock_path.write_text(json.dumps(lock_payload, indent=2), encoding="utf-8")
            return lock_path

        return None
