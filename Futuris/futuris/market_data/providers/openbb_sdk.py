"""OpenBB Platform SDK provider -- the post-ARM adoption path (TASK-IG-FUT-01).

This provider is the bounded integration point for the real OpenBB SDK:
it speaks the backbone contract on the outside and the OpenBB Platform
(``obb.equity.price.historical`` etc.) on the inside. The evaluation in
``docs/DATA_BACKBONE_IGFUT01.md`` measured the full SDK's import
footprint and found it cannot fit the current fleet's per-service
memory caps, so:

* ``openbb`` is imported ONLY inside :meth:`fetch_ohlcv` -- importing
  this module costs nothing, and the provider can sit in the registry
  on hardware that cannot run it;
* when the SDK is not installed (the production state today), every
  fetch returns ``unavailable`` naming that fact -- it never degrades
  into fabricated or substitute data;
* when the SDK IS installed (post-ARM), bars are standardized from the
  OBBject results and labelled with OpenBB's own provider attribution
  (``market_data:openbb_sdk:<obb provider>``).
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone

UTC = timezone.utc  # 3.11+ name: datetime.UTC is timezone.utc

from futuris.infra.logging import get_logger
from futuris.market_data.base import MarketDataProvider
from futuris.market_data.models import MarketDataResult, OHLCVBar

logger = get_logger("futuris.market_data.openbb_sdk")

#: Backbone interval -> OpenBB interval spelling.
_INTERVAL_MAP = {"1d": "1d", "1h": "1h", "1wk": "1W", "1mo": "1M", "5m": "5m",
                 "15m": "15m", "30m": "30m", "1m": "1m"}

#: Timestamp column spellings OpenBB frames use after ``reset_index()``:
#: daily equity frames carry ``date``; intraday frames carry ``timestamp``.
_TIMESTAMP_COLUMNS = ("date", "timestamp")


def sdk_available() -> bool:
    """True when the OpenBB Platform SDK is installed in this environment.

    Cheap by design: ``find_spec`` locates the package WITHOUT importing
    it. Importing ``openbb`` builds the application router (measured at
    ~996 MB peak RSS in ``docs/DATA_BACKBONE_IGFUT01.md``), which is
    exactly what this probe exists to avoid on the current fleet. The
    backbone's provider-status surface uses this to report the data
    layer's absence instead of discovering it per fetch.
    """
    try:
        return importlib.util.find_spec("openbb") is not None
    except (ImportError, ValueError):
        return False


def _as_float(value: object) -> float | None:
    """Coerce a frame cell to float; None for missing/NaN/unparseable.

    NaN is treated as missing (``f != f``), so a sparse OpenBB frame can
    never mint a bar out of a NaN close or a NaN volume -- the same
    drop-null discipline the Yahoo provider applies to its payloads.
    """
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if number != number else number


class OpenBBSDKProvider(MarketDataProvider):
    """OHLCV via the OpenBB Platform SDK, when it is installed."""

    name = "openbb_sdk"

    def __init__(self, obb_provider: str = "yfinance") -> None:
        #: The OpenBB provider extension to route through (free, keyless
        #: by default). Recorded on every bar's source label.
        self.obb_provider = obb_provider

    async def fetch_ohlcv(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        interval: str = "1d",
    ) -> MarketDataResult:
        fetched_at = datetime.now(UTC)
        if interval not in _INTERVAL_MAP:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"openbb_sdk does not map interval {interval!r}",
                fetched_at=fetched_at,
            )
        try:
            from openbb import obb  # lazy by design: see module docstring
        except Exception:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=(
                    "openbb SDK is not installed in this environment "
                    "(post-ARM adoption path; see docs/DATA_BACKBONE_IGFUT01.md)"
                ),
                fetched_at=fetched_at,
            )
        try:
            obbject = obb.equity.price.historical(
                symbol=symbol,
                start_date=start.date().isoformat(),
                end_date=end.date().isoformat(),
                interval=_INTERVAL_MAP[interval],
                provider=self.obb_provider,
            )
            rows = obbject.to_dataframe().reset_index()
            obb_provider_used = str(getattr(obbject, "provider", None) or self.obb_provider)
        except Exception as exc:
            logger.warning(
                "openbb_sdk_fetch_failed", symbol=symbol, error=type(exc).__name__
            )
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"openbb SDK fetch failed: {type(exc).__name__}",
                fetched_at=fetched_at,
            )

        source = self.source_label(obb_provider_used)
        bars: list[OHLCVBar] = []
        try:
            ts_column = next(
                (c for c in _TIMESTAMP_COLUMNS if c in rows.columns), None
            )
            if ts_column is None:
                return MarketDataResult.unavailable(
                    symbol=symbol,
                    interval=interval,
                    detail=(
                        "openbb SDK payload malformed: no date/timestamp "
                        f"column in frame (columns: {list(rows.columns)})"
                    ),
                    fetched_at=fetched_at,
                )
            for _, row in rows.iterrows():
                ts = row[ts_column]
                ts = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=UTC)
                open_ = _as_float(row["open"])
                high = _as_float(row["high"])
                low = _as_float(row["low"])
                close = _as_float(row["close"])
                if open_ is None or high is None or low is None or close is None:
                    # Sparse slot (e.g. a holiday row of NaNs): dropped,
                    # never interpolated -- the backbone's standing rule.
                    continue
                bars.append(
                    OHLCVBar(
                        symbol=symbol.upper().strip(),
                        provider_symbol=symbol,
                        timestamp=ts,
                        open=open_,
                        high=high,
                        low=low,
                        close=close,
                        volume=_as_float(row.get("volume")),
                        provider=self.name,
                        source=source,
                    )
                )
        except Exception as exc:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail=f"openbb SDK payload malformed: {type(exc).__name__}",
                fetched_at=fetched_at,
            )
        if not bars:
            return MarketDataResult.unavailable(
                symbol=symbol,
                interval=interval,
                detail="openbb SDK returned no bars for the window",
                fetched_at=fetched_at,
            )
        return MarketDataResult(
            status="ok",
            symbol=symbol.upper().strip(),
            interval=interval,
            provider=self.name,
            source=source,
            bars=bars,
            attempts=[f"{self.name}: ok ({len(bars)} bars)"],
            fetched_at=fetched_at,
        )
