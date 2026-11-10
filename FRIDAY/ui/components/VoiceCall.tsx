"use client";

import { AlertCircle, Headphones, Mic, PhoneOff, Radio, ShieldAlert, Volume2, Waves } from "lucide-react";
import { Room, RoomEvent, Track } from "livekit-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { OrbCore, OrbState } from "./OrbCore";
import { formatClock, requestJson } from "@/lib/api";

/* ============================================================
   Continuous LiveKit voice session with FRIDAY.
   - One tap -> room joins, mic opens, stays open the whole call.
   - The FRIDAY worker (Gemini Live voice agent on the Oracle
     server) is the other participant: full-duplex conversation,
     you can interrupt FRIDAY mid-sentence.
   - Auto-disconnects after 3 min of silence or a 30 min hard cap
     to protect the free LiveKit minutes.
   ============================================================ */

const IDLE_TIMEOUT_MS = 3 * 60 * 1000;
const HARD_CAP_MS = 30 * 60 * 1000;

type VoiceStatus = "idle" | "connecting" | "connected" | "error";

export function VoiceCall({ onStateChange }: { onStateChange?: (state: OrbState) => void }) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [message, setMessage] = useState("Tap to open a continuous voice line with FRIDAY.");
  const [peerSpeaking, setPeerSpeaking] = useState(false);
  const [micSpeaking, setMicSpeaking] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const roomRef = useRef<Room | null>(null);
  const lastActivityRef = useRef<number>(Date.now());
  const connectedAtRef = useRef<number>(0);

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

  const endCall = useCallback((note: string) => {
    roomRef.current?.disconnect();
    roomRef.current = null;
    clearAudioElements();
    setPeerSpeaking(false);
    setMicSpeaking(false);
    setAudioBlocked(false);
    setSeconds(0);
    setStatus("idle");
    setMessage(note);
  }, [clearAudioElements]);

  /* session timers: clock, idle auto-disconnect, hard cap */
  useEffect(() => {
    if (status !== "connected") return;
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - connectedAtRef.current) / 1000));
      const idleFor = Date.now() - lastActivityRef.current;
      if (idleFor > IDLE_TIMEOUT_MS) {
        endCall("Disconnected automatically after 3 minutes of silence to protect your free LiveKit minutes.");
      } else if (Date.now() - connectedAtRef.current > HARD_CAP_MS) {
        endCall("Session capped at 30 minutes to protect your free LiveKit minutes — tap to start again.");
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
    setMessage("Opening the voice room…");
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

      room.on(RoomEvent.Disconnected, () => {
        roomRef.current = null;
        clearAudioElements();
        setPeerSpeaking(false);
        setMicSpeaking(false);
        setSeconds(0);
        setStatus("idle");
        setMessage("Voice line closed.");
      });

      await room.connect(body.server_url, body.token);

      /* THE fix the old voice panel never had: publish the microphone.
         Without this the room is listen-only — FRIDAY hears nothing. */
      await room.localParticipant.setMicrophoneEnabled(true);

      roomRef.current = room;
      connectedAtRef.current = Date.now();
      lastActivityRef.current = Date.now();
      setSeconds(0);
      setStatus("connected");
      setMessage("Live — speak naturally. You can interrupt FRIDAY mid-sentence.");
    } catch (error) {
      const reason = error instanceof Error ? error.message : "Voice connection failed.";
      roomRef.current?.disconnect();
      roomRef.current = null;
      clearAudioElements();
      setStatus("error");
      setMessage(reason.includes("permission") || reason.toLowerCase().includes("denied")
        ? "Microphone permission was denied. Allow mic access in your browser, then try again."
        : reason);
    }
  }

  return (
    <div className="voice-layout">
      <div className="panel voice-stage">
        <OrbCore state={orbState} />
        <div className="voice-status">{status === "connected" ? <strong>{message}</strong> : message}</div>
        {status === "connected" && (
          <span className="voice-timer">
            <span className="rec-dot" aria-hidden="true" />
            {formatClock(seconds)}
          </span>
        )}
        <button
          className={`btn ${status === "connected" ? "btn-danger" : "btn-primary"} btn-lg`}
          onClick={() => (status === "connected" ? endCall("Voice line closed.") : startCall())}
          disabled={status === "connecting"}
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
              <Mic size={17} /> Talk to FRIDAY
            </>
          )}
        </button>
        {audioBlocked && (
          <div className="voice-error">
            <ShieldAlert size={15} />
            <span>Browser blocked playback — tap anywhere on the page, then press the call button again.</span>
          </div>
        )}
        <p className="voice-note">
          Auto-disconnects after 3 minutes of silence or 30 minutes total — your free LiveKit minutes are never wasted.
        </p>
      </div>

      <div className="panel" style={{ padding: "clamp(22px, 3vw, 34px)", display: "flex", flexDirection: "column", justifyContent: "center", gap: 16 }}>
        <h3 className="display" style={{ margin: 0, fontSize: 21, fontWeight: 700 }}>
          A real phone line to your <span className="grad-text">sovereign AI</span>
        </h3>
        <p style={{ margin: 0, color: "var(--muted)", fontSize: 14.5, lineHeight: 1.65 }}>
          The mic stays open the entire call — no press-to-talk, no one-shot search box. FRIDAY hears you
          continuously through the Gemini Live voice engine on your Oracle server, answers in English or Telugu,
          and stops mid-word when you interrupt.
        </p>
        <div className="voice-features">
          <div className="voice-feature">
            <Waves size={15} /> Full-duplex audio, interrupt anytime
          </div>
          <div className="voice-feature">
            <Volume2 size={15} /> FRIDAY&apos;s voice streams back instantly
          </div>
          <div className="voice-feature">
            <Headphones size={15} /> Works on phone browsers (WebRTC)
          </div>
          <div className="voice-feature">
            <AlertCircle size={15} /> Auto-disconnect protects free minutes
          </div>
        </div>
      </div>
    </div>
  );
}
