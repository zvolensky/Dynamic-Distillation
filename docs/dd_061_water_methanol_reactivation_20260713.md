# Water-Methanol Reactivation

Date: 2026-07-13

## Purpose

Revisit the 10-stage water-methanol ChemSep-seeded case with the current live
DWSIM UNIFAC path and inspect the tray liquid-flow profile near steady state.

## Resolved Feed Defect

The workbook calls its feed stream `Feed1`. The runner summary recognized that
stream, but the RHS previously accepted only the exact key `Feed`. Consequently,
the logs displayed the specified feed flow while the tray equations received no
feed source.

The feed lookup is now generic for canonical and numbered feed tags. The
corrected live probe applies:

- liquid feed: `4.409244 lbmol/s`
- vapor feed: `0 lbmol/s`
- effective vapor fraction: `0`

The feed-stage liquid holdup remained essentially unchanged during the first
`0.4 s`, confirming that the earlier deterministic drain was removed.

The same audit found a reporting-only alias gap for the workbook's `Top`
product stream. The physical draw was present, but summary distillate and
derived closure fields were `NaN`. The runner now recognizes `Top` as a
distillate alias; historical CSVs in the runs below retain the old reporting
gap.

## Valid Runs

- `logs/water_methanol_feed1fix_totalcond_alpha025_60s_20260713`
- `logs/water_methanol_feed1fix_topalign_totalcond_alpha025_120s_20260713`
- `logs/water_methanol_feed1fix_fullfrancis_totalcond_60s_20260713`

All use live DWSIM UNIFAC, total-condenser duty calculation, preserved seeded
vapor holdup, and `composition-exponential` equilibrium treatment.

## Gate Outcome

No accepted steady state was reached:

- 60-second full-Francis run: score `2.3556`, relative rate `0.00707/s`
- 120-second run: score `2.3119`, relative rate `0.00694/s`

The later limiting state was the reflux-drum water inventory. Distillate-drum
water mole fraction increased from `0.01442` to `0.02925`, while the live
condensate remained progressively richer in water. Top pressure also increased
from `14.6959` to `16.0624 psia`.

A larger `1 s` outer-step continuation initially appeared faster but was
rejected when its vapor-state score reversed and grew. It is not steady-state
evidence.

## Liquid Profile Comparison

At the valid 120-second endpoint, the used and fully calculated Francis rates
were practically identical and formed two flat sections:

| Stages | Used liquid flow (lbmol/h) | Francis liquid flow (lbmol/h) |
|---|---:|---:|
| 2-7 | about `15873.30` | about `15873.29` |
| 8-9 | about `31746.58` | about `31746.49` |

The corrected 100% Francis run followed the 25% blend almost exactly. The
section-wise plateaus are not caused by the old missing-feed defect and are not
merely inherited through profile blending.

ChemSep, however, predicts the same molar-flow pattern for this case:

- liquid flow is about `15873.3 lbmol/h` above the feed;
- the saturated-liquid feed adds about `15873.3 lbmol/h` at stage 8;
- liquid flow is about `31746.6 lbmol/h` below the feed;
- vapor flow remains about `23809.9 lbmol/h` through the interior.

This is consistent with constant molar overflow for a saturated-liquid feed,
not evidence by itself of defective tray hydraulics or phase totals.

The ChemSep mass-flow table is not flat. Its liquid mass rate decreases through
the rectifying section and changes again below the feed because average liquid
molecular weight changes with composition. The model's 120-second endpoint
shows the same distinction: internal molar liquid flow remains nearly constant
within each section while calculated liquid mass flow varies from about
`491847` to `372863 lb/h` over stages 2-7 and from about `720251` to
`710835 lb/h` over stages 8-9.

## Interpretation

This was not a good discriminator for DD-060's liquid-profile question because
the external ChemSep reference predicts the same section-wise molar plateaus.
The earlier interpretation that the profile shape independently proved missing
phase-total physics is withdrawn.

The dynamic result still should not be described as steady: the gate failed,
top pressure and overhead composition continued to drift, and the larger-step
continuation became less stable. Those convergence findings remain valid and
separate from whether the molar liquid-flow profile is physically reasonable.

DD-060 remains open based on the failed energy-inconsistent full-phase update
and conflicting pressure ownership, but this water-methanol profile is neither
supporting nor refuting evidence for that structural reformulation.
