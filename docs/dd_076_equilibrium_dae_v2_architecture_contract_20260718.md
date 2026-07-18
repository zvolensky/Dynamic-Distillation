# DD-076: Equilibrium-DAE V2 Architecture Contract

Date: 2026-07-18

## Decision

The external architecture review agrees with the DD-075 stop and sharpens its
meaning:

- dynamic distillation is not the failed idea;
- the current runtime is a sequential hybrid with overlapping physical owners;
- DD-060 through DD-075 should remain preserved evidence, not the base for
  another solver variant;
- the next rigorous implementation must begin with equations and ownership,
  not with initializer code.

The selected v2 modeling family is an **equilibrium-stage DAE**. A rate-based
nonequilibrium model is explicitly out of scope.

No v2 model code is authorized until this control-volume, ownership, equation,
degree-of-freedom, and gate contract has been reviewed.

## Relationship To Existing Work

The existing assets remain useful:

- DD-058 remains the accepted operational C3/C4 checkpoint;
- the Skogestad source-topology path remains the accepted material-dynamics
  validation baseline;
- DD-071/DD-072 remain valid equation-registry, conservation, scaling, and
  Jacobian-audit patterns;
- DD-075 remains the stop result for the current direct conserved formulation.

The v2 model must live in a new namespace and must not call
`column_rhs_v1.py` for its governing equations. Reusing property-provider,
case-loading, reporting, and generic audit utilities is allowed only when
their numerical meaning is unchanged and tested.

## Modeling Level

The first v2 physical layer deliberately uses:

- negligible tray vapor holdup;
- a prescribed, ordered pressure profile;
- total component tray inventories as differential states;
- total tray internal energy as a differential state;
- algebraic equilibrium vapor composition;
- Francis hydraulics as the sole owner of internal liquid flow;
- one explicit simplified vapor-traffic law;
- algebraic total-condenser transfer;
- explicit reflux-drum liquid inventory;
- one combined partial-reboiler/sump control volume;
- no equilibrium-relaxation source term.

This is less rigorous than the intended final model, but it is internally
owned and testable. Hydraulic pressure and explicit vapor inventory may be
added only after this layer passes.

## Physical Control Volumes

### Algebraic total condenser

The total condenser has no material or energy inventory.

Crossing streams:

- inlet: vapor from the top active tray;
- outlet: fully condensed liquid to the reflux drum;
- energy crossing: condenser duty.

It is not an equilibrium separation stage and has no resident vapor state.

### Reflux drum

The reflux drum is a well-mixed liquid control volume.

Crossing streams:

- inlet: condenser liquid;
- outlets: reflux and distillate.

Every liquid outlet uses the live drum composition. No product composition is
specified independently of the drum.

### Interior equilibrium trays

Each tray is one conserved control volume.

Crossing streams:

- liquid from the tray above;
- vapor from the tray below;
- optional feed;
- liquid to the tray below;
- vapor to the tray above;
- optional heat duty.

The tray has liquid inventory and energy storage. Vapor holdup is neglected in
the first layer, but the exiting vapor is in algebraic equilibrium with the
tray liquid.

### Combined partial reboiler and sump

The bottom equipment is one conserved liquid control volume with an algebraic
equilibrium vapor outlet.

Crossing streams:

- liquid from the lowest active tray;
- bottoms liquid product;
- boilup vapor to the column;
- reboiler duty.

No unmodeled reboiler-to-sump internal stream crosses the combined boundary.

## Ownership Table

| Quantity | V2 first-layer owner | Type | Not an owner |
|---|---|---|---|
| Component inventory | control-volume material balance | differential | imported phase holdups |
| Internal energy | control-volume energy balance | differential | stored phase enthalpy sheets |
| Liquid composition | inventory reconstruction | algebraic | product specification |
| Temperature | internal-energy/property closure | algebraic | relaxation ODE |
| Vapor composition | phase equilibrium | algebraic | separate vapor state |
| Pressure | prescribed ordered profile | parameter | EOS inversion, hydraulics |
| Liquid flow | Francis weir law | algebraic | imported flow profile/blend |
| Vapor flow | one declared simplified traffic law | algebraic/parameter | energy solve plus nominal cap |
| Reflux/distillate composition | reflux-drum liquid composition | algebraic | fixed component draw |
| Bottoms composition | bottom liquid composition | algebraic | fixed component draw |
| Condenser transfer | total-condenser balance | algebraic | dry tray inventory |
| Feed split | one declared source or flash basis | algebraic/parameter | second per-step reinterpretation |

No row may acquire a second active owner without a new architecture decision
and equation-count audit.

## Differential States

For every inventory-bearing control volume `j`:

```text
N[j,k] = total moles of component k
U[j]   = total internal energy
```

There are no independent `ML`, `MV`, `x`, `y`, `T`, or `P` differential
states in the first layer.

## Algebraic Variables

For every inventory-bearing control volume:

```text
NL[j]          liquid phase amount
x[j,k]        liquid composition
T[j]           temperature
```

For every equilibrium vapor outlet:

```text
y[j,k]        vapor composition
```

For internal trays:

```text
L[j]           Francis liquid outflow
```

The first layer treats `P[j]` as prescribed data and vapor traffic as the
output of one declared simplified traffic law.

## Governing Equations

### Interior tray material balance

For tray `i` and component `k`:

```text
dN[i,k]/dt =
    L[i-1] * x[i-1,k]
  + V[i+1] * y[i+1,k]
  + F[i,k]
  - L[i] * x[i,k]
  - V[i] * y[i,k]
```

### Interior tray energy balance

```text
dU[i]/dt =
    L[i-1] * hL[i-1]
  + V[i+1] * hV[i+1]
  + H_feed[i]
  + Q[i]
  - L[i] * hL[i]
  - V[i] * hV[i]
```

All enthalpies and internal energies come from the same property-provider
basis.

### Inventory reconstruction

With negligible vapor holdup:

```text
N[i,k] = NL[i] * x[i,k]
sum_k x[i,k] = 1
U[i] = NL[i] * uL(T[i], P[i], x[i])
```

### Equilibrium vapor

The exiting vapor satisfies the selected backend's phase-equilibrium
relation:

```text
fL[i,k](T[i], P[i], x[i]) = fV[i,k](T[i], P[i], y[i])
sum_k y[i,k] = 1
```

A documented backend-certified equivalent may be used. No artificial
phase-transfer relaxation appears in the balances.

### Liquid hydraulics

Liquid volume and head are:

```text
VL[i] = NL[i] / rhoL(T[i], P[i], x[i])
h[i]  = VL[i] / A[i]
```

The sole internal liquid-flow equation is:

```text
L[i] = C_F * C_hyd[i] * l_weir[i]
       * max(h[i] - h_weir[i], 0)^(3/2)
       * rhoL[i]
```

An imported liquid profile may initialize `NL` or calibrate documented
geometry parameters. It is never blended into `L[i]` at runtime.

### Simplified vapor traffic

The first layer uses one declared constant-molar traffic law:

```text
V[i] = V_boilup + sum(vapor feed entering on or below i)
```

This is an explicit modeling approximation. Vapor flow is not simultaneously
computed from an energy closure, pressure conductance, previous-step value,
and profile cap.

### Total condenser and reflux drum

The total condenser transfers all top vapor component flow into condenser
liquid. The reflux drum balances are:

```text
dN_D[k]/dt = V_top * y_top[k] - (R + D) * x_D[k]
dU_D/dt    = V_top * hV_top - (R + D) * hL_D - Q_C
N_D[k]     = NL_D * x_D[k]
U_D        = NL_D * uL(T_D, P_D, x_D)
```

Reflux and distillate compositions are both `x_D`.

### Combined reboiler and sump

```text
dN_B[k]/dt =
    L_in * x_in[k]
  - B * x_B[k]
  - V_boilup * y_B[k]

dU_B/dt =
    L_in * hL_in
  + Q_R
  - B * hL_B
  - V_boilup * hV_B
```

`y_B` is in equilibrium with `x_B` at `T_B,P_B`.

## Operating Degrees Of Freedom

The dynamic open-loop benchmark may hold a known steady operating point's
`R`, `D`, `B`, `V_boilup`, `Q_C`, and `Q_R` fixed for residual and disturbance
verification.

A steady-state solve must not fix all six blindly. Before solving, it must
publish:

- specified feed and pressure profile;
- selected operating specifications;
- unknown terminal flows and duties;
- one equation owner for each unknown;
- exact unknown/equation count;
- controller/MV ownership if controllers are later introduced.

Controllers are prohibited during the first natural-model acceptance run.

## Equation-Count Invariant

Let:

```text
J = number of inventory-bearing control volumes
C = number of components
E = number of inventory volumes with an equilibrium vapor outlet
H = number of Francis liquid-flow links
```

The first-layer dynamic model has `J*(C+1)` differential states: `J*C`
component inventories and `J` internal energies.

For each liquid-only inventory volume, the algebraic reconstruction has
`C+2` unknowns (`NL`, `x[1:C]`, and `T`) and `C+2` equations (component
reconstruction, composition normalization, and energy reconstruction).

For each inventory volume with an equilibrium vapor outlet, the algebraic
reconstruction has `2*C+2` unknowns (`NL`, `x[1:C]`, `T`, and `y[1:C]`) and
`2*C+2` equations (component reconstruction, liquid normalization, energy
reconstruction, `C` phase-equilibrium equations, and vapor normalization).

Each Francis link adds one liquid-flow unknown and one hydraulic equation.
The resulting algebraic core has
`(J-E)*(C+2) + E*(2*C+2) + H` unknowns and the same number of equations.
Therefore the physical state/reconstruction/hydraulic core is square before
operating degrees of freedom are added. Every terminal flow or duty promoted
to an unknown must add exactly one independent operating specification. Gate
artifacts must print the instantiated counts and rank; this invariant is not
a substitute for that audit.

## Explicit Exclusions

The first v2 layer shall not contain:

- tray vapor-holdup states;
- hydraulic pressure calculation;
- pressure inferred from vapor inventory;
- equilibrium-relaxation transfer;
- phase-total relaxation;
- profile-blended liquid flow;
- profile-capped vapor flow;
- previous-step flow ownership;
- stage-specific equation exceptions;
- hidden projection of accepted states;
- controller action used to create apparent steadiness;
- fallback property values in an accepted result.

## Phased Validation

### Gate A: source-equation assembly

Reproduce the already accepted Skogestad source-topology steady profile and
feed disturbance with the new v2 equation assembly. This is a regression
gate for indexing, terminal balances, composition reconstruction, and
integration.

Failure stops v2 before energy or hydraulics are added.

### Gate B: one-volume energy/property closure

Verify one inventory-bearing equilibrium volume with prescribed pressure:

- exact component and energy reconstruction;
- consistent property basis;
- full structural and numerical rank;
- identical root from predefined perturbations;
- stable response to a small energy or feed disturbance.

Failure stops v2 before a column solve.

### Gate C: five-volume prescribed-pressure Francis column

Build one five-inventory-volume case with an independently reproduced steady
reference:

- algebraic total condenser, which is not counted as an inventory volume;
- reflux drum;
- rectifying tray;
- feed tray;
- stripping tray;
- combined reboiler/sump.

Use the equations in this document, prescribed pressure, negligible vapor
holdup, simplified vapor traffic, and Francis hydraulics as the sole liquid
flow owner. Geometry or hydraulic coefficients must be documented parameters
fitted independently of the acceptance run. Require:

- physical residual `<1e-7`;
- exact component/energy telescoping;
- positive inventories and flows;
- common solution from predefined starts;
- stable short dynamics from the solved state;
- nonbinding imported-profile diagnostics.

One failed case stops the architecture. No tray-count ladder follows.

### Gate D: production tray count

Scale the unchanged Gate C equations directly to the production tray count.
No new physical owner or case-specific tray equation is permitted.

### Gate E: pressure layer

Only after Gate D passes may prescribed pressure be replaced by one
simultaneous algebraic pressure-drop network.

### Gate F: vapor-inventory layer

Explicit vapor holdup may be considered only after Gate E passes. Adding it
requires a new ownership table, index/rank audit, and pressure-volume-energy
derivation. It is not an optional switch on the first-layer equations.

## Stop Rules

At every gate, stop if the model:

- lacks a square full-rank equation registry;
- has no independently known or reproduced steady reference;
- cannot reach the declared residual tolerance from predefined starts;
- requires clipping, profile forcing, relaxation transfer, or controller
  action to remain bounded;
- fails exact global component or energy telescoping;
- introduces a second active owner for any quantity;
- needs case-specific interior tray logic.

After a failed gate, do not change tolerances, add tray counts, or sweep
solver settings. Revisit equations, ownership, or the selected modeling level.

## First Authorized Implementation

After review of this contract, the first authorized code is only:

1. a v2 control-volume and equation registry in a new namespace;
2. a structural-rank audit;
3. a source-equation Gate A residual comparison.

No DWSIM, Francis, pressure, vapor-holdup, controller, initializer, or dynamic
production integration code belongs in that first increment.
