export const EDGE_SCHEMA = 'AEGIS_EDGE_POSTURE_V1' as const;

export type PlatformName = 'android' | 'ios' | 'macos' | 'windows' | 'unknown';

export type DeviceFacts = {
  sample_id: string;
  collected_at: string;
  consent: true;
  platform: PlatformName;
  os_version: string | number;
  security_patch?: string | null;
  app_version?: string | null;
  screen_lock_configured?: boolean | null;
  developer_mode?: boolean | null;
  adb_enabled?: boolean | null;
  app_debuggable?: boolean | null;
  secure_store_available?: boolean | null;
  gateway_url?: string | null;
  session_present?: boolean | null;
};

export type AegisEdgePosture = {
  schema: typeof EDGE_SCHEMA;
  sample_id: string;
  collected_at: string;
  consent: true;
  platform: PlatformName;
  os_major: string;
  security_patch_month: string | null;
  app_version_major_minor: string | null;
  screen_lock_configured: boolean | null;
  developer_mode: boolean | null;
  adb_enabled: boolean | null;
  app_debuggable: boolean | null;
  secure_store_available: boolean | null;
  gateway_https: boolean | null;
  session_present: boolean | null;
};

export type EdgeSecurityEvent = {
  event_class: 'DEVICE_INTEGRITY' | 'NETWORK_RISK' | 'IDENTITY_RISK';
  severity: number;
  confidence: number;
  source: 'FUSE_AEGIS_EDGE';
  consent: true;
  attributes: Record<string, boolean | number | string | null>;
};

const SAMPLE_ID = /^[A-Za-z0-9._:-]{8,96}$/;
const PATCH = /^(\d{4})-(\d{2})(?:-\d{2})?$/;
const SEMVER_PREFIX = /^(\d+)\.(\d+)/;
const FORBIDDEN_KEYS = new Set([
  'imei', 'meid', 'serial', 'serial_number', 'android_id', 'advertising_id',
  'phone_number', 'email', 'contacts', 'messages', 'location', 'latitude',
  'longitude', 'ssid', 'bssid', 'ip', 'ip_address', 'mac_address', 'device_name',
  'app_list', 'installed_apps', 'file_paths', 'files', 'photos', 'clipboard',
]);

function assertIsoTimestamp(value: string): void {
  const epoch = Date.parse(value);
  if (!Number.isFinite(epoch)) throw new Error('EDGE_TIMESTAMP_INVALID');
}

function coarseOsMajor(value: string | number): string {
  const text = String(value).trim();
  if (!text) return 'unknown';
  const match = text.match(/^(\d+)/);
  const major = match?.[1];
  return major ?? text.slice(0, 16);
}

function patchMonth(value?: string | null): string | null {
  if (!value) return null;
  const match = value.trim().match(PATCH);
  if (!match) throw new Error('EDGE_SECURITY_PATCH_INVALID');
  const year = match[1];
  const monthText = match[2];
  if (!year || !monthText) throw new Error('EDGE_SECURITY_PATCH_INVALID');
  const month = Number(monthText);
  if (month < 1 || month > 12) throw new Error('EDGE_SECURITY_PATCH_INVALID');
  return `${year}-${monthText}`;
}

function appMajorMinor(value?: string | null): string | null {
  if (!value) return null;
  const match = value.trim().match(SEMVER_PREFIX);
  if (!match) throw new Error('EDGE_APP_VERSION_INVALID');
  const major = match[1];
  const minor = match[2];
  if (!major || !minor) throw new Error('EDGE_APP_VERSION_INVALID');
  return `${major}.${minor}`;
}

function boolOrNull(value: boolean | null | undefined): boolean | null {
  return typeof value === 'boolean' ? value : null;
}

function gatewayHttps(value?: string | null): boolean | null {
  if (!value) return null;
  const trimmed = value.trim().toLowerCase();
  if (trimmed.startsWith('https://')) return true;
  if (trimmed.startsWith('http://localhost')) return true;
  return false;
}

export function assertNoForbiddenKeys(value: Record<string, unknown>): void {
  for (const key of Object.keys(value)) {
    if (FORBIDDEN_KEYS.has(key.toLowerCase())) throw new Error(`EDGE_FORBIDDEN_FIELD:${key}`);
  }
}

export function buildAegisEdgePosture(facts: DeviceFacts): AegisEdgePosture {
  assertNoForbiddenKeys(facts as unknown as Record<string, unknown>);
  if (facts.consent !== true) throw new Error('EDGE_CONSENT_REQUIRED');
  if (!SAMPLE_ID.test(facts.sample_id)) throw new Error('EDGE_SAMPLE_ID_INVALID');
  assertIsoTimestamp(facts.collected_at);

  const posture: AegisEdgePosture = {
    schema: EDGE_SCHEMA,
    sample_id: facts.sample_id,
    collected_at: facts.collected_at,
    consent: true,
    platform: facts.platform,
    os_major: coarseOsMajor(facts.os_version),
    security_patch_month: patchMonth(facts.security_patch),
    app_version_major_minor: appMajorMinor(facts.app_version),
    screen_lock_configured: boolOrNull(facts.screen_lock_configured),
    developer_mode: boolOrNull(facts.developer_mode),
    adb_enabled: boolOrNull(facts.adb_enabled),
    app_debuggable: boolOrNull(facts.app_debuggable),
    secure_store_available: boolOrNull(facts.secure_store_available),
    gateway_https: gatewayHttps(facts.gateway_url),
    session_present: boolOrNull(facts.session_present),
  };
  assertNoForbiddenKeys(posture as unknown as Record<string, unknown>);
  return posture;
}

function monthsOld(month: string | null, collectedAt: string): number | null {
  if (!month) return null;
  const match = month.match(/^(\d{4})-(\d{2})$/);
  if (!match) return null;
  const yearText = match[1];
  const monText = match[2];
  if (!yearText || !monText) return null;
  const year = Number(yearText);
  const mon = Number(monText);
  const now = new Date(collectedAt);
  return Math.max(0, (now.getUTCFullYear() - year) * 12 + (now.getUTCMonth() + 1 - mon));
}

export function postureToSecurityEvents(posture: AegisEdgePosture): EdgeSecurityEvent[] {
  const events: EdgeSecurityEvent[] = [];
  const patchAge = monthsOld(posture.security_patch_month, posture.collected_at);
  const integritySignals = [
    posture.screen_lock_configured === false,
    posture.developer_mode === true,
    posture.adb_enabled === true,
    posture.app_debuggable === true,
    posture.secure_store_available === false,
    patchAge !== null && patchAge >= 6,
  ];
  const integrityCount = integritySignals.filter(Boolean).length;
  if (integrityCount > 0) {
    events.push({
      event_class: 'DEVICE_INTEGRITY',
      severity: Math.min(0.95, 0.25 + 0.12 * integrityCount + (patchAge !== null && patchAge >= 12 ? 0.12 : 0)),
      confidence: 0.90,
      source: 'FUSE_AEGIS_EDGE',
      consent: true,
      attributes: {
        screen_lock_configured: posture.screen_lock_configured,
        developer_mode: posture.developer_mode,
        adb_enabled: posture.adb_enabled,
        app_debuggable: posture.app_debuggable,
        secure_store_available: posture.secure_store_available,
        security_patch_age_months: patchAge,
      },
    });
  }
  if (posture.gateway_https === false) {
    events.push({
      event_class: 'NETWORK_RISK', severity: 0.85, confidence: 0.98,
      source: 'FUSE_AEGIS_EDGE', consent: true,
      attributes: { gateway_https: false },
    });
  }
  if (posture.session_present === false) {
    events.push({
      event_class: 'IDENTITY_RISK', severity: 0.35, confidence: 0.85,
      source: 'FUSE_AEGIS_EDGE', consent: true,
      attributes: { session_present: false },
    });
  }
  return events;
}
