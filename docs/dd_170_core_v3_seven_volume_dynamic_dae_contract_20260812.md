# DD-170 Seven-Volume Dynamic DAE Structural Contract

## Verdict

**DD-170 passes the structural gate.** The accepted DD-169 stationary root is
mapped into a conserved, open-loop dynamic DAE ledger without executing
dynamics.

## Ledger

- Physical volumes: `7`
- Component inventory coordinates: `21`
- Derivative variables: `21`
- Algebraic variables: `33`
- Rows / structural rank: `54 / 54`
- Structural nullity: `0`

| Equation block | Count |
|---|---:|
| Component inventory balances | 21 |
| Energy balances | 7 |
| Full fugacity equilibrium | 18 |
| Francis liquid hydraulics | 5 |
| Condenser bubble equations | 3 |

The DD-169 stationary system was `56 x 56`. The dynamic ledger is `54 x 54`
because the accepted distillate and bottoms rates become fixed open-loop
parameters, while the 21 component-inventory rates replace the stationary
component-balance unknown ownership. This is an ownership change, not a loss
of component or energy equations.

## Ownership

- Differential states are component inventories only.
- Internal energy is derived from inventory, temperature, and provider
  properties; it is not an independent coordinate.
- Temperatures, phase compositions, liquid flows, vapor flows, and condenser
  duty are algebraic variables.
- Pressure, feed, reflux, reboiler duty, geometry, and accepted DD-169 product
  rates are fixed open-loop parameters.
- No controller, terminal amount constraint, imported profile, flow cap,
  relaxation, clipping, projection, or fallback is present.
- Balance dependencies are generated from topology links, not named interior
  stages. Only the top condenser boundary and bottom product boundary retain
  explicit terminal roles.

## Scope Boundary

No property evaluation, numerical mass-matrix evaluation, nonlinear solve,
timestep selection, controller execution, or dynamic integration occurred in
DD-170.

## Decision

Authorize one separately frozen live numerical leading-Jacobian and
consistent-derivative audit at the accepted DD-169 root. Dynamic integration
remains unauthorized.

## Artifacts

- `logs/dd170_core_v3_seven_volume_dynamic_dae_contract_20260812.json`
- `logs/dd170_core_v3_seven_volume_dynamic_dae_contract_20260812.md`
- `tools/audit_core_v3_seven_volume_dynamic_dae_contract.py`
- `tests/test_core_v3_scaled_dynamic_dae_contract_v1.py`
