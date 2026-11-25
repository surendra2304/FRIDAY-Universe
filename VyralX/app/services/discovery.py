import httpx
from app.config import get_settings
from app.services.niche_guard import check_query, filter_candidates

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"



def discover_space_science_media(query: str, max_results: int = 10) -> list[dict]:
    """TASK-VYR-064: space/science discovery via the public-domain whitelist lane.

    Delegates to ``pd_whitelist.discover_pd_media`` (NASA, Wikimedia
    CC0/PD live; NOAA, USGS as catalogue entries), licence recorded
    per item, logo-guarded. No YouTube discovery is used here.
    """
    from app.services.pd_whitelist import discover_pd_media

    return discover_pd_media(query, max_results=max_results)


def discover_youtube_videos(query: str, max_results: int = 10, order: str = "viewCount") -> list[dict]:
    settings = get_settings()
    if not settings.youtube_data_api_key:
        raise RuntimeError("Set YOUTUBE_DATA_API_KEY in the protected environment")
    max_results = max(1, min(int(max_results), 25))
    if order not in {"relevance", "date", "viewCount", "rating"}:
        raise ValueError("Unsupported YouTube search ordering")
    # TASK-VYR-065: a query naming a banned niche is rejected outright —
    # the search is never issued, so no banned-niche pool can be built.
    allowed, reason = check_query(query)
    if not allowed:
        return []
    params = {"key": settings.youtube_data_api_key, "part": "snippet", "type": "video",
              "q": query[:200], "maxResults": max_results, "order": order,
              "safeSearch": "moderate"}
    try:
        with httpx.Client(timeout=20) as client:
            response = client.get(YOUTUBE_SEARCH_URL, params=params)
            response.raise_for_status()
            items = response.json().get("items", [])
            ids = [item.get("id", {}).get("videoId") for item in items]
            ids = [video_id for video_id in ids if video_id]
            if not ids:
                return []
            stats_response = client.get(YOUTUBE_VIDEOS_URL, params={
                "key": settings.youtube_data_api_key, "part": "statistics,contentDetails",
                "id": ",".join(ids)})
            stats_response.raise_for_status()
            stats = {item["id"]: item for item in stats_response.json().get("items", [])}
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(f"YouTube Data API returned HTTP {exc.response.status_code}") from None
    except httpx.RequestError as exc:
        raise RuntimeError(f"YouTube Data API request failed ({type(exc).__name__})") from None
    candidates = []
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        metric = stats.get(video_id, {})
        statistics = metric.get("statistics", {})
        candidates.append({
            "video_id": video_id,
            "url": "https://www.youtube.com/watch?v=" + video_id,
            "title": snippet.get("title", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt", ""),
            "description": snippet.get("description", "")[:500],
            "view_count": int(statistics.get("viewCount", 0)),
            "like_count": int(statistics.get("likeCount", 0)),
            "comment_count": int(statistics.get("commentCount", 0)),
            "duration": metric.get("contentDetails", {}).get("duration", ""),
            "discovery_only": True,
            "rights_verified": False,
        })
    # TASK-VYR-065: hard niche avoid-list — drop banned-niche candidates
    # before they can reach any caller (API route, orchestrator, project
    # pipeline, task dispatch, repurposer). Rejections are logged with
    # their reason inside filter_candidates.
    candidates, _rejected = filter_candidates(candidates)
    if order == "viewCount":
        return sorted(candidates, key=lambda x: x["view_count"], reverse=True)
    return candidates
