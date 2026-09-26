param(
  [ValidateSet('Status','AutoRoute','LocalGenerate','GeminiGenerate','GeminiRole','GeminiCouncil','ProviderRace')]
  [string]$Action='Status',
  [string]$Prompt='',
  [ValidateSet('PUBLIC','INTERNAL','CONFIDENTIAL','LEGAL_EVIDENCE','SECRET')]
  [string]$DataClassification='INTERNAL',
  [ValidateSet('general','reason','critic','creative','design','route','continuity','provenance','judge')]
  [string]$TaskKind='general',
  [ValidateSet('ALPHA_OMEGA_REASONER','CFBE_CRITIC','CREATIVE_BRIEF_COMPILER','DESIGNIR_VALIDATOR','ROUTE_RANKER','STORYBOARD_CONTINUITY_CRITIC','PROVENANCE_ANALYST','CHALLENGER_JUDGE')]
  [string]$Role='ALPHA_OMEGA_REASONER',
  [string]$InputJson='',
  [string]$ExpectedJson='',
  [string]$Model='gemini-2.5-flash',
  [int]$MaxOutputTokens=768
)
$ErrorActionPreference='Stop'
$ProjectId='sov-hybrid-suite'
$Location='global'
$Root=Join-Path $env:LOCALAPPDATA 'FUSE\LocalLLM'
$FabricRoot=Join-Path $Root 'provider-fabric'
$RolesPath=Join-Path $FabricRoot 'gemini_roles.json'
$ReceiptDir=Join-Path $Root 'receipts'
New-Item -ItemType Directory -Force -Path $ReceiptDir | Out-Null

function Write-FuseReceipt([hashtable]$Receipt){
  $Receipt['recorded_at_utc']=(Get-Date).ToUniversalTime().ToString('o')
  $Receipt['receipt_id']='LLM-'+[guid]::NewGuid().ToString('N')
  $json=$Receipt | ConvertTo-Json -Depth 20
  $path=Join-Path $ReceiptDir ($Receipt['receipt_id']+'.json')
  [IO.File]::WriteAllText($path,$json,[Text.UTF8Encoding]::new($false))
  return $Receipt
}
function Assert-Prompt { if([string]::IsNullOrWhiteSpace($Prompt)){ throw 'PROMPT_REQUIRED' } }
function Test-CloudAllowed([string]$Class){ return $Class -in @('PUBLIC','INTERNAL') }
function Get-LocalBase {
  foreach($port in @(8999,9001,11434)){
    try {
      $tcp=New-Object Net.Sockets.TcpClient
      $ar=$tcp.BeginConnect('127.0.0.1',$port,$null,$null)
      if($ar.AsyncWaitHandle.WaitOne(250) -and $tcp.Connected){
        $tcp.Close()
        if($port -eq 11434){ return 'http://127.0.0.1:11434/v1' }
        return "http://127.0.0.1:$port/v1"
      }
      $tcp.Close()
    } catch {}
  }
  return 'http://127.0.0.1:8999/v1'
}
function Get-GcloudExe {
  $candidates=@(
    (Get-Command gcloud.cmd -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    (Get-Command gcloud -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
    "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
  )
  foreach($p in $candidates){ if($p -and (Test-Path $p)){ return $p } }
  throw 'GCLOUD_NOT_AVAILABLE'
}
function Get-GcpAccessToken {
  $gcloud=Get-GcloudExe
  $token=& $gcloud auth print-access-token 2>$null
  if(-not $token){ throw 'GCLOUD_ADC_TOKEN_UNAVAILABLE' }
  return ($token | Select-Object -Last 1).Trim()
}
function Invoke-Local([string]$Text){
  $base=Get-LocalBase
  $uri="$base/chat/completions"
  $body=@{
    model='fuse-local'
    messages=@(@{role='user';content=$Text})
    temperature=0.2
    max_tokens=$MaxOutputTokens
    stream=$false
  } | ConvertTo-Json -Depth 8
  $sw=[Diagnostics.Stopwatch]::StartNew()
  $resp=Invoke-RestMethod -Method Post -Uri $uri -ContentType 'application/json' -Body $body -TimeoutSec 180
  $sw.Stop()
  $reply=[string]$resp.choices[0].message.content
  return Write-FuseReceipt @{
    schema='FUSE_LOCALLLM_PROVIDER_RECEIPT_V1'
    provider='FUSE_LOCAL_LLM'
    transport='LOOPBACK_OPENAI_COMPAT'
    model=[string]$resp.model
    route=$uri
    semantic_verified=[bool](-not [string]::IsNullOrWhiteSpace($reply))
    latency_ms=$sw.ElapsedMilliseconds
    data_classification=$DataClassification
    response=$reply
    external_effect=$false
  }
}
function Get-RoleContract([string]$Name){
  if(-not (Test-Path $RolesPath)){ throw "ROLE_CONTRACT_MISSING:$RolesPath" }
  $roles=(Get-Content $RolesPath -Raw | ConvertFrom-Json).roles
  $r=$roles.$Name
  if($null -eq $r){ throw "UNKNOWN_ROLE:$Name" }
  return $r
}
function Get-Threshold([string]$Rule,[double]$Fallback){
  $matches=[regex]::Matches($Rule,'(?<![A-Za-z])(?:0(?:\.\d+)?|1(?:\.0+)?)')
  if($matches.Count -gt 0){ return [double]$matches[$matches.Count-1].Value }
  return $Fallback
}
function Get-DerivedMetrics([string]$Name,[object]$Input){
  if($null -eq $Input){ return @{} }
  if($Name -eq 'CFBE_CRITIC' -and $Input.candidate -and $Input.incumbent){
    $threshold=Get-Threshold ([string]$Input.rule) 0.01
    $reg=[Math]::Max(0.0,[double]$Input.incumbent.quality-[double]$Input.candidate.quality)
    return @{quality_regression=[Math]::Round($reg,6);quality_regression_limit=$threshold;quality_floor_violated=($reg -gt $threshold)}
  }
  if($Name -eq 'CHALLENGER_JUDGE' -and $Input.A -and $Input.B){
    $threshold=Get-Threshold ([string]$Input.hard_rule) 0.10
    $lower=@('latency','cost','risk','error_rate','failure_rate')
    $regs=@{};$failing=@()
    foreach($criterion in @($Input.criteria)){
      $c=[string]$criterion;$a=[double]$Input.A.$c;$b=[double]$Input.B.$c
      if($lower -contains $c.ToLower()){ $r=$b-$a } else { $r=$a-$b }
      $r=[Math]::Max(0.0,$r);$regs[$c]=[Math]::Round($r,6)
      if($r -gt $threshold){ $failing += $c }
    }
    return @{regression_threshold=$threshold;criterion_regressions=$regs;criteria_exceeding_threshold=$failing;promotion_blocked_by_frozen_rule=($failing.Count -gt 0)}
  }
  return @{}
}
function Invoke-Gemini([string]$Text,[object]$ResponseSchema=$null,[string[]]$RequiredKeys=@()){
  if(-not (Test-CloudAllowed $DataClassification)){ throw "CLOUD_DENIED_DATA_CLASSIFICATION:$DataClassification" }
  $token=Get-GcpAccessToken
  try {
    $endpoint="https://aiplatform.googleapis.com/v1/projects/$ProjectId/locations/$Location/publishers/google/models/$Model" + ':generateContent'
    $config=@{temperature=0;candidateCount=1;maxOutputTokens=$MaxOutputTokens;responseMimeType='application/json';thinkingConfig=@{thinkingBudget=0}}
    if($null -ne $ResponseSchema){ $config['responseSchema']=$ResponseSchema }
    $payload=@{contents=@(@{role='user';parts=@(@{text=$Text})});generationConfig=$config} | ConvertTo-Json -Depth 30
    $headers=@{Authorization="Bearer $token";'Content-Type'='application/json'}
    $sw=[Diagnostics.Stopwatch]::StartNew()
    $web=Invoke-WebRequest -UseBasicParsing -Method Post -Uri $endpoint -Headers $headers -Body $payload -TimeoutSec 120
    $sw.Stop()
    $body=$web.Content | ConvertFrom-Json
    $textOut=[string](($body.candidates[0].content.parts | ForEach-Object {$_.text}) -join '')
    $parsed=$null;$shapeOk=$true
    try { $parsed=$textOut | ConvertFrom-Json } catch { $shapeOk=$false }
    if($shapeOk -and $RequiredKeys.Count -gt 0){
      foreach($k in $RequiredKeys){ if($null -eq $parsed.PSObject.Properties[$k]){ $shapeOk=$false; break } }
    }
    $requestId=[string]$body.responseId
    if([string]::IsNullOrWhiteSpace($requestId)){
      foreach($h in @('x-request-id','x-goog-request-id')){ if($web.Headers[$h]){ $requestId=[string]$web.Headers[$h]; break } }
    }
    $usage=@{}
    if($body.usageMetadata){
      foreach($k in @('promptTokenCount','candidatesTokenCount','thoughtsTokenCount','totalTokenCount','cachedContentTokenCount')){
        if($null -ne $body.usageMetadata.PSObject.Properties[$k]){ $usage[$k]=$body.usageMetadata.$k }
      }
    }
    return Write-FuseReceipt @{
      schema='FUSE_LOCALLLM_PROVIDER_RECEIPT_V1';provider='GOOGLE_VERTEX_AI';transport='GCLOUD_ADC_ACCESS_TOKEN'
      project_id=$ProjectId;location=$Location;model=$Model;provider_model_version=[string]$body.modelVersion
      provider_request_id=$requestId;semantic_verified=([int]$web.StatusCode -eq 200 -and $shapeOk -and -not [string]::IsNullOrWhiteSpace($requestId))
      http_status=[int]$web.StatusCode;latency_ms=$sw.ElapsedMilliseconds;usage=$usage;structured_output=$parsed;response=$textOut
      data_classification=$DataClassification;token_value_recorded=$false;provider_mutation=$false;external_effect=$false
    }
  } finally { $token=$null }
}
function Invoke-GeminiRole([string]$Name){
  Assert-Prompt
  $contract=Get-RoleContract $Name
  $input=$null
  if(-not [string]::IsNullOrWhiteSpace($InputJson)){ $input=$InputJson | ConvertFrom-Json }
  $derived=Get-DerivedMetrics $Name $input
  $lines=@(
    "ROLE=$Name","GUIDANCE=$($contract.guidance)",
    'RULE=Evidence and hard floors outrank model confidence.',
    'RULE=Do not invent authority, source evidence, eligibility, approval, execution or completion.',
    'RULE=Do not reveal hidden chain-of-thought; return concise decision fields only.',
    'RULE=If DERIVED_METRICS_JSON is non-empty, use it exactly rather than recomputing contradictory arithmetic.',
    "DERIVED_METRICS_JSON=$($derived | ConvertTo-Json -Compress -Depth 10)",
    "INPUT_JSON=$InputJson","TASK=$Prompt"
  )
  $r=Invoke-Gemini ($lines -join [Environment]::NewLine) $contract.response_schema @($contract.required_keys)
  $r['role']=$Name
  return $r
}
function Resolve-Role([string]$Kind){
  switch($Kind){
    'critic' {'CFBE_CRITIC'} 'creative' {'CREATIVE_BRIEF_COMPILER'} 'design' {'DESIGNIR_VALIDATOR'}
    'route' {'ROUTE_RANKER'} 'continuity' {'STORYBOARD_CONTINUITY_CRITIC'} 'provenance' {'PROVENANCE_ANALYST'}
    'judge' {'CHALLENGER_JUDGE'} default {'ALPHA_OMEGA_REASONER'}
  }
}
function Compact-Json([string]$Value){
  try { return (($Value | ConvertFrom-Json) | ConvertTo-Json -Compress -Depth 30) } catch { return $Value.Trim() }
}

switch($Action){
  'Status' {
    $local=Get-LocalBase;$gcloud=$null;try{$gcloud=Get-GcloudExe}catch{}
    Write-FuseReceipt @{
      schema='FUSE_LOCALLLM_HYBRID_STATUS_V1';local_endpoint=$local;gemini_provider='GOOGLE_VERTEX_AI';gemini_model=$Model
      gcloud_adc_available=[bool]$gcloud;primary_orchestrator='SOVARA';privacy_cloud_allowed=@('PUBLIC','INTERNAL')
      privacy_local_only=@('CONFIDENTIAL','LEGAL_EVIDENCE','SECRET')
      roles=@('ALPHA_OMEGA_REASONER','CFBE_CRITIC','CREATIVE_BRIEF_COMPILER','DESIGNIR_VALIDATOR','ROUTE_RANKER','STORYBOARD_CONTINUITY_CRITIC','PROVENANCE_ANALYST','CHALLENGER_JUDGE')
      hyper_performance_verified=$false;external_effect=$false
    } | ConvertTo-Json -Depth 12
  }
  'LocalGenerate' { Assert-Prompt; Invoke-Local $Prompt | ConvertTo-Json -Depth 20 }
  'GeminiGenerate' { Assert-Prompt; Invoke-Gemini $Prompt | ConvertTo-Json -Depth 20 }
  'GeminiRole' { Invoke-GeminiRole $Role | ConvertTo-Json -Depth 30 }
  'GeminiCouncil' {
    Assert-Prompt
    if(-not (Test-CloudAllowed $DataClassification)){ throw "CLOUD_DENIED_DATA_CLASSIFICATION:$DataClassification" }
    $outputs=@()
    foreach($name in @('ALPHA_OMEGA_REASONER','CFBE_CRITIC','CREATIVE_BRIEF_COMPILER','DESIGNIR_VALIDATOR','ROUTE_RANKER','STORYBOARD_CONTINUITY_CRITIC','PROVENANCE_ANALYST','CHALLENGER_JUDGE')){
      try{$outputs += Invoke-GeminiRole $name}catch{$outputs += @{role=$name;semantic_verified=$false;error=$_.Exception.Message}}
    }
    $verified=@($outputs | Where-Object {$_.semantic_verified}).Count
    Write-FuseReceipt @{schema='FUSE_LOCALLLM_GEMINI_COUNCIL_RECEIPT_V1';provider='GOOGLE_VERTEX_AI';model=$Model;role_count=8;verified_count=$verified;council_state=if($verified -eq 8){'COUNCIL_8_OF_8'}else{'COUNCIL_PARTIAL'};stances=$outputs;synthesis_rule='Preserve dissent; evidence resolves disagreement, not consensus.';external_effect=$false} | ConvertTo-Json -Depth 40
  }
  'ProviderRace' {
    Assert-Prompt
    $local=$null;$gemini=$null
    try{$local=Invoke-Local $Prompt}catch{$local=@{provider='FUSE_LOCAL_LLM';semantic_verified=$false;error=$_.Exception.Message}}
    if(Test-CloudAllowed $DataClassification){try{$gemini=Invoke-Gemini $Prompt}catch{$gemini=@{provider='GOOGLE_VERTEX_AI';semantic_verified=$false;error=$_.Exception.Message}}}
    else{$gemini=@{provider='GOOGLE_VERTEX_AI';semantic_verified=$false;error="CLOUD_DENIED_DATA_CLASSIFICATION:$DataClassification"}}
    $winner=$null;$rule='NO_ORACLE_NO_WINNER'
    if(-not [string]::IsNullOrWhiteSpace($ExpectedJson)){
      $expected=Compact-Json $ExpectedJson
      $lp=($local.semantic_verified -and (Compact-Json ([string]$local.response)) -eq $expected)
      $gp=($gemini.semantic_verified -and (Compact-Json ([string]$gemini.response)) -eq $expected)
      if($lp -and -not $gp){$winner='FUSE_LOCAL_LLM'}elseif($gp -and -not $lp){$winner='GOOGLE_VERTEX_AI'}
      elseif($lp -and $gp){if([double]$gemini.latency_ms -lt [double]$local.latency_ms){$winner='GOOGLE_VERTEX_AI'}else{$winner='FUSE_LOCAL_LLM'}}
      $rule='EXACT_JSON_PASS_THEN_LOWER_PROVIDER_LATENCY'
    }
    Write-FuseReceipt @{schema='FUSE_LOCALLLM_PROVIDER_RACE_RECEIPT_V1';local=$local;gemini=$gemini;winner=$winner;selection_rule=$rule;global_provider_promotion=$false;external_effect=$false} | ConvertTo-Json -Depth 40
  }
  'AutoRoute' {
    Assert-Prompt
    if(-not (Test-CloudAllowed $DataClassification)){Invoke-Local $Prompt | ConvertTo-Json -Depth 20;break}
    $roleName=Resolve-Role $TaskKind
    try{Invoke-GeminiRole $roleName | ConvertTo-Json -Depth 30}
    catch{$fallback=Invoke-Local $Prompt;$fallback['fallback_from']='GOOGLE_VERTEX_AI';$fallback['fallback_reason']=$_.Exception.Message;$fallback | ConvertTo-Json -Depth 20}
  }
}
