# DD-071 Direct Conserved Steady-State Registry

- Classification: `dd071_registry_structure_passed_combined_bottom`
- Decision: `authorize_numeric_residual_evaluator`
- Unknowns: `281`
- Residuals: `281`
- Difference: `0`
- Structural rank upper bound: `281`
- Structural nullity lower bound: `0`
- Selected topology: `combined_reboiler_vapor_and_sump_liquid_control_volume`

## Unknown Counts

| Block | Count |
|---|---:|
| conserved_component | 60 |
| conserved_energy | 20 |
| local_thermo | 40 |
| phase_amount | 40 |
| liquid_composition | 40 |
| vapor_composition | 40 |
| liquid_flow | 18 |
| vapor_flow | 19 |
| manipulated_variable | 4 |

## Residual Counts

| Block | Count |
|---|---:|
| local_component_closure | 60 |
| local_energy_closure | 20 |
| local_volume_closure | 20 |
| local_equilibrium | 60 |
| steady_component_balance | 60 |
| steady_energy_balance | 20 |
| liquid_hydraulics | 18 |
| vapor_pressure_drop | 19 |
| operating_specification | 4 |

## Ownership Failure

The proposed topology contains separate conserved partial-reboiler and liquid-only sump states. Their connecting liquid outlet is an unknown, but no hydraulic, valve, overflow, residence-time, or level relation owns it.

- Unowned unknown: `L_out[partial_reboiler_to_bottoms_sump]`

The selected correction combines reboiler vapor and sump liquid inside one conserved bottom control volume. The internal liquid transfer then crosses no control-volume boundary and is eliminated without adding an arbitrary equation.

## Selected Structure

- Unknowns: `281`
- Residuals: `281`
- Structural rank: `281`
- Structural nullity: `0`
- Structure gate: `True`

## Deferred Deliverables

This structural registry slice does not yet contain numerical property and balance evaluation. ChemSep, checkpoint, and perturbed residual vectors, numerical Jacobian rank, and nonlinear-solver work remain deferred to the next DD-071 implementation slice.

## Decision

The combined bottom control-volume registry is square and structurally full rank. Implement numerical residual evaluation next; a nonlinear solve remains unauthorized.
