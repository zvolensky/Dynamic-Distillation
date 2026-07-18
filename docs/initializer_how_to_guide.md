# Initializer Implementation Guide

Updated: 2026-07-17

Current model status: `docs/dynamic_model_current_state_2026-07-12.md`.

## Objective

This document describes the recommended implementation approach for building a robust dynamic initializer for the column model. The goal is to convert a steady-state seed into a dynamically acceptable initial state at $t=0$.

## Core Principle

A steady-state profile from ChemSep or Excel is only a seed. It is not automatically a valid dynamic initial condition for this model because the dynamic system includes explicit vapor states, pressure dynamics, energy balances, and boundary coupling.

The initializer should therefore be treated as two ordered mathematical
problems, not as a simple import-and-run step:

1. place the selected conserved state on the algebraic constraint manifold;
2. only then solve for a steady state by driving the required differential
   inventory and energy rates toward zero.

The initializer cannot repair an internally inconsistent runtime equation set.
Before pursuing zero differential residuals, verify that pressure, phase
totals, energy, hydraulic flow, and terminal inventories have unique and
compatible owners. DD-065 showed that the current C3/C4 checkpoint can pass
interior local UV closure while failing the global pressure/vapor-flow closure.
DD-066 completed terminal inventory accounting, then showed that frozen top
and bottom terminal UV assemblies imply reversed pressure ordering. Until a
globally conservative redistribution solve corrects that global and terminal
incompatibility, initializer optimization is diagnostic and operational
checkpoints are not rigorous golden seeds.

DD-067 demonstrates that conservative movement can repair the ordering at the
local UV level: fixed component inventories and redistributed internal energy
produced an ordered 20-node profile with exact whole-column conservation.
However, that pressure-isotonic construction moved `9.32%` of the checkpoint
energy inventory on an L1 basis and excluded hydraulics. It is an existence
proof, not an accepted seed. DD-068 therefore minimized scaled `Delta N` and
`Delta U` directly before considering the hydraulic network.

DD-068 completed that next diagnostic. A normalized L2 `Delta N`/`Delta U`
solve found the same local objective from the checkpoint and a moderate
random start, but three of five starts failed. The candidate moved more energy
than DD-067, retained a `79.159 psi` maximum pressure correction, and placed
`80.3%` of absolute energy movement in the terminal assemblies. Do not add
hydraulics to this state. Audit terminal energy ownership, fixed volumes,
vapor spaces, and `U=H-PV` conversion first. The controller degree-of-freedom
audit already passed in DD-065 and is not an open item.

DD-069 completed that basis audit. The `PV` conversion, phase aggregation,
mapped-U provenance, and empty placeholder pass. The sump and representative
interior phase volumes do not reproduce their mapped fixed volumes, stored
checkpoint enthalpy does not reproduce live DWSIM TP enthalpy, and DD-068's
node-local energy scaling makes equal terminal movement hundreds to thousands
of times cheaper than interior movement.

DD-070 completed the one corrected repeat. It used live-property canonical
internal energy, neutral whole-column scales, and a liquid-only sump volume.
Movement and pressure correction improved substantially, but only one of five
starts converged and the checkpoint enthalpy mismatch remained
state-dependent. Checkpoint repair is retired. The next initializer must solve
the conserved steady state directly from operating specifications; the
checkpoint and imported profiles are initial guesses, not conserved targets.

## Recommended Workflow

1. Load the seed.
   - Import the external steady-state profile as a reference seed.
   - Preserve the original values for audit and comparison.

2. Reconcile topology.
   - Map the seed onto the model's actual topology.
   - Reconcile tray indexing, feed stage, condenser/reboiler interpretation, and boundary equipment mapping.

3. Build an initial state vector.
   - For legacy restart mode, populate the existing packed phase states.
   - For rigorous mode, construct total component inventory and total internal energy for each conserved node.
   - Treat liquid/vapor phase inventories, temperature, pressure, phase split, compositions, and flows as algebraic initial guesses, not fixed truth.

4. Apply algebraic consistency gates.
   - Solve and report local component/energy/volume UV closure.
   - Solve and report the global pressure-drop/vapor-flow network separately.
   - Verify complete condenser, reflux-drum, reboiler, and sump mappings.
   - For conserved-state redistribution, require multi-start reproducibility and reject terminal-dominated movement before adding hydraulics.
   - Canonicalize energy from one live property basis; do not conserve an incompatible serialized phase-enthalpy total.
   - Stop checkpoint repair after its documented bounded retry fails. Move to the direct steady-state formulation rather than tuning another projection.
   - Stop before dynamic integration if any required algebraic gate fails.

5. Evaluate steady-state residuals only after algebraic closure.
   - Evaluate conserved component and total-energy rates at $t=0$.
   - Collect residuals by tray, boundary, feed, and whole-column balance.

6. Identify dominant inconsistencies.
   - Rank the residuals by block and by tray/component.
   - Determine whether the main problem is equilibrium mismatch, vapor-flow closure, pressure-vapor holdup inconsistency, energy inconsistency, or boundary coupling.

7. Apply the model-physics closure prerequisite.
   - Verify that hydraulic pressure agrees with the pressure implied by vapor holdup and volume.
   - Verify that net phase-total changes conserve tray energy.
   - Verify that imported liquid/vapor profiles are not retaining runtime ownership for a rigorous claim.
   - Verify that no accepted projection or flow limiter replaces the governing closure.
   - Verify convergence from at least `+/-10%` pressure and flow guesses.
   - If these checks fail, stop initializer optimization and return the issue to model-equation development.

8. Solve a constrained steady-state residual problem only after the closure prerequisite passes.
   - Solve for a state that reduces the residual vector toward zero.
   - Use a bounded nonlinear least-squares or Newton-like method.
   - Keep the solution close to the seed through regularization so the solver does not wander to unphysical states.
   - If tray conserved totals or energies are varied, preserve whole-column component and energy totals and honor the selected operating degrees of freedom.

9. Apply stabilization only where needed.
   - Use relaxation or homotopy terms to damp startup transients.
   - Do not rely on these terms alone to define a valid initial state.

10. Re-audit after each stage.
   - Recompute residuals after each solve stage.
   - Accept a stage only if it improves the relevant residuals and remains physically plausible.

11. Run a short dynamic smoke test.
   - Launch the model for a short interval.
   - Compare the candidate to the baseline seed using dynamic metrics.

12. Apply a dynamic acceptance gate.
    - Accept the candidate only if it improves the dynamic behavior relative to baseline.
    - Reject candidates that improve static residuals but fail dynamically.
    - Record an explicit `clean_usable_assessment` verdict so the run result is not inferred from scattered metrics.

13. Serialize the accepted state.
    - Prefer the native checkpoint emitted by the accepted dynamic smoke run.
    - Keep the workbook as an inspection/interoperability artifact unless reload parity has been proven.

## Mathematical Formulation

After algebraic model-physics closure is established, the steady-state portion
of the initializer can be posed as a constrained residual minimization problem:

$$
\min_{y_0} \left\| R(y_0) \right\|_2^2 + \lambda \left\| y_0 - y_{seed} \right\|_2^2
$$

subject to physical bounds on the state variables.

Here:
- $y_0$ is the initial state vector,
- $R(y_0)$ is the dynamic residual vector evaluated at $t=0$,
- $y_{seed}$ is the imported steady-state seed,
- $\lambda$ is a regularization weight.

## Implementation Notes

### Residual assembly

The residual vector should include the important RHS blocks that govern startup behavior. For example:
- tray liquid material balances,
- tray vapor material balances,
- top/bottom boundary balances,
- pressure/vapor-flow closure,
- energy balances,
- feed-stage terms.

### Solver choice

A bounded least-squares solver is a practical diagnostic and may become an initializer method after model closure because:
- the problem is nonlinear,
- the system is overdetermined in practice,
- and physical bounds are required.

For the current C3/C4 full topology, it is not the next primary development path. Earlier least-squares candidates reduced selected residuals while transferring inconsistency to other blocks or worsening the dynamic gate. Do not optimize around the DD-060 pressure/phase ownership conflict.

### Staged solve strategy

The solve should be attempted in stages rather than all at once:
1. local conserved-state UV closure,
2. terminal-equipment conserved-state closure,
3. uncapped global pressure/vapor-flow closure,
4. controller degree-of-freedom feasibility,
5. steady component and energy balances,
6. full residual and robustness solve.

This tends to be more robust than a single monolithic solve.

## Diagnostics to Report

Each candidate should produce a report containing:
- algebraic classification reason code,
- local component/energy/volume closure residuals,
- global pressure-drop and vapor-flow residuals,
- terminal inventory included/excluded totals,
- accepted and attempted projection counts,
- initial-guess robustness results,
- worst residual block,
- worst tray/component,
- K-state vs K-thermo mismatch,
- vapor closure error,
- pressure-vapor holdup mismatch,
- energy mismatch,
- and dynamic smoke-test metrics.

## Decision Rule

The initializer should not accept a candidate because it reduces a static
objective alone. It must first pass local, global hydraulic, and terminal
algebraic gates. Only then may steady-state and dynamic acceptance be assessed.

For rigorous acceptance, it must also pass the model physical-closure gate. A low residual against equations that contain profile ownership or competing pressure definitions is not sufficient.

Use these stable classifications where applicable:

- `local_uv_failed`
- `local_uv_passed_global_hydraulics_failed`
- `terminal_mapping_failed`
- `algebraically_consistent_not_steady`
- `steady_initialization_accepted`

In implementation terms, the final summary should contain a single clean/usable verdict. With the dynamic gate enabled, `usable=true` means both the residual gate and dynamic gate passed. Without the dynamic gate, the initializer may report that the residual gate passed, but that should be treated as provisional rather than final dynamic acceptance.

The final summary should also identify the accepted artifact. If a usable candidate has a native checkpoint, that checkpoint is the preferred restart artifact because it preserves packed state and runtime memory. If no checkpoint is available, workbook output should be marked provisional or diagnostic rather than silently treated as production-ready.

When promoting a checkpoint to a reusable initializer artifact, run the checkpoint reload gate. This reloads the native checkpoint with `--init-from-checkpoint`, launches a short smoke test, and compares the reload behavior against the accepted candidate smoke. Passing the dynamic gate proves the candidate; passing the reload gate proves the serialized artifact.

The initializer summary should include a restart command for the selected artifact. For checkpoint-backed artifacts, that command should keep the Excel workbook as the case/layout source and pass the native checkpoint through `--init-from-checkpoint`.
