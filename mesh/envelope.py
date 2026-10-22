"""Standard JSON message envelope for the FRIDAY Universe mesh.
Includes HMAC authentication, priority queuing, and correlation tracing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Optional


class MessagePriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    CRITICAL = "critical"


@dataclass
class AgentEnvelope:
    message_id: str = field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:12]}")
    correlation_id: str = field(default_factory=lambda: f"corr_{uuid.uuid4().hex[:8]}")
    from_agent: str = ""
    to_agent: str = ""
    intent: str = ""
    priority: str = MessagePriority.NORMAL
    ttl: int = 300  # seconds
    auth_token: Optional[str] = None
    signature: Optional[str] = None
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())

    def _signature_bytes(self) -> bytes:
        """Canonicalize every field that changes routing or handling semantics."""
        signed_fields = {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "intent": self.intent,
            "priority": self.priority,
            "ttl": self.ttl,
            "auth_token": self.auth_token,
            "payload": self.payload,
            "created_at": self.created_at,
        }
        return json.dumps(
            signed_fields, sort_keys=True, separators=(",", ":"), default=str
        ).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)

    def sign(self, secret_key: str) -> str:
        """Sign envelope payload with HMAC-SHA256."""
        sig = hmac.new(secret_key.encode("utf-8"), self._signature_bytes(), hashlib.sha256).hexdigest()
        self.signature = sig
        return sig

    def verify_signature(self, secret_key: str) -> bool:
        """Verify envelope HMAC-SHA256 signature."""
        if not self.signature:
            return False
        expected_sig = hmac.new(secret_key.encode("utf-8"), self._signature_bytes(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(self.signature, expected_sig)

    @classmethod
    def from_json(cls, raw: str) -> "AgentEnvelope":
        data = json.loads(raw)
        return cls(
            message_id=data.get("message_id", f"msg_{uuid.uuid4().hex[:12]}"),
            correlation_id=data.get("correlation_id", f"corr_{uuid.uuid4().hex[:8]}"),
            from_agent=data.get("from_agent", ""),
            to_agent=data.get("to_agent", ""),
            intent=data.get("intent", ""),
            priority=data.get("priority", MessagePriority.NORMAL),
            ttl=data.get("ttl", 300),
            auth_token=data.get("auth_token"),
            signature=data.get("signature"),
            payload=data.get("payload", {}),
            created_at=data.get("created_at", time.time()),
        )


class EnvelopeError(Exception):
    pass


def build_envelope(
    from_agent: str,
    to_agent: str,
    intent: str,
    payload: dict,
    priority: str = MessagePriority.NORMAL,
    ttl: int = 300,
    auth_token: Optional[str] = None,
    secret_key: Optional[str] = None,
    auth_secret: Optional[str] = None,
) -> AgentEnvelope:
    key = auth_secret or secret_key
    env = AgentEnvelope(
        from_agent=from_agent,
        to_agent=to_agent,
        intent=intent,
        payload=payload,
        priority=priority,
        ttl=ttl,
        auth_token=auth_token,
    )
    if key:
        env.sign(key)
    return env


def validate_envelope(data: dict) -> tuple[bool, str]:
    required = ["message_id", "correlation_id", "from_agent", "to_agent", "intent", "priority", "ttl", "payload"]
    for key in required:
        if key not in data:
            return False, f"Missing required field: {key}"
    if not isinstance(data.get("payload"), dict):
        return False, "Payload must be a JSON object"
    if not isinstance(data.get("ttl"), (int, float)) or data.get("ttl") <= 0:
        return False, "TTL must be a positive number"
    return True, ""
