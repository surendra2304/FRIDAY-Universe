"""Read-only Inference admin dashboard (TASK-IG2-INF-03).

Pattern cherry-picked from FreeLLMAPI (see ~/workspace/ig-references/repos/
freellmapi.md): one page where an operator can see the gateway's real state
— per-provider health, quota burn, per-key usage, and recent failovers —
instead of discovering quota exhaustion as a mysterious agent failure.

This is deliberately **not** the existing ``/ui`` control room: that page is
an unauthenticated liveness surface. This dashboard exposes audit data
(per-key usage fingerprints, failover reasons), so ``app.main`` mounts it
behind ``require_inference_api_key`` like every other audit surface.

Read-only means read-only: both routes are GETs over snapshots the gateway
already maintains — the quota ledger (TASK-INF-007), the provider health
tracker, the failover log (this task), the token-compression stats
(TASK-IG2-INF-04) and the latest Bytez probe report (TASK-IG2-INF-01).
Nothing here mutates state, calls a provider, or returns a key value; keys
appear only as the ledger's truncated SHA-256 fingerprints.

Routes:
* ``GET /admin/inference`` — server-rendered HTML (no client JS, no fetch:
  what you see is the snapshot taken when the page was served).
* ``GET /admin/inference.json`` — the same snapshot as JSON.
"""

from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import HTMLResponse

from app.providers.failover_log import failover_log
from app.providers.health import provider_health_tracker
from app.providers.quota_ledger import quota_ledger

admin_dashboard_router = APIRouter(prefix="/admin", tags=["Inference Admin (read-only)"])


def build_admin_snapshot() -> dict[str, Any]:
    """Assemble the dashboard snapshot from the live in-process trackers."""
    quota = quota_ledger.snapshot()
    health_reports = provider_health_tracker.get_all_health()
    providers: dict[str, Any] = {}
    names = sorted(set(quota.get("providers", {})) | set(health_reports))
    for name in names:
        report = health_reports.get(name)
        providers[name] = {
            "health": report.model_dump() if report is not None else None,
            "quota": quota.get("providers", {}).get(name),
        }
    bytez_probe = None
    try:
        from app.providers.bytez_probe import latest_probe_report

        bytez_probe = latest_probe_report()
    except Exception:  # noqa: BLE001 - a missing probe must not break the dashboard
        bytez_probe = None
    # TASK-IG2-INF-04 ships in its own PR; read its stats opportunistically
    # so this dashboard works whether or not that PR has landed yet.
    try:
        from app.providers.token_compression import compression_stats

        token_compression = compression_stats()
    except Exception:  # noqa: BLE001 - dashboard must not break on a missing stage
        token_compression = {}
    return {
        "service": "inference",
        "generated_at_utc": quota.get("generated_at_utc"),
        "quota_window_reset": quota.get("window_reset"),
        "any_warning": quota.get("any_warning"),
        "any_exhausted": quota.get("any_exhausted"),
        "warnings": quota.get("warnings", []),
        "providers": providers,
        "failovers": failover_log.snapshot(limit=20),
        "token_compression": token_compression,
        "bytez_probe": bytez_probe,
        "honesty": quota.get("honesty", {}),
    }


def _esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def _provider_rows(snapshot: dict[str, Any]) -> str:
    rows = []
    for name, data in sorted(snapshot["providers"].items()):
        health = data.get("health") or {}
        quota = data.get("quota") or {}
        rows.append(
            "<tr>"
            f"<td>{_esc(name)}</td>"
            f"<td>{_esc('healthy' if health.get('is_healthy') else 'unhealthy')}</td>"
            f"<td>{_esc(round(float(health.get('health_score') or 0), 3))}</td>"
            f"<td>{_esc(quota.get('state', 'no_data'))}</td>"
            f"<td>{_esc(quota.get('requests_today', 0))}</td>"
            f"<td>{_esc(quota.get('successes_today', 0))}</td>"
            f"<td>{_esc(quota.get('rate_limited_today', 0))}</td>"
            f"<td>{_esc(health.get('active_keys_count', 0))} active / {_esc(health.get('quarantined_keys_count', 0))} quarantined</td>"
            f"<td>{_esc(round(float(health.get('average_latency_seconds') or 0), 3))}s</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="9">No provider activity recorded yet.</td></tr>'


def _key_rows(snapshot: dict[str, Any]) -> str:
    rows = []
    for name, data in sorted(snapshot["providers"].items()):
        quota = data.get("quota") or {}
        for bucket in quota.get("daily_buckets", []):
            rows.append(
                "<tr>"
                f"<td>{_esc(name)}</td>"
                f"<td>{_esc(bucket.get('key_fingerprint') or 'unattributed')}</td>"
                f"<td>{_esc(bucket.get('model'))}</td>"
                f"<td>{_esc(bucket.get('requests'))}</td>"
                f"<td>{_esc(bucket.get('successes'))}</td>"
                f"<td>{_esc(bucket.get('rate_limited'))}</td>"
                f"<td>{_esc(bucket.get('total_tokens'))}</td>"
                f"<td>{_esc(bucket.get('state', ''))}</td>"
                f"<td>{_esc(bucket.get('last_seen_utc'))}</td>"
                "</tr>"
            )
    return "\n".join(rows) or '<tr><td colspan="9">No per-key usage recorded yet.</td></tr>'


def _failover_rows(snapshot: dict[str, Any]) -> str:
    rows = []
    for event in snapshot["failovers"].get("events", []):
        rows.append(
            "<tr>"
            f"<td>{_esc(event.get('at_utc'))}</td>"
            f"<td>{_esc(event.get('from_provider'))}</td>"
            f"<td>{_esc(event.get('model'))}</td>"
            f"<td>{_esc(event.get('capability'))}</td>"
            f"<td>{_esc(event.get('reason'))}</td>"
            "</tr>"
        )
    return "\n".join(rows) or '<tr><td colspan="5">No failovers recorded by this process yet.</td></tr>'


def render_admin_html(snapshot: dict[str, Any]) -> str:
    """Render the snapshot as a single static HTML page (no client JS)."""
    warnings = "\n".join(f"<li>{_esc(w)}</li>" for w in snapshot.get("warnings", []))
    compression = snapshot.get("token_compression", {})
    bytez = snapshot.get("bytez_probe") or {}
    bytez_line = (
        f"verdict {_esc(bytez.get('verdict'))} at {_esc(bytez.get('generated_at_utc'))}"
        if bytez
        else "no probe run yet — free volume unproven, rung disabled by default"
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Inference Admin — provider health, quota, failovers</title></head>
<body>
<h1>Inference Admin (read-only)</h1>
<p>Snapshot generated {_esc(snapshot.get('generated_at_utc'))} UTC. Quota window resets
{_esc((snapshot.get('quota_window_reset') or {}).get('next_reset_utc'))} UTC.
any_warning={_esc(snapshot.get('any_warning'))} any_exhausted={_esc(snapshot.get('any_exhausted'))}</p>
<h2>Warnings</h2>
<ul>{warnings or '<li>none</li>'}</ul>
<h2>Providers</h2>
<table border="1">
<tr><th>provider</th><th>health</th><th>score</th><th>quota state</th><th>requests today</th><th>successes</th><th>rate-limited</th><th>keys</th><th>avg latency</th></tr>
{_provider_rows(snapshot)}
</table>
<h2>Per-key usage (fingerprints only — key values are never displayed)</h2>
<table border="1">
<tr><th>provider</th><th>key fingerprint</th><th>model</th><th>requests</th><th>successes</th><th>rate-limited</th><th>total tokens</th><th>state</th><th>last seen (UTC)</th></tr>
{_key_rows(snapshot)}
</table>
<h2>Recent failovers</h2>
<table border="1">
<tr><th>at (UTC)</th><th>from provider</th><th>model</th><th>capability</th><th>reason</th></tr>
{_failover_rows(snapshot)}
</table>
<h2>Token compression (TASK-IG2-INF-04)</h2>
<p>enabled={_esc(compression.get('enabled'))} requests_seen={_esc(compression.get('requests_seen'))}
compressed={_esc(compression.get('requests_compressed'))} bypassed={_esc(compression.get('requests_bypassed'))}
est_tokens_saved={_esc(compression.get('est_tokens_saved'))}</p>
<h2>Bytez free-tier probe (TASK-IG2-INF-01)</h2>
<p>{bytez_line}</p>
<h2>Coverage &amp; honesty</h2>
<p>{_esc((snapshot.get('honesty') or {}).get('basis', ''))}</p>
<p>{_esc(snapshot['failovers'].get('basis', ''))}</p>
</body>
</html>"""


@admin_dashboard_router.get("/inference", status_code=status.HTTP_200_OK, response_class=HTMLResponse)
async def admin_dashboard_html() -> HTMLResponse:
    """Server-rendered read-only admin dashboard."""
    return HTMLResponse(content=render_admin_html(build_admin_snapshot()), status_code=status.HTTP_200_OK)


@admin_dashboard_router.get("/inference.json", status_code=status.HTTP_200_OK)
async def admin_dashboard_json() -> dict[str, Any]:
    """The dashboard snapshot as JSON (same data as the HTML page)."""
    return build_admin_snapshot()
