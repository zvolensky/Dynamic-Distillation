# DD-109 Conserved N/U Pressure Numerical Result

- Classification: `dd109_failed`
- Decision: `stop_conserved_nu_pressure_numerical_path`
- Wall clock: `3.564 s`
- Provider calls: `5993`
- Colored/full difference: `0.000000e+00`

## Formal Result

The frozen result is a failure and is not rerun. Two physical-reporting gates
fail because they require every entry of `liquid_height_ft` to be finite and
positive. The governing Core V3 property record intentionally stores `NaN`
for the reflux drum and combined reboiler/sump because only the three Francis
hydraulic tray volumes own tray liquid heights. All three applicable heights
are finite and positive in both states. The dry-only terminal pressure link
also correctly carries zero liquid-head pressure drop.

This is a frozen gate-scope defect, not a failed numerical rank or storage-
manifold result. It cannot be corrected retroactively inside DD-109.

## Numerical Evidence

- All four colored leading Jacobians have rank `46/46`.
- The canonical full Jacobian also has rank `46/46`.
- Worst condition number is `4.30341e5`, below the `1e8` limit.
- Both lower-storage row blocks have rank `4/4` at both difference steps.
- Colored and full canonical Jacobians agree exactly to reported precision.
- Spectrum changes are `4.47e-7` and `5.89e-5`, below `0.25`.
- Canonical scaled storage closure is `4.77e-16`.
- Component and energy conservation remain near machine precision.
- Pressure ordering, positive inventories/flows, normalized compositions,
  provider provenance, call count, and wall-clock limits all pass.

## Decision Boundary

The raw result and formal failure stand. No nonlinear solve, initializer,
repair, timestep, or integration was attempted. Any reporting-only correction
or successor numerical contract requires an explicit governance decision; it
must not reuse DD-109's one-execution authorization silently.
