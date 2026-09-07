# Model-Consistent Initialization Summary

- Input: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx`
- Selected output: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke2_20260708.xlsx`
- Execution log: `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke2_20260708\initializer_c3c4_orchestrator_end_to_end_smoke2_20260708_134153.log`
- Selection mode: `max-rate`
- Gate pass: `False`
- Clean usable assessment: `usable=False; basis=residual_and_dynamic_gate; reason=residual gate failed`
- Accepted artifact: `status=diagnostic_only; kind=workbook; path=C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke2_20260708.xlsx`
- Checkpoint reload gate: `enabled=True; passed=None; reason=skipped because candidate is not clean usable`
- Worst relative rate: `0.053786702 1/s`
- Max tray total residual: `639.56157 lbmol/h`

## Restart Command

```powershell
C:\Python314\python.exe -m dynamic_distillation.dynamic_run_scaffold_v1 --excel 'C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke2_20260708.xlsx' --runtime-mode hydraulic --thermo table --condenser-duty-mode total-condense --n-steps 5 --dt 0.2 --log-every 5 --logs-dir 'C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke2_20260708\accepted_artifact_restart' --allow-repeat-command --include-energy --use-excel-vapor-holdup --no-equilibrium --no-flash-feed-at-stage-conditions --disable-startup-thermo-conditioning --disable-restart-reentry-settling
```

## Candidates

| Candidate | Gate | Max rel 1/s | Max tray total lbmol/h | Workbook |
|---|---:|---:|---:|---|
| `coupled-vle-topL` | `False` | 0.053786702 | 639.56157 | `C:\Users\Thomas Zvolensky\Documents\Python Scripts\Dynamic_DistillationII\logs\initializer_orchestrator_end_to_end_smoke2_20260708\coupled-vle-topL.xlsx` |
