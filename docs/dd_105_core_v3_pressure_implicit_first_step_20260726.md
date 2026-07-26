# DD-105 Pressure-Enabled First-Step Result

- Classification: `dd105_failed`
- Decision: `stop_before_pressure_step`
- Wall clock: `60.414 s`
- Provider calls: `68037`
- Inventory refinement: `6.276666e-02`
- Algebraic refinement: `1.671493e+00`
- Pressure refinement: `2.772612e+00 psi`

## Assessment

Both independently solved first steps are exact numerical roots. The `1.0 s`
and `0.5 s` residuals are `1.05e-13` and `9.00e-13`; all four endpoint
Jacobians are rank `42/42`, have no zero row or column, and remain below the
`1e8` condition limit. Conservation, provider ownership, pressure ordering,
the `68,037`-call ceiling, and the `60.414 s` wall-clock gate all pass.

The result nevertheless fails decisively because it is not grid independent.
Inventory refinement is `6.2767e-2`, algebraic-coordinate separation is
`1.6715`, and the pressure profiles differ by `2.7726 psi`. Peak absolute
component rate rises from about `37,353 lbmol/h` at `1.0 s` to
`48,025 lbmol/h` at `0.5 s`. The endpoint therefore depends materially on the
arbitrary duration assigned to the initial pressure handoff.

This is not evidence that the pressure-enabled equations are singular or that
the nonlinear solver failed. It shows that DD-094 is not a consistent initial
state for the pressure-enabled model and that one backward-Euler step cannot
serve as an initializer without embedding timestep-dependent inventory and
energy movement.

## Decision

Stop before pressure-enabled stepping. Do not sweep smaller timesteps, retry,
substep, relax refinement limits, or begin a trajectory. The next work must be
a separately specified pressure-enabled consistent-initialization problem
that permits conserved-state movement under explicit whole-column component
and energy constraints and terminal inventory ownership. It must not reuse
the retired checkpoint-repair or manual continuation architectures.
