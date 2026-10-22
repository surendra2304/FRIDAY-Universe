"""
Smart Template Matcher and Hybrid AI Scaffolding Engine for Project FORGE.
"""

import re
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.marketplace.registry import template_registry

logger = get_logger("agents.template_matcher")


class TemplateMatchResult(BaseModel):
    matched_template_id: str | None = None
    template_name: str | None = None
    confidence: float = 0.0  # 0.0 to 1.0
    reasoning: str = ""
    use_hybrid_scaffold: bool = False
    customization_hints: list[str] = Field(default_factory=list)


# Keyword weights for semantic matching
TEMPLATE_INTENT_RULES: dict[str, dict[str, Any]] = {
    "portfolio-web": {
        "keywords": [
            "portfolio",
            "resume",
            "personal website",
            "showcase",
            "developer page",
            "bio",
        ],
        "min_score": 0.85,
    },
    "blog-web": {
        "keywords": ["blog", "markdown blog", "articles", "posts", "publishing"],
        "min_score": 0.90,
    },
    "ecommerce-web": {
        "keywords": [
            "ecommerce",
            "e-commerce",
            "storefront",
            "shopping cart",
            "checkout",
            "products catalog",
            "store",
        ],
        "min_score": 0.85,
    },
    "saas-landing": {
        "keywords": ["landing page", "saas", "pricing page", "lead capture", "product page"],
        "min_score": 0.85,
    },
    "admin-dashboard": {
        "keywords": [
            "dashboard",
            "admin panel",
            "analytics dashboard",
            "control panel",
            "metrics view",
        ],
        "min_score": 0.85,
    },
    "fastapi-crud": {
        "keywords": [
            "rest api",
            "crud",
            "fastapi",
            "endpoints",
            "users api",
            "items api",
            "backend service",
        ],
        "min_score": 0.85,
    },
    "auth-service": {
        "keywords": [
            "auth",
            "jwt",
            "login",
            "authentication",
            "user registration",
            "oauth",
            "passwords",
        ],
        "min_score": 0.88,
    },
    "webhook-handler": {
        "keywords": ["webhook", "event receiver", "hmac", "ingestor", "payload receiver"],
        "min_score": 0.90,
    },
    "graphql-api": {
        "keywords": ["graphql", "strawberry", "resolvers", "schema query"],
        "min_score": 0.90,
    },
    "websocket-server": {
        "keywords": ["websocket", "realtime", "real-time", "broadcast", "chat server", "sockets"],
        "min_score": 0.88,
    },
    "cli-utility": {
        "keywords": ["cli", "command line", "terminal tool", "argparse", "console app"],
        "min_score": 0.88,
    },
    "scraper": {
        "keywords": ["scraper", "scrape", "crawl", "web crawler", "beautifulsoup"],
        "min_score": 0.88,
    },
    "data-processor": {
        "keywords": ["etl", "data processing", "csv processing", "pipeline", "batch transform"],
        "min_score": 0.85,
    },
    "npm-package": {
        "keywords": ["npm package", "npm library", "typescript package", "publish to npm"],
        "min_score": 0.90,
    },
    "python-package": {
        "keywords": ["python package", "pypi", "pyproject.toml", "python library"],
        "min_score": 0.90,
    },
}


class SmartTemplateMatcher:
    """Matches task goals against curated marketplace templates to guide hybrid synthesis."""

    @classmethod
    def match_goal(cls, goal: str, requirements: list[str] | None = None) -> TemplateMatchResult:
        combined_text = f"{goal} {' '.join(requirements or [])}".lower()

        best_template_id: str | None = None
        best_score = 0.0
        best_reason = "No matching template found; generating codebase from scratch."

        for t_id, rule in TEMPLATE_INTENT_RULES.items():
            matched_keywords = [
                kw
                for kw in rule["keywords"]
                if re.search(r"\b" + re.escape(kw) + r"\b", combined_text)
            ]
            if matched_keywords:
                # Score based on keyword count and specificity
                score = min(0.98, rule["min_score"] + (0.03 * (len(matched_keywords) - 1)))
                if score > best_score:
                    best_score = score
                    best_template_id = t_id
                    best_reason = f"Matched keywords: {', '.join(matched_keywords)} with {round(score * 100)}% confidence."

        if best_template_id and best_score >= 0.80:
            template = template_registry.get_template(best_template_id)
            template_name = template.name if template else best_template_id

            return TemplateMatchResult(
                matched_template_id=best_template_id,
                template_name=template_name,
                confidence=round(best_score, 2),
                reasoning=best_reason,
                use_hybrid_scaffold=True,
                customization_hints=[
                    f"Use '{template_name}' as architectural foundation.",
                    "Let AI reasoning persona customize business logic and domain fields to fulfill user requirements.",
                ],
            )

        return TemplateMatchResult(
            matched_template_id=None,
            template_name=None,
            confidence=round(best_score, 2),
            reasoning=best_reason,
            use_hybrid_scaffold=False,
            customization_hints=[
                "Generate all project files dynamically via standard AI synthesis pipeline."
            ],
        )
