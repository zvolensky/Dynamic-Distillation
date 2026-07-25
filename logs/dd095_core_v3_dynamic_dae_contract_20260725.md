# DD-095 Core V3 Dynamic DAE Structural Contract

- Classification: `dd095_core_v3_dynamic_dae_structural_contract_passed`
- State coordinates: `15`
- Derivative/algebraic solve variables: `15 / 23`
- Rows/rank: `38 / 38`
- Component/energy conservation: `True / True`
- Structural gate: `True`

## Storage And Index

- Internal energy: `U[j]=NL[j]*uL(T[j],P[j],x[j]); dU[j]/dt is assembled by the provider-consistent chain rule against dN[j,k]/dt`
- Index status: `structural implicit-index-1 candidate; numerical leading-Jacobian rank and consistent-derivative audits remain required`
- Independent internal-energy coordinates are intentionally absent.
- A live leading-Jacobian audit is required before an index-1 claim.

## Open-Loop Ownership

- Pressure, feed, reflux, reboiler duty, geometry, and DD-094 product draws are fixed parameters.
- Four vapor links and condenser duty remain energy-owned algebraic quantities.
- Francis equations are the only internal liquid-flow owner.
- No terminal-level constraints, controllers, profiles, caps, relaxation, clipping, or fallback are present.

## Design-Point Qualification

- DD-094 drum temperature: `133.713293 F`
- Frozen source drum temperature: `117.816385 F`
- Difference: `15.896909 F`
- DD-094 is a reduced-model feasibility root, not a production design-point acceptance result.

## Scope

- No property evaluation or numerical mass matrix was attempted.
- No nonlinear solve, controller, initializer, or integration was attempted.

## Authorization

DD-096 may be drafted and precommitted as one live leading-Jacobian, provider-chain-rule, conservation, and consistent-derivative audit. Numerical mass-matrix implementation and dynamic integration remain unauthorized.
