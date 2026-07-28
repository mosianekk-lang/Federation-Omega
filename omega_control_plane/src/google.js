const SCOPES = "https://www.googleapis.com/auth/cloud-platform";

async function metadataToken() {
  const res = await fetch("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", {
    headers: { "Metadata-Flavor": "Google" }
  });
  if (!res.ok) throw new Error(`Unable to obtain Cloud Run identity: ${res.status}`);
  return (await res.json()).access_token;
}

export async function googleFetch(url, options = {}) {
  const token = await metadataToken();
  const res = await fetch(url, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });
  const text = await res.text();
  let body;
  try { body = text ? JSON.parse(text) : {}; } catch { body = { raw: text }; }
  if (!res.ok) throw new Error(JSON.stringify({ status: res.status, body }));
  return body;
}

export function urls(projectId, region) {
  return {
    services: `https://run.googleapis.com/v2/projects/${projectId}/locations/${region}/services`,
    enabledServices: `https://serviceusage.googleapis.com/v1/projects/${projectId}/services?filter=state:ENABLED`,
    service: (name) => `https://serviceusage.googleapis.com/v1/projects/${projectId}/services/${name}`,
    enable: (name) => `https://serviceusage.googleapis.com/v1/projects/${projectId}/services/${name}:enable`,
    operations: `https://serviceusage.googleapis.com/v1/operations`,
    schedulerJob: (schedulerRegion, jobName) => `https://cloudscheduler.googleapis.com/v1/projects/${projectId}/locations/${schedulerRegion}/jobs/${jobName}`,
    runSchedulerJob: (schedulerRegion, jobName) => `https://cloudscheduler.googleapis.com/v1/projects/${projectId}/locations/${schedulerRegion}/jobs/${jobName}:run`
  };
}

export { SCOPES };
