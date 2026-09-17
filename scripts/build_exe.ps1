$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.build-venv/Scripts/python.exe')) {
    python -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed' }
}
& '.build-venv/Scripts/python.exe' -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed' }
& '.build-venv/Scripts/python.exe' -m PyInstaller --noconfirm --onefile --name I-HSTMO-India --add-data 'web:web' --add-data 'data/processed:data/processed' --add-data 'outputs/model.json:outputs' --add-data 'outputs/evaluation.json:outputs' run.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed' }
Write-Output 'Executable: dist/I-HSTMO-India.exe'
