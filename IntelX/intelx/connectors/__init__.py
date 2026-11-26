"""INTELX Connectors and Ingestion Package."""

from intelx.connectors.agent_reach import (
    AgentReachReader,
    AgentReachUnavailable,
    classify_reach_url,
)
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
from intelx.connectors.camofox_macros import (
    CamofoxMacroRunner,
    MacroResult,
    build_search_url,
    parse_transcript_json3,
    parse_transcript_xml,
    youtube_transcript_url,
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
    "AgentReachReader",
    "AgentReachUnavailable",
    "BaseConnector",
    "BotWallVerdict",
    "BrowserSidecarConnector",
    "CamofoxClient",
    "CamofoxMacroRunner",
    "MacroResult",
    "SidecarConfig",
    "SidecarFallbackFetcher",
    "SidecarManager",
    "build_search_url",
    "classify_reach_url",
    "default_policy_guard",
    "detect_bot_wall",
    "maybe_wrap_with_sidecar_fallback",
    "parse_transcript_json3",
    "parse_transcript_xml",
    "youtube_transcript_url",
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
]
