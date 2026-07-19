# DD-091 Core V3 Provider-Governed Structural Audit

- Architecture: `Core V3 - Provider-Governed Energy-Owned Equilibrium Architecture`
- Classification: `dd091_core_v3_structural_gate_passed`
- Unknowns/residuals: `40 / 40`
- Structural rank/nullity: `40 / 0`
- Full stage-fugacity rows: `12`
- Condenser bubble-fugacity rows: `3`
- Energy-owned vapor links: `4`
- Francis-owned liquid flows: `3`
- Component telescoping: `True`
- Energy telescoping: `True`
- Provider contract: `True`
- Structural gate: `True`

## Prohibited Uses

- TP flash in governing rows: `()`
- Independent PR in production rows: `()`
- Mixed-basis dependencies: `()`
- Interface fallbacks: `()`
- Fixed condenser duty: `False`
- Imported historical acceptance: `False`

## Scope

- No DWSIM or independent-PR property evaluation was attempted.
- No column residual was evaluated.
- No nonlinear solve, root import, mass matrix, or dynamic integration was attempted.
- The registry does not import a Core V2 residual owner.

## Authorization

DD-092 may perform exactly one precommitted Core V3 live residual, provider-ownership, conservation, and Jacobian audit. A root solve and dynamics remain unauthorized.
