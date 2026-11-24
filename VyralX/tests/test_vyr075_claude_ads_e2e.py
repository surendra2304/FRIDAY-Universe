"""TASK-VYR-075 — Claude Ads adapt: live-path end-to-end proof.

The model layer (accounts, campaigns, audits, capability gates)
existed; this file proves it through the LIVE route surface:
create campaign → compliance → audit → report → capability-gated
action, including the failure cases (unknown account audits
critical; an action without the capability is refused; an unknown
campaign is a 404). No ad platform is ever called: there are no
ad accounts, and the module carries no HTTP client at all.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.services import real_media_routes


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = Settings(
        data_dir=tmp_path / "data",
        media_dir=tmp_path / "media",
        render_dir=tmp_path / "renders",
    )
    for d in (settings.data_dir, settings.media_dir, settings.render_dir):
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(real_media_routes, "get_settings", lambda: settings)
    app = FastAPI()
    app.include_router(real_media_routes.router, prefix="/api/v1/vyralx")
    return TestClient(app)


def test_ads_end_to_end_with_failure_cases(tmp_path: Path,
                                           monkeypatch: pytest.MonkeyPatch):
    client = _client(tmp_path, monkeypatch)
    account = f"acc_vyr075_{tmp_path.name[:8]}"

    # 1. Create a campaign (route auto-registers the account).
    created = client.post(
        "/api/v1/vyralx/engines/ads/campaign",
        json={"account_id": account, "name": "VYR075 Launch",
              "platform": "google_ads", "objective": "conversions",
              "budget_daily": 50.0, "budget_total": 1000.0})
    assert created.status_code == 200, created.text
    campaign_id = created.json()["campaign_id"]

    # 2. Compliance: a disclosed creative passes.
    checked = client.post(
        "/api/v1/vyralx/engines/ads/compliance",
        json={"title": "Shorts that teach",
              "description": "Original commentary over licensed footage #ad",
              "cta": "Get Started", "platform": "google_ads",
              "destination_url": "https://vyralx.ai/a",
              "landing_url": "https://vyralx.ai/b"})
    assert checked.status_code == 200
    assert checked.json()["compliant"] is True

    # 3. Audit of the known account: no critical findings.
    audit = client.post("/api/v1/vyralx/engines/ads/audit",
                        json={"account_id": account})
    assert audit.status_code == 200
    summary = audit.json()["summary"]
    assert summary["critical"] == 0
    assert summary["total_findings"] >= 0

    # 4. Audit of an unknown account: critical finding, not a 404.
    missing = client.post("/api/v1/vyralx/engines/ads/audit",
                          json={"account_id": "acc_does_not_exist"})
    assert missing.status_code == 200
    assert missing.json()["summary"]["critical"] == 1
    assert any(f["message"] == "Account not found"
               for f in missing.json()["findings"])

    # 5. Capability gate: pause without the capability is refused.
    refused = client.post(
        f"/api/v1/vyralx/engines/ads/campaign/{campaign_id}/action",
        json={"action": "pause", "capabilities": []})
    assert refused.status_code == 403
    assert "campaign_control" in refused.json()["detail"]["missing"]

    # 6. Same action WITH the capability succeeds.
    paused = client.post(
        f"/api/v1/vyralx/engines/ads/campaign/{campaign_id}/action",
        json={"action": "pause", "capabilities": ["campaign_control"]})
    assert paused.status_code == 200, paused.text
    assert paused.json()["success"] is True

    # 7. Unknown campaign is a 404.
    gone = client.post(
        "/api/v1/vyralx/engines/ads/campaign/camp_nope/action",
        json={"action": "pause", "capabilities": ["campaign_control"]})
    assert gone.status_code == 404

    # 8. Report aggregates the real in-memory state (zeros: no spend).
    report = client.get("/api/v1/vyralx/engines/ads/report/google_ads")
    assert report.status_code == 200
    assert report.json()["total_spend"] == 0.0


def test_ads_module_makes_no_platform_calls():
    """Guardrail: the adapt layer never calls an ad platform.

    There are no ad accounts; audits run over in-memory state.
    Any HTTP client import would mean the module pretends to call
    a platform API.
    """
    import re

    from app.services import real_claude_ads

    source = Path(real_claude_ads.__file__).read_text(encoding="utf-8")
    assert "import httpx" not in source
    assert "import requests" not in source
    assert "urllib.request" not in source
    assert not re.search(r"https?://.*ads.*api", source, re.IGNORECASE)
