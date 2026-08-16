/**
 * Forest-First Ω Private Event Sensor v1
 *
 * Trigger-only Google Workspace sensor. It never exposes a web app and never
 * exports Gmail/Drive content. It observes configured metadata, writes an
 * append-only private queue, and may dispatch a sanitized Bubbles command only
 * after a separately verified dispatch credential binding is enabled.
 *
 * No secret values belong in this source or Script Properties. The GitHub
 * dispatch credential, when eventually enabled, must be resolved from Google
 * Secret Manager through a configured secret resource name and must pass the
 * Federation provider/cost gates first.
 */

const FFO_SENSOR = Object.freeze({
  VERSION: '1.0.0',
  STATE_PREFIX: 'FFO_SENSOR_STATE_',
  PROP_GMAIL_QUERY: 'FFO_SENSOR_GMAIL_QUERY',
  PROP_DRIVE_IDS: 'FFO_SENSOR_DRIVE_IDS',
  PROP_QUEUE_SHEET_ID: 'FFO_SENSOR_QUEUE_SHEET_ID',
  PROP_QUEUE_TAB: 'FFO_SENSOR_QUEUE_TAB',
  PROP_MATTER_CLASS: 'FFO_SENSOR_MATTER_CLASS',
  PROP_DISPATCH_ENABLED: 'FFO_SENSOR_DISPATCH_ENABLED',
  PROP_GITHUB_REPO: 'FFO_SENSOR_GITHUB_REPO',
  PROP_GITHUB_WORKFLOW: 'FFO_SENSOR_GITHUB_WORKFLOW',
  PROP_GITHUB_REF: 'FFO_SENSOR_GITHUB_REF',
  PROP_GITHUB_TOKEN_SECRET: 'FFO_SENSOR_GITHUB_TOKEN_SECRET_RESOURCE',
  DEFAULT_GMAIL_QUERY: 'newer_than:1d',
  DEFAULT_QUEUE_TAB: 'FOREST_EVENT_QUEUE',
  DEFAULT_MATTER_CLASS: 'GENERAL',
  MAX_GMAIL_RESULTS: 25,
  DISPATCH_TIMEOUT_MS: 20000,
});

function FFO_SENSOR_INSTALL_15M() {
  FFO_SENSOR_REMOVE_TRIGGERS_();
  ScriptApp.newTrigger('FFO_SENSOR_TICK')
    .timeBased()
    .everyMinutes(15)
    .create();
  return {ok: true, cadence: '15_MINUTES', version: FFO_SENSOR.VERSION};
}

function FFO_SENSOR_REMOVE_TRIGGERS_() {
  ScriptApp.getProjectTriggers().forEach(function(trigger) {
    if (trigger.getHandlerFunction() === 'FFO_SENSOR_TICK') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

function FFO_SENSOR_TICK() {
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const config = FFO_SENSOR_CONFIG_();
    const events = [];
    events.push.apply(events, FFO_SENSOR_GMAIL_EVENTS_(config));
    events.push.apply(events, FFO_SENSOR_DRIVE_EVENTS_(config));

    const results = [];
    events.forEach(function(event) {
      FFO_SENSOR_QUEUE_(config, event, 'PENDING');
      let dispatch = {attempted: false, delivered: false, status: 'QUEUE_ONLY'};
      if (config.dispatchEnabled) {
        dispatch = FFO_SENSOR_DISPATCH_(config, event);
        FFO_SENSOR_QUEUE_(config, event, dispatch.delivered ? 'DISPATCHED' : 'DISPATCH_FAILED');
      }
      results.push({eventId: event.event_id, dispatch: dispatch});
    });

    return {
      ok: true,
      version: FFO_SENSOR.VERSION,
      detected: events.length,
      results: results,
      privateContentExported: false,
    };
  } finally {
    lock.releaseLock();
  }
}

function FFO_SENSOR_CONFIG_() {
  const props = PropertiesService.getScriptProperties();
  const queueSheetId = String(props.getProperty(FFO_SENSOR.PROP_QUEUE_SHEET_ID) || '').trim();
  if (!queueSheetId) throw new Error('Private queue sheet ID is required');

  const matterClass = String(props.getProperty(FFO_SENSOR.PROP_MATTER_CLASS) || FFO_SENSOR.DEFAULT_MATTER_CLASS).trim().toUpperCase();
  if (['LEGAL', 'EVIDENCE', 'SYSTEM', 'PLATFORM', 'GENERAL'].indexOf(matterClass) < 0) {
    throw new Error('Unsupported matter class');
  }

  return {
    gmailQuery: String(props.getProperty(FFO_SENSOR.PROP_GMAIL_QUERY) || FFO_SENSOR.DEFAULT_GMAIL_QUERY),
    driveIds: String(props.getProperty(FFO_SENSOR.PROP_DRIVE_IDS) || '')
      .split(',').map(function(v) { return v.trim(); }).filter(Boolean),
    queueSheetId: queueSheetId,
    queueTab: String(props.getProperty(FFO_SENSOR.PROP_QUEUE_TAB) || FFO_SENSOR.DEFAULT_QUEUE_TAB),
    matterClass: matterClass,
    dispatchEnabled: String(props.getProperty(FFO_SENSOR.PROP_DISPATCH_ENABLED) || 'false').toLowerCase() === 'true',
    githubRepo: String(props.getProperty(FFO_SENSOR.PROP_GITHUB_REPO) || ''),
    githubWorkflow: String(props.getProperty(FFO_SENSOR.PROP_GITHUB_WORKFLOW) || 'bubbles-command-bus.yml'),
    githubRef: String(props.getProperty(FFO_SENSOR.PROP_GITHUB_REF) || 'main'),
    githubTokenSecretResource: String(props.getProperty(FFO_SENSOR.PROP_GITHUB_TOKEN_SECRET) || ''),
  };
}

function FFO_SENSOR_GMAIL_EVENTS_(config) {
  const url = 'https://gmail.googleapis.com/gmail/v1/users/me/messages?' +
    'maxResults=' + encodeURIComponent(String(FFO_SENSOR.MAX_GMAIL_RESULTS)) + '&q=' + encodeURIComponent(config.gmailQuery);
  const payload = FFO_SENSOR_FETCH_JSON_(url, 'https://www.googleapis.com/auth/gmail.readonly');
  const messages = Array.isArray(payload.messages) ? payload.messages : [];
  const events = [];

  messages.forEach(function(message) {
    const opaque = String(message.id || '');
    if (!opaque) return;
    const stateKey = FFO_SENSOR.STATE_PREFIX + 'GMAIL_' + FFO_SENSOR_SHA256_(opaque);
    if (FFO_SENSOR_SEEN_(stateKey)) return;
    FFO_SENSOR_MARK_SEEN_(stateKey);
    events.push(FFO_SENSOR_EVENT_('GMAIL_METADATA', 'NEW_ITEM', config.matterClass, FFO_SENSOR_SHA256_('gmail:' + opaque), {
      materiality: 0.70,
      consequence: config.matterClass === 'LEGAL' ? 0.80 : 0.50,
      uncertainty: 0.75,
      provider_readback_missing: true,
    }));
  });
  return events;
}

function FFO_SENSOR_DRIVE_EVENTS_(config) {
  const events = [];
  config.driveIds.forEach(function(fileId) {
    const url = 'https://www.googleapis.com/drive/v3/files/' + encodeURIComponent(fileId) +
      '?fields=id%2CmodifiedTime&supportsAllDrives=true';
    const payload = FFO_SENSOR_FETCH_JSON_(url, 'https://www.googleapis.com/auth/drive.metadata.readonly');
    const modified = String(payload.modifiedTime || '');
    if (!modified) return;
    const fingerprint = FFO_SENSOR_SHA256_('drive:' + fileId + ':' + modified);
    const stateKey = FFO_SENSOR.STATE_PREFIX + 'DRIVE_' + FFO_SENSOR_SHA256_(fileId);
    const props = PropertiesService.getScriptProperties();
    if (props.getProperty(stateKey) === fingerprint) return;
    props.setProperty(stateKey, fingerprint);
    events.push(FFO_SENSOR_EVENT_('DRIVE_METADATA', 'STATE_CHANGE', config.matterClass, fingerprint, {
      materiality: 0.70,
      consequence: config.matterClass === 'LEGAL' ? 0.80 : 0.55,
      uncertainty: 0.50,
      provider_readback_missing: true,
    }));
  });
  return events;
}

function FFO_SENSOR_EVENT_(sourceClass, eventClass, matterClass, fingerprint, overrides) {
  overrides = overrides || {};
  return {
    schema: 'BUBBLES-FOREST-BACKGROUND-EVENT-V1',
    event_id: 'evt-' + fingerprint.substring(0, 24),
    source_class: sourceClass,
    event_class: eventClass,
    fingerprint_sha256: fingerprint,
    matter_class: matterClass,
    materiality: Number(overrides.materiality || 0.50),
    consequence: Number(overrides.consequence || 0.50),
    uncertainty: Number(overrides.uncertainty || 0.50),
    dependency_density: 0.50,
    adversarial_complexity: matterClass === 'LEGAL' ? 0.70 : 0.30,
    deadline_risk: false,
    evidence_risk: false,
    owner_only: false,
    provider_readback_missing: Boolean(overrides.provider_readback_missing),
    route_failure: false,
    objective_exhausted: false,
    material_strategy_change: false,
    private_content_included: false,
  };
}

function FFO_SENSOR_QUEUE_(config, event, state) {
  const ss = SpreadsheetApp.openById(config.queueSheetId);
  let sheet = ss.getSheetByName(config.queueTab);
  if (!sheet) {
    sheet = ss.insertSheet(config.queueTab);
    sheet.appendRow(['timestamp', 'event_id', 'state', 'source_class', 'event_class', 'fingerprint_sha256', 'matter_class']);
  }
  sheet.appendRow([
    new Date().toISOString(), event.event_id, state, event.source_class,
    event.event_class, event.fingerprint_sha256, event.matter_class,
  ]);
}

function FFO_SENSOR_DISPATCH_(config, event) {
  if (!config.githubRepo || !config.githubWorkflow || !config.githubTokenSecretResource) {
    return {attempted: false, delivered: false, status: 'DISPATCH_BINDING_INCOMPLETE'};
  }
  const token = FFO_SENSOR_SECRET_ACCESS_(config.githubTokenSecretResource);
  const command = {
    schema: 'BUBBLES-CONTROL-COMMAND-V1',
    adapter_id: 'bubbles_command_bus',
    action: 'forest_first_omega_event',
    effect: 'READ',
    target_alias: 'FOREST_FIRST_OMEGA_BACKGROUND_RUNTIME',
    payload: {event: event},
  };
  const url = 'https://api.github.com/repos/' + config.githubRepo + '/actions/workflows/' +
    encodeURIComponent(config.githubWorkflow) + '/dispatches';
  const response = UrlFetchApp.fetch(url, {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
    payload: JSON.stringify({ref: config.githubRef, inputs: {command_json: JSON.stringify(command)}}),
    muteHttpExceptions: true,
  });
  const code = response.getResponseCode();
  return {attempted: true, delivered: code === 204, status: code === 204 ? 'DISPATCHED' : 'HTTP_' + code};
}

function FFO_SENSOR_SECRET_ACCESS_(resourceName) {
  if (!/^projects\/[A-Za-z0-9._-]+\/secrets\/[A-Za-z0-9._-]+\/versions\/[A-Za-z0-9._-]+$/.test(resourceName)) {
    throw new Error('Secret Manager resource name is invalid');
  }
  const url = 'https://secretmanager.googleapis.com/v1/' + resourceName + ':access';
  const payload = FFO_SENSOR_FETCH_JSON_(url, 'https://www.googleapis.com/auth/cloud-platform');
  if (!payload.payload || !payload.payload.data) throw new Error('Secret payload unavailable');
  return Utilities.newBlob(Utilities.base64Decode(payload.payload.data)).getDataAsString();
}

function FFO_SENSOR_FETCH_JSON_(url, requiredScope) {
  const tokenInfo = ScriptApp.getAuthorizationInfo(ScriptApp.AuthMode.FULL, [requiredScope]);
  if (tokenInfo.getAuthorizationStatus() !== ScriptApp.AuthorizationStatus.NOT_REQUIRED) {
    throw new Error('Required OAuth scope is not authorised: ' + requiredScope);
  }
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    headers: {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()},
    muteHttpExceptions: true,
  });
  const code = response.getResponseCode();
  if (code < 200 || code >= 300) throw new Error('Provider metadata read failed HTTP ' + code);
  return JSON.parse(response.getContentText());
}

function FFO_SENSOR_SHA256_(value) {
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, String(value), Utilities.Charset.UTF_8);
  return bytes.map(function(b) { const n = b < 0 ? b + 256 : b; return ('0' + n.toString(16)).slice(-2); }).join('');
}

function FFO_SENSOR_SEEN_(stateKey) {
  return PropertiesService.getScriptProperties().getProperty(stateKey) === '1';
}

function FFO_SENSOR_MARK_SEEN_(stateKey) {
  PropertiesService.getScriptProperties().setProperty(stateKey, '1');
}
