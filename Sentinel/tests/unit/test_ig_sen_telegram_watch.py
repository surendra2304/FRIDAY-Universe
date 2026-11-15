"""TASK-IG-SEN-03 — Telegram public-channel threat-intel monitor tests.

The fetcher is faked with a recorded-style preview page: no test touches
the network.
"""

import pytest

from sentinel.core.models import SeverityLevel
from sentinel.integrations.threat_feeds.telegram_channels import (
    TelegramChannelMonitorAdapter,
    TelegramPost,
    parse_channel_html,
)
from sentinel.modules.operations.alerting import AlertEngine

CHANNEL = "leakschannel"

PREVIEW_HTML = """
<html><body>
<div class="tgme_widget_message_wrap">
 <div class="tgme_widget_message" data-post="leakschannel/101">
  <div class="tgme_widget_message_text">Fresh combo list drop, email:pass pairs
  from a gaming forum. Grab it at hxxps://evil-data.example/combo.txt</div>
 </div>
</div>
<div class="tgme_widget_message_wrap">
 <div class="tgme_widget_message" data-post="leakschannel/102">
  <div class="tgme_widget_message_text">Weather is nice today, all quiet here.</div>
 </div>
</div>
<div class="tgme_widget_message_wrap">
 <div class="tgme_widget_message" data-post="leakschannel/103">
  <div class="tgme_widget_message_text">FRIDAY Universe database dump for sale,
  oracle cloud creds included, DM for price</div>
 </div>
</div>
</body></html>
"""


def make_monitor(fetcher, tmp_path=None, **kw):
    return TelegramChannelMonitorAdapter(
        channels=[CHANNEL],
        keywords=["combo list", "database dump", "leak"],
        critical_keywords=["friday universe", "oracle cloud creds"],
        state_path=(tmp_path / "tg_state.json") if tmp_path else None,
        fetcher=fetcher,
        **kw,
    )


async def fake_fetch(url):
    assert url == f"https://t.me/s/{CHANNEL}"
    return PREVIEW_HTML


async def failing_fetch(url):
    raise ConnectionError("network down")


def test_parse_channel_html_extracts_posts():
    posts = parse_channel_html(PREVIEW_HTML, CHANNEL)
    assert [p.message_id for p in posts] == [101, 102, 103]
    assert "combo list" in posts[0].text
    assert posts[0].url == f"https://t.me/{CHANNEL}/101"


def test_match_post_severity_ladder():
    mon = make_monitor(fake_fetch)
    ioc_post = TelegramPost(
        channel=CHANNEL, message_id=1, text="new combo list at https://bad.example/x"
    )
    m = mon.match_post(ioc_post)
    assert m is not None and m.severity == SeverityLevel.MEDIUM and m.iocs

    crit = TelegramPost(
        channel=CHANNEL, message_id=2, text="FRIDAY Universe database dump leaked"
    )
    m2 = mon.match_post(crit)
    assert m2 is not None and m2.severity == SeverityLevel.HIGH and m2.critical_term

    quiet = TelegramPost(channel=CHANNEL, message_id=3, text="nothing relevant here")
    assert mon.match_post(quiet) is None


@pytest.mark.asyncio
async def test_sync_counts_new_matches_and_dedupes(tmp_path):
    mon = make_monitor(fake_fetch, tmp_path=tmp_path)
    assert await mon.sync_feed() == 2  # posts 101 + 103; 102 has no keyword
    assert mon.last_error is None
    # Second sync: everything already seen (state file persisted).
    assert await mon.sync_feed() == 0
    # A fresh monitor over the same state file also sees nothing new.
    mon2 = make_monitor(fake_fetch, tmp_path=tmp_path)
    assert await mon2.sync_feed() == 0


@pytest.mark.asyncio
async def test_sync_fail_closed_on_network_error():
    mon = make_monitor(failing_fetch)
    assert await mon.sync_feed() == 0
    assert mon.last_error is not None and "ConnectionError" in mon.last_error
    assert mon.drain_matches() == []


@pytest.mark.asyncio
async def test_emit_alerts_defanged_and_routed(tmp_path):
    mon = make_monitor(fake_fetch, tmp_path=tmp_path)
    await mon.sync_feed()
    matches = mon.drain_matches()
    assert len(matches) == 2
    engine = AlertEngine()
    alerts = TelegramChannelMonitorAdapter.emit_alerts(matches, engine)
    assert len(alerts) == 2
    severities = {a.severity for a in alerts}
    assert SeverityLevel.HIGH in severities  # the FRIDAY Universe dump post
    combo_alert = next(a for a in alerts if "combo" in a.message.lower())
    # IOC values must be defanged in the alert text.
    assert "hxxps://" in combo_alert.message
    assert "https://evil-data.example" not in combo_alert.message
