$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    $pythonCmd = "py"
    $pythonArgs = @("-3")
} else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python is needed only on this build computer."
    }
    $pythonCmd = "python"
    $pythonArgs = @()
}

$oldErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $pythonCmd @pythonArgs -m PyInstaller --version *> $null
$pyInstallerExit = $LASTEXITCODE
$ErrorActionPreference = $oldErrorActionPreference

if ($pyInstallerExit -ne 0) {
    Write-Host "Installing PyInstaller on this build computer..."
    & $pythonCmd @pythonArgs -m pip install --upgrade pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install PyInstaller."
    }
}

Write-Host "Building 3cx_bridge.exe..."
& $pythonCmd @pythonArgs -m PyInstaller --clean --onefile --name 3cx_bridge 3cx_bridge.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$exe = Join-Path $PSScriptRoot "dist\3cx_bridge.exe"
Copy-Item $exe (Join-Path $PSScriptRoot "3cx_bridge.exe") -Force
$portable = Join-Path $PSScriptRoot "portable-crm-windows"
if (Test-Path $portable) {
    Copy-Item $exe (Join-Path $portable "3cx_bridge.exe") -Force
}
Write-Host ""
Write-Host "Done. Standalone service (no Python needed):"
Write-Host "  $exe"
