# DD-104 Core V3 Pressure-Enabled Implicit DAE Contract

## Decision

DD-104 structural gate pass: `True`.

DD-103 proved that the DD-094 inventories cannot be held fixed while
the pressure-enabled equations are forced to zero rate. DD-104 therefore
does not attempt another steady repair. It restores the 15 component-
inventory rates as simultaneous implicit unknowns beside the 27 algebraic
coordinates.

## Structural Ledger

- State coordinates: `15`
- Inventory-rate variables: `15`
- Algebraic variables: `27`
- Total solve variables / rows: `42 / 42`
- Structural rank / nullity: `42 / 0`
- Pressure variables / pressure rates: `4 / 0`
- Jacobian colors: `20`
- Zero rows / columns: `0 / 0`

For three components the solve vector is `15` inventory rates plus
`27` algebraic coordinates. The equations are the existing `15` component
balances, `5` energy balances, `15` fugacity equations, `3` Francis
relations, and `4` pressure-drop equations.

## Pressure Ownership

Reflux-drum pressure remains the sole fixed anchor. Four lower-volume
pressures are algebraic unknowns; there is no pressure derivative or
resident vapor inventory. The terminal reboiler/sump return is dry-only.
The other three links are physical tray links with dry resistance plus
liquid head. Vapor flow remains energy-owned on every link.

## Implicit Ownership

`N_next = N_prev * exp(dt * nominal_rate / N_prev); physical inventory rates are recomputed from the exact endpoint difference`

`U_next = NL_next * (hL(T_next,P_next,x_next) - P_next/rhoL(T_next,P_next,x_next)); energy rows use the exact backward-Euler storage difference`

The structural Jacobian includes every rate-to-endpoint-inventory chain.
The terminal dry-only pressure row has no false sump-inventory/head
coupling; the three tray pressure rows retain their nine component-rate
couplings. The deterministic coloring is conflict-free.

## Scope And Authorization

No property call, mass-matrix evaluation, nonlinear solve, numerical
step, controller, or integration was attempted. Component and energy
conservation are inherited exactly. Fixed DD-094 product rates remain the
open-loop boundary condition.

A pass authorizes one separately frozen live leading-Jacobian and
consistent-rate audit at the DD-094 state using the DD-103 pressure seed.
It does not authorize a time step, trajectory, controller, vapor holdup,
or production-scale model.
