"""
Continuous Template Evolution & A/B Testing Engine for Project FORGE.
Tracks template efficacy, computes success scores from verification outcomes,
and evaluates template variants via A/B testing.
"""

from typing import Any

from pydantic import BaseModel

from app.core.logging import get_logger

logger = get_logger("improvement.template_evolution")


class TemplateVariant(BaseModel):
    """A template component variant under evaluation."""

    name: str
    archetype: str  # website, cli, api, script
    code_pattern: str
    success_count: int = 0
    failure_count: int = 0
    total_evaluations: int = 0
    security_scan_passes: int = 0
    security_scan_failures: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_evaluations == 0:
            return 100.0
        return round((self.success_count / self.total_evaluations) * 100.0, 1)

    @property
    def security_pass_rate(self) -> float:
        total_sec = self.security_scan_passes + self.security_scan_failures
        if total_sec == 0:
            return 100.0
        return round((self.security_scan_passes / total_sec) * 100.0, 1)

    @property
    def composite_score(self) -> float:
        """Composite score weighing functionality (60%) and security (40%)."""
        return round((self.success_rate * 0.60) + (self.security_pass_rate * 0.40), 1)


class TemplateEvolutionEngine:
    """Manages template success tracking, pattern scoring, and variant promotion."""

    def __init__(self):
        self.variants: dict[str, TemplateVariant] = {}
        self._initialize_default_variants()

    def _initialize_default_variants(self):
        """Seed initial template variants for A/B tracking."""
        self.register_variant(
            name="css_flexbox_base",
            archetype="website",
            code_pattern="display: flex; justify-content: space-between;",
        )
        self.register_variant(
            name="css_grid_base",
            archetype="website",
            code_pattern="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));",
        )
        self.register_variant(
            name="fastapi_in_memory_crud",
            archetype="api",
            code_pattern="ITEMS_DB: Dict[int, Item] = {}",
        )
        self.register_variant(
            name="fastapi_sqlite_crud",
            archetype="api",
            code_pattern="CREATE TABLE IF NOT EXISTS items",
        )

    def register_variant(self, name: str, archetype: str, code_pattern: str) -> TemplateVariant:
        """Register a new template pattern variant."""
        var = TemplateVariant(
            name=name,
            archetype=archetype,
            code_pattern=code_pattern,
        )
        self.variants[name] = var
        return var

    def record_outcome(self, variant_name: str, passed_verification: bool):
        """Record verification outcome for a template variant."""
        var = self.variants.get(variant_name)
        if not var:
            return
        var.total_evaluations += 1
        if passed_verification:
            var.success_count += 1
        else:
            var.failure_count += 1
        logger.debug(
            f"Template variant '{variant_name}' updated: {var.success_rate}% success ({var.total_evaluations} runs)"
        )

    def record_security_outcome(self, variant_name: str, passed_security: bool):
        """Record security scan outcome for a template variant."""
        var = self.variants.get(variant_name)
        if not var:
            return
        if passed_security:
            var.security_scan_passes += 1
        else:
            var.security_scan_failures += 1
        logger.debug(
            f"Template variant '{variant_name}' security updated: {var.security_pass_rate}% security pass ({var.security_scan_passes + var.security_scan_failures} scans)"
        )

    def get_winning_variant(self, archetype: str) -> TemplateVariant | None:
        """Select the highest scoring template variant for an archetype, factoring in security and function."""
        candidates = [v for v in self.variants.values() if v.archetype == archetype]
        if not candidates:
            return None
        evaluated = [
            v
            for v in candidates
            if v.total_evaluations > 0 or (v.security_scan_passes + v.security_scan_failures) > 0
        ]
        if evaluated:
            return max(evaluated, key=lambda v: (v.composite_score, v.total_evaluations))
        return candidates[0]

    def evaluate_ab_variants(self, variant_a: str, variant_b: str) -> dict[str, Any]:
        """Compare two template variants side-by-side."""
        va = self.variants.get(variant_a)
        vb = self.variants.get(variant_b)
        if not va or not vb:
            return {"error": "One or both variants not found"}

        winner = va.name if va.success_rate >= vb.success_rate else vb.name
        return {
            "variant_a": {
                "name": va.name,
                "success_rate": va.success_rate,
                "runs": va.total_evaluations,
            },
            "variant_b": {
                "name": vb.name,
                "success_rate": vb.success_rate,
                "runs": vb.total_evaluations,
            },
            "promoted_winner": winner,
        }


template_evolution_engine = TemplateEvolutionEngine()
