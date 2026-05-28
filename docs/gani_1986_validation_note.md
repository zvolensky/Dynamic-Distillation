# Gani 1986 Debutanizer Validation Note

Updated: 2026-05-26

## Status

The Gani/Ruiz/Cameron industrial debutanizer case is accepted only as a narrow
real-component source-topology material-balance parity check.

Accepted source-topology workbook:

- `validation_gani_1986_debutanizer_chemsep_source_topology.xlsx`

Accepted run:

- `logs/gani_chemsep_source_topology_material_60s/column_summary_20260525_220943.csv`

Accepted result:

- `steady_state_flag = 1`
- `steady_state_score = 1.08e-05`
- `ss_max_rel_state_rate_per_s = 3.24e-08/s`
- `ss_max_temp_rate_F_per_s = 0`

## What This Validates

This validates that the model can reproduce the ChemSep steady material-balance
profile when the model topology is made source-equivalent:

- no explicit reflux drum or bottom sump states
- no dynamic tray vapor states
- no equilibrium relaxation
- energy off
- ChemSep liquid and vapor compositions retained together
- ChemSep internal liquid/vapor flows retained together

This is useful because the case has named real hydrocarbon components and a
large industrial-style profile. It is stronger than a purely synthetic material
balance check, but it is still a limited validation claim.

## What This Does Not Validate

This run does not validate:

- explicit condenser drum dynamics
- explicit bottom sump dynamics
- tray vapor holdup dynamics
- hydraulic pressure dynamics
- stage energy balances
- condenser or reboiler duty response
- Clapeyron PR equivalence to ChemSep PR
- disturbance response

Those remain development targets.

## Why The Full Workbook Is Not Yet A Steady State

The full model-topology workbook intentionally includes explicit boundary
vessels, vapor states, and energy states. That topology is not the same as the
ChemSep steady profile.

The reconciliation audit showed two separate conflicts:

- In explicit-boundary topology, stage 28 accumulates about `+1231.76 lbmol/h`
  while the bottom sump loses about `-1231.76 lbmol/h`. This is a terminal
  reboiler/sump topology mismatch.
- In source topology, the original ChemSep vapor profile closes component
  balances to roundoff, but replacing that vapor profile with Clapeyron PR
  equilibrium vapor breaks component balances by up to about `186 lbmol/h`.

So there are two different notions of a steady seed:

- ChemSep material-balance parity requires ChemSep vapor composition.
- Model-thermo consistency requires a model-topology PR steady-state solve.

The second item has not yet been completed.

## Regression Check

Use this command to rerun the accepted narrow parity check:

```powershell
python tools\check_gani_source_topology_parity.py
```

The checker fails if the final run exceeds the configured steady-state score,
relative-rate, or temperature-rate thresholds.

## Next Development Step

The next rigorous target is a model-topology PR steady-state solve initialized
from the ChemSep profile:

- retain ChemSep liquid composition, temperatures, pressures, and flows as
  initial guesses
- use one PR backend consistently
- include explicit drum/sump states
- solve for model-consistent vapor composition, product draws, reflux/boilup,
  condenser duty, and reboiler duty
- only then run dynamic disturbance tests

