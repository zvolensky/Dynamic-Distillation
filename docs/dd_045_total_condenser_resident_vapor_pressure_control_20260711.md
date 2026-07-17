# DD-045 Total-Condenser Resident Vapor and Pressure Control

Date: 2026-07-11

## Problem

The DWSIM PR 900-second continuation reached a rate-based steady-state pass but
settled at an unacceptable top pressure of 250.82 psia against a 222.62 psia
setpoint. Condenser duty saturated at -48 MMBtu/h while all incoming overhead
vapor was already condensed.

Final boundary diagnostics showed:

- incoming vapor condensed: 7457.89 lbmol/h,
- vapor slip to the top accumulator: 0 lbmol/h,
- resident top-vapor condensation: 0 lbmol/h,
- top-vapor inventory: 133.74 lbmol,
- top pressure: 250.82 psia, and
- PSV/vent flow: 0 lbmol/h.

Additional condenser duty could only change liquid subcooling after incoming
vapor was fully condensed. It had no material path for removing vapor already
resident in the accumulator, so condenser duty had lost pressure authority.

## Root Cause

`_condenser_mass_split_from_duty()` intentionally set resident-vapor
condensation to zero in specified-duty mode. That protection was introduced to
prevent the earlier fixed-duty vacuum collapse, where unrestricted excess duty
could consume the entire headspace. The protection removed the runaway but also
removed the physically necessary pressure-control path.

As drum liquid inventory rose and vapor headspace shrank, trapped resident vapor
was compressed. The pressure controller could fully condense incoming vapor but
could not reduce the stored vapor inventory.

## Implemented Correction

The opt-in CLI switch is:

`--enable-top-drum-resident-condensation`

When enabled in specified-duty mode, excess condenser capacity may condense
resident top vapor only when pressure exceeds the pressure setpoint. The rate is
bounded by all of the following:

1. Remaining duty capacity after condensing incoming vapor.
2. Resident vapor inventory above the inventory corresponding to the target
   pressure at the current volume and temperature basis.
3. A configurable first-order timescale.
4. A configurable maximum fraction of resident inventory per integration step.

The default candidate settings are:

- resident-condensation tau: 30 s,
- maximum fraction per step: 0.10.

The target-inventory bound prevents the correction from consuming vapor below
the pressure target and therefore avoids the previous vacuum-collapse behavior.
Condensed resident vapor enters the top liquid balance with equal component
removal from the vapor state. Existing condenser-boundary energy accounting
includes the resident condensation load.

## Verification

Focused condenser, RHS, and runner tests passed (`249 passed`). A live 60-second
DWSIM PR authority probe started from the 250.82 psia checkpoint with all other
model and controller settings unchanged.

| Metric | Start | Final |
|---|---:|---:|
| Top pressure (psia) | 250.82 | 243.12 |
| Resident condensation (lbmol/h) | about 741 at first log | 417.88 |
| Condenser duty (MMBtu/h) | -48.00 | -47.67 |
| Distillate flow (lbmol/h) | about 341 | 481.80 |
| Top geometric level | 51.48% | 52.36% |
| Distillate C4 | 0.09771 | 0.09489 |
| Dynamic score | 0.5688 at source | 0.7604 |

Pressure decreased monotonically throughout the probe. Global mass closure at
the final point was approximately `-3.2e-12 lbmol/h`. No vacuum behavior,
negative-inventory failure, or vapor wave occurred.

## Status and Next Gate

The missing pressure-authority mechanism is corrected and demonstrated, but the
new path remains opt-in pending a longer approach-to-setpoint test. Acceptance
requires:

- pressure approaching 222.62 psia without crossing into a vacuum runaway,
- resident condensation tapering to zero as pressure approaches target,
- condenser duty leaving saturation,
- stable drum and sump inventories,
- acceptable distillate and bottoms flow rates, and
- continued mass and equilibrium-gate compliance.

Authority-probe artifacts:

`logs/c3c4_dd045_resident_condensation_pressure_authority_60s_20260711`
