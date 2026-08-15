# DD-231 Full-C3/C4 Aligned-Density Stationary Root

## Result

DD-231 succeeds decisively. Both independent starts converge to the same full 20-stage stationary state.

| Metric | Source start | Independent start |
|---|---:|---:|
| Function evaluations | 69 | 241 |
| Jacobian evaluations | 58 | 204 |
| Scaled residual infinity norm | `8.26e-14` | `4.22e-15` |
| Worst endpoint condition | `6.20e5` | `6.20e5` |
| Spectrum step change | `4.95e-9` | `4.10e-9` |
| Active bounds | 0 | 0 |

Physical root disagreement is only `5.95e-13`, far below the `1e-7` requirement. Every physicality, phase, conservation, rank, condition, provider-routing, call, and wall gate passes.

The run uses `821,564` logical provider calls in `179.634 s`. It performs no timestep or dynamic integration.

## Stationary operating point

- Feed: `7,142.974 lbmol/h`
- Distillate: `2,431.550 lbmol/h`
- Bottoms: `4,711.424 lbmol/h`
- Condenser duty: `-50.0522 MMBTU/h`
- Reboiler duty: `54.7060 MMBTU/h` specified
- Top temperature: `119.179 F`
- Bottom temperature: `219.908 F`
- Distillate composition, propane/butane/pentane: `0.897031 / 0.102937 / 0.0000328`
- Bottoms composition, propane/butane/pentane: `0.042411 / 0.789151 / 0.168438`

Distillate plus bottoms equals feed to about `2e-9 lbmol/h`.

## Meaning

The earlier full-column solve failure was not proof that the model equations lacked a steady state. DWSIM's discontinuous declared liquid-density root corrupted the hydraulic derivative. Once liquid density is evaluated from the smooth, phase-explicit, parameter-aligned PR liquid root and the fixed DD-230 coordinate scale is used, the same physical equation system has a unique, reproducible, tightly closed root.

## Decision

The full-column stationary root is accepted. The next permitted work is a structural full-column dynamic-DAE contract that maps this root into dynamic state and history storage while preserving the accepted provider routing. No dynamic step has yet been authorized or taken.
