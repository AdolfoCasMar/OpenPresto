param([string]$Archivo)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Falta el entorno virtual. Sigue la preparación indicada en README.md.'
}
Push-Location -LiteralPath $projectRoot
try {
    if ($Archivo) { & $pythonPath -m openpresto $Archivo }
    else { & $pythonPath -m openpresto }
} finally { Pop-Location }
