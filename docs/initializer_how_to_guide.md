# Initializer Implementation Guide

Updated: 2026-07-12

Current model status: `docs/dynamic_model_current_state_2026-07-12.md`.

## Objective

This document describes the recommended implementation approach for building a robust dynamic initializer for the column model. The goal is to convert a steady-state seed into a dynamically acceptable initial state at $t=0$.

## Core Principle

A steady-state profile from ChemSep or Excel is only a seed. It is not automatically a valid dynamic initial condition for this model because the dynamic system includes explicit vapor states, pressure dynamics, energy balances, and boundary coupling.

The initializer should therefore be treated as a separate consistency problem, not as a simple import-and-run step.

The initializer cannot repair an internally inconsistent runtime equation set. Before pursuing zero residuals, verify that pressure, vapor holdup, phase totals, energy, and hydraulic flow have unique and compatible owners. DD-060 showed that this prerequisite is not yet satisfied for the rigorous C3/C4 topology. Until that architecture is corrected, initializer optimization is diagnostic and DD-058's native checkpoint is an operational restart baseline rather than a rigorous golden seed.

## Recommended Workflow

1. Load the seed.
   - Import the external steady-state profile as a reference seed.
   - Preserve the original values for audit and comparison.

2. Reconcile topology.
   - Map the seed onto the model's actual topology.
   - Reconcile tray indexing, feed stage, condenser/reboiler interpretation, and boundary equipment mapping.

3. Build an initial state vector.
   - Populate tray liquid/vapor compositions, temperature, pressure, holdup, and boundary states.
   - Use the seed as the initial guess, not as the final truth.

4. Evaluate the dynamic residuals at $t=0$.
   - Call the RHS at $t=0$.
   - Collect residuals by block:
     - tray liquid,
     - tray vapor,
     - top/bottom boundary,
     - pressure/vapor-flow,
     - energy/temperature,
     - feed-stage terms.

5. Identify dominant inconsistencies.
   - Rank the residuals by block and by tray/component.
   - Determine whether the main problem is equilibrium mismatch, vapor-flow closure, pressure-vapor holdup inconsistency, energy inconsistency, or boundary coupling.

6. Apply the model-physics closure prerequisite.
   - Verify that hydraulic pressure agrees with the pressure implied by vapor holdup and volume.
   - Verify that net phase-total changes conserve tray energy.
   - Verify that imported liquid/vapor profiles are not retaining runtime ownership for a rigorous claim.
   - If these checks fail, stop initializer optimization and return the issue to model-equation development.

7. Solve a constrained residual problem only after the closure prerequisite passes.
   - Solve for a state that reduces the residual vector toward zero.
   - Use a bounded nonlinear least-squares or Newton-like method.
   - Keep the solution close to the seed through regularization so the solver does not wander to unphysical states.

8. Apply stabilization only where needed.
   - Use relaxation or homotopy terms to damp startup transients.
   - Do not rely on these terms alone to define a valid initial state.

9. Re-audit after each stage.
   - Recompute residuals after each solve stage.
   - Accept a stage only if it improves the relevant residuals and remains physically plausible.

10. Run a short dynamic smoke test.
   - Launch the model for a short interval.
   - Compare the candidate to the baseline seed using dynamic metrics.

11. Apply a dynamic acceptance gate.
    - Accept the candidate only if it improves the dynamic behavior relative to baseline.
    - Reject candidates that improve static residuals but fail dynamically.
    - Record an explicit `clean_usable_assessment` verdict so the run result is not inferred from scattered metrics.

12. Serialize the accepted state.
    - Prefer the native checkpoint emitted by the accepted dynamic smoke run.
    - Keep the workbook as an inspection/interoperability artifact unless reload parity has been proven.

## Mathematical Formulation

After model-physics closure is established, the initializer can be posed as a constrained residual minimization problem:

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
1. pressure/vapor holdup closure,
2. boundary states,
3. vapor composition/flow closure,
4. energy/temperature closure,
5. full residual solve.

This tends to be more robust than a single monolithic solve.

## Diagnostics to Report

Each candidate should produce a report containing:
- worst residual block,
- worst tray/component,
- K-state vs K-thermo mismatch,
- vapor closure error,
- pressure-vapor holdup mismatch,
- energy mismatch,
- and dynamic smoke-test metrics.

## Decision Rule

The initializer should not accept a candidate because it reduces a static objective alone. It should accept a candidate only when it also performs better dynamically.

For rigorous acceptance, it must also pass the model physical-closure gate. A low residual against equations that contain profile ownership or competing pressure definitions is not sufficient.

In implementation terms, the final summary should contain a single clean/usable verdict. With the dynamic gate enabled, `usable=true` means both the residual gate and dynamic gate passed. Without the dynamic gate, the initializer may report that the residual gate passed, but that should be treated as provisional rather than final dynamic acceptance.

The final summary should also identify the accepted artifact. If a usable candidate has a native checkpoint, that checkpoint is the preferred restart artifact because it preserves packed state and runtime memory. If no checkpoint is available, workbook output should be marked provisional or diagnostic rather than silently treated as production-ready.

When promoting a checkpoint to a reusable initializer artifact, run the checkpoint reload gate. This reloads the native checkpoint with `--init-from-checkpoint`, launches a short smoke test, and compares the reload behavior against the accepted candidate smoke. Passing the dynamic gate proves the candidate; passing the reload gate proves the serialized artifact.

The initializer summary should include a restart command for the selected artifact. For checkpoint-backed artifacts, that command should keep the Excel workbook as the case/layout source and pass the native checkpoint through `--init-from-checkpoint`.
