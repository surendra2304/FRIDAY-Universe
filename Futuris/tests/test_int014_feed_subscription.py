"""Tests for Futuris's Universe intel feed subscription (TASK-INT-014).

The feed is broadcast: IntelX publishes once (recipient "all") and each
consumer enforces its own domain subscription. Futuris's default is every
domain (she forecasts everything); these tests pin the domain extraction,
the env-configured narrowing, and the consume-loop behaviour — an
out-of-subscription notice is acknowledged (so it cannot block the feed)
but never persisted.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from futuris.integrations.memora_event_consumer import (
    CONSUMER_ID,
    consume_memora_events_once,
    notice_domain,
    subscribed_domains,
)


class FakeMemora:
    def __init__(self, events):
        self.events = events
        self.acks = []

    def read_event_cursor(self, agent, consumer_id):
        assert agent == "futuris" and consumer_id == CONSUMER_ID
        return {"status": "ok", "after_id": 0}

    def poll_events(self, agent, after_id, limit):
        return {"status": "ok", "events": self.events}

    def acknowledge_event(self, agent, event_id, consumer_id):
        self.acks.append(event_id)
        return {"status": "ok", "after_id": event_id}


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.pending = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, _model, key):
        return self.rows.get(key)

    def add(self, row):
        self.pending.append(row)

    async def commit(self):
        for row in self.pending:
            self.rows[row.event_id] = row


def wire_consumer(monkeypatch, rows, persisted):
    async def persist_notice(_event, _payload):
        persisted.append(_event["event_id"])

    monkeypatch.setattr(
        "futuris.integrations.memora_event_consumer._persist_notice_to_memora",
        persist_notice,
    )

    @asynccontextmanager
    async def sessions():
        yield FakeSession(rows)

    monkeypatch.setattr(
        "futuris.integrations.memora_event_consumer.async_session_factory", sessions
    )


def notice(event_pk: int, event_id: str, domain: str | None) -> dict:
    payload: dict = {"headline": f"Notice {event_id}", "source_agent": "intelx"}
    if domain is not None:
        payload["relevance"] = {"category": "watch_alert", "domain": domain}
    return {
        "id": event_pk,
        "event_id": event_id,
        "event_type": "intelx.news",
        "payload": payload,
    }


def test_notice_domain_extraction():
    assert notice_domain({"relevance": {"domain": "markets"}}) == "markets"
    assert notice_domain({"relevance": {"domain": "  tools_infra "}}) == "tools_infra"
    assert notice_domain({}) == "general"
    assert notice_domain({"relevance": 0.7}) == "general"  # legacy numeric
    assert notice_domain({"relevance": {"domain": " "}}) == "general"
    assert notice_domain({"relevance": {"category": "x"}}) == "general"


def test_subscribed_domains_default_and_env(monkeypatch):
    monkeypatch.delenv("FUTURIS_INTELX_FEED_DOMAINS", raising=False)
    assert subscribed_domains() is None  # every domain, the default
    monkeypatch.setenv("FUTURIS_INTELX_FEED_DOMAINS", "all")
    assert subscribed_domains() is None
    monkeypatch.setenv("FUTURIS_INTELX_FEED_DOMAINS", "markets, ai_models")
    assert subscribed_domains() == frozenset({"markets", "ai_models"})


@pytest.mark.asyncio
async def test_default_subscription_persists_every_domain(monkeypatch):
    monkeypatch.delenv("FUTURIS_INTELX_FEED_DOMAINS", raising=False)
    rows: dict = {}
    persisted: list = []
    wire_consumer(monkeypatch, rows, persisted)
    client = FakeMemora(
        [
            notice(1, "intelx-a-all", "platforms_policy"),
            notice(2, "intelx-b-all", None),  # legacy, un-domained
        ]
    )
    assert await consume_memora_events_once(client) == 2
    assert sorted(rows) == ["intelx-a-all", "intelx-b-all"]
    assert client.acks == [1, 2]


@pytest.mark.asyncio
async def test_narrowed_subscription_acks_but_does_not_persist(monkeypatch):
    monkeypatch.setenv("FUTURIS_INTELX_FEED_DOMAINS", "markets")
    rows: dict = {}
    persisted: list = []
    wire_consumer(monkeypatch, rows, persisted)
    client = FakeMemora(
        [
            notice(1, "intelx-a-all", "platforms_policy"),  # out of scope
            notice(2, "intelx-b-all", "markets"),  # in scope
            notice(3, "intelx-c-all", None),  # "general": out of scope
        ]
    )
    assert await consume_memora_events_once(client) == 3
    assert list(rows) == ["intelx-b-all"]
    assert persisted == ["intelx-b-all"]
    # Every event is acknowledged in order — skipped ones cannot jam the feed.
    assert client.acks == [1, 2, 3]
