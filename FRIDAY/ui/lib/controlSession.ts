/* ================================================================
   controlSession.ts — the D-023 credential flow for the Halo
   console (TASK-FRD-038 checkpoint 2).

   The problem (diagnosis, checkpoint 1): POST /api/chat is gated
   by _require_control_access since TASK-VAL-007, and the gate
   demands the control API key or a valid fcs1 session token from
   every remote caller — but the Halo console sent neither, so its
   chat answers 401 from any browser that is not on the server
   itself. The gate must NOT be stripped (VAL-005 F2); the console
   must present a credential instead.

   The flow, exactly as the D-023 design and the legacy console
   (FRIDAY/src/friday/api/app.js) do it:

     owner pastes the key once  ->  stored in this browser only
     (localStorage, never sent anywhere except the mint call)
     -> GET /api/control/session with x-friday-api-key
     -> 20-minute HMAC fcs1 token, cached here
     -> X-FRIDAY-Control-Token on chat calls
     -> refresh 5 minutes before the TTL elapses, and retry once
        on a 401 with a freshly minted token.

   The key never leaves the browser's storage except in the mint
   request's header, and the token — not the key — rides on every
   chat call. No key is ever logged, rendered, or committed.

   This module is window-independent except for storage: fetch,
   storage, base URL and clock are all injectable, so it runs under
   plain Node (controlSession.test.ts) as well as in the browser.
   ================================================================ */

export const CONTROL_SESSION_HEADER = "X-FRIDAY-Control-Token";
export const CONTROL_SESSION_MINT_PATH = "/api/control/session";
export const CONTROL_TOKEN_TTL_SECONDS = 1200; // 20 minutes, server-side
export const CONTROL_TOKEN_REFRESH_MARGIN_MS = 300_000; // refresh 5 min early
export const CONTROL_TOKEN_MIN_REFRESH_DELAY_MS = 60_000;

/* The legacy console (app.js) stores the pasted key under this name
   on the same origin, so a key the owner already pasted there works
   here too — paste-once means once per browser, not once per UI. */
export const CONTROL_KEY_STORAGE = "friday_prime_key";

export type ControlAuthCode =
  | "control-auth-required" // no key in this browser; the gate must ask for one
  | "control-key-rejected" // the stored key was refused (rotated / wrong)
  | "control-unavailable"; // the backend cannot mint right now (503 / network)

export class ControlAuthError extends Error {
  code: ControlAuthCode;
  constructor(code: ControlAuthCode, message: string) {
    super(message);
    this.name = "ControlAuthError";
    this.code = code;
  }
}

export function isControlAuthError(error: unknown): error is ControlAuthError {
  return error instanceof ControlAuthError;
}

export interface ControlSession {
  token: string;
  expiresAtMs: number;
}

export type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;
export type FetchLike = (
  input: string,
  init?: { headers?: Record<string, string>; cache?: string },
) => Promise<{
  ok: boolean;
  status: number;
  statusText: string;
  json: () => Promise<unknown>;
  text: () => Promise<string>;
}>;

export interface ControlSessionOptions {
  fetchImpl?: FetchLike;
  /** Same-origin base, e.g. wire's apiBase(). Empty = relative. */
  base?: string;
  storage?: StorageLike | null;
  now?: () => number;
}

/* ------------------------------------------------------------ storage */

/* undefined = resolve localStorage (browser) or null (Node / private
   mode); null = explicitly no storage; an object = use it. The setter
   is the test seam — the app never calls it. */
let storageOverride: StorageLike | null | undefined;

export function setControlSessionStorage(storage: StorageLike | null): void {
  storageOverride = storage;
}

function resolveStorage(explicit?: StorageLike | null): StorageLike | null {
  if (explicit !== undefined) return explicit;
  if (storageOverride !== undefined) return storageOverride;
  try {
    if (typeof localStorage !== "undefined") return localStorage;
  } catch {
    /* private mode / denied: act as if there were no storage */
  }
  return null;
}

function safeGet(storage: StorageLike | null, key: string): string | null {
  if (!storage) return null;
  try {
    return storage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(storage: StorageLike | null, key: string, value: string): void {
  if (!storage) return;
  try {
    storage.setItem(key, value);
  } catch {
    /* private mode: the session still works for this page load */
  }
}

function safeRemove(storage: StorageLike | null, key: string): void {
  if (!storage) return;
  try {
    storage.removeItem(key);
  } catch {
    /* already gone, or private mode */
  }
}

export function readStoredControlKey(options?: ControlSessionOptions): string | null {
  const key = safeGet(resolveStorage(options?.storage), CONTROL_KEY_STORAGE);
  return key && key.trim() ? key.trim() : null;
}

export function hasStoredControlKey(options?: ControlSessionOptions): boolean {
  return readStoredControlKey(options) !== null;
}

export function storeControlKey(key: string, options?: ControlSessionOptions): void {
  safeSet(resolveStorage(options?.storage), CONTROL_KEY_STORAGE, key.trim());
}

export function clearStoredControlKey(options?: ControlSessionOptions): void {
  safeRemove(resolveStorage(options?.storage), CONTROL_KEY_STORAGE);
}

/* --------------------------------------------------------------- minting */

function isValidControlToken(token: unknown): token is string {
  if (typeof token !== "string") return false;
  const parts = token.split(".");
  return parts.length === 3 && parts[0] === "fcs1" && parts[1].length > 0 && parts[2].length > 0;
}

export function parseControlSession(data: unknown, nowMs: number): ControlSession {
  if (!data || typeof data !== "object") {
    throw new ControlAuthError("control-unavailable", "The control session answer was not usable JSON.");
  }
  const record = data as Record<string, unknown>;
  if (!isValidControlToken(record.token)) {
    throw new ControlAuthError("control-unavailable", "The control session answer carried no usable token.");
  }
  let expiresAtMs = Number.NaN;
  if (typeof record.expires_at === "string" && record.expires_at) {
    expiresAtMs = Date.parse(record.expires_at);
  }
  if (!Number.isFinite(expiresAtMs)) {
    const ttl = typeof record.ttl_seconds === "number" ? record.ttl_seconds : CONTROL_TOKEN_TTL_SECONDS;
    expiresAtMs = nowMs + ttl * 1000;
  }
  return { token: record.token as string, expiresAtMs };
}

export async function mintControlSession(
  key: string,
  options?: ControlSessionOptions,
): Promise<ControlSession> {
  const fetchImpl = (options?.fetchImpl ?? globalThis.fetch) as FetchLike;
  const now = options?.now ?? Date.now;
  const base = (options?.base ?? "").replace(/\/+$/, "");
  const res = await fetchImpl(`${base}${CONTROL_SESSION_MINT_PATH}`, {
    headers: { "x-friday-api-key": key.trim() },
    cache: "no-store",
  });
  if (res.status === 401 || res.status === 403) {
    throw new ControlAuthError(
      "control-key-rejected",
      "The owner key was rejected while minting a FRIDAY control session.",
    );
  }
  if (!res.ok) {
    throw new ControlAuthError(
      "control-unavailable",
      `FRIDAY could not mint a control session (${res.status} ${res.statusText}).`,
    );
  }
  return parseControlSession(await res.json(), now());
}

/* ------------------------------------------------------- cached session */

let cachedSession: ControlSession | null = null;

export function clearControlSession(): void {
  cachedSession = null;
}

function sessionUsable(session: ControlSession, nowMs: number): boolean {
  return session.expiresAtMs - nowMs > CONTROL_TOKEN_REFRESH_MARGIN_MS;
}

/** A usable session token, minting one from the stored key when needed.
    Returns null when this browser holds no key — the caller then sends
    the request unauthenticated (loopback works keyless) and the 401 it
    gets back is the signal to show the key gate. */
export async function getControlSession(options?: ControlSessionOptions): Promise<ControlSession | null> {
  const now = options?.now ?? Date.now;
  const nowMs = now();
  if (cachedSession && sessionUsable(cachedSession, nowMs)) return cachedSession;
  const key = readStoredControlKey(options);
  if (!key) return null;
  cachedSession = await mintControlSession(key, options);
  return cachedSession;
}

/** Force a fresh mint from the stored key (401 retry path). Throws
    ControlAuthError when there is no key or the mint is refused. */
export async function refreshControlSession(options?: ControlSessionOptions): Promise<ControlSession> {
  const key = readStoredControlKey(options);
  if (!key) {
    throw new ControlAuthError(
      "control-auth-required",
      "No owner key is stored in this browser, so no control session can be minted.",
    );
  }
  cachedSession = await mintControlSession(key, options);
  return cachedSession;
}

/** Headers for an authenticated control call — empty when this browser
    holds no key, so loopback callers keep working keyless. */
export async function controlAuthHeaders(
  options?: ControlSessionOptions,
): Promise<Record<string, string>> {
  const session = await getControlSession(options);
  return session ? { [CONTROL_SESSION_HEADER]: session.token } : {};
}

/* --------------------------------------------------- background refresh */

let refreshTimer: ReturnType<typeof setTimeout> | null = null;

export function stopControlSessionRefresh(): void {
  if (refreshTimer !== null) {
    clearTimeout(refreshTimer);
    refreshTimer = null;
  }
}

/** Keep the session warm: re-mint before the TTL elapses and schedule
    the next refresh. A failed refresh clears the cache and stops the
    timer — the next chat call mints on demand instead of spinning. */
export async function startControlSessionRefresh(
  options?: ControlSessionOptions & { minDelayMs?: number },
): Promise<void> {
  stopControlSessionRefresh();
  const session = await getControlSession(options);
  if (!session) return;
  const now = options?.now ?? Date.now;
  const minDelay = options?.minDelayMs ?? CONTROL_TOKEN_MIN_REFRESH_DELAY_MS;
  const delay = Math.max(minDelay, session.expiresAtMs - now() - CONTROL_TOKEN_REFRESH_MARGIN_MS);
  refreshTimer = setTimeout(() => {
    refreshControlSession(options)
      .then(() => void startControlSessionRefresh(options))
      .catch(() => {
        clearControlSession();
        stopControlSessionRefresh();
      });
  }, delay);
}
