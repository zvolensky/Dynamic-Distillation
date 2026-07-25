# DD-096 Core V3 Dynamic DAE Numerical Contract

Date: 2026-07-25

## Purpose

DD-096 is the single live numerical audit authorized by DD-095. It asks
whether the reduced Core V3 implicit derivative/algebraic system remains
locally solvable when the actual DWSIM PR property derivatives enter the
energy-storage chain rule.

This increment does not solve for another steady state and does not integrate
the model through time.

## Frozen Source

The audit shall use only:

- the accepted DD-094 canonical Core V3 root;
- the DD-095 `38 x 38` structural derivative/algebraic registry;
- the DD-094 pressure profile, feed, geometry, reflux, reboiler duty, and
  accepted product rates;
- the DD-090 provider ownership rules and live DWSIM Peng-Robinson package.

The initial component inventories are fixed as:

```text
N[j,k] = NL_DD094[j] * x_DD094[j,k]
```

The initial derivative vector is exactly zero. The algebraic point is the
DD-094 temperature, vapor-composition, Francis-flow, energy-owned vapor-flow,
condenser-bubble, and condenser-duty solution. Distillate and bottoms rates
remain fixed at the DD-094 values.

## Implicit System

The numerical leading system is:

```text
F(N, dN/dt, z) = 0
```

with:

| Block | Count |
|---|---:|
| Component-inventory derivatives `dN/dt` | 15 |
| Algebraic variables `z` | 23 |
| Residual equations | 38 |

The component rows are `dN/dt - material_rhs`. The energy rows are
`dU/dt - energy_rhs`. Equilibrium, Francis hydraulics, and condenser bubble
rows are unchanged from the provider-governed steady residual. The two steady
terminal-amount rows are absent.

## Energy Storage

At fixed pressure and saturated-liquid equilibrium, stored energy is derived
from component inventory:

```text
U[j] = NL[j] * (hL[j] - P[j] * vL[j] * BTU_PER_PSI_FT3)
dU[j]/dt = sum_k (partial U[j]/partial N[j,k]) * dN[j,k]/dt
```

For each inventory perturbation, temperature and incipient vapor composition
shall be reconstructed with the direct-fugacity local bubble equations.
DWSIM phase enthalpy and liquid density supply `hL` and `vL`. No TP-flash
value, independent-PR value, profile value, or fallback may enter this
storage calculation.

The storage gradient shall be evaluated by physical-coordinate central
differences at relative steps `1e-5` and `5e-6`. Every value must be finite,
the maximum relative gradient change must be below `1e-3`, and every local
bubble residual must be below `1e-10`.

## Leading Jacobian

At the exact DD-094 state and zero derivative, evaluate:

```text
partial F / partial (dimensionless dN/dt, z)
```

with uncolored central differences at dimensionless steps `1e-5` and
`5e-6`. The derivative coordinates use the corresponding component-balance
scales. Algebraic coordinates and residual scales are inherited unchanged
from DD-094.

Both `38 x 38` matrices shall have:

- rank `38/38`;
- condition number below `1e8`;
- no zero row or column;
- no coupling outside the DD-095 structural registry above `1e-7`;
- maximum relative singular-spectrum change below `0.25`.

## Root And Conservation Gates

At zero derivative:

- the scaled implicit residual infinity norm shall be below `1e-8`;
- maximum component rate shall be reported;
- maximum derived energy-storage rate shall be reported;
- component telescoping relative error shall be below `1e-12`;
- energy telescoping relative error shall be below `1e-10`;
- every provider call shall satisfy the DD-090 ownership and no-fallback
  policy.

## Execution Rule

The implementation, source evidence, workbook, exact root, coordinates,
scales, steps, tolerances, and gates shall be hashed into a generated contract
artifact and committed before execution. The live campaign may execute once.
An existing result artifact prohibits another execution.

Preparation shall perform no property evaluation, numerical mass-matrix
evaluation, nonlinear solve, or dynamic integration.

## Hard Stops

Stop the Core V3 dynamic path before integration if any frozen gate fails.
Do not respond with another root, finite-difference step, scale, tolerance,
provider fallback, controller, profile force, relaxation term, clipping rule,
or integrator setting.

## Authorization Boundary

A pass authorizes only drafting and precommitting one numerical implicit
solver/consistent-step contract. It does not authorize integration,
controllers, disturbances, production tray scaling, pressure dynamics, vapor
holdup, or initializer development.

A failure stops this fixed-pressure saturated-liquid Core V3 dynamic path and
requires an architectural decision rather than numerical tuning.

