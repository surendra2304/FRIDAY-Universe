"""Futuris market-data backbone (TASK-IG-FUT-01).

OpenBB-style standardized OHLCV history behind a bounded provider
interface. Importing this package is cheap by design: it pulls in only
the record models and the provider contract -- provider runtimes load
lazily through ``futuris.market_data.service``'s registry, and the
OpenBB SDK is imported only inside its provider's fetch method.
"""

from futuris.market_data.base import MarketDataProvider
from futuris.market_data.models import MarketDataResult, OHLCVBar

__all__ = ["MarketDataProvider", "MarketDataResult", "OHLCVBar"]
