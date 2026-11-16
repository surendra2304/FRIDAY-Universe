/* TASK-IG2-WEB-02 (wiring) — the fleet → RankBoard entry mapping.

   Pure functions, no React, no I/O, no imports: the sheet component
   (components/stage/RankSheet.tsx) fetches the fleet snapshot and this
   module turns it into the entries components/RankBoard.tsx ranks.
   The shapes are structurally identical to lib/ranking.ts's RankEntry,
   so entries pass straight through. Unit-testable on its own
   (lib/fleetRank.test.ts, run with plain `node`).

   The honesty rule from the toprank pattern the board adapts: a board
   ranks MEASUREMENTS, never a list someone typed once. An agent whose
   latency was not measured is not given a score, a zero, or a fake
   rank — it is left off the board and counted, so the sheet can say
   out loud how many agents are unranked and why. */

export interface FleetRankAgentLike {
  id: string;
  name: string;
  /** Measured response latency in ms, when the fleet probe got one. */
  latency_ms?: number;
}

export interface FleetRankEntry {
  id: string;
  name: string;
  /** The measured latency itself; lower is faster (board order "asc"). */
  score: number;
  scoreLabel: string;
  /** Rank in the previous snapshot, 1-based, when known. */
  previousRank?: number;
}

export interface FleetRankResult {
  entries: FleetRankEntry[];
  /** Agents with no measured latency — counted, never scored. */
  unmeasured: number;
}

export function fleetRankEntries(
  agents: readonly FleetRankAgentLike[],
  previousRanks?: ReadonlyMap<string, number>,
): FleetRankResult {
  const entries: FleetRankEntry[] = [];
  let unmeasured = 0;
  for (const agent of agents) {
    const latency = agent.latency_ms;
    if (typeof latency !== "number" || !Number.isFinite(latency) || latency < 0) {
      unmeasured += 1;
      continue;
    }
    const entry: FleetRankEntry = {
      id: agent.id,
      name: agent.name,
      score: latency,
      scoreLabel: `${Math.round(latency)} ms`,
    };
    const previous = previousRanks?.get(agent.id);
    if (previous != null) entry.previousRank = previous;
    entries.push(entry);
  }
  return { entries, unmeasured };
}
