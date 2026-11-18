"""strategy_ensemble_book_3928 — DON+SHK+STO ensemble book (TASK-STR-EXP-002).

Thin daemon-facing module for the RD-025 PROVEN book 3928 (DON+SHK+STO):
equal-weight combination of donchian_turtle n55_b26 @ crypto30 1d,
shock_breakout k1.5 @ crypto30 1d, and stoch_reversion k14_raw @
forex28 1d. Mixed panels: the book needs evaluation context
(symbol/timeframe/venue) — without it the engine refuses. The execution
engine lives in strategies/ensemble_book.py; the canonical book
definition lives in strategies/ensemble_books.py.

Execution state: PENDING_WAVE_PR_MERGE — #987 (donchian), #996
(shock k1.5), #994 (stoch_reversion). The book refuses (fail-closed,
whole book, never a subset) until every member module is merged; it
then needs the allowlist append at deploy (see SLICE2.md).
"""

from strategies.ensemble_book import BookState, evaluate_book
from strategies.ensemble_books import BOOKS

BOOK = BOOKS["ensemble_book_3928"]

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
