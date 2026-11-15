"use client";

import { useEffect, useMemo, useState } from "react";
import Counter from "../reactbits/Counter";
import SpotlightCard from "../reactbits/SpotlightCard";
import { Reveal } from "./motion";
import {
  ageLabel,
  fetchFleet,
  fetchLive,
  oneLine,
  toneFor,
  type AgentsLiveSnapshot,
  type FleetSnapshot,
} from "@/lib/wire";

/* ================================================================
   The fleet, summoned — ten agents as living cards.
   Reachability and latency come from /api/agents/status; what
   each agent is doing right now comes from /api/agents/live.
   Numbers roll (React Bits Counter) instead of jumping, because
   a fleet that breathes is easier to read than one that blinks.
   Read-only: this layer reports the fleet, it does not drive it.
   ================================================================ */

const SPOTLIGHT_BY_TONE: Record<string, string> = {
  good: "rgba(56, 224, 193, 0.16)",
  warn: "rgba(251, 191, 36, 0.16)",
  bad: "rgba(248, 113, 113, 0.18)",
  muted: "rgba(148, 163, 184, 0.12)",
};

export function FleetSheet() {
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [live, setLive] = useState<AgentsLiveSnapshot | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [f, l] = await Promise.all([fetchFleet(), fetchLive()]);
        if (cancelled) return;
        setFleet(f);
        setLive(l);
        setFailed(false);
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    void load();
    const timer = window.setInterval(load, 12_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const liveById = useMemo(() => {
    const map = new Map<string, NonNullable<AgentsLiveSnapshot["agents"]>[number]>();
    for (const agent of live?.agents ?? []) map.set(agent.id, agent);
    return map;
  }, [live]);

  const answering = fleet?.agents.filter((a) => toneFor(a.status) === "good").length ?? 0;

  return (
    <div className="fleet">
      <p className="sheet-summary">
        {fleet ? (
          <>
            <Counter value={answering} fontSize={20} /> of {fleet.agent_count} answering
            {live ? <> · {live.ledger_total} delegations on the ledger</> : null}
          </>
        ) : failed ? (
          "The fleet didn't answer this time — the stage is still live underneath."
        ) : (
          "Asking the fleet…"
        )}
      </p>

      <div className="fleet-grid">
        {(fleet?.agents ?? []).map((agent, idx) => {
          const tone = toneFor(agent.status);
          const now = liveById.get(agent.id);
          return (
            <Reveal key={agent.id} delay={Math.min(idx, 8) * 60} className="fleet-reveal">
            <SpotlightCard className="fleet-card" spotlightColor={SPOTLIGHT_BY_TONE[tone]}>
              <div className="fleet-card-top">
                <div>
                  <h3 className="fleet-name">{agent.name}</h3>
                  <p className="fleet-role">{agent.role ?? ""}</p>
                </div>
                <span className={`pill tone-${tone}`}>{agent.status.toLowerCase()}</span>
              </div>
              <div className="fleet-meta">
                {typeof agent.latency_ms === "number" ? (
                  <span className="fleet-latency">
                    <Counter value={Math.round(agent.latency_ms)} fontSize={15} /> ms
                  </span>
                ) : (
                  <span className="fleet-latency">— ms</span>
                )}
                {agent.last_checked && <span className="fleet-age">checked {ageLabel(agent.last_checked) || "just now"}</span>}
              </div>
              <p className="fleet-now">
                {now?.in_flight
                  ? `Working: ${oneLine(now.in_flight.description, 110)}`
                  : now?.last_outcome
                    ? `Last: ${oneLine(now.last_outcome.description, 110)}`
                    : "Idle — nothing in flight."}
              </p>
            </SpotlightCard>
            </Reveal>
          );
        })}
      </div>
    </div>
  );
}
