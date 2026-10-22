"""
API Key Authentication, Token Verification, Sliding Window Rate Limiting, and Burst Control for Project FORGE.
"""

import time
from collections import defaultdict

from fastapi import Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config.production import production_settings
from app.core.logging import get_logger

logger = get_logger("security.api_keys")

bearer_scheme = HTTPBearer(auto_error=False)


class RateLimiter:
    """Sliding-window request rate limiter per client/API key with short-term burst allowance."""

    def __init__(self, limit_per_hour: int = 100, burst_limit_per_minute: int = 10):
        self.limit_per_hour = limit_per_hour
        self.burst_limit_per_minute = burst_limit_per_minute
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.failed_attempts: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, identifier: str) -> bool:
        """Check if client identifier is within hourly and burst request thresholds."""
        if not production_settings.rate_limit_enabled:
            return True

        now = time.time()
        hour_window = now - 3600.0
        minute_window = now - 60.0

        # Purge timestamps outside the 1-hour window
        self.requests[identifier] = [ts for ts in self.requests[identifier] if ts > hour_window]

        # Check hourly limit
        if len(self.requests[identifier]) >= self.limit_per_hour:
            return False

        # Check 60-second burst limit
        recent_minute_reqs = [ts for ts in self.requests[identifier] if ts > minute_window]
        if len(recent_minute_reqs) >= self.burst_limit_per_minute:
            return False

        self.requests[identifier].append(now)
        return True

    def record_failed_auth(self, ip_address: str) -> bool:
        """Record failed auth attempt and return True if under lockout threshold."""
        now = time.time()
        window = now - 60.0
        self.failed_attempts[ip_address] = [
            ts for ts in self.failed_attempts[ip_address] if ts > window
        ]
        self.failed_attempts[ip_address].append(now)
        return len(self.failed_attempts[ip_address]) <= 10

    def get_remaining(self, identifier: str) -> int:
        """Get remaining allowed requests in current 1-hour window."""
        now = time.time()
        hour_window = now - 3600.0
        active_reqs = [ts for ts in self.requests[identifier] if ts > hour_window]
        return max(0, self.limit_per_hour - len(active_reqs))


rate_limiter = RateLimiter(limit_per_hour=production_settings.default_rate_limit)


class APIKeyManager:
    """Validates API credentials and manages key rotations."""

    def __init__(self):
        self.valid_keys: set[str] = set()
        self._sync_keys()

    def _sync_keys(self):
        if production_settings.forge_api_key:
            self.valid_keys.add(production_settings.forge_api_key)

    def add_key(self, key: str):
        self.valid_keys.add(key)

    def revoke_key(self, key: str):
        self.valid_keys.discard(key)

    def rotate_key(self, old_key: str, new_key: str):
        self.revoke_key(old_key)
        self.add_key(new_key)

    def validate_key(self, key: str | None) -> bool:
        if self.valid_keys:
            return key in self.valid_keys
        if not production_settings.api_key_required:
            # If no API key requirement is configured and no specific keys loaded, allow request
            return True
        return False


api_key_manager = APIKeyManager()


async def verify_api_key(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    bearer_auth: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> str:
    """
    FastAPI security dependency validating incoming API key and enforcing rate limits.
    Accepts credentials via X-API-Key header or Bearer authorization.
    """
    key = x_api_key or (bearer_auth.credentials if bearer_auth else None)
    client_ip = request.client.host if request.client else "anonymous"

    # Validate FIRST, then account for failures. The old order recorded a failed
    # attempt before the key was even checked, so every client -- including
    # correctly authenticated ones -- was locked out with 429 after 10 requests
    # per minute.
    authenticated = api_key_manager.validate_key(key)
    if not authenticated:
        logger.warning(f"Unauthorized API request attempt from {client_ip}")
        # Check for excessive failed auth attempts from client IP
        if not rate_limiter.record_failed_auth(client_ip):
            logger.warning(
                f"Excessive failed authentication attempts from {client_ip}. Temporarily rate-limited."
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed authentication attempts. Please retry later.",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Provide X-API-Key header or Bearer token.",
        )

    # Rate limiting per API key/client identifier
    client_id = key or client_ip
    if not rate_limiter.is_allowed(client_id):
        logger.warning(f"Rate limit exceeded for client '{client_id[:8]}...'")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 100 requests per hour with burst limits applied.",
        )

    return client_id
