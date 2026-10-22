"""
Template Engine and Catalog Subsystem for Project FORGE.
"""

from app.templates.catalog import (
    CSS_BASE,
    FASTAPI_APP_BASE,
    FASTAPI_TEST_BASE,
    HTML_WEBSITE_BASE,
    JS_BASE,
    PYTHON_CLI_BASE,
    PYTHON_CLI_TEST_BASE,
)
from app.templates.engine import TemplateEngine

__all__ = [
    "CSS_BASE",
    "FASTAPI_APP_BASE",
    "FASTAPI_TEST_BASE",
    "HTML_WEBSITE_BASE",
    "JS_BASE",
    "PYTHON_CLI_BASE",
    "PYTHON_CLI_TEST_BASE",
    "TemplateEngine",
]
