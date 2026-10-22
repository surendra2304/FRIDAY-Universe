"""
Production Configuration for Project FORGE.
Defines environment-aware runtime settings, rate limit thresholds, and security hardening rules.
"""

import os
import secrets
from enum import Enum

from pydantic import BaseModel, Field


class EnvironmentType(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ProductionSettings(BaseModel):
    """Production-grade security, logging, and operational configuration."""

    env: EnvironmentType = Field(
        default_factory=lambda: EnvironmentType(os.getenv("FORGE_ENV", "development").lower())
    )
    log_level: str = Field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper())
    metrics_enabled: bool = Field(default=True)
    slow_query_threshold_seconds: float = Field(default=1.0)

    # Rate Limiting
    #
    # This used to be a hardcoded `default=True` with no environment-variable
    # binding at all (unlike every other security toggle in this class), and
    # -- more importantly -- the `RateLimiter`/`verify_api_key` machinery in
    # app/security/api_keys.py that reads this flag was never actually wired
    # into any route or middleware. The net effect: rate limiting was
    # entirely dead code, regardless of this setting's value. Both problems
    # are fixed together: this field now follows the same
    # explicit-env-var-overrides-a-production-aware-default pattern as
    # `api_key_required` below, and `app/main.py` now has a real middleware
    # that enforces it.
    rate_limit_enabled: bool = Field(
        default_factory=lambda: (
            os.getenv("RATE_LIMIT_ENABLED", "").lower() in ["true", "1", "yes"]
            if os.getenv("RATE_LIMIT_ENABLED") is not None
            else os.getenv("FORGE_ENV", "development").lower() == "production"
        )
    )
    default_rate_limit: int = Field(
        default_factory=lambda: int(os.getenv("DEFAULT_RATE_LIMIT", "100"))
    )  # requests per hour

    # API Security
    api_key_required: bool = Field(
        default_factory=lambda: (
            os.getenv("API_KEY_REQUIRED", "").lower() in ["true", "1", "yes"]
            if os.getenv("API_KEY_REQUIRED") is not None
            else os.getenv("FORGE_ENV", "development").lower() == "production"
        )
    )
    forge_api_key: str | None = Field(default_factory=lambda: os.getenv("FORGE_API_KEY"))
    # The calling agent's credential. The mesh authenticates every caller against its
    # own <AGENT>_API_KEY, so Forge must know FRIDAY's key to accept a delegation.
    friday_api_key: str | None = Field(default_factory=lambda: os.getenv("FRIDAY_API_KEY"))
    secret_key: str = Field(
        default_factory=lambda: os.getenv("FORGE_SECRET_KEY", secrets.token_hex(32))
    )

    # Network
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv(
                "CORS_ORIGINS",
                "https://friday-universe.duckdns.org,http://localhost:8000,http://127.0.0.1:8000,http://localhost:8002,http://localhost:3000",
            ).split(",")
            if o.strip()
        ]
    )

    # Hardening
    secure_cookies: bool = True
    csrf_protection: bool = True
    sql_injection_protection: bool = True


production_settings = ProductionSettings()
