import { GoogleAuth } from "google-auth-library";
import { z } from "zod";
import type { GatewayConfig } from "./config.js";

const hashSchema = z.string().regex(/^sha256:[a-f0-9]{64}$/);
const utcSchema = z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
const nodeSchema = z.string().regex(/^NODE-[A-Z0-9]{1,32}(?:-[0-9]{1,8})?$/);

const observationSchema = z.object({
  source_code: z.enum(["LOCAL_BIBLE", "LOCAL_REPO", "FORMATION_STATE"]),
  node_id: nodeSchema,
  capability_code: z.string().regex(/^(?:CAP|CAPABILITY)-[A-Z0-9]{1,40}$/),
  status: z.enum(["AVAILABLE", "DEGRADED", "UNAVAILABLE"]),
  confidence_bp: z.number().int().min(0).max(10_000),
  freshness_seconds: z.number().int().min(0).max(86_400),
  evidence_count: z.number().int().min(0).max(1_000_000),
  blocker_code: z.enum([
    "NONE",
    "CAPABILITY_ABSENT",
    "AUTHORITY_UNAVAILABLE",
    "ATTACHMENT_UNPROVEN",
    "INVENTORY_UNAVAILABLE",
    "SOURCE_STALE",
    "SEMANTIC_DRIFT",
    "CIRCUIT_OPEN",
    "RATE_LIMITED",
    "STOP_FENCED",
  ]),
  capability_hash: hashSchema,
  observed_at: utcSchema,
  semantic_receipt: hashSchema,
}).strict();

export const emitInputSchema = z.object({
  idempotency_hash: hashSchema,
  trace_id: hashSchema,
  root_transaction_id: hashSchema,
  mission_code: z.string().regex(/^MISSION-[A-F0-9]{8}$/),
  emitter_node_id: nodeSchema,
  authority_ceiling: z.literal("A0").default("A0"),
  state: z.enum(["IDLE", "NEEDS_CAPABILITY", "BLOCKED", "READY", "STOPPED"]),
  observed_at: utcSchema,
  expires_at: utcSchema,
  sequence: z.number().int().min(0).max(Number.MAX_SAFE_INTEGER),
  observations: z.array(observationSchema).min(1).max(32),
}).strict();

const resourceSummarySchema = z.object({
  resource_id: z.string().regex(/^(?:emitter\/[A-Z][A-Z0-9_.:-]{2,63}|heartbeat\/sha256:[a-f0-9]{64})$/),
  resource_kind: z.enum(["EMITTER", "HEARTBEAT"]),
  emitter_node_id: nodeSchema,
  authority_ceiling: z.literal("A0"),
  state_code: z.string().regex(/^[A-Z][A-Z0-9_.:-]{2,63}$/),
  observed_at: utcSchema,
  semantic_hash: hashSchema,
}).strict();

const nativeSearchResponseSchema = z.object({
  results: z.array(resourceSummarySchema),
  offset: z.number().int().nonnegative(),
  next_offset: z.number().int().nonnegative().nullable(),
  total: z.number().int().nonnegative(),
}).strict();

const nativeFetchResponseSchema = z.object({
  resource: z.record(z.unknown()),
  semantic_hash: hashSchema,
}).strict();

export const statusResponseSchema = z.object({
  schema: z.string().min(1),
  maturity: z.string().min(1),
  authority_ceiling: z.literal("A0"),
  recommendation_only: z.boolean(),
  ready: z.boolean(),
  readiness_reasons: z.array(z.string()),
  registry_source_code: z.string(),
  store: z.object({
    healthy: z.boolean(),
    backend_code: z.string(),
    durability_class: z.string(),
    object_count: z.number().int().nonnegative(),
  }).passthrough(),
  authority: z.record(z.unknown()).nullable(),
  live_awareness_flags: z.record(z.boolean()),
}).strict();

const ingestResponseSchema = z.object({
  resource_id: z.string().regex(/^heartbeat\/sha256:[a-f0-9]{64}$/),
  idempotency_hash: hashSchema,
  envelope_id: hashSchema,
  receipt_id: hashSchema,
  object_hash: hashSchema,
  authority_ceiling: z.literal("A0"),
  created: z.boolean(),
  replayed: z.boolean(),
}).strict();

const readbackResponseSchema = z.object({
  schema: z.string().min(1),
  verified: z.literal(true),
  resource_id: z.string().regex(/^heartbeat\/sha256:[a-f0-9]{64}$/),
  idempotency_hash: hashSchema,
  envelope_id: hashSchema,
  receipt_id: hashSchema,
  object_hash: hashSchema,
  semantic_hash: hashSchema,
  authority_ceiling: z.literal("A0"),
}).strict();

export const searchResponseSchema = z.object({
  results: z.array(z.object({ id: z.string(), title: z.string(), url: z.string().url() })).max(100),
});
export const fetchResponseSchema = z.object({
  id: z.string(),
  title: z.string(),
  text: z.string(),
  url: z.string().url(),
  metadata: z.record(z.unknown()),
});

export const emitResponseSchema = z.object({
  ingest: ingestResponseSchema,
  readback: readbackResponseSchema,
}).strict();

export type EmitInput = z.infer<typeof emitInputSchema>;
export type SearchResponse = z.infer<typeof searchResponseSchema>;
export type FetchResponse = z.infer<typeof fetchResponseSchema>;

export interface IdentityTokenProvider {
  getIdToken(audience: string): Promise<string>;
}

export class GoogleIdentityTokenProvider implements IdentityTokenProvider {
  private readonly auth = new GoogleAuth();

  async getIdToken(audience: string): Promise<string> {
    const client = await this.auth.getIdTokenClient(audience);
    return client.idTokenProvider.fetchIdToken(audience);
  }
}

export interface BackendApi {
  status(): Promise<Record<string, unknown>>;
  search(query: string): Promise<SearchResponse>;
  fetch(id: string): Promise<FetchResponse>;
  emit(input: EmitInput): Promise<Record<string, unknown>>;
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value));
}

export class HeartbeatBackendClient implements BackendApi {
  constructor(
    private readonly config: GatewayConfig,
    private readonly identity: IdentityTokenProvider,
    private readonly fetchImpl: typeof fetch = fetch,
  ) {}

  private resourceUrl(resourceId: string): string {
    const url = new URL(this.config.resourceUrl);
    url.searchParams.set("resource", resourceId);
    return url.href;
  }

  private async request(path: string, init: RequestInit = {}): Promise<unknown> {
    const idToken = await this.identity.getIdToken(this.config.backendAudience);
    const url = new URL(path, `${this.config.backendUrl.href.replace(/\/$/, "")}/`);
    const headers = new Headers(init.headers);
    headers.set("accept", "application/json");
    headers.set("x-serverless-authorization", `Bearer ${idToken}`);
    headers.set("x-evidenceops-internal-auth", this.config.internalAuthValue);
    if (init.body !== undefined) headers.set("content-type", "application/json");
    headers.delete("authorization");

    const response = await this.fetchImpl(url, {
      ...init,
      headers,
      signal: AbortSignal.timeout(this.config.backendTimeoutMs),
    });
    if (!response.ok) throw new Error(`Heartbeat backend returned HTTP ${response.status}`);
    const declaredLength = Number(response.headers.get("content-length") || "0");
    if (declaredLength > this.config.maxBackendResponseBytes) {
      throw new Error("Heartbeat backend response exceeded the configured limit");
    }
    const text = await response.text();
    if (Buffer.byteLength(text, "utf8") > this.config.maxBackendResponseBytes) {
      throw new Error("Heartbeat backend response exceeded the configured limit");
    }
    try {
      return JSON.parse(text) as unknown;
    } catch {
      throw new Error("Heartbeat backend returned invalid JSON");
    }
  }

  async status(): Promise<Record<string, unknown>> {
    return statusResponseSchema.parse(await this.request("v1/status"));
  }

  async search(query: string): Promise<SearchResponse> {
    const needle = query.trim().toLowerCase();
    const terms = needle.split(/[^a-z0-9_.:-]+/).filter(Boolean);
    const matched: Array<{ id: string; title: string; url: string }> = [];
    let offset = 0;
    for (let page = 0; page < 10; page += 1) {
      const native = nativeSearchResponseSchema.parse(await this.request("v1/search", {
        method: "POST",
        body: JSON.stringify({ resource_kind: "ALL", authority_ceiling: "A0", offset, limit: 100 }),
      }));
      for (const item of native.results) {
        const searchable = canonicalJson(item).toLowerCase();
        if (terms.every((term) => searchable.includes(term))) {
          matched.push({
            id: item.resource_id,
            title: `${item.resource_kind}: ${item.emitter_node_id} (${item.state_code})`,
            url: this.resourceUrl(item.resource_id),
          });
        }
      }
      if (matched.length >= 100 || native.next_offset === null) break;
      offset = native.next_offset;
    }
    return searchResponseSchema.parse({ results: matched.slice(0, 100) });
  }

  async fetch(id: string): Promise<FetchResponse> {
    const native = nativeFetchResponseSchema.parse(
      await this.request(`v1/resources/${encodeURIComponent(id).replaceAll("%2F", "/")}`),
    );
    const kind = typeof native.resource.resource_kind === "string" ? native.resource.resource_kind : "HEARTBEAT";
    return fetchResponseSchema.parse({
      id,
      title: `${kind}: ${id}`,
      text: canonicalJson(native.resource),
      url: this.resourceUrl(id),
      metadata: { semantic_hash: native.semantic_hash, authority_ceiling: native.resource.authority_ceiling ?? "A0" },
    });
  }

  async emit(input: EmitInput): Promise<Record<string, unknown>> {
    const validated = emitInputSchema.parse(input);
    const ingest = ingestResponseSchema.parse(await this.request("v1/ingest", {
      method: "POST",
      body: JSON.stringify(validated),
    }));
    const readback = readbackResponseSchema.parse(
      await this.request(`v1/readback/${validated.idempotency_hash}`),
    );
    const proofFields = [
      "resource_id",
      "idempotency_hash",
      "envelope_id",
      "receipt_id",
      "object_hash",
      "authority_ceiling",
    ] as const;
    for (const field of proofFields) {
      if (readback[field] !== ingest[field]) {
        throw new Error(`Heartbeat readback did not match ingest proof field: ${field}`);
      }
    }
    return emitResponseSchema.parse({ ingest, readback });
  }
}
