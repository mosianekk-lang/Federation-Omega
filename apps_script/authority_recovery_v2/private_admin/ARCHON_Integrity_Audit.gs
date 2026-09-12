/* ============================================================================
 * HASHING, DIFFS, AND SERIALIZATION
 * ========================================================================== */

function ARCHON_CODE_projectHash_(files) {
  const normalized =
    ARCHON_CODE_sortFiles_(files).map(function (file) {
      return {
        name: file.name,
        type: file.type,
        source: file.source
      };
    });

  return ARCHON_CODE_sha256_(
    ARCHON_CODE_canonicalJson_(normalized)
  );
}


function ARCHON_CODE_sha256_(text) {
  const digest = Utilities.computeDigest(
    Utilities.DigestAlgorithm.SHA_256,
    text,
    Utilities.Charset.UTF_8
  );

  return digest.map(function (byte) {
    const value = byte < 0 ? byte + 256 : byte;
    return value.toString(16).padStart(2, '0');
  }).join('');
}


function ARCHON_CODE_hashRecord_(record, hashField) {
  const copy = JSON.parse(JSON.stringify(record || {}));
  delete copy[hashField];
  return ARCHON_CODE_sha256_(ARCHON_CODE_canonicalJson_(copy));
}


function ARCHON_CODE_sortFiles_(files) {
  return files
    .slice()
    .sort(function (left, right) {
      return String(left.name)
        .localeCompare(String(right.name));
    });
}


function ARCHON_CODE_fileSummary_(file) {
  return {
    name: file.name,
    type: file.type,
    characters:
      typeof file.source === 'string'
        ? file.source.length
        : 0,
    hash: ARCHON_CODE_sha256_(
      file.source || ''
    )
  };
}


function ARCHON_CODE_diffFiles_(
  beforeFiles,
  afterFiles
) {
  const before = {};
  const after = {};
  const changes = [];

  beforeFiles.forEach(function (file) {
    before[file.name] = ARCHON_CODE_fileSummary_(file);
  });

  afterFiles.forEach(function (file) {
    after[file.name] = ARCHON_CODE_fileSummary_(file);
  });

  const names = Array.from(
    new Set(
      Object.keys(before).concat(Object.keys(after))
    )
  ).sort();

  names.forEach(function (name) {
    if (!before[name]) {
      changes.push({
        file: name,
        action: 'CREATED',
        after: after[name]
      });
    } else if (!after[name]) {
      changes.push({
        file: name,
        action: 'DELETED',
        before: before[name]
      });
    } else if (
      before[name].hash !== after[name].hash ||
      before[name].type !== after[name].type
    ) {
      changes.push({
        file: name,
        action: 'UPDATED',
        before: before[name],
        after: after[name]
      });
    }
  });

  return changes;
}


/* ============================================================================
 * AUDIT LEDGERS
 * ========================================================================== */

function ARCHON_CODE_writeAudit_(
  status,
  request,
  result
) {
  const sheet = ARCHON_CODE_ensureSheet_(
    ARCHON_CODE.SHEET.AUDIT,
    [
      'timestamp',
      'transactionId',
      'action',
      'status',
      'description',
      'resultJson'
    ]
  );

  sheet.appendRow([
    new Date().toISOString(),
    request.transactionId || '',
    request.action || '',
    status,
    request.description || '',
    ARCHON_CODE_limitCell_(
      JSON.stringify(result)
    )
  ]);
}


function ARCHON_CODE_writeRelease_(result) {
  const sheet = ARCHON_CODE_ensureSheet_(
    ARCHON_CODE.SHEET.RELEASES,
    [
      'timestamp',
      'transactionId',
      'versionNumber',
      'beforeHash',
      'afterHash',
      'deploymentId',
      'backupFileId',
      'releaseJson'
    ]
  );

  sheet.appendRow([
    new Date().toISOString(),
    result.transactionId || '',
    result.version
      ? result.version.versionNumber
      : '',
    result.beforeHash || '',
    result.afterHash || '',
    result.deployment
      ? result.deployment.deploymentId || ''
      : '',
    result.backup
      ? result.backup.fileId || ''
      : '',
    ARCHON_CODE_limitCell_(
      JSON.stringify(result)
    )
  ]);
}


function ARCHON_CODE_auditSpreadsheet_() {
  const spreadsheetId = String(
    PropertiesService.getScriptProperties().getProperty(
      ARCHON_CODE.PROPERTY.AUDIT_SPREADSHEET_ID
    ) || ''
  );
  if (!spreadsheetId) {
    throw new Error('ARCHON_AUDIT_SPREADSHEET_ID is not configured.');
  }
  return SpreadsheetApp.openById(spreadsheetId);
}

function ARCHON_CODE_assertNoSecretMaterial_(value, path) {
  const currentPath = path || 'request';
  if (value === null || typeof value === 'undefined') {
    return;
  }
  if (Array.isArray(value)) {
    value.forEach(function (item, index) {
      ARCHON_CODE_assertNoSecretMaterial_(item, currentPath + '[' + index + ']');
    });
    return;
  }
  if (typeof value === 'object') {
    Object.keys(value).forEach(function (key) {
      const normalized = String(key).replace(/[_-]/g, '').toLowerCase();
      if (
        /^(password|passwd|accesstoken|refreshtoken|idtoken|apikey|privatekey|authorization|cookie|credentialvalue|clientsecret)$/.test(normalized)
      ) {
        throw new Error('Secret-bearing request field rejected: ' + currentPath + '.' + key);
      }
      ARCHON_CODE_assertNoSecretMaterial_(
        value[key],
        currentPath + '.' + key
      );
    });
    return;
  }
  if (typeof value === 'string' && (
    /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/.test(value) ||
    /\bBearer\s+[A-Za-z0-9._~+\/-]{16,}/i.test(value) ||
    /\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b/.test(value) ||
    /\bgh[pousr]_[A-Za-z0-9]{20,}\b/.test(value)
  )) {
    throw new Error('Secret-shaped request value rejected at ' + currentPath);
  }
}

function ARCHON_CODE_assertNoEmbeddedSecret_(source, fileName) {
  const text = String(source || '');
  const patterns = [
    /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
    /\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b/,
    /\bgh[pousr]_[A-Za-z0-9]{20,}\b/,
    /(?:APPROVAL_KEY|GATEWAY_TOKEN|AUTHORIZATION_TOKEN)\s*:\s*['"][^'"]+['"]/i
  ];
  if (patterns.some(function (pattern) { return pattern.test(text); })) {
    throw new Error('Secret-like source material rejected in ' + String(fileName || 'file'));
  }
}

function ARCHON_CODE_namespaceAudit_(files) {
  const declarations = {};
  const critical = {
    doGet: true,
    doPost: true,
    SOVARA_ADMIN_dispatch: true,
    SOVARA_ARCHON_codeApply: true,
    SOVARA_ARCHON_codeRollback: true
  };
  (files || []).forEach(function (file) {
    const source = String(file.source || '');
    const pattern = /\bfunction\s+([A-Za-z_$][\w$]*)\s*\(/g;
    let match;
    while ((match = pattern.exec(source)) !== null) {
      declarations[match[1]] = declarations[match[1]] || [];
      declarations[match[1]].push(file.name);
    }
  });
  const errors = [];
  const warnings = [];
  Object.keys(declarations).sort().forEach(function (name) {
    if (critical[name] && declarations[name].length > 1) {
      errors.push(
        'Duplicate critical global function ' + name + ': ' +
        declarations[name].join(', ')
      );
    }
  });
  if (declarations.doGet || declarations.doPost) {
    errors.push('Private admin project must not contain doGet or doPost.');
  }
  return {errors: errors, warnings: warnings, declarations: declarations};
}

function ARCHON_CODE_captureDeploymentState_(suppliedDeploymentId) {
  const deploymentId = suppliedDeploymentId ||
    PropertiesService.getScriptProperties().getProperty(
      ARCHON_CODE.PROPERTY.DEPLOYMENT_ID
    ) || '';
  if (!deploymentId) {
    return null;
  }
  const deployments = ARCHON_CODE_listDeployments_();
  const selected = deployments.find(function (item) {
    return String(item.deploymentId || '') === String(deploymentId);
  });
  if (!selected || !selected.deploymentConfig) {
    throw new Error('Configured deployment state could not be read back.');
  }
  return {
    deploymentId: deploymentId,
    versionNumber: Number(selected.deploymentConfig.versionNumber),
    description: String(selected.deploymentConfig.description || '')
  };
}

function ARCHON_CODE_verifyDeploymentReadback_(deploymentId, versionNumber) {
  const deployments = ARCHON_CODE_listDeployments_();
  const selected = deployments.find(function (item) {
    return String(item.deploymentId || '') === String(deploymentId || '');
  });
  if (
    !selected ||
    !selected.deploymentConfig ||
    Number(selected.deploymentConfig.versionNumber) !== Number(versionNumber)
  ) {
    throw new Error('Deployment version readback mismatch.');
  }
  return {
    verified: true,
    deploymentId: selected.deploymentId,
    versionNumber: Number(selected.deploymentConfig.versionNumber)
  };
}


function ARCHON_CODE_latestAudit_(limit) {
  const spreadsheet = ARCHON_CODE_auditSpreadsheet_();

  const sheet = spreadsheet.getSheetByName(
    ARCHON_CODE.SHEET.AUDIT
  );

  if (!sheet || sheet.getLastRow() < 2) {
    return [];
  }

  const rowCount = Math.min(
    Number(limit || 20),
    sheet.getLastRow() - 1
  );

  const firstRow =
    sheet.getLastRow() - rowCount + 1;

  return sheet
    .getRange(
      firstRow,
      1,
      rowCount,
      sheet.getLastColumn()
    )
    .getDisplayValues()
    .reverse();
}


function ARCHON_CODE_ensureSheet_(
  name,
  headers
) {
  const spreadsheet = ARCHON_CODE_auditSpreadsheet_();

  let sheet = spreadsheet.getSheetByName(name);

  if (!sheet) {
    sheet = spreadsheet.insertSheet(name);
  }

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(headers);
    sheet.setFrozenRows(1);

    sheet.getRange(
      1,
      1,
      1,
      headers.length
    )
      .setFontWeight('bold')
      .setBackground('#102A43')
      .setFontColor('#FFFFFF');
  }

  return sheet;
}


function ARCHON_CODE_assertUnusedTransaction_(
  transactionId
) {
  const records = ARCHON_CODE_latestAudit_(500);

  const exists = records.some(function (row) {
    return String(row[1]) === String(transactionId) &&
      (
        row[3] === 'COMPLETED' ||
        row[3] === 'NO_CHANGE'
      );
  });

  if (exists) {
    throw new Error(
      `Transaction already completed: ${transactionId}`
    );
  }
}

