"""The Universe intel feed (TASK-INT-014).

IntelX publishes every verified finding once, to the whole Universe, over
Memora's durable event feed; each agent consumes the domains it subscribes
to. See ``intelx.feed.entries`` for why the mesh path is the channel and
``intelx.feed.subscriptions`` for the per-agent filters.
"""

from intelx.feed.entries import (
    WATCH_ALERT_FEED_CONFIDENCE,
    IntelFeedEntry,
    publish_feed_entry,
)
from intelx.feed.subscriptions import (
    DEFAULT_SUBSCRIPTIONS,
    accepts,
    domains_for,
)

__all__ = [
    "DEFAULT_SUBSCRIPTIONS",
    "WATCH_ALERT_FEED_CONFIDENCE",
    "IntelFeedEntry",
    "accepts",
    "domains_for",
    "publish_feed_entry",
]
