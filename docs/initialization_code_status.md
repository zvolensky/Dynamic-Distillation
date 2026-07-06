# Initialization Code Status

Updated: 2026-07-06

This note classifies the current initialization-related code after the ChemSep steady-state startup work showed that raw steady profiles are not model-consistent dynamic initial conditions.

## Position

ChemSep and other steady-state exports are seed data, not accepted dynamic initial states.

Do not claim that a full-topology dynamic case is initialized only because a run starts, a steady-state flag turns on, or a diagnostic path suppresses derivatives. A valid initialized state must pass the active model's residual gates with the same topology, thermo, boundary states, vapor states, energy states, and feed treatment that the later dynamic run will use.

## Supported

These tools and paths remain part of the intended workflow.

| Item | Status | Purpose |
|---|---|---|
| `tools/column_initialization_residual_audit.py` | Supported | First gate for imported or generated seeds. Evaluates `column_rhs_v1.py` at `t=0` and ranks state-rate, material, and energy residuals. |
| `tools/initialize_column_model_consistent_seed.py` | Supported workflow, pending accepted seed | Repeatable initializer orchestration: audits the input, runs named coupled reconciliation candidates, audits each candidate, selects the best workbook by explicit criteria, and writes a summary. Current named candidates include coupled tray/top-boundary reconciliation and bottom-boundary-balanced continuation. |
| Top-boundary diagnostics in `column_rhs_v1.py` | Supported | Reports reflux-drum liquid splits such as `top_L_cond_in_*`, `top_L_reflux_out_*`, `top_L_distillate_out_*`, and `top_L_net_*`. |
| Source-topology validation flags | Supported for validation only | `--disable-boundary-states`, `--disable-vapor-states`, and `--no-equilibrium` remain valid when deliberately matching a source model such as Skogestad Column A or the narrow Gani/ChemSep material-parity case. |
| Total-condenser dry-boundary routing | Supported | A dry stage-1 total-condenser placeholder should route condensate using the actual condensed stream mixture, not a stale tray-liquid composition. |

## Experimental

These are useful research tools, but their outputs are not accepted golden seeds by themselves.

| Item | Status | Current Interpretation |
|---|---|---|
| `tools/optimize_column_initialization_residual.py` | Experimental diagnostic | Useful for testing which degrees of freedom reduce residuals. It has not produced an accepted full-topology seed. |
| `tools/reconcile_column_vapor_closure_seed.py` | Experimental diagnostic | Helpful for understanding explicit vapor-state closure defects; not a production initializer. |
| `tools/reconcile_column_liquid_energy_seed.py` | Experimental diagnostic | Fast and informative for scoped liquid/energy objectives; does not by itself control explicit vapor-state waves. |
| `tools/solve_pressure_flow_closure.py` | Experimental diagnostic | Pressure-flow closure is necessary but insufficient without vapor composition, vapor inventory, and energy consistency. |
| `tools/optimize_column_profile_coefficients.py` | Experimental diagnostic | Smooth profile corrections are better behaved than local windows but have not exposed the missing closure alone. |
| `--runtime-mode total-reflux` | Experimental startup recipe | Mechanically viable and useful for probes, but not an accepted shortcut to a golden seed for the current C3/C4 case. |
| `--enable-startup-vapor-homotopy` | Experimental startup transition | Useful infrastructure for later vapor-closure transitions; current evidence shows the C3/C4 failure can occur before vapor beta activates. |
| `--startup-total-reflux-washout-sec` | Experimental diagnostic | Helps test reflux-drum washout behavior; short and 300 s washout probes did not produce an accepted seed. |

## Deprecated For Acceptance

These paths may remain temporarily for comparison, but they must not be used as evidence of rigorous initialization.

| Item | Status | Reason |
|---|---|---|
| Raw ChemSep profile marching | Deprecated | Raw `T/P/x/y/L/V` profiles can be steady in ChemSep and non-steady under this model's explicit boundary, vapor, pressure, and energy equations. |
| Freezing tray vapor derivatives as an acceptance path | Deprecated | It can make derivative metrics look quiet while liquid/composition profiles drift outside validation tolerance. |
| Local-only profile nudging without interface/global penalties | Deprecated for acceptance | Prior trials moved residuals inward rather than eliminating them. |
| Treating `steady_state_flag` as validation | Deprecated | The flag is diagnostic only. Validation requires source comparison or explicit case-specific residual/KPI gates. |

## Current Next Direction

Use the explicit initializer workflow before adding more broad initializer heuristics.

Near-term work should focus on making `tools/initialize_column_model_consistent_seed.py` produce an accepted seed:

- keep ChemSep or other steady-state exports as guesses only,
- solve coupled tray vapor/liquid/energy and top-boundary residuals with one repeatable command,
- keep interior corrections smooth with generic continuity penalties instead of hard local tray windows,
- include bottom-boundary state and flow degrees of freedom when the audit is dominated by `bottom_L`,
- select candidates by explicit residual metrics rather than by manual inspection,
- cap expensive optimizer probes gracefully so partial best-seen candidates are still audited and labeled,
- require the selected workbook or checkpoint to pass the active residual audit before using it as a dynamic launch seed.

If a tool writes a new workbook or checkpoint, it should be called an experimental or diagnostic seed until it passes the active residual audit and a short dynamic launch with hidden re-entry conditioning disabled.
