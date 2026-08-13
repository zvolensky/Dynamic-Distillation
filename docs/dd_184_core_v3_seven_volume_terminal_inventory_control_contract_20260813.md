# DD-184 Seven-Volume Terminal Inventory Control Contract

## Verdict

**DD-184 passes the structural gate.** The accepted open-loop seven-volume
DAE now has a square, topology-generic terminal inventory-control ownership
ledger.

## Ledger

- Physical volumes: `7`
- Differential states: `23`
- Derivative variables: `23`
- Algebraic variables: `35`
- Rows / structural rank: `58 / 58`
- Structural nullity: `0`
- Controller states / rates / outputs / rows: `2 / 2 / 2 / 4`

## Ownership Change

- Distillate and bottoms rates are no longer fixed parameters.
- Positive log-ratio controller outputs own the live product rates.
- The top output enters only top component and energy balances.
- The bottom output enters only bottom component and energy balances.
- Product component rates use each terminal's live liquid composition.
- Two PI memory states supply integral action; geometry-derived level
  fractions are the controlled variables.
- Every interior balance, equilibrium relation, Francis equation, and
  energy-owned vapor link is unchanged.

The equations are

```text
dI/dt = (Kc / Ti) * (level - level_setpoint)
log(product / reference) = I + Kc * (level - level_setpoint)
```

The positive sign is intentional: a high terminal level increases the product
draw. Log-ratio outputs keep both product rates positive.

## Geometry And Parameters

The structural contract carries the established C3/C4 vessel geometry and
prior positive PI constants so units and equation signs are explicit. DD-184
does not qualify those constants as tuned values.

## Scope Boundary

No property evaluation, residual evaluation, Jacobian evaluation, nonlinear
solve, controller execution, timestep selection, or dynamic integration
occurred. Passing does not show that the controlled DAE is numerically
conditioned or dynamically well tuned.

## Decision

Authorize one separately frozen live zero-time residual and leading-Jacobian
audit at the DD-169 root. Controller tuning, timestepping, and controlled
trajectories remain unauthorized.

## Artifacts

- `logs/dd184_core_v3_seven_volume_terminal_inventory_control_contract_20260813.json`
- `logs/dd184_core_v3_seven_volume_terminal_inventory_control_contract_20260813.md`
- `src/dynamic_distillation/core_v3/terminal_inventory_control_contract_v1.py`
- `tools/audit_core_v3_seven_volume_terminal_inventory_control_contract.py`
- `tests/test_core_v3_terminal_inventory_control_contract_v1.py`
