# Unit-K Quarantine Follow-Up

Date: 2026-07-09

## Context

After the unit-K quarantine patch, the Q42 fixed-condenser-duty run can pass the dynamic steady-state gate, but it relaxes from a near-Excel operating point at 300 s to a low-overhead operating point at 1800 s.

An external review suggested that the top boundary is likely a downstream symptom and that the core problems are:

- frequent unit-K thermo refresh failures/quarantine,
- a large vapor traffic cliff around stages 17 to 16,
- and stale thermo/K targets contributing to K-state drift.

## Confirmed From Current Logs

Run inspected:

- `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_unitKquarantine_1800s_20260709`

### Quarantine Frequency

The quarantine is not occasional. It fires persistently across much of the column.

| Stage | Logged rows | Quarantine rows | Fraction |
|---:|---:|---:|---:|
| 3 | 91 | 85 | 0.934 |
| 4 | 91 | 84 | 0.923 |
| 5 | 91 | 44 | 0.484 |
| 11 | 91 | 46 | 0.505 |
| 16 | 91 | 44 | 0.484 |
| 17 | 91 | 53 | 0.582 |
| 18 | 91 | 69 | 0.758 |
| 19 | 91 | 77 | 0.846 |

This means the defensive quarantine patch is masking a persistent thermo refresh failure, not just rare numerical edge cases.

### Stage 17-to-16 Vapor Cliff

At final time:

- stage 17 `V_out = 7019.4 lbmol/h`
- stage 16 `V_out = 4974.3 lbmol/h`
- adjacent drop = `2045.1 lbmol/h`

The energy-vapor-flow terms show why stage 16 is low:

- stage 16 `hL_in - hL_out = -943 BTU/lbmol`
- stage 16 liquid enthalpy term = `-3366 BTU/s`
- this negative liquid term suppresses the stage 16 vapor solve.

This points to a vapor/energy/enthalpy consistency issue in the lower-middle column, not a pure condenser or distillate-controller issue.

### K-State Drift Alignment

A fresh K-state drift audit was generated:

- `logs/k_state_drift_unitKquarantine_1800s_20260709.json`
- `logs/k_state_drift_unitKquarantine_1800s_20260709.md`

Key results:

- final max `|K_state - K_thermo| = 1.108`
- peak max `|K_state - K_thermo| = 1.731`
- final worst stage = 11, n-Pentane
- peak/worst trend is dominated by stages 3-5, n-Pentane

The worst K drift overlaps the stages with the heaviest quarantine:

| Stage | Quarantine fraction | Max abs K diff | Worst component |
|---:|---:|---:|---|
| 3 | 0.934 | 1.731 | n-Pentane |
| 4 | 0.923 | 1.662 | n-Pentane |
| 5 | 0.484 | 1.599 | n-Pentane |

This supports the stale-thermo-target hypothesis: K drift is at least partly driven by thermo packets being held stale by repeated unit-K quarantine.

## Updated Priority

1. Investigate why the thermo provider or its call inputs return unit-K so often.
2. Audit the stage 17-to-16 vapor/energy interface directly.
3. Treat top-boundary reflux/distillate infeasibility as downstream until overhead vapor traffic is restored.
4. Keep the unit-K quarantine patch as a defensive guard, but do not treat it as a physically complete fix.

## Current Engineering Interpretation

The model is not simply under-tuned at the top. The top drum is starved because the interior column is not delivering Excel-level overhead vapor. The current dynamic pass is therefore a numerically quiet but wrong operating state.
