$ErrorActionPreference = "Stop"

$projectRoot = $PSScriptRoot
$flashToolSource = Join-Path $projectRoot "flash_download_tool_3.9.7.exe"
$firmwareSource = Join-Path $projectRoot "CameraWebServer_STA_0x0.bin"
$configureSource = Join-Path $projectRoot "configure"

foreach ($required in @($flashToolSource, $firmwareSource, $configureSource)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required file or directory not found: $required"
    }
}

# Espressif Flash Download Tool can corrupt non-ASCII paths in its config.
# Stage everything in a stable ASCII-only directory before launching it.
$stageRoot = Join-Path $env:LOCALAPPDATA "ESP32S3CamFlashTool"
$stageConfigure = Join-Path $stageRoot "configure"
$stageEsp32S3 = Join-Path $stageConfigure "esp32s3"
New-Item -ItemType Directory -Path $stageEsp32S3 -Force | Out-Null

Copy-Item -LiteralPath $flashToolSource -Destination (Join-Path $stageRoot "flash_download_tool_3.9.7.exe") -Force
Copy-Item -LiteralPath $firmwareSource -Destination (Join-Path $stageRoot "CameraWebServer_STA_0x0.bin") -Force
Copy-Item -Path (Join-Path $configureSource "*") -Destination $stageConfigure -Recurse -Force

$firmwarePath = Join-Path $stageRoot "CameraWebServer_STA_0x0.bin"
$configPath = Join-Path $stageEsp32S3 "spi_download.conf"
if (-not (Test-Path -LiteralPath $configPath)) {
    throw "ESP32-S3 configuration not found after staging: $configPath"
}

$config = Get-Content -LiteralPath $configPath -Raw
$config = [regex]::Replace($config, '(?m)^file_sel0\s*=.*$', 'file_sel0 = 1')
$config = [regex]::Replace($config, '(?m)^file_path0\s*=.*$', "file_path0 = $firmwarePath")
$config = [regex]::Replace($config, '(?m)^file_flag0\s*=.*$', 'file_flag0 = True')
$config = [regex]::Replace($config, '(?m)^file_offset0\s*=.*$', 'file_offset0 = 0x0')
$config = [regex]::Replace($config, '(?m)^default_path\s*=.*$', "default_path = $stageRoot")
$config = [regex]::Replace($config, '(?m)^verify\s*=.*$', 'verify = True')
Set-Content -LiteralPath $configPath -Value $config -Encoding ASCII

$expectedHash = "561AEE1640ACBE2E30505281CE1F156E5387A5F1995C174A7AE7F92859295D8F"
$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $firmwarePath).Hash
if ($actualHash -ne $expectedHash) {
    throw "Firmware SHA-256 mismatch. Expected $expectedHash, got $actualHash"
}

Write-Host "Firmware verified: $actualHash"
Write-Host "Flash tool directory: $stageRoot"
Write-Host "The firmware row should be checked and its address should be 0x0."

$flashTool = Join-Path $stageRoot "flash_download_tool_3.9.7.exe"
Start-Process -FilePath $flashTool -WorkingDirectory $stageRoot

