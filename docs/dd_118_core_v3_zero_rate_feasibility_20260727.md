# DD-118 Core V3 Zero-Rate Feasibility Audit

- Classification: `dd118_passed`
- Decision: `authorize_frozen_live_zero_rate_readiness_contract`
- Zero-rate DAE core: `46 x 46`, rank `46`
- All-target zero-rate system: `52 x 46`, rank `46`
- Surplus exact targets: `6`
- Global targets to release: `4`
- Terminal scale selections retained for live audit: `2`
- Property/residual/Jacobian/solve/timestep calls: `0/0/0/0/0`

The current initializer cannot generically impose all component and energy rates equal to zero while preserving every DD-112 global inventory, stored-energy, and terminal-holdup equality. The zero-rate DAE itself is square and structurally viable. A successor should keep the two terminal holdups as physical scale selections, demote the three inherited global component totals and one inherited global energy total to diagnostics, and verify the resulting overdetermined terminal-scaled system numerically before any root solve.

## Meaning

DD-112 was solving a different problem from a steady-state initializer. It
preserved the previous model's whole-column component inventories, whole-column
stored energy, and both terminal holdups while minimizing 19 rates. Those 19
rates provided only 13 feasible selection directions, so setting every rate
exactly to zero leaves six surplus target equations.

The three-component zero-rate DAE alone is `46 x 46`, structural rank `46`.
Adding all six old initializer targets produces a `52 x 46` system with rank
`46`; the unmatched rows are exactly:

- three inherited global component totals;
- one inherited global stored-energy total;
- reflux-drum total holdup;
- combined reboiler/sump total holdup.

The same result holds generically for two components: the zero-rate core is
`36 x 36`, rank `36`, while the old targets create five surplus equations.

## Successor Boundary

The next architecture should:

1. Set all component and independent energy rates exactly to zero.
2. Retain every live DAE, equilibrium, hydraulic, pressure, and storage row.
3. Retain drum and sump total holdups provisionally to select terminal scale.
4. Remove inherited global component and stored-energy totals from exact
   constraints; report their resulting values instead.
5. Perform one frozen live residual/Jacobian readiness audit before any root
   solve.

DD-118 does not prove that a physical steady root exists. It proves that the
previous initializer targets were structurally the wrong requirements for
seeking one, and that a corrected zero-rate numerical audit is justified.
