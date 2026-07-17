# DD-049 ChemSep Reflux and Product Split

Date: 2026-07-11

Run folder: `logs/c3c4_dd049_chemsep_reflux_product_split_180s_r3_20260711`

## Question

Why did DD-048 produce `3523.80 lbmol/h` of distillate instead of the expected ChemSep value near `2380 lbmol/h`?

## Material split

At the DD-048 endpoint:

- Condensate entering the drum was `8356.23 lbmol/h`.
- Reflux was deliberately fixed at only `4900.00 lbmol/h` for control isolation.
- A near-steady drum therefore required approximately `8356 - 4900 = 3456 lbmol/h` of distillate.
- The actual distillate draw was `3523.80 lbmol/h`, with the small difference explained by the drum-level trend.

The high product flow was therefore the physically expected response to the imposed low reflux, compounded initially by retained top-level integral memory.

## Probe and result

DD-049 continued from the DD-048 checkpoint, rebased only the top-level integral, and fixed reflux at the ChemSep-like `5967.32 lbmol/h` value.

| Metric | Final value |
|---|---:|
| Distillate | 2364.10 lbmol/h |
| Expected distillate | approximately 2380 lbmol/h |
| Reflux | 5967.32 lbmol/h |
| Top level | 51.984% |
| Top level setpoint | 51.967% |
| Top pressure | 225.234 psia |
| Pressure setpoint | 222.619 psia |
| Condenser duty used | -49.967 MMBtu/h |
| Calculated condenser duty | -50.783 MMBtu/h |
| Distillate n-butane | 0.06770 mole fraction |
| Dynamic rate score | 2.302, FAIL |
| Global mass-closure error | 6.01e-12 lbmol/h |

## Decision

The ChemSep reflux/distillate material split is confirmed. Keep reflux fixed at this validated value for the next diagnostic. Do not change the top product equations or level tuning.

The next run should center pressure control closer to the current `-50.8 MMBtu/h` condensation load and provide adequate duty range. Dynamic acceptance must improve before composition control is reintroduced; DD-049's rate score rose throughout the final window even though its product flow was correct.
