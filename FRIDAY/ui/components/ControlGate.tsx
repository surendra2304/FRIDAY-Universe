"use client";

/* ================================================================
   ControlGate — the paste-once owner key prompt (TASK-FRD-038
   checkpoint 2, the D-023 credential flow).

   Shown when a chat call answers 401: either this browser holds no
   key yet, or the stored key was rejected. The owner pastes the
   control key once; it is stored in this browser's localStorage and
   never leaves it except in the mint request's header. A successful
   mint starts the background session refresh and hands the
   conversation back. A rejected key is cleared so a stale secret
   never sits in storage.
   ================================================================ */

import { useState } from "react";
import {
  clearStoredControlKey,
  isControlAuthError,
  refreshControlSession,
  startControlSessionRefresh,
  storeControlKey,
} from "@/lib/controlSession";

export function ControlGate({
  reason,
  onConnected,
}: {
  reason: "required" | "rejected";
  onConnected: () => void;
}) {
  const [key, setKey] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(
    reason === "rejected" ? "That key was rejected — it may have rotated on the server. Paste the current one." : null,
  );

  const connect = async () => {
    const trimmed = key.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      storeControlKey(trimmed);
      await refreshControlSession();
      await startControlSessionRefresh();
      setKey("");
      onConnected();
    } catch (err) {
      clearStoredControlKey();
      setError(
        isControlAuthError(err) && err.code === "control-key-rejected"
          ? "That key was rejected — check it on the server and try again."
          : "Could not reach FRIDAY to mint a session. Check the connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="control-gate" role="group" aria-label="Connect to FRIDAY">
      <p className="control-gate-text">
        {reason === "rejected"
          ? "FRIDAY refused the stored key, so this browser cannot answer yet."
          : "FRIDAY needs the owner key in this browser before it can answer."}{" "}
        Paste it once — it stays in this browser and is never sent anywhere except to mint a short-lived session.
      </p>
      <div className="control-gate-row">
        <input
          className="control-gate-input"
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void connect();
          }}
          placeholder="Paste the owner key…"
          aria-label="Owner key"
          autoComplete="off"
          autoCapitalize="off"
          autoCorrect="off"
          spellCheck={false}
          disabled={busy}
        />
        <button type="button" className="control-gate-button" onClick={() => void connect()} disabled={busy || key.trim().length === 0}>
          {busy ? "Connecting…" : "Connect"}
        </button>
      </div>
      {error && (
        <p className="control-gate-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
