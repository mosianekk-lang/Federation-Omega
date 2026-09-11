const SESSION_KEY = 'fuse.mobile.access_token';
const EXPIRY_KEY = 'fuse.mobile.access_token_expiry';
const DEVICE_KEY = 'fuse.mobile.device_token';

export type StoredSession = {
  accessToken: string;
  expiresAt?: string;
  deviceToken?: string;
};

function store(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export async function loadDeviceCredential(): Promise<string | null> {
  return store()?.getItem(DEVICE_KEY)?.trim() || null;
}

export async function saveDeviceCredential(deviceToken: string): Promise<void> {
  if (!deviceToken.trim()) throw new Error('DEVICE_TOKEN_REQUIRED');
  const storage = store();
  if (!storage) throw new Error('WEB_SESSION_STORAGE_UNAVAILABLE');
  storage.setItem(DEVICE_KEY, deviceToken.trim());
}

export async function loadSession(): Promise<StoredSession | null> {
  const storage = store();
  if (!storage) return null;
  const token = storage.getItem(SESSION_KEY)?.trim() ?? '';
  const expiresAt = storage.getItem(EXPIRY_KEY)?.trim() || undefined;
  const deviceToken = storage.getItem(DEVICE_KEY)?.trim() || undefined;
  if (!token) return null;
  if (expiresAt) {
    const expiresMs = Date.parse(expiresAt);
    if (!Number.isFinite(expiresMs) || expiresMs <= Date.now() + 15_000) {
      await clearAccessSession();
      return null;
    }
  }
  return { accessToken: token, expiresAt, deviceToken };
}

export async function saveSession(session: StoredSession): Promise<void> {
  if (!session.accessToken.trim()) throw new Error('SESSION_ACCESS_TOKEN_REQUIRED');
  const storage = store();
  if (!storage) throw new Error('WEB_SESSION_STORAGE_UNAVAILABLE');
  storage.setItem(SESSION_KEY, session.accessToken.trim());
  if (session.expiresAt) storage.setItem(EXPIRY_KEY, session.expiresAt);
  else storage.removeItem(EXPIRY_KEY);
  if (session.deviceToken) storage.setItem(DEVICE_KEY, session.deviceToken.trim());
}

export async function clearAccessSession(): Promise<void> {
  const storage = store();
  storage?.removeItem(SESSION_KEY);
  storage?.removeItem(EXPIRY_KEY);
}

export async function clearSession(): Promise<void> {
  const storage = store();
  storage?.removeItem(SESSION_KEY);
  storage?.removeItem(EXPIRY_KEY);
  storage?.removeItem(DEVICE_KEY);
}
