"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import type { VoiceLinkControls, VoicePhase } from "../VoiceCall";
import { Conversation } from "../stage/Conversation";
import { UltronOrb } from "./UltronOrb";
import {
  clockTime,
  clockTimeOrBlank,
  fetchAutonomy,
  fetchFleet,
  fetchTelemetry,
  oneLine,
  openActivitySocket,
  toneFor,
  type ActivityFrame,
  type AutonomySnapshot,
  type FleetSnapshot,
  type HostTelemetry,
} from "@/lib/wire";
import { getWakeArmedSnapshot, setWakeArmedPref, subscribeWakeArmed } from "@/lib/wakeWord";

/* ================================================================
   The ULTRON stage (TASK-WEB-003) — FRIDAY in the command-
   dashboard theme the owner picked on 2026-11-17.

   This is the real app wearing the picked look, not the mock:
   the conversation is the stage's own Conversation component,
   the voice line is the stage's own VoiceCall component (the orb
   starts it, exactly as the halo did), and the wake word is the
   same opt-in WakeListener with the same preference. The panels
   read the same live endpoints the Halo sheets read.

   What the picked mock showed that has NO real source in this
   app is never faked here:
     - the vision viewport (no camera/screen source exists in the
       web app) is labelled NOT WIRED instead of playing a feed;
     - uplink/downlink figures, neural-engine load, core
       temperature and the autonomy/cursor sliders are absent —
       the control panel holds only controls that do something
       (wake word, theme, the voice line, the composer);
     - the waveform band is a voice-state visual, driven by the
       call's phase, not a microphone measurement.
   The Halo sheets and veil are Halo surfaces; this stage's own
   panels carry the fleet and the machine live instead. Halo
   itself remains one switch away (see components/ThemeRoot.tsx).
   ================================================================ */

const VoiceCall = dynamic(() => import("../VoiceCall").then((m) => m.VoiceCall), { ssr: false });
const WakeListener = dynamic(() => import("../stage/WakeListener").then((m) => m.WakeListener), { ssr: false });

const STATUS_TEXT: Record<VoicePhase, string> = {
  resting: "STANDING BY",
  opening: "CONNECTING",
  listening: "LISTENING",
  thinking: "THINKING",
  speaking: "SPEAKING",
  down: "LINE DOWN",
};

interface LogEntry {
  id: number;
  at: string;
  text: string;
  done?: boolean;
}

let logSeq = 0;

function frameText(frame: ActivityFrame): string {
  const who = frame.agent || frame.agents_involved || "FRIDAY";
  const what = frame.directive || frame.action || frame.command || frame.detail || frame.type || "activity";
  return `${who} — ${oneLine(what, 110)}`;
}

export function UltronStage() {
  const [voicePhase, setVoicePhase] = useState<VoicePhase>("resting");
  const [chatBusy, setChatBusy] = useState(false);
  const [fleet, setFleet] = useState<FleetSnapshot | null>(null);
  const [fleetOk, setFleetOk] = useState(false);
  const [telemetry, setTelemetry] = useState<HostTelemetry | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomySnapshot | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [now, setNow] = useState(() => new Date());
  const [wakeNote, setWakeNote] = useState<string | null>(null);

  const wakeArmed = useSyncExternalStore(subscribeWakeArmed, getWakeArmedSnapshot, () => false);
  const linkRef = useRef<VoiceLinkControls | null>(null);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);

  const stagePhase: VoicePhase =
    voicePhase === "resting" || voicePhase === "down" ? (chatBusy ? "thinking" : voicePhase) : voicePhase;
  const callLive = voicePhase === "opening" || voicePhase === "listening" || voicePhase === "thinking" || voicePhase === "speaking";

  /* The header clock — the owner's own wall clock, ticking. */
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 200);
    return () => window.clearInterval(timer);
  }, []);

  /* Fleet + telemetry + autonomy, refreshed on the Halo stage's
     own cadence; every panel below renders only what these return. */
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
      try {
        const t = await fetchTelemetry();
        if (!cancelled) setTelemetry(t);
      } catch {
        /* telemetry quiet → the panel says so, it does not invent */
      }
      try {
        const a = await fetchAutonomy();
        if (!cancelled) setAutonomy(a);
      } catch {
        /* autonomy quiet → the log simply starts empty */
      }
    };
    void load();
    const timer = window.setInterval(load, 20_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  /* The activity log: seeded once from the autonomy ledger's recent
     actions, then fed live by the activity socket. */
  useEffect(() => {
    if (!autonomy?.recent_actions || log.length > 0) return;
    const seed: LogEntry[] = autonomy.recent_actions.slice(0, 7).map((a) => ({
      id: ++logSeq,
      /* recorded_at is the full ISO instant (TASK-FRD-029); the bare
         `timestamp` is a time-of-day string that never parses, and an
         entry with neither renders no time rather than "--:--:--". */
      at: clockTimeOrBlank(a.recorded_at || a.timestamp),
      text: oneLine(a.directive || a.action_type || a.target || "action", 110),
      done: a.success === true,
    }));
    if (seed.length > 0) setLog(seed);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autonomy]);

  useEffect(() => {
    const socket = openActivitySocket((frame) => {
      setLog((current) =>
        [...current, { id: ++logSeq, at: clockTimeOrBlank(frame.timestamp ?? Date.now()), text: frameText(frame), done: frame.success === true }].slice(-7),
      );
    });
    return () => socket?.close();
  }, []);

  const toggleWake = useCallback(() => {
    setWakeNote(null);
    setWakeArmedPref(!wakeArmed);
  }, [wakeArmed]);

  const agents = fleet?.agents ?? [];
  const onlineCount = agents.filter((a) => toneFor(a.status) === "good").length;
  const latencies = agents.map((a) => a.latency_ms).filter((v): v is number => typeof v === "number" && v > 0);
  const meanLatency = latencies.length > 0 ? Math.round(latencies.reduce((s, v) => s + v, 0) / latencies.length) : null;

  const pad = (n: number) => String(n).padStart(2, "0");
  const clock = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  const clockMs = `.${pad(Math.floor(now.getMilliseconds() / 10))}`;
  const dateLine = now
    .toLocaleDateString("en-IN", { weekday: "long", day: "2-digit", month: "short", year: "numeric" })
    .toUpperCase();

  const planLine = autonomy?.active_directive
    ? `Active directive: ${oneLine(autonomy.active_directive, 140)}`
    : callLive
      ? "The voice line is open — speak, FRIDAY is listening on the real LiveKit line."
      : chatBusy
        ? "FRIDAY is working on the written message below."
        : "Standing by — tap the orb or say the wake word (when armed) to open the line.";

  return (
    <main className="ultron-stage" data-phase={stagePhase}>
      <div className="ultron-app">
        {/* ================= HEADER ================= */}
        <header className="ultron-header">
          <div className="ultron-brand">
            <h1>
              FRI<b>D</b>AY
            </h1>
            <span className="ultron-ver">ULTRON COMMAND · TASK-WEB-003</span>
          </div>
          <div className="ultron-pills">
            <button
              type="button"
              className={`ultron-pill${callLive ? " active" : ""}`}
              onClick={() => (callLive ? linkRef.current?.end() : linkRef.current?.start())}
            >
              VOICE
            </button>
            <button type="button" className="ultron-pill" onClick={() => composerRef.current?.focus()}>
              TEXT
            </button>
          </div>
          <div className="ultron-head-right">
            <div className="ultron-live">
              <i className={fleetOk ? "is-live" : ""} />
              {fleetOk ? "LIVE" : "QUIET"}
            </div>
            <div className="ultron-clockbox">
              <div className="ultron-clock">
                <span>{clock}</span>
                <span className="ultron-clock-ms">{clockMs}</span>
              </div>
              <div className="ultron-date">{dateLine}</div>
            </div>
          </div>
        </header>

        {/* ================= MAIN ================= */}
        <div className="ultron-main">
          {/* LEFT */}
          <aside className="ultron-col">
            <section className="ultron-panel" style={{ flex: 1.25 }} aria-label="System diagnostics">
              <div className="ultron-p-head">
                <span className="ultron-sq" />
                <h2>SYSTEM DIAGNOSTICS</h2>
                <span className="ultron-tag">HOST</span>
              </div>
              {telemetry ? (
                <>
                  <div className="ultron-metric">
                    <div className="ultron-metric-row">
                      <span>CPU LOAD</span>
                      <b>{typeof telemetry.cpu_percent === "number" ? `${Math.round(telemetry.cpu_percent)}%` : "—"}</b>
                    </div>
                    <div className="ultron-bar">
                      <i style={{ width: `${Math.min(100, Math.max(0, telemetry.cpu_percent ?? 0))}%` }} />
                    </div>
                  </div>
                  <div className="ultron-metric">
                    <div className="ultron-metric-row">
                      <span>MEMORY</span>
                      <b>{typeof telemetry.ram_percent === "number" ? `${Math.round(telemetry.ram_percent)}%` : "—"}</b>
                    </div>
                    <div className="ultron-bar">
                      <i style={{ width: `${Math.min(100, Math.max(0, telemetry.ram_percent ?? 0))}%` }} />
                    </div>
                  </div>
                  <div className="ultron-kv">
                    <span className="k">RAM used</span>
                    <span className="v">
                      {telemetry.ram_used_gb ?? "—"} / {telemetry.ram_total_gb ?? "—"} GB
                    </span>
                  </div>
                  <div className="ultron-kv">
                    <span className="k">CPU cores</span>
                    <span className="v">{telemetry.cpu_cores ?? "—"}</span>
                  </div>
                  <div className="ultron-kv">
                    <span className="k">OS</span>
                    <span className="v">{telemetry.os ?? "—"}</span>
                  </div>
                  <div className="ultron-kv">
                    <span className="k">Agents awake</span>
                    <span className="v hot">
                      {onlineCount} / {agents.length || 10}
                    </span>
                  </div>
                </>
              ) : (
                <p className="ultron-nodata">Telemetry unreachable — no figures shown rather than invented ones.</p>
              )}
            </section>

            <section className="ultron-panel" style={{ flex: 1 }} aria-label="Core modules">
              <div className="ultron-p-head">
                <span className="ultron-sq" />
                <h2>CORE MODULES</h2>
                <span className="ultron-tag">{agents.length || 10} UNITS</span>
              </div>
              {agents.length > 0 ? (
                /* The rows scroll inside the panel (TASK-FRD-029): the
                   panel is a flex child with min-height 0, so an
                   unbounded list spilled past its border and the last
                   rows painted under the VOICE STATE band below. */
                <div className="ultron-mod-scroll">
                  {agents.map((agent) => {
                    const tone = toneFor(agent.status);
                    return (
                      <div className="ultron-kv" key={agent.id}>
                        <span className="k">{agent.name}</span>
                        <span className={`ultron-st ${tone === "good" ? "ok" : tone === "warn" ? "warn" : ""}`}>
                          <i />
                          {agent.status.toUpperCase()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="ultron-nodata">Fleet unreachable — module states unknown, not guessed.</p>
              )}
            </section>
          </aside>

          {/* CENTER */}
          <section className="ultron-center" aria-label="FRIDAY core">
            <span className="ultron-reticle tl">SYS.MONITOR // ACTIVE</span>
            <span className="ultron-reticle tr">CORE · LIVEKIT LINE</span>
            <span className="ultron-reticle bl">THEME · ULTRON</span>
            <span className="ultron-reticle br">{fleetOk ? "LINK STABLE" : "LINK QUIET"}</span>
            <UltronOrb
              phase={stagePhase}
              onTap={() => {
                /* The orb starts a call; it never ends one — a stray
                   tap mid-conversation must not hang up. Same rule
                   as the halo. */
                if (voicePhase === "resting" || voicePhase === "down") linkRef.current?.start();
              }}
            />
            <div className="ultron-status-line">
              <span className="ultron-sd" />
              <span>{STATUS_TEXT[stagePhase]}</span>
              <span className="ultron-ell">…</span>
            </div>
            <p className="ultron-plan-line">{planLine}</p>
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
              <p className="ultron-wake-note" aria-live="polite">
                {wakeNote ??
                  (callLive
                    ? "Wake word armed — paused while the line is open."
                    : "Wake word armed — say “Hey FRIDAY” to start the line.")}
              </p>
            )}
          </section>

          {/* RIGHT */}
          <aside className="ultron-col">
            <section className="ultron-panel" aria-label="Fleet link">
              <div className="ultron-p-head">
                <span className="ultron-sq" />
                <h2>FLEET LINK</h2>
                <span className="ultron-tag">REAL</span>
              </div>
              <div className="ultron-kv">
                <span className="k">Link</span>
                <span className="v hot">{fleetOk ? "ANSWERING" : "QUIET"}</span>
              </div>
              <div className="ultron-kv">
                <span className="k">Agents online</span>
                <span className="v">
                  {onlineCount} / {agents.length || "—"}
                </span>
              </div>
              <div className="ultron-kv">
                <span className="k">Mean latency</span>
                <span className="v">{meanLatency !== null ? `${meanLatency} MS` : "—"}</span>
              </div>
              <div className="ultron-kv">
                <span className="k">Last fleet check</span>
                <span className="v">{fleet?.timestamp ? clockTime(fleet.timestamp) : "—"}</span>
              </div>
              <p className="ultron-nodata">
                The picked mock showed uplink/downlink figures here; the web app measures neither, so none are shown.
              </p>
            </section>

            <section className="ultron-panel" style={{ flex: 1 }} aria-label="Vision">
              <div className="ultron-p-head">
                <span className="ultron-sq" />
                <h2>VISION — LIVE FEED</h2>
                <span className="ultron-tag">NOT WIRED</span>
              </div>
              <div className="ultron-vision">
                <span className="ultron-cnr a" />
                <span className="ultron-cnr b" />
                <span className="ultron-cnr c" />
                <span className="ultron-cnr d" />
                <div className="ultron-vision-cross" />
                <div className="ultron-vision-label">NO LIVE FEED — NO CAMERA OR SCREEN SOURCE IN THE WEB APP</div>
              </div>
              <p className="ultron-nodata">
                The mock played a screen capture here. This app has no such source, so the frame stays empty rather
                than pretend.
              </p>
            </section>
          </aside>
        </div>

        {/* ================= WAVEFORM BAND ================= */}
        <div className="ultron-waveband" data-phase={stagePhase} aria-hidden="true">
          <span className="ultron-wlabel">VOICE&nbsp;STATE</span>
          {Array.from({ length: 48 }, (_, i) => (
            <span key={i} className="ultron-wbar" style={{ animationDelay: `${(i % 12) * 0.09}s` }} />
          ))}
        </div>

        {/* ================= BOTTOM ================= */}
        <div className="ultron-bottom">
          <section className="ultron-panel" aria-label="Activity log">
            <div className="ultron-p-head">
              <span className="ultron-sq" />
              <h2>ACTIVITY LOG</h2>
              <span className="ultron-tag">REALTIME</span>
            </div>
            <div className="ultron-log-list">
              {log.length === 0 && <p className="ultron-nodata">No activity recorded yet this session.</p>}
              {log.map((entry) => (
                <div className={`ultron-log-item${entry.done ? " done" : ""}`} key={entry.id}>
                  <time>{entry.at}</time>
                  <i />
                  <div>{entry.text}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="ultron-panel ultron-chat-panel" aria-label="Conversation">
            <div className="ultron-p-head">
              <span className="ultron-sq" />
              <h2>CONVERSATION</h2>
              <span className="ultron-tag">HANDS-FREE SESSION</span>
            </div>
            <Conversation onBusyChange={setChatBusy} composerRef={composerRef} />
          </section>

          <section className="ultron-panel" aria-label="Control">
            <div className="ultron-p-head">
              <span className="ultron-sq" />
              <h2>CONTROL</h2>
              <span className="ultron-tag">REAL ONLY</span>
            </div>
            <div className="ultron-chips">
              <button type="button" className={`ultron-chip${wakeArmed ? " on" : ""}`} onClick={toggleWake} aria-pressed={wakeArmed}>
                WAKE WORD {wakeArmed ? "ARMED" : "OFF"}
              </button>
              <button
                type="button"
                className="ultron-chip"
                onClick={() => (callLive ? linkRef.current?.end() : linkRef.current?.start())}
              >
                {callLive ? "END THE LINE" : "START THE LINE"}
              </button>
              <button type="button" className="ultron-chip" onClick={() => composerRef.current?.focus()}>
                WRITE INSTEAD
              </button>
            </div>
            <p className="ultron-nodata">
              The mock's autonomy / voice-rate / cursor sliders changed nothing real, so they are not carried over.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
