import express, { Request, Response } from "express";
import crypto from "node:crypto";
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";

const PORT = Number(process.env.PORT || 8080);
const OPERATOR_URL = (process.env.FO_OPERATOR_URL || "").replace(/\/$/, "");
const FO_ADMIN_TOKEN = process.env.FO_ADMIN_TOKEN || "";
const MCP_ACCESS_TOKEN = process.env.MCP_ACCESS_TOKEN || "";

if (!OPERATOR_URL || !FO_ADMIN_TOKEN || !MCP_ACCESS_TOKEN) {
  throw new Error("FO_OPERATOR_URL, FO_ADMIN_TOKEN and MCP_ACCESS_TOKEN are required");
}

function secureEqual(a: string, b: string): boolean {
  const aa = Buffer.from(a);
  const bb = Buffer.from(b);
  return aa.length === bb.length && crypto.timingSafeEqual(aa, bb);
}

function authorised(req: Request): boolean {
  const auth = req.header("authorization") || "";
  const token = auth.startsWith("Bearer ") ? auth.slice(7) : "";
  return secureEqual(token, MCP_ACCESS_TOKEN);
}

async function operator(action: string, payload: Record<string, unknown>) {
  const response = await fetch(`${OPERATOR_URL}/execute`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-fo-admin-token": FO_ADMIN_TOKEN,
    },
    body: JSON.stringify({ action, payload }),
    signal: AbortSignal.timeout(90_000),
  });
  const text = await response.text();
  let body: unknown;
  try { body = JSON.parse(text); } catch { body = { raw: text }; }
  if (!response.ok) throw new Error(`Operator ${response.status}: ${text.slice(0, 1000)}`);
  return body;
}

function toolResult(value: unknown) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(value, null, 2) }],
    structuredContent: value as Record<string, unknown>,
  };
}

function createServer() {
  const server = new McpServer({ name: "EvidenceOps Federation Bridge", version: "1.0.0" });

  server.tool(
    "search",
    "Use this when searching EvidenceOps, Federation Omega, Apps Script, Drive-ingestion, runtime receipts or case-control records. Read-only.",
    { query: z.string().min(1).max(500) },
    { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    async ({ query }) => toolResult(await operator("search_registry", { query }))
  );

  server.tool(
    "fetch",
    "Use this when reading one exact resource returned by search. Read-only.",
    { id: z.string().min(1).max(500) },
    { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    async ({ id }) => toolResult(await operator("fetch_resource", { id }))
  );

  server.tool(
    "apps_script_list",
    "Use this when listing Apps Script projects available to the authorised Federation Omega operator. Read-only.",
    {},
    { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    async () => toolResult(await operator("apps_script_list", {}))
  );

  server.tool(
    "apps_script_get",
    "Use this when reading source and metadata for one Apps Script project. Read-only.",
    { scriptId: z.string().min(10).max(200) },
    { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    async ({ scriptId }) => toolResult(await operator("apps_script_get", { scriptId }))
  );

  server.tool(
    "ingest_official_url",
    "Use this when preserving an allowlisted official public document into the designated EvidenceOps Drive folder with SHA-256 and provenance receipts. Creates Drive files and therefore requires approval.",
    {
      url: z.string().url(),
      destinationFolderId: z.string().min(10).max(200),
      filename: z.string().min(1).max(240).optional(),
      expectedSha256: z.string().regex(/^[a-fA-F0-9]{64}$/).optional(),
    },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    async (input) => toolResult(await operator("evidenceops_ingest_url", input))
  );

  server.tool(
    "apps_script_backup",
    "Use this when creating a restorable backup and integrity receipt for one Apps Script project. Creates backup records and requires approval.",
    { scriptId: z.string().min(10).max(200) },
    { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: false },
    async ({ scriptId }) => toolResult(await operator("apps_script_backup", { scriptId }))
  );

  server.tool(
    "apps_script_deploy",
    "Use this only after explicit approval to deploy a verified Apps Script version. This changes a live deployment.",
    {
      scriptId: z.string().min(10).max(200),
      versionNumber: z.number().int().positive(),
      description: z.string().min(1).max(500),
    },
    { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: false },
    async (input) => toolResult(await operator("apps_script_deploy", input))
  );

  return server;
}

const app = express();
app.use(express.json({ limit: "2mb" }));

app.get("/health", (_req: Request, res: Response) => {
  res.json({
    status: "ok",
    service: "evidenceops-mcp-adapter",
    version: "1.0.0",
    auth: "bearer-required",
    operatorConfigured: Boolean(OPERATOR_URL && FO_ADMIN_TOKEN),
    noSendGate: true,
  });
});

app.all("/mcp", async (req: Request, res: Response) => {
  if (!authorised(req)) return res.status(401).json({ error: "unauthorised" });
  const server = createServer();
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  res.on("close", () => { void transport.close(); void server.close(); });
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

app.listen(PORT, "0.0.0.0", () => console.log(`EvidenceOps MCP adapter listening on ${PORT}`));
