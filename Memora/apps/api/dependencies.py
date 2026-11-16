"""
FastAPI Dependencies for Memora API
"""
import hmac
import logging
import os
import re
from typing import Optional
from fastapi import Header, HTTPException, Request, status
from core.config import settings
from storage.relational.session import get_db  # noqa: F401 — re-exported dependency

logger = logging.getLogger(__name__)

AGENT_API_KEY_ENV_VARS = {
    "friday": "FRIDAY_API_KEY",
    "inference": "INFERENCE_API_KEY",
    "stratex": "STRATEX_API_KEY",
    "intelx": "INTELX_API_KEY",
    "futuris": "FUTURIS_API_KEY",
    "cortex": "CORTEX_API_KEY",
    "forge": "FORGE_API_KEY",
    "sentinel": "SENTINEL_API_KEY",
    "ai_universe": "AI_UNIVERSE_API_KEY",
    "vyralx": "VYRALX_API_KEY",
    "memora": "MEMORA_API_KEY",
}


# ---------------------------------------------------------------------------
# Scoped delegation (TASK-MEM-005-R1)
#
# A caller may act for another agent ONLY by authenticating as itself with
# its own per-agent key and naming the target in the X-On-Behalf-Of header.
# Memora then grants the request the target's identity for that one call iff
# the MEMORA_DELEGATIONS policy in Memora's own environment names the
# (caller, target, scope) triple. The scope is derived from the route and
# method; routes outside the map reject the header outright (default deny).
# This replaces the old design in which a delegate had to hold the target's
# raw key (FRIDAY's env carried every agent's key) or the fleet master key.
#
# Policy format (semicolon-separated grants):
#   MEMORA_DELEGATIONS="friday>stratex:read,learn;friday>intelx:read,learn"
# ---------------------------------------------------------------------------

DELEGATION_SCOPES = {"read", "learn", "write", "mutate", "events"}

_LEARN_SUFFIXES = ("/learn-outcome", "/learn-experience", "/record-interaction")
_MUTATE_SUFFIXES = (
    "/share",
    "/supersede",
    "/promote",
    "/verify",
    "/relationships",
    "/forget",
    "/transition",
)


def delegation_scope_for(method: str, path: str) -> Optional[str]:
    """Map a request to its delegation scope, or None if delegation is not
    available on that route at all (the header is then rejected, never
    silently ignored)."""
    method = (method or "").upper()
    path = (path or "").rstrip("/") or "/"

    if path.startswith("/v1/events"):
        return "events"
    if path == "/v1/context" and method == "POST":
        return "read"

    for prefix in ("/v1/memories", "/memories"):
        if path == prefix or path.startswith(prefix + "/"):
            rest = path[len(prefix):]
            if method == "POST" and rest in _LEARN_SUFFIXES:
                return "learn"
            if rest == "":
                if method == "GET":
                    return "read"
                if method == "POST":
                    return "write"
                return None
            if rest in ("/search", "/experience") and method == "GET":
                return "read"
            if rest == "/query" and method == "POST":
                return "read"
            if method == "POST" and any(
                rest.endswith(suffix) for suffix in _MUTATE_SUFFIXES
            ):
                return "mutate"
            if re.fullmatch(r"/[^/]+/graph", rest) and method == "GET":
                return "read"
            if re.fullmatch(r"/[^/]+", rest):
                if method == "GET":
                    return "read"
                if method == "DELETE":
                    return "mutate"
            return None
    return None


def delegation_grants() -> dict:
    """Parse MEMORA_DELEGATIONS into {(caller, target): {scope, ...}}.

    Read from the environment on every call so policy changes need no code
    deploy and tests can pin policy with monkeypatch. Malformed entries are
    skipped; an unset/empty policy grants nothing.
    """
    grants: dict = {}
    for entry in os.getenv("MEMORA_DELEGATIONS", "").split(";"):
        entry = entry.strip()
        if not entry:
            continue
        pair, _, scopes = entry.partition(":")
        caller, _, target = pair.partition(">")
        caller = caller.strip().lower()
        target = target.strip().lower()
        scope_set = {
            s.strip().lower() for s in scopes.split(",") if s.strip() in DELEGATION_SCOPES
        }
        if caller and target and scope_set:
            grants.setdefault((caller, target), set()).update(scope_set)
    return grants


def _apply_delegation(
    principal: str,
    via_master: bool,
    x_on_behalf_of: Optional[str],
    request: Optional[Request],
) -> str:
    """Resolve the effective actor for a request.

    Without X-On-Behalf-Of the authenticated principal acts for itself. With
    it, the principal must hold a policy grant for the target and for the
    scope of the route being called; every failure is a 403 (fail closed,
    never a silent fall-back to the caller's own identity, which would mask
    a misconfigured delegation as a successful self-call).
    """
    if not x_on_behalf_of:
        return principal
    target = x_on_behalf_of.strip().lower()
    if target == principal:
        return principal
    if via_master:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The master credential cannot delegate; authenticate with the caller's own per-agent key.",
        )
    if target not in AGENT_API_KEY_ENV_VARS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Unknown delegation target '{target}'.",
        )
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Delegation requires a request context to scope the grant.",
        )
    scope = delegation_scope_for(request.method, request.url.path)
    if scope is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Delegation is not available on this route.",
        )
    if scope not in delegation_grants().get((principal, target), set()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Agent '{principal}' holds no '{scope}' delegation for '{target}'.",
        )
    logger.info(
        "memora delegation: caller=%s target=%s scope=%s %s %s",
        principal,
        target,
        scope,
        request.method,
        request.url.path,
    )
    return target


def get_actor_header(
    request: Request,
    x_agent_name: Optional[str] = Header(default=None, alias="X-Agent-Name"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_on_behalf_of: Optional[str] = Header(default=None, alias="X-On-Behalf-Of"),
) -> str:
    """Return the authenticated agent identity, never an unverified header claim.

    With a granted X-On-Behalf-Of delegation this is the TARGET agent's
    identity; the caller was still authenticated with its own key.
    """
    return authenticate_agent(
        x_agent_name, x_api_key, authorization, x_on_behalf_of, request
    )

def get_purpose_header(
    x_access_purpose: Optional[str] = Header(default=None, alias="X-Access-Purpose")
) -> Optional[str]:
    """Extracts the stated purpose / intent for audit and policy verification."""
    return x_access_purpose


def resolve_agent_selector(
    db,
    authenticated_name: str,
    requested_name: Optional[str],
    *,
    allow_direct_subagent: bool = False,
) -> str:
    """Bind a body agent selector to the authenticated principal.

    Most routes must use the authenticated agent only. The context route is the
    one exception: a parent may build context for one of its registered direct
    children, but never for an unrelated agent. The child's bounded scope is then
    enforced by the normal policy-filtered retrieval path.
    """
    principal = (authenticated_name or "").strip().lower()
    requested = str(requested_name or "").strip()

    # Import locally to keep the HTTP dependency module lightweight and to avoid
    # making identity/model imports part of authentication's import cycle.
    from core.identity.service import IdentityService
    from storage.relational.models import Agent

    # API credentials do not yet carry a tenant claim. Resolve the credential's
    # own principal in the API-bound tenant even when the body omits an agent
    # selector; otherwise downstream services can resolve the same name globally
    # and bind the request to a same-named identity in a foreign tenant.
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="An authenticated agent identity is required.",
        )
    actor = IdentityService.get_agent_by_name(db, principal, tenant_id="default")
    if actor is None:
        # The credential has already authenticated the principal. Bootstrap only
        # that exact principal into the API-bound tenant rather than adopting a
        # same-named row from elsewhere. This also preserves the SDK's first-write
        # workflow while keeping tenant selection unambiguous.
        actor = IdentityService.register_agent(
            db, principal, role="worker", tenant_id="default"
        )

    if not requested or requested.lower() == principal:
        return actor.name

    if requested == actor.id:
        return actor.name

    candidate = db.query(Agent).filter(
        Agent.tenant_id == actor.tenant_id,
        Agent.id == requested,
    ).first()
    if candidate is None:
        candidate = db.query(Agent).filter(
            Agent.tenant_id == actor.tenant_id,
            Agent.name == requested.lower(),
        ).first()

    if (
        allow_direct_subagent
        and candidate is not None
        and candidate.parent_agent_id == actor.id
        and candidate.bounded_scope
    ):
        return candidate.name

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="The requested agent does not match the authenticated identity or an authorized direct sub-agent.",
    )


#: Agents permitted to perform fabric-wide administration.
#:
#: Identity registration is the root of every policy decision in Memora, and the
#: audit trail records every actor and denial reason across the mesh. Routers
#: that expose those were authenticated but not authorised, so any agent holding
#: a valid credential could mint a new identity — including one with
#: role="supervisor" — and read other agents' audit entries. Verifying against a
#: live server: intelx created agent 'rogue' with role=supervisor (HTTP 201) and
#: read the whole audit log (HTTP 200).
ADMIN_AGENTS = {"memora"}


def require_admin(actor_name: str) -> str:
    """Raise 403 unless the caller may administer the fabric."""
    if actor_name not in ADMIN_AGENTS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Agent '{actor_name}' may not perform fabric administration. "
                f"Restricted to: {', '.join(sorted(ADMIN_AGENTS))}."
            ),
        )
    return actor_name


def authenticate_agent(
    x_agent_name: Optional[str] = Header(default=None, alias="X-Agent-Name"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
    x_on_behalf_of: Optional[str] = Header(default=None, alias="X-On-Behalf-Of"),
    request: Request = None,
) -> str:
    """Authenticate an ecosystem agent using its named service credential.

    Returns the effective actor: the authenticated agent itself, or — with a
    granted X-On-Behalf-Of delegation (TASK-MEM-005-R1) — the delegation
    target. See _apply_delegation.
    """
    # Direct (non-FastAPI) callers — unit tests, scripts — invoke this
    # function without the framework, in which case an unpassed Header
    # parameter holds its FieldInfo default rather than a string. Normalize
    # so only a real header value can trigger delegation.
    if not isinstance(x_on_behalf_of, str):
        x_on_behalf_of = None
    agent = (x_agent_name or "").strip().lower()
    supplied = x_api_key
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    expected = os.getenv(AGENT_API_KEY_ENV_VARS.get(agent, ""), "")
    production = str(getattr(settings, "MEMORA_ENV", "")).lower() == "production" or os.getenv("ENVIRONMENT", "").lower() == "production"

    # Authentication fails closed. The previous guard waved through any request that
    # carried no credential at all whenever the service was not flagged production,
    # so a deployment whose ENVIRONMENT value drifted or was lost silently accepted
    # unauthenticated writes into the memory every other agent reads. Every other agent
    # in the mesh rejects a missing credential outright, so this one did not either.
    anonymous_allowed = str(os.getenv("MEMORA_ALLOW_ANONYMOUS_DEV", "")).lower() in {"1", "true", "yes"}

    if not anonymous_allowed:
        if not agent or not supplied:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing agent credentials",
            )
        if agent not in AGENT_API_KEY_ENV_VARS or not expected:
            # A known caller whose key is absent is a configuration fault, not a
            # bad credential. Report it as such rather than as an authentication failure.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"No configured credential for agent '{agent or 'unknown'}'",
            )
        # TASK-MEM-005-R1: the master is MEMORA_MASTER_KEY ONLY. The previous
        # fallback made MEMORA_API_KEY — the memora identity's own per-agent
        # key, copied into every agent's env file — a universal impersonation
        # credential (audit finding F1). MEMORA_API_KEY now authenticates the
        # memora identity alone, like every other per-agent key.
        master_key = os.getenv("MEMORA_MASTER_KEY")
        if master_key and hmac.compare_digest(master_key, supplied):
            return _apply_delegation(agent or "friday", True, x_on_behalf_of, request)
        if not hmac.compare_digest(expected, supplied):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent credentials")
        return _apply_delegation(agent, False, x_on_behalf_of, request)

    # Opt-in anonymous access exists only for local development and tests.
    if not production and not supplied:
        return _apply_delegation(agent or "friday", False, x_on_behalf_of, request)
    if not agent or not expected or not supplied or not hmac.compare_digest(expected, supplied):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid agent credentials")
    return _apply_delegation(agent, False, x_on_behalf_of, request)
