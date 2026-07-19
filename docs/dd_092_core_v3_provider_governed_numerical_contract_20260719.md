# DD-092 Core V3 Frozen Live Numerical-Audit Contract

Date: 2026-07-19

## Purpose

DD-092 asks whether the independently implemented Core V3 residual remains
physically evaluable, conservative, correctly provider-owned, full rank, and
acceptably conditioned with live DWSIM properties.

This is not a steady-root campaign and not a dynamic test.

## Two-Commit Rule

The contract commit shall contain:

- the independent Core V3 residual evaluator;
- the provider-call provenance and enforcement layer;
- two complete 40-coordinate states;
- the residual scale vector;
- all finite-difference settings;
- all provider restrictions, tolerances, and hard stops;
- unit tests;
- the generated contract JSON and Markdown.

Only after that commit may one live audit execution occur. The result commit
may add evidence and decisions but shall not change this contract.

## Core V3 Boundary

The live evaluator is under `dynamic_distillation.core_v3`. It does not
import:

- a Core V2 residual evaluator;
- a Core V2 coordinate owner;
- DD-088 result data;
- DD-088 acceptance status.

Neutral case loading, DWSIM transport infrastructure, and dimensional data
may be reused.

## Coordinates

The frozen coordinate ledger contains:

- 5 log liquid amounts;
- 10 liquid-composition ALR coordinates;
- 5 affine temperatures;
- 8 column-vapor ALR coordinates;
- 3 log Francis liquid flows;
- 4 log vapor-link flows;
- log `D` and log `B`;
- 2 condenser incipient-vapor ALR coordinates;
- 1 signed affine condenser-duty coordinate.

Condenser duty is:

```text
Q_C = Q_C,ref + s_Q*q_Q_C
s_Q = max(abs(Q_C,ref), abs(Q_R), abs(H_feed))
```

Negative duty is never logarithmically transformed.

## Frozen States

Preparation constructs exactly two complete vectors before any live
full-column residual evaluation.

### Canonical

The canonical state uses:

- the role-mapped mini8 source profile;
- prescribed pressure, feed, reflux, and reboiler duty;
- a local three-variable direct-fugacity condenser bubble solve;
- condenser duty reconstructed from the condenser energy balance;
- live DWSIM enthalpy paths.

The local solve owns only drum temperature and two incipient-vapor ALR
coordinates. It is not a column solve.

### Deterministic Perturbation

The second state applies fixed bounded changes to:

- interior liquid amounts;
- all liquid compositions;
- interior temperatures;
- column vapor compositions;
- liquid and vapor flows;
- distillate and bottoms rates.

Its perturbed drum composition receives a separate local direct-fugacity
bubble reconstruction and a separate negative condenser-duty reconstruction.

The exact vectors are frozen in:

`logs/dd092_core_v3_provider_governed_numerical_contract_20260719.json`

## Residual and Jacobian

The live residual contains exactly 40 rows:

| Block | Rows |
|---|---:|
| Four stage full-fugacity blocks | 12 |
| Five component-balance blocks | 15 |
| Five energy balances | 5 |
| Francis hydraulics | 3 |
| Terminal amount specifications | 2 |
| Condenser bubble fugacity | 3 |

Use uncolored central differences at:

- `h = 1e-5`;
- `h/2 = 5e-6`.

Both states require:

- full numerical rank `40/40`;
- condition below `1e8`;
- no zero row or column;
- no coupling outside the DD-091 graph;
- stable rank at both steps;
- local condenser bubble rank `3/3`;
- finite local singular values and no local zero row or column.

The whole-column residual norm is diagnostic only.

## Provider Ownership

Every property request records:

- quantity;
- provider interface;
- caller;
- state identifier;
- residual, Jacobian, diagnostic, validation, or preparation phase.

Production residual and Jacobian calls may use only:

- DWSIM direct imposed-phase fugacity;
- declared DWSIM liquid/vapor phase enthalpy;
- declared DWSIM liquid density.

TP flash is diagnostic-only and runs after residual and Jacobian evaluation.
Independent parameter-aligned PR is validation-only.

The runtime layer rejects:

- TP flash in a residual or Jacobian;
- independent PR outside validation;
- provider substitution or fallback.

The audit does not calculate `normalize(K_flash*z)` as an equilibrium gate
and does not require direct incipient vapor to equal TP-flash vapor.

## Numerical Gates

Required limits:

- condenser direct-fugacity residual below `1e-10`;
- component telescoping relative error below `1e-12`;
- energy telescoping relative error below `1e-10`;
- independent PR bubble-temperature difference below `1e-3 F`;
- independent PR incipient-vapor difference below `1e-6`;
- TP flash does not classify the condenser state as stable vapor;
- TP flash vapor fraction at most `1e-3`;
- TP-flash `y = normalize(K*x_flash)` error below `1e-12`;
- TP-flash lever-rule error below `1e-12`.

Both states must also retain positive amounts, flows, product rates, and
compositions; finite temperatures and properties; negative condenser duty;
and liquid heights below tray spacing. No clipping, projection, limiter,
controller, or fallback is permitted.

## Hard Stop

Any failed numerical, conservation, provider, phase, physical, or provenance
gate stops Core V3 before a root campaign. Failure does not authorize provider
substitution, tolerance changes, DD-088 root import, or dynamic work.

## Pass Authorization

A pass authorizes only drafting and committing one bounded, three-start Core
V3 steady-root contract. It does not authorize executing that campaign before
its contract commit, deriving a mass matrix, or integrating dynamics.
