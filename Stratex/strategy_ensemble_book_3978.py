"""strategy_ensemble_book_3978 — DUAL+SHW+ZSC+HA1d+XSL ensemble book (TASK-STR-EXP-002).

Thin daemon-facing module for the RD-025 PROVEN book 3978 (size 5):
equal-weight combination of tsmom2_dual roc90_ema200 @ crypto30 1d,
shock_breakout k1.0 @ crypto30 1w, zscore_reversion w50_t2.5_filt @
forex28 1d, ha_trend two_candle @ crypto30 1d, and xs_lowvol lv20_r10
@ crypto30 1d. Mixed panels AND mixed timeframes (1d + 1w): the book
needs evaluation context (symbol/timeframe/venue) and the engine keeps
a per-member signal cache across scans — without context it refuses.
The execution engine lives in strategies/ensemble_book.py; the
canonical book definition lives in strategies/ensemble_books.py.

Execution state: BLOCKED on four members — DUAL 1d has no standalone
module (PR #991 built the 4h cell only), SHW has no 1wk module, ZSC has
no module, and xs_lowvol is a cross-sectional rotation, not a
per-symbol member. Only HA1d is in flight (#993). The book refuses
(fail-closed, whole book, never a subset) until all four exist; its
judged pooled figures (1698 trades, PF 1.3262, shallowest book DD
-0.168 of any proven book) INCLUDE the blocked members' trades.
"""

from strategies.ensemble_book import BookState, evaluate_book
from strategies.ensemble_books import BOOKS

BOOK = BOOKS["ensemble_book_3978"]

_STRATEGY_TYPE = "ENSEMBLE_BOOK"
_OOS_WIN_RATE_PRIOR = BOOK.win_rate
_RR_RATIO = round(
    sum(m.rr_ratio for m in BOOK.members) / len(BOOK.members), 4
)

_STATE = BookState()


def get_signal(df, symbol=None, timeframe=None, venue=None):
    """Daemon signal interface (context-aware: symbol/timeframe/venue).

    The registry detects the extended signature and passes context;
    without it the engine refuses mixed-panel/mixed-timeframe books.
    """
    return evaluate_book(
        BOOK, df, symbol=symbol, timeframe=timeframe, venue=venue, state=_STATE
    )
