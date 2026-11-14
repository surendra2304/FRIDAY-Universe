"use client";

import { Activity, Clock3 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { EmptyState, OnboardingHint, OwnerPreferences, VoiceDiagnostics } from "@/components/batch8";
import { CountUp, Reveal } from "@/components/effects";
import { OrbState } from "@/components/OrbCore";
import { ActivityFeed, FleetGrid, SystemPanel, TaskTimeline } from "@/components/panels";
import { VoiceCall } from "@/components/VoiceCall";
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
   FRIDAY Universe — "Reactor Deck" console (2026-11-14,
   rebuild #2).

   The owner rejected rebuild #1 (Sovereign Aurora) as "worst
   as before — completely change the theme and all": Aurora had
   restyled the SAME skeleton (top nav + tabs + left voice rail
   + right chat panel + stat band). This edition throws the
   skeleton away:

   - NO tabs, NO side rail, NO stat-card band. One flowing deck.
   - THE STAGE: the reactor core (voice orb) is the hero — a
     full-width stage at the top of the viewport whose own glow
     carries FRIDAY's state; the call control sits under it.
   - THE VITALS RIBBON: fleet vitals as one slim mono strip.
   - THE STREAM: conversation flows beneath the stage, no box.
   - THE CONSTELLATION: the fleet as a horizontal rail of agent
     nodes to flick through and tap.
   - OPS / MACHINE ROOM / CONTROL: ledgers and instruments in
     numbered deck sections below.
   - Warm graphite + amber/copper "reactor" palette; DM Mono is
     the display voice. Nothing of Aurora's cyan/violet glass
     remains.

   Data wiring is IDENTICAL to the previous editions: 30s
   snapshot polling (agents/status, system_telemetry,
   autonomous/status, agents/live, tasks/timeline), the
   /api/ws/activity live socket, and every component contract.

   Kept owner directives:
   - no scroll-jump when starting voice (connects in place)
   - IST is the only clock
   - chat and live calls survive anything (everything stays
     mounted — there are no tabs left to switch)
   ============================================================ */

export default function Page() {
  const [mounted, setMounted] = useState(false);
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
  const [voiceState, setVoiceState] = useState<OrbState>("idle");
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

  /* live agent activity over the keyless origin-gated WebSocket; polling
     above keeps everything fresh if the socket is unavailable. */
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

  /* Unified live count: an agent is live when it answers the probe. */
  const onlineCount = fleet?.agents?.filter((a) => statusTone(a.status) === "good").length ?? 0;
  const totalAgents = fleet?.agent_count ?? fleet?.agents?.length ?? 10;

  function askAgent(agent: Agent) {
    setChatPrefill({ text: `@${agent.name} `, seq: chatPrefill.seq + 1 });
    /* the composer is up-deck: glide to it (user-initiated tap, so this
       is navigation, not the forbidden scroll-jump on voice start). */
    requestAnimationFrame(() => {
      document.getElementById("chat")?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  if (!mounted) {
    return (
      <main className="splash" role="status" aria-label="Loading FRIDAY">
        <div className="splash-inner">
          <div className="splash-ring" />
          <span className="splash-text">FRIDAY</span>
        </div>
      </main>
    );
  }

  const cpuOk = telemetry?.status === "ok" && typeof telemetry.cpu_percent === "number";
  const ramOk = telemetry?.status === "ok" && typeof telemetry.ram_percent === "number";

  return (
    <>
      <header className="topbar">
        <a className="wordmark" href="#top" aria-label="FRIDAY home">
          <span className="wordmark-cell" aria-hidden="true" />
          FRIDAY
          <span className="wordmark-edition">REACTOR DECK</span>
        </a>
        <div className="topbar-status">
          <span
            title="Agents answering live health probes right now"
            className={`dot ${
              connected === "online" && onlineCount > 0 ? "good" : connected === "online" ? "warn" : connected === "offline" ? "bad" : "muted"
            } ${connected === "online" ? "pulse" : ""}`}
          />
          {connected === "online" ? (
            onlineCount > 0 ? (
              <span className="topbar-count">{`${onlineCount}/${totalAgents} agents live`}</span>
            ) : (
              <span className="topbar-count alert" role="status">
                dashboard online · agents unreachable
              </span>
            )
          ) : connected === "offline" ? (
            <span className="topbar-count">API offline</span>
          ) : (
            <span className="topbar-count">Connecting…</span>
          )}
          <span className="topbar-clock" title="Indian Standard Time">
            <Clock3 size={12} />
            {now ? `${istTime(now)} IST` : "--:-- IST"}
          </span>
        </div>
      </header>

      <main className="deck" id="top" data-voice={voiceState}>
        {/* ============ THE STAGE — the reactor core ============ */}
        <section className="stage" aria-label="FRIDAY voice">
          <div className="stage-glow" aria-hidden="true" />
          <p className="stage-eyebrow">Friday · Sovereign Operating System</p>
          <VoiceCall onStateChange={setVoiceState} orbitAgents={fleet?.agents} />
          <p className="stage-line">Ten specialist agents, one continuous line. Speak or type — FRIDAY listens, remembers and dispatches in real time.</p>

          {/* Vitals ribbon — the old stat band, flattened to one mono
              strip on REAL fleet/ledger data (values omitted while
              loading, never invented). */}
          <div className="vitals" role="status" aria-label="Live universe vitals">
            <span className="vital">
              <span className="vital-k">Agents</span>
              <span className="vital-v">
                {fleet ? (
                  <>
                    <CountUp value={onlineCount} />/{totalAgents}
                  </>
                ) : (
                  "··"
                )}
              </span>
            </span>
            <span className="vital">
              <span className="vital-k">Tasks delegated</span>
              <span className="vital-v">{timeline ? <CountUp value={timeline.total_records ?? 0} /> : "··"}</span>
            </span>
            <span className="vital">
              <span className="vital-k">Auto actions</span>
              <span className="vital-v">{autonomy ? <CountUp value={autonomy.history_count ?? 0} /> : "··"}</span>
            </span>
            <span className="vital">
              <span className="vital-k">Autonomy</span>
              <span className="vital-v">{autonomy ? (autonomy.autonomous_mode ? "ON" : "STANDBY") : "··"}</span>
            </span>
            <span className="vital">
              <span className="vital-k">CPU</span>
              <span className="vital-v">{cpuOk ? `${Math.round(telemetry!.cpu_percent!)}%` : "—"}</span>
            </span>
            <span className="vital">
              <span className="vital-k">Memory</span>
              <span className="vital-v">{ramOk ? `${Math.round(telemetry!.ram_percent!)}%` : "—"}</span>
            </span>
          </div>
        </section>

        <Reveal delay={60}>
          <OnboardingHint id="console-welcome">
            <strong>Welcome back, Boss.</strong> Talk or type — try <em>&quot;watch topic X&quot;</em> for briefings or{" "}
            <em>&quot;alert me when BTC &gt; 100k&quot;</em> for price alerts.
          </OnboardingHint>
        </Reveal>

        {/* ============ THE STREAM — conversation ============ */}
        <section className="deck-section" aria-label="FRIDAY conversation">
          <ChatPanel prefill={chatPrefill} />
        </section>

        {/* ============ 01 · THE CONSTELLATION — fleet rail ============ */}
        <section className="deck-section" aria-label="Agent fleet">
          <Reveal>
            <div className="section-head">
              <span className="section-no">01</span>
              <div>
                <h2 className="section-title">The constellation</h2>
                <p className="section-sub">
                  Nine specialists in orbit around FRIDAY. Every node answers a real health probe and shows its last piece of work — tap a
                  node to assign or ask.
                </p>
              </div>
            </div>
          </Reveal>
          <FleetGrid fleet={fleet} autonomy={autonomy} liveActivity={liveActivity} now={agentsLive} onAsk={askAgent} />
        </section>

        {/* ============ 02 · OPERATIONS — live ledgers ============ */}
        <section className="deck-section" aria-label="Live activity">
          <Reveal>
            <div className="section-head">
              <span className="section-no">02</span>
              <div>
                <h2 className="section-title">Operations</h2>
                <p className="section-sub">What the fleet is doing right now, and every delegation on record — newest first.</p>
              </div>
            </div>
          </Reveal>
          <Reveal delay={60}>
            <ActivityFeed autonomy={autonomy} liveActivity={liveActivity} />
          </Reveal>
          <Reveal delay={120}>
            <div className="subhead">Task timeline</div>
            <TaskTimeline timeline={timeline} />
          </Reveal>
        </section>

        {/* ============ 03 · MACHINE ROOM — servers & voice ============ */}
        <section className="deck-section" aria-label="System telemetry">
          <Reveal>
            <div className="section-head">
              <span className="section-no">03</span>
              <div>
                <h2 className="section-title">Machine room</h2>
                <p className="section-sub">Your Oracle servers, live — and the last voice session&apos;s vital signs.</p>
              </div>
            </div>
          </Reveal>
          <SystemPanel fleet={fleet} telemetry={telemetry} autonomy={autonomy} cpuHistory={cpuHistory} ramHistory={ramHistory} />
          <Reveal delay={100}>
            <div className="machine-extra">
              <VoiceDiagnostics />
              {timeline && Array.isArray(timeline.events) && timeline.events.length === 0 && (
                <EmptyState
                  icon={<Activity size={22} />}
                  title="No delegated tasks yet"
                  hint={'Assign work from the constellation (or say "assign IntelX: research X") — every delegation lands here with its live status.'}
                />
              )}
            </div>
          </Reveal>
        </section>

        {/* ============ 04 · CONTROL — owner preferences ============ */}
        <section className="deck-section" aria-label="Owner control">
          <Reveal>
            <div className="section-head">
              <span className="section-no">04</span>
              <div>
                <h2 className="section-title">Control</h2>
                <p className="section-sub">How FRIDAY addresses you, briefs you and speaks.</p>
              </div>
            </div>
          </Reveal>
          <OwnerPreferences />
        </section>

        <footer className="footer">
          <span>
            <strong>FRIDAY Universe</strong> — built for Surendra
          </span>
          <span className="footer-build">{`${BUILD_NAME} · build ${BUILD_TAG}`}</span>
          <span>
            Oracle Always Free · GitHub Actions · LiveKit · IST everywhere · <a href="status.html">fleet status page</a>
          </span>
        </footer>
      </main>
    </>
  );
}
