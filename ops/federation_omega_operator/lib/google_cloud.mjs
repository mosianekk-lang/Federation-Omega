import { sha256Hex } from "./contracts.mjs";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class GoogleCloudAdapter {
  constructor(env = process.env, fetchImpl = fetch) {
    this.env = env;
    this.fetch = fetchImpl;
    this.accessToken = null;
    this.accessTokenExpiresAt = 0;
  }

  async token() {
    if (this.accessToken && this.accessTokenExpiresAt > Date.now() + 60000) return this.accessToken;
    const response = await this.fetch("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token", { headers: { "Metadata-Flavor": "Google" } });
    if (!response.ok) throw new Error(`metadata token failed: ${response.status}`);
    const body = await response.json();
    this.accessToken = body.access_token;
    this.accessTokenExpiresAt = Date.now() + Number(body.expires_in || 300) * 1000;
    return this.accessToken;
  }

  async api(url, options = {}, expected = [200]) {
    const token = await this.token();
    const response = await this.fetch(url, { ...options, headers: { accept: "application/json", authorization: `Bearer ${token}`, ...(options.headers || {}) } });
    const text = await response.text();
    let body; try { body = text ? JSON.parse(text) : {}; } catch { body = { text: text.slice(0, 2000) }; }
    if (!expected.includes(response.status)) throw new Error(`provider ${response.status}: ${JSON.stringify(body).slice(0, 2000)}`);
    return { status: response.status, body };
  }

  async readService({ project, region, service }) {
    return (await this.api(`https://run.googleapis.com/v2/projects/${encodeURIComponent(project)}/locations/${encodeURIComponent(region)}/services/${encodeURIComponent(service)}`)).body;
  }

  async identityToken(audience) {
    const url = `http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience=${encodeURIComponent(audience)}&format=full`;
    const response = await this.fetch(url, { headers: { "Metadata-Flavor": "Google" } });
    if (!response.ok) throw new Error(`metadata identity token failed: ${response.status}`);
    return response.text();
  }

  async verifyServiceHealth(target) {
    const service = await this.readService(target);
    const audience = service.uri;
    const identity = await this.identityToken(audience);
    const response = await this.fetch(`${audience.replace(/\/$/, "")}/health`, { headers: { accept: "application/json", authorization: `Bearer ${identity}` } });
    const body = await response.json();
    return { ok: response.ok && body.ok === true, status: response.ok && body.ok === true ? "TARGET_HEALTH_VERIFIED" : "TARGET_HEALTH_FAILED", service: target.service, latestReadyRevision: service.latestReadyRevision || null, uri: service.uri, health: body };
  }

  async readBuild(payload = {}) {
    const project = payload.project || this.env.PROJECT_ID;
    const region = payload.region || this.env.REGION;
    if (!payload.buildId) throw new Error("buildId is required");
    return (await this.api(`https://cloudbuild.googleapis.com/v1/projects/${encodeURIComponent(project)}/locations/${encodeURIComponent(region)}/builds/${encodeURIComponent(payload.buildId)}`)).body;
  }

  vertexBase(location) {
    return location === "global"
      ? "https://aiplatform.googleapis.com"
      : `https://${encodeURIComponent(location)}-aiplatform.googleapis.com`;
  }

  vertexModelUrl({ project, location, model }, suffix = "") {
    return `${this.vertexBase(location)}/v1/projects/${encodeURIComponent(project)}/locations/${encodeURIComponent(location)}/publishers/google/models/${encodeURIComponent(model)}${suffix}`;
  }

  async readGeminiVertexCapability(target) {
    const service = await this.api(
      `https://serviceusage.googleapis.com/v1/projects/${encodeURIComponent(target.project)}/services/aiplatform.googleapis.com`,
    );
    if (service.body.state !== "ENABLED") {
      return {
        ok: false,
        status: "VERTEX_AI_API_DISABLED",
        provider: "vertex",
        authMode: "CLOUD_RUN_SERVICE_IDENTITY",
        target,
        serviceState: service.body.state || "UNKNOWN",
        semanticExecutionAttempted: false,
        incrementalCost: 0,
        silentFallback: false,
      };
    }
    const publisherModel = await this.api(this.vertexModelUrl(target));
    return {
      ok: true,
      status: "GEMINI_VERTEX_CAPABILITY_READ",
      provider: "vertex",
      authMode: "CLOUD_RUN_SERVICE_IDENTITY",
      target,
      serviceState: service.body.state,
      modelReadback: {
        name: publisherModel.body.name || null,
        versionId: publisherModel.body.versionId || null,
        displayName: publisherModel.body.displayName || null,
        launchStage: publisherModel.body.launchStage || null,
        supportedActions: publisherModel.body.supportedActions || null,
      },
      semanticExecutionAttempted: false,
      incrementalCost: 0,
      silentFallback: false,
    };
  }

  async verifyGeminiVertexSemantic(canary) {
    const capability = await this.readGeminiVertexCapability(canary);
    if (!capability.ok) throw new Error(`Gemini Vertex capability unavailable: ${capability.status}`);
    const request = {
      contents: [{ role: "user", parts: [{ text: `Return exactly this nonce and nothing else: ${canary.nonce}` }] }],
      generationConfig: {
        candidateCount: 1,
        temperature: 0,
        maxOutputTokens: canary.maxOutputTokens,
      },
    };
    const response = await this.api(
      this.vertexModelUrl(canary, ":generateContent"),
      { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request) },
    );
    const observed = (response.body.candidates?.[0]?.content?.parts || [])
      .map((part) => typeof part.text === "string" ? part.text : "")
      .join("")
      .trim();
    if (observed !== canary.nonce) {
      throw new Error("Gemini Vertex semantic nonce mismatch");
    }
    const usage = response.body.usageMetadata || {};
    return {
      ok: true,
      status: "GEMINI_VERTEX_SEMANTIC_VERIFIED",
      provider: "vertex",
      authMode: "CLOUD_RUN_SERVICE_IDENTITY",
      target: {
        project: canary.project,
        location: canary.location,
        model: canary.model,
        tenantId: canary.tenantId,
      },
      nonceVerified: true,
      idempotencyKey: canary.idempotencyKey,
      usage: {
        promptTokenCount: Number(usage.promptTokenCount || 0),
        candidatesTokenCount: Number(usage.candidatesTokenCount || 0),
        totalTokenCount: Number(usage.totalTokenCount || 0),
      },
      silentFallback: false,
    };
  }

  async downloadDriveFile(fileId) {
    const token = await this.token();
    const response = await this.fetch(`https://www.googleapis.com/drive/v3/files/${encodeURIComponent(fileId)}?alt=media&supportsAllDrives=true`, { headers: { authorization: `Bearer ${token}` } });
    if (!response.ok) throw new Error(`Drive artifact read failed: ${response.status}`);
    return Buffer.from(await response.arrayBuffer());
  }

  async stageSource(binding, bytes) {
    const bucket = this.env.CFRE_SOURCE_BUCKET || `fo-control-plane-${binding.project}`;
    const object = `cfre-private-runtime/source-${binding.sourceSha256}.tar.gz`;
    const metadataUrl = `https://storage.googleapis.com/storage/v1/b/${encodeURIComponent(bucket)}/o/${encodeURIComponent(object)}`;
    try {
      const existing = await this.api(metadataUrl, {}, [200, 404]);
      if (existing.status === 200) {
        if (existing.body.metadata?.sha256 !== binding.sourceSha256) throw new Error("immutable source object collision");
        return { bucket, object, generation: existing.body.generation, reused: true };
      }
    } catch (error) {
      if (!String(error.message).includes("404")) throw error;
    }
    const boundary = `fo-cfre-${binding.sourceSha256.slice(0, 16)}`;
    const metadata = JSON.stringify({ name: object, contentType: "application/gzip", metadata: { sha256: binding.sourceSha256, embeddedRepairSha256: binding.embeddedRepairSha256, manifestSha256: binding.manifestSha256 } });
    const multipart = Buffer.concat([
      Buffer.from(`--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${metadata}\r\n--${boundary}\r\nContent-Type: application/gzip\r\n\r\n`),
      bytes,
      Buffer.from(`\r\n--${boundary}--`),
    ]);
    const uploaded = await this.api(`https://storage.googleapis.com/upload/storage/v1/b/${encodeURIComponent(bucket)}/o?uploadType=multipart&ifGenerationMatch=0`, { method: "POST", headers: { "content-type": `multipart/related; boundary=${boundary}` }, body: multipart }, [200]);
    return { bucket, object, generation: uploaded.body.generation, reused: false };
  }

  async submitBuild(binding, staged) {
    const repository = this.env.CFRE_ARTIFACT_REPOSITORY || "fo-runtime";
    const image = `${binding.region}-docker.pkg.dev/${binding.project}/${repository}/${binding.service}:cfre-${binding.sourceSha256.slice(0, 24)}`;
    const request = {
      source: { storageSource: { bucket: staged.bucket, object: staged.object, generation: staged.generation } },
      steps: [
        { name: "gcr.io/cloud-builders/docker", args: ["build", "--pull", "-t", image, "."] },
        { name: "gcr.io/cloud-builders/docker", args: ["push", image] },
      ],
      images: [image],
      timeout: "1200s",
      options: { logging: "CLOUD_LOGGING_ONLY", machineType: "E2_HIGHCPU_8" },
      tags: ["cfre-omega", binding.sourceSha256.slice(0, 16)],
    };
    const submitted = await this.api(`https://cloudbuild.googleapis.com/v1/projects/${binding.project}/locations/${binding.region}/builds`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(request) }, [200]);
    const buildId = submitted.body.metadata?.build?.id || submitted.body.name?.split("/").at(-1);
    if (!buildId) throw new Error("Cloud Build id missing from submission");
    return { buildId, image };
  }

  async waitBuild(project, region, buildId, timeoutMs = 1200000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const build = await this.readBuild({ project, region, buildId });
      if (["SUCCESS", "FAILURE", "INTERNAL_ERROR", "TIMEOUT", "CANCELLED", "EXPIRED"].includes(build.status)) {
        if (build.status !== "SUCCESS") throw new Error(`Cloud Build terminal status ${build.status}`);
        return build;
      }
      await sleep(5000);
    }
    throw new Error("Cloud Build polling timeout");
  }

  async waitOperation(name, timeoutMs = 600000) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const operation = (await this.api(`https://run.googleapis.com/v2/${name}`)).body;
      if (operation.done) {
        if (operation.error) throw new Error(`Cloud Run operation failed: ${JSON.stringify(operation.error)}`);
        return operation.response || operation;
      }
      await sleep(3000);
    }
    throw new Error("Cloud Run operation polling timeout");
  }

  async deployPrivateService(binding, image) {
    let before = null;
    try { before = await this.readService(binding); } catch (error) { if (!String(error.message).includes("404")) throw error; }
    const body = {
      labels: { "fo-system": "cfre-omega", "fo-binding": binding.embeddedRepairSha256.slice(0, 16) },
      ingress: "INGRESS_TRAFFIC_ALL",
      template: {
        serviceAccount: binding.serviceAccount,
        maxInstanceRequestConcurrency: 8,
        timeout: "300s",
        scaling: { minInstanceCount: 0, maxInstanceCount: 1 },
        containers: [{ image, env: [
          { name: "CFRE_REPAIR_SHA256", value: binding.embeddedRepairSha256 },
          { name: "CFRE_MANIFEST_SHA256", value: binding.manifestSha256 },
        ], resources: { limits: { cpu: "1", memory: "512Mi" }, cpuIdle: true } }],
      },
    };
    const base = `https://run.googleapis.com/v2/projects/${binding.project}/locations/${binding.region}/services`;
    const result = before
      ? await this.api(`${base}/${binding.service}?updateMask=labels,ingress,template`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ ...body, name: before.name }) }, [200])
      : await this.api(`${base}?serviceId=${encodeURIComponent(binding.service)}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) }, [200]);
    const response = await this.waitOperation(result.body.name);
    const after = await this.readService(binding);
    const actualImage = after.template?.containers?.[0]?.image;
    if (!after.latestReadyRevision || actualImage !== image) throw new Error("Cloud Run semantic readback mismatch");
    return { before: before ? { latestReadyRevision: before.latestReadyRevision || null, image: before.template?.containers?.[0]?.image || null } : null, after: { name: after.name, uri: after.uri, latestReadyRevision: after.latestReadyRevision, image: actualImage, serviceAccount: after.template?.serviceAccount }, operation: response };
  }

  async bindCfrePrivateRuntime(binding) {
    const bytes = await this.downloadDriveFile(binding.sourceDriveId);
    const observedSha256 = sha256Hex(bytes);
    if (observedSha256 !== binding.sourceSha256) throw new Error(`source hash mismatch: ${observedSha256}`);
    const staged = await this.stageSource(binding, bytes);
    const submitted = await this.submitBuild(binding, staged);
    const build = await this.waitBuild(binding.project, binding.region, submitted.buildId);
    const service = await this.deployPrivateService(binding, submitted.image);
    return {
      ok: true,
      status: "CFRE_PRIVATE_RUNTIME_BOUND",
      identity: "CFRE-OMEGA",
      sourceSha256: observedSha256,
      embeddedRepairSha256: binding.embeddedRepairSha256,
      manifestSha256: binding.manifestSha256,
      build: { id: build.id, status: build.status, image: submitted.image },
      service,
      idempotencyKey: binding.idempotencyKey,
      rollback: service.before,
    };
  }
}
