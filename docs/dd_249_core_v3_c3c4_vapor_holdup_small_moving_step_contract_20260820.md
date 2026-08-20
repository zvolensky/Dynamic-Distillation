# DD-249 Vapor-Holdup Small Moving-Step Contract

- Payload SHA-256: `7bc61819dcaff38d36e44ca0b6dadc1bbc0d757cd13a3d4b7e40579ced0b99a2`
- Disturbance: `+0.1%` feed component rates and feed enthalpy.
- Comparison: one `0.25 s` backward-Euler step versus two `0.125 s` steps.
- Products, reflux, reboiler duty, and top-pressure anchor remain fixed.
- Condenser duty, pressure, vapor traffic, phase transfer, and both phase inventories remain solved.
- Solver: one frozen TRF configuration with a 28-color central Jacobian.
- Coordinate scaling: fixed from the accepted DD-247 Jacobian before execution.
- Retry, alternate step, controller action, or trajectory: `False`.

Failure stops trajectory work. Passing authorizes only one separately frozen short open-loop trajectory contract.
