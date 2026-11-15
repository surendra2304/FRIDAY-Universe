"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ageLabel,
  fetchFleet,
  fetchLive,
  fetchTimeline,
  oneLine,
  toneFor,
  type AgentsLiveSnapshot,
  type FleetAgent,
  type FleetSnapshot,
  type TimelineEvent,
} from "@/lib/wire";

/* ================================================================
   The Showcase, summoned (TASK-IG-WEB-05).

   Source idea (IG reference corpus, DePJT2NJvz_): a
   Netflix-style cinematic showcase — a billboard and browsable
   rows — applied to the universe itself. The catalogue is the
   real one: the billboard features an agent the fleet endpoint
   says is online, the crew row is the fleet, the ledger row is
   the delegation timeline, and the rooms row opens this
   stage's own layers. Nothing is stock footage; when an
   endpoint doesn't answer, the row says so.

   Cards summon the real layers through Stage's onSummon —
   the showcase is a browsing front-end over the room, not a
   parallel UI with its own copies of the data.
   ================================================================ */

type RoomKind = "fleet" | "chronicle" | "pulse";

const HUES: Record<string, number> = {
  friday: 222,
  inference: 199,
  memora: 262,
  stratex: 152,
  futuris: 280,
  intelx: 190,
  forge: 24,
  sentinel: 210,
  cortex: 330,
  vyralx: 350,
};

function hueFor(name: string): number {
  const known = HUES[name.toLowerCase()];
  if (known !== undefined) return known;
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
  return h;
}

function posterStyle(name: string): React.CSSProperties {
  const hue = hueFor(name);
  return {
    background: `linear-gradient(150deg, hsl(${hue} 70% 26%) 0%, hsl(${(hue + 40) % 360} 65% 12%) 78%)`,
  };
}

export function ShowcaseSheet({ onSummon }: { onSummon: (kind: RoomKind) => void }) {
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [live, setLive] = useState<AgentsLiveSnapshot | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [featuredIdx, setFeaturedIdx] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setReducedMotion(window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    let cancelled = false;
    (async () => {
      try {
        const snap = await fetchFleet();
        if (!cancelled) setFleet(snap);
      } catch {
        /* the rows render their own honest empties */
      }
      try {
        const snap = await fetchLive();
        if (!cancelled) setLive(snap);
      } catch {
        /* live detail is an enhancement on the cards */
      }
      try {
        const snap = await fetchTimeline();
        if (!cancelled) setEvents(snap.events ?? []);
      } catch {
        /* ledger row says so */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const agents = useMemo(() => fleet?.agents ?? [], [fleet]);
  const featuredPool = useMemo(() => {
    const online = agents.filter((a) => a.status === "online");
    return online.length > 0 ? online : agents;
  }, [agents]);

  /* The billboard rotates through whoever is awake — slowly,
     never under reduced motion, never behind a hidden tab. */
  useEffect(() => {
    if (reducedMotion || featuredPool.length < 2) return;
    const timer = window.setInterval(() => {
      if (document.hidden) return;
      setFeaturedIdx((idx) => (idx + 1) % featuredPool.length);
    }, 7000);
    return () => window.clearInterval(timer);
  }, [featuredPool, reducedMotion]);

  const featured: FleetAgent | undefined = featuredPool[featuredIdx % Math.max(featuredPool.length, 1)];
  const liveById = useMemo(
    () => new Map((live?.agents ?? []).map((a) => [a.id.toLowerCase(), a])),
    [live],
  );

  const rooms: Array<{ kind: RoomKind; name: string; blurb: string }> = [
    { kind: "fleet", name: "The Fleet", blurb: "The crew in detail — status, latency, last words." },
    { kind: "chronicle", name: "The Chronicle", blurb: "Everything asked, everything done, in order." },
    { kind: "pulse", name: "Machine Pulse", blurb: "The box underneath it all, breathing." },
  ];

  return (
    <div className="showcase">
      {featured ? (
        <section className="showcase-billboard" style={posterStyle(featured.name)} key={featured.name}>
          <p className="showcase-billboard-kicker">Now answering</p>
          <h3 className="showcase-billboard-name">{featured.name}</h3>
          <p className="showcase-billboard-role">{featured.role}</p>
          <div className="showcase-billboard-meta">
            <span className={`pill tone-${toneFor(featured.status)}`}>{featured.status}</span>
            {typeof featured.latency_ms === "number" && (
              <span className="showcase-latency">{featured.latency_ms} ms</span>
            )}
            {featuredPool.length > 1 && (
              <span className="showcase-dots" role="tablist" aria-label="Featured agent">
                {featuredPool.map((agent, idx) => (
                  <button
                    key={agent.name}
                    type="button"
                    role="tab"
                    aria-selected={idx === featuredIdx % featuredPool.length}
                    aria-label={`Feature ${agent.name}`}
                    className={`showcase-dot ${idx === featuredIdx % featuredPool.length ? "is-on" : ""}`}
                    onClick={() => setFeaturedIdx(idx)}
                  />
                ))}
              </span>
            )}
          </div>
          <button type="button" className="showcase-cta" onClick={() => onSummon("fleet")}>
            Open the fleet
          </button>
        </section>
      ) : (
        <p className="sheet-note">{fleet ? "No agent is answering to feature right now." : "Asking the fleet who is awake…"}</p>
      )}

      <section className="showcase-row-block">
        <h4 className="showcase-row-title">The crew</h4>
        {agents.length > 0 ? (
          <div className="showcase-row">
            {agents.map((agent) => {
              const liveAgent = liveById.get(agent.name.toLowerCase());
              return (
                <button
                  key={agent.name}
                  type="button"
                  className="showcase-card"
                  onClick={() => onSummon("fleet")}
                  aria-label={`Open the fleet at ${agent.name}`}
                >
                  <span className="showcase-poster" style={posterStyle(agent.name)} aria-hidden="true">
                    {agent.name.slice(0, 1)}
                  </span>
                  <span className="showcase-card-name">{agent.name}</span>
                  <span className="showcase-card-role">{agent.role}</span>
                  <span className="showcase-card-meta">
                    <span className={`pill tone-${toneFor(agent.status)}`}>{agent.status}</span>
                    {liveAgent?.in_flight && <span className="showcase-working">working</span>}
                  </span>
                </button>
              );
            })}
          </div>
        ) : (
          <p className="sheet-note">The fleet didn&apos;t answer — no crew cards are invented in its place.</p>
        )}
      </section>

      <section className="showcase-row-block">
        <h4 className="showcase-row-title">The ledger</h4>
        {events.length > 0 ? (
          <div className="showcase-row">
            {events.slice(0, 12).map((event) => (
              <button
                key={event.task_id}
                type="button"
                className="showcase-card is-wide"
                onClick={() => onSummon("chronicle")}
                aria-label={`Open the chronicle at ${event.owner_agent}`}
              >
                <span className="showcase-card-name">{event.owner_agent}</span>
                <span className="showcase-card-role">{oneLine(event.description, 110)}</span>
                <span className="showcase-card-meta">
                  <span
                    className={`pill tone-${toneFor(event.chip === "done" ? "COMPLETED" : event.chip === "failed" ? "FAILED" : event.chip)}`}
                  >
                    {event.chip}
                  </span>
                  <span className="showcase-latency">{ageLabel(event.updated_at)} ago</span>
                </span>
              </button>
            ))}
          </div>
        ) : (
          <p className="sheet-note">The ledger is quiet — nothing has been delegated lately, or it didn&apos;t answer.</p>
        )}
      </section>

      <section className="showcase-row-block">
        <h4 className="showcase-row-title">The rooms</h4>
        <div className="showcase-row">
          {rooms.map((room) => (
            <button
              key={room.kind}
              type="button"
              className="showcase-card is-wide"
              onClick={() => onSummon(room.kind)}
              aria-label={`Open ${room.name}`}
            >
              <span className="showcase-poster" style={posterStyle(room.name)} aria-hidden="true">
                {room.name.split(" ").pop()?.slice(0, 1)}
              </span>
              <span className="showcase-card-name">{room.name}</span>
              <span className="showcase-card-role">{room.blurb}</span>
            </button>
          ))}
        </div>
      </section>
    </div>
  );
}
