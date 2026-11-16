"""Bayesian strategy-uncertainty modelling for Stratex RD — research tooling.

TASK-IG2-STR-12 (IG wave 2, cluster #92; source shortcode DUYHoUdD5vk,
which names MCMC — Markov Chain Monte Carlo — among the algorithms
behind finance). RESEARCH-ONLY / DEMO-ONLY: this module consumes a
list of closed forward-fill trade results (R-multiples) and returns
*uncertainty evidence* for the RD promotion gate. It places no orders,
imports nothing from production, and promotes nothing by itself.

Why
---
The RD programme's promotion bar (rd/common.py PROMOTION_BAR) judges
point estimates: pooled expectancy > 0 and profit factor >= 1.2. A
point estimate from 40 forward trades carries wide uncertainty — a
strategy can clear PF 1.2 on luck. This module answers the question
the point estimate cannot: *given the fills actually observed, how
probable is it that the strategy's true expectancy is positive, and
that its true profit factor clears the bar?* The gate keeps the final
say; this is the evidence pack attached to the candidate's file.

Model (deliberately small — the fleet has no numpy/scipy budget in
this package and the RD ig/ convention is stdlib-only)
-----------------------------------------------------------------------
Trades are R-multiples. Each trade is a win (R > 0) with probability
``p`` or a loss (R < 0) with probability ``1 - p``; magnitudes are
log-normal::

    win  magnitude W ~ LogNormal(mu_w, sigma_w)
    loss magnitude L ~ LogNormal(mu_l, sigma_l)

Weakly-informative priors: p ~ Beta(2, 2); mu_* ~ N(0, 1) on log-R;
sigma_* ~ HalfNormal(1). Inference is Metropolis-Hastings MCMC over
(logit p, mu_w, log sigma_w, mu_l, log sigma_l) with Gaussian
random-walk proposals — two chains, fixed seed, fully deterministic:
the same fills and seed always produce the same summary, which is
what makes the output usable as gate evidence.

Per retained draw, expectancy and profit factor are derived in closed
form from the log-normal means::

    E[W] = exp(mu_w + sigma_w^2 / 2),  E[L] = exp(mu_l + sigma_l^2 / 2)
    expectancy_R = p * E[W] - (1 - p) * E[L]
    profit_factor = p * E[W] / ((1 - p) * E[L])

Reported: posterior mean/median and 90% credible intervals for
expectancy and PF, P(expectancy > 0), P(PF >= 1.2) (the PROMOTION_BAR
value), per-chain acceptance rates, and a split-chain mean-difference
diagnostic. ``gate_evidence()`` packages exactly the fields a gate
review needs, with ``supports_promotion`` set only when BOTH
P(expectancy > 0) >= 0.90 and P(PF >= 1.2) >= 0.80 — a deliberately
stricter evidential standard than the point-estimate bar, stated here
so it cannot drift silently.

Data requirements: at least 10 trades with at least 5 wins and 5
losses — with a one-sided record the missing magnitude distribution
is unidentified and any posterior would be prior theatre. Zero-R
trades (scratch fills) are dropped and counted.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any, Sequence

PROMOTION_PF_BAR = 1.2  # rd/common.py PROMOTION_BAR value
MIN_TRADES = 10
MIN_PER_SIDE = 5
SUPPORT_P_EXP_POSITIVE = 0.90
SUPPORT_P_PF_BAR = 0.80


class InsufficientDataError(ValueError):
    """The fill list cannot identify the model's two-sided posterior."""


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def _quantile(sorted_vals: Sequence[float], q: float) -> float:
    if not sorted_vals:
        raise ValueError("quantile of empty sequence")
    idx = min(len(sorted_vals) - 1, max(0, int(q * len(sorted_vals))))
    return sorted_vals[idx]


@dataclass
class PosteriorSummary:
    n_trades: int
    n_wins: int
    n_losses: int
    n_scratch_dropped: int
    observed_expectancy_r: float
    observed_profit_factor: float
    expectancy_mean: float
    expectancy_median: float
    expectancy_ci90: tuple[float, float]
    profit_factor_mean: float
    profit_factor_median: float
    profit_factor_ci90: tuple[float, float]
    p_expectancy_positive: float
    p_profit_factor_at_bar: float
    acceptance_rates: list[float] = field(default_factory=list)
    split_chain_expectancy_diff: float = 0.0
    draws_retained: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_trades": self.n_trades,
            "n_wins": self.n_wins,
            "n_losses": self.n_losses,
            "n_scratch_dropped": self.n_scratch_dropped,
            "observed_expectancy_r": round(self.observed_expectancy_r, 4),
            "observed_profit_factor": round(self.observed_profit_factor, 4),
            "expectancy": {
                "mean": round(self.expectancy_mean, 4),
                "median": round(self.expectancy_median, 4),
                "ci90": [round(v, 4) for v in self.expectancy_ci90],
            },
            "profit_factor": {
                "mean": round(self.profit_factor_mean, 4),
                "median": round(self.profit_factor_median, 4),
                "ci90": [round(v, 4) for v in self.profit_factor_ci90],
            },
            "p_expectancy_positive": round(self.p_expectancy_positive, 4),
            "p_profit_factor_at_bar": round(self.p_profit_factor_at_bar, 4),
            "acceptance_rates": [round(r, 3) for r in self.acceptance_rates],
            "split_chain_expectancy_diff": round(
                self.split_chain_expectancy_diff, 4),
            "draws_retained": self.draws_retained,
        }

    def gate_evidence(self) -> dict[str, Any]:
        """The evidence pack for the RD promotion gate (feeds the gate;
        the gate — walk-forward + PROMOTION_BAR — keeps the final say)."""
        supports = (
            self.p_expectancy_positive >= SUPPORT_P_EXP_POSITIVE
            and self.p_profit_factor_at_bar >= SUPPORT_P_PF_BAR
        )
        return {
            "source": "ig.bayesian_uncertainty (MCMC, TASK-IG2-STR-12)",
            "n_forward_trades": self.n_trades,
            "p_expectancy_positive": round(self.p_expectancy_positive, 4),
            "p_profit_factor_at_bar": round(self.p_profit_factor_at_bar, 4),
            "profit_factor_bar": PROMOTION_PF_BAR,
            "expectancy_ci90": [round(v, 4) for v in self.expectancy_ci90],
            "supports_promotion": supports,
            "standard": (
                f"supports_promotion requires P(expectancy>0) >= "
                f"{SUPPORT_P_EXP_POSITIVE} and P(PF>={PROMOTION_PF_BAR}) "
                f">= {SUPPORT_P_PF_BAR}; evidential support only — the "
                "promotion gate's own checks still apply in full"
            ),
        }


def _log_posterior(theta, log_wins, log_losses, n_wins, n_losses):
    logit_p, mu_w, log_s_w, mu_l, log_s_l = theta
    if not (-12.0 < logit_p < 12.0 and -4.0 < mu_w < 4.0 and -4.0 < mu_l < 4.0
            and -3.0 < log_s_w < 1.5 and -3.0 < log_s_l < 1.5):
        return -math.inf
    p = _sigmoid(logit_p)
    s_w, s_l = math.exp(log_s_w), math.exp(log_s_l)
    # Beta(2,2) prior on p, expressed in logit space: the density
    # contributes log p + log(1-p) and the change of variables adds the
    # same term again (dp/dlogit = p(1-p)).
    lp = 2.0 * (math.log(p) + math.log(1.0 - p))
    # Bernoulli likelihood
    lp += n_wins * math.log(p) + n_losses * math.log(1.0 - p)
    # N(0,1) priors on mu_*
    lp += -0.5 * mu_w * mu_w - 0.5 * mu_l * mu_l
    # HalfNormal(1) priors on sigma_* (log-sigma jacobian included)
    lp += -0.5 * s_w * s_w + log_s_w - 0.5 * s_l * s_l + log_s_l
    # LogNormal likelihoods on magnitudes
    for x in log_wins:
        lp += -log_s_w - 0.5 * ((x - mu_w) / s_w) ** 2
    for x in log_losses:
        lp += -log_s_l - 0.5 * ((x - mu_l) / s_l) ** 2
    return lp


# Per-parameter random-walk scales for (logit p, mu_w, log sigma_w,
# mu_l, log sigma_l): the log-sigma coordinates move on a tighter scale.
PROPOSAL_SDS = (0.10, 0.06, 0.04, 0.06, 0.04)


def _run_chain(rng, theta0, log_wins, log_losses, n_wins, n_losses,
               n_iter, burn):
    theta = list(theta0)
    current = _log_posterior(theta, log_wins, log_losses, n_wins, n_losses)
    kept_exp, kept_pf = [], []
    accepted = 0
    for i in range(n_iter):
        proposal = [t + rng.gauss(0.0, sd)
                    for t, sd in zip(theta, PROPOSAL_SDS)]
        value = _log_posterior(proposal, log_wins, log_losses,
                               n_wins, n_losses)
        if value >= current or rng.random() < math.exp(value - current):
            theta, current = proposal, value
            accepted += 1
        if i >= burn:
            p = _sigmoid(theta[0])
            e_w = math.exp(theta[1] + 0.5 * math.exp(2.0 * theta[2]))
            e_l = math.exp(theta[3] + 0.5 * math.exp(2.0 * theta[4]))
            kept_exp.append(p * e_w - (1.0 - p) * e_l)
            kept_pf.append((p * e_w) / ((1.0 - p) * e_l))
    return kept_exp, kept_pf, accepted / n_iter


def posterior_from_fills(
    fills_r: Sequence[float],
    *,
    seed: int = 20261116,
    n_iter: int = 6000,
    burn: int = 2000,
) -> PosteriorSummary:
    """MCMC posterior over expectancy / profit factor from forward fills.

    ``fills_r`` are closed-trade results in R-multiples (demo/forward
    fills only — this is RD evidence tooling, never a live input).
    Deterministic for a given (fills, seed, n_iter, burn).
    """
    wins = [float(r) for r in fills_r if r > 0]
    losses = [float(-r) for r in fills_r if r < 0]
    scratch = sum(1 for r in fills_r if r == 0)
    n_wins, n_losses = len(wins), len(losses)
    if n_wins + n_losses < MIN_TRADES or n_wins < MIN_PER_SIDE \
            or n_losses < MIN_PER_SIDE:
        raise InsufficientDataError(
            f"need >= {MIN_TRADES} non-scratch trades with >= {MIN_PER_SIDE} "
            f"per side; got {n_wins} wins / {n_losses} losses"
        )
    log_wins = [math.log(w) for w in wins]
    log_losses = [math.log(l) for l in losses]

    gross_win = sum(wins)
    gross_loss = sum(losses)
    observed_exp = (gross_win - gross_loss) / (n_wins + n_losses)
    observed_pf = gross_win / gross_loss if gross_loss else math.inf

    def _mean(xs):
        return sum(xs) / len(xs)

    def _logmean_sd(xs):
        m = _mean(xs)
        var = sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1)
        return m, math.sqrt(var) if var > 1e-9 else 0.35

    mu_w0, s_w0 = _logmean_sd(log_wins)
    mu_l0, s_l0 = _logmean_sd(log_losses)
    theta0 = [_logit(n_wins / (n_wins + n_losses)), mu_w0, math.log(s_w0),
              mu_l0, math.log(s_l0)]

    all_exp: list[float] = []
    all_pf: list[float] = []
    rates: list[float] = []
    chain_means: list[float] = []
    for chain in range(2):
        rng = random.Random(seed + chain * 7919)
        start = [t + (0.15 if chain else -0.15) for t in theta0]
        kept_exp, kept_pf, rate = _run_chain(
            rng, start, log_wins, log_losses, n_wins, n_losses,
            n_iter, burn,
        )
        all_exp.extend(kept_exp)
        all_pf.extend(kept_pf)
        rates.append(rate)
        chain_means.append(_mean(kept_exp))

    exp_sorted = sorted(all_exp)
    pf_sorted = sorted(all_pf)
    return PosteriorSummary(
        n_trades=n_wins + n_losses,
        n_wins=n_wins,
        n_losses=n_losses,
        n_scratch_dropped=scratch,
        observed_expectancy_r=observed_exp,
        observed_profit_factor=observed_pf,
        expectancy_mean=_mean(all_exp),
        expectancy_median=_quantile(exp_sorted, 0.5),
        expectancy_ci90=(_quantile(exp_sorted, 0.05),
                         _quantile(exp_sorted, 0.95)),
        profit_factor_mean=_mean(all_pf),
        profit_factor_median=_quantile(pf_sorted, 0.5),
        profit_factor_ci90=(_quantile(pf_sorted, 0.05),
                            _quantile(pf_sorted, 0.95)),
        p_expectancy_positive=sum(1 for e in all_exp if e > 0) / len(all_exp),
        p_profit_factor_at_bar=sum(
            1 for v in all_pf if v >= PROMOTION_PF_BAR) / len(all_pf),
        acceptance_rates=rates,
        split_chain_expectancy_diff=abs(chain_means[0] - chain_means[1]),
        draws_retained=len(all_exp),
    )
