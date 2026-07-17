# DD-047 ChemSep Duty Control Isolation

Date: 2026-07-11

## Question

Does centering the pressure controller around ChemSep's expected condenser duty of approximately `-49` to `-50 MMBtu/h` improve pressure behavior when reflux-composition interaction is removed?

## Probe

Run folder: `logs/c3c4_dd047_chemsep_duty_control_isolation_180s_r2_20260711`

- Continued from the final DD-046 physical checkpoint.
- Fixed reflux at `4900 lbmol/h` and disabled distillate-composition control for isolation.
- Used condenser-duty bias `-49.5 MMBtu/h`, minimum `-52 MMBtu/h`, and maximum `-46 MMBtu/h`.
- Used pressure `Kc=-150000 Btu/h/psi`, `Ti=300 s`.
- Kept top level `Kc=20`, `Ti=120 s`.
- Softened bottom level to `Kc=3`, `Ti=300 s`.
- Preserved checkpoint controller state using the normal native continuation behavior.

## Final result

| Metric | Final value |
|---|---:|
| Simulation / wall time | 180 / 363.84 s |
| Rate gate | PASS, score 0.5491 |
| Top pressure | 224.680 psia |
| Pressure setpoint | 222.619 psia |
| Condenser duty used | -51.629 MMBtu/h |
| Calculated incoming-condensation duty | -49.635 MMBtu/h |
| Fixed reflux | 4900.000 lbmol/h |
| Distillate | 3623.581 lbmol/h |
| Distillate n-butane | 0.072070 mole fraction |
| Top level | 52.103% |
| Top level setpoint | 51.967% |
| Bottom level | 47.664% |
| Bottom level setpoint | 49.438% |
| Bottom product controller output | 8176.580 lbmol/h |
| Global mass-closure error | 5.46e-12 lbmol/h |

## Findings

The ChemSep condenser-duty estimate is supported. Around `40 s`, applied and calculated duty both sat near `-48.6 MMBtu/h`; pressure then responded strongly as duty moved through the `-49` to `-50 MMBtu/h` range. Condenser authority is not the current blocker.

The run also shows why changing gains alone did not produce clean control. Native checkpoint continuation intentionally restored the prior pressure and bottom-level PI integrals. This provides bumpless transfer for an unchanged recipe, but the stored integrals reflected the previous bias, limits, tuning, and accumulated inventory error. At the endpoint:

- Pressure proportional contribution was only about `-0.269 MMBtu/h`, while integral contribution was about `-1.860 MMBtu/h`.
- Bottom proportional contribution had reversed to about `-98 lbmol/h`, but integral contribution remained about `+3512 lbmol/h`.

Those retained integrals continued driving both MVs after their PVs approached or crossed setpoint.

## Decision

Do not change column equations. The runner now provides repeatable `--rebase-controller-integral` selections to zero only the chosen saved PI integrals when the operator deliberately changes controller strategy, tuning, bias, limits, or MV ownership. Physical state and other controller memory remain unchanged. Existing restoration behavior remains the default for true same-recipe restarts.

The first live validation exposed a second level-controller restoration path that back-calculated the integral from the saved product command after checkpoint load. The implementation now suppresses that back-calculation only for explicitly selected level loops. The corrected DD-048 validation confirmed that both selected integrals remained rebased.
