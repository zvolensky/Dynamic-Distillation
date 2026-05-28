# Dynamic Column Initialization Strategy

Date: 2026-05-28

## Position

ChemSep steady-state results are valuable initialization data, but they are not a guaranteed dynamic initial condition for this model.

Use ChemSep/Excel values as a high-quality estimate for:
- components and thermo basis,
- approximate `T/P/x/y/L/V` profiles,
- product rates and duties,
- geometry and holdup scale.

The dynamic model must then convert that estimate into a state that is self-consistent with its own topology, holdup states, feed treatment, thermodynamics, and RHS equations.

## Why This Matters

An imported steady profile comes from another solver's mathematical topology. It can be perfectly steady in ChemSep and still be non-steady here if any of these differ:
- explicit reflux drum or bottom sump states,
- terminal condenser/reboiler interpretation,
- feed split basis,
- tray vapor holdup states,
- pressure/vapor-flow closure,
- energy states,
- thermo backend or binary parameters.

The recent C3/C4 diagnostic confirmed this. Freezing tray vapor derivatives allowed the steady-state detector to pass, but liquid compositions drifted far outside validation tolerance. That means numerical quiet is not the same thing as a valid initialized column.

## Initialization Contract

The workbook supplies a seed. The runner/initializer is responsible for making that seed dynamic-ready.

Accepted uses of ChemSep results:
- source-topology material-balance parity when our topology is intentionally reduced to match ChemSep/source assumptions,
- initial guesses for a model-topology steady initializer,
- reference profiles for comparison after topology and thermo differences are reconciled.

Not accepted:
- treating raw ChemSep `L/V/x/y` as final truth for full dynamic runs with explicit vapor holdups and boundary vessels,
- forcing a run to pass by freezing or disabling physics that the validation claim depends on,
- accepting `steady_state_flag=1` without profile/conservation checks.

## Recommended Workflow

1. **Source Import**
   - Load ChemSep/Excel `T/P/x/y/L/V`, duties, products, geometry, and estimated holdups.
   - Preserve the original source profile for audit and comparison.

2. **Topology Reconciliation**
   - Convert terminal condenser/reboiler/source-stage assumptions into this model's explicit top drum, bottom sump, and reboiler mappings.
   - Reconcile product draws and feed split assumptions before marching.

3. **Initialization Residual Audit**
   - Evaluate `column_rhs_v1.py` at `t=0`.
   - Report residuals by block: `tray_L`, `tray_V`, `top_L/top_V`, `bottom_L/bottom_V`, energy/temperature, pressure/vapor-flow, and feed-stage terms.
   - Use this to decide whether the remaining problem is structural or solvable.

4. **Sequential Dynamic-Consistency Solve**
   - Avoid a giant full-state Newton solve first.
   - Start with a narrow variable set, such as vapor compositions/holdups and boundary vessel states.
   - Add liquid composition, feed split, pressure/vapor-flow, and energy variables only when diagnostics prove they are needed.
   - Keep normalization, nonnegativity, and profile-deviation penalties explicit.

5. **Open-Loop Settle**
   - Run a short open-loop settle only after algebraic residuals are already small.
   - Controllers should be disabled until the plant model itself has a quiet baseline.

6. **Golden Seed Serialization**
   - Save accepted initialized states, thermo packets, hydraulic memory, and controller memory.
   - Use serialized seeds for disturbance and controller studies so every run starts from the same verified baseline.

## Acceptance Gates

An initialized state is accepted only if all relevant gates pass:
- low full-state derivatives by block, not just a low aggregate score,
- low `tray_V` residuals when vapor states are enabled,
- low `tray_L` residuals and no compensating liquid/vapor leakage,
- global and stage material closure,
- energy closure when energy states are enabled,
- pressure and vapor-flow diagnostics are physically reasonable,
- bounded drift from the intended source/seed profile,
- source/reference KPI comparison remains acceptable when the case is being used for validation.

`steady_state_flag=1` is useful diagnostic evidence. It is not sufficient by itself.

## Near-Term Implementation Plan

Use the C3/C4 case as the fast development case.

Recommended first tools:
- `tools/column_initialization_residual_audit.py`
- `tools/reconcile_column_vapor_closure_seed.py`

The first tool should decompose the initial RHS residuals. The second should attempt a narrow, bounded vapor-closure reconciliation. Only after those pass should the state be serialized as a golden seed.

Related issues:
- `DD-030`: Gani/ChemSep model-topology reconciliation.
- `DD-031`: profile-flow parity conflict with explicit tray vapor states.
- `DD-032`: dynamic initialization cannot rely on raw ChemSep profiles as full model-consistent initial conditions.
