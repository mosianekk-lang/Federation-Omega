import {HttpError} from './core.mjs';

function extractText(payload) {
  const text = (payload.candidates || [])
    .flatMap((candidate) => candidate?.content?.parts || [])
    .map((part) => part?.text)
    .filter((part) => typeof part === 'string')
    .join('\n');
  if (!text) throw new HttpError(502, 'EMPTY_MODEL_RESPONSE', 'Gemini returned no textual content', {finishReason: payload.candidates?.[0]?.finishReason});
  return text;
}

async function callJson({fetchImpl, url, headers, body, timeoutMs, externalSignal}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(new Error('provider timeout')), timeoutMs);
  const abort = () => controller.abort(externalSignal?.reason);
  externalSignal?.addEventListener('abort', abort, {once: true});
  try {
    const response = await fetchImpl(url, {method: 'POST', headers, body: JSON.stringify(body), signal: controller.signal});
    const text = await response.text();
    let payload;
    try { payload = text ? JSON.parse(text) : {}; } catch { payload = {unparseable: true}; }
    if (!response.ok) {
      throw new HttpError(response.status >= 500 ? 502 : response.status, 'GEMINI_PROVIDER_ERROR', 'Gemini provider rejected the request', {
        providerStatus: response.status,
        providerCode: payload?.error?.status,
        providerMessage: payload?.error?.message
      });
    }
    return {payload, text: extractText(payload)};
  } catch (error) {
    if (error instanceof HttpError) throw error;
    if (controller.signal.aborted) throw new HttpError(504, 'GEMINI_TIMEOUT', 'Gemini provider request timed out');
    throw new HttpError(502, 'GEMINI_UNAVAILABLE', 'Gemini provider could not be reached');
  } finally {
    clearTimeout(timeout);
    externalSignal?.removeEventListener('abort', abort);
  }
}

export class DeveloperProvider {
  constructor({apiKey, fetchImpl = fetch, timeoutMs}) {
    this.name = 'developer';
    this.apiKey = apiKey;
    this.fetchImpl = fetchImpl;
    this.timeoutMs = timeoutMs;
  }

  validateSource(source) {
    if (source.uri) throw new HttpError(422, 'DEVELOPER_URI_UNSUPPORTED', 'The Developer API route accepts inline audio in this connector; use Vertex for gs:// sources');
  }

  async generate({model, body, signal}) {
    return callJson({
      fetchImpl: this.fetchImpl,
      url: `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:generateContent`,
      headers: {'content-type': 'application/json', 'x-goog-api-key': this.apiKey},
      body,
      timeoutMs: this.timeoutMs,
      externalSignal: signal
    });
  }
}

export class VertexProvider {
  constructor({project, location, fetchImpl = fetch, timeoutMs, accessToken = ''}) {
    this.name = 'vertex';
    this.project = project;
    this.location = location;
    this.fetchImpl = fetchImpl;
    this.timeoutMs = timeoutMs;
    this.staticAccessToken = accessToken;
    this.cachedToken = null;
  }

  validateSource(source) {
    if (source.uri && !source.uri.startsWith('gs://')) throw new HttpError(422, 'UNSUPPORTED_AUDIO_URI', 'Vertex audio URIs must use gs://');
  }

  async token() {
    if (this.staticAccessToken) return this.staticAccessToken;
    if (this.cachedToken && this.cachedToken.expiresAt > Date.now() + 60_000) return this.cachedToken.value;
    try {
      const response = await this.fetchImpl('http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token', {
        headers: {'metadata-flavor': 'Google'}, signal: AbortSignal.timeout(5_000)
      });
      if (!response.ok) throw new Error('metadata token rejected');
      const payload = await response.json();
      if (!payload.access_token) throw new Error('metadata token absent');
      this.cachedToken = {value: payload.access_token, expiresAt: Date.now() + Math.max(0, (payload.expires_in || 300) * 1_000)};
      return this.cachedToken.value;
    } catch {
      throw new HttpError(503, 'VERTEX_IDENTITY_UNAVAILABLE', 'Cloud service identity access token is unavailable');
    }
  }

  async generate({model, body, signal}) {
    const token = await this.token();
    const host = this.location === 'global' ? 'aiplatform.googleapis.com' : `${this.location}-aiplatform.googleapis.com`;
    const resource = `projects/${encodeURIComponent(this.project)}/locations/${encodeURIComponent(this.location)}/publishers/google/models/${encodeURIComponent(model)}`;
    return callJson({
      fetchImpl: this.fetchImpl,
      url: `https://${host}/v1/${resource}:generateContent`,
      headers: {'authorization': `Bearer ${token}`, 'content-type': 'application/json'},
      body,
      timeoutMs: this.timeoutMs,
      externalSignal: signal
    });
  }
}

export function createProvider(config, dependencies = {}) {
  const mode = config.providerMode === 'auto' ? (config.apiKey ? 'developer' : 'vertex') : config.providerMode;
  if (mode === 'developer') {
    if (!config.apiKey) throw new HttpError(503, 'MISSING_CONFIGURATION', 'GEMINI_API_KEY is required for the Developer API route');
    return new DeveloperProvider({apiKey: config.apiKey, fetchImpl: dependencies.fetchImpl, timeoutMs: config.requestTimeoutMs});
  }
  if (!config.project) throw new HttpError(503, 'MISSING_CONFIGURATION', 'GOOGLE_CLOUD_PROJECT is required for the Vertex route');
  return new VertexProvider({project: config.project, location: config.location, fetchImpl: dependencies.fetchImpl, timeoutMs: config.requestTimeoutMs, accessToken: dependencies.accessToken});
}
