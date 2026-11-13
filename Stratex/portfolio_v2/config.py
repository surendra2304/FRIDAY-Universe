"""Stratex portfolio_v2 configuration.

Credentials come from the repo-root credentials.md (gitignored master copy).
Two formats are supported:
  * KEY=VALUE lines (agent-side copy)
  * the repo vault format:  "- API token: OANDA_API KEY" followed by an
    indented value line on the next row.

Live portfolio (validated on ~20 years of OANDA daily candles, split into two
non-overlapping decades - tuning on the first, out-of-sample on the second):

  * meanrev-d1  - RSI(3) extreme against the EMA(200) regime, ~70% win rate.
  * breakout-d1 - fresh 10-day Donchian high/low in the EMA(200) direction,
                  2:1 reward:risk.

Universe is majors + gold: crosses were excluded a priori (wider spreads,
choppier) and the tuning data agreed.
"""
import os
import re

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CREDENTIALS_FILE = os.path.join(PROJECT_ROOT, "credentials.md")

_CRED_RE = re.compile(r"^(OANDA_[A-Z_]+)\s*=\s*([^\s#]+)")
_CRED_KEY_REF = re.compile(r"(OANDA_[A-Z_]+)\s*:?\s*$")
_CRED_VALUE = re.compile(r"^[A-Za-z0-9._\-]{16,}$")
_CRED_INLINE = re.compile(r"(OANDA_[A-Z_]+)=(\S+)")


def _parse_credentials(path=CREDENTIALS_FILE):
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        match = _CRED_RE.match(stripped)
        if match:
            values[match.group(1)] = match.group(2)
            continue
        inline = _CRED_INLINE.search(stripped)
        if inline:
            values[inline.group(1)] = inline.group(2)
            continue
        key_ref = _CRED_KEY_REF.search(stripped)
        if key_ref and i + 1 < len(lines):
            candidate = lines[i + 1].strip()
            if _CRED_VALUE.match(candidate):
                values[key_ref.group(1)] = candidate
    return values


class Config:
    """Runtime configuration loaded from credentials.md (env vars as fallback)."""

    def __init__(self):
        creds = _parse_credentials()
        self.api_key = creds.get("OANDA_API_KEY") or os.environ.get("OANDA_API_KEY", "")
        self.environment = creds.get("OANDA_ENV", os.environ.get("OANDA_ENV", "practice"))
        if creds.get("OANDA_PRACTICE", "").lower() == "true":
            self.environment = "practice"
        self.account_id = (creds.get("OANDA_ACCOUNT_ID")
                           or os.environ.get("OANDA_ACCOUNT_ID", ""))
        if not self.api_key:
            raise RuntimeError("OANDA_API_KEY not set - add it to credentials.md")


# ---- live trading universe: majors + gold ----
UNIVERSE = ["EUR_USD", "GBP_USD", "USD_JPY", "AUD_USD", "USD_CAD",
            "USD_CHF", "NZD_USD", "XAU_USD"]

# ---- shared execution parameters ----
EXEC = {
    "max_positions": 6,     # portfolio-wide concurrent positions
    "risk_pct": 0.01,       # 1% of balance risked per trade
}

_COMMON = {
    "granularity": "D",
    "candle_count": 400,        # daily candles pulled for indicator computation
    "stale_bars": 1,            # a signal from the last closed candle only (or 1 older)
    "cooldown_bars": 3,         # days to wait after an exit before re-entering
    "session_utc": (0, 24),     # daily candles: no intraday session filter
    "ema_fast": 9,
    "ema_mid": 20,
    "ema_trend": 50,
    "ema_macro": 200,
    "rsi_period": 14,           # overridden by meanrev
    "atr_period": 14,
}

PORTFOLIO = {
    "meanrev-d1": dict(_COMMON, **{
        "name": "stratex-meanrev-d1",
        "mode": "meanrev",
        "rsi_period": 3,
        "rsi_buy_max": 15,       # buy panic dips while above EMA200
        "rsi_sell_min": 85,      # sell euphoric spikes while below EMA200
        "sl_atr": 1.5,
        "tp_atr": 0.75,
    }),
    "breakout-d1": dict(_COMMON, **{
        "name": "stratex-breakout-d1",
        "mode": "breakout",
        "breakout_bars": 10,     # fresh 10-day high/low
        "sl_atr": 2.0,
        "tp_atr": 4.0,           # 2:1 reward:risk
    }),
}

# Legacy single-strategy view (used by older tuning scripts).
STRATEGY = PORTFOLIO["meanrev-d1"]
