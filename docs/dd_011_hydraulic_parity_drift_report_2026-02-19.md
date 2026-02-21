# DD-011 Report: Hydraulic Parity Drift Root Cause

Date: 2026-02-19 (local)

## Problem Statement

The dynamic model deviates strongly from the ChemSep-provided steady-state initialization, even when initialized with matching stage temperatures, pressures, compositions, and internal flow profiles. A representative symptom is upper-column vapor composition drift (for example, stage-2 `y_n_Butane` trending toward feed-like values), which should not occur under a parity-consistent startup.

## Primary Symptoms Observed

1. Large immediate tray mass residuals at or near `t=0` when geometry-driven hydraulics are active.
2. Upper-section composition drift away from expected ChemSep profile within minutes.
3. Drift persists even with major controllers disabled (open-loop tests), indicating a model-structure issue rather than controller-only behavior.
4. Distillate drum / top-section behavior becomes counterintuitive when coupled with pressure and condenser dynamics.
5. Multiple controller tuning attempts (pressure PV filtering, gain damping, MV slew limiting, residual-based gain scaling, and related PI retuning) produced no material improvement in this specific parity/drift failure mode.

## Evidence Summary

Key diagnostics from 2026-02-19:

- `logs/parity_probe_20260219_090332.csv`
- `logs/steady_state_residual_audit_20260219_090332.csv`
- `logs/stage_residual_breakdown_spec_profile_20260219_090332.csv`
- `logs/stage_residual_breakdown_default_20260219_090332.csv`

Parity probe results:

1. `A_default_hyd_energy_geom_on`: max tray residual about `2529.9 lbmol/h`
2. `B_spec_profile_geom_on`: max tray residual about `2553.8 lbmol/h`
3. `C_spec_profile_geom_off`: max tray residual about `0.1 lbmol/h` (near parity)
4. `D_spec_energy_geom_off`: max tray residual about `74.5 lbmol/h`

Interpretation:

- With geometry/hydraulic liquid outflow active, initialization parity breaks badly.
- With geometry-driven liquid hydraulic override disabled, profile parity is restored to near-zero residual.

## Underlying Cause

In `src/dynamic_distillation/column_rhs_v1.py`, internal `L_out_profile` and `V_out_profile` are initialized from ChemSep/Excel profiles and described as source-of-truth. However, when geometry is present, a Francis-weir hydraulic calculation overrides internal-stage liquid outflows (`L_out[i]` for stages 2..N-1).

This means the runtime can start from ChemSep inventories/compositions but with materially different internal liquid traffic than the supplied steady-state profile. That inconsistency introduces immediate convective imbalance and pushes the state off the intended operating point.

Observed example from parity output:

- Stage 2 in spec/profile with geometry on:
  - `L_in ~= 5952.48 lbmol/h`
  - `L_out ~= 3752.11 lbmol/h`
  - Net tray accumulation `~= +2001.94 lbmol/h`

This is sufficient to drive rapid composition profile distortion, including stage-2 vapor composition shifts.

## Why Controller Tuning Did Not Fix It

Controller tuning cannot resolve a structural convective mismatch created inside the RHS flow construction itself. In this case, the internal liquid traffic used by the dynamic equations departs from the ChemSep profile when hydraulics are active, so tuning pressure/level/composition loops only moderates symptoms and does not remove the root inconsistency. This is consistent with prior tracking in `DD-009` (no material convergence improvement from pressure-loop stabilization changes).

## Why This Also Affects Long-Run Steady Behavior

A ramp-in of hydraulics can reduce initial shock but does not solve the root mismatch if full hydraulic mode is not calibrated to the same steady state. Without a consistent end-state, the model will still drift as the blend approaches full hydraulic influence.

## Recommended Corrective Actions

1. Add an explicit runtime parity mode that keeps internal `L_out` profile-fixed during startup diagnostics and regression checks.
2. Separate hydraulic usage modes:
   - `diagnostic/parity`: no internal liquid-hydraulic override.
   - `dynamic/hydraulic`: allow override with calibrated transition.
3. If ramp-in is used, gate blend progression on residual thresholds (mass and energy). Pause or back off when residuals increase.
4. Calibrate full hydraulic liquid-flow predictions (geometry, weir parameters, density basis, holdups) so the resulting `L_out` matches the intended steady operating point.
5. Keep level-control inventory closure active during transition, but treat it as secondary stabilization, not root-cause correction.

## Involved Modules

Core runtime modules:

1. `src/dynamic_distillation/column_rhs_v1.py` (flow assembly, hydraulics override, mass/energy RHS)
2. `src/dynamic_distillation/dynamic_run_scaffold_v1.py` (controller loops, runtime wiring, CLI execution)
3. `src/dynamic_distillation/stage_hydraulics_francis_v1.py` (Francis-weir liquid outflow model)
4. `src/dynamic_distillation/column_spec_builder_v1.py` (geometry/spec construction from Excel inputs)
5. `src/dynamic_distillation/state_vector_layout_v1.py` (state packing/unpacking for trays/drum/sump)

Diagnostic/audit modules used to establish evidence:

1. `tools/steady_state_residual_audit.py`
2. `tools/stage_residual_breakdown_report.py`
3. `tools/stage_energy_residual_breakdown_report.py`

## Expected Outcome After Fix

When initialization and internal flows are parity-consistent:

1. Initial tray residuals should remain near zero.
2. Upper-section compositions should stay close to ChemSep values in early transient.
3. Any remaining drift should be attributable to intended dynamic disturbances or control actions, not structural flow inconsistency.
