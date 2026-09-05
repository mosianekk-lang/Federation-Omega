import express from "express";
import {McpServer} from "@modelcontextprotocol/sdk/server/mcp.js";
import {StreamableHTTPServerTransport} from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import {z} from "zod";
import {config} from "./config.js";
import {audit} from "./audit.js";
import {healthPayload, SERVER_VERSION, TOOL_NAMES} from "./toolNames.js";
import {
  projectInfo, serviceStatus, enableService, scriptMetadata, scriptContent,
  scriptBackup, scriptDryRun, scriptApply, scriptRollback
} from "./operations.js";
import {
  artifactDockerImage, cloudBuildInfo, cloudBuildList, cloudRunRevision,
  cloudRunService, cloudRunServiceIamPolicy, deploymentAuditEvents,
  deploymentLineageAttest
} from "./lineage.js";

const server = new McpServer({
  name: "Federation Omega GCP Admin",
  version: SERVER_VERSION,
});

function response(record: unknown) {
  return {
    content: [{type: "text" as const, text: JSON.stringify(record, null, 2)}],
    structuredContent: record as Record<string, unknown>,
  };
}

server.registerTool(TOOL_NAMES.projectInfo, {
  title: "GCP Project Info",
  description: "Use this when you need verified metadata for an allowlisted Google Cloud project.",
  inputSchema: {project: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, openWorldHint: true},
}, async input => response(await audit("gcp_project_info", input, () => projectInfo(input.project))));

server.registerTool(TOOL_NAMES.serviceStatus, {
  title: "GCP Service Status",
  description: "Use this when you need to verify whether an allowlisted Google API is enabled.",
  inputSchema: {project: z.string(), service: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, openWorldHint: true},
}, async input => response(await audit("gcp_service_status", input, () =>
  serviceStatus(input.project, input.service))));

server.registerTool(TOOL_NAMES.enableService, {
  title: "Enable Google API",
  description: "Use this when the owner has explicitly approved enabling one allowlisted Google API in one allowlisted project.",
  inputSchema: {project: z.string(), service: z.string(), approvalToken: z.string()},
  annotations: {readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit("gcp_enable_service",
  {...input, approvalToken: "[REDACTED]"},
  () => enableService(input.project, input.service, input.approvalToken))));

server.registerTool(TOOL_NAMES.scriptMetadata, {
  title: "Apps Script Metadata",
  description: "Use this when you need verified metadata for an allowlisted Apps Script project.",
  inputSchema: {scriptId: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, openWorldHint: true},
}, async input => response(await audit("apps_script_metadata", input,
  () => scriptMetadata(input.scriptId))));

server.registerTool(TOOL_NAMES.scriptContent, {
  title: "Read Apps Script Source",
  description: "Use this when you need the complete current source of an allowlisted Apps Script project.",
  inputSchema: {scriptId: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, openWorldHint: true},
}, async input => response(await audit("apps_script_get_content", input,
  () => scriptContent(input.scriptId))));

server.registerTool(TOOL_NAMES.scriptBackup, {
  title: "Back Up Apps Script",
  description: "Use this before any source mutation to capture source, hash, and timestamp.",
  inputSchema: {scriptId: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, openWorldHint: true},
}, async input => response(await audit("apps_script_backup", input,
  () => scriptBackup(input.scriptId))));

server.registerTool(TOOL_NAMES.scriptDryRun, {
  title: "Dry Run Apps Script Update",
  description: "Use this to compare current source with proposed full project content without changing anything.",
  inputSchema: {scriptId: z.string(), proposedContent: z.object({files: z.array(z.any())})},
  annotations: {readOnlyHint: true, destructiveHint: false, openWorldHint: true},
}, async input => response(await audit("apps_script_dry_run", input,
  () => scriptDryRun(input.scriptId, input.proposedContent))));

server.registerTool(TOOL_NAMES.scriptApply, {
  title: "Apply Apps Script Update",
  description: "Use this only after backup and dry-run proof. Requires current source hash and explicit approval token.",
  inputSchema: {
    scriptId: z.string(),
    expectedCurrentSha256: z.string(),
    proposedContent: z.object({files: z.array(z.any())}),
    approvalToken: z.string(),
  },
  annotations: {readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true},
}, async input => response(await audit("apps_script_apply",
  {...input, approvalToken: "[REDACTED]"},
  () => scriptApply(input.scriptId, input.expectedCurrentSha256,
    input.proposedContent, input.approvalToken))));

server.registerTool(TOOL_NAMES.scriptRollback, {
  title: "Roll Back Apps Script",
  description: "Restore a complete Apps Script backup with post-write proof. Current-state and backup-source hashes enable the strongest optimistic lock; legacy callers remain compatible and are explicitly reported as compatibilityMode.",
  inputSchema: {
    scriptId: z.string(),
    expectedCurrentSha256: z.string().optional(),
    backupContent: z.object({files: z.array(z.any())}),
    expectedBackupSha256: z.string().optional(),
    approvalToken: z.string(),
  },
  annotations: {readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true},
}, async input => response(await audit("apps_script_rollback",
  {...input, approvalToken: "[REDACTED]"},
  () => scriptRollback(input.scriptId, input.expectedCurrentSha256,
    input.backupContent, input.expectedBackupSha256, input.approvalToken))));

server.registerTool(TOOL_NAMES.cloudRunService, {
  title: "Read Cloud Run Service",
  description: "Read exact Cloud Run v2 service state, including current revisions, traffic, runtime template and reconciliation state. HTTP health is never treated as this proof.",
  inputSchema: {project: z.string(), region: z.string(), service: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit(TOOL_NAMES.cloudRunService, input,
  () => cloudRunService(input.project, input.region, input.service))));

server.registerTool(TOOL_NAMES.cloudRunRevision, {
  title: "Read Cloud Run Revision",
  description: "Read one exact Cloud Run v2 revision and its immutable container image and runtime service account.",
  inputSchema: {project: z.string(), region: z.string(), service: z.string(), revision: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit(TOOL_NAMES.cloudRunRevision, input,
  () => cloudRunRevision(input.project, input.region, input.service, input.revision))));

server.registerTool(TOOL_NAMES.artifactDockerImage, {
  title: "Read Artifact Registry Docker Image",
  description: "Read one allowlisted Docker image by immutable sha256 digest. Mutable tags are rejected.",
  inputSchema: {
    project: z.string(), location: z.string(), repository: z.string(), dockerImage: z.string()
  },
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit(TOOL_NAMES.artifactDockerImage, input,
  () => artifactDockerImage(input.project, input.location, input.repository, input.dockerImage))));

server.registerTool(TOOL_NAMES.cloudBuildInfo, {
  title: "Read Cloud Build",
  description: "Read one exact regional Cloud Build record, including status, produced image digests, source provenance and build identity.",
  inputSchema: {project: z.string(), region: z.string(), buildId: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit(TOOL_NAMES.cloudBuildInfo, input,
  () => cloudBuildInfo(input.project, input.region, input.buildId))));

server.registerTool(TOOL_NAMES.cloudBuildList, {
  title: "List Recent Cloud Builds",
  description: "List a bounded page of regional Cloud Builds for digest discovery. The response is not itself deployment proof.",
  inputSchema: {
    project: z.string(), region: z.string(), pageSize: z.number().int().min(1).max(100).default(100),
    pageToken: z.string().optional().default("")
  },
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit(TOOL_NAMES.cloudBuildList, input,
  () => cloudBuildList(input.project, input.region, input.pageSize, input.pageToken))));

server.registerTool(TOOL_NAMES.deploymentAudit, {
  title: "Read Cloud Run Deployment Audit",
  description: "Read a bounded, newest-first Cloud Audit Log window for one allowlisted Cloud Run service and expose authenticated deployer evidence.",
  inputSchema: {
    project: z.string(), region: z.string(), service: z.string(),
    startTime: z.string().datetime().optional(),
    pageSize: z.number().int().min(1).max(100).default(50)
  },
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit(TOOL_NAMES.deploymentAudit, input,
  () => deploymentAuditEvents(input.project, input.region, input.service, input.startTime, input.pageSize))));

server.registerTool(TOOL_NAMES.serviceIam, {
  title: "Read Cloud Run Service IAM",
  description: "Read the direct IAM policy currently attached to one allowlisted Cloud Run service. Inherited policy is not inferred.",
  inputSchema: {project: z.string(), region: z.string(), service: z.string()},
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit(TOOL_NAMES.serviceIam, input,
  () => cloudRunServiceIamPolicy(input.project, input.region, input.service))));

server.registerTool(TOOL_NAMES.lineageAttest, {
  title: "Attest Deployment and Rollback Lineage",
  description: "Join project number, Cloud Run traffic/revision/runtime identity, immutable Artifact Registry digest, Cloud Build source provenance, deployer audit identity and IAM. Repeat every read independently and fail closed on missing fields, generic responses or identifier drift. Optionally attest an exact rollback revision too.",
  inputSchema: {
    project: z.string(),
    region: z.string(),
    service: z.string(),
    buildRegion: z.string().optional(),
    buildId: z.string().optional(),
    auditStartTime: z.string().datetime().optional(),
    rollback: z.object({revision: z.string(), buildId: z.string().optional()}).optional()
  },
  annotations: {readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true},
}, async input => response(await audit(TOOL_NAMES.lineageAttest, input,
  () => deploymentLineageAttest(input))));

const app = express();
app.use(express.json({limit: "20mb"}));

app.get("/healthz", (_req, res) => res.json(healthPayload()));

app.all(config.mcpPath, async (req, res) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
  });
  res.on("close", () => transport.close());
  await server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

app.listen(config.port, () => {
  console.log(JSON.stringify({
    event: "SERVER_STARTED",
    port: config.port,
    mcpPath: config.mcpPath,
  }));
});
