# DD-167 Core V3 Seven-Volume Structural Gate

## Purpose

DD-167 begins the controlled scale-up from the accepted five-volume Core V3
reference. It asks only whether the same equation ownership can be generated
for a larger generic topology without losing squareness, structural rank,
conservation, or thermodynamic-provider discipline.

This increment performs no live property evaluation, nonlinear solve,
timestep, or dynamic integration.

## Topology

The generated topology contains:

- one reflux drum;
- two rectifying interior volumes;
- one feed volume;
- two stripping interior volumes;
- one combined reboiler/sump volume.

The topology builder accepts rectifying and stripping section counts. Volume
and link identities are generated from section roles; no physical stage number
is embedded in production model logic.

## Preserved Physics And Ownership

- Conserved component and energy balances are assembled for every volume.
- Every non-drum volume has full imposed-phase fugacity equilibrium.
- Every interior liquid link is owned only by Francis hydraulics.
- Every vapor link is an independent energy-owned algebraic flow.
- Pressure, reflux, feed, reboiler duty, terminal holdup targets, and hydraulic
  geometry remain prescribed structural inputs.
- Condenser duty remains solved by the total-condenser boundary.
- DWSIM remains the declared governing provider.
- TP flash remains diagnostic only; independent PR remains validation only.
- No profile forcing, fallback, clipping, projection, relaxation, or controller
  equation is introduced.

## Result

| Metric | Result |
|---|---:|
| Components | 3 |
| Physical volumes | 7 |
| Unknowns | 56 |
| Equations | 56 |
| Structural rank | 56 |
| Structural nullity | 0 |
| Energy-owned vapor links | 6 |
| Francis liquid links | 5 |
| Full-fugacity rows | 18 |
| Component-balance rows | 21 |
| Energy-balance rows | 7 |
| Symbolic component conservation | Pass |
| Symbolic energy conservation | Pass |
| Provider-ownership gate | Pass |
| Live property calls | 0 |
| Nonlinear solves | 0 |
| Timesteps/integration | 0 |

The generic count is

```text
unknowns = equations = 2 * number_of_volumes * (number_of_components + 1)
```

and a separate eight-volume/four-component test also retains full structural
rank. The original five-volume default remains unchanged and its focused
registry tests continue to pass.

## Decision

**DD-167 passes.** The Core V3 ownership pattern scales structurally from five
to seven volumes. This is necessary evidence, but it does not establish a
numerical root or dynamic viability for the larger model.

The next authorized increment is one separately frozen live-DWSIM residual and
finite-difference Jacobian audit at a physically constructed seven-volume
reference state. It must check numerical rank, conditioning, finite-difference
stability, conservation, property ownership, physicality, and call cost.

No nonlinear solve, stationary-root campaign, timestep, initializer, or dynamic
integration is authorized until that numerical gate passes.

## Artifacts

- `src/dynamic_distillation/core_v3/provider_governed_registry_v1.py`
- `tests/test_core_v3_scaled_topology_v1.py`
- `tools/run_core_v3_scaled_structural_gate.py`
- `logs/dd167_core_v3_seven_volume_structural_gate_20260806.json`
