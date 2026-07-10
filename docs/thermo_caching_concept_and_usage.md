# Thermo Caching: Concept, Need, and Use in the Model

Date: 2026-07-08

## Purpose

Thermo caching is a numerical and performance strategy for reusing previously computed phase-equilibrium and enthalpy information instead of recomputing it every time the model needs a thermodynamic property.

In this project, the column model repeatedly needs quantities such as:
- vapor-liquid equilibrium ratios $K_i$
- liquid and vapor enthalpies $H_L$, $H_V$
- flash results and related phase properties
- condenser/reboiler closure information

Those evaluations can be expensive, especially when the model is running many time steps or repeatedly probing the same nearby states. Caching avoids unnecessary recomputation and can also provide a useful fallback when a live thermo call fails or becomes numerically unstable.

---

## Why Thermo Caching Is Needed

### 1. Runtime Cost

A dynamic distillation model evaluates thermodynamics at many points during each integration step. If every stage and boundary condition triggers a fresh flash or property calculation, the computational cost can become large enough to dominate runtime.

### 2. Numerical Stability During Startup and Transients

Dynamic startup is often stiff and sensitive to abrupt thermo changes. Reusing previous thermo information can smooth the transition between steps and reduce the chance that a transient thermo evaluation destabilizes the solver.

### 3. Robustness to Flash Failure

Real thermo backends can fail occasionally due to:
- poor initial guesses,
- out-of-range states,
- convergence problems,
- inconsistent temperature/pressure/composition combinations.

A cache gives the model a fallback path so it can continue with the last known valid thermo state rather than failing outright.

### 4. Consistency Across Coupled Equations

The column equations couple mass, energy, pressure, and phase behavior. Reusing recent thermo results helps keep those coupled relationships from drifting too quickly when the state is changing rapidly.

---

## What the Cache Stores

The repo uses several forms of cached thermo information, including:
- previous stage flash results,
- previous $K$ values,
- previous liquid/vapor enthalpy values,
- prior condenser/reboiler flash outputs,
- startup/seed thermo packets used to initialize a run.

The idea is not to replace the thermodynamics, but to reuse the most recent valid information as a practical approximation or starting point.

---

## How It Is Used in the Model

### Modules That Employ Caching

Thermo caching is used in several parts of the codebase, not just in one isolated function.

- [src/dynamic_distillation/column_rhs_v1.py](src/dynamic_distillation/column_rhs_v1.py)
  - main runtime path for stage and boundary thermo evaluation
  - reuses cached $K$, $H_L$, $H_V$, and flash-related values during RHS evaluation
  - provides fallback behavior for condenser/reboiler closures and transient thermo updates

- [src/dynamic_distillation/dynamic_run_scaffold_v1.py](src/dynamic_distillation/dynamic_run_scaffold_v1.py)
  - startup and initialization workflow
  - uses thermo seed/cache data to warm-start the model and improve early consistency

- [src/dynamic_distillation/thermo_surrogate_v1.py](src/dynamic_distillation/thermo_surrogate_v1.py)
  - builds and evaluates surrogate thermo tables
  - uses tabular thermo surfaces as a structured, reusable cache of property behavior

- [src/dynamic_distillation/thermo_table_pool_v1.py](src/dynamic_distillation/thermo_table_pool_v1.py)
  - parallel table-based thermo evaluation path
  - reuses the same cached table-based thermo surfaces across worker tasks and refreshes

### In the RHS evaluation path

The main dynamic model in [src/dynamic_distillation/column_rhs_v1.py](src/dynamic_distillation/column_rhs_v1.py) uses cached thermo information in the stage and boundary evaluation logic.

Typical uses include:
- reusing prior stage $K$ values when a fresh flash is unavailable,
- using prior enthalpy estimates for liquid and vapor flows,
- reusing condenser duty and flash data for boundary closures,
- falling back to cached values when thermo refresh logic decides the current state is too close to the previous one.

### In startup and initialization

The runner scaffolding in [src/dynamic_distillation/dynamic_run_scaffold_v1.py](src/dynamic_distillation/dynamic_run_scaffold_v1.py) also uses thermo-related startup seed handling. This is important because initialization is often more fragile than the long-run dynamics. A cached thermo packet can provide a warm start that is more consistent with the previous state than an entirely fresh thermo evaluation.

### In surrogate-table thermo mode

The thermo surrogate workflow in [src/dynamic_distillation/thermo_surrogate_v1.py](src/dynamic_distillation/thermo_surrogate_v1.py) and [src/dynamic_distillation/thermo_table_pool_v1.py](src/dynamic_distillation/thermo_table_pool_v1.py) also relies on the same idea, but at a higher level: instead of recomputing flash information from a full backend, the model interpolates from a precomputed table. In that context, the table acts as a structured cache of thermo surfaces.

---

## Why It Is Not a Substitute for a Real Thermo Solve

Caching is helpful, but it is not a replacement for a correct thermodynamic evaluation.

A cache can:
- reduce cost,
- improve robustness,
- stabilize updates,
- preserve continuity between steps.

But it can also introduce errors if the state has moved too far from the cached point. For that reason, the model uses caching as a controlled fallback or reuse mechanism, not as the sole source of truth.

In practice, the implementation usually combines:
- fresh thermo evaluation when appropriate,
- cached values when the current state is close enough,
- safeguards such as validity checks and refresh gating.

---

## Practical Interpretation in This Project

Thermo caching in this repo serves two overlapping purposes:

1. Performance
   - speed up the dynamic solve by avoiding needless flash evaluations.

2. Numerical conditioning
   - keep the model from oscillating or failing during startup and rapid transients.

This is especially relevant because the model is a stiff nonlinear DAE system with coupled vapor, liquid, pressure, and energy states.

---

## Summary

Thermo caching is a practical engineering tool for this model. It is needed because thermo calculations are expensive and because dynamic distillation startup and transient operation are numerically sensitive. In the implementation, it is used to reduce runtime cost, improve stability, and provide fallback behavior when live thermo evaluation is unavailable or unreliable.

It is best understood as a support mechanism for the main model equations, not as a replacement for them.
