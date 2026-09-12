export type FuseMode = 'AUTO' | 'FAST' | 'THINK' | 'CREATE' | 'BUILD' | 'RESEARCH' | 'EXECUTE' | 'PRIVATE';

export type Capability = {
  capability_id: string;
  kind: string;
  route: string;
  health: string;
  authority: string;
  freshness_ttl_seconds: number;
};

export type FederationCapabilityManifest = {
  schema: 'FUSE-MOBILE-GATEWAY-V1';
  version: string;
  subject: string;
  issued_at: string;
  expires_at: string;
  capabilities: Capability[];
  source_scopes: string[];
  model_scopes: string[];
  agent_scopes: string[];
  tool_scopes: string[];
  policies: Record<string, string>;
};

export type FuseMessageRequest = {
  intent: string;
  mode: FuseMode;
  verification: 'NORMAL' | 'HIGH';
};

export type FuseChatResponse = {
  text: string;
  trace_id?: string;
  status?: string;
  provider?: string;
  model?: string;
  source_refs?: string[];
};

export type FederationHealth = {
  status: string;
  version?: string;
  source_head?: string;
  checked_at?: string;
};

export type FuseSessionResponse = {
  access_token: string;
  token_type: string;
  expires_at: string;
  subject: string;
};

export type FuseEnrollmentResponse = FuseSessionResponse & {
  device_token: string;
  device_token_type: string;
  device_token_recoverable: boolean;
  owner_identity_source?: string;
};

const configuredGateway = process.env.EXPO_PUBLIC_FEDERATION_GATEWAY_URL?.trim().replace(/\/+$/, '');

export class FederationGatewayError extends Error {
  readonly status: number;
  readonly reason?: string;

  constructor(status: number, reason?: string) {
    super(reason ? `FEDERATION_GATEWAY_HTTP_${status}:${reason}` : `FEDERATION_GATEWAY_HTTP_${status}`);
    this.name = 'FederationGatewayError';
    this.status = status;
    this.reason = reason;
  }
}

export function federationGatewayConfigured(): boolean {
  return Boolean(configuredGateway);
}

function gatewayUrl(): string {
  if (!configuredGateway) throw new Error('FEDERATION_GATEWAY_UNCONFIGURED');
  if (!configuredGateway.startsWith('https://') && !configuredGateway.startsWith('http://localhost')) {
    throw new Error('FEDERATION_GATEWAY_INSECURE_URL');
  }
  return configuredGateway;
}

function transportHeaders(iapIdentityToken: string, fuseCredential?: string): Record<string, string> {
  if (!iapIdentityToken.trim()) throw new Error('IAP_ID_TOKEN_REQUIRED');
  const headers: Record<string, string> = {
    Authorization: `Bearer ${iapIdentityToken.trim()}`,
  };
  if (fuseCredential?.trim()) {
    headers['X-Fuse-Authorization'] = `Bearer ${fuseCredential.trim()}`;
  }
  return headers;
}

async function fetchJson<T>(
  path: string,
  iapIdentityToken: string,
  options: RequestInit = {},
  fuseCredential?: string,
  timeoutMs = 30_000,
  externalSignal?: AbortSignal,
): Promise<T> {
  const controller = new AbortController();
  const onExternalAbort = () => controller.abort();
  externalSignal?.addEventListener('abort', onExternalAbort, { once: true });
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${gatewayUrl()}${path}`, {
      ...options,
      headers: {
        ...transportHeaders(iapIdentityToken, fuseCredential),
        ...((options.headers as Record<string, string> | undefined) ?? {}),
      },
      signal: controller.signal,
    });
    const raw = await response.text();
    let parsed: unknown;
    if (raw) {
      try {
        parsed = JSON.parse(raw);
      } catch {
        parsed = undefined;
      }
    }
    if (!response.ok) {
      const detail = parsed && typeof parsed === 'object' && 'detail' in parsed
        ? (parsed as { detail?: { reason?: string } }).detail
        : undefined;
      throw new FederationGatewayError(response.status, detail?.reason);
    }
    if (parsed === undefined) throw new Error('FEDERATION_GATEWAY_INVALID_JSON');
    return parsed as T;
  } finally {
    clearTimeout(timeout);
    externalSignal?.removeEventListener('abort', onExternalAbort);
  }
}

export async function enrollOwner(iapIdentityToken: string): Promise<FuseEnrollmentResponse> {
  return fetchJson<FuseEnrollmentResponse>('/v1/enroll', iapIdentityToken, { method: 'POST' });
}

export async function createFuseSession(
  iapIdentityToken: string,
  deviceToken: string,
): Promise<FuseSessionResponse> {
  if (!deviceToken.trim()) throw new Error('FEDERATION_DEVICE_REQUIRED');
  return fetchJson<FuseSessionResponse>('/v1/session', iapIdentityToken, { method: 'POST' }, deviceToken);
}

export async function fetchFederationHealth(
  iapIdentityToken: string,
  accessToken: string,
): Promise<FederationHealth> {
  return fetchJson<FederationHealth>('/v1/federation/health', iapIdentityToken, {}, accessToken, 10_000);
}

export async function fetchCapabilityManifest(
  iapIdentityToken: string,
  accessToken: string,
): Promise<FederationCapabilityManifest> {
  return fetchJson<FederationCapabilityManifest>('/v1/capabilities', iapIdentityToken, {}, accessToken);
}

export async function sendFuseMessage(
  iapIdentityToken: string,
  accessToken: string,
  request: FuseMessageRequest,
  signal?: AbortSignal,
): Promise<FuseChatResponse> {
  return fetchJson<FuseChatResponse>(
    '/v1/chat',
    iapIdentityToken,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    },
    accessToken,
    120_000,
    signal,
  );
}
