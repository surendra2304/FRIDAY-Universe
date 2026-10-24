"""
mesh/unified_errors.py — FRIDAY Universe Unified Error Handling.

Provides consistent error envelopes across all 10 agents. Ensures
every API returns the same error format so agents can parse failures
reliably.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter, HTTPException

router = APIRouter()


@dataclass
class ErrorEnvelope:
    """Standardized error envelope."""
    status: str = "error"
    code: str = ""
    message: str = ""
    details: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            },
            "metadata": self.metadata,
        }


@dataclass
class SuccessEnvelope:
    """Standardized success envelope."""
    status: str = "success"
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "data": self.data,
            "metadata": self.metadata,
        }


@dataclass
class ErrorCatalog:
    """Error code catalog."""
    errors: dict[str, dict] = field(default_factory=dict)

    def register(
        self,
        code: str,
        message: str,
        severity: str = "error",
        http_status: int = 500,
        description: str = "",
    ) -> None:
        self.errors[code] = {
            "message": message,
            "severity": severity,
            "http_status": http_status,
            "description": description,
        }

    def get(self, code: str) -> dict:
        return self.errors.get(code, {
            "message": f"Unknown error: {code}",
            "severity": "error",
            "http_status": 500,
            "description": "",
        })


@dataclass
class ErrorLog:
    """An error log entry."""
    error_id: str
    agent: str
    code: str
    message: str
    details: dict
    timestamp: float
    severity: str
    http_status: int


class UnifiedErrorHandler:
    """Unified error handling engine."""

    def __init__(self):
        self.catalog = ErrorCatalog()
        self._logs: list[ErrorLog] = []
        self._stats: dict[str, int] = {}

        # Register standard error codes
        self._register_standard_errors()

    def _register_standard_errors(self) -> None:
        """Register the standard error catalog."""
        errors = {
            # Authentication & Authorization
            "AUTH_INVALID_KEY": ("Invalid or missing API key", "error", 401,
                                 "The provided API key is invalid or missing"),
            "AUTH_INSUFFICIENT_PERMISSIONS": ("Insufficient permissions", "error", 403,
                                              "The agent lacks permission for this action"),
            "AUTH_TOKEN_EXPIRED": ("Authentication token expired", "error", 401,
                                   "The authentication token has expired"),

            # Resource errors
            "RESOURCE_NOT_FOUND": ("Resource not found", "error", 404,
                                   "The requested resource does not exist"),
            "RESOURCE_ALREADY_EXISTS": ("Resource already exists", "error", 409,
                                        "The resource already exists"),
            "RESOURCE_CONFLICT": ("Resource conflict", "error", 409,
                                  "The operation conflicts with current resource state"),

            # Validation errors
            "VALIDATION_ERROR": ("Validation error", "error", 422,
                                 "The input data failed validation"),
            "VALIDATION_MISSING_FIELD": ("Missing required field", "error", 422,
                                         "A required field is missing from the input"),
            "VALIDATION_INVALID_VALUE": ("Invalid value", "error", 422,
                                         "A field contains an invalid value"),

            # Service errors
            "SERVICE_UNAVAILABLE": ("Service unavailable", "error", 503,
                                   "The service is currently unavailable"),
            "SERVICE_TIMEOUT": ("Service timeout", "error", 504,
                                "The service timed out"),
            "SERVICE_DEGRADED": ("Service degraded", "warning", 503,
                                 "The service is running but degraded"),
            "SERVICE_RATE_LIMITED": ("Rate limited", "error", 429,
                                     "Too many requests to this service"),

            # Mesh errors
            "MESH_AGENT_OFFLINE": ("Agent offline", "error", 503,
                                   "The target agent is offline"),
            "MESH_AGENT_UNREACHABLE": ("Agent unreachable", "error", 503,
                                       "The target agent cannot be reached"),
            "MESH_COMMUNICATION_FAILED": ("Mesh communication failed", "error", 502,
                                          "Failed to communicate with another agent"),
            "MESH_ROUTING_FAILED": ("Routing failed", "error", 503,
                                    "No available agent found to handle the task"),

            # Task errors
            "TASK_FAILED": ("Task failed", "error", 500,
                            "The task execution failed"),
            "TASK_TIMEOUT": ("Task timed out", "error", 504,
                             "The task exceeded its time limit"),
            "TASK_CANCELLED": ("Task cancelled", "error", 499,
                               "The task was cancelled"),
            "TASK_ALREADY_RUNNING": ("Task already running", "error", 409,
                                     "The task is already running"),

            # Trading errors (Stratex)
            "TRADE_REJECTED": ("Trade rejected", "error", 400,
                               "The exchange rejected the trade order"),
            "TRADE_RISK_LIMIT": ("Risk limit exceeded", "error", 403,
                                 "The trade violates a risk management limit"),
            "TRADE_INSUFFICIENT_FUNDS": ("Insufficient funds", "error", 400,
                                         "The account lacks sufficient funds for the trade"),

            # Memory errors (Memora)
            "MEMORY_SCOPE_DENIED": ("Memory scope denied", "error", 403,
                                    "The agent does not have access to this memory scope"),
            "MEMORY_NOT_FOUND": ("Memory not found", "error", 404,
                                 "The requested memory does not exist"),
            "MEMORY_DUPLICATE": ("Duplicate memory", "error", 409,
                                 "A memory with identical content already exists"),

            # Forge errors
            "SANDBOX_VIOLATION": ("Sandbox violation", "error", 403,
                                  "The code attempted to access outside its sandbox"),
            "BUILD_FAILED": ("Build failed", "error", 500,
                             "The code build failed"),
            "TEST_FAILED": ("Tests failed", "error", 500,
                            "The test suite did not pass"),

            # Security errors (Sentinel)
            "SECURITY_VIOLATION": ("Security violation", "error", 403,
                                   "The operation violates security policies"),
            "SECURITY_SCAN_FAILED": ("Security scan failed", "error", 500,
                                     "The security scan could not be completed"),
            "VULNERABILITY_DETECTED": ("Vulnerability detected", "error", 403,
                                       "A security vulnerability was detected"),

            # Internal errors
            "INTERNAL_ERROR": ("Internal server error", "error", 500,
                               "An unexpected internal error occurred"),
            "DATABASE_ERROR": ("Database error", "error", 500,
                               "A database operation failed"),
            "CONFIGURATION_ERROR": ("Configuration error", "error", 500,
                                    "The system configuration is invalid"),
        }

        for code, (msg, severity, http_status, desc) in errors.items():
            self.catalog.register(code, msg, severity, http_status, desc)

    def create_error(
        self,
        agent: str,
        code: str,
        details: dict | None = None,
        metadata: dict | None = None,
    ) -> ErrorEnvelope:
        """Create a standardized error envelope."""
        info = self.catalog.get(code)

        error_id = hashlib.md5(
            f"error:{agent}:{code}:{time.time()}".encode()
        ).hexdigest()[:12]

        log = ErrorLog(
            error_id=error_id,
            agent=agent,
            code=code,
            message=info["message"],
            details=details or {},
            timestamp=time.time(),
            severity=info["severity"],
            http_status=info["http_status"],
        )

        self._logs.append(log)
        self._stats[code] = self._stats.get(code, 0) + 1

        envelope = ErrorEnvelope(
            status="error",
            code=code,
            message=info["message"],
            details=details or {},
            metadata={
                "agent": agent,
                "error_id": error_id,
                "timestamp": time.time(),
                **(metadata or {}),
            },
        )

        return envelope

    def create_success(
        self,
        data: dict,
        metadata: dict | None = None,
    ) -> SuccessEnvelope:
        """Create a standardized success envelope."""
        return SuccessEnvelope(
            status="success",
            data=data,
            metadata=metadata or {},
        )

    def get_error_logs(self, limit: int = 50, agent: str | None = None) -> list[ErrorLog]:
        """Get error logs."""
        logs = self._logs
        if agent:
            logs = [l for l in logs if l.agent == agent]
        return sorted(logs, key=lambda l: -l.timestamp)[:limit]

    def get_error_stats(self) -> dict:
        """Get error statistics."""
        return {
            "total_errors": len(self._logs),
            "error_breakdown": self._stats,
            "top_errors": sorted(
                self._stats.items(),
                key=lambda x: -x[1]
            )[:10],
        }

    def get_error_catalog(self) -> dict:
        """Get the full error catalog."""
        return {
            code: info for code, info in self.catalog.errors.items()
        }


# Module-level singleton
unified_errors = UnifiedErrorHandler()


# ── API Routes ──────────────────────────────────────────────────────────────


@router.get("/api/v1/mesh/errors/catalog")
async def get_error_catalog():
    """Get error catalog."""
    return unified_errors.get_error_catalog()


@router.get("/api/v1/mesh/errors/logs")
async def get_error_logs(limit: int = 50, agent: str = ""):
    """Get error logs."""
    logs = unified_errors.get_error_logs(limit, agent or None)
    return [l.__dict__ for l in logs]


@router.get("/api/v1/mesh/errors/stats")
async def get_error_stats():
    """Get error statistics."""
    return unified_errors.get_error_stats()


@router.post("/api/v1/mesh/errors/test")
async def test_error(payload: dict):
    """Create a test error envelope."""
    envelope = unified_errors.create_error(
        agent=payload.get("agent", "unknown"),
        code=payload.get("code", "INTERNAL_ERROR"),
        details=payload.get("details", {}),
    )
    return envelope.to_dict()
