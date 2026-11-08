# Gera dist\HoneyAnt.exe (Windows) com o PyInstaller 6.22.3. Veja o ADR 0011.
#
#   powershell -ExecutionPolicy Bypass -File infra\app\construir.ps1
#
# Precisa de:
#   infra\app\app-local.json          {"url": "https://<ip-elastico>"}  (fora do git)
#   %USERPROFILE%\.honeyant\ca\ca.crt  certificado PÚBLICO da CA (honeyant-certificados)
# A chave de acesso NUNCA entra no .exe: cada pessoa digita na primeira execução.
# O .exe gerado nunca vai para o repositório nem para Releases.

param(
    [string]$Config = "infra\app\app-local.json",
    [string]$Ca = (Join-Path $env:USERPROFILE ".honeyant\ca\ca.crt")
)
$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "..\.."))

if (-not (Test-Path $Config)) {
    Write-Error "Falta $Config. Copie infra\app\app-local.exemplo.json e ponha o IP elástico."
}
if (-not (Test-Path $Ca)) {
    Write-Error "Falta $Ca. Rode: uv run honeyant-certificados --ip <ip-elastico>"
}
# A URL precisa ser https:// com um IP de verdade (o exemplo tem <ip-elastico>): senão o
# .exe sai pronto e fica offline para sempre.
$url = (Get-Content $Config -Raw | ConvertFrom-Json).url
if ($url -notmatch '^https://\d{1,3}(\.\d{1,3}){3}(:\d+)?/?$') {
    Write-Error "URL inválida em ${Config}: '$url'. Use https://<ip-elastico>, com o IP de verdade."
}

Remove-Item -Recurse -Force build-app -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force build-app | Out-Null
Copy-Item $Config build-app\app.json
Copy-Item $Ca build-app\ca.crt

uv run --with pyinstaller==6.22.3 pyinstaller --noconfirm --clean `
    --onefile --console --name HoneyAnt `
    --specpath build-app `
    --collect-submodules uvicorn `
    --add-data "$PWD\docs\demo;docs\demo" `
    --add-data "$PWD\src\honeyant\painel\static;honeyant\painel\static" `
    --add-data "$PWD\src\honeyant\painel\login;honeyant\painel\login" `
    --add-data "$PWD\build-app\app.json;." `
    --add-data "$PWD\build-app\ca.crt;." `
    src\honeyant\apps\aplicativo.py
if ($LASTEXITCODE -ne 0) { Write-Error "o PyInstaller falhou" }

$exe = Get-Item dist\HoneyAnt.exe
"Pronto: $($exe.FullName) ($([math]::Round($exe.Length / 1MB, 1)) MB)"
