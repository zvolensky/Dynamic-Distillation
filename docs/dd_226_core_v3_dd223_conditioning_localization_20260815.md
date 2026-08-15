# DD-226 DD-223 Conditioning Localization

## Plain-language result

The full-column equations do not currently look hopeless. Two numerical problems are mixed together.

First, one derivative is unreliable. When the finite-difference step is halved, the calculated sensitivity of `francis_hydraulics[stripping_volume_6]` to `T[stripping_volume_6]` almost doubles. This makes the largest Jacobian value almost double and explains the near-100% spectrum-change failure in DD-223.

Second, the variables and equations are poorly scaled relative to one another. The original matrix conditions are about `1.20e9` to `2.09e10`. Simple diagnostic row-and-column equilibration reduces them to about `631` to `1,274`. This does not change or solve the equations, but it shows that most of the alarming condition number is numerical scaling rather than an unavoidable physical singularity.

## Weak direction

The weakest direction is different from the unstable large derivative. It is dominated by liquid/vapor composition coordinates and component balances, especially the n-pentane balance chain in the reflux drum and upper rectifying volumes. This is where a solver has the least independent numerical leverage.

## Endpoint residuals

- The source-start endpoint's largest scaled residual is the n-propane component balance in `stripping_volume_6`: `4.3099236e-4`.
- The independent-start endpoint's largest scaled residual is the n-pentane component balance in `rectifying_volume_10`: `1.2317328e-2`.

The two endpoints therefore remain different failed states, as DD-223 already concluded.

## Decision

Do not alter the physical equations and do not retry the root solve yet. Run one small direct-column probe around the identified temperature/hydraulics derivative:

1. perturb only `T[stripping_volume_6]` at several fixed step sizes;
2. compare the direct derivative with the saved colored derivative;
3. record the liquid density, height, weir head, Francis flow, and residual on both sides.

If the direct derivative is stable, the colored sparsity grouping is wrong. If it is unstable, the discontinuity lies in the property/hydraulic evaluation path. Only after that distinction is resolved should fixed coordinate scaling be designed.

DD-226 uses zero model, provider, solver, timestep, or integration calls.
