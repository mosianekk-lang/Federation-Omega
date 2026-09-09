import {
  createFuseSession,
  enrollOwner,
  FederationGatewayError,
  sendFuseMessage,
  type FuseChatResponse,
  type FuseMessageRequest,
} from './federation';
import { getIapIdentityToken } from './iap';
import {
  clearAccessSession,
  loadDeviceCredential,
  loadSession,
  saveDeviceCredential,
  saveSession,
  type StoredSession,
} from './session';

const REFRESHABLE_SESSION_REASONS = new Set([
  'SESSION_EXPIRED',
  'SESSION_INVALID',
  'SESSION_DEVICE_BINDING_REQUIRED',
]);

function storedFromResponse(
  response: { access_token: string; expires_at: string },
  deviceToken?: string,
): StoredSession {
  return {
    accessToken: response.access_token,
    expiresAt: response.expires_at,
    deviceToken,
  };
}

export async function connectOwner(): Promise<StoredSession> {
  const iapIdentityToken = await getIapIdentityToken(true);
  const enrollment = await enrollOwner(iapIdentityToken);
  await saveDeviceCredential(enrollment.device_token);
  const session = storedFromResponse(enrollment, enrollment.device_token);
  await saveSession(session);
  return session;
}

async function refreshFromDevice(deviceToken: string): Promise<StoredSession> {
  const iapIdentityToken = await getIapIdentityToken(false);
  const response = await createFuseSession(iapIdentityToken, deviceToken);
  const session = storedFromResponse(response, deviceToken);
  await saveSession(session);
  return session;
}

export async function restoreOwnerSession(): Promise<StoredSession | null> {
  const existing = await loadSession();
  if (existing) return existing;
  const deviceToken = await loadDeviceCredential();
  if (!deviceToken) return null;
  try {
    return await refreshFromDevice(deviceToken);
  } catch {
    return null;
  }
}

export async function ensureOwnerSession(): Promise<StoredSession> {
  const existing = await loadSession();
  if (existing) return existing;
  const deviceToken = await loadDeviceCredential();
  if (!deviceToken) throw new Error('OWNER_CONNECTION_REQUIRED');
  return refreshFromDevice(deviceToken);
}

export async function sendOwnerFuseMessage(request: FuseMessageRequest): Promise<FuseChatResponse> {
  let session = await ensureOwnerSession();
  let iapIdentityToken = await getIapIdentityToken(false);
  try {
    return await sendFuseMessage(iapIdentityToken, session.accessToken, request);
  } catch (error) {
    if (!(error instanceof FederationGatewayError) || error.status !== 401 || !error.reason) throw error;
    if (!REFRESHABLE_SESSION_REASONS.has(error.reason)) throw error;
    const deviceToken = session.deviceToken ?? await loadDeviceCredential();
    if (!deviceToken) throw error;
    await clearAccessSession();
    session = await refreshFromDevice(deviceToken);
    iapIdentityToken = await getIapIdentityToken(false);
    return sendFuseMessage(iapIdentityToken, session.accessToken, request);
  }
}
