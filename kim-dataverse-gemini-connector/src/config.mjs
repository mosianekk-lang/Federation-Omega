const integer = (name, fallback, minimum, maximum) => {
  const raw = process.env[name];
  const value = raw === undefined ? fallback : Number.parseInt(raw, 10);
  if (!Number.isInteger(value) || value < minimum || value > maximum) {
    throw new Error(`${name} must be an integer from ${minimum} to ${maximum}`);
  }
  return value;
};

const csv = (value) => [...new Set(value.split(',').map((item) => item.trim()).filter(Boolean))];

export function loadConfig(overrides = {}) {
  const allowedModels = overrides.allowedModels ?? csv(process.env.KDV_ALLOWED_MODELS || 'gemini-2.5-flash,gemini-2.5-pro');
  const defaultModel = overrides.defaultModel ?? process.env.KDV_DEFAULT_MODEL ?? allowedModels[0];
  if (!allowedModels.includes(defaultModel)) throw new Error('KDV_DEFAULT_MODEL must be listed in KDV_ALLOWED_MODELS');

  const providerMode = overrides.providerMode ?? process.env.KDV_PROVIDER ?? 'auto';
  if (!['auto', 'developer', 'vertex'].includes(providerMode)) throw new Error('KDV_PROVIDER must be auto, developer, or vertex');

  return Object.freeze({
    port: overrides.port ?? integer('PORT', 8080, 1, 65535),
    providerMode,
    apiKey: overrides.apiKey ?? process.env.GEMINI_API_KEY ?? process.env.GOOGLE_API_KEY ?? '',
    project: overrides.project ?? process.env.GOOGLE_CLOUD_PROJECT ?? process.env.GCLOUD_PROJECT ?? '',
    location: overrides.location ?? process.env.GOOGLE_CLOUD_LOCATION ?? 'africa-south1',
    sharedToken: overrides.sharedToken ?? process.env.KDV_SHARED_TOKEN ?? '',
    allowedModels,
    defaultModel,
    maxRequestBytes: overrides.maxRequestBytes ?? integer('KDV_MAX_REQUEST_BYTES', 18_000_000, 1_024, 25_000_000),
    maxInlineAudioBytes: overrides.maxInlineAudioBytes ?? integer('KDV_MAX_INLINE_AUDIO_BYTES', 13_000_000, 1_024, 18_000_000),
    maxOutputTokens: overrides.maxOutputTokens ?? integer('KDV_MAX_OUTPUT_TOKENS', 8_192, 128, 65_536),
    requestTimeoutMs: overrides.requestTimeoutMs ?? integer('KDV_REQUEST_TIMEOUT_MS', 120_000, 1_000, 600_000),
    maxConcurrency: overrides.maxConcurrency ?? integer('KDV_MAX_CONCURRENCY', 4, 1, 100),
    dailyRequestLimit: overrides.dailyRequestLimit ?? integer('KDV_DAILY_REQUEST_LIMIT', 250, 1, 1_000_000),
    idempotencyTtlMs: overrides.idempotencyTtlMs ?? integer('KDV_IDEMPOTENCY_TTL_MS', 86_400_000, 1_000, 604_800_000)
  });
}

export function configReadiness(config) {
  const chosen = config.providerMode === 'auto' ? (config.apiKey ? 'developer' : 'vertex') : config.providerMode;
  const missing = [];
  if (chosen === 'developer' && !config.apiKey) missing.push('GEMINI_API_KEY');
  if (chosen === 'vertex' && !config.project) missing.push('GOOGLE_CLOUD_PROJECT');
  return {ready: missing.length === 0, provider: chosen, missing};
}
