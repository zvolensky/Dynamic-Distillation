$ErrorActionPreference = "Stop"

$simulationPid = 33752
$runDirectory = $PSScriptRoot
$repository = (Resolve-Path -LiteralPath (Join-Path $runDirectory "..\..")).Path
$watchLog = Join-Path $runDirectory "word_report_watcher.log"
$renderScript = "C:\Users\Thomas Zvolensky\.codex\plugins\cache\openai-primary-runtime\documents\26.630.12135\skills\documents\render_docx.py"

try {
    "[watcher] waiting for simulation PID $simulationPid at $((Get-Date).ToString('o'))" |
        Set-Content -LiteralPath $watchLog -Encoding utf8
    Wait-Process -Id $simulationPid -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 5
    "[watcher] simulation ended at $((Get-Date).ToString('o'))" |
        Add-Content -LiteralPath $watchLog

    $metadata = Get-ChildItem -LiteralPath $runDirectory -Filter "run_metadata_*.json" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $metadata) {
        throw "Run metadata was not found."
    }

    Set-Location -LiteralPath $repository
    $env:PYTHONPATH = Join-Path $repository "src"
    & python -c "from dynamic_distillation.run_report_v1 import generate_run_report; import sys; print(generate_run_report(sys.argv[1]))" $metadata.FullName *>> $watchLog
    if ($LASTEXITCODE -ne 0) {
        throw "Word report generation exited with code $LASTEXITCODE."
    }

    $report = Get-ChildItem -LiteralPath $runDirectory -Filter "run_report_*.docx" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if (-not $report) {
        throw "Word report was not created."
    }

    $qaDirectory = Join-Path $runDirectory "word_report_render_qa"
    & python $renderScript $report.FullName --output_dir $qaDirectory --emit_pdf *>> $watchLog
    if ($LASTEXITCODE -ne 0) {
        throw "Word report rendering exited with code $LASTEXITCODE."
    }

    "[watcher] report and render complete at $((Get-Date).ToString('o'))" |
        Add-Content -LiteralPath $watchLog
}
catch {
    "[watcher] ERROR at $((Get-Date).ToString('o')): $($_.Exception.Message)" |
        Add-Content -LiteralPath $watchLog
    exit 1
}
