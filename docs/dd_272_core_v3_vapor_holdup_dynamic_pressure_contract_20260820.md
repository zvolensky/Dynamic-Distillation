# DD-272 Vapor-Holdup Dynamic-Pressure Contract

- Classification: `vapor_holdup_dynamic_pressure_structure_passed`
- Decision: `authorize_separately_frozen_fixed_duty_residual_audit`
- C3/C4 system/rank: `262 x 262 / 262`
- Generic two-component system/rank: `202 x 202 / 202`
- Pressure-anchor rows: `0`
- Condenser-duty specification rows: `1`
- Property call, residual, solve, or timestep: `False`

## Correction

The fixed reflux-drum pressure equation is removed. It is replaced one-for-one by a specified condenser-duty equation, while `Q_C` remains coupled to the reflux-drum total-energy balance. The system therefore remains square and full rank.

Pressure is now structurally free to respond to vapor inventory, temperature, EOS free-volume closure, and tray pressure losses. No pressure-dynamic result is claimed yet. One separately frozen live fixed-duty residual and Jacobian audit is required before a timestep.
