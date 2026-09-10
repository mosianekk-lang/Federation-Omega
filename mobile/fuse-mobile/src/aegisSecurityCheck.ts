import Constants from 'expo-constants';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import { getIapIdentityToken } from './iap';
import { ensureOwnerSession } from './ownerConnection';
import { getQualifiedNativeAegisPosture } from './aegisNativePosture';
import {
  type AegisEdgePosture,
  type DeviceFacts,
  buildAegisEdgePosture,
} from './aegisEdgeCore';

export type AegisSecurityCheckReceipt = {
  request_id: string;
  payload_sha256: string;
  pseudonymous_device_id: string;
  event_count: number;
  case_id?: string | null;
  provider_state_verified: boolean;
  provider_effect_performed: boolean;
  status: string;
};

const configuredGateway = process.env.EXPO_PUBLIC_FEDERATION_GATEWAY_URL?.trim().replace(/\/+$/, '');

function gatewayUrl(): string {
  if (!configuredGateway) throw new Error('FEDERATION_GATEWAY_UNCONFIGURED');
  if (!configuredGateway.startsWith('https://') && !configuredGateway.startsWith('http://localhost')) {
    throw new Error('FEDERATION_GATEWAY_INSECURE_URL');
  }
  return configuredGateway;
}

function sampleId(now: Date): string {
  // Per-check correlation ID only. It is not a device identifier and is not persisted.
  const entropy = Math.floor(Math.random() * 0x1_0000_0000).toString(16).padStart(8, '0');
  return `fuse-aegis-${now.getTime().toString(36)}-${entropy}`;
}

function platformName(): DeviceFacts['platform'] {
  if (Platform.OS === 'android' || Platform.OS === 'ios' || Platform.OS === 'windows' || Platform.OS === 'macos') {
    return Platform.OS;
  }
  return 'unknown';
}

export async function collectOwnerTriggeredAegisFacts(): Promise<DeviceFacts> {
  const now = new Date();
  const session = await ensureOwnerSession();
  const [secureStoreAvailable, nativePosture] = await Promise.all([
    SecureStore.isAvailableAsync(),
    getQualifiedNativeAegisPosture(),
  ]);
  return {
    sample_id: sampleId(now),
    collected_at: now.toISOString(),
    consent: true,
    platform: platformName(),
    os_version: String(Platform.Version),
    // Standard Expo APIs do not expose these safely/portably. Unknown stays null;
    // AEGIS must never invent a security signal.
    security_patch: nativePosture?.securityPatch ?? null,
    app_version: Constants.expoConfig?.version ?? null,
    screen_lock_configured: nativePosture?.screenLockConfigured ?? null,
    developer_mode: null,
    adb_enabled: null,
    app_debuggable: nativePosture?.appDebuggable ?? (typeof __DEV__ === 'boolean' ? __DEV__ : null),
    secure_store_available: secureStoreAvailable,
    gateway_url: configuredGateway ?? null,
    session_present: Boolean(session.accessToken),
  };
}

export async function submitOwnerTriggeredAegisPosture(
  posture: AegisEdgePosture,
): Promise<AegisSecurityCheckReceipt> {
  const session = await ensureOwnerSession();
  const iapIdentityToken = await getIapIdentityToken(false);
  const response = await fetch(`${gatewayUrl()}/v1/aegis/posture`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${iapIdentityToken}`,
      'X-Fuse-Authorization': `Bearer ${session.accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(posture),
  });
  const raw = await response.text();
  let body: unknown;
  try { body = raw ? JSON.parse(raw) : undefined; } catch { body = undefined; }
  if (!response.ok) {
    const reason = body && typeof body === 'object' && 'detail' in body
      ? String((body as {detail?: {reason?: string}}).detail?.reason ?? '')
      : '';
    throw new Error(reason || `AEGIS_EDGE_HTTP_${response.status}`);
  }
  if (!body || typeof body !== 'object') throw new Error('AEGIS_EDGE_INVALID_RECEIPT');
  const receipt = body as Partial<AegisSecurityCheckReceipt>;
  if (!receipt.request_id || typeof receipt.event_count !== 'number' || !receipt.status ||
      typeof receipt.provider_state_verified !== 'boolean' || typeof receipt.provider_effect_performed !== 'boolean') {
    throw new Error('AEGIS_EDGE_INVALID_RECEIPT');
  }
  if (receipt.provider_state_verified && !receipt.case_id) {
    throw new Error('AEGIS_EDGE_PROVIDER_CASE_REQUIRED');
  }
  return receipt as AegisSecurityCheckReceipt;
}

/**
 * Explicit owner-triggered security check. No timer, background task, listener,
 * startup hook or continuous collection is registered by this module.
 */
export async function runOwnerTriggeredAegisSecurityCheck(): Promise<AegisSecurityCheckReceipt> {
  const facts = await collectOwnerTriggeredAegisFacts();
  const posture = buildAegisEdgePosture(facts);
  return submitOwnerTriggeredAegisPosture(posture);
}
