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

const gateway = process.env.EXPO_PUBLIC_FEDERATION_GATEWAY_URL;

export async function fetchCapabilityManifest(accessToken: string): Promise<FederationCapabilityManifest> {
  if (!gateway) throw new Error('FEDERATION_GATEWAY_UNCONFIGURED');
  const response = await fetch(`${gateway}/v1/capabilities`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!response.ok) throw new Error(`CAPABILITY_MANIFEST_FAILED:${response.status}`);
  return response.json();
}

export async function sendFuseMessage(accessToken: string, request: FuseMessageRequest) {
  if (!gateway) throw new Error('FEDERATION_GATEWAY_UNCONFIGURED');
  const response = await fetch(`${gateway}/v1/chat`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error(`FUSE_CHAT_FAILED:${response.status}`);
  return response.json() as Promise<{ text: string; trace_id?: string }>;
}
