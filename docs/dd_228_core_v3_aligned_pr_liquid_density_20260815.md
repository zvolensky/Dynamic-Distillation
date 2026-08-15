# DD-228 Parameter-Aligned PR Liquid Density

## Purpose

DD-227 showed that DWSIM's declared liquid density switches discontinuously between roots near one lower interior state. DD-228 tests a phase-explicit density calculation without changing the governing column.

The candidate uses the same extracted Peng-Robinson component parameters and binary interactions as the independent thermo validator. It selects the smallest positive compressibility root as the liquid root and computes molar density from `P/(ZRT)`.

## Result

The candidate passes:

- all sampled states have three ordered positive PR roots;
- the selected liquid density remains positive;
- the source endpoint gives `0.5034328 lbmol/ft3`;
- the independent endpoint gives `0.5046996 lbmol/ft3`;
- density derivatives are about `-0.167` and `-0.171 lbmol/ft3/F`;
- relative derivative spread across four step sizes is below `5e-10` at both endpoints;
- no DWSIM, solver, timestep, or integration call occurs.

The smooth density lies between DWSIM's two discontinuous branches. This is encouraging but not enough to adopt it as a governing property.

## Decision

One frozen full-residual and Jacobian parity audit is authorized. It may route liquid density to this aligned PR calculation while keeping DWSIM as the authority for imposed-phase fugacity and phase enthalpy. It must compare residual movement, rank, condition, step stability, conservation, and physicality at both exact DD-223 endpoints.

A root solve and dynamics remain unauthorized.
