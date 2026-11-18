"""strategy_ensemble_book_3933 — VA+SHK+XSL ensemble book (TASK-STR-EXP-002).

Thin daemon-facing module for the RD-025 PROVEN book 3933 (VA+SHK+XSL):
equal-weight combination of vol_adaptive_trend ema12_26_nogate @
crypto30 1d, shock_breakout k1.5 @ crypto30 1d, and xs_lowvol lv20_r10
@ crypto30 1d. The execution engine lives in
strategies/ensemble_book.py; the canonical book definition lives in
strategies/ensemble_books.py.

Execution state: BLOCKED on xs_lowvol — a cross-sectional rotation
(rank 30 symbols by 20d vol, hold 3 lowest, rebalance every 10 bars),
not a per-symbol signal strategy; it cannot be a member of a per-symbol
ensemble book without xs rotation machinery. The book refuses
(fail-closed, whole book, never a subset) until that machinery exists;
its judged pooled figures (1295 trades, PF 1.4072) INCLUDE the xs legs.
Also PENDING_WAVE_PR_MERGE — #983 (vol_adaptive), #996 (shock k1.5).
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
