/* Wake-phrase logic for the stage's opt-in wake word — see
   FRIDAY/docs/WAKE_WORD.md for the full scope statement.
 *
 * Background: the IG full-watch lane package (F-items) and the lane
 * baseline proved FRIDAY had NO wake word anywhere in code — the wave-2
 * triage claim that wake-word behaviour was "COVERED" was wrong (the only
 * `wake` hit in the voice package was a docstring in an unrelated policy
 * module). This module is the pure half of the fix: phrase matching and
 * the persisted arm/disarm preference. The listening half is
 * components/stage/WakeListener.tsx (browser SpeechRecognition).
 *
 * Pure and import-free, in the style of lib/ranking.ts and
 * lib/fleetRank.ts: everything here is testable with plain Node
 * (lib/wakeWord.test.ts) and nothing touches the DOM except through the
 * storage/window guards noted per function. */

/** The phrases that start the voice line. Deliberately multi-word:
 *  a bare "friday" would fire constantly in conversation *about* FRIDAY. */
export const WAKE_PHRASES: readonly string[] = [
  "hey friday",
  "ok friday",
  "okay friday",
  "yo friday",
];

/** Lowercase, drop punctuation, collapse whitespace — the form in which
 *  transcripts and phrases are compared. */
export function normalizeTranscript(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/** The wake phrase found in `transcript` (word-boundary match on the
 *  normalized forms), or null. Interim speech results are partial
 *  sentences, so containment — not equality — is the right test. */
export function matchWakePhrase(
  transcript: string,
  phrases: readonly string[] = WAKE_PHRASES,
): string | null {
  const padded = ` ${normalizeTranscript(transcript)} `;
  for (const phrase of phrases) {
    const p = normalizeTranscript(phrase);
    if (p && padded.includes(` ${p} `)) return p;
  }
  return null;
}

/** The words after the wake phrase — the would-be command — or null when
 *  no wake phrase is present. May be "" (the owner said the wake phrase
 *  and nothing else yet); the stage treats any wake as "start the line",
 *  so this is informational, for a future command pass-through. */
export function extractAfterWake(
  transcript: string,
  phrases: readonly string[] = WAKE_PHRASES,
): string | null {
  const matched = matchWakePhrase(transcript, phrases);
  if (!matched) return null;
  const norm = normalizeTranscript(transcript);
  const idx = norm.indexOf(matched);
  return norm.slice(idx + matched.length).trim();
}

/* — The arm/disarm preference (localStorage, "friday.wakeWord") ————
   Read through useSyncExternalStore in Stage.tsx: getWakeArmedSnapshot
   is the snapshot, subscribeWakeArmed the subscription, and
   setWakeArmedPref the only writer (it persists, then notifies). */

export const WAKE_STORAGE_KEY = "friday.wakeWord";

export interface WakeStorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function loadWakeArmed(storage: WakeStorageLike): boolean {
  try {
    return storage.getItem(WAKE_STORAGE_KEY) === "on";
  } catch {
    return false;
  }
}

export function saveWakeArmed(storage: WakeStorageLike, on: boolean): void {
  try {
    storage.setItem(WAKE_STORAGE_KEY, on ? "on" : "off");
  } catch {
    /* private mode / storage disabled — the preference simply won't persist */
  }
}

let wakeListeners: Array<() => void> = [];

export function subscribeWakeArmed(callback: () => void): () => void {
  wakeListeners = [...wakeListeners, callback];
  return () => {
    wakeListeners = wakeListeners.filter((l) => l !== callback);
  };
}

export function getWakeArmedSnapshot(): boolean {
  if (typeof window === "undefined") return false;
  return loadWakeArmed(window.localStorage);
}

export function setWakeArmedPref(on: boolean): void {
  if (typeof window !== "undefined") saveWakeArmed(window.localStorage, on);
  for (const listener of wakeListeners) listener();
}
