# DD-072 Numerical Residual And Jacobian Audit

- Classification: `dd072_numerical_audit_passed`
- Gate passed: `True`
- Nonlinear solve attempted: `False`
- Live thermo: `DWSIM PR`
- Wall time: `60.72 s`

## Guess Results

| Guess | Valid | Scaled L2 | Component telescope | Energy telescope | Rank h | Rank h/2 |
|---|---:|---:|---:|---:|---:|---:|
| chemsep | True | 2.04121 | True | True | 281 | 281 |
| perturbed_chemsep | True | 2.04933 | True | True | 281 | 281 |
| checkpoint | True | 5.15485 | True | True | 281 | 281 |

## Reference Pattern Check

- Uncolored rank: `281`
- Unexpected numerical nonzeros: `0`
- Structurally allowed entries numerically zero: `468`
- Colored/uncolored maximum expected-entry difference: `0`

The structurally allowed pattern is intentionally an upper bound. Numerically zero allowed entries are reported, while any nonzero outside the registered graph fails the gate.

## Dominant Residuals

### chemsep

- `liquid_hydraulics[tray_18]`: scaled `0.713344`, raw `5095.4 lbmol_per_h`
- `liquid_hydraulics[tray_19]`: scaled `0.691161`, raw `4936.94 lbmol_per_h`
- `liquid_hydraulics[tray_14]`: scaled `0.495471`, raw `3539.14 lbmol_per_h`
- `liquid_hydraulics[tray_13]`: scaled `0.485894`, raw `3470.73 lbmol_per_h`
- `liquid_hydraulics[tray_12]`: scaled `0.475966`, raw `3399.81 lbmol_per_h`
- `liquid_hydraulics[tray_2]`: scaled `0.459569`, raw `3282.69 lbmol_per_h`
- `liquid_hydraulics[tray_15]`: scaled `0.406833`, raw `2906 lbmol_per_h`
- `liquid_hydraulics[tray_3]`: scaled `0.401401`, raw `2867.19 lbmol_per_h`

### perturbed_chemsep

- `liquid_hydraulics[tray_18]`: scaled `0.713497`, raw `5096.49 lbmol_per_h`
- `liquid_hydraulics[tray_19]`: scaled `0.692746`, raw `4948.27 lbmol_per_h`
- `liquid_hydraulics[tray_14]`: scaled `0.509572`, raw `3639.86 lbmol_per_h`
- `liquid_hydraulics[tray_13]`: scaled `0.489445`, raw `3496.09 lbmol_per_h`
- `liquid_hydraulics[tray_12]`: scaled `0.464528`, raw `3318.11 lbmol_per_h`
- `liquid_hydraulics[tray_2]`: scaled `0.462235`, raw `3301.73 lbmol_per_h`
- `liquid_hydraulics[tray_15]`: scaled `0.422428`, raw `3017.39 lbmol_per_h`
- `liquid_hydraulics[tray_3]`: scaled `0.403681`, raw `2883.48 lbmol_per_h`

### checkpoint

- `equilibrium[reflux_drum,n-Pentane]`: scaled `4.5065`, raw `4.5065 dimensionless`
- `equilibrium[reflux_drum,n-Butane]`: scaled `1.53937`, raw `1.53937 dimensionless`
- `liquid_hydraulics[tray_19]`: scaled `-0.531543`, raw `-3796.8 lbmol_per_h`
- `volume_closure[partial_reboiler]`: scaled `-0.467576`, raw `-1592.33 ft3`
- `liquid_hydraulics[tray_18]`: scaled `-0.372743`, raw `-2662.5 lbmol_per_h`
- `liquid_hydraulics[tray_11]`: scaled `-0.369101`, raw `-2636.48 lbmol_per_h`
- `volume_closure[tray_3]`: scaled `-0.353891`, raw `-89.9623 ft3`
- `liquid_hydraulics[tray_10]`: scaled `-0.341047`, raw `-2436.09 lbmol_per_h`

## Decision

DD-072 passes the numerical gate. The direct residual is finite at both ChemSep-related guesses, conservation telescopes, and both scaled Jacobians are full rank at both step sizes. This authorizes planning DD-073 bounded continuation, but DD-072 itself does not attempt a nonlinear solve.

DD-072 performs no Newton step, least-squares step, line search, continuation, optimization, or state correction.
