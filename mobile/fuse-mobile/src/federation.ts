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
};

export type FederationHealth = {
  status: string;
  version?: string;
  source_head?: string;
  checked_at?: string;
};

const configuredGateway = process.env.EXPO_PUBLIC_FEDERATION_GATEWAY_URL?.trim().replace(/\/+$/, '');

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

async function fetchJson<T>(path: string, options: RequestInit = {}, timeoutMs = 30_000): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${gatewayUrl()}${path}`, {
      ...options,
      signal: controller.signal,
    });
    if (!response.ok) throw new Error(`FEDERATION_GATEWAY_HTTP_${response.status}`);
    return (await response.json()) as T;
  } finally {
    clearTimeout(timeout);
  }
}

function bearer(accessToken: string): Record<string, string> {
  if (!accessToken.trim()) throw new Error('FEDERATION_SESSION_REQUIRED');
  return { Authorization: `Bearer ${accessToken}` };
}

export async function fetchFederationHealth(accessToken?: string): Promise<FederationHealth> {
  return fetchJson<FederationHealth>('/v1/federation/health', {
    headers: accessToken ? bearer(accessToken) : undefined,
  }, 10_000);
}

export async function fetchCapabilityManifest(accessToken: string): Promise<FederationCapabilityManifest> {
  return fetchJson<FederationCapabilityManifest>('/v1/capabilities', {
    headers: bearer(accessToken),
  });
}

export async function sendFuseMessage(accessToken: string, request: FuseMessageRequest): Promise<FuseChatResponse> {
  return fetchJson<FuseChatResponse>('/v1/chat', {
    method: 'POST',
    headers: {
      ...bearer(accessToken),
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  }, 120_000);
}
