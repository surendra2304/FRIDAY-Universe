# FRIDAY Engineering Bridge Authentication

## Scope

The bridge is exposed through public ingress and currently has no request authentication. This change introduces a fail-closed ASGI middleware using one runtime-provided shared secret.

- Header: `X-FRIDAY-BRIDGE-KEY`
- Runtime variable: `FRIDAY_BRIDGE_SHARED_SECRET`
- Protected paths: `/`, `/bridge/**`, `/mcp/**`, `/messages/**`, and `/sse/**`
- `GET /health` remains public for liveness monitoring.
- CORS `OPTIONS` preflight requests pass through to CORS middleware.
- Missing runtime configuration returns HTTP 503; missing or incorrect credentials return HTTP 401.
- Secret comparison uses `hmac.compare_digest`.

## Runtime activation is a separate owner-approved operation

The source module and integration patch do not change the running service by themselves. Before activating the guard on Server 2:

1. Create a high-entropy shared secret outside GitHub and ChatGPT.
2. Provision it to the `friday-bridge.service` process through the approved secret manager (prefer an OCI Vault-backed environment injection).
3. Confirm the unit receives `FRIDAY_BRIDGE_SHARED_SECRET` without printing the value.
4. Apply `bridge/server_auth.patch` to the bridge server entry point.
5. Schedule an owner-approved service restart and validate authenticated MCP/SSE/messages plus public health.
6. Update the architecture/handoff evidence only after runtime verification.

Do not put the secret value in this repository, `CREDENTIALS.md`, commits, logs, pull-request comments or chat. Do not restart the production bridge as part of this code task.

## Integration

`bridge/server_auth.patch` wraps the existing Starlette app after route registration and CORS setup. The middleware is deliberately a pure ASGI component so the tests do not need to import or start the live MCP server.
