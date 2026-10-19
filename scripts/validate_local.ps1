$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskPython = Join-Path $taskRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPython)) { throw 'Create .venv and install requirements.txt first.' }
$env:PYTHONIOENCODING = 'utf-8'
Push-Location -LiteralPath $taskRoot
try {
    & $taskPython -m compileall -q main.py src scripts tests
    if ($LASTEXITCODE -ne 0) { throw 'Python compilation failed.' }
    & $taskPython -m unittest discover -s tests -p 'test*.py'
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & $taskPython scripts/check_docker.py
    if ($LASTEXITCODE -eq 2) { Write-Warning 'Python tests passed; Docker acceptance remains BLOCKED.' }
    elseif ($LASTEXITCODE -ne 0) { throw 'Docker acceptance failed.' }
}
finally { Pop-Location }
