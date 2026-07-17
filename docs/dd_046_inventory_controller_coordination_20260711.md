# DD-046 Inventory Controller Coordination

Date: 2026-07-11

## Purpose

After bounded resident-vapor condensation restored condenser-duty pressure authority, the top accumulator and bottom sump continued accumulating liquid. This probe tests whether the remaining inventory drift is a controller-coordination problem rather than another material-balance or hydraulic-equation defect.

## Changes from the prior checkpoint

- Continued from the final DD-045 native checkpoint.
- Kept DWSIM Peng-Robinson thermo, live feed flashing, partial Francis-weir hydraulic ownership (`alpha=0.25`), composition-exponential equilibrium relaxation, and bounded resident-vapor condensation.
- Increased top level tuning from `Kc=5, Ti=300 s` to `Kc=20, Ti=120 s`.
- Increased bottom level tuning from `Kc=1, Ti=300 s` to `Kc=5, Ti=120 s`.
- Reduced the reflux command minimum from `5967.32` to `4500 lbmol/h`. This allows the distillate-composition controller to reduce reflux when distillate C4 is already below its `0.11` target.

No column equations or stage-specific behavior were changed for this probe.

## 120-second result

Run folder: `logs/c3c4_dd046_inventory_coordination_120s_20260711`

| Metric | Final value |
|---|---:|
| Dynamic rate gate | PASS |
| Steady-state score | 0.3455 |
| Top pressure | 232.872 psia |
| Condenser duty | -48.000 MMBtu/h |
| Distillate | 2936.796 lbmol/h |
| Reflux | 5814.745 lbmol/h |
| Distillate n-butane | 0.083153 mole fraction |
| Top level | 54.616% |
| Top level setpoint | 51.967% |
| Bottom level | 67.613% |
| Bottom level setpoint | 49.438% |
| Bottom product controller output | 6543.445 lbmol/h |
| Global mass-closure error | -7.73e-12 lbmol/h |

Final-60-second linear trends:

- Top pressure: `-1.914 psi/min`.
- Top level: `-0.154 percentage point/min`.
- Bottom level: `-0.731 percentage point/min`.
- Distillate C4: `-0.00199 mole fraction/min`.

## Interpretation

The coordinated control changes reversed both inventory trends without saturation, instability, or loss of mass closure. Distillate flow also recovered past the Excel target while reflux remained free to move. This is useful evidence that the immediate accumulation was substantially a controller-bandwidth and manipulated-variable coordination problem.

The result is not yet an accepted operating point. Both inventories remain above setpoint, pressure is still approaching its target, and distillate C4 is moving farther below specification. The next run must be long enough to reveal controller overshoot, interaction with the saturated condenser-duty command, and whether composition control can recover after inventories approach their setpoints.

## 300-second continuation

Run folder: `logs/c3c4_dd046_inventory_coordination_continue300s_20260711`

The longer continuation passed the rate gate at `score=0.5472`, but it showed that the candidate tuning is diagnostic rather than final:

| Metric | Final value |
|---|---:|
| Top pressure | 232.165 psia |
| Condenser duty used | -47.604 MMBtu/h |
| Incoming-condensation duty calculated | -48.524 MMBtu/h |
| Distillate | 3573.551 lbmol/h |
| Reflux | 4894.537 lbmol/h |
| Distillate n-butane | 0.075139 mole fraction |
| Top level | 52.232% |
| Top level setpoint | 51.967% |
| Bottom level | 56.150% |
| Bottom level setpoint | 49.438% |
| Bottom product controller output | 8565.615 lbmol/h |
| Global mass-closure error | -1.91e-11 lbmol/h |

Over the final `60 s`, top level fell about `0.247 percentage point/min` and bottom level fell about `2.93 points/min`. Pressure rose about `1.25 psi/min`, after reaching a minimum of `229.412 psia`, because the pressure PI backed duty away from the required incoming-condensation load. Distillate C4 continued falling, to `0.07514`, while the composition controller reduced reflux.

## Decision

Stay the course on controller coordination, but do not accept the current gains:

- Keep the top level loop near this tuning; it approached setpoint without a sharp crossing.
- Reduce bottom integral action before continuing, because the present draw trajectory will overshoot the sump setpoint.
- Retune pressure duty around the actual `48-49 MMBtu/h` load and provide enough lower duty range; the current `-48 MMBtu/h` clamp is already weaker than the calculated condensation requirement.
- Hold further reflux/composition tuning until pressure and vessel inventories are near their targets. Composition response is delayed by the column inventory, so simultaneous aggressive changes obscure the result.
