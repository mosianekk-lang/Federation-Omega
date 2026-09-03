// ===== 00_Config.gs =====
var KIOAS_GNEN = Object.freeze({
  SCHEMA: "kioas.google-native-execution-node.v1",
  VERSION: "1.0.0",
  NODE_CLASS: "THIN_GOOGLE_NATIVE_EXECUTION_NODE",
  LOGICAL_TIME_ZONE: "Africa/Johannesburg",
  PRODUCTION_EFFECT: false,
  MAX_QUEUE_BATCH: 5,
  MAX_RANGE_ROWS: 200,
  MAX_RANGE_COLS: 20,
  HEARTBEAT_MINUTES: 15,
  COMMAND_POLL_MINUTES: 5,
  COMMAND_TRIGGER_SINGLETON: "GNEN_processQueue",
  HEARTBEAT_TRIGGER_SINGLETON: "GNEN_heartbeat",
  PROPS: {
    OWNER_EMAIL: "KIOAS_GNEN_OWNER_EMAIL",
    CONTROL_PLANE_ID: "KIOAS_GNEN_CONTROL_PLANE_ID",
    NODE_ID: "KIOAS_GNEN_NODE_ID",
    ALLOWED_RESOURCE_IDS: "KIOAS_GNEN_ALLOWED_RESOURCE_IDS",
    BUILD_SHA: "KIOAS_GNEN_BUILD_SHA",
    INSTALLED_AT: "KIOAS_GNEN_INSTALLED_AT"
  },
  REQUIRED_SHEETS: [
    "CONTROL","COMMAND_QUEUE","COMMAND_RESULTS","PROOF_LEDGER","FAILURE_BOOK",
    "LEARNING_LEDGER","ROUTE_MEMORY","OBSERVABILITY","SECURITY_GATES",
    "ARTIFACT_REGISTRY","METRICS","SNAPSHOTS"
  ],
  SAFE_APPEND_SHEETS: [
    "PROOF_LEDGER","FAILURE_BOOK","LEARNING_LEDGER","ROUTE_MEMORY",
    "OBSERVABILITY","ARTIFACT_REGISTRY","METRICS","SNAPSHOTS"
  ],
  ALLOWED_ACTIONS: [
    "STATUS","HEARTBEAT","GENESIS_CHECK","TRIGGER_STATUS","CONTROL_READ",
    "CONTROL_APPEND","DRIVE_METADATA","DOC_TEXT_READ","CHECKPOINT","HANDOFF_PREPARE",
    "RUN_CANARY"
  ],
  BLOCKED_ACTION_PREFIXES: [
    "SEND_","DELETE_","GRANT_","REVOKE_","DEPLOY_","PUBLISH_","BILL_","PAY_",
    "ROTATE_SECRET","READ_SECRET","WRITE_SECRET","EXECUTE_ARBITRARY"
  ],
  SENSITIVE_KEY_PATTERN: /(secret|token|password|passwd|cookie|authorization|credential|api[_-]?key|private[_-]?key|session[_-]?state)/i
});

// ===== 01_Util.gs =====
function GNEN_now_(){ return new Date().toISOString(); }
function GNEN_json_(x){ return JSON.stringify(x); }
function GNEN_hash_(text){
  var bytes=Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256,String(text||""),Utilities.Charset.UTF_8);
  return bytes.map(function(b){var v=(b<0?b+256:b).toString(16);return v.length===1?"0"+v:v;}).join("");
}
function GNEN_props_(){ return PropertiesService.getScriptProperties(); }
function GNEN_parse_(s,fallback){ try{return JSON.parse(s);}catch(e){return fallback;} }
function GNEN_controlId_(){ return GNEN_props_().getProperty(KIOAS_GNEN.PROPS.CONTROL_PLANE_ID)||""; }
function GNEN_openControl_(){
  var id=GNEN_controlId_(); if(!id) throw new Error("GNEN_CONTROL_PLANE_UNCONFIGURED");
  return SpreadsheetApp.openById(id);
}
function GNEN_sheet_(name){
  var sh=GNEN_openControl_().getSheetByName(name); if(!sh) throw new Error("GNEN_MISSING_SHEET:"+name); return sh;
}
function GNEN_scriptId_(){ try{return ScriptApp.getScriptId();}catch(e){return "UNAVAILABLE";} }
function GNEN_sanitize_(value){
  if(value===null||value===undefined) return value;
  if(Array.isArray(value)) return value.map(GNEN_sanitize_);
  if(typeof value==="object"){
    var out={}; Object.keys(value).forEach(function(k){
      if(KIOAS_GNEN.SENSITIVE_KEY_PATTERN.test(String(k))) out[k]="[REDACTED]";
      else out[k]=GNEN_sanitize_(value[k]);
    }); return out;
  }
  return value;
}
function GNEN_assertNoSensitivePayload_(value,path){
  path=path||"$";
  if(value===null||value===undefined) return true;
  if(Array.isArray(value)){value.forEach(function(v,i){GNEN_assertNoSensitivePayload_(v,path+"["+i+"]");});return true;}
  if(typeof value==="object"){
    Object.keys(value).forEach(function(k){
      if(KIOAS_GNEN.SENSITIVE_KEY_PATTERN.test(String(k))) throw new Error("GNEN_SENSITIVE_PAYLOAD_REJECTED:"+path+"."+k);
      GNEN_assertNoSensitivePayload_(value[k],path+"."+k);
    });
  }
  return true;
}
function GNEN_allowedResourceIds_(){
  return GNEN_parse_(GNEN_props_().getProperty(KIOAS_GNEN.PROPS.ALLOWED_RESOURCE_IDS)||"[]",[]);
}
function GNEN_assertResourceAllowed_(id){
  if(GNEN_allowedResourceIds_().indexOf(String(id||""))<0) throw new Error("GNEN_RESOURCE_NOT_ALLOWLISTED");
  return true;
}

// ===== 02_Identity.gs =====
function GNEN_ownerEmail_(){ return GNEN_props_().getProperty(KIOAS_GNEN.PROPS.OWNER_EMAIL)||""; }
function GNEN_assertOwner_(){
  var expected=GNEN_ownerEmail_(), actual=Session.getEffectiveUser().getEmail();
  if(!expected) throw new Error("GNEN_OWNER_UNCONFIGURED");
  if(!actual||String(actual).toLowerCase()!==String(expected).toLowerCase()) throw new Error("GNEN_OWNER_IDENTITY_MISMATCH");
  return true;
}
function GNEN_nodeId_(){ return GNEN_props_().getProperty(KIOAS_GNEN.PROPS.NODE_ID)||("KIOAS-GNEN:"+GNEN_scriptId_()); }

// ===== 03_Proof.gs =====
function GNEN_recordProof_(kind,subject,evidence){
  GNEN_assertNoSensitivePayload_(evidence||{});
  var clean=GNEN_sanitize_(evidence||{}), at=GNEN_now_();
  var payload={schema:"kioas.gnen.proof.v1",kind:kind,subject:subject,evidence:clean,nodeId:GNEN_nodeId_(),at:at};
  var ref="GNEN-PROOF-"+GNEN_hash_(GNEN_json_(payload));
  GNEN_sheet_("PROOF_LEDGER").appendRow([ref,kind,subject,GNEN_json_(clean),at,"RECORDED"]);
  return ref;
}
function GNEN_semanticReceipt_(action,result,readback){
  var evidence={semanticReadback:true,provenance:true,action:action,result:GNEN_sanitize_(result),readback:GNEN_sanitize_(readback)};
  return GNEN_recordProof_("COMMAND_SEMANTIC_READBACK",action,evidence);
}

// ===== 04_IdempotencyLease.gs =====
function GNEN_withCommandLock_(idempotencyKey,fn){
  if(!idempotencyKey) throw new Error("GNEN_IDEMPOTENCY_KEY_REQUIRED");
  var lock=LockService.getScriptLock(); lock.waitLock(30000);
  try{
    var props=GNEN_props_(), key="GNEN_DONE:"+idempotencyKey;
    var prior=props.getProperty(key); if(prior) return {status:"IDEMPOTENT_REPLAY",receipt:prior};
    var out=fn(); var receipt=GNEN_hash_(GNEN_json_(GNEN_sanitize_(out)));
    props.setProperty(key,receipt); return out;
  } finally { lock.releaseLock(); }
}

// ===== 05_ControlPlane.gs =====
function GNEN_validateA1Range_(rangeA1){
  var m=String(rangeA1||"").match(/^([A-Z]+)(\d+):([A-Z]+)(\d+)$/i); if(!m) throw new Error("GNEN_INVALID_RANGE");
  function col(s){var n=0;String(s).toUpperCase().split("").forEach(function(c){n=n*26+c.charCodeAt(0)-64;});return n;}
  var rows=Math.abs(Number(m[4])-Number(m[2]))+1, cols=Math.abs(col(m[3])-col(m[1]))+1;
  if(rows>KIOAS_GNEN.MAX_RANGE_ROWS||cols>KIOAS_GNEN.MAX_RANGE_COLS) throw new Error("GNEN_RANGE_TOO_LARGE");
  return true;
}
function GNEN_controlRead_(payload){
  var sheet=String(payload.sheet||""), range=String(payload.range||"");
  if(KIOAS_GNEN.REQUIRED_SHEETS.indexOf(sheet)<0) throw new Error("GNEN_SHEET_NOT_ALLOWLISTED");
  GNEN_validateA1Range_(range); var values=GNEN_sheet_(sheet).getRange(range).getValues();
  return {sheet:sheet,range:range,values:GNEN_sanitize_(values)};
}
function GNEN_controlAppend_(payload){
  var sheet=String(payload.sheet||""), row=payload.row||[];
  if(KIOAS_GNEN.SAFE_APPEND_SHEETS.indexOf(sheet)<0) throw new Error("GNEN_APPEND_SHEET_NOT_ALLOWLISTED");
  if(!Array.isArray(row)||row.length>20) throw new Error("GNEN_INVALID_APPEND_ROW");
  GNEN_assertNoSensitivePayload_(row); var sh=GNEN_sheet_(sheet), before=sh.getLastRow();
  sh.appendRow(row); var after=sh.getLastRow(); var readback=sh.getRange(after,1,1,row.length).getValues()[0];
  if(after!==before+1||GNEN_json_(readback)!==GNEN_json_(row)) throw new Error("GNEN_APPEND_READBACK_MISMATCH");
  return {sheet:sheet,rowNumber:after,readback:readback};
}

// ===== 06_GoogleReadAdapters.gs =====
function GNEN_googleGet_(url){
  if(!/^https:\/\/(www\.googleapis\.com\/drive\/v3\/|docs\.googleapis\.com\/v1\/)/.test(String(url))) throw new Error("GNEN_GOOGLE_HOST_NOT_ALLOWLISTED");
  var response=UrlFetchApp.fetch(String(url),{
    method:"get",
    headers:{Authorization:"Bearer "+ScriptApp.getOAuthToken()},
    muteHttpExceptions:true,
    followRedirects:false
  });
  var status=response.getResponseCode(), text=response.getContentText();
  if(status<200||status>=300) throw new Error("GNEN_GOOGLE_READ_FAILED:"+status);
  return GNEN_parse_(text,{});
}
function GNEN_driveMetadata_(payload){
  var id=String(payload.fileId||""); GNEN_assertResourceAllowed_(id);
  var url="https://www.googleapis.com/drive/v3/files/"+encodeURIComponent(id)+"?fields=id,name,mimeType,modifiedTime,size,md5Checksum,version";
  return GNEN_sanitize_(GNEN_googleGet_(url));
}
function GNEN_docTextRead_(payload){
  var id=String(payload.documentId||""); GNEN_assertResourceAllowed_(id);
  var doc=GNEN_googleGet_("https://docs.googleapis.com/v1/documents/"+encodeURIComponent(id));
  var chunks=[];
  (doc.body&&doc.body.content||[]).forEach(function(block){
    (block.paragraph&&block.paragraph.elements||[]).forEach(function(el){
      if(el.textRun&&el.textRun.content) chunks.push(el.textRun.content);
    });
  });
  return {documentId:id,title:String(doc.title||""),text:chunks.join("")};
}

// ===== 07_Authority.gs =====
function GNEN_authorityClass_(command){ return String(command.authorityClass||"A1").toUpperCase(); }
function GNEN_assertActionAllowed_(action){
  action=String(action||"").toUpperCase();
  KIOAS_GNEN.BLOCKED_ACTION_PREFIXES.forEach(function(prefix){
    if(action.indexOf(prefix)===0) throw new Error("GNEN_ACTION_BLOCKED:"+action);
  });
  if(KIOAS_GNEN.ALLOWED_ACTIONS.indexOf(action)<0) throw new Error("GNEN_ACTION_NOT_ALLOWLISTED:"+action);
  return action;
}
function GNEN_holdHighAuthority_(command){
  var heldClasses=["A2","A3"], authority=GNEN_authorityClass_(command);
  if(heldClasses.indexOf(authority)<0) return null;
  return {
    status:"HELD_AUTHORITY",
    authorityClass:authority,
    heldAuthorityClasses:["A2","A3"],
    networkCallPerformed:false,
    providerMutationAttempted:false,
    reason:"GNEN_A2_A3_REQUIRE_EXTERNAL_OWNER_AUTHORITY"
  };
}

// ===== 08_StatusHeartbeat.gs =====
function GNEN_status(){
  return {
    schema:KIOAS_GNEN.SCHEMA,
    version:KIOAS_GNEN.VERSION,
    nodeClass:KIOAS_GNEN.NODE_CLASS,
    nodeId:GNEN_nodeId_(),
    scriptId:GNEN_scriptId_(),
    productionEffect:false,
    networkCallPerformed:false,
    controlPlaneConfigured:!!GNEN_controlId_(),
    buildSha:GNEN_props_().getProperty(KIOAS_GNEN.PROPS.BUILD_SHA)||"",
    installedAt:GNEN_props_().getProperty(KIOAS_GNEN.PROPS.INSTALLED_AT)||"",
    observedAt:GNEN_now_()
  };
}
function GNEN_heartbeat(){
  GNEN_assertOwner_();
  var status=GNEN_status(), row=[GNEN_now_(),status.nodeId,status.version,"HEALTHY",status.buildSha];
  try{ GNEN_sheet_("OBSERVABILITY").appendRow(row); }catch(e){ /* health remains readable even if ledger is unavailable */ }
  return status;
}
function GNEN_genesisCheck(){
  var status=GNEN_status(), missing=[];
  if(!status.controlPlaneConfigured) missing.push("CONTROL_PLANE_ID");
  if(!GNEN_ownerEmail_()) missing.push("OWNER_EMAIL");
  return {status:missing.length?"SOURCE_READY_CONFIGURATION_REQUIRED":"SOURCE_READY",missing:missing,node:status};
}

// ===== 09_Triggers.gs =====
function GNEN_triggerStatus_(){
  var triggers=ScriptApp.getProjectTriggers(), counts={command:0,heartbeat:0}, detail=[];
  triggers.forEach(function(t){
    var handler=t.getHandlerFunction();
    if(handler===KIOAS_GNEN.COMMAND_TRIGGER_SINGLETON) counts.command++;
    if(handler===KIOAS_GNEN.HEARTBEAT_TRIGGER_SINGLETON) counts.heartbeat++;
    detail.push({handlerFunction:handler,eventType:String(t.getEventType())});
  });
  return {COMMAND_TRIGGER_SINGLETON:counts.command,HEARTBEAT_TRIGGER_SINGLETON:counts.heartbeat,triggers:detail};
}
function GNEN_deleteHandlerTriggers_(handler){
  ScriptApp.getProjectTriggers().forEach(function(t){ if(t.getHandlerFunction()===handler) ScriptApp.deleteTrigger(t); });
}
function GNEN_installTriggers(){
  GNEN_assertOwner_();
  GNEN_deleteHandlerTriggers_(KIOAS_GNEN.COMMAND_TRIGGER_SINGLETON);
  GNEN_deleteHandlerTriggers_(KIOAS_GNEN.HEARTBEAT_TRIGGER_SINGLETON);
  ScriptApp.newTrigger(KIOAS_GNEN.COMMAND_TRIGGER_SINGLETON).timeBased().everyMinutes(KIOAS_GNEN.COMMAND_POLL_MINUTES).create();
  ScriptApp.newTrigger(KIOAS_GNEN.HEARTBEAT_TRIGGER_SINGLETON).timeBased().everyMinutes(KIOAS_GNEN.HEARTBEAT_MINUTES).create();
  var readback=GNEN_triggerStatus_();
  if(readback.COMMAND_TRIGGER_SINGLETON!==1||readback.HEARTBEAT_TRIGGER_SINGLETON!==1) throw new Error("GNEN_TRIGGER_SINGLETON_READBACK_FAILED");
  return readback;
}

// ===== 10_CheckpointHandoff.gs =====
function GNEN_checkpoint_(payload){
  var snapshot={
    schema:"kioas.gnen.checkpoint.v1",
    nodeId:GNEN_nodeId_(),
    buildSha:GNEN_props_().getProperty(KIOAS_GNEN.PROPS.BUILD_SHA)||"",
    reason:String(payload.reason||"manual"),
    sourceRollbackPointer:String(payload.sourceRollbackPointer||""),
    at:GNEN_now_()
  };
  GNEN_assertNoSensitivePayload_(snapshot);
  var result=GNEN_controlAppend_({sheet:"SNAPSHOTS",row:[snapshot.at,snapshot.nodeId,snapshot.buildSha,snapshot.reason,snapshot.sourceRollbackPointer,GNEN_hash_(GNEN_json_(snapshot))]});
  return {snapshot:snapshot,readback:result};
}
function GNEN_handoffPrepare_(payload){
  var envelope={
    schema:"kioas.gnen.handoff.v1",
    nodeId:GNEN_nodeId_(),
    missionId:String(payload.missionId||""),
    targetCapability:String(payload.targetCapability||""),
    artifactRefs:Array.isArray(payload.artifactRefs)?payload.artifactRefs:[],
    authorityClass:GNEN_authorityClass_(payload),
    productionEffect:false,
    networkCallPerformed:false,
    preparedAt:GNEN_now_()
  };
  GNEN_assertNoSensitivePayload_(envelope);
  return envelope;
}

// ===== 11_CommandDispatcher.gs =====
function GNEN_dispatch_(command){
  command=command||{}; GNEN_assertNoSensitivePayload_(command);
  var held=GNEN_holdHighAuthority_(command); if(held) return held;
  var action=GNEN_assertActionAllowed_(command.action), payload=command.payload||{};
  switch(action){
    case "STATUS": return GNEN_status();
    case "HEARTBEAT": return GNEN_heartbeat();
    case "GENESIS_CHECK": return GNEN_genesisCheck();
    case "TRIGGER_STATUS": return GNEN_triggerStatus_();
    case "CONTROL_READ": return GNEN_controlRead_(payload);
    case "CONTROL_APPEND": return GNEN_controlAppend_(payload);
    case "DRIVE_METADATA": return GNEN_driveMetadata_(payload);
    case "DOC_TEXT_READ": return GNEN_docTextRead_(payload);
    case "CHECKPOINT": return GNEN_checkpoint_(payload);
    case "HANDOFF_PREPARE": return GNEN_handoffPrepare_(payload);
    case "RUN_CANARY": return {status:"CANARY_OK",nodeId:GNEN_nodeId_(),networkCallPerformed:false,providerMutationAttempted:false,at:GNEN_now_()};
  }
  throw new Error("GNEN_UNREACHABLE_ACTION:"+action);
}

// ===== 12_QueueFailureLearning.gs =====
function GNEN_recordFailure_(command,error){
  var safe={
    action:String(command&&command.action||""),
    idempotencyKey:String(command&&command.idempotencyKey||""),
    errorName:String(error&&error.name||"Error"),
    errorMessage:String(error&&error.message||error||"UNKNOWN"),
    at:GNEN_now_()
  };
  safe=GNEN_sanitize_(safe);
  try{ GNEN_sheet_("FAILURE_BOOK").appendRow([safe.at,safe.action,safe.idempotencyKey,safe.errorName,safe.errorMessage,"OPEN"]); }catch(ignore){}
  try{ GNEN_sheet_("LEARNING_LEDGER").appendRow([safe.at,"FAILURE_TO_WIN",safe.action,"ROUTE_REVIEW_REQUIRED",GNEN_hash_(GNEN_json_(safe))]); }catch(ignore2){}
  return safe;
}
function GNEN_executeCommand_(command){
  var key=String(command.idempotencyKey||"");
  return GNEN_withCommandLock_(key,function(){
    try{
      var result=GNEN_dispatch_(command);
      var receipt=GNEN_semanticReceipt_(String(command.action||"UNKNOWN"),result,{status:"EXECUTED_OR_HELD",idempotencyKey:key});
      return {status:"COMPLETED",result:GNEN_sanitize_(result),proofRef:receipt};
    }catch(error){
      GNEN_recordFailure_(command,error);
      throw error;
    }
  });
}
function GNEN_processQueue(){
  GNEN_assertOwner_();
  var sh=GNEN_sheet_("COMMAND_QUEUE"), last=sh.getLastRow();
  if(last<2) return {status:"EMPTY",processed:0};
  var width=Math.max(sh.getLastColumn(),6), values=sh.getRange(2,1,last-1,width).getValues(), processed=0;
  for(var i=0;i<values.length&&processed<KIOAS_GNEN.MAX_QUEUE_BATCH;i++){
    var row=values[i], state=String(row[5]||"").toUpperCase();
    if(state&&state!=="QUEUED") continue;
    var command={
      commandId:String(row[0]||""),
      action:String(row[1]||""),
      payload:GNEN_parse_(String(row[2]||"{}"),{}),
      authorityClass:String(row[3]||"A1"),
      idempotencyKey:String(row[4]||row[0]||"")
    };
    try{
      var out=GNEN_executeCommand_(command);
      GNEN_sheet_("COMMAND_RESULTS").appendRow([GNEN_now_(),command.commandId,command.action,out.status,GNEN_json_(GNEN_sanitize_(out)),command.idempotencyKey]);
      sh.getRange(i+2,6).setValue("DONE");
    }catch(error){
      GNEN_sheet_("COMMAND_RESULTS").appendRow([GNEN_now_(),command.commandId,command.action,"FAILED",GNEN_json_(GNEN_sanitize_({message:String(error.message||error)})),command.idempotencyKey]);
      sh.getRange(i+2,6).setValue("FAILED");
    }
    processed++;
  }
  return {status:"PROCESSED",processed:processed};
}

// ===== 13_Compatibility.gs =====
function FED_status(){ return GNEN_status(); }
function FED_genesisCheck(){ return GNEN_genesisCheck(); }

// ===== 14_Bootstrap.gs =====
function GNEN_bootstrap(config){
  config=config||{}; GNEN_assertNoSensitivePayload_(config); GNEN_assertOwner_();
  var props=GNEN_props_();
  if(config.controlPlaneId) props.setProperty(KIOAS_GNEN.PROPS.CONTROL_PLANE_ID,String(config.controlPlaneId));
  if(config.allowedResourceIds) props.setProperty(KIOAS_GNEN.PROPS.ALLOWED_RESOURCE_IDS,GNEN_json_(config.allowedResourceIds));
  if(config.buildSha) props.setProperty(KIOAS_GNEN.PROPS.BUILD_SHA,String(config.buildSha));
  if(!props.getProperty(KIOAS_GNEN.PROPS.INSTALLED_AT)) props.setProperty(KIOAS_GNEN.PROPS.INSTALLED_AT,GNEN_now_());
  var triggers=GNEN_installTriggers();
  var canary=GNEN_dispatch_({action:"RUN_CANARY",authorityClass:"A0",payload:{},idempotencyKey:"bootstrap-canary"});
  return {status:"SOURCE_READY",triggers:triggers,canary:canary,node:GNEN_status()};
}
