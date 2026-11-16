"""Vibe-Trading research-layer pattern (TASK-IG2-STR-03): factor zoo + IC,
committee review, plain-English backtest specs. Research only."""
from .committee import CommitteeVerdict, ProposalEvidence, ResearchCommittee
from .factors import (FACTOR_ZOO, compute_factor, information_coefficient,
                      zscore)
from .spec_parser import BacktestPlan, parse_spec

__all__ = ["CommitteeVerdict", "ProposalEvidence", "ResearchCommittee",
           "FACTOR_ZOO", "compute_factor", "information_coefficient",
           "zscore", "BacktestPlan", "parse_spec"]
