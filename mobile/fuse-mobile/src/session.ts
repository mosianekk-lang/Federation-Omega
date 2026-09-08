import * as SecureStore from 'expo-secure-store';

const ACCESS_TOKEN_KEY = 'fuse.mobile.access_token';
const ACCESS_TOKEN_EXPIRY_KEY = 'fuse.mobile.access_token_expiry';

export type StoredSession = {
  accessToken: string;
  expiresAt?: string;
};

export async function saveSession(session: StoredSession): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_TOKEN_KEY, session.accessToken, {
    keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
  });
  if (session.expiresAt) {
    await SecureStore.setItemAsync(ACCESS_TOKEN_EXPIRY_KEY, session.expiresAt, {
      keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY,
    });
  } else {
    await SecureStore.deleteItemAsync(ACCESS_TOKEN_EXPIRY_KEY);
  }
}

export async function loadSession(): Promise<StoredSession | null> {
  const accessToken = await SecureStore.getItemAsync(ACCESS_TOKEN_KEY);
  if (!accessToken) return null;

  const expiresAt = await SecureStore.getItemAsync(ACCESS_TOKEN_EXPIRY_KEY);
  if (expiresAt && Date.parse(expiresAt) <= Date.now()) {
    await clearSession();
    return null;
  }

  return { accessToken, ...(expiresAt ? { expiresAt } : {}) };
}

export async function clearSession(): Promise<void> {
  await Promise.all([
    SecureStore.deleteItemAsync(ACCESS_TOKEN_KEY),
    SecureStore.deleteItemAsync(ACCESS_TOKEN_EXPIRY_KEY),
  ]);
}
