"""strategy_ensemble_book_3900 — loop first-light ensemble book (TASK-STR-EXP-002).

Thin daemon-facing module for the self-experiment loop's first-light
book (loop trial 3900, TASK-STR-EXP-001): equal-weight combination of
vol_adaptive_trend ema12_26_nogate, shock_breakout k1.0, and
stoch_reversion k14_raw — all @ crypto30 1d, all judged on the loop's
fixture store (the loop's own judge: pooled PF 1.2643, 1719 trades, 4/5
folds, p ~1.2e-05 vs Bonferroni 1.28e-05 at N=3,900, holdout +2.91% ->
PROVEN). These are the LOOP's recorded cells — NOT RD-025's k1.5 shock
cell (book 3905) and NOT the forex28 stoch cell (book 3927): related
but not identical books. The execution engine lives in
strategies/ensemble_book.py; the canonical book definition lives in
strategies/ensemble_books.py.

Execution state: PENDING_WAVE_PR_MERGE — #983 (vol_adaptive), #994
(stoch_reversion crypto variant); shock k1.0 is on main. The book
refuses (fail-closed, whole book, never a subset) until every member
module is merged; it then needs the allowlist append at deploy.

NETTING WARNING: this book's judged union diverges most from live
netting of all 8 books — 45.2% of its judged member position-days
would be cancelled by the one-net-position rule (its three crypto-1d
members, one a reversion stream, oppose each other on 20.8% of active
days). Expect the live book to trade far less often than the judged
union suggests; the forward demo record is the arbiter.
"""

from strategies.ensemble_book import BookState, evaluate_book
from strategies.ensemble_books import BOOKS

BOOK = BOOKS["ensemble_book_3900"]

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
