/*
 * MODISA-HMAC-V2 Apps Script migration adapter.
 * No secret values are stored in Script Properties, logged, or returned.
 */

var MODISA_HMAC_V2 = (function () {
  'use strict';

  var VERSION = 'MODISA-HMAC-V2';
  var PATH = '/v2/webhooks/modisa';
  var CONFIG_PROPERTY = 'MODISA_HMAC_V2_CONFIG_JSON';
  var RESOURCE_RE = /^projects\/(?:[a-z][a-z0-9-]{4,28}[a-z0-9]|[0-9]{6,30})\/secrets\/[A-Za-z0-9_-]{1,255}\/versions\/[1-9][0-9]*$/;
  var BASE_URL_RE = /^https:\/\/[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::[0-9]{2,5})?$/;
  var KEY_ID_RE = /^[A-Za-z0-9._/@:-]{3,200}$/;
  var ALLOWED_CONFIG_KEYS = {
    endpointBase: true,
    keyId: true,
    secretVersionResource: true,
    timeoutSeconds: true
  };

  function fail_(message) {
    throw new Error('MODISA-HMAC-V2: ' + message);
  }

  function assertPlainObject_(value, label) {
    if (!value || Object.prototype.toString.call(value) !== '[object Object]') {
      fail_(label + ' must be an object');
    }
  }

  function assertKnownKeys_(value, allowed) {
    Object.keys(value).forEach(function (key) {
      if (!allowed[key]) fail_('unknown configuration field');
    });
  }

  function assertExactKeys_(value, expected) {
    assertPlainObject_(value, 'receipt');
    var actual = Object.keys(value).sort();
    var wanted = expected.slice().sort();
    if (JSON.stringify(actual) !== JSON.stringify(wanted)) fail_('receipt fields are not exact');
  }

  function validateConfig_(config) {
    assertPlainObject_(config, 'configuration');
    assertKnownKeys_(config, ALLOWED_CONFIG_KEYS);
    if (!BASE_URL_RE.test(config.endpointBase || '')) fail_('endpointBase is not canonical HTTPS');
    if ((config.endpointBase || '').indexOf('secretmanager.googleapis.com') !== -1) {
      fail_('endpointBase cannot be the Secret Manager origin');
    }
    if (!KEY_ID_RE.test(config.keyId || '')) fail_('keyId is not canonical');
    if (!RESOURCE_RE.test(config.secretVersionResource || '')) {
      fail_('secretVersionResource must name an exact numeric version');
    }
    if (!Number.isInteger(config.timeoutSeconds) || config.timeoutSeconds < 1 || config.timeoutSeconds > 30) {
      fail_('timeoutSeconds must be an integer from 1 to 30');
    }
    return {
      endpointBase: config.endpointBase,
      keyId: config.keyId,
      secretVersionResource: config.secretVersionResource,
      timeoutSeconds: config.timeoutSeconds
    };
  }

  function requireBoolean_(value, label) {
    if (value !== true && value !== false) fail_(label + ' must be a Boolean');
    return value;
  }

  function configure(config, dryRun) {
    var clean = validateConfig_(config);
    requireBoolean_(dryRun, 'dryRun');
    if (dryRun) return {status: 'validated_not_written', external_effects: 0};
    var lock = LockService.getScriptLock();
    if (!lock.tryLock(5000)) fail_('configuration lock unavailable');
    try {
      PropertiesService.getScriptProperties().setProperty(CONFIG_PROPERTY, JSON.stringify(clean));
    } finally {
      lock.releaseLock();
    }
    return {status: 'configured', external_effects: 1};
  }

  function loadConfig_() {
    var encoded = PropertiesService.getScriptProperties().getProperty(CONFIG_PROPERTY);
    if (!encoded) fail_('configuration unavailable');
    try {
      return validateConfig_(JSON.parse(encoded));
    } catch (error) {
      fail_('configuration invalid');
    }
  }

  function unsignedByte_(value) {
    return (Number(value) + 256) % 256;
  }

  function bytesToHex_(bytes) {
    return bytes.map(function (value) {
      return unsignedByte_(value).toString(16).padStart(2, '0');
    }).join('');
  }

  function crc32c_(bytes) {
    var crc = 0xFFFFFFFF;
    bytes.forEach(function (value) {
      crc ^= unsignedByte_(value);
      for (var bit = 0; bit < 8; bit += 1) {
        crc = (crc >>> 1) ^ ((crc & 1) ? 0x82F63B78 : 0);
      }
    });
    return (crc ^ 0xFFFFFFFF) >>> 0;
  }

  function parseSecretResponse_(config, response) {
    if (response.getResponseCode() !== 200) fail_('Secret Manager access failed');
    var decoded;
    try {
      decoded = JSON.parse(response.getContentText());
    } catch (error) {
      fail_('Secret Manager response is not JSON');
    }
    if (!decoded || decoded.name !== config.secretVersionResource || !decoded.payload) {
      fail_('Secret Manager response identity is invalid');
    }
    if (typeof decoded.payload.dataCrc32c !== 'string' ||
        !/^[0-9]{1,10}$/.test(decoded.payload.dataCrc32c)) {
      fail_('Secret Manager checksum is unavailable');
    }
    var expected = Number(decoded.payload.dataCrc32c);
    if (!Number.isInteger(expected) || expected < 0 || expected > 0xFFFFFFFF) {
      fail_('Secret Manager checksum is unavailable');
    }
    var secretBytes;
    try {
      secretBytes = Utilities.base64Decode(decoded.payload.data);
    } catch (error) {
      fail_('Secret Manager payload encoding is invalid');
    }
    if (secretBytes.length < 32 || secretBytes.length > 65536) {
      fail_('Secret Manager payload length is outside policy');
    }
    if (crc32c_(secretBytes) !== expected) fail_('Secret Manager checksum mismatch');
    return secretBytes;
  }

  function fetchSecret_(config) {
    var url = 'https://secretmanager.googleapis.com/v1/' + config.secretVersionResource + ':access';
    var lastCode = 0;
    for (var attempt = 0; attempt < 2; attempt += 1) {
      var response;
      try {
        response = UrlFetchApp.fetch(url, {
          method: 'get',
          headers: {Authorization: 'Bearer ' + ScriptApp.getOAuthToken()},
          followRedirects: false,
          muteHttpExceptions: true,
          validateHttpsCertificates: true,
          timeoutSeconds: config.timeoutSeconds
        });
      } catch (error) {
        fail_('Secret Manager transport failed safely');
      }
      lastCode = response.getResponseCode();
      if (lastCode === 200) return parseSecretResponse_(config, response);
      if (attempt === 0 && [401, 429, 500, 502, 503, 504].indexOf(lastCode) !== -1) {
        Utilities.sleep(Math.min(1000, config.timeoutSeconds * 100));
        continue;
      }
      break;
    }
    fail_('Secret Manager access failed');
  }

  function canonical_(keyId, timestamp, nonce, bodyBytes) {
    if (!KEY_ID_RE.test(keyId)) fail_('keyId is not canonical');
    if (!Number.isInteger(timestamp) || timestamp < 1) fail_('timestamp is invalid');
    if (!/^[A-Za-z0-9._~-]{16,256}$/.test(nonce)) fail_('nonce is invalid');
    var bodyHash = bytesToHex_(Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      bodyBytes
    ));
    return {
      bodyHash: bodyHash,
      message: [VERSION, keyId, String(timestamp), nonce, 'POST', PATH, bodyHash].join('\n')
    };
  }

  function buildSignedRequestWithSecret_(config, bodyText, secretBytes, timestamp, nonce) {
    var clean = validateConfig_(config);
    if (typeof bodyText !== 'string') fail_('bodyText must be a string');
    try {
      JSON.parse(bodyText);
    } catch (error) {
      fail_('bodyText must contain JSON');
    }
    if (!Array.isArray(secretBytes) || secretBytes.length < 32 || secretBytes.length > 65536) {
      fail_('secret bytes are outside policy');
    }
    var bodyBytes = Utilities.newBlob(bodyText, 'application/json').getBytes();
    var canonical = canonical_(clean.keyId, timestamp, nonce, bodyBytes);
    var canonicalBytes = Utilities.newBlob(canonical.message, 'text/plain').getBytes();
    var signature = bytesToHex_(Utilities.computeHmacSha256Signature(canonicalBytes, secretBytes));
    return {
      url: clean.endpointBase + PATH,
      options: {
        method: 'post',
        contentType: 'application/json; charset=utf-8',
        payload: bodyBytes,
        headers: {
          'X-Modisa-Key-Id': clean.keyId,
          'X-Modisa-Timestamp': String(timestamp),
          'X-Modisa-Nonce': nonce,
          'X-Modisa-Signature': signature
        },
        followRedirects: false,
        muteHttpExceptions: true,
        validateHttpsCertificates: true,
        timeoutSeconds: clean.timeoutSeconds
      },
      expected: {
        keyId: clean.keyId,
        timestamp: timestamp,
        nonceSha256: bytesToHex_(Utilities.computeDigest(
          Utilities.DigestAlgorithm.SHA_256,
          Utilities.newBlob(nonce, 'text/plain').getBytes()
        )),
        bodySha256: canonical.bodyHash
      }
    };
  }

  function buildSignedRequest_(config, bodyText) {
    var secretBytes = fetchSecret_(config);
    return buildSignedRequestWithSecret_(
      config,
      bodyText,
      secretBytes,
      Math.floor(Date.now() / 1000),
      Utilities.getUuid().replace(/-/g, '')
    );
  }

  function validateReceipt_(request, response) {
    if (response.getResponseCode() !== 200) fail_('MODISA webhook did not return success');
    var receipt;
    try {
      receipt = JSON.parse(response.getContentText());
    } catch (error) {
      fail_('MODISA webhook receipt is not JSON');
    }
    var auth = receipt && receipt.auth;
    assertExactKeys_(receipt, ['status', 'external_effects', 'auth']);
    assertExactKeys_(auth, [
      'schema', 'signature_version', 'key_id', 'timestamp', 'nonce_sha256',
      'body_sha256', 'secret_ref_scheme', 'signature_valid', 'replay_protected',
      'secret_material_persisted'
    ]);
    if (
      receipt.status !== 'authenticated_no_dispatch' ||
      receipt.external_effects !== 0 ||
      !auth ||
      auth.schema !== 'MODISA_WEBHOOK_AUTH_RECEIPT_V1' ||
      auth.signature_version !== VERSION ||
      auth.key_id !== request.expected.keyId ||
      auth.timestamp !== request.expected.timestamp ||
      auth.nonce_sha256 !== request.expected.nonceSha256 ||
      auth.body_sha256 !== request.expected.bodySha256 ||
      auth.secret_ref_scheme !== 'gcp-secret' ||
      auth.signature_valid !== true ||
      auth.replay_protected !== true ||
      auth.secret_material_persisted !== false
    ) fail_('MODISA webhook semantic receipt is invalid');
    return {
      status: receipt.status,
      key_id: auth.key_id,
      body_sha256: auth.body_sha256,
      nonce_sha256: auth.nonce_sha256,
      external_effects: 0
    };
  }

  function dryRun(bodyText) {
    var config = loadConfig_();
    if (typeof bodyText !== 'string') fail_('bodyText must be a string');
    try {
      JSON.parse(bodyText);
    } catch (error) {
      fail_('bodyText must contain JSON');
    }
    var bodyBytes = Utilities.newBlob(bodyText, 'application/json').getBytes();
    var bodyHash = bytesToHex_(Utilities.computeDigest(
      Utilities.DigestAlgorithm.SHA_256,
      bodyBytes
    ));
    return {
      status: 'configuration_and_body_validated_not_signed',
      key_id: config.keyId,
      body_sha256: bodyHash,
      external_effects: 0
    };
  }

  function send(bodyText) {
    var request = buildSignedRequest_(loadConfig_(), bodyText);
    var response = UrlFetchApp.fetch(request.url, request.options);
    return validateReceipt_(request, response);
  }

  return Object.freeze({
    configure: configure,
    dryRun: dryRun,
    send: send,
    _test: Object.freeze({
      buildSignedRequestWithSecret: buildSignedRequestWithSecret_,
      crc32c: crc32c_,
      fetchSecret: fetchSecret_,
      parseSecretResponse: parseSecretResponse_,
      validateConfig: validateConfig_,
      validateReceipt: validateReceipt_
    })
  });
}());
