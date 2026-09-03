/************************************************************
 * ARCHITRON MetaExecutor v2.1 â€” KIOAS A0/A1 Hardened Compatibility Core
 *
 * One-time install file for Apps Script.
 *
 * What this adds over v1:
 * - Sheet-based capability registry
 * - Policy/risk tiers
 * - Dry-run mode
 * - Pre-execution validation
 * - Project snapshot before file updates
 * - Rollback from snapshot
 * - Dependency checks
 * - Function discovery
 * - Failure logging
 * - Self-test suite
 * - Future module expansion through Sheets, not hardcoded edits only
 *
 * Queue Spreadsheet:
 * https://docs.google.com/spreadsheets/d/1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg/edit
 ************************************************************/

const META_V2 = {
  version: '2.1.0-kioas-hardening',
  queueSpreadsheetId: '1LSVjK9YK6u2CMrvetOcXpun4VQnOh5cE6b3w6z_KTHg',
  notifyEmail: 'mosianekk@gmail.com',

  sheets: {
    commands: 'Commands',
    files: 'Files',
    logs: 'Logs',
    config: 'Config',
    capabilities: 'Capabilities',
    snapshots: 'Snapshots',
    failures: 'Failures',
    policy: 'Policy',
    heartbeat: 'Heartbeat'
  },

  triggerHandler: 'processMetaExecutorQueueV2',

  legacyApprovalKeyName: 'META_EXECUTOR_APPROVAL_KEY',
  authorityMode: 'A0_A1_ONLY',

  risk: {
    LOW: 'LOW',
    MEDIUM: 'MEDIUM',
    HIGH: 'HIGH',
    CRITICAL: 'CRITICAL'
  },

  defaultAllowedFunctions: [
    'verifyArchitronConnectorOnly',
    'checkArchitronCloudStatus',
    'testFindSourceZip',
    'getLastArchitronCloudConnectorState'
  ],

  defaultAllowedFiles: [
    'CloudConnector.gs',
    'StatusExecutor.gs',
    'SourceRepair.gs',
    'Code.gs',
    'MetaExecutor.gs',
    'appsscript.json'
  ]
};

/************************************************************
 * INSTALL / RUNNERS
 ************************************************************/

function installMetaExecutorV2() {
  ensureMetaV2Sheets_();
  seedMetaV2Defaults_();
  // KIOAS hardening: this legacy compatibility core must not own recurrence.
  // GNS3 is the sole Federation scheduler; remove legacy MetaExecutor triggers and do not recreate them.
  deleteMetaV2Triggers_();
  logMetaV2_('INFO', 'INSTALL', 'MetaExecutor v2.1 hardened compatibility core installed without recurring trigger or email.', '');
  writeHeartbeat_('INSTALLED_NO_RECURRING_TRIGGER');
  return selfTestMetaExecutorV2();
}

function runMetaExecutorV2Now() {
  ensureMetaV2Sheets_();
  seedMetaV2Defaults_();
  return processMetaExecutorQueueV2();
}

function processMetaExecutorQueueV2() {
  ensureMetaV2Sheets_();
  seedMetaV2Defaults_();
  writeHeartbeat_('RUNNING');

  const ss = SpreadsheetApp.openById(META_V2.queueSpreadsheetId);
  const sheet = ss.getSheetByName(META_V2.sheets.commands);
  const values = sheet.getDataRange().getValues();

  if (values.length < 2) {
    writeHeartbeat_('NO_COMMANDS');
    return { status: 'NO_COMMANDS', checkedAt: new Date().toISOString() };
  }

  const headers = values[0].map(v => String(v || '').trim());
  const idx = headerIndex_(headers, commandHeaders_());
  const processed = [];

  for (let r = 1; r < values.length; r++) {
    const row = values[r];
    const status = String(row[idx.status] || '').trim().toUpperCase();
    if (status && status !== 'PENDING') continue;

    const command = readCommandRow_(row, idx);

    try {
      sheet.getRange(r + 1, idx.id + 1).setValue(command.id);
      sheet.getRange(r + 1, idx.status + 1).setValue('RUNNING');

      const validation = validateCommand_(command);
      if (!validation.ok) throw new Error(validation.error);

      let result;
      if (command.dryRun) {
        result = {
          status: 'DRY_RUN_OK',
          command: sanitizeCommandForResult_(command),
          validation: validation,
          checkedAt: new Date().toISOString()
        };
      } else {
        result = executeCommand_(command);
      }

      sheet.getRange(r + 1, idx.status + 1).setValue('DONE');
      sheet.getRange(r + 1, idx.resultJson + 1).setValue(JSON.stringify(result, null, 2));
      sheet.getRange(r + 1, idx.processedAt + 1).setValue(new Date().toISOString());
      sheet.getRange(r + 1, idx.error + 1).setValue('');

      logMetaV2_('INFO', command.action, JSON.stringify(result), command.id);
      processed.push({ id: command.id, action: command.action, status: 'DONE' });
    } catch (error) {
      const msg = String(error && error.message ? error.message : error);
      sheet.getRange(r + 1, idx.status + 1).setValue('ERROR');
      sheet.getRange(r + 1, idx.processedAt + 1).setValue(new Date().toISOString());
      sheet.getRange(r + 1, idx.error + 1).setValue(msg);

      logMetaV2_('ERROR', command.action || 'UNKNOWN', msg, command.id);
      logFailure_(command, msg);
      processed.push({ id: command.id, action: command.action, status: 'ERROR', error: msg });
    }
  }

  writeHeartbeat_('QUEUE_PROCESSED');
  return { status: 'QUEUE_PROCESSED', processed: processed, checkedAt: new Date().toISOString() };
}

/************************************************************
 * COMMAND EXECUTION ROUTER
 ************************************************************/

function executeCommand_(command) {
  switch (command.action) {
    case 'PING':
      return { status: 'PONG', version: META_V2.version, checkedAt: new Date().toISOString() };

    case 'SELF_TEST':
      return selfTestMetaExecutorV2();

    case 'RUN_FUNCTION':
      return runAllowedFunctionV2_(command.functionName, command.payload);

    case 'GET_PROJECT_CONTENT':
      return getAppsScriptProjectContentV2_(command.scriptId);

    case 'SNAPSHOT_PROJECT':
      return snapshotProjectV2_(command.scriptId, command.id, command.payload.reason || 'Manual snapshot');

    case 'UPSERT_SCRIPT_FILE':
    case 'INSTALL_MODULE':
      return upsertAppsScriptFileV2_(command.scriptId, command.payload.fileName, command.payload.source, command.payload.type || 'SERVER_JS', command.id);

    case 'ROLLBACK_PROJECT':
      return rollbackProjectV2_(command.scriptId, command.payload.snapshotId);

    case 'DISCOVER_FUNCTIONS':
      return discoverFunctionsV2_(command.scriptId);

    case 'CHECK_DEPENDENCIES':
      return checkDependenciesV2_(command.scriptId, command.payload);

    case 'VERIFY_HEALTH':
      return verifyHealthV2_();

    case 'WRITE_LEDGER':
      return writeLedgerV2_(command.payload);

    case 'SEND_STATUS_EMAIL':
      return sendStatusEmailV2_(command.payload);

    default:
      throw new Error('Unsupported action: ' + command.action);
  }
}

function runAllowedFunctionV2_(functionName, payload) {
  if (!functionName) throw new Error('Missing functionName.');

  const capability = getCapabilityByName_(functionName);
  const allowedByRegistry = capability && capability.enabled === true && capability.type === 'FUNCTION';
  const allowedByDefault = META_V2.defaultAllowedFunctions.includes(functionName);

  if (!allowedByRegistry && !allowedByDefault) {
    throw new Error('Function not allowed by registry/default allowlist: ' + functionName);
  }

  const fn = globalThis[functionName];
  if (typeof fn !== 'function') {
    throw new Error('Function not found in this Apps Script project: ' + functionName);
  }

  return fn(payload || {});
}

/************************************************************
 * VALIDATION / POLICY
 ************************************************************/

function validateCommand_(command) {
  if (!command.action) return { ok: false, error: 'Missing action.' };
  if²È="251}XÔ¹Í¡••ÑÌ¹Ý•‰¡½½­Ì¤°™•‘•É…Ñ¥½¹]•‰¡½½­!•…‘•ÉÍXÕ| ¤¤ì(€•¹ÍÕÉ•!•…‘•É|¡•Ñ=ÉÉ•…Ñ•M¡••Ñ|¡ÍÌ°}-I91}XÔ¹Í¡••ÑÌ¹‘É½Áé½¹•Ì¤°™•‘•É…Ñ¥½¹É½Áé½¹•!•…‘•ÉÍXÕ| ¤¤ì(€•¹ÍÕÉ•!•…‘•É|¡•Ñ=ÉÉ•…Ñ•M¡••Ñ|¡ÍÌ°}-I91}XÔ¹Í¡••ÑÌ¹Í½ÕÉ•5…À¤°™•‘•É…Ñ¥½¹M½ÕÉ•5…Á!•…‘•ÉÍXÕ| ¤¤ì)ô()™Õ¹Ñ¥½¸Í••‘•‘•É…Ñ¥½¹-•É¹•±•™…Õ±ÑÍXÕ| ¤ì(€½¹ÍÐÍ¡••Ð€ôMÁÉ•…‘Í¡••ÑÁÀ¹½Á•¹	å%¡}-I91}XÔ¹ÅÕ•Õ•MÁÉ•…‘Í¡••Ñ%¤¹•ÑM¡••Ñ	å9…µ”¡}-I91}XÔ¹Í¡••ÑÌ¹Í½ÕÉ•Ì¤ì(€½¹ÍÐ‘•™…Õ±ÑÌ€ôl(€€€l‘É¥Ù”¹Í•…É œ°€==1}I%Y}MI œ°ÑÉÕ”°€œœ°€==1}9Q%Yœ°íô°€1=\œ°€M•…É É¥Ù”™¥±•Ìt°(€€€l‘É¥Ù”¹™¥±•Q•áÐœ°€==1}I%Y}%1}QaPœ°ÑÉÕ”°€œœ°€==1}9Q%Yœ°íô°€5%U4œ°€I•…É¥Ù”Ñ•áÐ™¥±”t°(€€€l‘½Ì¹Ñ•áÐœ°€==1}=}QaPœ°ÑÉÕ”°€œœ°€==1}9Q%Yœ°íô°€5%U4œ°€I•…½½±”½ŒÑ•áÐt°(€€€lÍ¡••ÑÌ¹É…¹”œ°€==1}M!Q}I9œ°ÑÉÕ”°€œœ°€==1}9Q%Yœ°íô°€5%U4œ°€I•…M¡••ÐÉ…¹”t°(€€€lµ…¥°¹Í•…É œ°€5%1}MI œ°ÑÉÕ”°€œœ°€==1}9Q%Yœ°íô°€5%U4œ°€M•…É µ…¥°t°(€€€lµ…¥°¹Ñ¡É•…œ°€5%1}Q!Iœ°ÑÉÕ”°€œœ°€==1}9Q%Yœ°íô°€!% œ°€I•…µ…¥°Ñ¡É•…t°(€€€l…±•¹‘…È¹Í•…É œ°€==1}19I}MI œ°ÑÉÕ”°€œœ°€==1}9Q%Yœ°íô°€5%U4œ°€M•…É ½½±”…±•¹‘…Èt°(€€€l¡ÑÑÀ¹©Í½¸œ°€!QQA})M=8œ°ÑÉÕ”°€œœ°€9=9}=I}	IHœ°íô°€5%U4œ°€•Ñ )M=8t°(€€€l¡ÑÑÀ¹Ñ•áÐœ°€!QQA}QaPœ°ÑÉÕ”°€œœ°€9=9}=I}	IHœ°íô°€5%U4œ°€•Ñ Ñ•áÐt°(€€€lÝ•‰¡½½¬¹•¹•É¥Œœ°€]	!==-}A=MPœ°ÑÉÕ”°€œœ°€	II}=I}MIPœ°íô°€!% œ°€…±°Ý•‰¡½½¬t°(€€€l½¹¹•Ñ½È¹ÁÉ½áäœ°€=99Q=I}AI=adœ°ÑÉÕ”°€œœ°€	II}=I}MIPœ°íô°€!% œ°€I½ÕÑ”•áÑ•É¹…°½¹¹•Ñ½ÈÑ¡É½Õ ÁÉ½áät°(€€€l‘É½Áé½¹”¹‘É¥Ù”œ°€I%Y}I=Ai=9œ°ÑÉÕ”°€œœ°€==1}9Q%Yœ°íô°€1=\œ°€I•…É¥Ù”‘É½Áé½¹”t(€tì(€‘•™…Õ±ÑÌ¹™½É… ¡È€ôøÕÁÍ•ÉÑ•‘•É…Ñ¥½¹I½ÝXÕ|¡Í¡••Ð°™•‘•É…Ñ¥½¹M½ÕÉ•!•…‘•ÉÍXÕ| ¤°ÉlÁt°mÉlÁt°ÉlÅt°MÑÉ¥¹œ¡ÉlÉt¤¹Ñ½UÁÁ•É…Í” ¤°ÉlÍt°ÉlÑt°)M=8¹ÍÑÉ¥¹¥™ä¡ÉlÕt¤°ÉlÙt°ÉlÝt°¹•Ü…Ñ” ¤¹Ñ½%M=MÑÉ¥¹œ ¥t¤¤ì)ô()™Õ¹Ñ¥½¸¹½Éµ…±¥é••‘•É…Ñ¥½¹I•ÅÕ•ÍÑXÕ|¡Á…å±½…¤ì(€É•ÑÕÉ¸ì(€€€É•ÅÕ•ÍÑ%èÁ…å±½…¹É•ÅÕ•ÍÑ%ñð€ ´œ€¬¹•Ü…Ñ” ¤¹Ñ½%M=MÑÉ¥¹œ ¤¹É•Á±…” ½lè¹t½œ°€œ´œ¤€¬€œ´œ€¬UÑ¥±¥Ñ¥•Ì¹•ÑUÕ¥ ¤¤°(€€€Í½ÕÉ•9…µ”èÁ…å±½…¹Í½ÕÉ•9…µ”ñð€œœ°(€€€Í½ÕÉ•QåÁ”èÁ…å±½…¹Í½ÕÉ•QåÁ”ñð€œœ°(€€€Á…É…µÌèÁ…å±½…¹Á…É…µÌñðíô°(€€€…ÁÁÉ½Ù…±-•äèÁ…å±½…¹…ÁÁÉ½Ù…±-•äñð€œœ(€ôì)ô()™Õ¹Ñ¥½¸•Ñ•‘•É…Ñ¥½¹M½ÕÉ•XÕ|¡Í½ÕÉ•9…µ”°Í½ÕÉ•QåÁ”¤ì(€½¹ÍÐÉ½ÝÌ€ô•Ñ•‘•É…Ñ¥½¹M¡••Ñ=‰©•ÑÍXÕ|¡}-I91}XÔ¹Í¡••ÑÌ¹Í½ÕÉ•Ì°™•‘•É…Ñ¥½¹M½ÕÉ•!•…‘•ÉÍXÕ| ¤¤ì(€½¹ÍÐÉ½Ü€ôÉ½ÝÌ¹™¥¹¡È€ôøMÑÉ¥¹œ¡È¹¹…µ”¤¹ÑÉ¥´ ¤€ôôôÍ½ÕÉ•9…µ”¤ñðÉ½ÝÌ¹™¥¹¡È€ôøMÑÉ¥¹œ¡È¹ÑåÁ”¤¹ÑÉ¥´ ¤€ôôôÍ½ÕÉ•QåÁ”¤ì(€¥˜€ …É½Ü¤Ñ¡É½Ü¹•ÜÉÉ½È •‘•É…Ñ¥½¸Í½ÕÉ”¹½ÐÉ•¥ÍÑ•É•è€œ€¬€¡Í½ÕÉ•9…µ”ñðÍ½ÕÉ•QåÁ”¤¤ì(€É•ÑÕÉ¸ì(€€€¹…µ”èMÑÉ¥¹œ¡É½Ü¹¹…µ”ñð€œœ¤°(€€€ÑåÁ”èMÑÉ¥¹œ¡É½Ü¹ÑåÁ”ñð€œœ¤°(€€€•¹…‰±•èMÑÉ¥¹œ¡É½Ü¹•¹…‰±•¤¹Ñ½UÁÁ•É…Í” ¤€ôôô€QIUœ°(€€€‰…Í•UÉ°èMÑÉ¥¹œ¡É½Ü¹‰…Í•UÉ°ñð€œœ¤°(€€€…ÕÑ¡5½‘”èMÑÉ¥¹œ¡É½Ü¹…ÕÑ¡5½‘”ñð€9=9œ¤°(€€€½¹™¥œèÍ…™•)Í½¹A…ÉÍ•]¥Ñ¡•™…Õ±Ñ|¡MÑÉ¥¹œ¡É½Ü¹½¹™¥)Í½¸ñð€íôœ¤°íô¤°(€€€É¥Í¬èMÑÉ¥¹œ¡É½Ü¹É¥Í¬ñð€5%U4œ¤°(€€€¹½Ñ•ÌèMÑÉ¥¹œ¡É½Ü¹¹½Ñ•Ìñð€œœ¤(€ôì)ô()™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹ÕÑ¡!•…‘•ÉÍXÕ|¡Í½ÕÉ”°É•Ä¤ì(€½¹ÍÐ¡•…‘•ÉÌ€ôì•ÁÐè€…ÁÁ±¥…Ñ¥½¸½©Í½¸±Ñ•áÐ½Á±…¥¸°¨¼¨œôì(€½¹ÍÐÑ½­•¸€ôÉ•Ä¹Á…É…µÌ¹‰•…É•ÉQ½­•¸ñðÍ½ÕÉ”¹½¹™¥œ¹‰•…É•ÉQ½­•¸ñð€œœì(€½¹ÍÐÍ•É•Ð€ôÉ•Ä¹Á…É…µÌ¹Í¡…É•‘M•É•ÐñðÍ½ÕÉ”¹½¹™¥œ¹Í¡…É•‘M•É•Ðñð€œœì(€¥˜€¡Ñ½­•¸¤¡•…‘•ÉÌ¹ÕÑ¡½É¥é…Ñ¥½¸€ô€	•…É•È€œ€¬Ñ½­•¸ì(€¥˜€¡Í•É•Ð¤¡•…‘•ÉÍl`µI!%QI=8µMIPt€ôÍ•É•Ðì(€É•ÑÕÉ¸¡•…‘•ÉÌì)ô()™Õ¹Ñ¥½¸‰Õ¥±‘•‘•É…Ñ¥½¹UÉ±XÕ|¡‰…Í”°ÅÕ•ÉåA…É…µÌ¤ì(€¥˜€ …‰…Í”¤É•ÑÕÉ¸€œœì(€½¹ÍÐÅÌ€ô=‰©•Ð¹­•åÌ¡ÅÕ•ÉåA…É…µÌñðíô¤¹µ…À¡¬€ôø•¹½‘•UI%½µÁ½¹•¹Ð¡¬¤€¬€œôœ€¬•¹½‘•UI%½µÁ½¹•¹Ð¡ÅÕ•ÉåA…É…µÍm­t¤¤¹©½¥¸ œ˜œ¤ì(€É•ÑÕÉ¸ÅÌ€ü‰…Í”€¬€¡‰…Í”¹¥¹‘•á=˜ œüœ¤€øô€À€ü€œ˜œ€è€œüœ¤€¬ÅÌ€è‰…Í”ì)ô()™Õ¹Ñ¥½¸ÝÉ¥Ñ••‘•É…Ñ¥½¹M½ÕÉ•I•ÍÕ±ÑXÕ|¡É•½É¤ì(€½¹ÍÐÍ¡••Ð€ôMÁÉ•…‘Í¡••ÑÁÀ¹½Á•¹	å%¡}-I91}XÔ¹ÅÕ•Õ•MÁÉ•…‘Í¡••Ñ%¤¹•ÑM¡••Ñ	å9…µ”¡}-I91}XÔ¹Í¡••ÑÌ¹Í½ÕÉ•I•ÍÕ±ÑÌ¤ì(€•¹ÍÕÉ•!•…‘•É|¡Í¡••Ð°™•‘•É…Ñ¥½¹I•ÍÕ±Ñ!•…‘•ÉÍXÕ| ¤¤ì(€Í¡••Ð¹…ÁÁ•¹‘I½Ü¡mÉ•½É¹É•ÅÕ•ÍÑ%°É•½É¹™¥¹¥Í¡•‘Ð°É•½É¹Í½ÕÉ•9…µ”°É•½É¹Í½ÕÉ•QåÁ”°É•½É¹ÍÑ…ÑÕÌ°)M=8¹ÍÑÉ¥¹¥™ä¡É•½É¹É•ÍÕ±Ð¤¹Í±¥” À°€ÐÔÀÀÀ¥t¤ì)ô()™Õ¹Ñ¥½¸ÝÉ¥Ñ••‘•É…Ñ¥½¹M½ÕÉ•…¥±ÕÉ•XÕ|¡™…¥±ÕÉ”¤ì(€½¹ÍÐÍ¡••Ð€ôMÁÉ•…‘Í¡••ÑÁÀ¹½Á•¹	å%¡}-I91}XÔ¹ÅÕ•Õ•MÁÉ•…‘Í¡••Ñ%¤¹•ÑM¡••Ñ	å9…µ”¡}-I91}XÔ¹Í¡••ÑÌ¹Í½ÕÉ•…¥±ÕÉ•Ì¤ì(€•¹ÍÕÉ•!•…‘•É|¡Í¡••Ð°™•‘•É…Ñ¥½¹…¥±ÕÉ•!•…‘•ÉÍXÕ| ¤¤ì(€Í¡••Ð¹…ÁÁ•¹‘I½Ü¡m™…¥±ÕÉ”¹É•ÅÕ•ÍÑ%°™…¥±ÕÉ”¹™…¥±•‘Ð°™…¥±ÕÉ”¹Í½ÕÉ•9…µ”°™…¥±ÕÉ”¹Í½ÕÉ•QåÁ”°™…¥±ÕÉ”¹•ÉÉ½Ét¤ì)ô()™Õ¹Ñ¥½¸±½•‘•É…Ñ¥½¹M½ÕÉ•IÕ¹XÕ|¡•Ù•¹Ð°ÍÑ…ÑÕÌ°‘•Ñ…¥±Ì¤ì(€½¹ÍÐÍ¡••Ð€ôMÁÉ•…‘Í¡••ÑÁÀ¹½Á•¹	å%¡}-I91}XÔ¹ÅÕ•Õ•MÁÉ•…‘Í¡••Ñ%¤¹•ÑM¡••Ñ	å9…µ”¡}-I91}XÔ¹Í¡••ÑÌ¹Í½ÕÉ•IÕ¹Ì¤ì(€•¹ÍÕÉ•!•…‘•É|¡Í¡••Ð°™•‘•É…Ñ¥½¹IÕ¹!•…‘•ÉÍXÕ| ¤¤ì(€Í¡••Ð¹…ÁÁ•¹‘I½Ü¡m¹•Ü…Ñ” ¤¹Ñ½%M=MÑÉ¥¹œ ¤°•Ù•¹Ð°ÍÑ…ÑÕÌ°)M=8¹ÍÑÉ¥¹¥™ä¡‘•Ñ…¥±Ì¤¹Í±¥” À°€ÐÔÀÀÀ¥t¤ì)ô()™Õ¹Ñ¥½¸•Ñ•‘•É…Ñ¥½¹M¡••Ñ=‰©•ÑÍXÕ|¡Í¡••Ñ9…µ”°¡•…‘•ÉÌ¤ì(€½¹ÍÐÍÌ€ôMÁÉ•…‘Í¡••ÑÁÀ¹½Á•¹	å%¡}-I91}XÔ¹ÅÕ•Õ•MÁÉ•…‘Í¡••Ñ%¤ì(€½¹ÍÐÍ¡••Ð€ô•Ñ=ÉÉ•…Ñ•M¡••Ñ|¡ÍÌ°Í¡••Ñ9…µ”¤ì(€•¹ÍÕÉ•!•…‘•É|¡Í¡••Ð°¡•…‘•ÉÌ¤ì(€½¹ÍÐÙ…±Õ•Ì€ôÍ¡••Ð¹•Ñ…Ñ…I…¹” ¤¹•ÑY…±Õ•Ì ¤ì(€¥˜€¡Ù…±Õ•Ì¹±•¹Ñ €ð€È¤É•ÑÕÉ¸mtì(€½¹ÍÐ €ôÙ…±Õ•ÍlÁt¹µ…À¡Ø€ôøMÑÉ¥¹œ¡Øñð€œœ¤¹ÑÉ¥´ ¤¤ì(€É•ÑÕÉ¸Ù…±Õ•Ì¹Í±¥” Ä¤¹™¥±Ñ•È¡É½Ü€ôøÉ½Ü¹©½¥¸ œœ¤¹ÑÉ¥´ ¤¤¹µ…À¡É½Ü€ôøì(€€€½¹ÍÐ½‰¨€ôíôì(€€€ ¹™½É…  ¡¹…µ”°¤¤€ôø½‰©m¹…µ•t€ôÉ½Ým¥t¤ì(€€€É•ÑÕÉ¸½‰¨ì(€ô¤ì)ô()™Õ¹Ñ¥½¸ÕÁÍ•ÉÑ•‘•É…Ñ¥½¹I½ÝXÕ|¡Í¡••Ð°¡•…‘•ÉÌ°­•ä°É½ÝY…±Õ•Ì¤ì(€•¹ÍÕÉ•!•…‘•É|¡Í¡••Ð°¡•…‘•ÉÌ¤ì(€½¹ÍÐ±…ÍÐ€ôÍ¡••Ð¹•Ñ1…ÍÑI½Ü ¤ì(€¥˜€¡±…ÍÐ€øô€È¤ì(€€€½¹ÍÐ­•åÌ€ôÍ¡••Ð¹•ÑI…¹” È°€Ä°±…ÍÐ€´€Ä°€Ä¤¹•ÑY…±Õ•Ì ¤ì(€€€™½È€¡±•Ð¤€ô€Àì¤€ð­•åÌ¹±•¹Ñ ì¤¬¬¤ì(€€€€€¥˜€¡MÑÉ¥¹œ¡­•åÍm¥ulÁt¤¹ÑÉ¥´ ¤€ôôôMÑÉ¥¹œ¡­•ä¤¹ÑÉ¥´ ¤¤ì(€€€€€€€Í¡••Ð¹•ÑI…¹”¡¤€¬€È°€Ä°€Ä°É½ÝY…±Õ•Ì¹±•¹Ñ ¤¹Í•ÑY…±Õ•Ì¡mÉ½ÝY…±Õ•Ít¤ì(€€€€€€€É•ÑÕÉ¸ì(€€€€€ô(€€€ô(€ô(€Í¡••Ð¹…ÁÁ•¹‘I½Ü¡É½ÝY…±Õ•Ì¤ì)ô()™Õ¹Ñ¥½¸…ÕÑ¡½É¥é•5•Ñ…á•ÕÑ½ÉM½Á•Ì ¤ì(€MÁÉ•…‘Í¡••ÑÁÀ¹½Á•¹	å% œÅ1MY©,åe,ÙÔÉ5ÉÙ•Ñ=aÁÕ¸ÑYE¹= ÕÙˆÍÜÙé}-Q!œœ¤ì(€É¥Ù•ÁÀ¹•ÑI½½Ñ½±‘•È ¤ì(€µ…¥±ÁÀ¹Í•…É  I!%QI=8œ°€À°€Ä¤ì(€…±•¹‘…ÉÁÀ¹•Ñ•™…Õ±Ñ…±•¹‘…È ¤ì(€UÉ±•Ñ¡ÁÀ¹™•Ñ  ¡ÑÑÁÌè¼½ÝÝÜ¹½½±•…Á¥Ì¹½´½‘¥Í½Ù•Éä½ØÄ½…Á¥Ìœ¤ì(€É•ÑÕÉ¸€UQ!=I%iQ%=9}=,œì)ô()™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹M½ÕÉ•!•…‘•ÉÍXÕ| ¤ìÉ•ÑÕÉ¸l¹…µ”œ°€ÑåÁ”œ°€•¹…‰±•œ°€‰…Í•UÉ°œ°€…ÕÑ¡5½‘”œ°€½¹™¥)Í½¸œ°€É¥Í¬œ°€¹½Ñ•Ìœ°€ÕÁ‘…Ñ•‘Ðtìô)™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹IÕ¹!•…‘•ÉÍXÕ| ¤ìÉ•ÑÕÉ¸l±½•‘Ðœ°€•Ù•¹Ðœ°€ÍÑ…ÑÕÌœ°€‘•Ñ…¥±Í)Í½¸tìô)™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹I•ÍÕ±Ñ!•…‘•ÉÍXÕ| ¤ìÉ•ÑÕÉ¸lÉ•ÅÕ•ÍÑ%œ°€™¥¹¥Í¡•‘Ðœ°€Í½ÕÉ•9…µ”œ°€Í½ÕÉ•QåÁ”œ°€ÍÑ…ÑÕÌœ°€É•ÍÕ±Ñ)Í½¸tìô)™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹…¥±ÕÉ•!•…‘•ÉÍXÕ| ¤ìÉ•ÑÕÉ¸lÉ•ÅÕ•ÍÑ%œ°€™…¥±•‘Ðœ°€Í½ÕÉ•9…µ”œ°€Í½ÕÉ•QåÁ”œ°€•ÉÉ½Ètìô)™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹½¹¹•Ñ½É!•…‘•ÉÍXÕ| ¤ìÉ•ÑÕÉ¸l½¹¹•Ñ½É9…µ”œ°€ÁÉ½áåUÉ°œ°€…ÕÑ¡5½‘”œ°€•¹…‰±•œ°€¹½Ñ•Ìtìô)™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹]•‰¡½½­!•…‘•ÉÍXÕ| ¤ìÉ•ÑÕÉ¸lÝ•‰¡½½­9…µ”œ°€ÕÉ°œ°€…ÕÑ¡5½‘”œ°€•¹…‰±•œ°€¹½Ñ•Ìtìô)™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹É½Áé½¹•!•…‘•ÉÍXÕ| ¤ìÉ•ÑÕÉ¸l™½±‘•É9…µ”œ°€ÁÕÉÁ½Í”œ°€•¹…‰±•œ°€¹½Ñ•Ìtìô)™Õ¹Ñ¥½¸™•‘•É…Ñ¥½¹M½ÕÉ•5…Á!•…‘•ÉÍXÕ| ¤ìÉ•ÑÕÉ¸lÍ½ÕÉ•9…µ”œ°€•¹Ñ¥ÑåQåÁ”œ°€…¹½¹¥…±UÍ”œ°€ÁÉ¥½É¥Ñäœ°€¹½Ñ•Ìtìô((¼¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨(€¨5…¹¥™•ÍÐ…‘‘¥Ñ¥½¹Ì™½ÈÑ¡¥ÌØÔ­•É¹•°è(€¨€´¡ÑÑÁÌè¼½ÝÝÜ¹½½±•…Á¥Ì¹½´½…ÕÑ ½‘É¥Ù”(€¨€´¡ÑÑÁÌè¼½ÝÝÜ¹½½±•…Á¥Ì¹½´½…ÕÑ ½‘½Õµ•¹ÑÌ(€¨€´¡ÑÑÁÌè¼½ÝÝÜ¹½½±•…Á¥Ì¹½´½…ÕÑ ½ÍÁÉ•…‘Í¡••ÑÌ(€¨€´¡ÑÑÁÌè¼½ÝÝÜ¹½½±•…Á¥Ì¹½´½…ÕÑ ½µ…¥°¹É•…‘½¹±ä(€¨€´¡ÑÑÁÌè¼½ÝÝÜ¹½½±•…Á¥Ì¹½´½…ÕÑ ½…±•¹‘…È¹É•…‘½¹±ä(€¨€´¡ÑÑÁÌè¼½ÝÝÜ¹½½±•…Á¥Ì¹½´½…ÕÑ ½ÍÉ¥ÁÐ¹•áÑ•É¹…±}É•ÅÕ•ÍÐ(€¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¨¼(