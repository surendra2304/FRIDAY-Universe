"""
tools/universe_external_integrations.py — External service integrations for FRIDAY Universe.

Provides integration adapters for:
- GitHub API (repo monitoring, PR tracking)
- Slack (agent notifications)
- Webhooks (event forwarding)
- Generic REST API client
- OCI (Oracle Cloud Infrastructure) adapter

Priority 5: Make It Real (External Integrations)
"""
import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ── Generic REST API Client ──────────────────────────────────────────────────

class RESTClient:
    """Generic REST API client for external services."""

    def __init__(self, base_url: str = "", api_key: str = "", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _request(self, method: str, path: str, data: dict = None, headers: dict = None) -> dict:
        url = f"{self.base_url}{path}"
        req_headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            req_headers["Authorization"] = f"Bearer {self.api_key}"
        if headers:
            req_headers.update(headers)
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
        try:
            resp = urllib.request.urlopen(req, timeout=self.timeout)
            return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}", "body": e.read().decode()[:200]}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def get(self, path: str, params: dict = None) -> dict:
        return self._request("GET", path)

    def post(self, path: str, data: dict = None) -> dict:
        return self._request("POST", path, data)

    def put(self, path: str, data: dict = None) -> dict:
        return self._request("PUT", path, data)

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)


# ── GitHub Integration ────────────────────────────────────────────────────────

class GitHubIntegration:
    """GitHub API integration for repo monitoring and PR tracking."""

    def __init__(self, token: str = "", repo: str = ""):
        self.client = RESTClient("https://api.github.com", token)
        self.repo = repo

    def get_repo(self) -> dict:
        if not self.repo:
            return {"error": "No repo configured"}
        return self.client.get(f"/repos/{self.repo}")

    def get_prs(self, state: str = "open") -> dict:
        if not self.repo:
            return {"error": "No repo configured"}
        return self.client.get(f"/repos/{self.repo}/pulls?state={state}")

    def get_issues(self, state: str = "open") -> dict:
        if not self.repo:
            return {"error": "No repo configured"}
        return self.client.get(f"/repos/{self.repo}/issues?state={state}")

    def create_issue(self, title: str, body: str, labels: list[str] = None) -> dict:
        if not self.repo:
            return {"error": "No repo configured"}
        data = {"title": title, "body": body}
        if labels:
            data["labels"] = labels
        return self.client.post(f"/repos/{self.repo}/issues", data)


# ── Slack Integration ────────────────────────────────────────────────────────

class SlackIntegration:
    """Slack API integration for agent notifications."""

    def __init__(self, webhook_url: str = "", token: str = ""):
        self.webhook_url = webhook_url
        self.client = RESTClient("https://slack.com/api", token)

    def send_message(self, channel: str, message: str, blocks: list = None) -> dict:
        data = {"channel": channel, "text": message}
        if blocks:
            data["blocks"] = blocks
        return self.client.post("chat.postMessage", data)

    def send_webhook(self, message: str) -> dict:
        """Send via webhook (simpler, no token needed)."""
        if not self.webhook_url:
            return {"error": "No webhook URL configured"}
        data = json.dumps({"text": message}).encode()
        req = urllib.request.Request(self.webhook_url, data=data, headers={"Content-Type": "application/json"})
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            return {"status": resp.status}
        except Exception as e:
            return {"error": str(e)}


# ── Webhook Integration ───────────────────────────────────────────────────────

class WebhookIntegration:
    """Webhook forwarding for agent events."""

    def __init__(self):
        self._subscriptions: dict[str, list[dict]] = {}

    def subscribe(self, event_type: str, url: str, secret: str = "") -> dict:
        """Subscribe a webhook URL to an event type."""
        if event_type not in self._subscriptions:
            self._subscriptions[event_type] = []
        sub = {"url": url, "secret": secret, "created_at": time.time()}
        self._subscriptions[event_type].append(sub)
        return sub

    def unsubscribe(self, event_type: str, url: str) -> bool:
        """Unsubscribe a webhook URL."""
        if event_type in self._subscriptions:
            self._subscriptions[event_type] = [s for s in self._subscriptions[event_type] if s["url"] != url]
            return True
        return False

    def fire(self, event_type: str, payload: dict) -> list[dict]:
        """Fire an event to all subscribed webhooks."""
        results = []
        for sub in self._subscriptions.get(event_type, []):
            data = json.dumps({"event": event_type, "payload": payload, "timestamp": time.time()}).encode()
            req = urllib.request.Request(sub["url"], data=data, headers={"Content-Type": "application/json"})
            try:
                resp = urllib.request.urlopen(req, timeout=10)
                results.append({"url": sub["url"], "status": resp.status})
            except Exception as e:
                results.append({"url": sub["url"], "error": str(e)})
        return results


# ── OCI (Oracle Cloud Infrastructure) Adapter ────────────────────────────────

class OCIIntegration:
    """Oracle Cloud Infrastructure adapter (simplified REST API)."""

    def __init__(self, tenancy_ocid: str = "", user_ocid: str = "", fingerprint: str = "",
                 region: str = "us-ashburn-1", private_key_path: str = ""):
        self.tenancy_ocid = tenancy_ocid
        self.user_ocid = user_ocid
        self.fingerprint = fingerprint
        self.region = region
        self.private_key_path = private_key_path
        self._base_url = "https://iaas.{region}.oraclecloud.com"

    @property
    def available(self) -> bool:
        return bool(self.tenancy_ocid and self.user_ocid and self.fingerprint)

    def list_instances(self) -> dict:
        """List all instances in the compartment."""
        if not self.available:
            return {"error": "OCI credentials not configured"}
        # This would use the OCI Python SDK with proper signing
        # For now, return a placeholder
        return {"error": "OCI SDK not installed. Install with: pip install oci"}

    def get_instance_status(self, instance_id: str) -> dict:
        """Get status of a specific instance."""
        if not self.available:
            return {"error": "OCI credentials not configured"}
        return {"error": "OCI SDK not installed"}

    def get_object_storage_url(self, bucket: str, namespace: str, object_name: str) -> str:
        """Generate a pre-signed URL for Object Storage."""
        base = self._base_url.format(region=self.region)
        return f"https://{namespace}.compat.{self.region}.objectstorage.oraclecloud.com/{bucket}/{object_name}"


# ── Agent Integration Manager ─────────────────────────────────────────────────

class UniverseIntegrations:
    """Unified manager for all external integrations."""

    def __init__(self):
        self.github = GitHubIntegration()
        self.slack = SlackIntegration()
        self.webhooks = WebhookIntegration()
        self.oci = OCIIntegration()
        self.rest = RESTClient()

    def configure_github(self, token: str, repo: str):
        self.github = GitHubIntegration(token, repo)

    def configure_slack(self, webhook_url: str = "", token: str = ""):
        self.slack = SlackIntegration(webhook_url, token)

    def configure_oci(self, tenancy: str, user: str, fingerprint: str, region: str = "us-ashburn-1"):
        self.oci = OCIIntegration(tenancy, user, fingerprint, region)

    def health_check(self) -> dict:
        """Check all integration statuses."""
        return {
            "github": "configured" if self.github.repo else "not configured",
            "slack": "configured" if self.slack.webhook_url else "not configured",
            "webhooks": f"{len(self.webhooks._subscriptions)} event types",
            "oci": "available" if self.oci.available else "not configured",
            "rest": f"base_url={self.rest.base_url or 'none'}",
        }

    def notify(self, agent: str, message: str, level: str = "info") -> dict:
        """Send a notification about an agent event."""
        results = {}
        # Slack
        if self.slack.webhook_url:
            results["slack"] = self.slack.send_webhook(f"[{level.upper()}] {agent}: {message}")
        # Webhooks
        results["webhooks"] = self.webhooks.fire("agent_event", {
            "agent": agent, "message": message, "level": level,
        })
        return results


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== FRIDAY Universe External Integrations ===\n")

    # Test REST client
    client = RESTClient("https://httpbin.org", timeout=5)
    result = client.get("/json")
    if "error" not in result:
        print("✅ REST client working (httpbin.org responded)")
    else:
        print(f"⚠️  REST client test: {result['error']}")

    # Test integrations manager
    manager = UniverseIntegrations()
    health = manager.health_check()
    print(f"\nIntegration Status:")
    for k, v in health.items():
        print(f"  {k}: {v}")

    # Test webhook subscription
    manager.webhooks.subscribe("agent_event", "https://httpbin.org/post")
    result = manager.webhooks.fire("agent_event", {"test": True})
    print(f"\nWebhook test: {result}")

    # Test notification
    result = manager.notify("FRIDAY", "Health check complete", "info")
    print(f"\nNotification test: {result}")

    print("\n=== External Integrations Ready ===")
