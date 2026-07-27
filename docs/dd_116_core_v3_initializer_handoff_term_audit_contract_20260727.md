# DD-116 Frozen Core V3 Initializer Handoff Term Audit Contract

- Base commit: `f324926e57f9d9d3f4b08dff1238ee37cf7b62cd`
- Contract payload SHA-256: `c82a9ebda4657fab2bc086a283d455638f9cd423f85cd1b745c879124bdf1c00`
- Frozen snapshots: `t=0`, refined `t=0.5 s`, refined `t=1.0 s`
- Permitted live work: exactly three residual/property evaluations
- Prohibited: solve, Jacobian, timestep, controller, trajectory, or initializer

The audit independently expands every component and energy balance into signed physical terms, reconciles those sums against the immutable DD-114/DD-115 rates, and ranks the contributors to the largest rate changes. It may distinguish an explained non-steady transient from an ownership or equation discontinuity. Passing authorizes only a property-free structural study of whether a zero-rate or slow-start state is feasible under the retained physical constraints.
