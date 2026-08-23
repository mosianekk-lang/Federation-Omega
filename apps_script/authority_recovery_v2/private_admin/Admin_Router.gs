/**
 * Private owner/admin dispatch only. This project has no public doGet/doPost.
 * Invocation must use a separately authenticated Apps Script API execution
 * route bound to the canonical standard Cloud project.
 */
function SOVARA_ADMIN_dispatch(request) {
  if (!request || typeof request !== 'object' || Array.isArray(request)) {
    throw new Error('ADMIN_REQUEST_REQUIRED');
  }
  const action = String(request.action || '').trim().toUpperCase();
  switch (action) {
    case 'LINEAGE_STATUS':
      ARCHON_CODE_verifySignedRequest_(ARCHON_CODE_getParameters_(request));
      return SOVARA_ADMIN_lineageStatus();
    case 'CODE_STATUS':
      ARCHON_CODE_verifySignedRequest_(ARCHON_CODE_getParameters_(request));
      return SOVARA_ARCHON_codeStatus(request);
    case 'CODE_DRY_RUN':
      return SOVARA_ARCHON_codeDryRun(request);
    case 'CODE_APPLY':
      return SOVARA_ARCHON_codeApply(request);
    case 'CODE_ROLLBACK':
      return SOVARA_ARCHON_codeRollback(request);
    default:
      throw new Error('ADMIN_ACTION_NOT_ALLOWLISTED');
  }
}
