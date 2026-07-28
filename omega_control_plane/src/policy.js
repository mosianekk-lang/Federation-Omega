const READ_ACTIONS = new Set([
  "runtime_status", "list_services", "list_enabled_services", "list_operations",
  "get_service", "get_audit_summary", "inspect_deadman_scheduler_job"
]);

const RECOVERY_ACTIONS = new Set([
  "enable_service", "repair_apps_script_api", "verify_control_plane", "run_deadman_scheduler_job"
]);

const MUTATION_ACTIONS = new Set([
  "deploy_revision", "update_service_env", "set_iam_binding", "delete_resource"
]);

export function actionClass(action) {
  if (READ_ACTIONS.has(action)) return "read";
  if (RECOVERY_ACTIONS.has(action)) return "recovery";
  if (MUTATION_ACTIONS.has(action)) return "mutation";
  throw new Error(`Unsupported action: ${action}`);
}

export function authorize({ action, payload, policy }) {
  const kind = actionClass(action);
  if (kind === "read") return { kind, approval: "not-required" };
  if (kind === "recovery") {
    if (!policy.autoRecovery) throw new Error("Automatic recovery is disabled by policy.");
    if (action === "enable_service" && !policy.allowedServices.includes(payload.service)) {
      throw new Error("Service is not allowlisted for automatic enablement.");
    }
    if (action === "run_deadman_scheduler_job") {
      if (payload.projectId !== policy.deadman.projectId || payload.region !== policy.deadman.region || payload.jobName !== policy.deadman.jobName) {
        throw new Error("Scheduler target is not the exact allowlisted deadman job.");
      }
      if (payload.confirmation !== policy.deadman.confirmation) {
        throw new Error("Exact deadman execution confirmation is required.");
      }
    }
    return { kind, approval: "policy-approved" };
  }
  if (!payload.changeTicket || !payload.rollback) {
    throw new Error("Mutations require changeTicket and rollback details.");
  }
  if (!policy.allowMutations) throw new Error("Mutations are disabled by policy.");
  return { kind, approval: "change-approved" };
}

export const defaultPolicy = Object.freeze({
  autoRecovery: true,
  allowMutations: false,
  allowedServices: ["serviceusage.googleapis.com", "script.googleapis.com", "cloudscheduler.googleapis.com"],
  deadman: Object.freeze({
    projectId: "sov-hybrid-suite",
    region: "europe-west1",
    jobName: "fo-apps-script-queue-deadman",
    confirmation: "RUN_EXACT_EXISTING_DEADMAN_JOB"
  }),
  maxActionsPerRequest: 8
});
