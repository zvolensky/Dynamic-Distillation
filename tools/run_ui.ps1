param(
    [int]$Port = 8501,
    [switch]$Detached
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = (Get-Command python -ErrorAction Stop).Source
$StdoutLog = Join-Path $RepoRoot "ui_streamlit_stdout.log"
$StderrLog = Join-Path $RepoRoot "ui_streamlit_stderr.log"

$env:PYTHONPATH = (Join-Path $RepoRoot "src")

$bootstrap = @'
import streamlit
print(streamlit.__version__)
'@
@"
$bootstrap
"@ | & $PythonExe - | Out-Null

$arguments = @(
    "-m",
    "streamlit",
    "run",
    "ui/streamlit_app.py",
    "--server.port",
    "$Port",
    "--server.headless",
    "true"
)

if ($Detached) {
    Start-Process `
        -FilePath $PythonExe `
        -ArgumentList $arguments `
        -WorkingDirectory $RepoRoot `
        -RedirectStandardOutput $StdoutLog `
        -RedirectStandardError $StderrLog | Out-Null
    Write-Host "Streamlit UI started in the background on http://localhost:$Port"
    Write-Host "stdout: $StdoutLog"
    Write-Host "stderr: $StderrLog"
}
else {
    Set-Location $RepoRoot
    & $PythonExe @arguments
}
