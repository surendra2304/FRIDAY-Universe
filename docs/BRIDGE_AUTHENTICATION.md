# FRIDAY Engineering Bridge Authentication

## Scope

The bridge is exposed through public ingress and currently has no request authentication. This change introduces a fail-closed ASGI middleware using one runtime-provided shared secret.

- Preferred MCP-compatible header: `Authorization: Bearer <secret>`.
- Alternative explicit header: `X-FRIDAY-BRIDGE-KEY: <secret>`.
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
4. Confirm both MCP client configurations support standard Bearer auth or the alternative custom header before enabling enforcement.
5. Apply `bridge/server_auth.patch` to the bridge server entry point.
6. Verify that **both Claude and ChatGPT MCP clients can send `Authorization: Bearer <secret>` or `X-FRIDAY-BRIDGE-KEY`** (and that any SSE/EventSource consumers support the selected header or are migrated to a header-capable transport). Test both clients end to end before enabling enforcement; otherwise the guard can lock out the management connectors.
7. Schedule an owner-approved service restart and validate authenticated MCP/SSE/messages plus public health.
8. Update the architecture/handoff evidence only after runtime verification.

Do not put the secret value in this repository, `CREDENTIALS.md`, commits, logs, pull-request comments or chat. Do not restart the production bridge as part of this code task.

## Integration

`bridge/server_auth.patch` registers the authentication middleware before CORS, so Starlette places CORS outside authentication and CORS headers are retained on 401/503 responses. The middleware is deliberately a pure ASGI component so the tests do not need to start the live MCP server.
