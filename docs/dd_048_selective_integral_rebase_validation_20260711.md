# DD-048 Selective Integral Rebase Validation

Date: 2026-07-11

Run folder: `logs/c3c4_dd048_selective_integral_rebase_180s_r2_20260711`

## Configuration

The run continued from the DD-047 physical checkpoint and explicitly rebased only `top-pressure` and `bottom-level`. Reflux remained fixed at `4900 lbmol/h`. Pressure control used a `-49.5 MMBtu/h` duty bias and `-52` to `-46 MMBtu/h` range.

## Result

| Metric | Final value |
|---|---:|
| Dynamic rate gate | PASS, score 0.8171 |
| Top pressure | 223.213 psia |
| Pressure setpoint | 222.619 psia |
| Condenser duty used | -49.640 MMBtu/h |
| Calculated incoming-condensation duty | -49.904 MMBtu/h |
| Top level | 51.906% |
| Top level setpoint | 51.967% |
| Bottom level | 49.244% |
| Bottom level setpoint | 49.438% |
| Bottoms draw | 4720.232 lbmol/h |
| Distillate draw | 3523.795 lbmol/h |
| Distillate n-butane | 0.069578 mole fraction |
| Global mass-closure error | -6.14e-12 lbmol/h |

The bottom integral ended near zero (`-31.2` controller units), rather than the inherited `+3512` contribution. The pressure integral also rebuilt from zero rather than retaining the previous `-1.86 MMBtu/h` contribution.

## Assessment

Selective integral rebase is working and solves the continuation-control-memory problem. Pressure and both vessel levels ended close to their setpoints without changing the physical checkpoint state or column equations.

This is not yet a settled product-composition operating point. The final rate score was increasing, distillate n-butane continued falling with fixed reflux, and bottoms composition continued changing. Composition control should be reintroduced only after confirming the pressure and level trajectories remain bounded over a longer continuation.
