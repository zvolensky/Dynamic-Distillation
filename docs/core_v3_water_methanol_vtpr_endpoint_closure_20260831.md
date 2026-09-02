# Core V3 stationary endpoint closure audit

- Finding: `active_bound_has_only_marginal_local_descent`
- Decision: `investigate_generic_energy_closure_before_any_second_solve`
- Active coordinate bounds: `NV[combined_reboiler_sump,Methanol] (upper)`
- Base scaled residual: `3.783530e-03`
- Best outward probe residual: `3.783530e-03`
- Base/best outward least-squares cost: `7.922971e-05 / 7.922680e-05`
- Global external energy rate: `-1.247707e+07 BTU/h`
- Energy residuals have one sign: `False`
- Component-specific logic: `False`
- Nonlinear solve, bound change, equation change, or timestep: `False`

The audit discovers variables, components, volumes, links, and energy terms from the Core V3 ledgers and topology.
