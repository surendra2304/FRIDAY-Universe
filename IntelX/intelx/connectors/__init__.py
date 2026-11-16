"""INTELX Connectors and Ingestion Package."""

from intelx.connectors.base import BaseConnector, default_policy_guard
from intelx.connectors.browser_sidecar import (
    BotWallVerdict,
    BrowserSidecarConnector,
    CamofoxClient,
    SidecarConfig,
    SidecarFallbackFetcher,
    SidecarManager,
    detect_bot_wall,
    maybe_wrap_with_sidecar_fallback,
)
from intelx.connectors.files import FileConnector, FileIngestResult
from intelx.connectors.sanitize import IngestionSanitizer, ScanResult
from intelx.connectors.search import (
    DuckDuckGoSearchConnector,
    SearchResult,
    SearXNGSearchConnector,
    TavilySearchConnector,
    WebSearchConnector,
)
from intelx.connectors.web import FetchResult, HttpFetchConnector

__all__ = [
    "BaseConnector",
    "default_policy_guard",
    "HttpFetchConnector",
    "FetchResult",
    "WebSearchConnector",
    "TavilySearchConnector",
    "SearXNGSearchConnector",
    "DuckDuckGoSearchConnector",
    "SearchResult",
    "FileConnector",
    "FileIngestResult",
    "IngestionSanitizer",
    "ScanResult",
    "BotWallVerdict",
    "BrowserSidecarConnector",
    "CamofoxClient",
    "SidecarConfig",
    "SidecarFallbackFetcher",
    "SidecarManager",
    "detect_bot_wall",
    "maybe_wrap_with_sidecar_fallback",
]
