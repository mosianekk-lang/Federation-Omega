import assert from "node:assert/strict";
import test from "node:test";
import request from "supertest";
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";
import type { OAuthTokenVerifier } from "@modelcontextprotocol/sdk/server/auth/provider.js";
import type { AuthInfo } from "@modelcontextprotocol/sdk/server/auth/types.js";
import type { BackendApi, EmitInput, FetchResponse, SearchResponse } from "../src/backend.js";
import { createApp, createMcpServer } from "../src/server.js";
import { testConfig } from "./helpers.js";

class FakeBackend implements BackendApi {
  emitCalls = 0;

  async status(): Promise<Record<string, unknown>> {
    return { status: "ready", maturity: "implemented_tested_not_deployed" };
  }

  async search(query: string): Promise<SearchResponse> {
    return { results: [{ id: "node-1", title: query, url: "https://heartbeat.example/items/node-1" }] };
  }

  async fetch(id: string): Promise<FetchResponse> {
    return {
      id,
      title: "Node one",
      text: "Verified metadata",
      url: `https://heartbeat.example/items/${id}`,
      metadata: { authority_ceiling: "A0" },
    };
  }

  async emit(input: EmitInput): Promise<Record<string, unknown>> {
    this.emitCalls += 1;
    return {
      receiptId: "receipt-1",
      acceptedAt: "2026-08-02T22:00:00Z",
      idempotency_hash: input.idempotency_hash,
    };
  }
}

class FakeVerifier implements OAuthTokenVerifier {
  constructor(private readonly scopes: string[]) {}

  async verifyAccessToken(token: string): Promise<AuthInfo> {
    if (token !== "valid-token") throw new Error("invalid token");
    return {
      token,
      clientId: "test-client",
      scopes: this.scopes,
      expiresAt: Math.floor(Date.now() / 1000) + 300,
    };
  }
}

test("protected-resource metadata is public while /mcp requires Bearer auth", async () => {
  const config = testConfig();
  const app = createApp(config, new FakeVerifier(["heartbeat:read"]), new FakeBackend());

  const metadata = await request(app).get("/.well-known/oauth-protected-resource").expect(200);
  assert.equal(metadata.body.resource, config.resourceUrl.href);
  assert.deepEqual(metadata.body.scopes_supported, ["heartbeat:read", "heartbeat:emit"]);

  const denied = await request(app).post("/mcp").send({
    jsonrpc: "2.0",
    id: 1,
    method: "tools/list",
  }).expect(401);
  assert.match(String(denied.headers["www-authenticate"]), /resource_metadata=/);
});

test("effectful MCP call requires heartbeat:emit scope before transport dispatch", async () => {
  const config = testConfig();
  const backend = new FakeBackend();
  const app = createApp(config, new FakeVerifier(["heartbeat:read"]), backend);

  const denied = await request(app)
    .post("/mcp")
    .set("authorization", "Bearer valid-token")
    .send({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: { name: "heartbeat_emit", arguments: {} },
    })
    .expect(403);
  assert.match(String(denied.headers["www-authenticate"]), /insufficient_scope/);
  assert.match(String(denied.headers["www-authenticate"]), /heartbeat:emit/);
  assert.equal(backend.emitCalls, 0);
});

test("raw tools/list mirrors OAuth securitySchemes at top level and in _meta", async () => {
  const config = testConfig();
  const app = createApp(config, new FakeVerifier(["heartbeat:read"]), new FakeBackend());
  const response = await request(app)
    .post("/mcp")
    .set("authorization", "Bearer valid-token")
    .set("accept", "application/json, text/event-stream")
    .set("mcp-protocol-version", "2025-06-18")
    .send({ jsonrpc: "2.0", id: 3, method: "tools/list", params: {} })
    .expect(200);
  const tools = response.body.result?.tools as Array<{
    securitySchemes?: unknown;
    _meta?: { securitySchemes?: unknown };
  }>;
  assert.equal(tools.length, 4);
  for (const tool of tools) {
    assert.deepEqual(tool.securitySchemes, tool._meta?.securitySchemes);
  }
});

test("MCP catalog exposes OAuth schemes and accurate annotations", async () => {
  const backend = new FakeBackend();
  const server = createMcpServer(backend);
  const client = new Client({ name: "gateway-test", version: "1.0.0" });
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  await Promise.all([server.connect(serverTransport), client.connect(clientTransport)]);
  try {
    const catalog = await client.listTools();
    assert.deepEqual(catalog.tools.map((tool) => tool.name).sort(), [
      "fetch",
      "heartbeat_emit",
      "heartbeat_status",
      "search",
    ]);
    for (const tool of catalog.tools) {
      const schemes = tool._meta?.securitySchemes as Array<{ type: string; scopes: string[] }>;
      assert.equal(schemes[0]?.type, "oauth2");
      assert.equal(schemes[0]?.scopes.length, 1);
      assert.equal(tool.annotations?.openWorldHint, false);
      assert.equal(tool.annotations?.destructiveHint, false);
      assert.equal(tool.annotations?.readOnlyHint, tool.name !== "heartbeat_emit");
    }

    const search = await client.callTool({ name: "search", arguments: { query: "runtime" } });
    const searchContent = search.content as Array<{ type: string; text?: string }>;
    assert.equal(searchContent.length, 1);
    assert.equal(searchContent[0]?.type, "text");
    assert.deepEqual(JSON.parse(searchContent[0]?.text ?? "{}"), {
      results: [{ id: "node-1", title: "runtime", url: "https://heartbeat.example/items/node-1" }],
    });

    const invalidEmit = await client.callTool({
      name: "heartbeat_emit",
      arguments: {
        idempotency_hash: `sha256:${"a".repeat(64)}`,
        trace_id: `sha256:${"b".repeat(64)}`,
        root_transaction_id: `sha256:${"c".repeat(64)}`,
        mission_code: "MISSION-A1B2C3D4",
        emitter_node_id: "NODE-ROOT",
        authority_ceiling: "A0",
        state: "NEEDS_CAPABILITY",
        observed_at: "2026-08-02T22:00:00Z",
        expires_at: "2026-08-02T22:05:00Z",
        sequence: 1,
        observations: [{
          source_code: "LOCAL_REPO",
          node_id: "NODE-ROOT",
          capability_code: "CAP-INDEX",
          status: "AVAILABLE",
          confidence_bp: 9000,
          freshness_seconds: 1,
          evidence_count: 3,
          blocker_code: "NONE",
          capability_hash: `sha256:${"d".repeat(64)}`,
          observed_at: "2026-08-02T22:00:00Z",
          semantic_receipt: `sha256:${"e".repeat(64)}`,
        }],
        payload: "must never cross this boundary",
      },
    });
    assert.equal(invalidEmit.isError, true);
    assert.equal(backend.emitCalls, 0);
  } finally {
    await client.close();
    await server.close();
  }
});
