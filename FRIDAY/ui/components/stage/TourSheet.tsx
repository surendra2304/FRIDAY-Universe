"use client";

import { useEffect, useRef, useState } from "react";
import {
  fetchAutonomy,
  fetchFleet,
  fetchLive,
  fetchTelemetry,
  type AutonomySnapshot,
  type FleetSnapshot,
  type HostTelemetry,
} from "@/lib/wire";
import { Reveal } from "./motion";

/* ================================================================
   The Guided Tour, summoned (TASK-IG-WEB-06).

   Source idea (IG reference corpus, DcBGh30yOLW): a cinematic
   full-bleed hero with a guided-tour scroll narrative. The
   tour lives inside this layer — Halo's voice-first home is
   the live design and is not rebuilt into a landing page.

   Inside: a serif hero, one amber call to action, then five
   numbered chapters that reveal as the sheet scrolls. Each
   chapter carries a live fact chip ONLY when its endpoint
   actually answered (no chip is better than an invented
   number), and a call to action that summons the real layer
   the chapter describes.

   Reveal-on-scroll uses TASK-IG-WEB-01's shared motion layer
   (motion.tsx, PR #482): the chapters rise into view via its
   Reveal, the same component the fleet sheet uses. This sheet
   originally carried a local copy because #482 had not merged
   when it branched; the swap to the shared Reveal was made
   once #482 was on main (WEB-06 follow-up).
   ================================================================ */

type RoomKind = "fleet" | "chronicle" | "pulse";

interface Facts {
  fleet: FleetSnapshot | null;
  ledgerTotal: number | null;
  telemetry: HostTelemetry | null;
  autonomy: AutonomySnapshot | null;
}

export function TourSheet({ onSummon }: { onSummon: (kind: RoomKind) => void }) {
  const [facts, setFacts] = useState<Facts>({ fleet: null, ledgerTotal: null, telemetry: null, autonomy: null });
  const firstChapterRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [fleet, live, telemetry, autonomy] = await Promise.allSettled([
        fetchFleet(),
        fetchLive(),
        fetchTelemetry(),
        fetchAutonomy(),
      ]);
      if (cancelled) return;
      setFacts({
        fleet: fleet.status === "fulfilled" ? fleet.value : null,
        ledgerTotal: live.status === "fulfilled" ? live.value.ledger_total : null,
        telemetry: telemetry.status === "fulfilled" ? telemetry.value : null,
        autonomy: autonomy.status === "fulfilled" ? autonomy.value : null,
      });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const answering = facts.fleet?.agents.filter((a) => a.status === "online").length;
  const crewTotal = facts.fleet?.agents.length;
  const recentMoves = facts.autonomy?.recent_actions?.length;

  const begin = () => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    firstChapterRef.current?.scrollIntoView({ behavior: reduced ? "auto" : "smooth", block: "start" });
  };

  return (
    <div className="tour">
      <section className="tour-hero">
        <p className="tour-hero-chip">EST. 2026 · ONE ROOM, TEN MINDS</p>
        <h3 className="tour-hero-title">Meet FRIDAY.</h3>
        <p className="tour-hero-sub">
          Not an app with a chatbot in it — a room that listens, remembers, and sends a crew of ten
          specialists out to do the work. This is the short tour.
        </p>
        <button type="button" className="tour-cta" onClick={begin}>
          Begin the tour
        </button>
      </section>

      <div ref={firstChapterRef} className="tour-anchor" aria-hidden="true" />

      <Reveal>
        <section className="tour-chapter">
          <p className="tour-chapter-num">01</p>
          <h4 className="tour-chapter-title">Voice first</h4>
          <p className="tour-chapter-body">
            The room is built around talking. Tap the halo, or start the voice line from the veil,
            and speak the way you would to a person — FRIDAY answers out loud, remembers what
            matters, and delegates the rest. Typing is the fallback, never the point.
          </p>
          <p className="tour-chapter-note">Close this tour and tap the halo on the stage to try it.</p>
        </section>
      </Reveal>

      <Reveal>
        <section className="tour-chapter">
          <p className="tour-chapter-num">02</p>
          <h4 className="tour-chapter-title">The crew</h4>
          <p className="tour-chapter-body">
            Ten specialists share the work: memory, markets, research, building, watching. FRIDAY
            routes each request to the mind built for it and reports back in one voice.
          </p>
          {typeof answering === "number" && crewTotal ? (
            <p className="tour-fact">
              Right now: <b>{answering} of {crewTotal}</b> are answering
            </p>
          ) : null}
          <button type="button" className="tour-link" onClick={() => onSummon("fleet")}>
            Meet them in the Fleet →
          </button>
        </section>
      </Reveal>

      <Reveal>
        <section className="tour-chapter">
          <p className="tour-chapter-num">03</p>
          <h4 className="tour-chapter-title">The ledger</h4>
          <p className="tour-chapter-body">
            Nothing is done in the dark. Every delegation — who took it, what came of it, what
            failed — is written to a chronicle you can open at any time.
          </p>
          {typeof facts.ledgerTotal === "number" ? (
            <p className="tour-fact">
              On record: <b>{facts.ledgerTotal}</b> delegations
            </p>
          ) : null}
          <button type="button" className="tour-link" onClick={() => onSummon("chronicle")}>
            Read the Chronicle →
          </button>
        </section>
      </Reveal>

      <Reveal>
        <section className="tour-chapter">
          <p className="tour-chapter-num">04</p>
          <h4 className="tour-chapter-title">The machine</h4>
          <p className="tour-chapter-body">
            All of it runs on two small cloud servers — no datacentre theatre. The pulse layer
            shows the host&apos;s real vitals, the voice service, and whether the boxes are
            keeping up.
          </p>
          {typeof facts.telemetry?.cpu_percent === "number" ? (
            <p className="tour-fact">
              Host right now: <b>{Math.round(facts.telemetry.cpu_percent)}%</b> CPU
              {typeof facts.telemetry.ram_percent === "number" ? (
                <>
                  {" "}· <b>{Math.round(facts.telemetry.ram_percent)}%</b> RAM
                </>
              ) : null}
            </p>
          ) : null}
          <button type="button" className="tour-link" onClick={() => onSummon("pulse")}>
            Check the Machine Pulse →
          </button>
        </section>
      </Reveal>

      <Reveal>
        <section className="tour-chapter">
          <p className="tour-chapter-num">05</p>
          <h4 className="tour-chapter-title">The watch</h4>
          <p className="tour-chapter-body">
            When nobody is asking, FRIDAY is not idle — within the bounds the owner sets, it
            watches, checks, and prepares. Its autonomous moves are logged in the same pulse
            layer, in the open.
          </p>
          {typeof recentMoves === "number" && recentMoves > 0 ? (
            <p className="tour-fact">
              Recent autonomous moves on record: <b>{recentMoves}</b>
            </p>
          ) : null}
          <button type="button" className="tour-link" onClick={() => onSummon("pulse")}>
            See the watch in Machine Pulse →
          </button>
        </section>
      </Reveal>

      <Reveal>
        <p className="tour-end">
          That is the whole tour. Everything you just read about is one veil away — press
          <b> Everything else</b>, or hit Ctrl/⌘-K, anywhere on the stage.
        </p>
      </Reveal>
    </div>
  );
}
