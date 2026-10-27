# PowerShell launcher for CallCenter CRM v2
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$port = 8000
$url = "http://127.0.0.1:$port"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Starting CallCenter CRM v2.0 (Multilingual)" -ForegroundColor Green
Write-Host "   Access URL: $url" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

Start-Process $url

$pythonCandidates = @(
    "python",
    "py",
    "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
    "$env:ProgramFiles\Python313\python.exe",
    "$env:ProgramFiles\Python312\python.exe"
)

foreach ($py in $pythonCandidates) {
    if (Get-Command $py -ErrorAction SilentlyContinue) {
        Write-Host "Using Python: $py" -ForegroundColor Gray
        & $py app.py
        exit
    }
    if (Test-Path $py) {
        Write-Host "Using Python: $py" -ForegroundColor Gray
        & $py app.py
        exit
    }
}

Write-Error "Python executable not found. Please install Python 3.9+."
