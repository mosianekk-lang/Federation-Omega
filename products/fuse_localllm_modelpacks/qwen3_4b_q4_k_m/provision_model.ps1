param(
  [string]$DestinationRoot = (Join-Path $env:LOCALAPPDATA "FUSE\Models"),
  [switch]$Force
)
$ErrorActionPreference="Stop"
$ModelFile="Qwen3-4B-Q4_K_M.gguf"
$ExpectedSha="7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
$ExpectedSize=[int64]2497280256
$Source="https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/a9a60d009fa7ff9606305047c2bf77ac25dbec49/Qwen3-4B-Q4_K_M.gguf?download=true"
New-Item -ItemType Directory -Path $DestinationRoot -Force | Out-Null
$Target=Join-Path $DestinationRoot $ModelFile
$Receipt=Join-Path $DestinationRoot "Qwen3-4B-Q4_K_M.MODEL_RECEIPT.json"

function Assert-Model([string]$Path) {
  if(-not (Test-Path -LiteralPath $Path)){ return $false }
  $item=Get-Item -LiteralPath $Path
  if($item.Length -ne $ExpectedSize){ return $false }
  $sha=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
  return $sha -eq $ExpectedSha
}

if((-not $Force) -and (Assert-Model $Target)){
  [ordered]@{
    schema="FUSE-MODEL-PROVISION-RECEIPT-V1";pack_id="FUSE-MODELPACK-QWEN3-4B-Q4-K-M-V1";
    state="REUSED_VERIFIED";path=$Target;size_bytes=$ExpectedSize;sha256=$ExpectedSha;
    source=$Source;verified_at=(Get-Date).ToString("o")
  } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Receipt -Encoding UTF8
  Get-Content -LiteralPath $Receipt
  exit 0
}

$Temp=Join-Path $DestinationRoot ($ModelFile+".partial")
Remove-Item -LiteralPath $Temp -Force -ErrorAction SilentlyContinue
try {
  if(Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue){
    Start-BitsTransfer -Source $Source -Destination $Temp -DisplayName "FUSE Qwen3-4B model pack"
  } else {
    Invoke-WebRequest -Uri $Source -OutFile $Temp -UseBasicParsing
  }
  if(-not (Assert-Model $Temp)){
    $actualSize=(Get-Item -LiteralPath $Temp).Length
    $actualSha=(Get-FileHash -LiteralPath $Temp -Algorithm SHA256).Hash.ToLowerInvariant()
    throw "MODEL_INTEGRITY_MISMATCH size=$actualSize sha256=$actualSha"
  }
  Move-Item -LiteralPath $Temp -Destination $Target -Force
  if(-not (Assert-Model $Target)){ throw "MODEL_POST_MOVE_INTEGRITY_MISMATCH" }
  [ordered]@{
    schema="FUSE-MODEL-PROVISION-RECEIPT-V1";pack_id="FUSE-MODELPACK-QWEN3-4B-Q4-K-M-V1";
    state="DOWNLOADED_VERIFIED";path=$Target;size_bytes=$ExpectedSize;sha256=$ExpectedSha;
    source=$Source;verified_at=(Get-Date).ToString("o")
  } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $Receipt -Encoding UTF8
  Get-Content -LiteralPath $Receipt
} finally {
  Remove-Item -LiteralPath $Temp -Force -ErrorAction SilentlyContinue
}
