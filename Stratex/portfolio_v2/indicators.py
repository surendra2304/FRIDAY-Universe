"""Pure-python technical indicators (no external dependencies)."""


def ema(values, period):
    """Exponential moving average seeded with an SMA. None until `period` samples."""
    out = [None] * len(values)
    if period <= 0 or len(values) < period:
        return out
    seed = sum(values[:period]) / period
    out[period - 1] = seed
    k = 2.0 / (period + 1.0)
    for i in range(period, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1.0 - k)
    return out


def rsi(closes, period=14):
    """Wilder-smoothed RSI. None until index `period`."""
    out = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    gains = 0.0
    losses = 0.0
    for i in range(1, period + 1):
        delta = closes[i] - closes[i - 1]
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    for i in range(period + 1, len(closes)):
        delta = closes[i] - closes[i - 1]
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        if avg_loss == 0:
            out[i] = 100.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def true_range(highs, lows, closes, i):
    prev_close = closes[i - 1]
    return max(highs[i] - lows[i], abs(highs[i] - prev_close), abs(lows[i] - prev_close))


def atr(highs, lows, closes, period=14):
    """Wilder-smoothed ATR. None until index `period`."""
    out = [None] * len(closes)
    if len(closes) < period + 1:
        return out
    wilder = sum(true_range(highs, lows, closes, i) for i in range(1, period + 1)) / period
    out[period] = wilder
    for i in range(period + 1, len(closes)):
        wilder = (wilder * (period - 1) + true_range(highs, lows, closes, i)) / period
        out[i] = wilder
    return out
