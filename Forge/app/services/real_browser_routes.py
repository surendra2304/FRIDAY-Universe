from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from app.services.real_camofox_browser import (
        BrowserFingerprint,
        StealthDetector,
        AntiBotBypass,
        ProxyManager,
        BrowserContext,
        CamofoxManager,
    )
except ImportError:
    from Forge.app.services.real_camofox_browser import (
        BrowserFingerprint,
        StealthDetector,
        AntiBotBypass,
        ProxyManager,
        BrowserContext,
        CamofoxManager,
    )

logger = logging.getLogger("forge.real_browser_routes")
router = APIRouter(prefix="/browser", tags=["Camofox Stealth Browser"])

_manager = CamofoxManager()


class StealthAssessRequest(BaseModel):
    navigator_data: Dict[str, Any] = Field(default_factory=lambda: {"webdriver": False, "userAgent": "Mozilla/5.0", "plugins": [1, 2], "languages": ["en-US"]})
    permission_data: Dict[str, Any] = Field(default_factory=lambda: {"notifications": "prompt"})
    canvas_hash: str = "abc123def456789"


class ChallengeDetectRequest(BaseModel):
    html_content: str = "<html><title>Just a moment...</title><body>Checking your browser</body></html>"
    retry_attempt: int = 1


class TrajectoryRequest(BaseModel):
    start_pos: Tuple[int, int] = (0, 0)
    end_pos: Tuple[int, int] = (450, 680)
    steps: int = 10
    scroll_direction: str = "down"
    scroll_distance: int = 600


class CreateContextRequest(BaseModel):
    proxy: Optional[str] = None
    use_proxy: bool = False


@router.post("/fingerprint")
def generate_stealth_fingerprint():
    """Generate randomized, consistent browser fingerprint with anti-detection evasions."""
    fp = BrowserFingerprint.generate()
    return {
        "status": "success",
        "engine": "CamofoxBrowser",
        "fingerprint": fp.to_dict(),
        "fingerprint_hash": fp.fingerprint_hash(),
    }


@router.post("/stealth-assess")
def assess_browser_stealth(req: StealthAssessRequest):
    """Assess headless detection risks and provide anti-bot bypass suggestions."""
    detection = StealthDetector.detect_all(
        req.navigator_data,
        req.permission_data,
        req.canvas_hash,
    )
    suggestions = StealthDetector.bypass_suggestions(detection)

    return {
        "status": "success",
        "engine": "CamofoxBrowser",
        "detection_results": detection,
        "bypass_suggestions": suggestions,
    }


@router.post("/antibot/challenge")
def handle_antibot_challenge(req: ChallengeDetectRequest):
    """Detect and handle Cloudflare/Datadome interstitial challenges."""
    challenge_type = AntiBotBypass.cloudflare_challenge_type(req.html_content)
    response_strategy = AntiBotBypass.challenge_response(challenge_type)
    backoff_delay = AntiBotBypass.backoff_strategy(req.retry_attempt)

    return {
        "status": "success",
        "engine": "CamofoxBrowser",
        "challenge_type": challenge_type,
        "response_strategy": response_strategy,
        "recommended_backoff_seconds": backoff_delay,
    }


@router.post("/antibot/trajectory")
def generate_human_trajectories(req: TrajectoryRequest):
    """Generate human-like mouse movement curves and scroll patterns."""
    mouse_path = AntiBotBypass.mouse_movement_path(req.start_pos, req.end_pos, steps=req.steps)
    scroll_steps = AntiBotBypass.scroll_pattern(req.scroll_direction, req.scroll_distance)

    return {
        "status": "success",
        "engine": "CamofoxBrowser",
        "mouse_path": mouse_path,
        "scroll_pattern": scroll_steps,
    }


@router.post("/context")
def create_stealth_context(req: CreateContextRequest):
    """Create an isolated, stealth-configured browser session context."""
    if req.proxy:
        _manager.add_proxy(req.proxy)
    context = _manager.create_context(use_proxy=req.use_proxy)
    assessment = _manager.assess_stealth(context)

    return {
        "status": "success",
        "engine": "CamofoxBrowser",
        "session_id": context.session_id,
        "user_agent": context.fingerprint.user_agent,
        "proxy": context.proxy,
        "stealth_assessment": assessment,
        "total_active_contexts": _manager.context_count,
    }


@router.get("/health-report")
def get_browser_health_report():
    """Retrieve full browser fleet health report and stealth checklist."""
    report = _manager.health_report()
    checklist = _manager.stealth_checklist()

    return {
        "status": "success",
        "engine": "CamofoxBrowser",
        "health_report": report,
        "stealth_checklist": checklist,
    }
