export const TOOL_NAMES = {
  projectInfo: "gcp_project_info",
  serviceStatus: "gcp_service_status",
  enableService: "gcp_enable_service",
  scriptMetadata: "apps_script_metadata",
  scriptContent: "apps_script_get_content",
  scriptBackup: "apps_script_backup",
  scriptDryRun: "apps_script_dry_run",
  scriptApply: "apps_script_apply",
  scriptRollback: "apps_script_rollback",
  cloudRunService: "gcp_cloud_run_service",
  cloudRunRevision: "gcp_cloud_run_revision",
  artifactDockerImage: "gcp_artifact_docker_image",
  cloudBuildInfo: "gcp_cloud_build_info",
  cloudBuildList: "gcp_cloud_build_list",
  deploymentAudit: "gcp_cloud_run_deployment_audit",
  serviceIam: "gcp_cloud_run_service_iam",
  lineageAttest: "gcp_deployment_lineage_attest"
} as const;

export const SERVER_VERSION = "0.2.2";

export function healthPayload(now = new Date()): Record<string, unknown> {
  return {
    ok: true,
    service: "federation-omega-gcp-admin-mcp",
    version: SERVER_VERSION,
    timestamp: now.toISOString(),
    proofBoundary: "transport_liveness_only"
  };
}
