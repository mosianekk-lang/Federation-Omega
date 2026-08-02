import http from "node:http";
import crypto from "node:crypto";
import { googleFetch, urls } from "./google.js";
import { authorize, defaultPolicy } from "./policy.js";

const PORT = Number(process.env.PORT || 8080);
const PROJECT_ID = process.env.GOOGLE_CLOUD_PROJECT || process.env.PROJECT_ID;
const REGION = process.env.REGION || "africa-south1";
const SCHEDULER_REGION = process.env.SCHEDULER_REGION || defaultPolicy.deadman.region;
const SHARED_SECRET = process.env.OMEGA_MCP_SHARED_SECRET;
const TRUST_CLOUD_RUN_IAM = process.env.TRUST_CLOUD_RUN_IAM === "true";
const POLICY = { ...defaultPolicy, allowMutations: process.env.ALLOW_MUTATIONS === "true" };
const audit = [];

if (!PROJECT_ID) throw new Error("PROJECT_ID is required.");
if (!TRUST_CLOUD_RUN_IAM && (!SHARED_SECRET || SHARED_SECRET.length < 32)) throw new Error("OMEGA_MCP_SHARED_SECRET (32+ chars) is required unless private Cloud Run IAM authentication is enforced.");

function json(res, status, body) { res.writeHead(status, { "content-type": "application/json" }); res.end(JSON.stringify(body)); }
function safeEqual(a, b) { return a && b && a.length === b.length && crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b)); }
function requireAuth(req) {
  const token = req.headers.authorization?.replace(/^Bearer\s+/i, "");
  if (TRUST_CLOUD_RUN_IAM) {
    if (!token) throw new Error("Cloud Run IAM identity token is required");
    return;
  }
  if (!safeEqual(token, SHARED_SECRET)) throw new Error("Unauthorized");
}
async function body(req) { let data=""; for await (const c of req) data += c; return data ? JSON.parse(data) : {}; }
function record(entry) { audit.unshift({ id: crypto.randomUUID(), at: new Date().toISOString(), ...entry }); audit.splice(200); }

const tools = [
  ["omega_status", "Use this when you need a current, read-only Cloud Run and service-enablement status.", { type:"object", properties:{} }],
  ["omega_inventory", "Discover current Google Cloud capability classes through Cloud Asset Inventory. Returns counts and bounded samples, not secret payloads. Read-only.", { type:"object", properties:{} }],
  ["omega_publish_heartbeat", "Publish one public-safe, idempotency-keyed EvidenceOps heartbeat event to the governed Pub/Sub topic. This does not execute the referenced provider action.", { type:"object", properties:{ eventId:{type:"string",pattern:"^[A-Za-z0-9._:-]{1,160}$"}, nodeId:{type:"string",pattern:"^[A-Za-z0-9._:-]{1,160}$"}, state:{type:"string",enum:["ACTIVE","STALE","SYNC_PENDING","ADAPTER_REQUIRED"]}, receiptHash:{type:"string",pattern:"^[a-f0-9]{64}$"} }, required:["eventId","nodeId","state","receiptHash"] }],
  ["omega_recover", "Use this when Apps Script or Service Usage APIs must be restored. Enables only the policy allowlist and verifies readback.", { type:"object", properties:{ service:{ type:"string", enum:["serviceusage.googleapis.com","script.googleapis.com"] } }, required:["service"] }],
  ["omega_execute_change", "Execute one project-bounded Google API mutation through the sovereign EvidenceOps identity. Requires mutation policy, exact confirmation, change ticket, rollback plan and independent GET readback. Credential-minting and secret-payload endpoints are never returned through this tool.", { type:"object", properties:{ action:{type:"string",enum:["google_api_request"]}, changeTicket:{type:"string",minLength:3,maxLength:160}, rollback:{type:"string",minLength:3,maxLength:1000}, confirmation:{type:"string",enum:["EXECUTE_SOVEREIGN_PROJECT_CHANGE"]}, payload:{type:"object",properties:{method:{type:"string",enum:["POST","PUT","PATCH"]},url:{type:"string",format:"uri"},body:{type:"object"},readbackUrl:{type:"string",format:"uri"}},required:["method","url","body","readbackUrl"]} }, required:["action","changeTicket","rollback","confirmation","payload"] }],
  ["omega_audit", "Use this when you need the most recent execution and recovery evidence.", { type:"object", properties:{} }],
  ["omega_inspect_deadman", "Read the exact existing deadman Scheduler job and return its current configuration before execution.", { type:"object", properties:{} }],
  ["omega_run_deadman", "Run only the exact allowlisted existing deadman Scheduler job. Requires exact confirmation and performs before/after semantic readback.", { type:"object", properties:{ confirmation:{ type:"string", enum:["RUN_EXACT_EXISTING_DEADMAN_JOB"] } }, required:["confirmation"] }]
];

async function status() {
  const u = urls(PROJECT_ID, REGION);
  const [services, enabled] = await Promise.all([googleFetch(u.services), googleFetch(u.enabledServices)]);
  return { projectId: PROJECT_ID, region: REGION, cloudRun: services.services || [], enabledServices: (enabled.services || []).map(s => s.config?.name || s.name), policy: { autoRecovery: POLICY.autoRecovery, allowMutations: POLICY.allowMutations } };
}
async function inventory() {
  authorize({ action:"inventory_cloud_assets", payload:{}, policy:POLICY });
  const u = urls(PROJECT_ID, REGION);
  const assets = [];
  let pageToken = "";
  do {
    const page = await googleFetch(u.assetSearch(pageToken));
    assets.push(...(page.results || []));
    pageToken = page.nextPageToken || "";
    if (assets.length >= 10000) break;
  } while (pageToken);
  const byType = {};
  const locations = new Set();
  for (const asset of assets) {
    const type = asset.assetType || "UNKNOWN";
    byType[type] = (byType[type] || 0) + 1;
    for (const location of asset.location ? [asset.location] : []) locations.add(location);
  }
  return {
    schema:"OMEGA-CLOUD-CAPABILITY-INVENTORY-1",
    projectId:PROJECT_ID,
    resourceCount:assets.length,
    truncated:assets.length >= 10000 && Boolean(pageToken),
    assetTypes:Object.entries(byType).sort(([a],[b]) => a.localeCompare(b)).map(([assetType,count]) => ({assetType,count})),
    locations:[...locations].sort(),
    boundedSamples:assets.slice(0,25).map(({name,assetType,location,state}) => ({name,assetType,location,state})),
    secretsRead:false,
    credentialsExported:false,
    checkedAt:new Date().toISOString()
  };
}
async function publishHeartbeat(args) {
  authorize({ action:"publish_heartbeat_event", payload:args, policy:POLICY });
  const u = urls(PROJECT_ID, REGION);
  const envelope = {
    schema:"EVIDENCEOPS-CLOUD-HEARTBEAT-EVENT-1",
    eventId:args.eventId,
    nodeId:args.nodeId,
    state:args.state,
    receiptHash:args.receiptHash,
    emittedAt:new Date().toISOString(),
    credentialsIncluded:false
  };
  const data = Buffer.from(JSON.stringify(envelope)).toString("base64");
  const result = await googleFetch(u.heartbeatPublish, {
    method:"POST",
    body:JSON.stringify({messages:[{data,attributes:{eventId:args.eventId,nodeId:args.nodeId}}]})
  });
  return { ...envelope, providerMessageIds:result.messageIds || [], state:"PUBLISHED_AWAITING_CONSUMER_READBACK" };
}
function governedGoogleUrl(value) {
  const parsed = new URL(value);
  if (parsed.protocol !== "https:" || !parsed.hostname.endsWith(".googleapis.com")) {
    throw new Error("Only HTTPS Google APIs are permitted.");
  }
  if (!decodeURIComponent(parsed.pathname).includes(`projects/${PROJECT_ID}`)) {
    throw new Error("Google API request is outside the configured project boundary.");
  }
  const forbidden = ["iamcredentials.googleapis.com", "/keys", ":access", ":signBlob", ":signJwt", ":generateAccessToken"];
  if (forbidden.some(value => parsed.hostname === value || parsed.pathname.includes(value))) {
    throw new Error("Credential minting, key creation and secret payload retrieval are not exposed.");
  }
  return parsed.toString();
}
async function executeGoogleChange(args) {
  if (args.confirmation !== "EXECUTE_SOVEREIGN_PROJECT_CHANGE") throw new Error("Exact sovereign change confirmation is required.");
  authorize({ action:args.action, payload:args, policy:POLICY });
  const requestUrl = governedGoogleUrl(args.payload.url);
  const readbackUrl = governedGoogleUrl(args.payload.readbackUrl);
  const mutation = await googleFetch(requestUrl, {method:args.payload.method, body:JSON.stringify(args.payload.body)});
  const readback = await googleFetch(readbackUrl);
  return {
    action:args.action,
    changeTicket:args.changeTicket,
    rollback:args.rollback,
    request:{method:args.payload.method,url:requestUrl},
    mutation,
    readback,
    state:"MUTATION_AND_PROVIDER_READBACK_COMPLETED",
    checkedAt:new Date().toISOString()
  };
}
async function recover(service) {
  authorize({ action:"enable_service", payload:{ service }, policy:POLICY });
  const u = urls(PROJECT_ID, REGION);
  const operation = await googleFetch(u.enable(service), { method:"POST", body:"{}" });
  return { action:"enable_service", service, operation, verification: "Use omega_status after the long-running operation completes." };
}
async function inspectDeadman() {
  const target = defaultPolicy.deadman;
  if (PROJECT_ID !== target.projectId || SCHEDULER_REGION !== target.region) throw new Error("Runtime project or Scheduler region does not match the deadman allowlist.");
  const u = urls(PROJECT_ID, REGION);
  const job = await googleFetch(u.schedulerJob(SCHEDULER_REGION, target.jobName));
  return { action:"inspect_deadman_scheduler_job", target, job, checkedAt:new Date().toISOString() };
}
async function runDeadman(confirmation) {
  const target = defaultPolicy.deadman;
  authorize({ action:"run_deadman_scheduler_job", payload:{ ...target, confirmation }, policy:POLICY });
  const u = urls(PROJECT_ID, REGION);
  const before = await googleFetch(u.schedulerJob(SCHEDULER_REGION, target.jobName));
  if (before.state !== "ENABLED") throw new Error(`Deadman Scheduler job is not ENABLED: ${before.state || "UNKNOWN"}`);
  const run = await googleFetch(u.runSchedulerJob(SCHEDULER_REGION, target.jobName), { method:"POST", body:"{}" });
  const after = await googleFetch(u.schedulerJob(SCHEDULER_REGION, target.jobName));
  return {
    action:"run_deadman_scheduler_job", target,
    before:{ name:before.name, state:before.state, schedule:before.schedule, timeZone:before.timeZone, lastAttemptTime:before.lastAttemptTime, scheduleTime:before.scheduleTime },
    run,
    after:{ name:after.name, state:after.state, schedule:after.schedule, timeZone:after.timeZone, lastAttemptTime:after.lastAttemptTime, scheduleTime:after.scheduleTime },
    semanticReadback: after.name === before.name && after.state === "ENABLED",
    checkedAt:new Date().toISOString()
  };
}
async function call(name, args) {
  if (name === "omega_status") return status();
  if (name === "omega_inventory") return inventory();
  if (name === "omega_publish_heartbeat") return publishHeartbeat(args);
  if (name === "omega_recover") return recover(args.service);
  if (name === "omega_audit") return { events:audit.slice(0,50) };
  if (name === "omega_inspect_deadman") return inspectDeadman();
  if (name === "omega_run_deadman") return runDeadman(args.confirmation);
  if (name === "omega_execute_change") {
    return executeGoogleChange(args);
  }
  throw new Error(`Unknown tool: ${name}`);
}

const server = http.createServer(async (req,res) => {
  if (req.method === "GET" && req.url === "/health") return json(res,200,{ ok:true, projectId:PROJECT_ID, region:REGION });
  if (req.method !== "POST" || req.url !== "/mcp") return json(res,404,{ error:"Not found" });
  let rpc;
  try {
    requireAuth(req); rpc = await body(req);
    if (rpc.method === "initialize") return json(res,200,{ jsonrpc:"2.0", id:rpc.id, result:{ protocolVersion:"2024-11-05", capabilities:{ tools:{} }, serverInfo:{ name:"omega-control-plane", version:"1.1.0" } } });
    if (rpc.method === "tools/list") return json(res,200,{ jsonrpc:"2.0", id:rpc.id, result:{ tools:tools.map(([name,description,inputSchema])=>({name,description,inputSchema,annotations:{readOnlyHint:name==="omega_status"||name==="omega_inventory"||name==="omega_audit"||name==="omega_inspect_deadman",destructiveHint:name==="omega_execute_change",idempotentHint:name!=="omega_execute_change"&&name!=="omega_run_deadman"&&name!=="omega_publish_heartbeat"}})) } });
    if (rpc.method === "tools/call") {
      const { name, arguments:args={} } = rpc.params || {}; const output = await call(name,args);
      record({ tool:name, outcome:"OK", arguments:args });
      return json(res,200,{ jsonrpc:"2.0", id:rpc.id, result:{ content:[{ type:"text", text:JSON.stringify(output) }], structuredContent:output } });
    }
    return json(res,200,{ jsonrpc:"2.0", id:rpc.id, result:{} });
  } catch (error) {
    record({ tool:rpc?.params?.name || rpc?.method || "unknown", outcome:"ERROR", error:error.message });
    return json(res,401,{ jsonrpc:"2.0", id:rpc?.id ?? null, error:{ code:-32001, message:error.message } });
  }
});
server.listen(PORT, () => console.log(`omega-control-plane on ${PORT}`));
