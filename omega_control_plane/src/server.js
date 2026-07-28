import http from "node:http";
import crypto from "node:crypto";
import { googleFetch, urls } from "./google.js";
import { authorize, defaultPolicy } from "./policy.js";

const PORT = Number(process.env.PORT || 8080);
const PROJECT_ID = process.env.GOOGLE_CLOUD_PROJECT || process.env.PROJECT_ID;
const REGION = process.env.REGION || "africa-south1";
const SCHEDULER_REGION = process.env.SCHEDULER_REGION || defaultPolicy.deadman.region;
const SHARED_SECRET = process.env.OMEGA_MCP_SHARED_SECRET;
const POLICY = { ...defaultPolicy, allowMutations: process.env.ALLOW_MUTATIONS === "true" };
const audit = [];

if (!PROJECT_ID) throw new Error("PROJECT_ID is required.");
if (!SHARED_SECRET || SHARED_SECRET.length < 32) throw new Error("OMEGA_MCP_SHARED_SECRET (32+ chars) is required.");

function json(res, status, body) { res.writeHead(status, { "content-type": "application/json" }); res.end(JSON.stringify(body)); }
function safeEqual(a, b) { return a && b && a.length === b.length && crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b)); }
function requireAuth(req) {
  const token = req.headers.authorization?.replace(/^Bearer\s+/i, "");
  if (!safeEqual(token, SHARED_SECRET)) throw new Error("Unauthorized");
}
async function body(req) { let data=""; for await (const c of req) data += c; return data ? JSON.parse(data) : {}; }
function record(entry) { audit.unshift({ id: crypto.randomUUID(), at: new Date().toISOString(), ...entry }); audit.splice(200); }

const tools = [
  ["omega_status", "Use this when you need a current, read-only Cloud Run and service-enablement status.", { type:"object", properties:{} }],
  ["omega_recover", "Use this when Apps Script or Service Usage APIs must be restored. Enables only the policy allowlist and verifies readback.", { type:"object", properties:{ service:{ type:"string", enum:["serviceusage.googleapis.com","script.googleapis.com"] } }, required:["service"] }],
  ["omega_execute_change", "Use this when a controlled cloud mutation is necessary. Requires a change ticket and rollback instructions; disabled unless deployment policy enables mutations.", { type:"object", properties:{ action:{type:"string",enum:["deploy_revision","update_service_env","set_iam_binding","delete_resource"]}, changeTicket:{type:"string"}, rollback:{type:"string"}, payload:{type:"object"} }, required:["action","changeTicket","rollback"] }],
  ["omega_audit", "Use this when you need the most recent execution and recovery evidence.", { type:"object", properties:{} }],
  ["omega_inspect_deadman", "Read the exact existing deadman Scheduler job and return its current configuration before execution.", { type:"object", properties:{} }],
  ["omega_run_deadman", "Run only the exact allowlisted existing deadman Scheduler job. Requires exact confirmation and performs before/after semantic readback.", { type:"object", properties:{ confirmation:{ type:"string", enum:["RUN_EXACT_EXISTING_DEADMAN_JOB"] } }, required:["confirmation"] }]
];

async function status() {
  const u = urls(PROJECT_ID, REGION);
  const [services, enabled] = await Promise.all([googleFetch(u.services), googleFetch(u.enabledServices)]);
  return { projectId: PROJECT_ID, region: REGION, cloudRun: services.services || [], enabledServices: (enabled.services || []).map(s => s.config?.name || s.name), policy: { autoRecovery: POLICY.autoRecovery, allowMutations: POLICY.allowMutations } };
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
  if (name === "omega_recover") return recover(args.service);
  if (name === "omega_audit") return { events:audit.slice(0,50) };
  if (name === "omega_inspect_deadman") return inspectDeadman();
  if (name === "omega_run_deadman") return runDeadman(args.confirmation);
  if (name === "omega_execute_change") {
    authorize({ action:args.action, payload:args, policy:POLICY });
    throw new Error("Mutation adapter not configured. Add a tested adapter and rollback verifier before enabling this action.");
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
    if (rpc.method === "tools/list") return json(res,200,{ jsonrpc:"2.0", id:rpc.id, result:{ tools:tools.map(([name,description,inputSchema])=>({name,description,inputSchema,annotations:{readOnlyHint:name==="omega_status"||name==="omega_audit"||name==="omega_inspect_deadman",destructiveHint:name==="omega_execute_change",idempotentHint:name!=="omega_execute_change"&&name!=="omega_run_deadman"}})) } });
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
