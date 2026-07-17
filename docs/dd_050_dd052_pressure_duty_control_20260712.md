# DD-050 through DD-052 Pressure-Duty Control

Date: 2026-07-12

## Purpose

Validate a `55 MMBtu/h` condenser-duty magnitude cap while preserving the DD-049 ChemSep-like reflux/product split.

## DD-050: cap and bias probe

DD-050 used duty bias `-50.8 MMBtu/h` and limits `-55` to `-46 MMBtu/h`. The cap was not reached. Applied duty matched calculated incoming-condensation demand near `-51.64 MMBtu/h`, but pressure still rose because essentially no excess duty remained to condense resident drum vapor. The rate score improved from DD-049's `2.30` to `1.14`, but still failed.

## DD-051: resident-vapor margin

DD-051 retained the `-55 MMBtu/h` cap and used:

- Bias: `-51.6 MMBtu/h`
- Pressure gain: `Kc=-300000 Btu/h/psi`
- Integral time: `Ti=180 s`

The run passed at `score=0.464`. Pressure fell to `223.40 psia`, applied duty was `-52.25 MMBtu/h`, and bounded resident condensation was about `44.8 lbmol/h`. The duty cap remained inactive.

## DD-052: unchanged setpoint approach

The unchanged `90 s` continuation passed at `score=0.469` and ended with:

| Metric | Final value |
|---|---:|
| Top pressure | 222.525 psia |
| Pressure setpoint | 222.619 psia |
| Condenser duty used | -52.052 MMBtu/h |
| Incoming-condensation duty calculated | -51.683 MMBtu/h |
| Resident condensation | 0 lbmol/h |
| Reflux | 5967.323 lbmol/h |
| Distillate | 2901.164 lbmol/h |
| Top level | 52.182% |
| Top level setpoint | 51.967% |
| Bottom level | 50.842% |
| Bottom level setpoint | 49.438% |
| Global mass-closure error | -1.30e-11 lbmol/h |

## Assessment

The `55 MMBtu/h` magnitude cap provides adequate safe authority, and the faster pressure tuning reached the pressure target without vacuum collapse or cap saturation. Pressure-loop development should stop here unless a longer hold reveals renewed drift.

Distillate is still above the ChemSep target because the drum is draining inventory accumulated during pressure recovery and because current condensate traffic (`8668 lbmol/h`) remains above the ChemSep-like reflux-plus-product total. Do not tune distillate or reflux again from this transient endpoint. Continue unchanged long enough to determine whether overhead traffic and product flow settle after pressure recovery.
