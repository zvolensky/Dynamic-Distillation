# DD-140 DD-138 Jacobian Repeatability Result

- Classification: `jacobian_process_or_order_dependent`
- Decision: `stop_solver_work_and_isolate_provider_derivative_state`
- Within-process repeatable: `True`
- Cross-process/order repeatable: `False`
- DD-138 captured matrices reproduced: `False`
- Finite-difference step stable: `False`
- Worst cross-process relative Frobenius difference: `4.184301622e-03`
- Worst `h` versus `h/2` relative Frobenius difference: `2.102432855e-03`
- Worst singular-spectrum relative change: `7.872590921e-02`
- Condition range: `2.084335314e+05` to `7.306833438e+05`
- Aggregate DWSIM calls: `28227`
- Wall clock: `64.979 s`

No nonlinear solve, correction, state advance, timestep, or trajectory was attempted.

## Interpretation

All 12 same-process comparisons are bit-for-bit identical. The failure appears only across fresh process/order histories. The largest affected entries are density/enthalpy-sensitive derivatives:

- coarse `h`: sump level rows versus sump temperature differ by `0.4646983`;
- coarse `h/2`: the same entries differ by `0.9293966`;
- refined `h`: drum energy versus drum temperature differs by `0.7805882`;
- refined `h/2`: the same entry differs by `1.5628156`.

The near doubling as the step halves is evidence of a small process-history-dependent property/residual numerator offset divided by the finite-difference step. It is not the expected convergence pattern of ordinary central-difference truncation error. Differences occur in 31 registered entries across temperature, pressure, and inventory-rate columns; the largest affect energy, Francis hydraulics, and terminal level rows.

This explains why complete residual replay can be exact while Jacobians and frozen-Jacobian trajectories differ. Solver work remains stopped. The next bounded diagnostic should capture the exact plus/minus residual and provider-property packets for selected affected columns in fresh process orders, with no matrix campaign or solve.
