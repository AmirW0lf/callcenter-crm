$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    $pythonCmd = "py"
    $pythonArgs = @("-3")
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python is needed only on this build computer. Install Python here, build the portable CRM once, then copy the output folder to agent PCs."
    }
    $pythonCmd = "python"
    $pythonArgs = @()
}

Write-Host "Checking PyInstaller..."
$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $pythonCmd @pythonArgs -m PyInstaller --version *> $null
$pyInstallerExit = $LASTEXITCODE
$ErrorActionPreference = $oldErrorActionPreference

if ($pyInstallerExit -ne 0) {
    Write-Host "Installing PyInstaller on this build computer..."
    & $pythonCmd @pythonArgs -m pip install --upgrade pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install PyInstaller. Check internet connection, then run: py -3 -m pip install --upgrade pyinstaller"
    }
}

Write-Host "Building CallCenterCRM.exe..."
& $pythonCmd @pythonArgs -m PyInstaller --clean --onefile --name CallCenterCRM app.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$packageDir = Join-Path $PSScriptRoot "portable-crm-windows"
if (Test-Path $packageDir) {
    Remove-Item $packageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $packageDir | Out-Null

# Copy the main executable
Copy-Item (Join-Path $PSScriptRoot "dist\CallCenterCRM.exe") (Join-Path $packageDir "CallCenterCRM.exe")

# Copy the launcher script
Copy-Item (Join-Path $PSScriptRoot "start-portable-crm.bat") (Join-Path $packageDir "start-crm.bat")

# Copy database (if exists)
if (Test-Path (Join-Path $PSScriptRoot "crm.sqlite3")) {
    Copy-Item (Join-Path $PSScriptRoot "crm.sqlite3") (Join-Path $packageDir "crm.sqlite3")
}

# Copy asset files needed at runtime (app.css is served via /static/app.css)
$assetFiles = @("app.css", "flatpickr.min.css", "flatpickr.min.js", "flatpickr-fa.js")
foreach ($file in $assetFiles) {
    $src = Join-Path $PSScriptRoot $file
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $packageDir $file)
        Write-Host "  Copied: $file"
    } else {
        Write-Host "  WARNING: $file not found, skipping."
    }
}

Write-Host ""
Write-Host "Done. Copy this folder to the agent/server PC:"
Write-Host "  $packageDir"
Write-Host "Contents:"
Get-ChildItem $packageDir | ForEach-Object { Write-Host "  - $($_.Name)" }
Write-Host ""
Write-Host "Agents run start-crm.bat. They do not need Python installed."
