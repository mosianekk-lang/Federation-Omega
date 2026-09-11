const IAP_RESOURCE_CLIENT_ID = process.env.EXPO_PUBLIC_FUSE_IAP_RESOURCE_CLIENT_ID?.trim() ?? '';
const WEB_TOKEN_KEY = 'fuse.mobile.iap_id_token';
const GOOGLE_IDENTITY_SCRIPT_ID = 'fuse-google-identity-services';

type CredentialResponse = { credential?: string };
type PromptMomentNotification = {
  isNotDisplayed?: () => boolean;
  isSkippedMoment?: () => boolean;
  getNotDisplayedReason?: () => string;
  getSkippedReason?: () => string;
};
type GoogleIdentityApi = {
  initialize: (config: { client_id: string; callback: (response: CredentialResponse) => void; auto_select?: boolean; cancel_on_tap_outside?: boolean }) => void;
  prompt: (callback?: (notification: PromptMomentNotification) => void) => void;
  disableAutoSelect: () => void;
};
type GoogleIdentityWindow = Window & { google?: { accounts?: { id?: GoogleIdentityApi } } };

let scriptPromise: Promise<GoogleIdentityApi> | null = null;

export function iapConfigured(): boolean {
  return IAP_RESOURCE_CLIENT_ID.length > 0;
}

function browserSession(): Storage | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function tokenIsFresh(token: string): boolean {
  try {
    const payload = token.split('.')[1];
    if (!payload || typeof window === 'undefined') return false;
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    const parsed = JSON.parse(window.atob(padded)) as { exp?: number; aud?: string | string[] };
    const audienceOk = !parsed.aud
      || parsed.aud === IAP_RESOURCE_CLIENT_ID
      || (Array.isArray(parsed.aud) && parsed.aud.includes(IAP_RESOURCE_CLIENT_ID));
    return typeof parsed.exp === 'number'
      && parsed.exp * 1000 > Date.now() + 60_000
      && audienceOk;
  } catch {
    return false;
  }
}

function cachedToken(): string | null {
  const storage = browserSession();
  const value = storage?.getItem(WEB_TOKEN_KEY)?.trim() ?? '';
  if (!value || !tokenIsFresh(value)) {
    storage?.removeItem(WEB_TOKEN_KEY);
    return null;
  }
  return value;
}

function loadGoogleIdentity(): Promise<GoogleIdentityApi> {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return Promise.reject(new Error('OWNER_WEB_IDENTITY_BROWSER_REQUIRED'));
  }
  const existing = (window as GoogleIdentityWindow).google?.accounts?.id;
  if (existing) return Promise.resolve(existing);
  if (scriptPromise) return scriptPromise;

  scriptPromise = new Promise<GoogleIdentityApi>((resolve, reject) => {
    const finish = () => {
      const api = (window as GoogleIdentityWindow).google?.accounts?.id;
      if (api) resolve(api);
      else reject(new Error('GOOGLE_IDENTITY_SERVICES_UNAVAILABLE'));
    };
    const prior = document.getElementById(GOOGLE_IDENTITY_SCRIPT_ID) as HTMLScriptElement | null;
    if (prior) {
      prior.addEventListener('load', finish, { once: true });
      prior.addEventListener('error', () => reject(new Error('GOOGLE_IDENTITY_SERVICES_LOAD_FAILED')), { once: true });
      return;
    }
    const script = document.createElement('script');
    script.id = GOOGLE_IDENTITY_SCRIPT_ID;
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = finish;
    script.onerror = () => reject(new Error('GOOGLE_IDENTITY_SERVICES_LOAD_FAILED'));
    document.head.appendChild(script);
  });
  return scriptPromise;
}

export async function getIapIdentityToken(interactive = false): Promise<string> {
  if (!IAP_RESOURCE_CLIENT_ID) throw new Error('FUSE_IAP_RESOURCE_CLIENT_ID_REQUIRED');
  const existing = cachedToken();
  if (existing) return existing;
  if (!interactive) throw new Error('OWNER_SIGN_IN_REQUIRED');

  const api = await loadGoogleIdentity();
  return new Promise<string>((resolve, reject) => {
    let settled = false;
    const timeout = window.setTimeout(() => finish(undefined, new Error('OWNER_SIGN_IN_TIMEOUT')), 60_000);
    const finish = (token?: string, error?: Error) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timeout);
      if (token) {
        browserSession()?.setItem(WEB_TOKEN_KEY, token);
        resolve(token);
      } else {
        reject(error ?? new Error('OWNER_SIGN_IN_REQUIRED'));
      }
    };
    api.initialize({
      client_id: IAP_RESOURCE_CLIENT_ID,
      auto_select: false,
      cancel_on_tap_outside: false,
      callback: (response) => {
        const token = response.credential?.trim();
        if (!token) finish(undefined, new Error('IAP_ID_TOKEN_REQUIRED'));
        else finish(token);
      },
    });
    api.prompt((notification) => {
      if (notification.isNotDisplayed?.()) {
        finish(undefined, new Error(`OWNER_SIGN_IN_NOT_DISPLAYED:${notification.getNotDisplayedReason?.() ?? 'UNKNOWN'}`));
      } else if (notification.isSkippedMoment?.()) {
        finish(undefined, new Error(`OWNER_SIGN_IN_SKIPPED:${notification.getSkippedReason?.() ?? 'UNKNOWN'}`));
      }
    });
  });
}

export async function signOutOwnerIdentity(): Promise<void> {
  browserSession()?.removeItem(WEB_TOKEN_KEY);
  if (typeof window === 'undefined') return;
  const api = (window as GoogleIdentityWindow).google?.accounts?.id;
  api?.disableAutoSelect();
}
