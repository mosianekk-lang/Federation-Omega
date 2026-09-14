/* ============================================================================
 * PROJECT CONTENT
 * ========================================================================== */

function ARCHON_CODE_getProjectContent_() {
  return ARCHON_CODE_apiRequest_(
    'get',
    `/projects/${encodeURIComponent(
      ScriptApp.getScriptId()
    )}/content`
  );
}


function ARCHON_CODE_updateProjectContent_(files) {
  return ARCHON_CODE_apiRequest_(
    'put',
    `/projects/${encodeURIComponent(
      ScriptApp.getScriptId()
    )}/content`,
    { files: files }
  );
}


function ARCHON_CODE_buildProposedContent_(
  current,
  request
) {
  const action = String(
    request.action || ''
  ).toUpperCase();

  let files = JSON.parse(
    JSON.stringify(current.files || [])
  );

  switch (action) {
    case 'UPSERT_FILE':
      ARCHON_CODE_validateIncomingFile_(
        request.file,
        request
      );

      files = files.filter(function (file) {
        return file.name !== request.file.name;
      });

      files.push({
        name: request.file.name,
        type: request.file.type || 'SERVER_JS',
        source: request.file.source
      });

      break;

    case 'DELETE_FILE':
      ARCHON_CODE_assertFileMutationAllowed_(
        request.fileName,
        request
      );

      files = files.filter(function (file) {
        return file.name !== request.fileName;
      });

      break;

    case 'REPLACE_PROJECT':
      if (!Array.isArray(request.files)) {
        throw new Error(
          'files array is required for REPLACE_PROJECT.'
        );
      }

      request.files.forEach(function (file) {
        ARCHON_CODE_validateIncomingFile_(
          file,
          request
        );
      });

      files = JSON.parse(JSON.stringify(request.files));
      break;

    default:
      throw new Error(
        `Unsupported code action: ${action}`
      );
  }

  return { files: ARCHON_CODE_sortFiles_(files) };
}


function ARCHON_CODE_validateIncomingFile_(
  file,
  request
) {
  if (!file || !file.name) {
    throw new Error('File name is required.');
  }

  if (
    !/^[A-Za-z0-9_.-]{1,120}$/.test(file.name)
  ) {
    throw new Error(
      `Invalid Apps Script file name: ${file.name}`
    );
  }

  ARCHON_CODE_assertFileMutationAllowed_(
    file.name,
    request
  );

  if (
    ARCHON_CODE.ALLOWED_TYPES.indexOf(
      file.type || 'SERVER_JS'
    ) === -1
  ) {
    throw new Error(
      `Unsupported file type: ${file.type}`
    );
  }

  if (typeof file.source !== 'string') {
    throw new Error('File source must be a string.');
  }

  if (
    file.source.length >
    ARCHON_CODE.MAX_SOURCE_LENGTH
  ) {
    throw new Error(
      `File exceeds maximum source length: ${file.name}`
    );
  }

  ARCHON_CODE_assertNoEmbeddedSecret_(file.source, file.name);
}


function ARCHON_CODE_assertFileMutationAllowed_(
  fileName,
  request
) {
  const protectedFile =
    ARCHON_CODE.PROTECTED_FILES.indexOf(fileName) !== -1;

  if (!protectedFile) {
    return;
  }

  const globallyAllowed =
    PropertiesService
      .getScriptProperties()
      .getProperty(
        ARCHON_CODE.PROPERTY.ALLOW_CORE_MUTATION
      ) === 'true';

  const requestAllowed =
    request.allowProtectedMutation === true;

  if (!(globallyAllowed && requestAllowed)) {
    throw new Error(
      `Protected file cannot be modified: ${fileName}`
    );
  }
}


function ARCHON_CODE_validateProject_(files) {
  const errors = [];
  const warnings = [];
  const names = {};

  if (!Array.isArray(files) || files.length === 0) {
    errors.push('Project cannot contain zero files.');
  }

  files.forEach(function (file) {
    if (!file.name) {
      errors.push('Project contains an unnamed file.');
    }

    if (names[file.name]) {
      errors.push(
        `Duplicate project file name: ${file.name}`
      );
    }

    names[file.name] = true;

    if (
      ARCHON_CODE.ALLOWED_TYPES.indexOf(file.type) === -1
    ) {
      errors.push(
        `Unsupported file type ${file.type} in ${file.name}.`
      );
    }

    if (typeof file.source !== 'string') {
      errors.push(
        `Missing source for ${file.name}.`
      );
    }

    if (
      file.source &&
      file.source.length >
        ARCHON_CODE.MAX_SOURCE_LENGTH
    ) {
      errors.push(
        `Source is too large for ${file.name}.`
      );
    }
  });

  if (!names.appsscript) {
    errors.push(
      'Project manifest appsscript.json is missing.'
    );
  }

  if (
    !names.ARCHON_Core
  ) {
    warnings.push(
      'ARCHON core is absent from the proposed project.'
    );
  }

  ARCHON_CODE.REQUIRED_FILES.forEach(function (requiredName) {
    if (!names[requiredName]) {
      errors.push(`Required protected file is missing: ${requiredName}`);
    }
  });

  const manifestFile = (files || []).find(function (file) {
    return file.name === 'appsscript';
  });
  if (manifestFile) {
    try {
      const manifest = JSON.parse(manifestFile.source || '{}');
      if (manifest.webapp) {
        errors.push('Private admin project must not expose a webapp entry point.');
      }
    } catch (error) {
      errors.push('Private admin manifest is invalid JSON.');
    }
  }

  const namespace = ARCHON_CODE_namespaceAudit_(files || []);
  Array.prototype.push.apply(errors, namespace.errors);
  Array.prototype.push.apply(warnings, namespace.warnings);

  return {
    passed: errors.length === 0,
    fileCount: files.length,
    errors: errors,
    warnings: warnings,
    namespace: namespace
  };
}

