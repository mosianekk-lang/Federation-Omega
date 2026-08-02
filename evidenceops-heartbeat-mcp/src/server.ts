import crypto from "node:crypto";
import express, { type NextFunction, type Request, type Response } from "express";
import { requireBearerAuth } from "@modelcontextprotocol/sdk/server/auth/middleware/bearerAuth.js";
import type { OAuthTokenVerifier } from "@modelcontextprotocol/sdk/server/auth/provider.js";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { toJsonSchemaCompat } from "@modelcontextprotocol/sdk/server/zod-json-schema-compat.js";
import { ListToolsRequestSchema, type CallToolResult } from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";
import type { BackendApi } from "./backend.js";
import {
  emitInputSchema,
  emitResponseSchema,
  fetchResponseSchema,
  searchResponseSchema,
  statusResponseSchema,
} from "./backend.js";
import type { GatewayConfig } from "./config.js";
import { HEARTBEAT_EMIT_SCOPE, HEARTBEAT_READ_SCOPE } from "./config.js";
import {
  fetchInputSchema,
  requiredScopeForBody,
  searchInputSchema,
  toolMeta,
} from "./tool-catalog.js";

type ToolOperation = () => Promise<CallToolResult>;

function errorResult(): CallToolResult {
  return {
    isError: true,
    content: [{ type: "text", text: "The heartbeat service could not complete this operation." }],
  };
}

async function guarded(operation: ToolOperation): Promise<CallToolResult> {
  try {
    return await operation();
  } catch (error) {
    console.error(JSON.stringify({
      severity: "ERROR",
      event: "heartbeat_tool_failure",
      errorType: error instanceof Error ? error.name : "UnknownError",
    }));
    return errorResult();
  }
}

function jsonToolResult(value: Record<string, unknown>): CallToolResult {
  return {
    content: [{ type: "text", text: JSON.stringify(value) }],
    structuredContent: value,
  };
}

export function createMcpServer(backend: BackendApi): McpServer {
  const server = new McpServer({ name: "EvidenceOps Capability Heartbeat", version: "1.0.0" });

  server.registerTool("heartbeat_status", {
    title: "Heartbeat status",
    description: "Use this when checking the verified EvidenceOps capability-heartbeat status. Read-only.",
    outputSchema: statusResponseSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    _meta: toolMeta(HEARTBEAT_READ_SCOPE),
  }, async () => guarded(async () => {
    const value = await backend.status();
    return {
      content: [{ type: "text", text: JSON.stringify(value) }],
      structuredContent: value,
    };
  }));

  server.registerTool("search", {
    title: "Search heartbeat registry",
    description: "Use this when searching the verified heartbeat emitter and capability registry. Read-only.",
    inputSchema: searchInputSchema,
    outputSchema: searchResponseSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    _meta: toolMeta(HEARTBEAT_READ_SCOPE),
  }, async ({ query }) => guarded(async () => jsonToolResult(await backend.search(query))));

  server.registerTool("fetch", {
    title: "Fetch heartbeat registry item",
    description: "Use this when fetching one exact heartbeat resource returned by search. Read-only.",
    inputSchema: fetchInputSchema,
    outputSchema: fetchResponseSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    _meta: toolMeta(HEARTBEAT_READ_SCOPE),
  }, async ({ id }) => guarded(async () => jsonToolResult(await backend.fetch(id))));

  server.registerTool("heartbeat_emit", {
    title: "Emit heartbeat metadata",
    description: "Use this only when recording bounded heartbeat metadata after authorization. This writes one idempotent receipt and accepts no document, message, evidence, or secret content.",
    inputSchema: emitInputSchema,
    outputSchema: emitResponseSchema,
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
    _meta: toolMeta(HEARTBEAT_EMIT_SCOPE),
  }, async (input) => guarded(async () => {
    const value = await backend.emit(input);
    return {
      content: [{ type: "text", text: JSON.stringify(value) }],
      structuredContent: value,
    };
  }));

  // MCP SDK v1.30 models extension fields in `_meta`, while current OpenAI Apps
  // clients also consume `securitySchemes` at the top level. Replace only the
  // generated list handler so both representations are emitted; tool calls
  // remain on the SDK's validated handler.
  const descriptor = (
    name: string,
    title: string,
    description: string,
    inputSchema: z.ZodObject<z.ZodRawShape>,
    outputSchema: z.ZodObject<z.ZodRawShape>,
    readOnly: boolean,
    scope: string,
  ) => {
    const securitySchemes = [
      { type: "oauth2", scopes: [scope] },
    ];
    return {
      name,
      title,
      description,
      inputSchema: toJsonSchemaCompat(inputSchema),
      outputSchema: toJsonSchemaCompat(outputSchema),
      annotations: {
        readOnlyHint: readOnly,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
      execution: { taskSupport: "forbidden" },
      securitySchemes,
      _meta: { securitySchemes },
    };
  };
  const descriptors = [
    descriptor(
      "heartbeat_status",
      "Heartbeat status",
      "Use this when checking the verified EvidenceOps capability-heartbeat status. Read-only.",
      z.object({}),
      statusResponseSchema,
      true,
      HEARTBEAT_READ_SCOPE,
    ),
    descriptor(
      "search",
      "Search heartbeat registry",
      "Use this when searching the verified heartbeat emitter and capability registry. Read-only.",
      searchInputSchema,
      searchResponseSchema,
      true,
      HEARTBEAT_READ_SCOPE,
    ),
    descriptor(
      "fetch",
      "Fetch heartbeat registry item",
      "Use this when fetching one exact heartbeat resource returned by search. Read-only.",
      fetchInputSchema,
      fetchResponseSchema,
      true,
      HEARTBEAT_READ_SCOPE,
    ),
    descriptor(
      "heartbeat_emit",
      "Emit heartbeat metadata",
      "Use this only when recording bounded heartbeat metadata after authorization. This writes one idempotent receipt and accepts no document, message, evidence, or secret content.",
      emitInputSchema,
      emitResponseSchema,
      false,
      HEARTBEAT_EMIT_SCOPE,
    ),
  ];
  server.server.removeRequestHandler("tools/list");
  server.server.setRequestHandler(ListToolsRequestSchema, () => ({ tools: descriptors } as never));

  return server;
}

function resourceMetadata(config: GatewayConfig): Record<string, unknown> {
  return {
    resource: config.resourceUrl.href,
    authorization_servers: [config.oauthIssuer],
    scopes_supported: [HEARTBEAT_READ_SCOPE, HEARTBEAT_EMIT_SCOPE],
    bearer_methods_supported: ["header"],
    resource_name: "EvidenceOps Capability Heartbeat",
  };
}

function insufficientScope(config: GatewayConfig, requiredScope: string, req: Request, res: Response): void {
  res.set("WWW-Authenticate", [
    "Bearer",
    'error="insufficient_scope"',
    `scope="${requiredScope}"`,
    `resource_metadata="${config.resourceMetadataUrl.href}"`,
  ].join(", "));
  res.status(403).json({
    jsonrpc: "2.0",
    id: req.body && typeof req.body === "object" && !Array.isArray(req.body) ? req.body.id ?? null : null,
    error: { code: -32001, message: "Insufficient OAuth scope" },
  });
}

export function createApp(
  config: GatewayConfig,
  verifier: OAuthTokenVerifier,
  backend: BackendApi,
): express.Express {
  const app = express();
  app.disable("x-powered-by");

  app.use((req: Request, res: Response, next: NextFunction) => {
    const requestId = req.header("x-request-id")?.slice(0, 160) || crypto.randomUUID();
    res.set("x-request-id", requestId);
    res.set("cache-control", "no-store");
    next();
  });

  app.get("/healthz", (_req, res) => {
    res.json({ status: "ok", service: "evidenceops-heartbeat-mcp", version: "1.0.0" });
  });

  const metadata = resourceMetadata(config);
  app.get("/.well-known/oauth-protected-resource", (_req, res) => res.json(metadata));
  app.get("/.well-known/oauth-protected-resource/mcp", (_req, res) => res.json(metadata));

  const bearerAuth = requireBearerAuth({
    verifier,
    resourceMetadataUrl: config.resourceMetadataUrl.href,
  });
  const jsonBody = express.json({ limit: "64kb", strict: true });

  app.all("/mcp", bearerAuth, jsonBody, (req: Request, res: Response, next: NextFunction) => {
    if (Array.isArray(req.body)) {
      res.status(400).json({
        jsonrpc: "2.0",
        id: null,
        error: { code: -32600, message: "JSON-RPC batching is not supported" },
      });
      return;
    }
    const requiredScope = requiredScopeForBody(req.body);
    if (requiredScope && !req.auth?.scopes.includes(requiredScope)) {
      insufficientScope(config, requiredScope, req, res);
      return;
    }
    next();
  }, async (req: Request, res: Response) => {
    const server = createMcpServer(backend);
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
      enableJsonResponse: true,
    });
    res.on("close", () => {
      void transport.close();
      void server.close();
    });
    await server.connect(transport);
    await transport.handleRequest(req, res, req.body);
  });

  app.use((error: unknown, _req: Request, res: Response, _next: NextFunction) => {
    console.error(JSON.stringify({
      severity: "ERROR",
      event: "heartbeat_gateway_request_failure",
      errorType: error instanceof Error ? error.name : "UnknownError",
    }));
    if (!res.headersSent) res.status(500).json({ error: "internal_server_error" });
  });

  return app;
}
