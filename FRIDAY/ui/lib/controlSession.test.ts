/* Control-session tests for lib/controlSession.ts (TASK-FRD-038).
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/controlSession.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import {
  CONTROL_KEY_STORAGE,
  CONTROL_SESSION_HEADER,
  CONTROL_TOKEN_REFRESH_MARGIN_MS,
  ControlAuthError,
  clearControlSession,
  clearStoredControlKey,
  controlAuthHeaders,
  getControlSession,
  hasStoredControlKey,
  isControlAuthError,
  mintControlSession,
  parseControlSession,
  readStoredControlKey,
  refreshControlSession,
  setControlSessionStorage,
  startControlSessionRefresh,
  stopControlSessionRefresh,
  storeControlKey,
} from "./controlSession.ts";

/* A tiny in-memory stand-in for localStorage. */
function memoryStorage(initial: Record<string, string> = {}): Map<string, string> & {
  getItem(k: string): string | null;
  setItem(k: string, v: string): void;
  removeItem(k: string): void;
} {
  const map = new Map<string, string>(Object.entries(initial));
  const storage = map as Map<string, string> & {
    getItem(k: string): string | null;
    setItem(k: string, v: string): void;
    removeItem(k: string): void;
  };
  storage.getItem = (k) => (map.has(k) ? map.get(k)! : null);
  storage.setItem = (k, v) => {
    map.set(k, v);
  };
  storage.removeItem = (k) => {
    map.delete(k);
  };
  return storage;
}

type FetchCall = { url: string; headers: Record<string, string>; cache?: string };
function mockFetch(
  handler: (call: FetchCall) => { ok: boolean; status: number; statusText: string; body: unknown },
): { fetchImpl: (url: string, init?: { headers?: Record<string, string>; cache?: string }) => Promise<{ ok: boolean; status: number; statusText: string; json: () => Promise<unknown>; text: () => Promise<string> }>; calls: FetchCall[] } {
  const calls: FetchCall[] = [];
  const fetchImpl = async (url: string, init?: { headers?: Record<string, string>; cache?: string }) => {
    const call = { url, headers: init?.headers ?? {}, cache: init?.cache };
    calls.push(call);
    const res = handler(call);
    return {
      ok: res.ok,
      status: res.status,
      statusText: res.statusText,
      json: async () => res.body,
      text: async () => JSON.stringify(res.body),
    };
  };
  return { fetchImpl, calls };
}

const NOW = 1_800_000_000_000; // fixed clock for the mint tests
const TOKEN = "fcs1.1800001200.deadbeef";
const mintOk = () => ({
  ok: true,
  status: 200,
  statusText: "OK",
  body: { status: "ok", token: TOKEN, expires_at: new Date(NOW + 1_200_000).toISOString(), ttl_seconds: 1200 },
});

// --- parseControlSession -------------------------------------------------
{
  const session = parseControlSession(
    { token: TOKEN, expires_at: new Date(NOW + 1_200_000).toISOString(), ttl_seconds: 1200 },
    NOW,
  );
  assert.equal(session.token, TOKEN);
  assert.equal(session.expiresAtMs, NOW + 1_200_000);
  // No expires_at: fall back to ttl_seconds.
  assert.equal(parseControlSession({ token: TOKEN, ttl_seconds: 600 }, NOW).expiresAtMs, NOW + 600_000);
  // A malformed answer is a control-unavailable, never a crash.
  assert.throws(() => parseControlSession({ token: "not-a-token" }, NOW), (e: unknown) => isControlAuthError(e) && (e as ControlAuthError).code === "control-unavailable");
  assert.throws(() => parseControlSession(null, NOW), (e: unknown) => isControlAuthError(e));
}

// --- mintControlSession --------------------------------------------------
{
  const { fetchImpl, calls } = mockFetch(() => mintOk());
  const session = await mintControlSession("owner-key", { fetchImpl, now: () => NOW });
  assert.equal(session.token, TOKEN);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/control/session");
  assert.equal(calls[0].headers["x-friday-api-key"], "owner-key");
  assert.equal(calls[0].cache, "no-store");

  // A 401 from the mint is a key rejection, not a generic failure.
  const denied = mockFetch(() => ({ ok: false, status: 401, statusText: "Unauthorized", body: {} }));
  await assert.rejects(
    mintControlSession("wrong-key", { fetchImpl: denied.fetchImpl, now: () => NOW }),
    (e: unknown) => isControlAuthError(e) && (e as ControlAuthError).code === "control-key-rejected",
  );
  // A 503 is unavailable (backend not configured), not a key problem.
  const down = mockFetch(() => ({ ok: false, status: 503, statusText: "Service Unavailable", body: {} }));
  await assert.rejects(
    mintControlSession("owner-key", { fetchImpl: down.fetchImpl, now: () => NOW }),
    (e: unknown) => isControlAuthError(e) && (e as ControlAuthError).code === "control-unavailable",
  );
}

// --- storage round-trip --------------------------------------------------
{
  const storage = memoryStorage();
  setControlSessionStorage(storage);
  try {
    assert.equal(readStoredControlKey(), null);
    assert.equal(hasStoredControlKey(), false);
    storeControlKey("  owner-key  ");
    assert.equal(readStoredControlKey(), "owner-key");
    assert.equal(storage.getItem(CONTROL_KEY_STORAGE), "owner-key");
    assert.equal(hasStoredControlKey(), true);
    clearStoredControlKey();
    assert.equal(readStoredControlKey(), null);
  } finally {
    setControlSessionStorage(null);
  }
}

// --- getControlSession: cache, refresh margin, no-key -------------------
{
  const storage = memoryStorage({ [CONTROL_KEY_STORAGE]: "owner-key" });
  setControlSessionStorage(storage);
  clearControlSession();
  try {
    const { fetchImpl, calls } = mockFetch(() => mintOk());
    const opts = { fetchImpl, now: () => NOW };
    // First call mints; the second reuses the cached token.
    const first = await getControlSession(opts);
    assert.equal(first?.token, TOKEN);
    assert.equal(calls.length, 1);
    const second = await getControlSession(opts);
    assert.equal(second?.token, TOKEN);
    assert.equal(calls.length, 1);

    // Inside the 5-minute refresh margin the token is re-minted.
    const late = await getControlSession({
      fetchImpl,
      now: () => NOW + 1_200_000 - CONTROL_TOKEN_REFRESH_MARGIN_MS + 1,
    });
    assert.equal(late?.token, TOKEN);
    assert.equal(calls.length, 2);

    // Headers carry the token under the server's header name.
    const headers = await controlAuthHeaders({ fetchImpl, now: () => NOW });
    assert.equal(headers[CONTROL_SESSION_HEADER], TOKEN);

    // No key stored: no mint, no headers — the caller sends the request
    // unauthenticated (loopback works keyless; remote gets the 401 that
    // raises the gate).
    clearStoredControlKey();
    clearControlSession();
    const noKey = mockFetch(() => mintOk());
    assert.equal(await getControlSession({ fetchImpl: noKey.fetchImpl, now: () => NOW }), null);
    assert.equal(noKey.calls.length, 0);
    assert.deepEqual(await controlAuthHeaders({ fetchImpl: noKey.fetchImpl, now: () => NOW }), {});
    await assert.rejects(
      refreshControlSession({ fetchImpl: noKey.fetchImpl, now: () => NOW }),
      (e: unknown) => isControlAuthError(e) && (e as ControlAuthError).code === "control-auth-required",
    );
  } finally {
    stopControlSessionRefresh();
    clearControlSession();
    setControlSessionStorage(null);
  }
}

// --- startControlSessionRefresh: re-mints before expiry ------------------
{
  const storage = memoryStorage({ [CONTROL_KEY_STORAGE]: "owner-key" });
  setControlSessionStorage(storage);
  clearControlSession();
  try {
    let mints = 0;
    // A token that expires 5ms past the refresh margin: the first
    // refresh is due ~immediately, and every re-mint schedules the next.
    const shortMint = () => ({
      ok: true,
      status: 200,
      statusText: "OK",
      body: {
        status: "ok",
        token: TOKEN,
        expires_at: new Date(NOW + CONTROL_TOKEN_REFRESH_MARGIN_MS + 5).toISOString(),
        ttl_seconds: 1200,
      },
    });
    const { fetchImpl } = mockFetch(() => {
      mints += 1;
      return shortMint();
    });
    // minDelayMs compresses the wait so the test can observe a refresh.
    await startControlSessionRefresh({ fetchImpl, now: () => NOW, minDelayMs: 10 });
    assert.equal(mints, 1);
    await new Promise((r) => setTimeout(r, 60));
    assert.ok(mints >= 2, `expected the refresh timer to re-mint, saw ${mints} mint(s)`);
  } finally {
    stopControlSessionRefresh();
    clearControlSession();
    setControlSessionStorage(null);
  }
}

console.log("controlSession.test.ts: all expectations passed");
