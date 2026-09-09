import * as SecureStore from 'expo-secure-store';

const SESSION_KEY = 'fuse.mobile.access_token';
const EXPIRY_KEY = 'fuse.mobile.access_token_expiry';
const DEVICE_KEY = 'fuse.mobile.device_token';

export type StoredSession = {
  accessToken: string;
  expiresAt?: string;
  deviceToken?: string;
};

export async function loadDeviceCredential(): Promise<string | null> {
  const token = await SecureStore.getItemAsync(DEVICE_KEY);
  return token?.trim() || null;
}

export async function saveDeviceCredential(deviceToken: string): Promise<void> {
  if (!deviceToken.trim()) throw new Error('DEVICE_TOKEN_REQUIRED');
  await SecureStore.setItemAsync(DEVICE_KEY, deviceToken.trim());
}

export async function loadSession(): Promise<StoredSession | null> {
  const [token, expiresAt, deviceToken] = await Promise.all([
    SecureStore.getItemAsync(SESSION_KEY),
    SecureStore.getItemAsync(EXPIRY_KEY),
    SecureStore.getItemAsync(DEVICE_KEY),
  ]);
  if (!token) return null;
  if (expiresAt) {
    const expiresMs = Date.parse(expiresAt);
    if (!Number.isFinite(expiresMs) || expiresMs <= Date.now() + 15_000) {
      await clearAccessSession();
      return null;
    }
  }
  return {
    accessToken: token,
    expiresAt: expiresAt ?? undefined,
    deviceToken: deviceToken ?? undefined,
  };
}

export async function saveSession(session: StoredSession): Promise<void> {
  if (!session.accessToken.trim()) throw new Error('SESSION_ACCESS_TOKEN_REQUIRED');
  await SecureStore.setItemAsync(SESSION_KEY, session.accessToken.trim());
  if (session.expiresAt) {
    await SecureStore.setItemAsync(EXPIRY_KEY, session.expiresAt);
  } else {
    await SecureStore.deleteItemAsync(EXPIRY_KEY);
  }
  if (session.deviceToken) await saveDeviceCredential(session.deviceToken);
}

export async function clearAccessSession(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(SESSION_KEY),
    SecureStore.deleteItemAsync(EXPIRY_KEY),
  ]);
}

export async function clearSession(): Promise<void> {
  await Promise.all([
    clearAccessSession(),
    SecureStore.deleteItemAsync(DEVICE_KEY),
  ]);
}
