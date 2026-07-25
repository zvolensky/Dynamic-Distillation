# DD-097 Core V3 Implicit-Step Contract

Date: 2026-07-25

## Purpose

DD-097 is the first numerical step contract authorized by the DD-096 live
leading-Jacobian pass. It asks whether one backward-Euler endpoint can be
solved consistently from the exact DD-094 reduced steady root.

This is not a trajectory campaign. It introduces no controller, disturbance,
initializer, profile force, pressure dynamics, vapor holdup, or production
tray scaling.

## Frozen Source

The contract retains unchanged:

- the accepted DD-094 component inventories and algebraic root;
- the DD-095 `38 x 38` derivative/algebraic ledger;
- the DD-096 energy-storage and provider ownership basis;
- fixed DD-094 feed, pressure, geometry, reflux, reboiler duty, distillate,
  and bottoms rates;
- live DWSIM Peng-Robinson properties with no fallback.

## Backward-Euler Form

For each component inventory:

```text
(N_next[j,k] - N_previous[j,k]) / dt = material_rhs_next[j,k]
```

The five energy rows use the exact provider-derived storage difference:

```text
(U_next[j] - U_previous[j]) / dt = energy_rhs_next[j]
```

Each `U` is reconstructed from the saturated-liquid bubble state, declared
DWSIM liquid enthalpy, liquid density, and the `P*v` conversion already
validated by DD-096. The remaining equilibrium, Francis hydraulic, and
condenser bubble rows are evaluated at the endpoint.

The solve has `38` unknowns and `38` residuals:

| Unknown block | Count |
|---|---:|
| Dimensionless component-inventory rates | 15 |
| Endpoint algebraic coordinates | 23 |

Positive inventories are represented without clipping by:

```text
N_next = N_previous * exp(dt * rate_scale * r / N_previous)
```

The physical rate used in every balance is then recomputed exactly from the
endpoint difference. No rate cap or projection is permitted.

## Frozen Solver

Use exactly one `scipy.optimize.least_squares(method="trf")` implementation
with:

```text
central-difference Jacobian step = 1e-5
ftol = xtol = gtol              = 1e-12
max_nfev                         = 40
x_scale                          = 1
bounds                           = none
```

The initial rate coordinates are zero and the initial algebraic coordinates
are the exact DD-094 root. No alternate start or retry is authorized.

## Frozen Checks

Execute, in order:

1. One zero-rate algebraic recovery at fixed DD-094 inventory.
2. One independent backward-Euler step of `1.0 s` from DD-094.
3. One independent backward-Euler refinement step of `0.5 s` from DD-094.

The two finite steps are separate one-step checks from the same root; neither
continues from the other.

## Acceptance Gates

Every solve shall terminate successfully within `40` residual evaluations
and have scaled residual infinity norm below `1e-8`.

The zero-rate recovery shall have:

- algebraic Jacobian rank `23/23`;
- condition below `1e8`;
- maximum algebraic movement below `1e-7`.

Each finite step shall have:

- endpoint Jacobian rank `38/38` and condition below `1e8`;
- maximum absolute component rate below `1e-4 lbmol/h`;
- maximum inventory movement divided by its starting inventory below `1e-9`;
- maximum algebraic movement below `1e-7`;
- positive finite inventories, compositions, temperatures, and flows;
- strictly increasing temperature from drum to bottom volume;
- negative condenser duty and physical hydraulic heights;
- local storage bubble residual below `1e-10`;
- global discrete component and energy errors below `1e-8` relative.

Between the `1.0 s` and `0.5 s` endpoints:

- maximum normalized inventory difference shall be below `1e-9`;
- maximum dimensionless rate difference shall be below `1e-7`;
- maximum algebraic-coordinate difference shall be below `1e-7`.

All provider calls shall pass DD-090 ownership with no fallback. No clipping,
projection, regularization, alternate property interface, solver variation,
or post-result tolerance change is permitted.

## Execution Rule

The exact source evidence, implementation, tests, workbook, root, settings,
steps, and limits shall be hashed into a generated contract and committed
before one live execution. An existing result artifact prohibits rerun.

Preparation performs no live property evaluation, nonlinear solve, or
dynamic step.

## Hard Stop

Any failed gate stops the implicit-step path. Do not tune the solver, reduce
the step, change coordinates, perturb the root, or introduce a controller in
response.

## Authorization Boundary

A pass authorizes only a separately frozen short open-loop trajectory
contract with fixed step/refinement and conservation gates. It does not by
itself establish useful dynamic behavior, production initialization, or
full-column scalability.
