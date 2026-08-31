# DD-101 Core V3 Pressure-Layer Structural Contract

Status: Historical reference. This document describes an earlier algebraic-pressure feasibility layer and is superseded by the accepted vapor-holdup C3/C4 formulation documented in `docs/dynamic_model_current_state_2026-08-20.md` and `docs/model_architecture.md`.

## Decision

DD-100 authorizes one explicit dynamic-scope decision. DD-101 selects the
simultaneous algebraic pressure-drop layer, not a longer fixed-pressure run and
not pressure dynamics with vapor inventory.

This ordering is deliberate. Interstage vapor rates are already energy-owned.
The next missing closure is the pressure profile consistent with those same
rates. A pressure controller or pressure differential state would be premature
while interior pressure remains prescribed.

## Ownership

The accepted DD-100 `38 x 38` implicit system is extended by:

- four algebraic pressure unknowns, one for every volume below the reflux drum;
- four uncapped vapor pressure-drop equations, one per internal vapor link.

Reflux-drum pressure remains the sole fixed pressure anchor. No interior
pressure is prescribed.

Each pressure-drop equation uses the existing energy-owned vapor flow and the
generic dry-tray-plus-liquid-head relation:

`P_source - P_destination = deltaP_liquid + deltaP_dry`

The liquid-head term uses current inventory, liquid composition, geometry, and
declared liquid density. The dry term uses current vapor rate, vapor
composition, temperature, pressure, active area, molecular weight, dry-tray
coefficient, and declared vapor compressibility `Z`.

There is no conductance flow owner, profile forcing, previous-step pressure,
flow cap, relaxation, or duplicate vapor-flow equation.

## Structural result

For three components:

- solve variables: `42`;
- equations: `42`;
- structural rank: `42`;
- structural nullity: `0`;
- pressure unknowns: `4`;
- pressure-drop equations: `4`;
- energy-owned vapor flows retained: `4`;
- zero rows/columns: none;
- unregistered dependencies: none.

Component and energy conservation remain inherited from the accepted Core V3
ledger. The pressure equations add no material or energy source.

## Provider boundary

The future live residual must extend Core V3 provider ownership with one
quantity: direct declared vapor-phase compressibility factor. TP flash,
independent PR, ideal-gas substitution, stale `Z`, and fallback remain
prohibited for governing pressure drop.

## Scope gate

DD-101 performs no property call, residual evaluation, nonlinear solve, or
dynamic integration. Passing authorizes only one frozen live residual and
Jacobian audit of the `42 x 42` layer at the accepted root and a bounded
pressure perturbation.

Pressure differential states, vapor holdup, pressure control, product control,
and production-horizon integration remain unauthorized.
