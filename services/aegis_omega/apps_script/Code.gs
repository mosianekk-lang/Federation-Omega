/**
 * AEGIS-Ω Apps Script operator adapter.
 * Defensive status/assessment submission only. Secrets live in Script Properties.
 */
function aegisConfig_() {
  const p = PropertiesService.getScriptProperties();
  return {
    baseUrl: p.getProperty('AEGIS_BASE_URL'),
    bearer: p.getProperty('AEGIS_ID_TOKEN') || ''
  };
}

function aegisHeaders_() {
  const c = aegisConfig_();
  const h = {'Content-Type': 'application/json'};
  if (c.bearer) h['Authorization'] = 'Bearer ' + c.bearer;
  return h;
}

function aegisHealth() {
  const c = aegisConfig_();
  if (!c.baseUrl) throw new Error('Set AEGIS_BASE_URL in Script Properties.');
  const r = UrlFetchApp.fetch(c.baseUrl + '/healthz', {headers: aegisHeaders_(), muteHttpExceptions: true});
  return {status: r.getResponseCode(), body: JSON.parse(r.getContentText())};
}

function aegisAssess(events) {
  const c = aegisConfig_();
  if (!Array.isArray(events) || events.length === 0) throw new Error('Provide authorized defensive events.');
  const r = UrlFetchApp.fetch(c.baseUrl + '/v1/assess', {
    method: 'post', headers: aegisHeaders_(), payload: JSON.stringify({request_id: Utilities.getUuid(), events: events}), muteHttpExceptions: true
  });
  if (r.getResponseCode() >= 300) throw new Error(r.getContentText());
  return JSON.parse(r.getContentText());
}
