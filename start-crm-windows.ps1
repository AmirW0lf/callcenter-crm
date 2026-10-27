$ErrorActionPreference = "Stop"

Set-Location -LiteralPath $PSScriptRoot

$env:CRM_HOST = "0.0.0.0"
$env:CRM_PORT = "8000"
$localUrl = "http://127.0.0.1:$env:CRM_PORT"

Write-Host $localUrl

Start-Process $localUrl

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 app.py
} else {
    python app.py
}
