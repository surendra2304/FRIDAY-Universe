"""
Task Analyzer for Project FORGE.
Evaluates high-level goals and requirements to extract technical domain, language stack, and complexity.
"""

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.providers import BaseModelProvider, get_provider

logger = get_logger("core.analyzer")


class TaskAnalysisResult(BaseModel):
    goal_summary: str
    detected_domain: str = "Software Engineering"
    primary_language: str = "Python"
    detected_runtime: str = "Python"
    detected_frameworks: list[str] = Field(default_factory=list)
    estimated_complexity: str = "medium"  # low, medium, high, critical
    recommended_mode: str = "autonomous"
    key_constraints: list[str] = Field(default_factory=list)
    suggested_milestones: list[str] = Field(default_factory=list)


class TaskAnalyzer:
    """Intakes goals and requirements to produce a structured TaskAnalysisResult."""

    def __init__(self, provider: BaseModelProvider | None = None):
        self.provider = provider or get_provider()

    async def analyze(self, goal: str, requirements: list[str] | None = None) -> TaskAnalysisResult:
        """Perform static and heuristic analysis on input goal and requirements."""
        req_list = requirements or []
        logger.info(
            f"Analyzing task goal: '{goal[:80]}...' with {len(req_list)} explicit requirements"
        )

        text = f"{goal} {' '.join(req_list)}".lower()

        # 1. Detect Frameworks
        detected_frameworks = []
        framework_keywords = {
            "express": "Express.js",
            "fastify": "Fastify",
            "react": "React",
            "next.js": "Next.js",
            "nextjs": "Next.js",
            "vue": "Vue",
            "fastapi": "FastAPI",
            "flask": "Flask",
            "django": "Django",
            "gin": "Gin",
            "fiber": "Fiber",
            "chi": "Chi",
        }
        for kw, fw_name in framework_keywords.items():
            if kw in text and fw_name not in detected_frameworks:
                detected_frameworks.append(fw_name)

        # 2. Detect Primary Language & Runtime
        primary_lang = "Python"
        detected_runtime = "Python"

        if (
            "typescript" in text
            or "tsx" in text
            or ("react" in text and "python" not in text)
            or "next.js" in text
            or "nextjs" in text
        ):
            primary_lang = "TypeScript"
            detected_runtime = "Node.js"
        elif any(
            k in text
            for k in ["node", "nodejs", "javascript", "js", "npm", "express", "fastify", "yarn"]
        ):
            primary_lang = "TypeScript" if "typescript" in text else "JavaScript"
            detected_runtime = "Node.js"
        elif (
            any(k in text for k in ["golang", "go ", "go.mod", "gin", "fiber", "chi"])
            and "python" not in text
        ):
            primary_lang = "Go"
            detected_runtime = "Go"
        elif "rust" in text or "cargo" in text:
            primary_lang = "Rust"
            detected_runtime = "Rust"

        complexity = "medium"
        if (
            len(req_list) > 5
            or "distributed" in text
            or "microservice" in text
            or "full-stack" in text
        ):
            complexity = "high"
        elif len(req_list) <= 1 and len(goal.split()) < 10:
            complexity = "low"

        domain = (
            "Full-Stack Engineering"
            if ("frontend" in text or "react" in text or "ui" in text)
            and ("backend" in text or "api" in text or "fastapi" in text or "express" in text)
            else "Software Engineering"
        )

        return TaskAnalysisResult(
            goal_summary=goal.strip(),
            detected_domain=domain,
            primary_language=primary_lang,
            detected_runtime=detected_runtime,
            detected_frameworks=detected_frameworks,
            estimated_complexity=complexity,
            key_constraints=req_list,
            suggested_milestones=[
                "Requirements Specification",
                "Architecture Design",
                "Implementation",
                "Verification Gate",
                "Security Review Gate",
                "Release Package",
            ],
        )


task_analyzer = TaskAnalyzer()
