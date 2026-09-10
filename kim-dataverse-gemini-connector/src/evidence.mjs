import {HttpError, canonicalJson, sha256} from './core.mjs';

const BASE64 = /^[A-Za-z0-9+/]*={0,2}$/;

function audioPart(audio, provider, maximumBytes) {
  if (!audio || typeof audio !== 'object') throw new HttpError(400, 'INVALID_AUDIO', 'audio must be an object');
  const hasInline = typeof audio.dataBase64 === 'string' && audio.dataBase64.length > 0;
  const hasUri = typeof audio.uri === 'string' && audio.uri.length > 0;
  if (hasInline === hasUri) throw new HttpError(400, 'INVALID_AUDIO_SOURCE', 'Provide exactly one of audio.dataBase64 or audio.uri');
  if (typeof audio.mimeType !== 'string' || !/^audio\/[a-z0-9.+-]+$/i.test(audio.mimeType)) {
    throw new HttpError(400, 'INVALID_MIME_TYPE', 'audio.mimeType must be an audio MIME type');
  }
  const source = {uri: hasUri ? audio.uri : undefined};
  provider.validateSource(source);
  if (hasInline) {
    if (!BASE64.test(audio.dataBase64) || audio.dataBase64.length % 4 !== 0) throw new HttpError(400, 'INVALID_BASE64', 'audio.dataBase64 must be valid base64');
    const bytes = Buffer.from(audio.dataBase64, 'base64');
    if (bytes.length === 0) throw new HttpError(400, 'EMPTY_AUDIO', 'Inline audio is empty');
    if (bytes.length > maximumBytes) throw new HttpError(413, 'INLINE_AUDIO_TOO_LARGE', `Inline audio exceeds ${maximumBytes} bytes`);
    return {
      part: {inlineData: {mimeType: audio.mimeType, data: audio.dataBase64}},
      provenance: {sourceType: 'inline', contentSha256: sha256(bytes), byteLength: bytes.length, mimeType: audio.mimeType}
    };
  }
  return {
    part: {fileData: {mimeType: audio.mimeType, fileUri: audio.uri}},
    provenance: {sourceType: 'gcs-uri', sourceLocatorSha256: sha256(audio.uri), contentSha256: null, byteLength: null, mimeType: audio.mimeType}
  };
}

function transcriptionPrompt(input) {
  const speakerHint = Array.isArray(input.speakers) && input.speakers.length
    ? `Candidate speaker labels supplied by the requester: ${input.speakers.slice(0, 20).join(', ')}. Treat these as hints, never as proof.`
    : 'No verified speaker identities are supplied. Use Speaker 1, Speaker 2, etc., and [UNKNOWN] when attribution is uncertain.';
  return [
    'Create a faithful, evidence-aware transcript of this audio.',
    'Do not invent inaudible words, speaker identities, dates, or events. Mark uncertainty as [INAUDIBLE], [UNCLEAR], or [UNKNOWN SPEAKER].',
    'Preserve material wording, false starts, interruptions, and legally significant qualifiers.',
    input.timestamps === false ? 'Timestamps are optional.' : 'Include start and end timestamps for each utterance when the audio supports them.',
    input.diarization === false ? 'Do not infer identity; separate turns only when apparent.' : speakerHint,
    input.language ? `Requested language or locale hint: ${input.language}.` : 'Detect the spoken language and report it.',
    input.instructions ? `Additional requester instruction: ${String(input.instructions).slice(0, 4_000)}` : '',
    'Return JSON only with this shape: {"verbatimTranscript":"string","utterances":[{"speaker":"string","start":"HH:MM:SS.mmm|null","end":"HH:MM:SS.mmm|null","text":"string","confidence":"high|medium|low|unknown"}],"detectedLanguages":["string"],"unknownSegments":[{"timestamp":"string|null","reason":"string"}],"qualityWarnings":["string"],"summary":"string"}.'
  ].filter(Boolean).join('\n');
}

function parseModelJson(text) {
  const cleaned = text.trim().replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '');
  try {
    const value = JSON.parse(cleaned);
    if (!value || typeof value !== 'object' || typeof value.verbatimTranscript !== 'string') throw new Error('schema');
    return value;
  } catch {
    return {
      verbatimTranscript: text,
      utterances: [],
      detectedLanguages: [],
      unknownSegments: [],
      qualityWarnings: ['MODEL_OUTPUT_WAS_NOT_VALID_STRUCTURED_JSON'],
      summary: ''
    };
  }
}

function safeGenerationConfig(input, config) {
  const requested = input.maxOutputTokens === undefined ? config.maxOutputTokens : Number(input.maxOutputTokens);
  if (!Number.isInteger(requested) || requested < 128 || requested > config.maxOutputTokens) {
    throw new HttpError(400, 'INVALID_OUTPUT_LIMIT', `maxOutputTokens must be an integer from 128 to ${config.maxOutputTokens}`);
  }
  const temperature = input.temperature === undefined ? 0.1 : Number(input.temperature);
  if (!Number.isFinite(temperature) || temperature < 0 || temperature > 2) throw new HttpError(400, 'INVALID_TEMPERATURE', 'temperature must be from 0 to 2');
  return {maxOutputTokens: requested, temperature};
}

export function validateModel(input, config) {
  const model = input.model || config.defaultModel;
  if (!config.allowedModels.includes(model)) throw new HttpError(400, 'MODEL_NOT_ALLOWED', 'Requested model is not allowlisted');
  return model;
}

export async function transcribe({input, provider, config, signal, now = () => new Date()}) {
  const model = validateModel(input, config);
  const {part, provenance} = audioPart(input.audio, provider, config.maxInlineAudioBytes);
  const prompt = transcriptionPrompt(input);
  const body = {
    contents: [{role: 'user', parts: [{text: prompt}, part]}],
    generationConfig: {...safeGenerationConfig(input, config), responseMimeType: 'application/json'}
  };
  const startedAt = now().toISOString();
  const result = await provider.generate({model, body, signal});
  const transcript = parseModelJson(result.text);
  const completedAt = now().toISOString();
  const outputSha256 = sha256(canonicalJson(transcript));
  return {
    transcript,
    evidence: {
      caseId: typeof input.caseId === 'string' ? input.caseId.slice(0, 200) : null,
      evidenceId: typeof input.evidenceId === 'string' ? input.evidenceId.slice(0, 200) : null,
      ...provenance,
      outputSha256,
      startedAt,
      completedAt,
      provider: provider.name,
      model,
      evidentiaryStatus: 'MODEL_GENERATED_REQUIRES_HUMAN_VERIFICATION'
    },
    usage: result.payload.usageMetadata || null,
    finishReason: result.payload.candidates?.[0]?.finishReason || null,
    safetyRatings: result.payload.candidates?.[0]?.safetyRatings || []
  };
}

export async function generate({input, provider, config, signal}) {
  if (typeof input.prompt !== 'string' || input.prompt.trim().length === 0 || input.prompt.length > 100_000) {
    throw new HttpError(400, 'INVALID_PROMPT', 'prompt must contain 1 to 100000 characters');
  }
  const model = validateModel(input, config);
  const body = {
    contents: [{role: 'user', parts: [{text: input.prompt}]}],
    generationConfig: safeGenerationConfig(input, config)
  };
  if (typeof input.systemInstruction === 'string' && input.systemInstruction.trim()) {
    body.systemInstruction = {parts: [{text: input.systemInstruction.slice(0, 20_000)}]};
  }
  if (input.responseMimeType === 'application/json') body.generationConfig.responseMimeType = 'application/json';
  const result = await provider.generate({model, body, signal});
  return {
    text: result.text,
    provider: provider.name,
    model,
    outputSha256: sha256(result.text),
    usage: result.payload.usageMetadata || null,
    finishReason: result.payload.candidates?.[0]?.finishReason || null,
    safetyRatings: result.payload.candidates?.[0]?.safetyRatings || []
  };
}
