# DD-011 Report: Hydraulic Parity Drift Root Cause

Date: 2026-02-19 (local)

Status addendum: 2026-02-23 (local)

## Problem Statement

The dynamic model deviates strongly from the ChemSep-provided steady-state initialization, even when initialized with matching stage temperatures, pressures, compositions, and internal flow profiles. A representative symptom is upper-column vapor composition drift (for example, stage-2 `y_n_Butane` trending toward feed-like values), which should not occur under a parity-consistent startup.

## Executive Summary (2026-02-23)

This is the current high-level DD-011 status.

Current status:
1. The model no longer shows an immediate startup blow-up in the corrected overhead-capacitance case.
2. It remains off parity over time; dominant divergence appears later, not at `t=0`.
3. The highest-impact instability window is in stages 16-18 around `~90-112 s`, followed by late pressure-loop chatter.

Most recent evidence run:
1. Case/workbook: `distillation_column_template_overhead_caps.xlsx`
2. Runtime: `legacy`, `dt=0.2 s`, `300 s`, `log-every=1`
3. Controllers ON: level + pressure (`MV=condenser-duty`) + distillate composition + bottoms composition
4. Logs:
   - `logs/overhead_totalcond_ctrl_on/column_summary_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/column_profile_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/overall_derivative_metrics_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/stage_derivative_metrics_20260223_133146.csv`
   - `logs/overhead_totalcond_ctrl_on/startup_t_p_l_v_ml_mv_derivatives_20260223_133146.csv`

Key numbers:
1. Max tray mass residual (0..300 s): `7263.26 lbmol/h` (stage 18, `t~94.6 s`).
2. Top pressure drift: `220.44 -> 236.92 psia` (`+16.48 psia` in 300 s).
3. Peak hydraulic-rate derivatives:
   - `|dL_out_hyd/dt|`: `2818.70 lbmol/h/s` (stage 16, `t~89.4 s`)
   - `|dV_out/dt|`: `334.66 lbmol/h/s` (stage 18, `t~112.2 s`)
4. Startup derivatives are elevated but moderate on a relative basis:
   - `t=0.0 s`: max `|dL/dt|=819.84`, max `|dV/dt|=129.13`
   - `0.0->0.2 s` relative change: liquid max about `1.01%`, vapor max about `0.34%`

Interpretation:
1. Startup mismatch is no longer the main failure signal.
2. The root mechanism remains structural hydraulic/pressure/vapor coupling.
3. Controllers contribute but are not the sole driver.
4. Startup sequence testing exists historically, but not yet as an apples-to-apples re-test on the corrected 2026-02-23 case.

## Current State Addendum (2026-02-23)

Latest high-frequency diagnostics (corrected ChemSep-aligned case, controllers on, `dt=0.2 s`, `log-every=1`) are in:

1. `logs/overhead_totalcond_ctrl_on/column_summary_20260223_133146.csv`
2. `logs/overhead_totalcond_ctrl_on/column_profile_20260223_133146.csv`
3. `logs/overhead_totalcond_ctrl_on/overall_derivative_metrics_20260223_133146.csv`
4. `logs/overhead_totalcond_ctrl_on/stage_derivative_metrics_20260223_133146.csv`
5. `logs/overhead_totalcond_ctrl_on/startup_t_p_l_v_ml_mv_derivatives_20260223_133146.csv`

Key updates:

1. Startup rates are elevated but not catastrophic relative to profile scale:
   - At `t=0.0 s`, max `|dL/dt| ~= 819.84 lbmol/h/s` (stage 19), max `|dV/dt| ~= 129.13 lbmol/h/s` (stage 12).
   - Startup relative flow change (`0.0 -> 0.2 s`) is modest: liquid max about `1.01%` and vapor max about `0.34%`.
2. The larger divergence develops later (not at startup):
   - Max tray mass residual (0..300 s) about `7263.26 lbmol/h` at stage 18 around `94.6 s`.
   - Peak hydraulic slew occurs around stages 16-18:
     - max `|dL_out_hyd/dt| ~= 2818.70 lbmol/h/s` (stage 16, `~89.4 s`)
     - max `|dV_out/dt| ~= 334.66 lbmol/h/s` (stage 18, `~112.2 s`)
3. Pressure-loop interaction remains a late amplifier:
   - `P_top` drifts from `220.44` to `236.92 psia` (`+16.48 psia` in 300 s).
   - Late-window condenser-duty chatter is large (`~ -50.8` to `-54.2 MMBtu/h`, 290-300 s).
4. Interpretation update:
   - The root-cause statement remains valid (hydraulic-mode structural coupling dominates).
   - Current evidence indicates the main destabilizing window is mid-run hydraulic acceleration and pressure-MV chatter, not a gross `t=0` initialization shock.
5. Startup hydraulic sequencing was previously tested, but those tests were on older workbook/sign settings; it has not yet been re-run apples-to-apples on the corrected 2026-02-23 case.

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
