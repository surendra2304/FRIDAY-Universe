"""
Template Engine for Project FORGE.
Provides variable interpolation and structured code synthesis from predefined component templates.
"""

import re
from typing import Any


class TemplateEngine:
    """Lightweight deterministic template renderer for code and component scaffolds."""

    VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\-]+)\s*\}\}")

    @classmethod
    def render(cls, template_text: str, context: dict[str, Any]) -> str:
        """Replace {{variable}} placeholders with values from context."""

        def replacer(match: re.Match) -> str:
            key = match.group(1).strip()
            val = context.get(key)
            if val is None:
                return f"{{{{ {key} }}}}"
            return str(val)

        return cls.VARIABLE_PATTERN.sub(replacer, template_text)
