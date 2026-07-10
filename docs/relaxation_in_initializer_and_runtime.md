# Relaxation in the Dynamic Column Model

## What relaxation means

In this model, relaxation refers to a damping or smoothing mechanism used to prevent the dynamic equations from changing too aggressively from one step to the next. Instead of allowing a state variable to jump fully to a newly computed target, the model moves partway toward that target over time.

This is useful because the column model is a stiff nonlinear dynamic system. At startup, small inconsistencies in pressure, vapor holdup, vapor composition, temperature, or energy can cause large derivatives and unstable early dynamics.

## Why relaxation is needed

Relaxation is needed for three main reasons:

1. Numerical stability.
   - The model can otherwise produce very large initial derivatives.
   - That can lead to pressure spikes, temperature spikes, vapor-flow blowups, or solver failure.

2. Coupling between states.
   - Tray vapor flow, pressure, equilibrium, and energy are tightly coupled.
   - If one block updates too aggressively, it can force the others into inconsistent motion.

3. Startup conditioning.
   - The first few steps are especially sensitive because the model is often initialized from an external steady-state seed that is not perfectly consistent with the dynamic equations.
   - Relaxation gives the solver a smoother path from the seed into the dynamic regime.

## Important distinction

Relaxation is not the same as solving the initialization problem.

- A residual solve tries to make the initial state internally consistent at $t=0$.
- Relaxation smooths the transition from the current state toward a target during runtime or startup.

In other words, relaxation is a stabilizer, not a substitute for a true initialization solve.

## Where relaxation is employed in this model

Relaxation appears in several places in the codebase and in the dynamic RHS logic.

### 1. Equilibrium relaxation

The model includes equilibrium relaxation paths for tray vapor/liquid phase behavior.

Relevant code:
- [src/dynamic_distillation/column_rhs_v1.py](src/dynamic_distillation/column_rhs_v1.py)

This is used to soften the transition between:
- the current tray state,
- and a thermo-equilibrium target derived from current $T$, $P$, and composition.

This helps prevent abrupt phase-transfer changes during startup.

### 2. Vapor-flow relaxation

The model supports a vapor-flow relaxation timescale that damps aggressive vapor-flow updates.

Relevant code:
- [src/dynamic_distillation/column_rhs_v1.py](src/dynamic_distillation/column_rhs_v1.py)

This is used when vapor-flow calculations become too sensitive to small pressure mismatches or when startup vapor traffic needs to be smoothed.

### 3. Hydraulic pressure relaxation

Pressure updates can be smoothed with a relaxation timescale to avoid sharp hydraulic shocks.

Relevant code:
- [src/dynamic_distillation/column_rhs_v1.py](src/dynamic_distillation/column_rhs_v1.py)

This is particularly relevant when pressure states are tightly linked to vapor holdup and vapor transport.

### 4. Top-drum pressure and temperature smoothing

The model includes a relaxation path for top-drum pressure and temperature updates to reduce startup shocks near the condenser boundary.

Relevant code:
- [src/dynamic_distillation/column_rhs_v1.py](src/dynamic_distillation/column_rhs_v1.py)

### 5. Startup conditioning and thermo consistency passes

The startup workflow includes extra conditioning passes that use relaxation-like behavior to prepare the system before a full dynamic run.

Relevant code:
- [src/dynamic_distillation/dynamic_run_scaffold_v1.py](src/dynamic_distillation/dynamic_run_scaffold_v1.py)

These passes are used to precondition thermo state, feed-state flash behavior, hydraulic energy consistency, and startup vapor closure.

## Typical relaxation pattern

A relaxation update often looks like this conceptually:

$$
x_{new} = x_{current} + \alpha (x_{target} - x_{current})
$$

where:
- $x_{current}$ is the current state,
- $x_{target}$ is a newly computed target,
- $\alpha$ is a relaxation factor between $0$ and $1$.

A smaller $\alpha$ means stronger damping.

## Practical interpretation

In this project, relaxation is used when the model would otherwise react too violently to a plausible but imperfect startup state. It is especially relevant for:
- equilibrium updates,
- vapor-flow updates,
- hydraulic pressure updates,
- and temperature/energy transitions near startup.

## Recommended use

Relaxation should be used as a startup and stability tool, not as the primary way to define the initial state.

Best practice is:
1. build a consistent initial state as well as possible,
2. use relaxation to smooth the first dynamic steps,
3. and remove or reduce the damping once the model has settled.

## Summary

Relaxation is needed because the dynamic column model is stiff and strongly coupled. It is employed in the model to damp:
- equilibrium changes,
- vapor-flow changes,
- pressure updates,
- temperature/energy shocks,
- and startup transients.

It is a crucial stabilization mechanism, but it should be considered a support mechanism rather than the core solution to initialization.
