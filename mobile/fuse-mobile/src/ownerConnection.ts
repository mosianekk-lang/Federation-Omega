import {
  createFuseSession,
  enrollOwner,
  FederationGatewayError,
  sendFuseMessage,
  type FuseChatResponse,
  type FuseMessageRequest,
} from './federation';
import { captureEvolutionOutcome, type EvolutionReceipt } from './evolutionRuntime';
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

let lastEvolutionReceipt: EvolutionReceipt | null = null;

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

function failureClass(error: unknown): string {
  if (error instanceof FederationGatewayError) {
    return `GATEWAY_HTTP_${error.status}${error.reason ? `:${error.reason}` : ''}`;
  }
  if (error instanceof Error && error.name) return error.name;
  return 'UNCLASSIFIED_CLIENT_FAILURE';
}

function captureOwnerEvolution(input: Parameters<typeof captureEvolutionOutcome>[0]): EvolutionReceipt | null {
  try {
    lastEvolutionReceipt = captureEvolutionOutcome(input);
    return lastEvolutionReceipt;
  } catch {
    return null;
  }
}

export function getLastOwnerEvolutionReceipt(): EvolutionReceipt | null {
  return lastEvolutionReceipt;
}

export async function connectOwner(): Promise<StoredSession> {
  const started = Date.now();
  try {
    const iapIdentityToken = await getIapIdentityToken(true);
    const enrollment = await enrollOwner(iapIdentityToken);
    await saveDeviceCredential(enrollment.device_token);
    const session = storedFromResponse(enrollment, enrollment.device_token);
    await saveSession(session);
    captureOwnerEvolution({
      kind: 'SUCCESS',
      operation: 'OWNER_CONNECT',
      status: 'OWNER_ENROLLED',
      evidenceRefs: ['PROVIDER:OWNER_ENROLLMENT_READBACK'],
      latencyMs: Date.now() - started,
      successfulTechnique: 'governed owner enrollment and device-bound session establishment',
    });
    return session;
  } catch (error) {
    captureOwnerEvolution({
      kind: 'FAILURE',
      operation: 'OWNER_CONNECT',
      status: 'OWNER_CONNECT_FAILED',
      evidenceRefs: [`LOCAL:${failureClass(error)}`],
      latencyMs: Date.now() - started,
      failureClass: failureClass(error),
    });
    throw error;
  }
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

async function sendOwnerFuseMessageWithRefresh(
  request: FuseMessageRequest,
  signal?: AbortSignal,
): Promise<FuseChatResponse> {
  let session = await ensureOwnerSession();
  let iapIdentityToken = await getIapIdentityToken(false);
  try {
    return await sendFuseMessage(iapIdentityToken, session.accessToken, request, signal);
  } catch (error) {
    if (signal?.aborted) throw error;
    if (!(error instanceof FederationGatewayError) || error.status !== 401 || !error.reason) throw error;
    if (!REFRESHABLE_SESSION_REASONS.has(error.reason)) throw error;
    const deviceToken = session.deviceToken ?? await loadDeviceCredential();
    if (!deviceToken) throw error;
    await clearAccessSession();
    session = await refreshFromDevice(deviceToken);
    iapIdentityToken = await getIapIdentityToken(false);
    return sendFuseMessage(iapIdentityToken, session.accessToken, request, signal);
  }
}

export async function sendOwnerFuseMessage(
  request: FuseMessageRequest,
  signal?: AbortSignal,
): Promise<FuseChatResponse> {
  const started = Date.now();
  try {
    const response = await sendOwnerFuseMessageWithRefresh(request, signal);
    captureOwnerEvolution({
      kind: 'SUCCESS',
      operation: 'FUSE_REQUEST',
      mode: request.mode,
      status: response.status ?? 'OK',
      evidenceRefs: response.trace_id
        ? [`TRACE:${response.trace_id}`]
        : [`PROVIDER:CHAT_READBACK:${response.status ?? 'OK'}`],
      latencyMs: Date.now() - started,
      successfulTechnique: `${request.mode} governed gateway route with provider readback`,
      requirements: [
        'preserve request cancellation support',
        'preserve provider/source/trace proof visibility when returned',
      ],
    });
    return response;
  } catch (error) {
    const cancelled = Boolean(signal?.aborted);
    captureOwnerEvolution({
      kind: cancelled ? 'BLOCKED' : 'FAILURE',
      operation: 'FUSE_REQUEST',
      mode: request.mode,
      status: cancelled ? 'REQUEST_CANCELLED' : 'REQUEST_FAILED',
      evidenceRefs: [cancelled ? 'LOCAL:USER_CANCELLED_REQUEST' : `LOCAL:${failureClass(error)}`],
      latencyMs: Date.now() - started,
      failureClass: cancelled ? 'USER_CANCELLED' : failureClass(error),
      requirements: [
        'preserve request cancellation support',
        'retry only through bounded governed routes',
      ],
    });
    throw error;
  }
}
