/**
 * RETAINED / NAMESPACED ARCHON CODE MANAGER
 * Source lineage: supplied FO_GAS fleet backup.
 * Changes: unique public names, durable nonce claim, externally anchored
 * provider/effect admission for apply/rollback, disabled test signer default.
 * The original backup remains the rollback evidence anchor.
 */

/**
 * ============================================================================
 * ARCHON AUTONOMOUS CODE MANAGER
 * Version: 2.0.0
 *
 * Provides:
 * - Readback of the complete Apps Script project
 * - Safe file creation and replacement
 * - Project-wide backups
 * - SHA-256 integrity records
 * - HMAC-authenticated update requests
 * - Dry-run previews
 * - Immutable Apps Script version creation
 * - Existing deployment promotion
 * - Automatic rollback after failed verification
 * - Durable update and audit ledgers
 *
 * SECURITY MODEL
 * - Updates require an HMAC signature.
 * - Protected files cannot be changed unless explicitly allowed.
 * - Existing project files are fetched and merged before updateContent.
 * - Every update receives a backup and transaction ID.
 *
 * REQUIRED SCRIPT PROPERTIES
 * - ARCHON_CODE_UPDATE_SECRET
 * - ARCHON_CODE_BACKUP_FOLDER_ID
 * - ARCHON_AUDIT_SPREADSHEET_ID
 * - ARCHON_DEPLOYMENT_ID              optional
 * - ARCHON_ALLOW_CORE_MUTATION         optional; default false
 *
 * REQUIRED API
 * - Google Apps Script API enabled for the project's Google Cloud project.
 * ============================================================================
 */

const ARCHON_CODE = Object.freeze({
  VERSION: '2.0.0',

  API_ROOT: 'https://script.googleapis.com/v1',

  PROPERTY: Object.freeze({
    SECRET: 'ARCHON_CODE_UPDATE_SECRET',
    BACKUP_FOLDER_ID: 'ARCHON_CODE_BACKUP_FOLDER_ID',
    AUDIT_SPREADSHEET_ID: 'ARCHON_AUDIT_SPREADSHEET_ID',
    DEPLOYMENT_ID: 'ARCHON_DEPLOYMENT_ID',
    ALLOW_CORE_MUTATION: 'ARCHON_ALLOW_CORE_MUTATION'
  }),

  SHEET: Object.freeze({
    AUDIT: 'ARCHON_CODE_AUDIT',
    RELEASES: 'ARCHON_CODE_RELEASES'
  }),

  PROTECTED_FILES: Object.freeze([
    'appsscript',
    'Admin_Router',
    'Admin_Security',
    'Project_Lineage',
    'ARCHON_Core',
    'ARCHON_Project_Content',
    'ARCHON_Version_Backup_API',
    'ARCHON_Integrity_Audit',
    'ARCHON_Execution'
  ]),

  REQUIRED_FILES: Object.freeze([
    'appsscript',
    'Admin_Router',
    'Admin_Security',
    'Project_Lineage',
    'ARCHON_Core',
    'ARCHON_Project_Content',
    'ARCHON_Version_Backup_API',
    'ARCHON_Integrity_Audit',
    'ARCHON_Execution'
  ]),

  ALLOWED_TYPES: Object.freeze([
    'SERVER_JS',
    'HTML',
    'JSON'
  ]),

  MAX_SOURCE_LENGTH: 500000,

  LOCK_TIMEOUT_MS: 30000
});


/* ============================================================================
 * PUBLIC COMMAND HANDLERS
 * Register these functions in the current Sovereign Federation router.
 * ========================================================================== */

/**
 * Returns project metadata, files, hashes, deployments, and latest releases.
 */
function SOVARA_ARCHON_codeStatus(context) {
  return ARCHON_CODE_execute_('code_status', context || {}, function () {
    const project = ARCHON_CODE_getProjectContent_();
    const deployments = ARCHON_CODE_listDeployments_();

    return {
      serviceVersion: ARCHON_CODE.VERSION,
      scriptId: ScriptApp.getScriptId(),
      fileCount: project.files.length,
      projectHash: ARCHON_CODE_projectHash_(project.files),
      files: project.files.map(ARCHON_CODE_fileSummary_),
      deployments: deployments,
      latestAuditRecords: ARCHON_CODE_latestAudit_(20),
      verification: {
        projectReadable: true,
        projectHashCreated: true,
        deploymentListReadable: true
      }
    };
  });
}


/**
 * Performs a dry-run without changing project source.
 *
 * context.parameters:
 * {
 *   transactionId: "...",
 *   timestamp: "...",
 *   nonce: "...",
 *   action: "UPSERT_FILE",
 *   file: {
 *     name: "ARCHON_New_Module",
 *     type: "SERVER_JS",
 *     source: "function example() {}"
 *   },
 *   signature: "hex-hmac"
 * }
 */
function SOVARA_ARCHON_codeDryRun(context) {
  return ARCHON_CODE_execute_('code_dry_run', context || {}, function () {
    const request = ARCHON_CODE_getParameters_(context);

    ARCHON_CODE_verifySignedRequest_(request);

    const current = ARCHON_CODE_getProjectContent_();
    const proposed = ARCHON_CODE_buildProposedContent_(current, request);

    const beforeHash = ARCHON_CODE_projectHash_(current.files);
    const afterHash = ARCHON_CODE_projectHash_(proposed.files);
    return {
      dryRun: true,
      transactionId: request.transactionId,
      action: request.action,
      requestSha256: SOVARA_ADMIN_mutationIntentSha256_(request),
      beforeHash: beforeHash,
      afterHash: afterHash,
      changes: ARCHON_CODE_diffFiles_(current.files, proposed.files),
      verification: ARCHON_CODE_validateProject_(proposed.files),
      truthBoundary: 'DRY_RUN_NO_PROVIDER_MUTATION_NO_PERMIT_CONSUMPTION'
    };
  });
}


/**
 * Applies a signed source update and optionally promotes the deployment.
 *
 * Supported actions:
 * - UPSERT_FILE
 * - DELETE_FILE
 * - REPLACE_PROJECT
 * Rollback is exposed only through CODE_ROLLBACK.
 */
function SOVARA_ARCHON_codeApply(context) {
  return ARCHON_CODE_execute_('code_apply', context || {}, function () {
    const request = ARCHON_CODE_getParameters_(context);

    ARCHON_CODE_verifySignedRequest_(request);
    const admission = SOVARA_ADMIN_assertProviderMutationPermit_(
      request,
      'CODE_APPLY'
    );

    const lock = LockService.getScriptLock();
    lock.waitLock(ARCHON_CODE.LOCK_TIMEOUT_MS);

    let backup = null;
    let permitConsumed = false;
    let deploymentBefore = null;
    let sourceUpdateSubmitted = false;

    try {
      ARCHON_CODE_assertUnusedTransaction_(request.transactionId);

      const current = ARCHON_CODE_getProjectContent_();
      const beforeHash = ARCHON_CODE_projectHash_(current.files);
      if (beforeHash !== admission.expectedBeforeHash) {
        throw new Error(
          'Expected-before hash mismatch. ' +
          `Permit ${admission.expectedBeforeHash}; current ${beforeHash}.`
        );
      }

      const proposed = ARCHON_CODE_buildProposedContent_(current, request);
      const validation = ARCHON_CODE_validateProject_(proposed.files);
      if (!validation.passed) {
        throw new Error(
          'Project validation failed: ' + JSON.stringify(validation.errors)
        );
      }
      const proposedHash = ARCHON_CODE_projectHash_(proposed.files);
      if (proposedHash !== admission.expectedAfterHash) {
        throw new Error(
          'Expected-after hash mismatch. ' +
          `Permit ${admission.expectedAfterHash}; proposed ${proposedHash}.`
        );
      }

      if (beforeHash === proposedHash) {
        return {
          transactionId: request.transactionId,
          status: 'NO_CHANGE',
          requestSha256: admission.requestSha256,
          beforeHash: beforeHash,
          afterHash: proposedHash,
          backup: null,
          admission: admission,
          permitConsumed: false,
          changes: [],
          validation: validation,
          truthBoundary: 'NO_PROVIDER_MUTATION_NO_PERMIT_CONSUMPTION'
        };
      }

      SOVARA_ADMIN_claimEffectPermitUnderLock_(
        request.effectPermit,
        request.transactionId
      );
      permitConsumed = true;

      backup = ARCHON_CODE_createBackup_(
        current,
        request.transactionId,
        'PRE_UPDATE'
      );
      deploymentBefore = request.promoteDeployment === true
        ? ARCHON_CODE_captureDeploymentState_(request.deploymentId || null)
        : null;

      ARCHON_CODE_updateProjectContent_(proposed.files);
      sourceUpdateSubmitted = true;

      const readback = ARCHON_CODE_getProjectContent_();
      const afterHash = ARCHON_CODE_projectHash_(readback.files);
      if (afterHash !== proposedHash) {
        throw new Error(
          'Post-update project hash mismatch. ' +
          `Expected ${proposedHash}; received ${afterHash}.`
        );
      }

      const version = ARCHON_CODE_createVersion_(
        request.description || `ARCHON transaction ${request.transactionId}`
      );
      let deployment = null;
      let deploymentReadback = null;
      if (request.promoteDeployment === true) {
        deployment = ARCHON_CODE_promoteDeployment_(
          version.versionNumber,
          request.deploymentId || null,
          request.description || ''
        );
        deploymentReadback = ARCHON_CODE_verifyDeploymentReadback_(
          deployment.deploymentId || request.deploymentId || '',
          Number(version.versionNumber)
        );
      }

      const result = {
        transactionId: request.transactionId,
        status: 'COMPLETED',
        action: request.action,
        requestSha256: admission.requestSha256,
        beforeHash: beforeHash,
        proposedHash: proposedHash,
        afterHash: afterHash,
        backup: backup,
        admission: admission,
        permitConsumed: permitConsumed,
        version: version,
        deployment: deployment,
        deploymentReadback: deploymentReadback,
        changes: ARCHON_CODE_diffFiles_(current.files, readback.files),
        validation: validation,
        verification: {
          backupCreatedAndReadBack: Boolean(
            backup && backup.verificationPassed === true
          ),
          updateSubmitted: true,
          sourceReadbackCompleted: true,
          sourceHashMatched: afterHash === proposedHash,
          immutableVersionCreated: Boolean(version.versionNumber),
          deploymentPromoted: request.promoteDeployment === true
            ? Boolean(deployment)
            : null,
          deploymentConfigurationReadBack: request.promoteDeployment === true
            ? Boolean(deploymentReadback && deploymentReadback.verified)
            : null
        }
      };
      result.externalSemanticReadback =
        SOVARA_ADMIN_verifyExternalPostEffect_(request, result);

      ARCHON_CODE_writeAudit_('COMPLETED', request, result);
      ARCHON_CODE_writeRelease_(result);
      return result;

    } catch (error) {
      let rollback = null;
      let deploymentRollback = null;
      if (backup && sourceUpdateSubmitted) {
        try {
          rollback = ARCHON_CODE_restoreBackupByFileId_(backup.fileId, request);
        } catch (rollbackError) {
          rollback = {
            status: 'ROLLBACK_FAILED',
            error: ARCHON_CODE_error_(rollbackError)
          };
        }
      }
      if (deploymentBefore && deploymentBefore.deploymentId) {
        try {
          deploymentRollback = ARCHON_CODE_promoteDeployment_(
            deploymentBefore.versionNumber,
            deploymentBefore.deploymentId,
            'Automatic deployment rollback after failed transaction ' +
              String(request.transactionId || '')
          );
        } catch (deploymentRollbackError) {
          deploymentRollback = {
            status: 'DEPLOYMENT_ROLLBACK_FAILED',
            error: ARCHON_CODE_error_(deploymentRollbackError)
          };
        }
      }

      const failure = {
        transactionId: request.transactionId || '',
        status: 'FAILED',
        error: ARCHON_CODE_error_(error),
        admission: admission,
        permitConsumed: permitConsumed,
        backup: backup,
        rollback: rollback,
        deploymentRollback: deploymentRollback
      };
      ARCHON_CODE_writeAudit_('FAILED', request, failure);
      throw new Error(JSON.stringify(failure));

    } finally {
      lock.releaseLock();
    }
  });
}


/**
 * Restores a backup previously created by ARCHON.
 */
function SOVARA_ARCHON_codeRollback(context) {
  return ARCHON_CODE_execute_('code_rollback', context || {}, function () {
    const request = ARCHON_CODE_getParameters_(context);

    ARCHON_CODE_verifySignedRequest_(request);
    const admission = SOVARA_ADMIN_assertProviderMutationPermit_(
      request,
      'CODE_ROLLBACK'
    );
    if (!request.backupFileId) {
      throw new Error('backupFileId is required.');
    }

    const lock = LockService.getScriptLock();
    lock.waitLock(ARCHON_CODE.LOCK_TIMEOUT_MS);

    let safetyBackup = null;
    let permitConsumed = false;
    let deploymentBefore = null;
    try {
      ARCHON_CODE_assertUnusedTransaction_(request.transactionId);
      const current = ARCHON_CODE_getProjectContent_();
      const beforeHash = ARCHON_CODE_projectHash_(current.files);
      if (beforeHash !== admission.expectedBeforeHash) {
        throw new Error('Rollback expected-before hash mismatch.');
      }
      SOVARA_ADMIN_claimEffectPermitUnderLock_(
        request.effectPermit,
        request.transactionId
      );
      permitConsumed = true;

      safetyBackup = ARCHON_CODE_createBackup_(
        current,
        request.transactionId,
        'PRE_ROLLBACK'
      );
      deploymentBefore = request.promoteDeployment === true
        ? ARCHON_CODE_captureDeploymentState_(request.deploymentId || null)
        : null;

      const rollback = ARCHON_CODE_restoreBackupByFileId_(
        request.backupFileId,
        request
      );
      if (rollback.restoredHash !== admission.expectedAfterHash) {
        throw new Error('Rollback expected-after hash mismatch.');
      }
      const version = ARCHON_CODE_createVersion_(
        request.description || `ARCHON rollback ${request.transactionId}`
      );
      let deployment = null;
      let deploymentReadback = null;
      if (request.promoteDeployment === true) {
        deployment = ARCHON_CODE_promoteDeployment_(
          version.versionNumber,
          request.deploymentId || null,
          request.description || ''
        );
        deploymentReadback = ARCHON_CODE_verifyDeploymentReadback_(
          deployment.deploymentId || request.deploymentId || '',
          Number(version.versionNumber)
        );
      }

      const result = {
        transactionId: request.transactionId,
        status: 'ROLLED_BACK',
        requestSha256: admission.requestSha256,
        admission: admission,
        permitConsumed: permitConsumed,
        beforeHash: beforeHash,
        afterHash: rollback.restoredHash,
        safetyBackup: safetyBackup,
        rollback: rollback,
        version: version,
        deployment: deployment,
        deploymentReadback: deploymentReadback
      };
      result.externalSemanticReadback =
        SOVARA_ADMIN_verifyExternalPostEffect_(request, result);
      ARCHON_CODE_writeAudit_('ROLLED_BACK', request, result);
      ARCHON_CODE_writeRelease_(result);
      return result;

    } catch (error) {
      let recovery = null;
      let deploymentRecovery = null;
      if (safetyBackup) {
        try {
          recovery = ARCHON_CODE_restoreBackupByFileId_(safetyBackup.fileId, request);
        } catch (recoveryError) {
          recovery = {
            status: 'SAFETY_RECOVERY_FAILED',
            error: ARCHON_CODE_error_(recoveryError)
          };
        }
      }
      if (deploymentBefore && deploymentBefore.deploymentId) {
        try {
          deploymentRecovery = ARCHON_CODE_promoteDeployment_(
            deploymentBefore.versionNumber,
            deploymentBefore.deploymentId,
            'Automatic deployment recovery after failed rollback ' +
              String(request.transactionId || '')
          );
        } catch (deploymentRecoveryError) {
          deploymentRecovery = {
            status: 'DEPLOYMENT_RECOVERY_FAILED',
            error: ARCHON_CODE_error_(deploymentRecoveryError)
          };
        }
      }
      const failure = {
        transactionId: request.transactionId || '',
        status: 'ROLLBACK_FAILED',
        error: ARCHON_CODE_error_(error),
        admission: admission,
        permitConsumed: permitConsumed,
        safetyBackup: safetyBackup,
        recovery: recovery,
        deploymentRecovery: deploymentRecovery
      };
      ARCHON_CODE_writeAudit_('ROLLBACK_FAILED', request, failure);
      throw new Error(JSON.stringify(failure));

    } finally {
      lock.releaseLock();
    }
  });
}


/* ============================================================================
 * ROUTER ADAPTER
 * ========================================================================== */

/**
 * Add this map to the current command router.
 *
 * Example:
 *
 * const handler = ARCHON_CODE_COMMANDS[command];
 * if (handler) return handler(context);
 */
const ARCHON_CODE_COMMANDS = Object.freeze({
  code_status: SOVARA_ARCHON_codeStatus,
  code_dry_run: SOVARA_ARCHON_codeDryRun,
  code_apply: SOVARA_ARCHON_codeApply,
  code_rollback: SOVARA_ARCHON_codeRollback
});


/* ============================================================================
 * SIGNATURE AND REQUEST VALIDATION
 * ========================================================================== */

function ARCHON_CODE_verifySignedRequest_(request) {
  if (!request.transactionId) {
    throw new Error('transactionId is required.');
  }

  if (!request.timestamp) {
    throw new Error('timestamp is required.');
  }

  if (!request.nonce) {
    throw new Error('nonce is required.');
  }

  if (!request.signature) {
    throw new Error('signature is required.');
  }

  const timestamp = new Date(request.timestamp);

  if (isNaN(timestamp.getTime())) {
    throw new Error('Invalid timestamp.');
  }

  const ageMs = Date.now() - timestamp.getTime();

  if (
    ageMs > SOVARA_ADMIN_SECURITY.MAX_AGE_MS ||
    ageMs < -SOVARA_ADMIN_SECURITY.MAX_FUTURE_SKEW_MS
  ) {
    throw new Error('Signed request is stale or implausibly future-dated.');
  }

  ARCHON_CODE_assertNoSecretMaterial_(request);

  const unsigned = JSON.parse(JSON.stringify(request));
  delete unsigned.signature;

  const expected = ARCHON_CODE_signObject_(unsigned);

  if (!ARCHON_CODE_secureEqual_(
    expected,
    request.signature
  )) {
    throw new Error('Invalid update signature.');
  }

  SOVARA_ADMIN_claimNonce_(request.nonce, timestamp);
}


function ARCHON_CODE_signObject_(object) {
  const secret = PropertiesService
    .getScriptProperties()
    .getProperty(ARCHON_CODE.PROPERTY.SECRET);

  if (!secret || String(secret).length < 32) {
    throw new Error(
      'ARCHON_CODE_UPDATE_SECRET must be configured with 32+ characters.'
    );
  }

  const canonical = ARCHON_CODE_canonicalJson_(object);

  const signature = Utilities.computeHmacSha256Signature(
    canonical,
    secret,
    Utilities.Charset.UTF_8
  );

  return signature
    .map(function (byte) {
      const value = byte < 0 ? byte + 256 : byte;
      return value.toString(16).padStart(2, '0');
    })
    .join('');
}


function ARCHON_CODE_secureEqual_(left, right) {
  const a = String(left || '');
  const b = String(right || '');

  if (a.length !== b.length) {
    return false;
  }

  let difference = 0;

  for (let i = 0; i < a.length; i++) {
    difference |=
      a.charCodeAt(i) ^ b.charCodeAt(i);
  }

  return difference === 0;
}


function ARCHON_CODE_canonicalJson_(value) {
  if (
    value === null ||
    typeof value !== 'object'
  ) {
    return JSON.stringify(value);
  }

  if (Array.isArray(value)) {
    return '[' +
      value
        .map(ARCHON_CODE_canonicalJson_)
        .join(',') +
      ']';
  }

  const keys = Object.keys(value).sort();

  return '{' +
    keys.map(function (key) {
      return JSON.stringify(key) +
        ':' +
        ARCHON_CODE_canonicalJson_(value[key]);
    }).join(',') +
    '}';
}

