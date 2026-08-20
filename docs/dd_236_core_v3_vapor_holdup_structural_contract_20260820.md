# DD-236 Core V3 Vapor-Holdup Structural Contract

- Classification: `vapor_holdup_structural_contract_passed`
- Decision: `authorize_live_vapor_property_and_eos_residual_implementation`
- Historical Core V3 contracts/results modified: `False`
- Live properties, residual, solve, timestep, or trajectory: `False`

## Structural Results

- Five-volume development contract: `63 x 63`, rank `63`
- Twenty-volume C3/C4 contract: `258 x 258`, rank `258`
- Conserved states per volume: `N_L[j,k]` and `N_V[j,k]`
- Vapor composition: derived only as `N_V/sum(N_V)`
- Pressure: vapor EOS + interstage pressure drop + one top anchor
- Energy storage: `U_total = U_L + U_V`
- Phase transfer: equal and opposite in liquid/vapor balances

## Boundary

The positive volume values used here are structural test values, not accepted tray or vessel geometry. Real free-volume geometry is mandatory before a live property or numerical residual audit.
