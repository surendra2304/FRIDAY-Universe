"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  MapInterface,
  Parallax,
  Reveal,
  ScrollProgress,
  ScrollVideo,
  ShowcaseRows,
  useFeaturedPool,
  type ShowcaseItem,
  type ShowcaseRow,
} from "@/components/kit";
import { DEFAULT_SETTINGS } from "@/lib/glassWidgets";
import {
  ageLabel,
  fetchFleet,
  fetchLive,
  fetchTimeline,
  oneLine,
  type AgentsLiveSnapshot,
  type FleetSnapshot,
  type TimelineEvent,
} from "@/lib/wire";

/* ================================================================
   The UI kit demo (TASK-WEB-008 checkpoint 2). Every section
   exercises one kit component against REAL data or an honestly
   labelled sample — nothing is invented:

   - ScrollVideo scrubs a CC0 sample video (MDN), labelled as such.
   - ScrollPlaybook runs on a scrollable panel in this page.
   - ShowcaseRows is fed by the live fleet / timeline endpoints;
     when they don't answer, the rows say so.
   - MapInterface geocodes the house default city on mount.
   - GlassStartPage takes no props and is a full page — the demo
     links to /start instead of embedding it.
   ================================================================ */

const ROOMS: ShowcaseItem[] = [
  { id: "room-fleet", name: "The Fleet", role: "The crew in detail — status, latency, last words." },
  { id: "room-chronicle", name: "The Chronicle", role: "Everything asked, everything done, in order." },
  { id: "room-pulse", name: "Machine Pulse", role: "The box underneath it all, breathing." },
];

export function KitDemo() {
  const panelRef = useRef<HTMLDivElement | null>(null);
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [live, setLive] = useState<AgentsLiveSnapshot | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [fleetAsked, setFleetAsked] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
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
      if (!cancelled) setFleetAsked(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const agents = useMemo(() => fleet?.agents ?? [], [fleet]);
  const featuredPool = useFeaturedPool(agents);
  const liveById = useMemo(
    () => new Map((live?.agents ?? []).map((a) => [a.id.toLowerCase(), a])),
    [live],
  );

  const rows: ShowcaseRow[] = useMemo(
    () => [
      {
        title: "The crew",
        items: agents.map((agent) => {
          const liveAgent = liveById.get(agent.name.toLowerCase());
          const item: ShowcaseItem = {
            id: agent.name,
            name: agent.name,
            role: agent.role,
            status: agent.status,
            flag: liveAgent?.in_flight ? "working" : undefined,
          };
          if (typeof agent.latency_ms === "number") {
            item.meta = `${agent.latency_ms} ms`;
          }
          return item;
        }),
        emptyText: fleetAsked
          ? "The fleet didn't answer — no crew cards are invented in its place."
          : "Asking the fleet who is awake…",
      },
      {
        title: "The ledger",
        items: events.slice(0, 12).map((event) => ({
          id: event.task_id,
          name: event.owner_agent,
          role: oneLine(event.description, 110),
          status:
            event.chip === "done"
              ? "COMPLETED"
              : event.chip === "failed"
                ? "FAILED"
                : event.chip,
          meta: `${ageLabel(event.updated_at)} ago`,
        })),
        emptyText:
          "The ledger is quiet — nothing has been delegated lately, or it didn't answer.",
        wide: true,
      },
      {
        title: "The rooms",
        items: ROOMS,
        emptyText: "",
        wide: true,
      },
    ],
    [agents, events, fleetAsked, liveById],
  );

  return (
    <div style={{ maxWidth: 960, margin: "0 auto", padding: "32px 20px 64px" }}>
      <p className="sheet-note">FRIDAY UI kit — TASK-WEB-008</p>
      <h1 style={{ fontSize: 32, margin: "8px 0 4px" }}>UI kit</h1>
      <p className="sheet-note" style={{ marginBottom: 32 }}>
        Design-technique components for the FRIDAY site. Each section below
        exercises one kit component against real data or an honestly
        labelled sample.
      </p>

      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: 22, marginBottom: 8 }}>Scroll-driven video</h2>
        <p className="sheet-note" style={{ marginBottom: 12 }}>
          <code>ScrollVideo</code> — the video scrubs as this page scrolls.
          Sample video: CC0, MDN interactive examples.
        </p>
        <ScrollVideo
          src="https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
          caption="CC0 sample video (MDN)."
          label="Scroll-driven video demo"
          scrubPx={900}
        />
      </section>

      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: 22, marginBottom: 8 }}>Scroll playbook</h2>
        <p className="sheet-note" style={{ marginBottom: 12 }}>
          <code>Reveal</code>, <code>Parallax</code> and{" "}
          <code>ScrollProgress</code> — scroll the panel below.
        </p>
        <div
          style={{
            border: "1px solid var(--hair)",
            borderRadius: 12,
            overflow: "hidden",
          }}
        >
          <ScrollProgress scrollerRef={panelRef} />
          <div
            ref={panelRef}
            style={{ height: 320, overflowY: "auto", padding: 16 }}
          >
            <Reveal>
              <p>A reveal: this line rose into view as the panel scrolled.</p>
            </Reveal>
            <Parallax speed={0.08}>
              <p>A parallax layer: this line drifts against the scroll.</p>
            </Parallax>
            <Reveal delay={120}>
              <p>A delayed reveal, 120 ms stagger.</p>
            </Reveal>
            {[1, 2, 3, 4, 5].map((n) => (
              <Reveal key={n} delay={n * 40}>
                <p>Panel filler line {n} — keep scrolling.</p>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: 22, marginBottom: 8 }}>Showcase rows</h2>
        <p className="sheet-note" style={{ marginBottom: 12 }}>
          <code>ShowcaseRows</code> — billboard + browsable rows over the
          live fleet and timeline. Selecting a card names it below; it
          opens nothing in the demo.
        </p>
        <ShowcaseRows
          featuredPool={featuredPool.map((agent) => ({
            id: agent.name,
            name: agent.name,
            role: agent.role,
            status: agent.status,
            meta:
              typeof agent.latency_ms === "number"
                ? `${agent.latency_ms} ms`
                : undefined,
          }))}
          featuredKicker="Now answering"
          featuredCta="Select"
          rows={rows}
          onSelect={(item) => setSelected(`${item.name} — ${item.role}`)}
        />
        {selected && (
          <p className="sheet-note" role="status" style={{ paddingTop: 8 }}>
            Selected: {selected}
          </p>
        )}
      </section>

      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: 22, marginBottom: 8 }}>Map interface</h2>
        <p className="sheet-note" style={{ marginBottom: 12 }}>
          <code>MapInterface</code> — Nominatim search + OpenStreetMap
          embed, no key. Centred on the house default city (
          {DEFAULT_SETTINGS.city}) until you search.
        </p>
        <MapInterface defaultQuery={DEFAULT_SETTINGS.city} />
      </section>

      <section style={{ marginBottom: 48 }}>
        <h2 style={{ fontSize: 22, marginBottom: 8 }}>Glass start page</h2>
        <p className="sheet-note" style={{ marginBottom: 12 }}>
          <code>GlassStartPage</code> takes no props and is a full page —
          the kit re-exports it unchanged. See it live at{" "}
          <Link href="/start">/start</Link>.
        </p>
      </section>
    </div>
  );
}
