# DD-053 Unchanged Hold and Lower-Column Composition Front

Date: 2026-07-12

Run folder: `logs/c3c4_dd053_unchanged_operating_point_hold_300s_20260712`

## Result

The unchanged `300 s` hold failed the dynamic rate gate at `score=2.506`. Final operating values included:

| Metric | Final value |
|---|---:|
| Top pressure | 220.832 psia |
| Condenser duty | -51.285 MMBtu/h |
| Condensate | 8315.506 lbmol/h |
| Reflux | 5967.323 lbmol/h |
| Distillate | 2503.562 lbmol/h |
| Top level | 51.705% |
| Bottom level | 49.859% |
| Distillate n-butane | 0.064792 mole fraction |
| Bottoms n-butane | 0.774982 mole fraction |
| Global mass-closure error | 1.36e-12 lbmol/h |

Product traffic moved toward the ChemSep reflux/product split, but composition continued changing and the rate score worsened after approximately `240 s`.

## Failure localization

The gate's worst state was liquid n-propane on generic interior stage 19 at `0.00752/s`. The supporting audits show:

- Final maximum `|K_state-K_thermo|` improved monotonically to `0.2913`; it did not regrow.
- Median vapor transport/equilibrium cancellation coverage was `1.0027`.
- Maximum live vapor relative RHS was only `0.000942/s`.
- Stage 19 total liquid accumulation declined from about `0.0272` to `0.0222 lbmol/s` late in the run.
- Stage 19 used liquid outflow converged to its live hydraulic prediction: `12810` versus `12845 lbmol/h`.

At the endpoint, stage 19 contained only `3.682 lbmol` of liquid propane. Liquid transport brought propane in at `0.1569 lbmol/s`, while equilibrium phase transfer removed `0.1216 lbmol/s`, leaving `+0.0352 lbmol/s`. The implied component-inventory timescale was about `104 s`.

## Interpretation

This is consistent with a real propane composition front moving through the lower column after the earlier reflux and pressure changes. The finite-difference rate gate correctly rejects the state as steady because a small component inventory is changing quickly. The evidence does not support another pressure, level, equilibrium, or hydraulic equation change.

## Decision

Continue the current recipe unchanged. Reassess after the lower-column front passes, using all of:

- dynamic rate score and final-window trend,
- stage 19 liquid-component inventory rate,
- K-state drift audit,
- product-flow and product-composition proximity,
- pressure and geometric vessel-level control.
