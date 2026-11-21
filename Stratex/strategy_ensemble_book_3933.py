"""strategy_ensemble_book_3933 — VA+SHK+XSL ensemble book (TASK-STR-EXP-002).

Thin daemon-facing module for the RD-025 PROVEN book 3933 (VA+SHK+XSL):
equal-weight combination of vol_adaptive_trend ema12_26_nogate @
crypto30 1d, shock_breakout k1.5 @ crypto30 1d, and xs_lowvol lv20_r10
@ crypto30 1d. The execution engine lives in
strategies/ensemble_book.py; the canonical book definition lives in
strategies/ensemble_books.py.

Execution state: EVALUATING (TASK-STR-FWD-030) — every member module
is on main (vol_adaptive #983, shock k1.5 #996) and the xs member
resolves via the panel context the engine passes (strategy_xs_lowvol
looks its symbol up in the persisted panel membership; with no
persisted membership the xs leg abstains and the book nets the
members that did signal). Its judged pooled figures (1295 trades,
PF 1.4072) INCLUDE the xs legs. The book module itself still needs
to be appended to S1's STRATEX_STRATEGY_ALLOWLIST at deploy.
"""

from strategies.ensemble_book import BookState, evaluate_book
from strategies.ensemble_books import BOOKS

BOOK = BOOKS["ensemble_book_3933"]

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
