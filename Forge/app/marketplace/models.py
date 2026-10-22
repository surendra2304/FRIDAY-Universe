"""
Marketplace and Template Data Models for Project FORGE.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class TemplateCategory(str, Enum):
    WEB_APPS = "web-apps"
    APIS = "apis"
    TOOLS = "tools"
    LIBRARIES = "libraries"


class TemplateVariable(BaseModel):
    name: str
    description: str
    default: str | None = None
    required: bool = True


class TemplateManifest(BaseModel):
    id: str
    name: str
    description: str
    category: TemplateCategory
    language: str  # python, javascript, typescript
    framework: str  # fastapi, express, react, nextjs, etc.
    author: str = "FORGE Curated"
    version: str = "1.0.0"
    downloads: int = 0
    rating: float = 5.0
    status: str = "published"  # published, pending, archived
    variables: list[TemplateVariable] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)  # rel_path -> template_content
    requirements: list[str] = Field(default_factory=list)
    readme_content: str = ""
    tests_content: dict[str, str] = Field(default_factory=dict)
    changelog: list[str] = Field(default_factory=lambda: ["1.0.0: Initial release"])
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class TemplateSubmission(BaseModel):
    name: str
    description: str
    category: TemplateCategory
    language: str
    framework: str
    author: str
    variables: list[TemplateVariable] = Field(default_factory=list)
    files: dict[str, str] = Field(default_factory=dict)
    requirements: list[str] = Field(default_factory=list)
    readme_content: str = ""
    tests_content: dict[str, str] = Field(default_factory=dict)
