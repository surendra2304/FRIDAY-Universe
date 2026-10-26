"""
Stratex/real_quote_briefing.py — Real Quote Ingestion, Momentum Calls & Briefing.

Turns a vendor chart payload (the Yahoo-style ``chart.result[0]`` shape) into a
typed quote, scores it against short and long moving averages, and composes the
spoken market briefing a voice surface reads out. No network access happens
here: parsing, signal logic and formatting are pure functions so they can be
tested and replayed against recorded payloads.

Real working implementations:
- QuoteSeries: close/high/low series with None-gap handling and statistics
  (SMA, EMA, realized volatility, range position, drawdown from high)
- Quote: parsed price/change/percentage, currency glyph, day range
- QuoteParser: chart-payload parsing, including previous-close fallbacks
- MomentumSignalEngine: SMA-stack signal with a numeric score and a reason
- SignalTable: signal -> score/severity mapping, call labels
- Watchlist: symbol -> display name, per-market defaults, grouping
- PriceFormatter: currency glyphs, Indian lakh/crore and Western grouping
- MarketBriefing: spoken lines, gainers/losers, breadth, plain-text digest
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence


# ── Series ────────────────────────────────────────────────────────────────

@dataclass
class QuoteSeries:
    """A numeric series with real gaps, as vendors actually send them."""

    values: list[float]
    interval: str = "15m"

    @classmethod
    def from_raw(cls, raw: Iterable[Any], interval: str = "15m") -> "QuoteSeries":
        clean: list[float] = []
        for value in raw or []:
            if value is None:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isnan(number) or math.isinf(number):
                continue
            clean.append(number)
        return cls(clean, interval)

    def __len__(self) -> int:
        return len(self.values)

    @property
    def last(self) -> float:
        return self.values[-1] if self.values else 0.0

    @property
    def first(self) -> float:
        return self.values[0] if self.values else 0.0

    def sma(self, window: int) -> float | None:
        """Simple mean of the newest ``window`` closes.

        None when there are fewer than ``window`` closes: a five-bar average of
        two bars is not a five-bar average, and a signal built on it would be a
        guess dressed as a measurement.
        """
        if window <= 0 or len(self.values) < window:
            return None
        sample = self.values[-window:]
        return sum(sample) / len(sample)

    def ema(self, window: int) -> float | None:
        """Exponential mean, seeded with the SMA of the first window."""
        if window <= 0 or len(self.values) < window:
            return None
        seed = sum(self.values[:window]) / window
        multiplier = 2.0 / (window + 1.0)
        value = seed
        for price in self.values[window:]:
            value = price * multiplier + value * (1.0 - multiplier)
        return value

    def change(self) -> float:
        if len(self.values) < 2:
            return 0.0
        return self.values[-1] - self.values[0]

    def pct_change(self) -> float:
        base = self.first
        if base == 0 or len(self.values) < 2:
            return 0.0
        return (self.values[-1] - base) / base * 100.0

    def returns(self) -> list[float]:
        out: list[float] = []
        for previous, current in zip(self.values, self.values[1:]):
            if previous:
                out.append((current - previous) / previous)
        return out

    def volatility(self, annualize: float | None = None) -> float:
        """Standard deviation of simple returns, as a percentage.

        ``annualize`` multiplies by sqrt(bars per year) when supplied; the
        per-bar (unannualized) figure is returned otherwise.
        """
        series = self.returns()
        if len(series) < 2:
            return 0.0
        mean = sum(series) / len(series)
        variance = sum((r - mean) ** 2 for r in series) / (len(series) - 1)
        value = math.sqrt(variance) * 100.0
        if annualize:
            value *= math.sqrt(annualize)
        return value

    def range_position(self, high: float, low: float) -> float:
        """Where the last close sits in the day range, 0 (low) to 1 (high)."""
        if high is None or low is None or high <= low:
            return 0.5
        position = (self.last - low) / (high - low)
        return max(0.0, min(1.0, position))

    def drawdown_from_high(self) -> float:
        """Percentage drop from the series high to the last close."""
        if not self.values:
            return 0.0
        peak = max(self.values)
        if peak == 0:
            return 0.0
        return (self.last - peak) / peak * 100.0

    def momentum(self, window: int = 5) -> float:
        """Percentage change across the trailing ``window`` closes."""
        if window <= 0 or len(self.values) < window + 1:
            return 0.0
        base = self.values[-window - 1]
        if base == 0:
            return 0.0
        return (self.values[-1] - base) / base * 100.0


# ── Quote ─────────────────────────────────────────────────────────────────

# Currency -> glyph used when speaking or printing a price.
CURRENCY_GLYPHS = {
    "INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥",
    "AUD": "A$", "CAD": "C$", "CHF": "CHF ", "CNY": "¥", "HKD": "HK$",
}

INDIAN_SUFFIXES = ("^", ".NS", ".BO")


@dataclass
class Quote:
    """One instrument's parsed state."""

    symbol: str
    name: str
    price: float
    previous_close: float
    currency: str = "USD"
    day_high: float = 0.0
    day_low: float = 0.0
    series: QuoteSeries = field(default_factory=lambda: QuoteSeries([]))
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def glyph(self) -> str:
        return CURRENCY_GLYPHS.get(self.currency.upper(), self.currency + " ")

    @property
    def change(self) -> float:
        return self.price - self.previous_close

    @property
    def pct_change(self) -> float:
        if not self.previous_close:
            return 0.0
        return self.change / self.previous_close * 100.0

    @property
    def direction(self) -> str:
        if self.pct_change > 0.05:
            return "up"
        if self.pct_change < -0.05:
            return "down"
        return "flat"

    @property
    def is_indian(self) -> bool:
        return any(marker in self.symbol for marker in INDIAN_SUFFIXES)

    def range_position(self) -> float:
        return self.series.range_position(self.day_high or self.price,
                                          self.day_low or self.price)

    def formatted_price(self, digits: int = 2) -> str:
        return f"{self.glyph}{PriceFormatter().format(self.price, self.is_indian, digits)}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "name": self.name,
            "price": round(self.price, 4),
            "change": round(self.change, 4),
            "pct_change": round(self.pct_change, 4),
            "currency": self.currency,
            "display": self.formatted_price(),
            "high": round(self.day_high, 4),
            "low": round(self.day_low, 4),
            "range_position": round(self.range_position(), 4),
        }


class PriceFormatter:
    """Group digits the way the instrument's market writes them.

    Indian markets group as 12,34,567.89 (last three, then pairs); most others
    as 1,234,567.89.
    """

    @staticmethod
    def _group_western(digits: str) -> str:
        out: list[str] = []
        while len(digits) > 3:
            out.insert(0, digits[-3:])
            digits = digits[:-3]
        out.insert(0, digits)
        return ",".join(out)

    @staticmethod
    def _group_indian(digits: str) -> str:
        if len(digits) <= 3:
            return digits
        head, tail = digits[:-3], digits[-3:]
        parts: list[str] = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        return ",".join(parts + [tail])

    def format(self, value: float, indian: bool = False, digits: int = 2) -> str:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return "n/a"
        negative = value < 0
        text = f"{abs(float(value)):,.{digits}f}".replace(",", "")
        whole, _, fraction = text.partition(".")
        grouped = (self._group_indian(whole) if indian
                   else self._group_western(whole))
        result = grouped + ("." + fraction if fraction else "")
        return ("-" if negative else "") + result


class QuoteParser:
    """Parse the chart payload a market data vendor returns."""

    def __init__(self, names: dict[str, str] | None = None,
                 default_currency: str | None = None) -> None:
        self.names = dict(names or {})
        self.default_currency = default_currency

    def _currency(self, symbol: str, meta: dict[str, Any]) -> str:
        declared = str(meta.get("currency") or "").upper()
        if declared:
            return declared
        if self.default_currency:
            return self.default_currency.upper()
        # Indian tickers carry ^ for indices and .NS/.BO for listings.
        return "INR" if any(m in symbol for m in INDIAN_SUFFIXES) else "USD"

    def parse(self, symbol: str, payload: Any) -> Quote | None:
        """Return a Quote, or None when the payload holds no usable price."""
        if isinstance(payload, (str, bytes)):
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                return None
        if not isinstance(payload, dict):
            return None

        chart = payload.get("chart", payload)
        if not isinstance(chart, dict):
            return None
        results = chart.get("result") or []
        if not results or not isinstance(results[0], dict):
            return None
        result = results[0]
        meta = result.get("meta") or {}

        price = meta.get("regularMarketPrice")
        if price is None:
            # Some feeds put the last close only in the quote array.
            closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
            usable = [c for c in closes if c is not None]
            price = usable[-1] if usable else None
        if price is None:
            return None
        try:
            price = float(price)
        except (TypeError, ValueError):
            return None

        previous = meta.get("chartPreviousClose")
        if previous is None:
            previous = meta.get("previousClose")
        if previous is None:
            closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
            usable = [float(c) for c in closes if c is not None]
            previous = usable[0] if usable else price
        try:
            previous = float(previous)
        except (TypeError, ValueError):
            previous = price

        closes_raw = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
        interval = str(meta.get("dataGranularity") or "15m")
        series = QuoteSeries.from_raw(closes_raw, interval)

        high = meta.get("regularMarketDayHigh") or price
        low = meta.get("regularMarketDayLow") or price
        try:
            high = float(high)
            low = float(low)
        except (TypeError, ValueError):
            high = low = price

        return Quote(
            symbol=symbol,
            name=self.names.get(symbol, symbol),
            price=price,
            previous_close=previous,
            currency=self._currency(symbol, meta),
            day_high=max(high, price, low),
            day_low=min(low, price, high),
            series=series,
            extra={"meta": meta} if meta else {},
        )

    def parse_many(self, payloads: dict[str, Any]) -> list[Quote]:
        """Parse a watchlist, dropping symbols the vendor had no price for."""
        quotes = [self.parse(symbol, payload) for symbol, payload in payloads.items()]
        return [q for q in quotes if q is not None]


# ── Signals ───────────────────────────────────────────────────────────────

# Signal label -> (score in [-1, 1], call, severity 1-4).
SIGNAL_TABLE: dict[str, tuple[float, str, int]] = {
    "STRONG BUY": (1.0, "buy", 4),
    "BUY / ACCUMULATE": (0.6, "buy", 3),
    "HOLD": (0.0, "hold", 2),
    "SELL / TAKE PROFIT": (-0.6, "sell", 3),
    "STRONG SELL / SHORT": (-1.0, "sell", 4),
}


@dataclass
class MomentumSignal:
    """A scored momentum call on one quote."""

    symbol: str
    signal: str
    score: float
    reason: str
    short_sma: float = 0.0
    long_sma: float = 0.0
    pct_change: float = 0.0

    @property
    def call(self) -> str:
        return SIGNAL_TABLE.get(self.signal, (0.0, "hold", 2))[1]

    @property
    def severity(self) -> int:
        return SIGNAL_TABLE.get(self.signal, (0.0, "hold", 2))[2]

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol, "signal": self.signal,
            "score": round(self.score, 4), "call": self.call,
            "severity": self.severity, "reason": self.reason,
            "short_sma": round(self.short_sma, 4),
            "long_sma": round(self.long_sma, 4),
        }


class MomentumSignalEngine:
    """Score a quote on the short/long SMA stack plus the day's change.

    The four-branch call follows the classic stack: price above both averages
    with a rising long average is the strongest long; price below both with a
    falling long average is the strongest short. Between the branches, the score
    blends the price-to-SMA spread with the SMA spread, so two instruments that
    land on the same label still rank by conviction.
    """

    def __init__(self, short_window: int = 5, long_window: int = 15,
                 strong_threshold: float = 0.5) -> None:
        self.short_window = max(2, short_window)
        self.long_window = max(self.short_window, long_window)
        self.strong_threshold = strong_threshold

    def evaluate(self, quote: Quote) -> MomentumSignal:
        series = quote.series
        pct = quote.pct_change
        short = series.sma(self.short_window)
        long = series.sma(self.long_window)

        if short is None or long is None or long == 0:
            return MomentumSignal(
                symbol=quote.symbol, signal="HOLD", score=0.0,
                reason="Not enough history for a moving-average call.",
                short_sma=short or 0.0, long_sma=long or 0.0, pct_change=pct,
            )

        price = quote.price
        # Normalized spreads: how far price is from the short average, and how
        # far the short average is from the long one.
        price_spread = (price - short) / short
        stack_spread = (short - long) / long
        raw = 0.5 * math.tanh(price_spread * 40.0) + 0.3 * math.tanh(stack_spread * 60.0)
        raw += 0.2 * math.tanh(pct / 2.0)
        score = max(-1.0, min(1.0, raw))

        if price > short > long and pct > self.strong_threshold:
            signal = "STRONG BUY"
            reason = ("Bullish momentum above both moving averages with the "
                      "short average leading the long one.")
        elif price > short and pct >= 0.0:
            signal = "BUY / ACCUMULATE"
            reason = "Holding above short-term support with positive price action."
        elif price < short < long and pct < -self.strong_threshold:
            signal = "STRONG SELL / SHORT"
            reason = ("Bearish stack below both moving averages with active "
                      "selling pressure.")
        elif price < short:
            signal = "SELL / TAKE PROFIT"
            reason = "Slipping below short-term support; further pullback risk."
        else:
            signal = "HOLD"
            reason = "Consolidating around the short-term average."

        return MomentumSignal(
            symbol=quote.symbol, signal=signal, score=score, reason=reason,
            short_sma=short, long_sma=long, pct_change=pct,
        )

    def rank(self, quotes: Sequence[Quote]) -> list[MomentumSignal]:
        """Signals for a watchlist, strongest conviction first."""
        signals = [self.evaluate(q) for q in quotes]
        return sorted(signals, key=lambda s: -abs(s.score))


# ── Watchlist ─────────────────────────────────────────────────────────────

DEFAULT_WATCHLIST: dict[str, str] = {
    "^NSEI": "Nifty 50",
    "^BSESN": "Sensex",
    "RELIANCE.NS": "Reliance Industries",
    "TCS.NS": "TCS",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
    "NVDA": "Nvidia",
    "AAPL": "Apple",
    "BTC-USD": "Bitcoin",
}

# The instruments a spoken overview leads with.
BRIEFING_SYMBOLS = ("^NSEI", "RELIANCE.NS", "NVDA", "BTC-USD")


@dataclass
class Watchlist:
    """A named set of symbols with display names and grouping."""

    names: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_WATCHLIST))
    briefing_symbols: tuple[str, ...] = BRIEFING_SYMBOLS

    def add(self, symbol: str, name: str = "") -> None:
        self.names[symbol] = name or symbol

    def remove(self, symbol: str) -> bool:
        return self.names.pop(symbol, None) is not None

    def symbols(self) -> list[str]:
        return list(self.names)

    def name_of(self, symbol: str) -> str:
        return self.names.get(symbol, symbol)

    def find(self, text: str) -> str | None:
        """Map a spoken phrase to a symbol ("nifty", "reliance", "btc")."""
        lowered = (text or "").lower().strip()
        if not lowered:
            return None
        for symbol, name in self.names.items():
            if lowered == symbol.lower() or lowered == name.lower():
                return symbol
        for symbol, name in self.names.items():
            # "reliance" finds Reliance Industries; "nifty 50" finds ^NSEI.
            if lowered in name.lower() or name.lower() in lowered:
                return symbol
            bare = symbol.lower().replace(".ns", "").replace("^", "").replace("-usd", "")
            if bare and bare in lowered:
                return symbol
        return None

    def group(self, symbol: str) -> str:
        if symbol.startswith("^"):
            return "index"
        if symbol.endswith(("-USD", "-EUR", "-INR")):
            return "crypto"
        if symbol.endswith((".NS", ".BO")):
            return "india"
        return "global"

    def grouped(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for symbol in self.names:
            out.setdefault(self.group(symbol), []).append(symbol)
        return out

    def briefing(self) -> list[str]:
        """The briefing order, extended with any extra Indian listings."""
        chosen = [s for s in self.briefing_symbols if s in self.names]
        for symbol in self.names:
            if len(chosen) >= 4:
                break
            if symbol not in chosen and self.group(symbol) == "india":
                chosen.append(symbol)
        return chosen


# ── Briefing ──────────────────────────────────────────────────────────────

@dataclass
class BriefingLine:
    """One instrument, ready to speak."""

    name: str
    display_price: str
    direction: str
    change_pct: float
    signal: str

    def speak(self) -> str:
        if self.direction == "flat":
            movement = "flat"
            return f"{self.name} is at {self.display_price}, {movement}."
        return (f"{self.name} is at {self.display_price}, {self.direction} "
                f"{abs(self.change_pct):.2f}%. Signal: {self.signal}.")

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "price": self.display_price,
            "direction": self.direction,
            "change_pct": round(self.change_pct, 4), "signal": self.signal,
        }


class MarketBriefing:
    """Compose the spoken market overview from parsed quotes."""

    def __init__(self, engine: MomentumSignalEngine | None = None,
                 watchlist: Watchlist | None = None) -> None:
        self.engine = engine or MomentumSignalEngine()
        self.watchlist = watchlist or Watchlist()

    def lines(self, quotes: Sequence[Quote]) -> list[BriefingLine]:
        out: list[BriefingLine] = []
        for quote in quotes:
            signal = self.engine.evaluate(quote)
            out.append(BriefingLine(
                name=quote.name,
                display_price=quote.formatted_price(),
                direction=quote.direction,
                change_pct=quote.pct_change,
                signal=signal.signal,
            ))
        return out

    def speak(self, quotes: Sequence[Quote], limit: int = 4) -> str:
        """One paragraph a voice surface can read without edits."""
        if not quotes:
            return "I have no market data to report right now."
        selected = list(quotes)[:limit]
        return " ".join(line.speak() for line in self.lines(selected))

    def movers(self, quotes: Sequence[Quote], limit: int = 2) -> dict[str, list[dict[str, Any]]]:
        ranked = sorted(quotes, key=lambda q: q.pct_change, reverse=True)
        gainers = [q.as_dict() for q in ranked[:limit] if q.pct_change > 0]
        losers = [q.as_dict() for q in reversed(ranked) if q.pct_change < 0][:limit]
        return {"gainers": gainers, "losers": losers}

    def summary(self, quotes: Sequence[Quote]) -> dict[str, Any]:
        if not quotes:
            return {"count": 0, "advancers": 0, "decliners": 0, "breadth": 0.0,
                    "average_pct_change": 0.0, "leader": "", "laggard": ""}
        advancers = sum(1 for q in quotes if q.direction == "up")
        decliners = sum(1 for q in quotes if q.direction == "down")
        average = sum(q.pct_change for q in quotes) / len(quotes)
        leader = max(quotes, key=lambda q: q.pct_change)
        laggard = min(quotes, key=lambda q: q.pct_change)
        return {
            "count": len(quotes),
            "advancers": advancers,
            "decliners": decliners,
            "flat": len(quotes) - advancers - decliners,
            "breadth": round(advancers / len(quotes), 4),
            "average_pct_change": round(average, 4),
            "leader": leader.name,
            "laggard": laggard.name,
        }

    def digest(self, quotes: Sequence[Quote]) -> str:
        """Plain multi-line digest for a terminal or a dashboard card."""
        summary = self.summary(quotes)
        header = (
            f"{summary['count']} instruments | {summary['advancers']} up, "
            f"{summary['decliners']} down | average "
            f"{summary['average_pct_change']:+.2f}%"
        )
        rows = [
            f"{quote.name:<22} {quote.formatted_price():>14} "
            f"{quote.pct_change:+7.2f}%  {self.engine.evaluate(quote).signal}"
            for quote in quotes
        ]
        return "\n".join([header] + rows)

    def brief(self, payloads: dict[str, Any],
              parser: QuoteParser | None = None) -> dict[str, Any]:
        """End-to-end: raw watchlist payloads -> quotes, speech and summary."""
        parser = parser or QuoteParser(self.watchlist.names)
        quotes = parser.parse_many(payloads)
        ordered = sorted(
            quotes,
            key=lambda q: (self.watchlist.group(q.symbol) != "index",
                           -q.pct_change),
        )
        return {
            "quotes": [q.as_dict() for q in quotes],
            "spoken": self.speak(ordered),
            "movers": self.movers(quotes),
            "summary": self.summary(quotes),
        }
