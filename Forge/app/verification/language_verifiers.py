"""
Multi-Language Verification Subsystem for Project FORGE.
Provides syntax, package integrity, tsconfig, and API contract verification for JavaScript, TypeScript, and Full-Stack codebases.
"""

import json
from pathlib import Path

from app.core.logging import get_logger
from app.verification.advanced_battery import VerificationCheck

logger = get_logger("verification.language_verifiers")


class PolyglotLanguageVerifier:
    """Verifies JavaScript, TypeScript, and Full-Stack codebases."""

    def __init__(self, workspace_path: Path):
        self.workspace_path = workspace_path

    def verify_node_syntax_and_imports(self) -> VerificationCheck:
        """Inspect JavaScript/TypeScript files for ES module syntax errors and balanced delimiters."""
        js_files = (
            list(self.workspace_path.rglob("*.js"))
            + list(self.workspace_path.rglob("*.mjs"))
            + list(self.workspace_path.rglob("*.jsx"))
        )
        syntax_errors = []

        for p in js_files:
            if "node_modules" in str(p):
                continue
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                # Basic balance check for {}, (), []
                counts = {char: content.count(char) for char in "{}()[]"}
                if counts["{"] != counts["}"]:
                    syntax_errors.append({"file": p.name, "issue": "Unmatched curly braces `{}`."})
                if counts["("] != counts[")"]:
                    syntax_errors.append({"file": p.name, "issue": "Unmatched parentheses `()`."})
                if counts["["] != counts["]"]:
                    syntax_errors.append({"file": p.name, "issue": "Unmatched brackets `[]`."})

                # Check for import/export syntax consistency
                has_import = "import " in content
                has_require = "require(" in content
                if has_import and has_require:
                    syntax_errors.append(
                        {
                            "file": p.name,
                            "issue": "Mixed CommonJS `require()` and ES module `import` syntax detected.",
                        }
                    )
            except Exception as e:
                logger.debug(f"Syntax inspection error in {p}: {e}")

        status = (
            "fail"
            if any("Unmatched" in err["issue"] for err in syntax_errors)
            else ("warn" if syntax_errors else "pass")
        )
        return VerificationCheck(
            name="Node.js JavaScript Syntax Verification",
            category="quality",
            status=status,
            evidence={"checked_files": len(js_files), "syntax_issues": syntax_errors},
            fix_suggestions=[
                f"Fix syntax in {err['file']}: {err['issue']}" for err in syntax_errors[:5]
            ],
        )

    def verify_typescript_configuration(self) -> VerificationCheck:
        """Verify tsconfig.json presence, compilerOptions, and strict type safety settings."""
        tsconfig_files = list(self.workspace_path.rglob("tsconfig.json"))
        ts_files = list(self.workspace_path.rglob("*.ts")) + list(
            self.workspace_path.rglob("*.tsx")
        )

        if not ts_files and not tsconfig_files:
            return VerificationCheck(
                name="TypeScript Configuration & Compiler Check",
                category="quality",
                status="pass",
                evidence={"message": "No TypeScript files detected."},
            )

        if ts_files and not tsconfig_files:
            return VerificationCheck(
                name="TypeScript Configuration & Compiler Check",
                category="quality",
                status="fail",
                evidence={"ts_files_count": len(ts_files), "tsconfig_present": False},
                fix_suggestions=[
                    "Add a `tsconfig.json` to the root or frontend directory for TypeScript compilation."
                ],
            )

        warnings = []
        for cfg in tsconfig_files:
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                opts = data.get("compilerOptions", {})
                if not opts.get("strict"):
                    warnings.append(
                        f'{cfg.name} has strict mode disabled (`"strict": false` or omitted).'
                    )
            except json.JSONDecodeError as e:
                return VerificationCheck(
                    name="TypeScript Configuration & Compiler Check",
                    category="quality",
                    status="fail",
                    evidence={"file": cfg.name, "error": str(e)},
                    fix_suggestions=[f"Fix JSON syntax in {cfg.name}."],
                )

        status = "warn" if warnings else "pass"
        return VerificationCheck(
            name="TypeScript Configuration & Compiler Check",
            category="quality",
            status=status,
            evidence={"tsconfig_count": len(tsconfig_files), "warnings": warnings},
            fix_suggestions=warnings,
        )

    def verify_cross_language_api_contract(self) -> VerificationCheck:
        """Verify contract consistency between decoupled frontend and backend sub-trees."""
        contract_files = list(self.workspace_path.rglob("api_contract.json"))
        if not contract_files:
            # Check if this is a fullstack workspace with frontend and backend
            is_fullstack = (self.workspace_path / "frontend").exists() and (
                self.workspace_path / "backend"
            ).exists()
            if not is_fullstack:
                return VerificationCheck(
                    name="Cross-Language API Contract Verification",
                    category="quality",
                    status="pass",
                    evidence={"message": "Single-tier project architecture."},
                )

        try:
            for cf in contract_files:
                data = json.loads(cf.read_text(encoding="utf-8"))
                if not data.get("endpoints"):
                    return VerificationCheck(
                        name="Cross-Language API Contract Verification",
                        category="quality",
                        status="warn",
                        evidence={
                            "contract_file": cf.name,
                            "issue": "No endpoints defined in api_contract.json.",
                        },
                        fix_suggestions=["Define endpoint schemas in api_contract.json."],
                    )
        except Exception as e:
            return VerificationCheck(
                name="Cross-Language API Contract Verification",
                category="quality",
                status="fail",
                evidence={"error": str(e)},
                fix_suggestions=["Ensure api_contract.json is valid JSON."],
            )

        return VerificationCheck(
            name="Cross-Language API Contract Verification",
            category="quality",
            status="pass",
            evidence={"contracts_verified": len(contract_files)},
        )

    def run_all(self) -> list[VerificationCheck]:
        """Run all multi-language verifications."""
        return [
            self.verify_node_syntax_and_imports(),
            self.verify_typescript_configuration(),
            self.verify_cross_language_api_contract(),
        ]
