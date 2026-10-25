"""
Forge — camofox-browser Engine

Stealth headless browser for AI agents. Bypasses bot detection, anti-scraping,
and Cloudflare challenges. Drop-in Puppeteer/Playwright replacement concepts.

Key concepts: browser fingerprinting, stealth detection, anti-bot bypass,
proxy rotation, request timing, and browser automation.

Tests: tests/test_real_batch4a.py
"""

from __future__ import annotations

import hashlib
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BrowserFingerprint:
    """Browser fingerprint generation."""
    user_agent: str
    platform: str
    language: str
    screen_width: int
    screen_height: int
    viewport_width: int
    viewport_height: int
    timezone: str
    webgl_vendor: str
    webgl_renderer: str
    hardware_concurrency: int
    device_memory: float
    color_depth: int
    pixel_ratio: float
    touch_support: bool = False

    @staticmethod
    def generate() -> BrowserFingerprint:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
        ]
        platforms = ["Windows", "macOS", "Linux"]
        timezones = ["America/New_York", "America/Los_Angeles", "Europe/London", "Europe/Paris", "Asia/Tokyo", "Asia/Kolkata"]
        webgl_vendors = ["Google Inc. (NVIDIA)", "Google Inc. (AMD)", "Google Inc. (Intel)"]
        webgl_renderers = ["ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)", "ANGLE (AMD, AMD Radeon RX 6800 XT Direct3D11 vs_5_0 ps_5_0, D3D11)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"]
        return BrowserFingerprint(
            user_agent=random.choice(user_agents),
            platform=random.choice(platforms),
            language="en-US,en;q=0.9",
            screen_width=random.choice([1920, 2560, 1440, 1366]),
            screen_height=random.choice([1080, 1440, 900, 768]),
            viewport_width=random.choice([1920, 1366, 1440]),
            viewport_height=random.choice([1080, 768, 900]),
            timezone=random.choice(timezones),
            webgl_vendor=random.choice(webgl_vendors),
            webgl_renderer=random.choice(webgl_renderers),
            hardware_concurrency=random.choice([4, 8, 12, 16]),
            device_memory=random.choice([4.0, 8.0, 16.0]),
            color_depth=24,
            pixel_ratio=random.choice([1.0, 1.25, 1.5, 2.0]),
        )

    def fingerprint_hash(self) -> str:
        data = f"{self.user_agent}:{self.platform}:{self.screen_width}x{self.screen_height}:{self.timezone}:{self.webgl_vendor}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_agent": self.user_agent,
            "platform": self.platform,
            "language": self.language,
            "screen": f"{self.screen_width}x{self.screen_height}",
            "viewport": f"{self.viewport_width}x{self.viewport_height}",
            "timezone": self.timezone,
            "webgl_vendor": self.webgl_vendor,
            "webgl_renderer": self.webgl_renderer,
            "hardware_concurrency": self.hardware_concurrency,
            "device_memory": self.device_memory,
        }

    @staticmethod
    def random_fingerprint() -> BrowserFingerprint:
        return BrowserFingerprint.generate()


@dataclass
class StealthDetector:
    """Detection of bot/automation characteristics."""
    @staticmethod
    def webdriver_detection(navigator_props: dict) -> bool:
        return navigator_props.get("webdriver", False)

    @staticmethod
    def headless_detection(navigator_props: dict) -> bool:
        ua = navigator_props.get("userAgent", "")
        plugins = navigator_props.get("plugins", [])
        languages = navigator_props.get("languages", [])
        if "HeadlessChrome" in ua:
            return True
        if len(plugins) == 0:
            return True
        if len(languages) == 0:
            return True
        return False

    @staticmethod
    def automation_detection(navigator_props: dict) -> bool:
        if navigator_props.get("__webdriver_evaluate", False):
            return True
        if navigator_props.get("cdc_adoQpoasnfa76pfcZLmcfl_", False):
            return True
        return False

    @staticmethod
    def permissions_detection(permissions: dict) -> bool:
        if permissions.get("notifications") == "denied":
            return True
        if permissions.get("geolocation") == "denied":
            return True
        return False

    @staticmethod
    def canvas_fingerprint_score(fingerprint: str) -> float:
        if len(fingerprint) < 10:
            return 0.0
        return min(1.0, len(fingerprint) / 64)

    @staticmethod
    def detect_all(navigator_props: dict, permissions: dict, canvas_fp: str) -> dict[str, Any]:
        results = {
            "webdriver": StealthDetector.webdriver_detection(navigator_props),
            "headless": StealthDetector.headless_detection(navigator_props),
            "automation": StealthDetector.automation_detection(navigator_props),
            "permissions_anomaly": StealthDetector.permissions_detection(permissions),
            "canvas_score": StealthDetector.canvas_fingerprint_score(canvas_fp),
        }
        risk_score = sum(1 for v in results.values() if v is True)
        results["risk_level"] = "high" if risk_score >= 3 else "medium" if risk_score >= 1 else "low"
        results["risk_score"] = risk_score
        return results

    @staticmethod
    def bypass_suggestions(detection_results: dict) -> list[str]:
        suggestions = []
        if detection_results.get("webdriver"):
            suggestions.append("Override navigator.webdriver property")
        if detection_results.get("headless"):
            suggestions.append("Add realistic user-agent and plugins")
        if detection_results.get("automation"):
            suggestions.append("Remove CDC (Chrome DevTools) variables")
        if detection_results.get("permissions_anomaly"):
            suggestions.append("Simulate real permission responses")
        if detection_results.get("canvas_score", 0) < 0.5:
            suggestions.append("Add canvas noise for fingerprint diversity")
        return suggestions


@dataclass
class AntiBotBypass:
    """Anti-bot challenge bypass strategies."""
    @staticmethod
    def cloudflare_challenge_type(html: str) -> str:
        if "Just a moment..." in html:
            return "cloudflare_interstitial"
        elif "cf-challenge" in html:
            return "cloudflare_js_challenge"
        elif "DDoS protection by Cloudflare" in html:
            return "cloudflare_ddos"
        elif "Attention Required" in html:
            return "cloudflare_block"
        return "none"

    @staticmethod
    def challenge_response(challenge_type: str) -> dict[str, Any]:
        responses = {
            "cloudflare_interstitial": {"action": "wait_for_redirect", "timeout": 30, "poll_interval": 2},
            "cloudflare_js_challenge": {"action": "execute_js", "timeout": 15, "poll_interval": 1},
            "cloudflare_ddos": {"action": "wait_and_retry", "timeout": 60, "poll_interval": 5},
            "cloudflare_block": {"action": "rotate_proxy", "timeout": 0, "poll_interval": 0},
            "none": {"action": "proceed", "timeout": 0, "poll_interval": 0},
        }
        return responses.get(challenge_type, responses["none"])

    @staticmethod
    def adaptive_retry(attempt: int, max_retries: int = 3) -> bool:
        return attempt < max_retries

    @staticmethod
    def backoff_strategy(attempt: int) -> float:
        return 2 ** attempt + random.uniform(0.5, 1.5)

    @staticmethod
    def proxy_rotation(proxies: list[str], attempt: int) -> str:
        if not proxies:
            return ""
        return proxies[attempt % len(proxies)]

    @staticmethod
    def human_like_delay(min_ms: int = 500, max_ms: int = 3000) -> float:
        return random.uniform(min_ms, max_ms) / 1000.0

    @staticmethod
    def mouse_movement_path(start: tuple[int, int], end: tuple[int, int], steps: int = 10) -> list[tuple[int, int]]:
        path = []
        for i in range(steps + 1):
            t = i / steps
            x = int(start[0] + (end[0] - start[0]) * t + random.uniform(-2, 2))
            y = int(start[1] + (end[1] - start[1]) * t + random.uniform(-2, 2))
            path.append((x, y))
        return path

    @staticmethod
    def scroll_pattern(direction: str = "down", amount: int = 500) -> list[dict]:
        steps = []
        position = 0
        while position < amount:
            delta = random.randint(50, 150)
            steps.append({"delta": delta, "direction": direction, "position": position})
            position += delta
        return steps


@dataclass
class ProxyManager:
    """Proxy rotation and management."""
    proxies: list[str] = field(default_factory=list)
    current_index: int = 0
    failed_proxies: set[str] = field(default_factory=set)

    def add_proxy(self, proxy: str) -> None:
        if proxy not in self.proxies:
            self.proxies.append(proxy)

    def remove_proxy(self, proxy: str) -> None:
        if proxy in self.proxies:
            self.proxies.remove(proxy)
        if proxy in self.failed_proxies:
            self.failed_proxies.remove(proxy)

    def get_next(self) -> str:
        if not self.proxies:
            return ""
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return self.proxies[self.current_index]

    def mark_failed(self, proxy: str) -> None:
        self.failed_proxies.add(proxy)

    def mark_success(self, proxy: str) -> None:
        if proxy in self.failed_proxies:
            self.failed_proxies.remove(proxy)

    @property
    def available_count(self) -> int:
        return len([p for p in self.proxies if p not in self.failed_proxies])

    @property
    def failure_rate(self) -> float:
        if not self.proxies:
            return 0.0
        return len(self.failed_proxies) / len(self.proxies)

    def health_check_summary(self) -> dict[str, Any]:
        return {
            "total": len(self.proxies),
            "healthy": self.available_count,
            "failed": len(self.failed_proxies),
            "failure_rate": self.failure_rate,
        }


@dataclass
class BrowserContext:
    """Browser context for stealth browsing."""
    fingerprint: BrowserFingerprint
    proxy: str = ""
    cookies: dict[str, str] = field(default_factory=dict)
    local_storage: dict[str, str] = field(default_factory=dict)
    session_id: str = ""
    request_count: int = 0

    @staticmethod
    def create_context(proxy: str = "") -> BrowserContext:
        fp = BrowserFingerprint.generate()
        session_id = hashlib.md5(f"{fp.fingerprint_hash()}:{time.time()}".encode()).hexdigest()[:16]
        return BrowserContext(
            fingerprint=fp,
            proxy=proxy,
            session_id=session_id,
        )

    def add_cookie(self, name: str, value: str, domain: str = "") -> None:
        key = f"{domain}:{name}" if domain else name
        self.cookies[key] = value

    def add_local_storage(self, key: str, value: str) -> None:
        self.local_storage[key] = value

    def record_request(self) -> None:
        self.request_count += 1

    @property
    def cookie_count(self) -> int:
        return len(self.cookies)

    @property
    def storage_count(self) -> int:
        return len(self.local_storage)

    def context_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "fingerprint_hash": self.fingerprint.fingerprint_hash(),
            "proxy": self.proxy,
            "cookies": len(self.cookies),
            "storage_entries": len(self.local_storage),
            "request_count": self.request_count,
        }


@dataclass
class CamofoxManager:
    """Unified stealth browser manager."""
    contexts: dict[str, BrowserContext] = field(default_factory=dict)
    proxy_manager: ProxyManager = field(default_factory=ProxyManager)
    detector: StealthDetector = field(default_factory=StealthDetector)

    def create_context(self, use_proxy: bool = True) -> BrowserContext:
        proxy = self.proxy_manager.get_next() if use_proxy and self.proxy_manager.available_count > 0 else ""
        context = BrowserContext.create_context(proxy)
        self.contexts[context.session_id] = context
        return context

    def add_proxy(self, proxy: str) -> None:
        self.proxy_manager.add_proxy(proxy)

    def assess_stealth(self, context: BrowserContext) -> dict[str, Any]:
        navigator_props = {
            "webdriver": False,
            "userAgent": context.fingerprint.user_agent,
            "plugins": [{"name": "PDF Viewer"}, {"name": "Chrome PDF Viewer"}, {"name": "Chromium PDF Viewer"}],
            "languages": ["en-US", "en"],
        }
        permissions = {"notifications": "prompt", "geolocation": "prompt"}
        canvas_fp = context.fingerprint.fingerprint_hash()
        return StealthDetector.detect_all(navigator_props, permissions, canvas_fp)

    def challenge_handler(self, html: str) -> dict[str, Any]:
        challenge_type = AntiBotBypass.cloudflare_challenge_type(html)
        response = AntiBotBypass.challenge_response(challenge_type)
        return {
            "challenge_type": challenge_type,
            "response": response,
            "needs_retry": challenge_type != "none",
        }

    def stealth_checklist(self) -> list[str]:
        return [
            "Override webdriver property",
            "Add realistic plugins and languages",
            "Randomize canvas fingerprint",
            "Use rotating proxies",
            "Simulate human mouse movements",
            "Implement variable request timing",
            "Mask CDC variables",
            "Add WebGL fingerprint diversity",
        ]

    @property
    def context_count(self) -> int:
        return len(self.contexts)

    @property
    def proxy_count(self) -> int:
        return self.proxy_manager.available_count

    def context_statistics(self) -> dict[str, Any]:
        total_requests = sum(c.request_count for c in self.contexts.values())
        total_cookies = sum(c.cookie_count for c in self.contexts.values())
        return {
            "contexts": self.context_count,
            "proxies": self.proxy_count,
            "total_requests": total_requests,
            "total_cookies": total_cookies,
        }

    def health_report(self) -> dict[str, Any]:
        return {
            "contexts": self.context_count,
            "proxy_health": self.proxy_manager.health_check_summary(),
            "stealth_level": "high",
            "challenge_handlers": ["cloudflare", "ddos", "js_challenge"],
        }
