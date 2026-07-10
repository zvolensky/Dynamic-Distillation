# External Review Brief: Unit-K Quarantine and Low-Overhead Steady State

Date: 2026-07-09

## Purpose

This package captures the latest C3/C4 dynamic distillation model state after two related findings:

1. Specified condenser duty no longer consumes reflux-drum vapor holdup as a material sink.
2. Refreshed thermo packets with unit K-values are quarantined when a valid prior non-unit-K packet exists.

The new behavior is materially better, but still not fully satisfactory. The model can pass the dynamic steady-state gate while settling to a low-pressure, low-overhead operating point that is not the Excel/ChemSep operating point.

## Headline Findings

- The previous fixed-duty Q42 run after the condenser-material-sink fix ended with overhead vapor around 5335 lbmol/h and distillate around 622 lbmol/h.
- A 300 s run after the unit-K quarantine produced a near-Excel transient state:
  - overhead vapor: 7819.6 lbmol/h
  - distillate: 2393.4 lbmol/h
  - bottoms: 4693.8 lbmol/h
  - top drum pressure: 233.0 psia
- The full 1800 s run after the same patch passed the dynamic gate but drifted away from that operating point:
  - steady-state score: 0.410, PASS
  - overhead vapor: 5035.1 lbmol/h
  - distillate: 1155.9 lbmol/h
  - bottoms: 4443.5 lbmol/h
  - top drum pressure: 195.2 psia

## Interpretation

The unit-K thermo packet issue was real and the patch changed the trajectory substantially. However, the model appears to relax from a near-Excel operating point into another dynamically quiet state with much lower overhead traffic. That suggests the remaining issue is not simply numerical blow-up or controller tuning. It is likely an operating-point closure problem involving pressure, condenser duty, reflux demand, and vapor/energy closure.

At final time, the top boundary is again infeasible relative to Excel:

- Excel reference reflux + distillate demand: 8332.3 lbmol/h
- Final condensate to top drum: 5035.1 lbmol/h
- Fixed reflux draw: 5967.3 lbmol/h
- Final condensate is below reflux alone by 932.2 lbmol/h

The dynamic gate passes because rates are small, but the accepted state is not the desired Excel/ChemSep operating point.

## Important Time Trend

| t | steady-state score | top drum pressure psia | overhead vapor lbmol/h | distillate lbmol/h | bottoms lbmol/h | top level | Qcalc MMBtu/h |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 300 | 3.491 | 232.99 | 7819.6 | 2393.4 | 4693.8 | 0.512 | -46.69 |
| 600 | 2.311 | 230.33 | 7306.8 | 2330.9 | 4570.1 | 0.496 | -45.79 |
| 900 | 1.256 | 229.74 | 6611.0 | 2179.4 | 4434.2 | 0.466 | -42.60 |
| 1200 | 1.038 | 219.81 | 6172.1 | 1940.5 | 4404.6 | 0.428 | -39.78 |
| 1500 | 1.810 | 207.67 | 5382.0 | 1606.1 | 4410.9 | 0.383 | -34.76 |
| 1800 | 0.410 | 195.20 | 5035.1 | 1155.9 | 4443.5 | 0.330 | -32.45 |

## Questions for External Review

1. Is the runtime model missing an operating pressure/condenser duty closure that should keep the system near the Excel total-condenser operating point?
2. Should a dynamic acceptance gate require product/pressure/overhead-vapor proximity to the seed, not just low rates?
3. Is fixed condenser duty being interpreted correctly for a total condenser, especially when actual required duty drifts from the specified value?
4. Is the unit-K quarantine physically appropriate, or should the thermo provider avoid returning unit-K packets for live distillation trays in the first place?
5. Is the model overconstrained by fixed reflux plus level-controller distillate plus fixed condenser duty, causing migration to another feasible but undesired steady state?

## Included Artifacts

- Source workbook: `logs/c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx`
- Latest 300 s run: `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_unitKquarantine_300s_20260709`
- Latest 1800 s run: `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_unitKquarantine_1800s_20260709`
- Prior patched-condenser 1800 s run: `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_no_topv_condense_1800s_20260709`
- Overhead feasibility reports for the latest and prior runs.
- Relevant source/test files and a local patch diff.
