/** Retained ARCHON v2 — versions, deployments, backups and Apps Script API. */
/* ============================================================================
 * VERSION AND DEPLOYMENT MANAGEMENT
 * ========================================================================== */

function ARCHON_CODE_createVersion_(description) {
  return ARCHON_CODE_apiRequest_(
    'post',
    `/projects/${encodeURIComponent(
      ScriptApp.getScriptId()
    )}/versions`,
    {
      description:
        description ||
        `ARCHON release ${new Date().toISOString()}`
    }
  );
}


function ARCHON_CODE_listDeployments_() {
  const response = ARCHON_CODE_apiRequest_(
    'get',
    `/projects/${encodeURIComponent(
      ScriptApp.getScriptId()
    )}/deployments`
  );

  return response.deployments || [];
}


function ARCHON_CODE_promoteDeployment_(
  versionNumber,
  suppliedDeploymentId,
  description
) {
  const properties =
    PropertiesService.getScriptProperties();

  const deploymentId =
    suppliedDeploymentId ||
    properties.getProperty(
      ARCHON_CODE.PROPERTY.DEPLOYMENT_ID
    );

  if (!deploymentId) {
    throw new Error(
      'No deployment ID supplied or configured.'
    );
  }

  const response = ARCHON_CODE_apiRequest_(
    'put',
    `/projects/${encodeURIComponent(
      ScriptApp.getScriptId()
    )}/deployments/${encodeURIComponent(
      deploymentId
    )}`,
    {
      deploymentConfig: {
        scriptId: ScriptApp.getScriptId(),
        versionNumber: Number(versionNumber),
        manifestFileName: 'appsscript',
        description:
          description ||
          `ARCHON deployment ${versionNumber}`
      }
    }
  );

  properties.setProperty(
    ARCHON_CODE.PROPERTY.DEPLOYMENT_ID,
    deploymentId
  );

  return response;
}


/* ============================================================================
 * BACKUP AND ROLLBACK
 * ========================================================================== */

function ARCHON_CODE_createBackup_(
  project,
  transactionId,
  reason
) {
  const folderId = PropertiesService
    .getScriptProperties()
    .getProperty(
      ARCHON_CODE.PROPERTY.BACKUP_FOLDER_ID
    );

  if (!folderId) {
    throw new Error(
      'ARCHON_CODE_BACKUP_FOLDER_ID is not configured.'
    );
  }

  const folder = DriveApp.getFolderById(folderId);

  const backup = {
    schema: 'ARCHON_CODE_BACKUP_V1',
    scriptId: ScriptApp.getScriptId(),
    transactionId: transactionId,
    reason: reason,
    createdAt: new Date().toISOString(),
    projectHash:
      ARCHON_CODE_projectHash_(project.files),
    project: project
  };

  const name = [
    'ARCHON_CODE_BACKUP',
    transactionId,
    Date.now()
  ].join('_') + '.json';

  const file = folder.createFile(
    name,
    JSON.stringify(backup, null, 2),
    MimeType.PLAIN_TEXT
  );

  return {
    fileId: file.getId(),
    fileName: file.getName(),
    createdAt: backup.createdAt,
    projectHash: backup.projectHash
  };
}


function ARCHON_CODE_restoreBackupByFileId_(
  backupFileId
) {
  const file = DriveApp.getFileById(backupFileId);
  const backup = JSON.parse(
    file.getBlob().getDataAsString('UTF-8')
  );

  if (
    backup.schema !== 'ARCHON_CODE_BACKUP_V1'
  ) {
    throw new Error(
      'Unsupported ARCHON backup schema.'
    );
  }

  if (
    backup.scriptId !== ScriptApp.getScriptId()
  ) {
    throw new Error(
      'Backup belongs to a different script project.'
    );
  }

  const validation = ARCHON_CODE_validateProject_(
    backup.project.files
  );

  if (!validation.passed) {
    throw new Error(
      'Backup validation failed: ' +
      JSON.stringify(validation.errors)
    );
  }

  ARCHON_CODE_updateProjectContent_(
    backup.project.files
  );

  const readback = ARCHON_CODE_getProjectContent_();
  const restoredHash =
    ARCHON_CODE_projectHash_(readback.files);

  if (restoredHash !== backup.projectHash) {
    throw new Error(
      'Rollback readback hash mismatch.'
    );
  }

  return {
    status: 'RESTORED',
    backupFileId: backupFileId,
    restoredHash: restoredHash,
    verificationPassed: true
  };
}


/* ============================================================================
 * APPS SCRIPT API CLIENT
 * ========================================================================== */

function ARCHON_CODE_apiRequest_(
  method,
  path,
  body
) {
  const options = {
    method: method,
    headers: {
      Authorization:
        'Bearer ' + ScriptApp.getOAuthToken()
    },
    muteHttpExceptions: true
  };

  if (typeof body !== 'undefined') {
    options.contentType = 'application/json';
    options.payload = JSON.stringify(body);
  }

  const response = UrlFetchApp.fetch(
    ARCHON_CODE.API_ROOT + path,
    options
  );

  const status = response.getResponseCode();
  const text = response.getContentText();

  let parsed;

  try {
    parsed = text ? JSON.parse(text) : {};
  } catch (error) {
    parsed = {
      unparsedResponse: text
    };
  }

  if (status < 200 || status >= 300) {
    throw new Error(
      JSON.stringify({
        code: 'APPS_SCRIPT_API_ERROR',
        httpStatus: status,
        response: parsed
      })
    );
  }

  return parsed;
}


