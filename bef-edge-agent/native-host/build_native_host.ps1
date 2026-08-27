param(
  [string]$PythonExe = 'py',
  [string]$OutputDir = ''
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $here 'bef_native_host.py'
if (-not $OutputDir) { $OutputDir = Join-Path $here 'dist' }
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

& $PythonExe -3 -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
  throw 'PYINSTALLER_NOT_AVAILABLE: bind an approved local Python build environment before packaging; do not download dependencies silently from this script.'
}

$work = Join-Path $env:TEMP 'sovara-bef-native-build'
if (Test-Path $work) { Remove-Item -LiteralPath $work -Recurse -Force }
New-Item -ItemType Directory -Path $work -Force | Out-Null

& $PythonExe -3 -m PyInstaller --noconfirm --clean --onefile --name bef_native_host --distpath $OutputDir --workpath (Join-Path $work 'work') --specpath (Join-Path $work 'spec') $source
if ($LASTEXITCODE -ne 0) { throw 'PYINSTALLER_BUILD_FAILED' }

$exe = Join-Path $OutputDir 'bef_native_host.exe'
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { throw 'NATIVE_HOST_EXE_MISSING_AFTER_BUILD' }
$selfTest = & $exe --self-test
if ($LASTEXITCODE -ne 0 -or ($selfTest -notmatch 'BEF_NATIVE_HOST_SELF_TEST_PASS')) {
  throw "NATIVE_HOST_SELF_TEST_FAILED: $selfTest"
}
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $exe).Hash.ToLowerInvariant()

[pscustomobject]@{
  State = 'NATIVE_HOST_EXE_BUILT_SELF_TEST_VERIFIED'
  Executable = (Resolve-Path -LiteralPath $exe).Path
  Sha256 = $hash
  SelfTest = $selfTest
  TruthBoundary = 'Local executable build/self-test only; browser registration and live provenance delivery remain separate gates.'
} | ConvertTo-Json -Depth 5
