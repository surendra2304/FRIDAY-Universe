"""
FORGE Application Configuration using Pydantic Settings.
"""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Information
    app_name: str = Field(default="Project FORGE", description="Application display name")
    app_version: str = Field(default="2.0.0", description="Application semantic version")
    debug: bool = Field(default=True, description="Enable debug mode")
    # Keep this in lockstep with app.config.production.ProductionSettings.env,
    # which reads FORGE_ENV and defaults to "development". Defaulting here to
    # "production" while the production config said "development" made the two
    # settings disagree about whether authentication was required.
    env: str = Field(
        default_factory=lambda: os.getenv("FORGE_ENV", "development").lower(),
        description="Environment stage",
    )

    # Network & Server
    host: str = Field(default="0.0.0.0", description="Server bind host")
    port: int = Field(
        default=8000,
        validation_alias=AliasChoices("PORT", "FORGE_PORT", "port"),
        description="Server port",
    )

    # Filesystem Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    data_dir: Path = Field(default_factory=lambda: Path("data"))
    database_path: Path = Field(default_factory=lambda: Path("data/forge.db"))
    workspaces_dir: Path = Field(default_factory=lambda: Path("workspaces"))
    artifacts_dir: Path = Field(default_factory=lambda: Path("artifacts"))

    # Provider Defaults
    default_provider: str = Field(
        default="direct",
        validation_alias=AliasChoices(
            "DEFAULT_PROVIDER", "FORGE_DEFAULT_PROVIDER", "default_provider"
        ),
        description="Default model provider: openai, anthropic, direct, or mock",
    )
    default_model: str = Field(
        default="direct-default",
        validation_alias=AliasChoices("DEFAULT_MODEL", "FORGE_DEFAULT_MODEL", "default_model"),
        description="Default model identifier",
    )
    model_temperature: float = Field(
        default=0.2,
        validation_alias=AliasChoices(
            "MODEL_TEMPERATURE", "FORGE_MODEL_TEMPERATURE", "model_temperature"
        ),
        description="Default generation temperature",
    )

    # API Keys (Optional)
    openai_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
        description="OpenAI API Key",
    )
    openai_default_model: str = Field(
        default="gpt-4o",
        validation_alias=AliasChoices("OPENAI_DEFAULT_MODEL", "openai_default_model"),
        description="Default OpenAI model",
    )
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "anthropic_api_key"),
        description="Anthropic API Key",
    )
    anthropic_default_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        validation_alias=AliasChoices("ANTHROPIC_DEFAULT_MODEL", "anthropic_default_model"),
        description="Default Anthropic model",
    )
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GEMINI_API_KEY", "gemini_api_key"),
        description="Gemini API Key",
    )
    github_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_TOKEN", "github_token"),
        description="GitHub Personal Access Token or App Token for pushing and PR creation",
    )
    github_repo: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GITHUB_REPO", "github_repo"),
        description="Default GitHub repository (e.g. owner/repo)",
    )
    ai_universe_url: str = Field(
        default="http://inference:8000",
        validation_alias=AliasChoices("INFERENCE_URL", "AI_UNIVERSE_URL", "ai_universe_url"),
        description="Base URL for external Inference / AI Universe reasoning engine",
    )
    ai_universe_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "INFERENCE_API_KEY", "AI_UNIVERSE_API_KEY", "ai_universe_api_key"
        ),
        description="API Key for Inference REST API authentication",
    )
    intelx_url: str = Field(
        default="http://intelx:8000",
        validation_alias=AliasChoices("INTELX_URL", "FORGE_INTELX_URL", "intelx_url"),
        description="Base URL for IntelX technical research intelligence service",
    )
    intelx_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INTELX_API_KEY", "FORGE_INTELX_API_KEY", "intelx_api_key"),
        description="API Key for IntelX Technical Research API authentication",
    )
    futuris_url: str = Field(
        default="http://futuris:8000",
        validation_alias=AliasChoices("FUTURIS_URL", "FORGE_FUTURIS_URL", "futuris_url"),
        description="Base URL for Futuris predictive capacity & success intelligence service",
    )
    futuris_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "FUTURIS_API_KEY", "FORGE_FUTURIS_API_KEY", "futuris_api_key"
        ),
        description="API Key for Futuris API authentication",
    )
    cortex_url: str = Field(
        default="http://cortex:8000",
        validation_alias=AliasChoices("CORTEX_URL", "NEXUS_URL", "cortex_url"),
        description="Base URL for Cortex Web Operations engine",
    )
    cortex_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CORTEX_API_KEY", "NEXUS_API_KEY", "cortex_api_key"),
        description="API Key for Cortex API authentication",
    )
    memora_url: str = Field(
        default="http://memora:8000",
        validation_alias=AliasChoices("MEMORA_URL", "FORGE_MEMORA_URL", "memora_url"),
        description="Base URL for Memora persistent memory fabric",
    )
    memora_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FORGE_API_KEY", "FORGE_MEMORA_API_KEY", "MEMORA_API_KEY", "memora_api_key"),
        description="Forge's named agent credential for Memora Cloud",
    )
    sentinel_url: str = Field(
        default="http://sentinel:8000",
        validation_alias=AliasChoices("SENTINEL_URL", "FORGE_SENTINEL_URL", "sentinel_url"),
        description="Base URL for Sentinel security audit and vulnerability analysis gate",
    )
    sentinel_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SENTINEL_API_KEY", "FORGE_SENTINEL_API_KEY", "sentinel_api_key"),
        description="API Key for Sentinel API authentication",
    )
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DATABASE_URL", "FORGE_DATABASE_URL", "database_url"),
        description="Explicit database connection URL (e.g. postgresql+asyncpg://... or sqlite+aiosqlite://...)",
    )
    postgres_host: str = Field(
        default="dokploy-postgres",
        validation_alias=AliasChoices("POSTGRES_HOST", "FORGE_POSTGRES_HOST", "postgres_host"),
        description="PostgreSQL hostname within the mesh",
    )
    postgres_port: int = Field(
        default=5432,
        validation_alias=AliasChoices("POSTGRES_PORT", "FORGE_POSTGRES_PORT", "postgres_port"),
        description="PostgreSQL port",
    )
    postgres_user: str = Field(
        default="forge_user",
        validation_alias=AliasChoices("POSTGRES_USER", "FORGE_POSTGRES_USER", "postgres_user"),
        description="PostgreSQL username",
    )
    postgres_password: str = Field(
        default="Rk5fcxK4A-V2i11aBnbvHOMT",
        validation_alias=AliasChoices("POSTGRES_PASSWORD", "FORGE_POSTGRES_PASSWORD", "postgres_password"),
        description="PostgreSQL password",
    )
    postgres_db: str = Field(
        default="forge_db",
        validation_alias=AliasChoices("POSTGRES_DB", "FORGE_POSTGRES_DB", "postgres_db"),
        description="PostgreSQL database name",
    )
    git_push_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FORGE_GIT_PUSH_TOKEN", "git_push_token"),
        description=(
            "Elevated token that may stand in for explicit git-push authorization. "
            "When unset, no presented token can satisfy the push gate."
        ),
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    def get_database_url(self) -> str:
        """Return the effective database URL (PostgreSQL asyncpg or SQLite aiosqlite)."""
        if self.database_url:
            return self.database_url
        if os.getenv("FORGE_USE_POSTGRES", "0").lower() in ("1", "true", "yes"):
            return (
                f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@"
                f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
            )
        abs_sqlite = self.base_dir / self.database_path if not self.database_path.is_absolute() else self.database_path
        path_str = str(abs_sqlite).replace("\\", "/")
        return f"sqlite+aiosqlite:///{path_str}"

    def ensure_directories(self) -> None:
        """Create runtime directories if they do not exist."""
        for path in [
            self.data_dir,
            self.database_path.parent,
            self.workspaces_dir,
            self.artifacts_dir,
        ]:
            abs_path = self.base_dir / path if not path.is_absolute() else path
            abs_path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    settings = Settings()
    settings.ensure_directories()
    return settings
