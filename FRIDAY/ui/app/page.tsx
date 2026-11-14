"use client";

import { AudioWaveform, Bot, Clock3, Cpu, ScrollText } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ArcState } from "@/components/Arc";
import { Conversation } from "@/components/Conversation";
import { Crew } from "@/components/Crew";
import { DelegationLedger, LiveLedger } from "@/components/Record";
import { Instruments, OwnerSettings, VoiceLineCard } from "@/components/Machine";
import { VoiceLine } from "@/components/VoiceLine";
import {
  Agent,
  AgentsLiveSnapshot,
  AutonomySnapshot,
  FleetSnapshot,
  HostTelemetry,
  LiveActivityEvent,
  TaskTimelineSnapshot,
  apiBase,
  istTime,
  requestJson,
  statusTone,
} from "@/lib/api";
import { BUILD_NAME, BUILD_TAG } from "@/lib/build-info";

/* ============================================================
   FRIDAY — the Arc edition (TASK-WEB-001, 2026-11-15).

   A from-scratch console, designed from the owner's jobs
   rather than inherited from the previous site:

   - TALK is the home screen and holds exactly two things: the
     voice line (the Arc, one tap to a live call) and the written
     conversation with the same brain. Nothing else lives here.
   - CREW, RECORD and UNDER THE HOOD sit behind a bottom dock —
     reachable in one tap, never competing with the conversation.
   - Every view stays mounted while you move between them, so a
     live call and a half-written message survive the trip.

   The data wiring is the production contract, unchanged: 30s
   snapshot polling (agents/status, system_telemetry,
   autonomous/status, agents/live, tasks/timeline), the
   /api/ws/activity live socket, and every component's own
   endpoints. IST is the only clock on the page.
   ============================================================ */

type View = "talk" | "crew" | "record" | "machine";

const DOCK: Array<{ id: View; label: string; icon: React.ReactNode }> = [
  { id: "talk", label: "Talk", icon: <AudioWaveform size={20} /> },
  { id: "crew", label: "Crew", icon: <Bot size={20} /> },
  { id: "record", label: "Record", icon: <ScrollText size={20} /> },
  { id: "machine", label: "Machine", icon: <Cpu size={20} /> },
];

export default function Page() {
  const [mounted, setMounted] = useState(false);
  const [view, setView] = useState<View>("talk");
  const [now, setNow] = useState<Date | null>(null);
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [agentsLive, setAgentsLive] = useState<AgentsLiveSnapshot | null>(null);
  const [telemetry, setTelemetry] = useState<HostTelemetry | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomySnapshot | null>(null);
  const [liveActivity, setLiveActivity] = useState<Record<string, LiveActivityEvent>>({});
  const [timeline, setTimeline] = useState<TaskTimelineSnapshot | null>(null);
  const [connected, setConnected] = useState<"checking" | "online" | "offline">("checking");
  const [cpuHistory, setCpuHistory] = useState<number[]>([]);
  const [ramHistory, setRamHistory] = useState<number[]>([]);
  const [voiceState, setVoiceState] = useState<ArcState>("idle");
  const [chatPrefill, setChatPrefill] = useState<{ text: string; seq: number }>({ text: "", seq: 0 });

  useEffect(() => {
    setMounted(true);
    setNow(new Date());
    const clock = window.setInterval(() => setNow(new Date()), 15_000);
    return () => window.clearInterval(clock);
  }, []);

  const refresh = useCallback(async () => {
    const [fleetResult, telemetryResult, autonomyResult, liveResult, timelineResult] = await Promise.allSettled([
      requestJson<FleetSnapshot>("/api/agents/status"),
      requestJson<HostTelemetry>("/api/system_telemetry"),
      requestJson<AutonomySnapshot>("/api/autonomous/status"),
      requestJson<AgentsLiveSnapshot>("/api/agents/live"),
      requestJson<TaskTimelineSnapshot>("/api/tasks/timeline?limit=50"),
    ]);
    if (fleetResult.status === "fulfilled") {
      setFleet(fleetResult.value);
      setConnected("online");
    } else {
      setConnected("offline");
    }
    if (telemetryResult.status === "fulfilled") {
      const data = telemetryResult.value;
      setTelemetry(data);
      if (data.status === "ok" && typeof data.cpu_percent === "number") {
        setCpuHistory((current) => [...current, data.cpu_percent!].slice(-40));
      }
      if (data.status === "ok" && typeof data.ram_percent === "number") {
        setRamHistory((current) => [...current, data.ram_percent!].slice(-40));
      }
    } else {
      setTelemetry(null);
    }
    if (autonomyResult.status === "fulfilled") setAutonomy(autonomyResult.value);
    if (liveResult.status === "fulfilled") setAgentsLive(liveResult.value);
    if (timelineResult.status === "fulfilled") setTimeline(timelineResult.value);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    void refresh();
    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") void refresh();
    }, 30_000);
    return () => window.clearInterval(timer);
  }, [mounted, refresh]);

  /* Live agent activity over the keyless origin-gated WebSocket; the
     polling above keeps everything fresh if the socket is unavailable. */
  useEffect(() => {
    if (!mounted) return;
    let socket: WebSocket | null = null;
    let retry: number | null = null;
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      try {
        socket = new WebSocket(`${apiBase().replace(/^http/, "ws")}/api/ws/activity`);
      } catch {
        return;
      }
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(String(event.data)) as LiveActivityEvent;
          const known = ["activity", "agent_action", "chat_command"];
          if (known.includes(String(data.type))) {
            const key = String(data.agent || data.agents_involved || "friday").toLowerCase();
            setLiveActivity((current) => ({ ...current, [key]: data }));
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = () => {
        if (!cancelled && retry === null) {
          retry = window.setTimeout(() => {
            retry = null;
            connect();
          }, 10_000);
        }
      };
      socket.onerror = () => {
        try {
          socket?.close();
        } catch {
          /* ignore */
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (retry !== null) window.clearTimeout(retry);
      try {
        socket?.close();
      } catch {
        /* ignore */
      }
    };
  }, [mounted]);

  const answering = fleet?.agents?.filter((a) => statusTone(a.status) === "good").length ?? 0;
  const totalAgents = fleet?.agent_count ?? fleet?.agents?.length ?? 10;
  const callLive = voiceState === "listening" || voiceState === "speaking";

  function askAgent(agent: Agent) {
    setChatPrefill({ text: `@${agent.name} `, seq: chatPrefill.seq + 1 });
    setView("talk");
  }

  if (!mounted) {
    return (
      <main className="boot" role="status" aria-label="FRIDAY is starting">
        <span className="boot-ring" aria-hidden="true" />
        <span className="boot-word">FRIDAY</span>
      </main>
    );
  }

  return (
    <div className="frame" data-voice={voiceState}>
      <header className="topbar">
        <span className="brand">
          <span className="brand-mark" aria-hidden="true" />
          FRIDAY
        </span>
        <div className="topbar-right">
          <span
            className="link-state"
            role="status"
            title={
              connected === "online"
                ? "This page is receiving live readings from FRIDAY"
                : connected === "offline"
                  ? "This page cannot reach FRIDAY right now"
                  : "First contact…"
            }
          >
            <span className={`dot ${connected === "online" ? "good pulse" : connected === "offline" ? "bad" : "muted"}`} />
            {connected === "online" ? "in contact" : connected === "offline" ? "no contact" : "reaching out"}
          </span>
          <span className="topbar-clock" title="Indian Standard Time">
            <Clock3 size={12} />
            {now ? `${istTime(now)} IST` : "--:-- IST"}
          </span>
        </div>
      </header>

      <main className="stage-area">
        {/* ================= TALK — the home screen ================= */}
        <section className="view view-talk" hidden={view !== "talk"} aria-label="Talk to FRIDAY">
          <div className="talk-voice">
            <VoiceLine onStateChange={setVoiceState} />
          </div>
          <Conversation prefill={chatPrefill} />
        </section>

        {/* ================= CREW ================= */}
        <section className="view" hidden={view !== "crew"} aria-label="The crew">
          <div className="view-head">
            <h2>The crew</h2>
            <p>
              Nine specialists stand behind the voice on the Talk screen — FRIDAY is the tenth, and the one you talk
              to. Every tile below is a live reading
              {fleet ? (
                <>
                  : <strong>{answering} of {totalAgents} answering right now</strong>
                </>
              ) : (
                "."
              )}
            </p>
          </div>
          <Crew fleet={fleet} autonomy={autonomy} liveActivity={liveActivity} now={agentsLive} onAsk={askAgent} />
        </section>

        {/* ================= RECORD ================= */}
        <section className="view" hidden={view !== "record"} aria-label="The record">
          <div className="view-head">
            <h2>The record</h2>
            <p>Nothing the crew does is off the books. Live moves first; underneath, every job you&apos;ve handed out — and what came back.</p>
          </div>
          <h3 className="view-sub">As it happens</h3>
          <LiveLedger autonomy={autonomy} liveActivity={liveActivity} />
          <h3 className="view-sub">Work you&apos;ve handed out</h3>
          <DelegationLedger timeline={timeline} />
        </section>

        {/* ================= MACHINE ================= */}
        <section className="view" hidden={view !== "machine"} aria-label="Under the hood">
          <div className="view-head">
            <h2>Under the hood</h2>
            <p>The two small servers all of this runs on, the measured health of your voice line, and the settings that shape how FRIDAY treats you.</p>
          </div>
          <Instruments fleet={fleet} telemetry={telemetry} autonomy={autonomy} cpuHistory={cpuHistory} ramHistory={ramHistory} />
          <h3 className="view-sub">The voice line</h3>
          <VoiceLineCard />
          <h3 className="view-sub">Your settings</h3>
          <OwnerSettings />
          <footer className="colophon">
            <span>
              <strong>{BUILD_NAME}</strong> · build {BUILD_TAG}
            </span>
            <span>Running on your two Oracle servers · every clock here is IST</span>
          </footer>
        </section>
      </main>

      <nav className="dock" aria-label="Console views">
        {DOCK.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`dock-item${view === item.id ? " active" : ""}`}
            onClick={() => setView(item.id)}
            aria-current={view === item.id ? "page" : undefined}
          >
            {item.icon}
            <span>{item.label}</span>
            {item.id === "talk" && callLive && <span className="dock-live" aria-label="a call is live" />}
          </button>
        ))}
      </nav>
    </div>
  );
}
