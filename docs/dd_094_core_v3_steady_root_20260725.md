# DD-094 Core V3 Accepted Steady Root

Date: 2026-07-25

## Decision

DD-094 passes every frozen gate in its one authorized execution. This is the
first accepted provider-governed Core V3 steady root.

All three precommitted starts converge to the same positive, conservative,
phase-valid, interior root. The most independent pair differs by only
`2.47414e-10` in the frozen normalized physical comparison, well below the
`1e-7` requirement.

## Campaign Results

| Metric | Canonical | Perturbed | Independent | Gate |
|---|---:|---:|---:|---:|
| `nfev` | 47 | 42 | 55 | `<=500` |
| Wall time, s | 68.418 | 63.811 | 51.292 | reported |
| Final scaled residual infinity norm | `3.22e-15` | `2.89e-15` | `7.43e-11` | `<1e-8` |
| Minimum transformed bound distance | `0.182322` | `0.182322` | `0.182322` | `>1e-6` |
| Worst condition | `1373.6910` | `1373.6910` | `1373.6911` | `<1e8` |
| Maximum spectrum relative change | `4.21e-7` | `4.21e-7` | `3.91e-7` | `<0.25` |
| TP vapor fraction | `6.43829e-4` | `6.43829e-4` | `6.43829e-4` | `<=1e-3` |
| Start pass | yes | yes | yes | required |

Every endpoint retains full Jacobian rank `40/40` and local bubble rank
`3/3` at both finite-difference steps. There are no zero rows, zero columns,
off-registry couplings, active bounds, safeguards, projections, property
fallbacks, or provider-authority violations.

Component and energy telescoping remain near machine precision. TP-flash
`K*x_flash` identity and lever-rule closure pass, stable vapor is rejected,
and validation-only independent PR agrees with the direct-fugacity bubble.

## Accepted Root

The values below are from the canonical endpoint; the other two endpoints
are materially identical.

| Volume | Temperature F | Liquid amount lbmol | Liquid C3 | Liquid C4 | Liquid C5 |
|---|---:|---:|---:|---:|---:|
| Reflux drum | 133.713293 | 1388.900000 | 0.703001 | 0.283606 | 0.013393 |
| Rectifying tray | 154.422168 | 32.859247 | 0.500235 | 0.458420 | 0.041345 |
| Feed tray | 173.924644 | 45.855669 | 0.349298 | 0.563707 | 0.086995 |
| Stripping tray | 184.824013 | 54.424933 | 0.271950 | 0.623557 | 0.104492 |
| Reboiler/sump | 199.740489 | 794.000000 | 0.180880 | 0.667710 | 0.151411 |

Internal liquid flows are `5628.901`, `12792.976`, and `12811.306 lbmol/h`.
Bottom-to-top vapor links are `7753.998`, `7735.668`, `7714.567`, and
`8038.146 lbmol/h`. Products are `D=2085.666` and `B=5057.308 lbmol/h`.
Solved condenser duty is `Q_C=-52.515728 MMBTU/h`.

The drum is `20.709 F` colder than its supplying rectifying stage. Hydraulic
liquid heights are `0.35064`, `0.52149`, and `0.55707 ft`, all below the
`1.5 ft` tray spacing.

## Design-Point Qualification

DD-094 establishes a physical root for the reduced five-volume architecture;
it does not establish the production C3/C4 operating point. The accepted drum
is `15.897 F` warmer than the frozen source (`133.713 F` versus `117.816 F`)
because its liquid contains materially less propane (`0.7030` versus
`0.9057`). Its product rates and bottom composition likewise are not
production acceptance targets. See the DD-095 dynamic contract for the
separate feasibility and design-point gates.

## Authorization

DD-094 authorizes one next artifact only: a structural dynamic-DAE contract
covering conserved component and internal-energy states, algebraic variables
and equations, mass-matrix ownership, DAE index, and consistent
initialization requirements.

It does not authorize mass-matrix coding, initialization solving, or dynamic
integration.
