"""Backbone behaviour tests (TASK-IG-FUT-01): ordered failover, honest
total failure, and provenance-correct conversion to pipeline
observations."""

from datetime import datetime, timezone

import pytest

from futuris.connectors.provenance import resolve_provenance
from futuris.core.enums import EvidenceClass
from futuris.market_data.base import MarketDataProvider
from futuris.market_data.models import MarketDataResult, OHLCVBar
from futuris.market_data.service import (
    MarketDataBackbone,
    build_provider,
    to_observations,
)

UTC = timezone.utc
START = datetime(2026, 1, 1, tzinfo=UTC)
END = datetime(2026, 1, 10, tzinfo=UTC)


def _bar(provider: str, source: str) -> OHLCVBar:
    return OHLCVBar(
        symbol="BTCUSDT",
        provider_symbol="BTC-USD",
        timestamp=START,
        open=1.0,
        high=2.0,
        low=0.5,
        close=1.5,
        volume=10.0,
        provider=provider,
        source=source,
    )


class _StubProvider(MarketDataProvider):
    def __init__(self, name: str, result: MarketDataResult | None = None,
                 raises: bool = False) -> None:
        self.name = name
        self._result = result
        self._raises = raises

    async def fetch_ohlcv(self, symbol, start, end, interval="1d"):
        if self._raises:
            raise RuntimeError("boom")
        return self._result


def _ok(name: str) -> MarketDataResult:
    source = f"market_data:{name}:BTC-USD"
    return MarketDataResult(
        status="ok", symbol="BTCUSDT", interval="1d", provider=name,
        source=source, bars=[_bar(name, source)],
        attempts=[f"{name}: ok (1 bars)"], fetched_at=START,
    )


def _down(name: str) -> MarketDataResult:
    return MarketDataResult.unavailable(
        symbol="BTCUSDT", interval="1d", detail=f"{name} down",
        fetched_at=START, attempts=[f"{name}: unavailable"],
    )


def test_registry_rejects_unknown_provider():
    with pytest.raises(ValueError, match="unknown market-data provider"):
        build_provider("nope")


def test_registry_builds_keyless_providers():
    assert build_provider("yahoo_chart").name == "yahoo_chart"
    assert build_provider("stooq").name == "stooq"
    assert build_provider("openbb_sdk").name == "openbb_sdk"


async def test_first_real_answer_wins_and_attempts_are_recorded():
    backbone = MarketDataBackbone(
        [_StubProvider("first", _down("first")), _StubProvider("second", _ok("second"))]
    )
    result = await backbone.get_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "ok"
    assert result.provider == "second"
    assert result.attempts[0].startswith("first")
    assert any(a.startswith("second") for a in result.attempts)


async def test_total_failure_is_unavailable_never_fabricated():
    backbone = MarketDataBackbone(
        [_StubProvider("a", _down("a")), _StubProvider("b", _down("b"))]
    )
    result = await backbone.get_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "unavailable"
    assert result.bars == []
    assert result.provider is None
    assert "all configured" in (result.detail or "")


async def test_raising_provider_is_recorded_and_skipped():
    backbone = MarketDataBackbone(
        [_StubProvider("bad", raises=True), _StubProvider("good", _ok("good"))]
    )
    result = await backbone.get_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "ok"
    assert any("bad" in a and "raised" in a for a in result.attempts)


def test_to_observations_labels_real_source_and_provenance_is_live():
    observations = to_observations(_ok("yahoo_chart"))
    assert len(observations) == 1
    obs = observations[0]
    assert obs.series_id == "market:BTCUSDT:close"
    assert obs.source == "market_data:yahoo_chart:BTC-USD"
    assert obs.value == 1.5
    assert obs.tags["open"] == 1.0 and obs.tags["volume"] == 10.0
    provenance = resolve_provenance(object(), observations)
    assert provenance.evidence_class is EvidenceClass.LIVE
    assert provenance.synthetic is False


def test_to_observations_of_unavailable_is_empty():
    assert to_observations(_down("a")) == []


def test_from_settings_threads_openbb_provider():
    """FUTURIS_OPENBB_PROVIDER reaches the openbb_sdk provider instance:
    the OpenBB extension is a config switch, not a code edit."""

    class _Settings:
        FUTURIS_MARKET_DATA_PROVIDERS = "openbb_sdk"
        FUTURIS_OPENBB_PROVIDER = "fmp"

    backbone = MarketDataBackbone.from_settings(_Settings())
    (provider,) = backbone.providers
    assert provider.name == "openbb_sdk"
    assert provider.obb_provider == "fmp"


async def test_backbone_fails_over_past_absent_openbb(monkeypatch):
    """With the SDK absent, the real openbb_sdk provider degrades to an
    explicit unavailable and the backbone moves on to real data."""
    import sys

    from futuris.market_data.providers.openbb_sdk import OpenBBSDKProvider

    monkeypatch.setitem(sys.modules, "openbb", None)
    backbone = MarketDataBackbone(
        [OpenBBSDKProvider(), _StubProvider("second", _ok("second"))]
    )
    result = await backbone.get_ohlcv("BTCUSDT", START, END, "1d")
    assert result.status == "ok"
    assert result.provider == "second"
    assert any(a.startswith("openbb_sdk") for a in result.attempts)


def test_provider_statuses_report_openbb_absent(monkeypatch):
    import sys

    from futuris.market_data.service import provider_statuses

    monkeypatch.setitem(sys.modules, "openbb", None)

    class _Settings:
        FUTURIS_MARKET_DATA_PROVIDERS = "yahoo_chart,openbb_sdk"

    statuses = {s.name: s for s in provider_statuses(_Settings())}
    assert statuses["openbb_sdk"].kind == "sdk"
    assert statuses["openbb_sdk"].available is False
    assert "not installed" in (statuses["openbb_sdk"].detail or "")
    # Network providers never guess availability.
    assert statuses["yahoo_chart"].kind == "http"
    assert statuses["yahoo_chart"].available is None


def test_provider_statuses_flag_unknown_names():
    from futuris.market_data.service import provider_statuses

    class _Settings:
        FUTURIS_MARKET_DATA_PROVIDERS = "nope"

    (status,) = provider_statuses(_Settings())
    assert status.name == "nope"
    assert status.available is False
    assert "registered" in (status.detail or "")


def test_package_import_is_cheap_no_openbb_no_pandas():
    """REL-048 discipline: importing the backbone package must not drag
    the OpenBB SDK (or any provider runtime) into the process."""
    import subprocess
    import sys

    code = (
        "import sys\n"
        "import futuris.market_data\n"
        "import futuris.market_data.service\n"
        "assert 'openbb' not in sys.modules, 'openbb leaked into import'\n"
        "assert 'futuris.market_data.providers.yahoo' not in sys.modules\n"
        "print('cheap')\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr
    assert "cheap" in out.stdout
