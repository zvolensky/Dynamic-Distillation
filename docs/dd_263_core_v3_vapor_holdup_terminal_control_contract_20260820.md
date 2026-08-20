# DD-263 C3/C4 Vapor-Holdup Terminal Level-Control Contract

- Classification: `vapor_holdup_terminal_control_structure_passed`
- Decision: `authorize_separately_frozen_live_zero_motion_control_audit`
- Structural system: `262 x 262`
- Structural rank: `262`
- Historical contracts or results modified: `False`
- Property call, residual, solve, timestep, or dynamics: `False`

## Workbook Geometry

- Reflux drum diameter: `12.1000 ft`
- Reflux drum tangent length: `36.3000 ft`
- Reflux drum heads: `two hemispherical`
- Reflux drum gross capacity: `5101.729438 ft3`
- Bottom sump diameter: `18.1759 ft`
- Bottom sump height: `12.0000 ft`
- Bottom sump gross capacity: `3113.601134 ft3`

The dimensions are read through the normalized Excel loader from the C3/C4 workbook. They are not copied into the controller setup. The reboiler vapor extension remains part of bottom vapor capacity but is not part of the sump liquid-level calculation.

## Ownership

- The reflux-drum level controller manipulates distillate flow `D`.
- The bottom-sump level controller manipulates bottoms flow `B`.
- Product compositions use the live terminal liquid compositions.
- Reflux and reboiler duty remain fixed inputs for this first control step.
- Controller memories are new differential states.
- Fixed `D/B` parameters are removed from the controlled contract.

## Boundary

This is a structural pass only. The next permitted work is one separately frozen live zero-motion audit that reconstructs terminal levels from live liquid density and initializes controller memory bumplessly. A controlled trajectory is not yet authorized.
