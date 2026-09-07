$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$runDir = Join-Path $repo "logs\core_v3_water_methanol_dual_level_control_feed_step_5pct_1800s_20260908"
$inputs = @(
    "logs/core_v3_water_methanol_partial_hydraulic_root_20260901.json",
    "logs/core_v3_water_methanol_partial_hydraulic_root_20260901.npz",
    "water_methanol_template_10stage_chemsep_excess_enthalpy_p14p7_to_p17p7_geometry_20260713.xlsx"
)

New-Item -ItemType Directory -Force -Path $runDir | Out-Null
$statusPath = Join-Path $runDir "scheduler_status.json"
$started = Get-Date
$exitCode = $null
$errorText = $null

try {
    git -C $repo restore --source=579cc63^1 --worktree -- $inputs
    Push-Location $repo
    try {
        & python tools\run_core_v3_water_methanol_dual_level_control.py `
            --duration-sec 1800 `
            --feed-multiplier 1.05 `
            --json (Join-Path $runDir "result.json") `
            --doc (Join-Path $runDir "report.md") `
            --matrix (Join-Path $runDir "trajectory.npz") `
            *> (Join-Path $runDir "console.txt")
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
catch {
    $exitCode = 1
    $errorText = $_.Exception.ToString()
    $errorText | Set-Content -Encoding utf8 (Join-Path $runDir "scheduler_error.txt")
}

[ordered]@{
    started_edt = $started.ToString("o")
    finished_edt = (Get-Date).ToString("o")
    exit_code = $exitCode
    error = $errorText
    result_json = (Join-Path $runDir "result.json")
} | ConvertTo-Json | Set-Content -Encoding utf8 $statusPath

exit $exitCode
