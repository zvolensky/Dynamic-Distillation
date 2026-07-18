# DD-079 Gate A Dynamic-Response Comparison

- Classification: `dd079_gate_a_dynamics_passed`
- Decision: `authorize_gate_b_one_volume_energy_property_closure`
- Horizon/output interval: `500.0 / 1.0 min`
- Primary integrator: `BDF`
- Refinement integrator: `Radau`
- Trajectory parity tolerance: `1e-09`
- Integration refinement tolerance: `1e-07`
- Conservation tolerance: `1e-10`

## Cases

| Case | V2/reference | BDF/refinement | Total closure | Light closure | Domain |
|---|---:|---:|---:|---:|---:|
| nominal_profile_drift | 3.851e-11 | 1.362e-10 | 0.000e+00 | 1.363e-15 | True |
| feed_plus_1_percent | 4.970e-13 | 1.392e-09 | 2.426e-15 | 2.764e-12 | True |
| bounded_perturbed_state | 3.673e-13 | 1.600e-09 | 2.079e-15 | 7.300e-13 | True |

## Interpretation

All comparisons use the same initial state, output grid, exact feed-event segmentation, and tight solver tolerances. The independent reference calls the accepted direct Skogestad translation and does not call the v2 evaluator.

The conservation gate uses external-balance accumulator states integrated by the solver. Separate trapezoidal values on the saved output grid are reported as quadrature diagnostics and are not confused with differential or solver closure.

No clipping, projection, holdup floor, profile substitution, controller, DWSIM property, energy equation, mini8 equation, or historical trajectory was used.

## Authorization

Gate A is complete. Gate B may begin on one representative mini8 inventory volume with prescribed pressure and live DWSIM properties. The five-volume Gate C solve remains unauthorized.
