import http from "node:http";
import { authenticate, AuthenticationError } from "./lib/auth.mjs";
import { ALLOWED_ACTIONS, ContractError, OPERATOR_IDENTITY, OPERATOR_VERSION } from "./lib/contracts.mjs";
import { GoogleCloudAdapter } from "./lib/google_cloud.mjs";
import { executeAction } from "./lib/operator.mjs";

const adapter = new GoogleCloudAdapter();
const now = () => new Date().toISOString();

function send(res, status, body) {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  res.end(JSON.stringify({ ...body, checkedAt: now() }));
}

async function readJson(req) {
  const chunks = [];
  let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 1024 * 1024) throw new ContractError("request body exceeds 1 MiB", "BODY_TOO_LARGE");
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try { return JSON.parse(Buffer.concat(chunks).toString("utf8")); }
  catch { throw new ContractError("request body is not valid JSON", "INVALID_JSON"); }
}

export const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://operator.invalid");
    if (req.method === "GET" && url.pathname === "/health") {
      return send(res, 200, { ok: true, status: "OPERATOR_READY", service: OPERATOR_IDENTITY, version: OPERATOR_VERSION, targetService: process.env.TARGET_SERVICE || "architron9", noGmail: true });
    }
    if (req.method === "GET" && url.pathname === "/") {
      return send(res, 200, { ok: true, service: OPERATOR_IDENTITY, version: OPERATOR_VERSION, targetService: process.env.TARGET_SERVICE || "architron9", allowedActions: ALLOWED_ACTIONS, authentication: ["SECRET_MANAGER_TOKEN", "GOOGLE_OIDC_ALLOWLIST"] });
    }
    if (req.method !== "POST" || url.pathname !== "/execute") return send(res, 404, { ok: false, status: "NOT_FOUND" });
    const principal = await authenticate(req.headers);
    const request = await readJson(req);
    const result = await executeAction({ action: String(request.action || "STATUS"), payload: request.payload || {}, principal, adapter });
    return send(res, result.httpStatus, result.body);
  } catch (error) {
    if (error instanceof AuthenticationError) return send(res, 403, { ok: false, status: "DENIED", reason: error.code });
    if (error instanceof ContractError) return send(res, 400, { ok: false, status: "CONTRACT_REJECTED", reason: error.code, message: error.message });
    return send(res, 500, { ok: false, status: "OPERATOR_ERROR", error: String(error?.message || error).slice(0, 2000) });
  }
});

if (process.argv[1] === new URL(import.meta.url).pathname) {
  server.listen(Number(process.env.PORT || 8080), "0.0.0.0", () => console.log(`${OPERATOR_IDENTITY} ${OPERATOR_VERSION} ready`));
}
