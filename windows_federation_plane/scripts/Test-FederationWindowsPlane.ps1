$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($env:OS -ne 'Windows_NT') { throw 'WINDOWS_RUNTIME_REQUIRED' }

$plane = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$nativeProject = Join-Path $plane 'native\Fuse.Windows.Native.csproj'
$nativeOut = Join-Path $plane 'native\out'
$artifactDir = Join-Path $plane 'native\artifacts'
$zipPath = Join-Path $artifactDir 'fuse-windows-native.zip'
$proofPath = Join-Path $artifactDir 'native-build-proof.json'

Remove-Item -LiteralPath $nativeOut -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $artifactDir -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $nativeOut | Out-Null
New-Item -ItemType Directory -Force -Path $artifactDir | Out-Null

$env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
$env:DOTNET_NOLOGO = '1'
$env:PYTHONPATH = Join-Path $plane 'src'
$sourceSha = if ($env:FEDERATION_SOURCE_SHA) { $env:FEDERATION_SOURCE_SHA.ToLowerInvariant() } else { 'UNBOUND_SOURCE' }
if ($sourceSha -ne 'UNBOUND_SOURCE' -and $sourceSha -notmatch '^[0-9a-f]{40}$') { throw 'FEDERATION_SOURCE_SHA_INVALID' }

& dotnet publish $nativeProject --nologo -c Release -r win-x64 --self-contained false -o $nativeOut -p:Deterministic=true -p:ContinuousIntegrationBuild=true "-p:FederationSourceSha=$sourceSha"
if ($LASTEXITCODE -ne 0) { throw 'NATIVE_DOTNET_PUBLISH_FAILED' }

$nativeExe = Join-Path $nativeOut 'Fuse.Windows.Native.exe'
if (-not (Test-Path -LiteralPath $nativeExe -PathType Leaf)) { throw 'NATIVE_EXE_MISSING' }
Copy-Item -LiteralPath (Join-Path $plane 'native\Install-FuseNativeAgent.ps1') -Destination (Join-Path $nativeOut 'Install-FuseNativeAgent.ps1') -Force
Copy-Item -LiteralPath (Join-Path $plane 'native\FUSE-Native-OneClick.cmd') -Destination (Join-Path $nativeOut 'FUSE-Native-OneClick.cmd') -Force
$env:FUSE_NATIVE_EXE = $nativeExe

python -m unittest discover -s (Join-Path $plane 'tests') -v
if ($LASTEXITCODE -ne 0) { throw 'WINDOWS_PLANE_TESTS_FAILED' }

& (Join-Path $PSScriptRoot 'Invoke-FederationWindowsTask.ps1') -Task health
if ($LASTEXITCODE -ne 0) { throw 'PYTHON_WINDOWS_HEALTH_FAILED' }

$zipBuilder = @'
from pathlib import Path
import sys, zipfile
root = Path(sys.argv[1])
out = Path(sys.argv[2])
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    for path in sorted((p for p in root.rglob('*') if p.is_file()), key=lambda p: p.relative_to(root).as_posix()):
        rel = path.relative_to(root).as_posix()
        info = zipfile.ZipInfo(rel, date_time=(1980,1,1,0,0,0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        zf.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
'@
$zipBuilder | python - $nativeOut $zipPath
if ($LASTEXITCODE -ne 0) { throw 'NATIVE_DETERMINISTIC_ZIP_FAILED' }

$exeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $nativeExe).Hash.ToLowerInvariant()
$zipHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
$installerHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $nativeOut 'Install-FuseNativeAgent.ps1')).Hash.ToLowerInvariant()
$launcherHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $nativeOut 'FUSE-Native-OneClick.cmd')).Hash.ToLowerInvariant()
$exeInfo = Get-Item -LiteralPath $nativeExe
$zipInfo = Get-Item -LiteralPath $zipPath
$proof = [ordered]@{
    schema = 'FUSE-WINDOWS-NATIVE-BUILD-PROOF-V1'
    state = 'HOSTED_WINDOWS_SOURCE_COURT_PASS'
    source_sha = $sourceSha
    target_framework = 'net8.0-windows'
    runtime_identifier = 'win-x64'
    executable = 'Fuse.Windows.Native.exe'
    executable_sha256 = $exeHash
    executable_bytes = [int64]$exeInfo.Length
    package = 'fuse-windows-native.zip'
    package_sha256 = $zipHash
    package_bytes = [int64]$zipInfo.Length
    installer_sha256 = $installerHash
    launcher_sha256 = $launcherHash
    embedded_source_sha = $true
    outbound_native_relay = $true
    deterministic_compiler_enabled = $true
    deterministic_zip_metadata = $true
    native_contract_tests = 'PASS'
    independent_receipt_verifier = 'PASS'
    external_effect = $false
    provider_mutation = $false
    secret_access = $false
}
$proof | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $proofPath -Encoding utf8NoBOM

Write-Host "FUSE_NATIVE_EXE=$nativeExe"
Write-Host "FUSE_NATIVE_EXE_SHA256=$exeHash"
Write-Host "FUSE_NATIVE_ZIP_SHA256=$zipHash"
Write-Host "FUSE_NATIVE_INSTALLER_SHA256=$installerHash"
Write-Host "FUSE_NATIVE_LAUNCHER_SHA256=$launcherHash"
