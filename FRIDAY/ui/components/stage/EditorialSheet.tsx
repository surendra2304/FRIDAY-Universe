"use client";

import { useEffect, useMemo, useState } from "react";
import {
  clockTime,
  fetchFleet,
  fetchLive,
  oneLine,
  type AgentsLiveSnapshot,
  type FleetAgent,
  type FleetSnapshot,
} from "@/lib/wire";

/* ================================================================
   The Editorial Edition, summoned (TASK-IG-WEB-08).

   Source idea (IG reference corpus, DfcHcbDOyJm): the NOOLAM
   editorial layout language — a serif masthead, a styled
   "Meet the…" feature with an itemised spec sidebar, a
   centred spotlight carousel with a FRONT/BACK detail toggle,
   and a tilted card row.

   Applied here to the crew, on an ivory page that exists only
   inside this layer (the palette is scoped to the sheet; the
   room outside stays Halo dark). The "specs" are the fleet's
   real figures — role, status, port, latency, last checked —
   labelled as what they are. There are no prices: nothing on
   this page is for sale, and no figure is dressed up as one.
   ================================================================ */

/* The fleet's published ports (AGENTS.yaml v3.0.0). */
const PORTS: Record<string, number> = {
  friday: 10000,
  inference: 8001,
  memora: 8002,
  stratex: 8003,
  futuris: 8004,
  intelx: 8005,
  forge: 8006,
  sentinel: 8008,
  cortex: 8009,
  vyralx: 8010,
};

type Filter = "all" | "online" | "working";

export function EditorialSheet() {
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [live, setLive] = useState<AgentsLiveSnapshot | null>(null);
  const [spotId, setSpotId] = useState<string>("friday");
  const [back, setBack] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const snap = await fetchFleet();
        if (!cancelled) setFleet(snap);
      } catch {
        /* masthead over an honest notice */
      }
      try {
        const snap = await fetchLive();
        if (!cancelled) setLive(snap);
      } catch {
        /* working detail simply absent */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const agents = useMemo(() => fleet?.agents ?? [], [fleet]);
  const liveById = useMemo(
    () => new Map((live?.agents ?? []).map((a) => [a.id.toLowerCase(), a])),
    [live],
  );

  const featured: FleetAgent | undefined =
    agents.find((a) => a.status === "online") ?? agents[0];
  const spotlight: FleetAgent | undefined =
    agents.find((a) => a.name.toLowerCase() === spotId) ?? featured;
  const spotlightLive = spotlight ? liveById.get(spotlight.name.toLowerCase()) : undefined;
  const featuredLive = featured ? liveById.get(featured.name.toLowerCase()) : undefined;

  const visible = agents.filter((agent) => {
    if (filter === "online") return agent.status === "online";
    if (filter === "working") return Boolean(liveById.get(agent.name.toLowerCase())?.in_flight);
    return true;
  });

  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "Asia/Kolkata",
  });

  const step = (dir: 1 | -1) => {
    if (agents.length === 0) return;
    const idx = agents.findIndex((a) => a.name.toLowerCase() === spotlight?.name.toLowerCase());
    const next = agents[(idx + dir + agents.length) % agents.length];
    setSpotId(next.name.toLowerCase());
    setBack(false);
  };

  const specRows = (agent: FleetAgent, liveAgent?: AgentsLiveSnapshot["agents"][number]) => [
    { label: "Role", value: agent.role },
    { label: "Status", value: agent.status },
    { label: "Port", value: PORTS[agent.name.toLowerCase()] ? `:${PORTS[agent.name.toLowerCase()]}` : "—" },
    { label: "Latency", value: typeof agent.latency_ms === "number" ? `${agent.latency_ms} ms` : "—" },
    { label: "Last checked", value: liveAgent?.last_checked ? clockTime(liveAgent.last_checked) : "—" },
  ];

  return (
    <div className="editorial">
      <header className="editorial-masthead">
        <p className="editorial-dateline">{today} · The daily edition</p>
        <h3 className="editorial-title">THE UNIVERSE</h3>
        <p className="editorial-tagline">Ten minds, one room — the crew, presented properly.</p>
      </header>

      {!fleet ? (
        <p className="editorial-notice">
          The fleet hasn&apos;t answered, so this edition carries no specs — an editorial page
          does not invent its figures.
        </p>
      ) : (
        <>
          {featured && (
            <section className="editorial-feature">
              <div className="editorial-feature-main">
                <p className="editorial-kicker">Meet the Crew · No. 1</p>
                <h4 className="editorial-feature-name">{featured.name}</h4>
                <p className="editorial-feature-role">{featured.role}</p>
                <p className="editorial-feature-body">
                  {featured.name} is {featured.status === "online" ? "awake and answering" : "quiet"} at the
                  time of this edition
                  {featuredLive?.in_flight
                    ? `, and is at work right now: ${oneLine(featuredLive.in_flight.description, 120)}`
                    : featuredLive?.last_outcome
                      ? `; its last recorded work was ${oneLine(featuredLive.last_outcome.description, 120)}`
                      : ""}
                  .
                </p>
              </div>
              <aside className="editorial-spec" aria-label={`${featured.name} specifications`}>
                <p className="editorial-spec-head">Specifications</p>
                <dl>
                  {specRows(featured, featuredLive).map((row) => (
                    <div key={row.label} className="editorial-spec-row">
                      <dt>{row.label}</dt>
                      <dd>{row.value}</dd>
                    </div>
                  ))}
                </dl>
              </aside>
            </section>
          )}

          {spotlight && (
            <section className="editorial-spotlight-block">
              <p className="editorial-kicker is-centred">The Spotlight</p>
              <div className="editorial-carousel">
                <button type="button" className="editorial-arrow" onClick={() => step(-1)} aria-label="Previous agent">
                  ←
                </button>
                <article className="editorial-spotlight">
                  {!back ? (
                    <>
                      <p className="editorial-spot-name">{spotlight.name}</p>
                      <p className="editorial-spot-role">{spotlight.role}</p>
                      <p className={`editorial-status is-${spotlight.status === "online" ? "on" : "off"}`}>
                        {spotlight.status === "online" ? "● Answering now" : `○ ${spotlight.status}`}
                      </p>
                    </>
                  ) : (
                    <dl className="editorial-spot-back">
                      {specRows(spotlight, spotlightLive).map((row) => (
                        <div key={row.label} className="editorial-spec-row">
                          <dt>{row.label}</dt>
                          <dd>{row.value}</dd>
                        </div>
                      ))}
                      <div className="editorial-spec-row">
                        <dt>Current task</dt>
                        <dd>
                          {spotlightLive?.in_flight
                            ? oneLine(spotlightLive.in_flight.description, 90)
                            : "Nothing in flight"}
                        </dd>
                      </div>
                    </dl>
                  )}
                  <button type="button" className="editorial-flip" onClick={() => setBack((b) => !b)}>
                    {back ? "FRONT" : "BACK"} ⤾
                  </button>
                </article>
                <button type="button" className="editorial-arrow" onClick={() => step(1)} aria-label="Next agent">
                  →
                </button>
              </div>
            </section>
          )}

          <section className="editorial-row-block">
            <div className="editorial-row-head">
              <p className="editorial-kicker">The Full Roster</p>
              <div className="editorial-filters" role="tablist" aria-label="Filter the roster">
                {(["all", "online", "working"] as Filter[]).map((f) => (
                  <button
                    key={f}
                    type="button"
                    role="tab"
                    aria-selected={filter === f}
                    className={`editorial-chip ${filter === f ? "is-on" : ""}`}
                    onClick={() => setFilter(f)}
                  >
                    {f === "all" ? "All ten" : f === "online" ? "Answering" : "At work"}
                  </button>
                ))}
              </div>
            </div>
            {visible.length > 0 ? (
              <div className="editorial-row">
                {visible.map((agent, idx) => (
                  <button
                    key={agent.name}
                    type="button"
                    className="editorial-card"
                    style={{ transform: `rotate(${((idx % 5) - 2) * 1.1}deg)` }}
                    onClick={() => {
                      setSpotId(agent.name.toLowerCase());
                      setBack(false);
                    }}
                    aria-label={`Spotlight ${agent.name}`}
                  >
                    <span className="editorial-card-name">{agent.name}</span>
                    <span className="editorial-card-role">{agent.role}</span>
                    <span className={`editorial-card-status is-${agent.status === "online" ? "on" : "off"}`}>
                      {agent.status}
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <p className="editorial-notice">Nobody matches that filter at the time of this edition.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
