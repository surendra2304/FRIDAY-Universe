"""Binance venue agent and environment-safe client factory.

The legacy Stratex trading lifecycle still uses python-binance's Futures methods.
This agent isolates exchange credentials/endpoints from the strategy and risk core.
It supports the current Binance Demo Trading API only. The legacy Futures
Testnet compatibility mode was removed with the retirement of the
classic-testnet venue (owner decision 2026-11-15, TASK-STR-RETIRE-001;
TASK-STR-FWD-032): there is no non-demo fallback any more.

Never falls back from Demo credentials to legacy keys: those credentials are not
interchangeable. Live endpoints are never selected by this factory.
"""
from __future__ import annotations

import os
from typing import Any

from binance.client import Client


BINANCE_DEMO_SPOT_API_URL = "https://demo-api.binance.com/api"
BINANCE_DEMO_FUTURES_API_URL = "https://demo-fapi.binance.com/fapi"
_PLACEHOLDERS = {"", "YOUR_BINANCE_API_KEY", "YOUR_BINANCE_API_SECRET",
                 "YOUR_API_KEY", "YOUR_API_SECRET"}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _real_secret(value: str | None) -> bool:
    return bool(value and value.strip() and value.strip() not in _PLACEHOLDERS)


class BinanceFuturesAgent:
    """Isolated Binance client lifecycle for Stratex's demo runtime."""

    agent_id = "binance_futures"

    def __init__(self, demo_trading: bool | None = None):
        self.demo_trading = _truthy(os.getenv("BINANCE_DEMO_TRADING", "false")) if demo_trading is None else bool(demo_trading)

    def _assert_safe_mode(self, mode: str) -> None:
        normalized = str(mode).upper()
        if normalized not in {"TESTNET", "FUTURES"}:
            raise RuntimeError(f"Binance execution agent refuses TRADING_MODE={normalized!r}; expected TESTNET or FUTURES.")
        if _truthy(os.getenv("LIVE_TRADING_ENABLED", "false")):
            raise RuntimeError("Binance execution agent refuses LIVE_TRADING_ENABLED=true.")
        if normalized == "PAPER":
            raise RuntimeError("Paper mode must not construct an exchange execution client.")

    def create_client(
        self,
        mode: str,
        *,
        client_cls: Any = None,
    ) -> Any:
        """Create a signed client pinned to Demo Trading URLs only."""
        self._assert_safe_mode(mode)
        client_type = client_cls or Client
        if not self.demo_trading:
            # The classic-testnet venue was retired by owner decision 2026-11-15
            # (TASK-STR-RETIRE-001) and excised here (TASK-STR-FWD-032): there
            # is no non-demo fallback any more. Demo Trading is the only venue.
            raise RuntimeError(
                "BINANCE_DEMO_TRADING is not enabled; the retired Binance classic-testnet "
                "venue is no longer available. Set BINANCE_DEMO_TRADING=true with fresh "
                "Demo Trading credentials in BINANCE_API_KEY and BINANCE_API_SECRET."
            )
        # Deliberately do not fallback to API_KEY/SECRET_KEY: those may belong
        # to a different, retired venue or account.
        api_key = os.getenv("BINANCE_API_KEY", "").strip().strip("'\"")
        api_secret = os.getenv("BINANCE_API_SECRET", "").strip().strip("'\"")
        if not _real_secret(api_key) or not _real_secret(api_secret):
            raise RuntimeError(
                "BINANCE_DEMO_TRADING=true requires fresh Demo Trading credentials in "
                "BINANCE_API_KEY and BINANCE_API_SECRET. Legacy API_KEY/SECRET_KEY are not used."
            )
        client = client_type(api_key, api_secret, testnet=False, ping=False)
        client.API_URL = BINANCE_DEMO_SPOT_API_URL
        client.FUTURES_URL = BINANCE_DEMO_FUTURES_API_URL
        # Explicit audit markers; not used to choose endpoint URLs downstream.
        client.stratex_venue = "binance"
        client.stratex_environment = "demo_trading"
        self._assert_no_production_endpoints(client)
        return client

    def create_public_client(self, *, futures: bool = True, client_cls: Any = None) -> Any:
        """Create an unauthenticated market-data client pinned to Demo Trading.

        Public market data carries no credentials, so it is pinned to the Demo
        Trading hosts unconditionally: the retired classic-testnet venue is
        never selected, whatever the demo flag says.
        """
        client_type = client_cls or Client
        client = client_type("", "", testnet=False, ping=False)
        client.API_URL = BINANCE_DEMO_SPOT_API_URL
        client.FUTURES_URL = BINANCE_DEMO_FUTURES_API_URL
        client.stratex_environment = "demo_trading_public"
        client.stratex_venue = "binance"
        self._assert_no_production_endpoints(client)
        return client

    @staticmethod
    def _assert_no_production_endpoints(client: Any) -> None:
        """Fail closed if a client endpoint accidentally points at production."""
        api_url = str(getattr(client, "API_URL", ""))
        futures_url = str(getattr(client, "FUTURES_URL", ""))
        allowed_api = {BINANCE_DEMO_SPOT_API_URL}
        allowed_futures = {BINANCE_DEMO_FUTURES_API_URL}
        if api_url not in allowed_api or futures_url not in allowed_futures:
            raise RuntimeError("Binance agent rejected unrecognized/non-demo endpoint configuration.")
