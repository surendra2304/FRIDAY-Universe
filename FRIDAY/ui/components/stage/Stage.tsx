"use client";

import { Layers } from "lucide-react";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import SplitText from "../reactbits/SplitText";
import Magnet from "../reactbits/Magnet";
import type { VoiceLinkControls, VoicePhase } from "../VoiceCall";
import { Halo } from "./Halo";
import { Ambience } from "./Ambience";
import { Conversation } from "./Conversation";
import { Veil, type VeilCommand } from "./Veil";
import { Sheet } from "./Sheet";
import { fetchFleet, openActivitySocket, toneFor, type FleetSnapshot } from "@/lib/wire";
import { getWakeArmedSnapshot, setWakeArmedPref, subscribeWakeArmed } from "@/lib/wakeWord";

/* The voice line (LiveKit) and the three sheets are lazy chunks:
   the stage paints and breathes on the small core bundle, and
   the heavy machinery streams in behind it. The sheets only
   exist when summoned, so they only load when summoned. */
const VoiceCall = dynamic(() => import("../VoiceCall").then((m) => m.VoiceCall), { ssr: false });
const WakeListener = dynamic(() => import("./WakeListener").then((m) => m.WakeListener), { ssr: false });
const FleetSheet = dynamic(() => import("./FleetSheet").then((m) => m.FleetSheet), { ssr: false });
const ChronicleSheet = dynamic(() => import("./ChronicleSheet").then((m) => m.ChronicleSheet), { ssr: false });
const PulseSheet = dynamic(() => import("./PulseSheet").then((m) => m.PulseSheet), { ssr: false });
const LifeSheet = dynamic(() => import("./LifeSheet").then((m) => m.LifeSheet), { ssr: false });
const GalaxySheet = dynamic(() => import("./GalaxySheet").then((m) => m.GalaxySheet), { ssr: false });
const ShowcaseSheet = dynamic(() => import("./ShowcaseSheet").then((m) => m.ShowcaseSheet), { ssr: false });
const TourSheet = dynamic(() => import("./TourSheet").then((m) => m.TourSheet), { ssr: false });
const CitySheet = dynamic(() => import("./CitySheet").then((m) => m.CitySheet), { ssr: false });
const EditorialSheet = dynamic(() => import("./EditorialSheet").then((m) => m.EditorialSheet), { ssr: false });

/* ================================================================
   The stage (TASK-WEB-002) — the whole app is this one room.

   A black stage, a living light at its centre, the conversation
   flowing underneath it, and ten small lights breathing around
   the rim — one per agent, so the fleet is glanceable without
   opening anything. There are no other screens. Everything else
   (the fleet in detail, the chronicle, the machine's pulse) is
   summoned over this stage through one veil and sinks back into
   it; the stage — and any live call on it — never unmounts.

   The wordmark, the pill in the corner, a swipe up from the
   halo, or Cmd/Ctrl-K all open the same veil.
   ================================================================ */

type SheetKind = "fleet" | "chronicle" | "pulse" | "life" | "galaxy" | "showcase" | "tour" | "city" | "editorial";

const SHEET_HEADS: Record<SheetKind, { kicker: string; title: string }> = {
  fleet: { kicker: "The crew, in detail", title: "The Fleet" },
  chronicle: { kicker: "Everything asked, everything done", title: "The Chronicle" },
  pulse: { kicker: "The box underneath it all", title: "Machine Pulse" },
  life: { kicker: "Your time, as a grid of dots", title: "Life in Weeks" },
  galaxy: { kicker: "What FRIDAY remembers, as a sky", title: "Memory Galaxy" },
  showcase: { kicker: "The universe, browsable", title: "The Showcase" },
  tour: { kicker: "New here? Start with the story", title: "The Guided Tour" },
  city: { kicker: "The universe as a place", title: "The City" },
  editorial: { kicker: "The crew, presented properly", title: "The Editorial Edition" },
};

export function Stage() {
  const [voicePhase, setVoicePhase] = useState<VoicePhase>("resting");
  /* The opt-in wake word (FRIDAY/docs/WAKE_WORD.md): off by default,
     persisted in localStorage, read through useSyncExternalStore so the
     server render and the first client render agree on "off". */
  const wakeArmed = useSyncExternalStore(subscribeWakeArmed, getWakeArmedSnapshot, () => false);
  const [wakeNote, setWakeNote] = useState<string | null>(null);
  const [chatBusy, setChatBusy] = useState(false);
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [fleetOk, setFleetOk] = useState(false);
  const [flaring, setFlaring] = useState<ReadonlySet<string>>(new Set());
  const [veilOpen, setVeilOpen] = useState(false);
  const [sheet, setSheet] = useState<SheetKind | null>(null);
  /* The ambient sky (IG-WEB-04) is opt-in and off by default:
     Halo's home look is the live design and does not change
     uninvited. The choice lives in this browser only. */
  const [ambienceOn, setAmbienceOn] = useState(false);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setAmbienceOn(window.localStorage.getItem("friday.ambience") === "on");
  }, []);

  const toggleAmbience = useCallback(() => {
    setAmbienceOn((on) => {
      window.localStorage.setItem("friday.ambience", on ? "off" : "on");
      return !on;
    });
  }, []);
  const linkRef = useRef<VoiceLinkControls | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const haloTouchY = useRef<number | null>(null);

  const stagePhase: VoicePhase =
    voicePhase === "resting" || voicePhase === "down" ? (chatBusy ? "thinking" : voicePhase) : voicePhase;

  /* The rim lights need the fleet even when no sheet is open. */
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const snap = await fetchFleet();
        if (cancelled) return;
        setFleet(snap);
        setFleetOk(true);
      } catch {
        if (!cancelled) setFleetOk(false);
      }
    };
    void load();
    const timer = window.setInterval(load, 20_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  /* Live activity makes the rim breathe: a working agent's light
     flares as its frames arrive, then settles after ~2.6 s. */
  useEffect(() => {
    const timers = new Set<number>();
    const socket = openActivitySocket((frame) => {
      const who = (frame.agent || frame.agents_involved || "").toLowerCase();
      if (!who) return;
      setFlaring((current) => new Set(current).add(who));
      const timer = window.setTimeout(() => {
        setFlaring((current) => {
          const next = new Set(current);
          next.delete(who);
          return next;
        });
        timers.delete(timer);
      }, 2600);
      timers.add(timer);
    });
    return () => {
      socket?.close();
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, []);

  /* Cmd/Ctrl-K summons the veil from anywhere. */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setVeilOpen((open) => !open);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const openSheet = useCallback((kind: SheetKind) => setSheet(kind), []);

  const callLive = voicePhase === "opening" || voicePhase === "listening" || voicePhase === "thinking" || voicePhase === "speaking";

  const commands = useMemo<VeilCommand[]>(
    () => [
      {
        id: "fleet",
        label: "Look at the fleet",
        hint: "who is awake, who is working, how fast they answer",
        keys: "agents crew status online latency stratex memora forge",
        run: () => openSheet("fleet"),
      },
      {
        id: "chronicle",
        label: "Open the chronicle",
        hint: "every delegation FRIDAY has taken on, and what came of it",
        keys: "history record tasks delegations activity done",
        run: () => openSheet("chronicle"),
      },
      {
        id: "pulse",
        label: "Check the machine's pulse",
        hint: "the host's vitals, the voice service, autonomy's latest moves",
        keys: "system telemetry cpu ram health diagnostics voice worker",
        run: () => openSheet("pulse"),
      },
      {
        id: "life",
        label: "See your life in weeks",
        hint: "every week of a 90-year life as one dot — lived, left, and marked",
        keys: "life weeks calendar planning birthday dots year days grid",
        run: () => openSheet("life"),
      },
      {
        id: "galaxy",
        label: "Wander the memory galaxy",
        hint: "FRIDAY's memories as stars — pinned, ordinary, and trivial",
        keys: "memory galaxy memories remember stars memora sky brain",
        run: () => openSheet("galaxy"),
      },
      {
        id: "ambience",
        label: ambienceOn ? "Turn off the ambient sky" : "Turn on the ambient sky",
        hint: "a slow field of drifting light behind the room",
        keys: "ambience background sky particles stars ambient animated backdrop",
        run: toggleAmbience,
      },
      {
        id: "showcase",
        label: "Browse the showcase",
        hint: "the universe as a catalogue — billboard, crew, ledger, rooms",
        keys: "showcase browse netflix catalogue billboard featured rows discover",
        run: () => openSheet("showcase"),
      },
      {
        id: "tour",
        label: "Take the guided tour",
        hint: "five short chapters — voice, crew, ledger, machine, watch",
        keys: "tour guide story intro about meet friday chapters welcome",
        run: () => openSheet("tour"),
      },
      {
        id: "city",
        label: "Walk the city",
        hint: "the ten agents as districts in a night skyline, lit by who's awake",
        keys: "city districts skyline places map explore streets plaza watchtower",
        run: () => openSheet("city"),
      },
      {
        id: "editorial",
        label: "Read the editorial edition",
        hint: "the crew in print — masthead, specifications, spotlight, roster",
        keys: "editorial newspaper magazine edition print roster spotlight specs noolam",
        run: () => openSheet("editorial"),
      },
      {
        id: "talk",
        label: callLive ? "End the voice line" : "Start the voice line",
        hint: callLive ? "close the call — the stage stays as it is" : "talk to FRIDAY out loud, hands-free",
        keys: "voice call talk speak microphone livekit",
        run: () => {
          if (callLive) linkRef.current?.end();
          else linkRef.current?.start();
        },
      },
      {
        id: "wake",
        label: wakeArmed ? "Disarm the wake word" : "Arm the wake word",
        hint: wakeArmed
          ? "stop listening for “Hey FRIDAY” in this tab"
          : "start the voice line when you say “Hey FRIDAY” — this tab only",
        keys: "wake word hey friday hands free always listening",
        run: () => {
          setWakeNote(null);
          setWakeArmedPref(!wakeArmed);
        },
      },
      {
        id: "write",
        label: "Write a message instead",
        hint: "drop the cursor into the composer below the halo",
        keys: "chat type message text keyboard send",
        run: () => composerRef.current?.focus(),
      },
    ],
    [callLive, openSheet, ambienceOn, toggleAmbience, wakeArmed],
  );

  const agents = fleet?.agents ?? [];

  return (
    <main className="stage" data-phase={stagePhase}>
      <div className="stage-ambience" aria-hidden="true">
        {ambienceOn && <Ambience />}
      </div>

      <header className="stage-top">
        <button type="button" className="wordmark" onClick={() => setVeilOpen(true)} aria-label="Open the veil — everything the room can show">
          <SplitText text="FRIDAY" tag="span" splitType="chars" delay={45} duration={0.9} trigger="load" />
        </button>
        <div className="stage-top-right">
          <span className={`link-dot ${fleetOk ? "is-live" : ""}`} title={fleetOk ? "Fleet link is answering" : "Fleet link is quiet"} aria-hidden="true" />
          <Magnet padding={60} magnetStrength={3}>
            <button type="button" className="summon-pill" onClick={() => setVeilOpen(true)}>
              <Layers size={15} aria-hidden="true" /> Everything else
            </button>
          </Magnet>
        </div>
      </header>

      <div
        className="halo-zone"
        onTouchStart={(e) => {
          haloTouchY.current = e.touches[0]?.clientY ?? null;
        }}
        onTouchEnd={(e) => {
          const start = haloTouchY.current;
          haloTouchY.current = null;
          if (start === null) return;
          const end = e.changedTouches[0]?.clientY ?? start;
          if (start - end > 70) setVeilOpen(true);
        }}
      >
        <div className="halo-wrap">
          <Halo
            phase={stagePhase}
            onTap={() => {
              /* The halo starts a call; it never ends one — a stray
                 tap mid-conversation must not hang up. */
              if (voicePhase === "resting" || voicePhase === "down") linkRef.current?.start();
            }}
          />
          <div className="rim" aria-label="Fleet at a glance">
            {agents.map((agent, idx) => {
              const tone = toneFor(agent.status);
              const isFlaring = flaring.has(agent.name.toLowerCase()) || flaring.has(agent.id.toLowerCase());
              const angle = (idx / Math.max(agents.length, 1)) * 360;
              return (
                <button
                  key={agent.id}
                  type="button"
                  className={`rim-light tone-${tone}${isFlaring ? " is-flaring" : ""}`}
                  style={{ "--a": `${angle}deg` } as React.CSSProperties}
                  onClick={() => openSheet("fleet")}
                  aria-label={`${agent.name}: ${agent.status}. Open the fleet.`}
                  title={`${agent.name} — ${agent.status}`}
                />
              );
            })}
          </div>
        </div>
      </div>

      <VoiceCall onPhase={setVoicePhase} linkRef={linkRef} />

      {wakeArmed && !callLive && (
        <WakeListener
          enabled
          onWake={() => linkRef.current?.start()}
          onBlocked={(reason) => {
            setWakeArmedPref(false);
            setWakeNote(
              reason === "mic-denied"
                ? "Wake word off — the browser refused microphone access."
                : "Wake word off — this browser has no speech recognition.",
            );
          }}
        />
      )}
      {(wakeArmed || wakeNote) && (
        <p style={{ textAlign: "center", fontSize: 12, opacity: 0.65, margin: "6px 0 0" }} aria-live="polite">
          {wakeNote ??
            (callLive
              ? "Wake word armed — paused while the line is open."
              : "Wake word armed — say “Hey FRIDAY” to start the line.")}
        </p>
      )}

      <Conversation onBusyChange={setChatBusy} composerRef={composerRef} />

      {veilOpen && <Veil commands={commands} onClose={() => setVeilOpen(false)} />}

      {sheet && (
        <Sheet kicker={SHEET_HEADS[sheet].kicker} title={SHEET_HEADS[sheet].title} onClose={() => setSheet(null)}>
          {sheet === "fleet" && <FleetSheet />}
          {sheet === "chronicle" && <ChronicleSheet />}
          {sheet === "pulse" && <PulseSheet />}
          {sheet === "life" && <LifeSheet />}
          {sheet === "galaxy" && <GalaxySheet />}
          {sheet === "showcase" && <ShowcaseSheet onSummon={(kind) => openSheet(kind)} />}
          {sheet === "tour" && <TourSheet onSummon={(kind) => openSheet(kind)} />}
          {sheet === "city" && <CitySheet onSummon={(kind) => openSheet(kind)} />}
          {sheet === "editorial" && <EditorialSheet />}
        </Sheet>
      )}
    </main>
  );
}
