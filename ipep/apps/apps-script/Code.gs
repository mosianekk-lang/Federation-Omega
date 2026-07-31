/** EvidenceOps Drive orchestration scaffold. */
function createIpepJob(sourceFileId, workspaceFolderId) {
  const source = DriveApp.getFileById(sourceFileId);
  const workspace = DriveApp.getFolderById(workspaceFolderId);
  const job = {
    run_id: Utilities.getUuid(),
    source_file_id: sourceFileId,
    source_name: source.getName(),
    workspace_folder_id: workspaceFolderId,
    state: 'DISCOVERED',
    created_at: new Date().toISOString()
  };
  workspace.createFile('ipep-job-' + job.run_id + '.json', JSON.stringify(job, null, 2), MimeType.PLAIN_TEXT);
  return job;
}
