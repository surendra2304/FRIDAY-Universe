"""The closed experiment catalogue (TASK-STR-EXP-001).

The loop may only ever propose what is declared here, in code. The
catalogue is not data, not configuration, and not in the loop's data
directory — the loop cannot extend it (Self-Upgrade DESIGN section 5).

Slice 1 implements ONE experiment family end-to-end: COMBINATIONS of
already-admitted streams (brief type b). The other two brief families
are declared below with implemented=False so the catalogue's full
shape is on record; the loop never proposes an unimplemented type.

Combination semantics (declared): a combination is the equal-standing
union of its members' judged OOS trade streams — the pooled trade
list is judged exactly as a single stream's list would be. Members
must share panel AND timeframe. This is NOT the Stage-C daily-book
accounting (audit section 4 warns that accounting is not the live
sleeve's sizing either); capital contention between members is
arbitrated live by the lane's frozen heat caps, not by this judgement.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Any

from .bounds import DATA_WINDOW
from .store import StreamRecord

# ---------------------------------------------------------------------------
# Mechanism clusters — declared map, family -> cluster. The cluster-
# champion ensemble takes the strongest admitted stream of each
# declared cluster (owner, 2026-11-18: combinations beyond 2-3 members;
# 4-8 members by construction of this map).
# ---------------------------------------------------------------------------

FAMILY_CLUSTERS: dict[str, str] = {
    "vol_adaptive_trend": "trend",
    "ts_momentum": "trend",
    "tsmom2_dual": "trend",
    "macd_trend": "trend",
    "ichimoku_trend": "trend",
    "bollinger_trend": "trend",
    "donchian_turtle": "trend",
    "turtle2": "trend",
    "shock_breakout": "breakout",
    "keltner_breakout": "breakout",
    "volume_breakout": "breakout",
    "stoch_reversion": "reversion",
    "rsi_momentum": "reversion",
    "zscore_reversion": "reversion",
    "fx_meanrev": "reversion",
    "vol_compression": "volatility",
    "vol_regime_trend": "volatility",
    "ha_trend": "pattern",
    "bar_patterns": "pattern",
}

DECLARED_CLUSTERS = ("trend", "breakout", "reversion", "volatility", "pattern")

#: Greedy forward selection never builds a set larger than this.
GREEDY_MAX_MEMBERS = 10


@dataclass(frozen=True)
class ExperimentType:
    name: str
    brief_family: str  # "a" parameter variants | "b" combinations | "c" exit/sizing/gate
    implemented: bool
    note: str


EXPERIMENT_TYPES: tuple[ExperimentType, ...] = (
    ExperimentType(
        "combination_pair", "b", True,
        "Two admitted streams, same panel+timeframe, pooled OOS trades.",
    ),
    ExperimentType(
        "combination_triple", "b", True,
        "Three admitted streams, same panel+timeframe, pooled OOS trades.",
    ),
    ExperimentType(
        "combination_cluster_champions", "b", True,
        "Champion (highest recorded PF) of each declared mechanism "
        "cluster in the group, combined — 4-8 members by construction.",
    ),
    ExperimentType(
        "combination_greedy_forward", "b", True,
        "Greedy forward selection from the group's strongest stream, "
        "up to 10 members; every candidate evaluation is a counted "
        "trial; only the final set is judged for admission.",
    ),
    ExperimentType(
        "parameter_variant", "a", False,
        "New parameter variants of existing families within "
        "pre-declared grids. Declared, NOT implemented in slice 1: "
        "needs the harness re-runner over stored market data "
        "(follow-up slice).",
    ),
    ExperimentType(
        "exit_sizing_gate_variant", "c", False,
        "Exit/sizing/regime-gate variants of live streams. Declared, "
        "NOT implemented in slice 1: needs the harness re-runner "
        "(follow-up slice). Sizing here means the judged bracket/"
        "overlay shape under test — never the lane's risk parameters, "
        "which bounds.py puts outside the loop's reach entirely.",
    ),
)

TYPES_BY_NAME = {t.name: t for t in EXPERIMENT_TYPES}


@dataclass(frozen=True)
class Proposal:
    """One declarable experiment. to_dict() is the ledger form."""

    experiment_type: str
    members: tuple[str, ...]
    panel: str
    timeframe: str
    hypothesis: str
    candidate_pool: tuple[str, ...] = ()  # greedy only: streams it may add

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_type": self.experiment_type,
            "members": list(self.members),
            "candidate_pool": list(self.candidate_pool),
            "panel": self.panel,
            "timeframe": self.timeframe,
            "hypothesis": self.hypothesis,
            "data_window": DATA_WINDOW,
        }


def cluster_of(record: StreamRecord) -> str:
    return FAMILY_CLUSTERS.get(record.family, record.cluster or "other")


def _hypothesis(kind: str, members: tuple[str, ...], panel: str, tf: str) -> str:
    joined = " + ".join(members)
    return (
        f"Combining {joined} (@ {panel} {tf}) as an equal-standing union "
        f"of their judged OOS trade streams will clear the frozen bar "
        f"better than the members' individual records suggest, because "
        f"the member mechanisms differ ({kind}). Judged pooled, "
        f"pre-declared, on {DATA_WINDOW}."
    )


def group_proposals(
    panel: str, timeframe: str, records: list[StreamRecord]
) -> list[Proposal]:
    """All slice-1 proposals for one (panel, timeframe) group, in the
    loop's deterministic order: cluster champions, pairs, triples,
    greedy. The loop takes the first undeclared one each cycle."""
    records = sorted(records, key=lambda r: r.stream_id)
    ids = tuple(r.stream_id for r in records)
    proposals: list[Proposal] = []

    champions: list[StreamRecord] = []
    for cluster in DECLARED_CLUSTERS:
        members = [r for r in records if cluster_of(r) == cluster]
        if members:
            champions.append(max(members, key=lambda r: r.recorded_pf))
    if len(champions) >= 2:
        member_ids = tuple(c.stream_id for c in champions)
        proposals.append(
            Proposal(
                experiment_type="combination_cluster_champions",
                members=member_ids,
                panel=panel,
                timeframe=timeframe,
                hypothesis=_hypothesis(
                    "one champion per mechanism cluster", member_ids, panel, timeframe
                ),
            )
        )

    for size, type_name in ((2, "combination_pair"), (3, "combination_triple")):
        for combo in combinations(ids, size):
            proposals.append(
                Proposal(
                    experiment_type=type_name,
                    members=tuple(combo),
                    panel=panel,
                    timeframe=timeframe,
                    hypothesis=_hypothesis(
                        f"{size}-stream combination", tuple(combo), panel, timeframe
                    ),
                )
            )

    if len(records) >= 3:
        seed = max(records, key=lambda r: r.recorded_pf)
        proposals.append(
            Proposal(
                experiment_type="combination_greedy_forward",
                members=(seed.stream_id,),
                candidate_pool=ids,
                panel=panel,
                timeframe=timeframe,
                hypothesis=_hypothesis(
                    "greedy forward selection (add the stream that most "
                    "improves pooled PF, up to 10 members)",
                    (seed.stream_id,),
                    panel,
                    timeframe,
                ),
            )
        )
    return proposals


def all_proposals(store) -> list[Proposal]:
    """Every proposal the catalogue can make over the store, in order."""
    out: list[Proposal] = []
    groups = store.groups()
    for panel, timeframe in sorted(groups):
        out.extend(group_proposals(panel, timeframe, groups[(panel, timeframe)]))
    return out
