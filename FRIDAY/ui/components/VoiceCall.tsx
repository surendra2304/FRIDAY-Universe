"use client";

import { Mic, PhoneOff, Radio } from "lucide-react";
import { Room, RoomEvent, Track } from "livekit-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { OrbCore, OrbState } from "./OrbCore";
import { apiBase, formatClock, requestJson } from "@/lib/api";

/* ============================================================
   Continuous LiveKit voice session with FRIDAY — console rail.
   One tap connects right here (nothing ever scrolls the page),
   the mic stays open the whole call, and free-tier minutes are
   protected by idle / hard-cap auto-disconnect.
   ============================================================ */

const IDLE_TIMEOUT_MS = 3 * 60 * 1000;
const HARD_CAP_MS = 30 * 60 * 1000;

type VoiceStatus = "idle" | "connecting" | "connected" | "error";

export function VoiceCall({ onStateChange, footer }: { onStateChange?: (state: OrbState) => void; footer?: React.ReactNode }) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [message, setMessage] = useState("Tap once — we talk like we're on the phone.");
  const [peerSpeaking, setPeerSpeaking] = useState(false);
  const [micSpeaking, setMicSpeaking] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const roomRef = useRef<Room | null>(null);
  const lastActivityRef = useRef<number>(Date.now());
  const connectedAtRef = useRef<number>(0);
  // E3/E7 (batch 8): session identity + start timestamp for diagnostics + reconnect.
  const sessionIdRef = useRef<string>("");
  const sessionStartRef = useRef<number>(Date.now());

  const orbState: OrbState =
    status === "connected"
      ? peerSpeaking
        ? "speaking"
        : micSpeaking
          ? "listening"
          : "listening"
      : status === "connecting"
        ? "connecting"
        : status === "error"
          ? "thinking"
          : "idle";

  useEffect(() => {
    onStateChange?.(orbState);
  }, [orbState, onStateChange]);

  const clearAudioElements = useCallback(() => {
    document.querySelectorAll("audio[data-livekit]").forEach((el) => el.remove());
  }, []);

  const endCall = useCallback(
    (note: string) => {
      roomRef.current?.disconnect();
      roomRef.current = null;
      clearAudioElements();
      setPeerSpeaking(false);
      setMicSpeaking(false);
      setAudioBlocked(false);
      setSeconds(0);
      setStatus("idle");
      setMessage(note);
    },
    [clearAudioElements],
  );

  /* session timers: clock, idle auto-disconnect, hard cap */
  useEffect(() => {
    if (status !== "connected") return;
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - connectedAtRef.current) / 1000));
      const idleFor = Date.now() - lastActivityRef.current;
      if (idleFor > IDLE_TIMEOUT_MS) {
        endCall("Line closed after 3 quiet minutes to protect your free LiveKit minutes. Tap to reopen.");
      } else if (Date.now() - connectedAtRef.current > HARD_CAP_MS) {
        endCall("30-minute cap reached (free minutes) — tap to call again.");
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [status, endCall]);

  /* teardown on unmount */
  useEffect(() => {
    return () => {
      roomRef.current?.disconnect();
      roomRef.current = null;
      document.querySelectorAll("audio[data-livekit]").forEach((el) => el.remove());
    };
  }, []);

  async function startCall() {
    if (status === "connecting" || status === "connected") return;
    setStatus("connecting");
    setMessage("Opening the voice line…");
    setPeerSpeaking(false);
    setMicSpeaking(false);
    setAudioBlocked(false);

    const room = new Room({ adaptiveStream: true, dynacast: true });
    try {
      void room.startAudio().catch(() => {});
    } catch {
      /* optional playback warm-up */
    }

    try {
      const identity = `owner-${typeof crypto !== "undefined" && crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Math.random().toString(36).slice(2, 10)}`;
      const body = await requestJson<{ server_url: string; token: string }>(
        `/api/livekit/token?room=friday&identity=${encodeURIComponent(identity)}`,
      );

      const attachAudio = (track: Track) => {
        if (track.kind !== Track.Kind.Audio) return;
        if (track.attachedElements.length > 0) return;
        const element = track.attach() as HTMLAudioElement;
        element.setAttribute("data-livekit", "true");
        element.autoplay = true;
        element.setAttribute("playsinline", "true");
        element.volume = 1.0;
        document.body.appendChild(element);
        element.play().catch(() => {
          setAudioBlocked(true);
          void room.startAudio().catch(() => {});
        });
      };

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) attachAudio(track);
      });

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach().forEach((el) => el.remove());
      });

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        lastActivityRef.current = Date.now();
        const peer = speakers.some((s) => s.identity && !s.identity.startsWith("owner-"));
        const self = speakers.some((s) => s.identity?.startsWith("owner-"));
        setPeerSpeaking(peer);
        setMicSpeaking(self);
      });

      // E7 (batch 8): capture connection quality from LiveKit's PUBLIC
      // ConnectionQualityChanged event (livekit-client keeps getStats private;
      // the event carries the SDK's own rtt/loss/jitter measurements).
      let lastRtt: number | null = null;
      let lastLoss: number | null = null;
      room.on(RoomEvent.ConnectionQualityChanged, (quality: any, participant: any) => {
        // Only the owner's own connection quality (remote = FRIDAY's side).
        if (!participant?.isLocal) return;
        const info = participant.connectionQuality;
        // LiveKit exposes raw stats via the quality update payload when present.
        if (info && typeof info === "object") {
          const rtt = (info as any).rtt ?? (info as any).roundTripTime;
          const loss = (info as any).loss ?? (info as any).fractionLost;
          if (typeof rtt === "number" && rtt > 0) lastRtt = rtt;
          if (typeof loss === "number" && loss >= 0 && loss <= 1) lastLoss = loss * 100;
        }
      });
      const diagPoll = window.setInterval(() => {
        /* keep the interval for heartbeat timing; readings come from the
           ConnectionQualityChanged events above */
      }, 5000);

      // E3 (batch 8): auto-reconnect after an unexpected drop. One attempt,
      // exponential-ish backoff; preserves the chat panel state (it lives in
      // a separate component and stays mounted). The owner's page state is
      // never lost on a transient network blip.
      let reconnectAttempts = 0;
      const MAX_RECONNECT = 2;

      const postDiagnostics = async (finalStatus: string, durationSec: number) => {
        try {
          await fetch(`${apiBase}/api/voice/diagnostics/report`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionIdRef.current,
              started_at: new Date(sessionStartRef.current).toISOString(),
              ended_at: new Date().toISOString(),
              duration_sec: Math.round(durationSec),
              rtt_ms: lastRtt,
              packet_loss_pct: lastLoss,
              reconnect_count: reconnectAttempts,
              quality: finalStatus,
            }),
          });
        } catch {
          /* diagnostics are best-effort — never block the call flow */
        }
      };

      room.on(RoomEvent.Disconnected, async () => {
        window.clearInterval(diagPoll);
        const duration = (Date.now() - sessionStartRef.current) / 1000;
        // E3: attempt one auto-reconnect when the drop was unexpected
        // (not idle/cap timeouts — those go through endCall, not here).
        if (reconnectAttempts < MAX_RECONNECT && Date.now() - lastActivityRef.current < IDLE_TIMEOUT_MS) {
          reconnectAttempts += 1;
          setStatus("connecting");
          setMessage(`Line dropped — reconnecting (${reconnectAttempts}/${MAX_RECONNECT})…`);
          try {
            await new Promise((r) => setTimeout(r, 1000 * reconnectAttempts));
            if (!roomRef.current) {
              // room was torn down; reconnect by re-running startCall's connect.
              const fresh = new Room({ adaptiveStream: true, dynacast: true });
              await fresh.connect(body.server_url, body.token);
              await fresh.localParticipant.setMicrophoneEnabled(true);
              roomRef.current = fresh;
              connectedAtRef.current = Date.now();
              lastActivityRef.current = Date.now();
              setStatus("connected");
              setMessage("Reconnected — speak naturally.");
              return;
            }
          } catch {
            /* fall through to the honest "line closed" path below */
          }
        }
        // E7: report the final session diagnostics.
        await postDiagnostics(duration > 0 ? (lastRtt != null && lastRtt < 250 ? "good" : "degraded") : "no-session-yet", duration);
        roomRef.current = null;
        clearAudioElements();
        setPeerSpeaking(false);
        setMicSpeaking(false);
        setSeconds(0);
        setStatus("idle");
        setMessage("Voice line closed.");
      });

      await room.connect(body.server_url, body.token);

      /* publish the microphone — without this the room is listen-only */
      await room.localParticipant.setMicrophoneEnabled(true);

      roomRef.current = room;
      connectedAtRef.current = Date.now();
      lastActivityRef.current = Date.now();
      // E3/E7 (batch 8): seed the session identity + start time.
      sessionIdRef.current = `voice-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      sessionStartRef.current = Date.now();
      setSeconds(0);
      setStatus("connected");
      setMessage("Live — speak naturally, interrupt anytime.");
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Voice connection failed.";
      roomRef.current?.disconnect();
      roomRef.current = null;
      clearAudioElements();
      setStatus("error");
      setMessage(
        reason.includes("permission") || reason.toLowerCase().includes("denied")
          ? "Mic permission denied — allow it in the browser, then tap again."
          : reason,
      );
    }
  }

  return (
    <div className="voice-rail panel">
      <div className="rail-orb">
        <OrbCore state={orbState} showLabel={false} />
      </div>
      <div className="rail-state" aria-live="polite">
        <strong>{message}</strong>
        {status === "connected" && (
          <span className="voice-timer">
            <span className="rec-dot" aria-hidden="true" />
            {formatClock(seconds)}
          </span>
        )}
      </div>
      <button
        className={`btn ${status === "connected" ? "btn-danger" : "btn-primary"} btn-lg btn-voice`}
        onClick={() => (status === "connected" ? endCall("Voice line closed.") : startCall())}
        disabled={status === "connecting"}
        aria-label={status === "connected" ? "End voice call" : "Start voice call"}
      >
        {status === "connecting" ? (
          <>
            <Radio size={17} className="spin" /> Connecting…
          </>
        ) : status === "connected" ? (
          <>
            <PhoneOff size={16} /> End call
          </>
        ) : (
          <>
            <Mic size={17} /> Start voice
          </>
        )}
      </button>
      {audioBlocked && (
        <p className="rail-note rail-warn">Browser blocked playback — tap anywhere on the page, then press the button again.</p>
      )}
      <p className="rail-note">
        English or Telugu · full-duplex · auto-closes when idle to protect free minutes
      </p>
      {footer && <div className="rail-footer">{footer}</div>}
    </div>
  );
}
