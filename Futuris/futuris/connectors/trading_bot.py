"""TradingBot telemetry connector fetching trading performance and market metrics."""

from datetime import UTC, datetime
from typing import Any

import httpx

from futuris.connectors.base import BaseConnector, Observation
from futuris.core.enums import SignalClass
from futuris.infra.logging import get_logger

logger = get_logger("futuris.connectors.trading_bot")

class TradingBotConnector(BaseConnector):
    """Ingests trading telemetry including equity, volatility, drawdowns, and advisory outcomes."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        from futuris.infra.config import settings

        resolved_url = (
            base_url
            or getattr(settings, "STRATEX_URL", None)
            or "http://trading-bot.local"
        )
        self.base_url = resolved_url.rstrip("/")
        configured_key = api_key if api_key is not None else getattr(settings, "STRATEX_API_KEY", None)
        self.api_key = configured_key.strip() if isinstance(configured_key, str) else None
        self.api_key = self.api_key or None
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.last_positions_status = "not_checked"
        self.last_pairs_discovery_status = "not_checked"
        self.last_pairs_source = "not_checked"

    def _auth_headers(self) -> dict[str, str] | None:
        """Return Stratex read credentials only when explicitly configured.

        Stratex's read API accepts the configured X-API-Key or the same value as
        a Bearer token. Never substitute a repository placeholder or sample key:
        an unauthenticated telemetry request is not evidence of portfolio state.
        """
        if not self.api_key:
            return None
        return {
            "X-API-Key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def fetch(self, start: datetime, end: datetime) -> list[Observation]:
        """Fetch trading observations across [start, end]."""
        s_dt = start.replace(tzinfo=UTC) if start.tzinfo is None else start.astimezone(UTC)
        e_dt = end.replace(tzinfo=UTC) if end.tzinfo is None else end.astimezone(UTC)

        headers = self._auth_headers()
        if headers is None:
            logger.warning("trading_telemetry_unavailable", status="not_configured")
            return []
        params = {
            "start": s_dt.isoformat(),
            "end": e_dt.isoformat(),
        }

        url = f"{self.base_url}/api/v1/telemetry/trading"
        logger.info(
            "trading_telemetry_fetch",
            url=url,
            start=s_dt.isoformat(),
            end=e_dt.isoformat(),
        )

        data: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_seconds
            ) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                elif resp.status_code == 404:
                    # A status snapshot may contain current values, but never
                    # manufacture a time series from a single snapshot.
                    status_url = f"{self.base_url}/api/v1/status"
                    resp_status = await client.get(status_url, headers=headers)
                    if resp_status.status_code == 200:
                        status_json = resp_status.json().get("data", {})
                        observed_at = status_json.get("updated_at") or status_json.get("timestamp")
                        if observed_at:
                            for key, metric_type in (
                                ("equity", "equity"),
                                ("max_drawdown_pct", "drawdown"),
                                ("volatility", "volatility"),
                            ):
                                value = status_json.get(key)
                                if isinstance(value, (int, float)) and not isinstance(value, bool):
                                    data.append(
                                        {
                                            "timestamp": observed_at,
                                            "metric_type": metric_type,
                                            "value": value,
                                            "source": "stratex:status_snapshot",
                                        }
                                    )
        except Exception as exc:
            logger.warning("trading_telemetry_unavailable_no_fallback", error=type(exc).__name__)

        observations: list[Observation] = []
        for item in data:
            raw_dt = datetime.fromisoformat(item["timestamp"])
            obs_dt = raw_dt.replace(tzinfo=UTC) if raw_dt.tzinfo is None else raw_dt.astimezone(UTC)

            # Map raw series types to normalized series_id constants
            raw_type = item.get("metric_type", "")
            if raw_type == "equity":
                series_id = "trading:equity"
                unit = "USD"
            elif raw_type == "volatility":
                symbol = item.get("symbol", "btc").lower()
                series_id = f"trading:volatility:{symbol}"
                unit = "volatility_idx"
            elif raw_type == "drawdown":
                series_id = "trading:drawdown"
                unit = "percentage"
            elif raw_type == "position_exposure":
                series_id = "trading:position_exposure"
                unit = "ratio"
            elif raw_type == "advisory_accuracy":
                series_id = "trading:advisory_accuracy"
                unit = "win_rate"
            else:
                series_id = item.get("series_id", f"trading:{raw_type}")
                unit = item.get("unit", "raw")

            observations.append(
                Observation(
                    observed_at=obs_dt,
                    source=item.get("source", "trading_bot:core"),
                    series_id=series_id,
                    value=float(item["value"]),
                    unit=unit,
                    tags={
                        "signal_class": SignalClass.TELEMETRY.value,
                        "strategy": item.get("strategy", "momentum_v1"),
                        "market_regime": item.get("regime", "trending"),
                        **item.get("metadata", {}),
                    },
                )
            )

        logger.info("trading_fetch_completed", count=len(observations))
        return observations

    async def fetch_ticker_series(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
    ) -> list[Observation]:
        """Fetch historical price and volatility observations for a specific market ticker.

        Supports target assets like BTCUSDT, ETHUSDT, SOLUSDT from Stratex.
        """
        s_dt = start.replace(tzinfo=UTC) if start.tzinfo is None else start.astimezone(UTC)
        e_dt = end.replace(tzinfo=UTC) if end.tzinfo is None else end.astimezone(UTC)
        sym_clean = symbol.upper().replace("-", "").replace("/", "")

        headers = self._auth_headers()
        if headers is None:
            logger.warning("trading_telemetry_unavailable", status="not_configured")
            return []
        params = {
            "symbol": sym_clean,
            "start": s_dt.isoformat(),
            "end": e_dt.isoformat(),
        }

        url = f"{self.base_url}/api/v1/telemetry/market/{sym_clean}"
        data: list[dict[str, Any]] = []
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_seconds
            ) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    res_json = resp.json()
                    data = res_json if isinstance(res_json, list) else res_json.get("data", [])
                elif resp.status_code == 404:
                    fallback_url = f"{self.base_url}/api/v1/telemetry/trading"
                    resp2 = await client.get(fallback_url, params=params, headers=headers)
                    if resp2.status_code == 200:
                        res_json2 = resp2.json()
                        data = (
                            res_json2
                            if isinstance(res_json2, list)
                            else res_json2.get("data", [])
                        )
        except Exception as exc:
            logger.warning(
                "ticker_telemetry_unavailable",
                symbol=sym_clean,
                error=f"{type(exc).__name__}: {exc}",
            )

        observations: list[Observation] = []
        for item in data:
            raw_ts = item.get("timestamp") or item.get("observed_at")
            if not raw_ts:
                continue
            raw_dt = datetime.fromisoformat(str(raw_ts))
            obs_dt = raw_dt.replace(tzinfo=UTC) if raw_dt.tzinfo is None else raw_dt.astimezone(UTC)
            val = float(item.get("value") or item.get("price") or 0.0)
            m_type = item.get("metric_type", "price")
            observations.append(
                Observation(
                    observed_at=obs_dt,
                    source=f"stratex:{sym_clean}",
                    series_id=f"trading:{sym_clean}:{m_type}",
                    value=val,
                    unit=item.get("unit", "USD"),
                    tags={
                        "signal_class": SignalClass.TELEMETRY.value,
                        "symbol": sym_clean,
                        **item.get("metadata", {}),
                    },
                )
            )

        logger.info("ticker_series_fetch_completed", symbol=sym_clean, count=len(observations))
        return observations

    async def discover_active_trade_pairs(self) -> list[str]:
        """Return a market watchlist enriched only by the documented Stratex positions API.

        BTC/ETH/SOL are a research watchlist when Stratex data is unavailable;
        they are not represented as confirmed open positions. The source and
        failure status are exposed for the risk payload.
        """
        defaults = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        headers = self._auth_headers()
        if headers is None:
            self.last_pairs_discovery_status = "not_configured"
            self.last_pairs_source = "core_watchlist"
            logger.warning("trade_pair_discovery_unavailable", status="not_configured")
            return defaults

        discovered: set[str] = set()
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_seconds
            ) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/positions",
                    headers=headers,
                )
            if response.status_code in (401, 403):
                self.last_pairs_discovery_status = "unauthorized"
            elif response.status_code == 404:
                self.last_pairs_discovery_status = "not_found"
            elif response.status_code != 200:
                self.last_pairs_discovery_status = "unavailable"
            else:
                payload = response.json()
                raw_positions: Any = payload
                if isinstance(payload, dict):
                    raw_positions = payload.get("data", payload.get("positions", []))
                    if isinstance(raw_positions, dict):
                        raw_positions = raw_positions.get("positions", [])
                if not isinstance(raw_positions, list):
                    self.last_pairs_discovery_status = "invalid_response"
                else:
                    for item in raw_positions:
                        if not isinstance(item, dict):
                            continue
                        symbol = item.get("symbol") or item.get("ticker") or item.get("pair")
                        if not isinstance(symbol, str):
                            continue
                        clean = (
                            symbol.upper()
                            .replace("-", "")
                            .replace("/", "")
                            .replace("_PERP", "")
                            .strip()
                        )
                        if 3 <= len(clean) <= 15:
                            discovered.add(clean)
                    self.last_pairs_discovery_status = "available" if discovered else "empty"
        except httpx.TimeoutException:
            self.last_pairs_discovery_status = "timeout"
        except httpx.HTTPError as exc:
            self.last_pairs_discovery_status = "unavailable"
            logger.warning("trade_pair_discovery_failed", error=type(exc).__name__)
        except (TypeError, ValueError) as exc:
            self.last_pairs_discovery_status = "invalid_response"
            logger.warning("trade_pair_discovery_invalid_response", error=type(exc).__name__)

        self.last_pairs_source = "stratex_positions" if discovered else "core_watchlist"
        pairs = sorted(set(defaults).union(discovered))
        logger.info(
            "active_trade_pairs_discovered",
            count=len(pairs),
            source=self.last_pairs_source,
            status=self.last_pairs_discovery_status,
            pairs=pairs,
        )
        return pairs

    async def fetch_active_positions(self) -> list[dict[str, Any]]:
        """Fetch confirmed open positions from Stratex; never synthesize live positions.

        An empty list means no confirmed positions were returned. The accompanying
        `last_positions_status` differentiates an empty account from missing
        credentials, authorization failure, bad routing, and transport failure.
        """
        headers = self._auth_headers()
        if headers is None:
            self.last_positions_status = "not_configured"
            logger.warning("active_positions_unavailable", status="not_configured")
            return []

        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_seconds
            ) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/positions",
                    headers=headers,
                )
        except httpx.TimeoutException:
            self.last_positions_status = "timeout"
            logger.warning("active_positions_unavailable", status="timeout")
            return []
        except httpx.HTTPError as exc:
            self.last_positions_status = "unavailable"
            logger.warning("active_positions_unavailable", error=type(exc).__name__)
            return []

        if response.status_code in (401, 403):
            self.last_positions_status = "unauthorized"
            logger.warning("active_positions_unavailable", status="unauthorized")
            return []
        if response.status_code == 404:
            self.last_positions_status = "not_found"
            logger.warning("active_positions_unavailable", status="not_found")
            return []
        if response.status_code != 200:
            self.last_positions_status = "unavailable"
            logger.warning(
                "active_positions_unavailable",
                status="http_error",
                status_code=response.status_code,
            )
            return []

        try:
            payload = response.json()
        except ValueError:
            self.last_positions_status = "invalid_response"
            return []

        raw_positions: Any = payload
        if isinstance(payload, dict):
            raw_positions = payload.get("data", payload.get("positions", []))
            if isinstance(raw_positions, dict):
                raw_positions = raw_positions.get("positions", [])
        if not isinstance(raw_positions, list):
            self.last_positions_status = "invalid_response"
            return []

        positions: list[dict[str, Any]] = []
        for item in raw_positions:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol") or item.get("ticker") or item.get("pair")
            if not isinstance(symbol, str) or not symbol.strip():
                continue

            size_raw = item.get("size")
            if size_raw is None:
                size_raw = item.get("positionAmt")
            if size_raw is None:
                size_raw = item.get("quantity")
            try:
                signed_size = float(size_raw)
            except (TypeError, ValueError):
                continue
            if signed_size == 0:
                continue

            sym_val = (
                symbol.upper()
                .replace("-", "")
                .replace("/", "")
                .replace("_PERP", "")
                .strip()
            )
            side = str(item.get("side") or ("SHORT" if signed_size < 0 else "LONG")).upper()
            if signed_size < 0 and side == "LONG":
                side = "SHORT"

            def _number(*keys: str, default: float = 0.0) -> float:
                for key in keys:
                    value = item.get(key)
                    if value is not None and value != "":
                        try:
                            return float(value)
                        except (TypeError, ValueError):
                            return default
                return default

            positions.append(
                {
                    "symbol": sym_val,
                    "side": side,
                    "size": abs(signed_size),
                    "entry_price": _number("entry_price", "entryPrice", "entry"),
                    "current_price": _number("current_price", "mark_price", "markPrice", "price"),
                    "unrealized_pnl": _number("unrealized_pnl", "unRealizedProfit", "pnl"),
                    "leverage": int(_number("leverage", default=1.0)),
                    "liquidation_price": _number("liquidation_price", "liquidationPrice"),
                    "margin": _number("margin", "isolatedMargin", "collateral"),
                    "margin_type": str(item.get("margin_type") or item.get("marginType") or "UNKNOWN").upper(),
                    "isolated_wallet": _number("isolated_wallet", "isolatedWallet"),
                    "funding_rate": _number("funding_rate", "fundingRate"),
                    "updated_at": item.get("updated_at") or item.get("timestamp"),
                }
            )

        self.last_positions_status = "available" if positions else "empty"
        logger.info(
            "active_positions_fetch_completed",
            status=self.last_positions_status,
            count=len(positions),
        )
        return positions

    async def fetch_futures_funding_telemetry(self, symbol: str) -> dict[str, Any]:
        """Fetch read-only funding data from Stratex CCXT market-data API.

        Unavailable data is marked explicitly; the neutral 0.0001 estimate is
        not returned as if it were an observed exchange funding rate.
        """
        clean = (
            symbol.upper()
            .replace("-", "")
            .replace("/", "")
            .replace("_PERP", "")
            .strip()
        )
        result = {
            "symbol": clean,
            "funding_rate": None,
            "funding_time": None,
            "mark_price": None,
            "predicted_rate": None,
            "status": "not_configured",
            "source": None,
        }
        headers = self._auth_headers()
        if headers is None:
            return result

        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_seconds
            ) as client:
                response = await client.get(
                    f"{self.base_url}/api/v1/ccxt/funding",
                    params={"symbol": clean},
                    headers=headers,
                )
            if response.status_code in (401, 403):
                result["status"] = "unauthorized"
                return result
            if response.status_code == 404:
                result["status"] = "not_found"
                return result
            if response.status_code != 200:
                result["status"] = "unavailable"
                return result
            payload = response.json()
            item = payload.get("data", payload) if isinstance(payload, dict) else payload
            if isinstance(item, list):
                item = item[0] if item else None
            if not isinstance(item, dict):
                result["status"] = "invalid_response"
                return result
            result.update(
                {
                    "funding_rate": item.get("funding_rate", item.get("fundingRate")),
                    "funding_time": item.get("funding_time") or item.get("fundingTime") or item.get("timestamp"),
                    "mark_price": item.get("mark_price", item.get("markPrice")),
                    "predicted_rate": item.get("predicted_rate", item.get("predictedRate")),
                    "status": "available",
                    "source": "stratex_ccxt",
                }
            )
            return result
        except httpx.TimeoutException:
            result["status"] = "timeout"
            return result
        except (httpx.HTTPError, ValueError) as exc:
            result["status"] = "unavailable"
            logger.warning("futures_funding_telemetry_unavailable", error=type(exc).__name__)
            return result


# Standard Trading Forecast Targets
TARGET_VOLATILITY_SPIKE = "trading:btc:volatility_spike_24h"
TARGET_DRAWDOWN_RISK = "trading:portfolio:drawdown_exceedance_7d"
TARGET_STRATEGY_DEGRADATION = "trading:strategy:winrate_degradation_14d"
TARGET_CAPITAL_UTILIZATION = "trading:portfolio:capital_utilization_24h"
TARGET_REGIME_TRANSITION = "trading:market:regime_transition_24h"

# Primary Market Target Series
TARGET_BTC_PRICE_VARIANCE = "trading:BTCUSDT:price_variance_24h"
TARGET_ETH_PRICE_VARIANCE = "trading:ETHUSDT:price_variance_24h"
TARGET_SOL_PRICE_VARIANCE = "trading:SOLUSDT:price_variance_24h"
