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
    Object.keys(value).forEach(function(d){
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
  var response=Ur