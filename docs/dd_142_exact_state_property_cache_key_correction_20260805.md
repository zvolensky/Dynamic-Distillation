# DD-142 Exact-State Property Cache-Key Correction

## Change

`ThermoProviderV1` now keys liquid-density and heat-capacity cache entries by the exact normalized temperature, pressure, and composition values. The former `0.001` temperature/pressure and eight-decimal composition rounding is removed.

Exact repeated states still reuse cached properties. Distinct states, including finite-difference perturbations, cannot inherit a neighboring state's property value.

## Scope

- Production files changed: `thermo_provider_v1.py` only.
- Density and heat-capacity caches use the same exact-state key helper.
- DWSIM property calculations, equations, solver settings, finite-difference steps, and physical states are unchanged.
- No residual, Jacobian, solve, state advance, timestep, or trajectory was executed as part of the correction.

## Verification

- Nearby temperature states produce distinct density and Cp values.
- Reversing query order reverses the output sequence, not the state-to-value mapping.
- An exact repeated state still records one miss followed by one hit.
- Existing provider tests remain passing.

The correction does not by itself reopen solver work. A separately frozen cross-process Jacobian repeatability proof is required.
