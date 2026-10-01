param([switch]$Cuda,[string]$BuildDir="build")
$ErrorActionPreference="Stop"
Set-Location "$PSScriptRoot\.."
if(-not (Get-Command cmake -ErrorAction SilentlyContinue)){throw "CMake not found"}
if(-not (Get-Command git -ErrorAction SilentlyContinue)){throw "Git not found"}
$cudaArg="-DGGML_CUDA=OFF"
if($Cuda -or (Get-Command nvcc -ErrorAction SilentlyContinue)){$cudaArg="-DGGML_CUDA=ON"}
cmake -S . -B $BuildDir -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF $cudaArg
cmake --build $BuildDir --config Release -j
New-Item -ItemType Directory -Force dist | Out-Null
$runtime=@("$BuildDir\Release\FUSE-LocalLLM.exe","$BuildDir\FUSE-LocalLLM.exe")|?{Test-Path $_}|Select -First 1
$desktop=@("$BuildDir\Release\FUSE-LocalLLM-Desktop.exe","$BuildDir\FUSE-LocalLLM-Desktop.exe")|?{Test-Path $_}|Select -First 1
if(!$runtime -or !$desktop){throw "Expected Windows product binaries not found"}
Copy-Item $runtime dist\FUSE-LocalLLM.exe -Force
Copy-Item $desktop dist\FUSE-LocalLLM-Desktop.exe -Force
$receipt=[ordered]@{
 schema="FUSE-LOCAL-LLM-DESKTOP-BUILD-RECEIPT-V1";version="0.2.0";
 llama_cpp_commit="60081bb2b5b3294165a4d67c5cbeebe74c868014";cuda=($cudaArg -eq "-DGGML_CUDA=ON");
 runtime_sha256=(Get-FileHash dist\FUSE-LocalLLM.exe -Algorithm SHA256).Hash.ToLower();
 desktop_sha256=(Get-FileHash dist\FUSE-LocalLLM-Desktop.exe -Algorithm SHA256).Hash.ToLower();
 built_at=(Get-Date).ToString("o")
}
$receipt|ConvertTo-Json|Set-Content dist\BUILD_RECEIPT.json -Encoding UTF8
$receipt|ConvertTo-Json
