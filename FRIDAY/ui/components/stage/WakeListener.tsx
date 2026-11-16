"use client";

/* WakeListener — the listening half of the stage's opt-in wake word.
 *
 * Scope, stated plainly (full statement in FRIDAY/docs/WAKE_WORD.md):
 * this is a BROWSER wake word. It exists only while the FRIDAY stage tab
 * is open in a Chromium-family browser that exposes the Web Speech API
 * (SpeechRecognition / webkitSpeechRecognition), it is OFF until the
 * owner arms it from the Veil, and it stops the moment a voice call is
 * live (Stage unmounts it — LiveKit owns the microphone during a call).
 * It is not an OS-level always-on listener and it does not exist on the
 * phone or laptop surfaces.
 *
 * On hearing a wake phrase (lib/wakeWord.ts) it calls onWake exactly
 * once and tears itself down; Stage's onWake starts the voice line
 * through the same linkRef the "Start the voice line" command uses.
 * If the browser has no speech recognition, or refuses the microphone,
 * it reports through onBlocked so the stage can disarm and say why —
 * it never retries a refused microphone in a loop. */

import { useEffect, useRef } from "react";
import { matchWakePhrase } from "@/lib/wakeWord";

/* The Web Speech API is not in TypeScript's DOM lib — the minimal
   structural shape this component actually uses. */
interface RecognitionAlternativeLike {
  transcript: string;
}
interface RecognitionResultLike {
  0: RecognitionAlternativeLike;
  isFinal: boolean;
}
interface RecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<RecognitionResultLike>;
}
interface RecognitionErrorLike {
  error: string;
}
interface RecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onresult: ((event: RecognitionEventLike) => void) | null;
  onerror: ((event: RecognitionErrorLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
  abort: () => void;
}
type RecognitionCtor = new () => RecognitionLike;

function recognitionCtor(): RecognitionCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function WakeListener({
  enabled,
  onWake,
  onBlocked,
}: {
  enabled: boolean;
  onWake: () => void;
  onBlocked?: (reason: "unsupported" | "mic-denied") => void;
}) {
  const wakeRef = useRef(onWake);
  const blockedRef = useRef(onBlocked);
  useEffect(() => {
    wakeRef.current = onWake;
    blockedRef.current = onBlocked;
  });

  useEffect(() => {
    if (!enabled) return;
    const Ctor = recognitionCtor();
    if (!Ctor) {
      blockedRef.current?.("unsupported");
      return;
    }
    let stopped = false;
    const rec = new Ctor();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-IN";
    rec.onresult = (event) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i]?.[0]?.transcript ?? "";
        if (matchWakePhrase(text)) {
          stopped = true;
          try {
            rec.stop();
          } catch {
            /* already stopped */
          }
          wakeRef.current();
          return;
        }
      }
    };
    rec.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        stopped = true;
        blockedRef.current?.("mic-denied");
      }
      /* Any other error (no-speech, network, aborted) falls through to
         onend, which restarts while armed — the standard recognizer
         lifecycle, not a retry loop. */
    };
    rec.onend = () => {
      if (!stopped) {
        try {
          rec.start();
        } catch {
          /* a restart raced a stop — the next onend settles it */
        }
      }
    };
    try {
      rec.start();
    } catch {
      /* already started */
    }
    return () => {
      stopped = true;
      rec.onresult = null;
      rec.onerror = null;
      rec.onend = null;
      try {
        rec.abort();
      } catch {
        /* nothing to abort */
      }
    };
  }, [enabled]);

  return null;
}
