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
    friday_url: str = Field(
        default="http://10.0.0.121:10000",
        validation_alias=AliasChoices("FRIDAY_URL", "FORGE_FRIDAY_URL", "friday_url"),
        description="Base URL for FRIDAY central orchestrator and action gateway",
    )
    friday_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FRIDAY_API_KEY", "FORGE_FRIDAY_API_KEY", "friday_api_key"),
        description="API Key for FRIDAY API authentication",
    )
    ai_universe_url: str = Field(
        default="http://10.0.0.121:8001",
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
        default="http://10.0.0.121:8005",
        validation_alias=AliasChoices("INTELX_URL", "FORGE_INTELX_URL", "intelx_url"),
        description="Base URL for IntelX technical research intelligence service",
    )
    intelx_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("INTELX_API_KEY", "FORGE_INTELX_API_KEY", "intelx_api_key"),
        description="API Key for IntelX Technical Research API authentication",
    )
    futuris_url: str = Field(
        default="http://10.0.0.121:8004",
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
    stratex_url: str = Field(
        default="http://10.0.0.121:8003",
        validation_alias=AliasChoices("STRATEX_URL", "FORGE_STRATEX_URL", "stratex_url"),
        description="Base URL for Stratex quantitative algorithmic trading and risk desk",
    )
    stratex_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("STRATEX_API_KEY", "FORGE_STRATEX_API_KEY", "stratex_api_key"),
        description="API Key for Stratex API authentication",
    )
    cortex_url: str = Field(
        default="http://10.0.0.120:8009",
        validation_alias=AliasChoices("CORTEX_URL", "NEXUS_URL", "cortex_url"),
        description="Base URL for Cortex Web Operations engine",
    )
    cortex_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CORTEX_API_KEY", "NEXUS_API_KEY", "cortex_api_key"),
        description="API Key for Cortex API authentication",
    )
    memora_url: str = Field(
        default="http://10.0.0.121:8002",
        validation_alias=AliasChoices("MEMORA_URL", "FORGE_MEMORA_URL", "memora_url"),
        description="Base URL for Memora persistent memory fabric",
    )
    memora_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FORGE_API_KEY", "FORGE_MEMORA_API_KEY", "MEMORA_API_KEY", "memora_api_key"),
        description="Forge's named agent credential for Memora Cloud",
    )
    sentinel_url: str = Field(
        default="http://10.0.0.120:8008",
        validation_alias=AliasChoices("SENTINEL_URL", "FORGE_SENTINEL_URL", "sentinel_url"),
        description="Base URL for Sentinel security audit and vulnerability analysis gate",
    )
    sentinel_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SENTINEL_API_KEY", "FORGE_SENTINEL_API_KEY", "sentinel_api_key"),
        description="API Key for Sentinel API authentication",
    )
    vyralx_url: str = Field(
        default="http://10.0.0.120:8010",
        validation_alias=AliasChoices("VYRALX_URL", "FORGE_VYRALX_URL", "vyralx_url"),
        description="Base URL for VyralX video production studio",
    )
    vyralx_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("VYRALX_API_KEY", "FORGE_VYRALX_API_KEY", "vyralx_api_key"),
        description="API Key for VyralX API authentication",
    )
    database_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "DATABASE_URL",
            "ORACLE_CORE_ASYNC_URL",
            "ORACLE_CORE_URL",
            "FORGE_DATABASE_URL",
            "database_url",
        ),
        description="Explicit database connection URL (e.g. oracle+oracledb_async://..., postgresql+asyncpg://..., or sqlite+aiosqlite://...)",
    )
    postgres_host: str = Field(
        default="",
        validation_alias=AliasChoices("POSTGRES_HOST", "FORGE_POSTGRES_HOST", "postgres_host"),
        description="Legacy PostgreSQL hostname; PostgreSQL is not a supported backend.",
    )
    postgres_port: int = Field(
        default=0,
        validation_alias=AliasChoices("POSTGRES_PORT", "FORGE_POSTGRES_PORT", "postgres_port"),
        description="Legacy PostgreSQL port; PostgreSQL is not a supported backend.",
    )
    postgres_user: str = Field(
        default="",
        validation_alias=AliasChoices("POSTGRES_USER", "FORGE_POSTGRES_USER", "postgres_user"),
        description="Legacy PostgreSQL username; PostgreSQL is not a supported backend.",
    )
    postgres_password: str = Field(
        default="",
        validation_alias=AliasChoices("POSTGRES_PASSWORD", "FORGE_POSTGRES_PASSWORD", "postgres_password"),
        description="Legacy PostgreSQL password; PostgreSQL is not a supported backend.",
    )
    postgres_db: str = Field(
        default="",
        validation_alias=AliasChoices("POSTGRES_DB", "FORGE_POSTGRES_DB", "postgres_db"),
        description="Legacy PostgreSQL database name; PostgreSQL is not a supported backend.",
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
        """Return the configured database URL, failing closed when unset.

        Oracle Autonomous Database is the only supported backend. There is no
        PostgreSQL or SQLite fallback: an unset ``FORGE_DATABASE_URL`` /
        ``DATABASE_URL`` is a deployment error, not a reason to create a local
        file.
        """
        if self.database_url:
            return self.database_url
        raise RuntimeError(
            "No database URL configured. Set FORGE_DATABASE_URL or DATABASE_URL to an "
            "Oracle Autonomous Database DSN (oracle+oracledb://USER:<password>@...). "
            "PostgreSQL and SQLite are not supported backends."
        )

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
