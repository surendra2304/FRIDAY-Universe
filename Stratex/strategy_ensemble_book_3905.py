"""strategy_ensemble_book_3905 — SHK+DON ensemble book (TASK-STR-EXP-002).

Thin daemon-facing module for the RD-025 PROVEN book 3905 (SHK+DON):
equal-weight combination of shock_breakout k1.5 and donchian_turtle
n55_b26, both @ crypto30 1d. The execution engine lives in
strategies/ensemble_book.py; the canonical book definition lives in
strategies/ensemble_books.py. This module only binds the book to the
daemon's signal interface (get_signal) and carries the module-level
priors the registry reads.

Execution state: PENDING_WAVE_PR_MERGE — #996 (shock k1.5), #987
(donchian). The book refuses (fail-closed, whole book, never a subset)
until every member module is merged; it then needs the allowlist append
at deploy (see SLICE2.md).
"""

from strategies.ensemble_book import BookState, evaluate_book
from strategies.ensemble_books import BOOKS

BOOK = BOOKS["ensemble_book_3905"]

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
