# DD-064: Global Inventory Gate and Phase-Closure Probe

Date: 2026-07-17

## Problem

The C3/C4 run with bottoms propane composition control reached a low
rate-based steady-state score, but its products did not satisfy the overall
material balance:

- feed: `7142.98 lbmol/h`
- distillate: `2983.79 lbmol/h`
- bottoms: `4692.97 lbmol/h`
- `F - D - B`: `-533.79 lbmol/h`

The model conserved mass numerically: total modeled inventory was declining at
the same rate. The defect was therefore not arithmetic mass creation or loss.
The run was simply not at a material steady state.

## Experimental Probe

An opt-in, generic transport-balanced phase-transfer closure was tested from
the accepted 2400-second checkpoint. On every active tray it added the
equal-and-opposite liquid/vapor phase-transfer rate required to cancel the
pre-equilibrium total vapor derivative.

The one-step test showed:

- summed active-tray vapor derivative before correction: `-66.50 lbmol/h`
- summed vapor derivative after correction: numerical zero
- no change to pressure, product rates, duties, or global mass rate
- matched control and candidate both had restart score `8.7045`

The 60-second candidate remained bounded and ended at:

- old rate-gate score: `0.3735` (`PASS`)
- pressure: `223.62 psia`
- global inventory rate: `-530.03 lbmol/h`
- required phase generation: `352.77 lbmol/h`
- combined tray-liquid depletion: about `534.76 lbmol/h`

## Decision

Reject the local closure as a production solution.

It stabilizes vapor phase totals by removing the same material from tray
liquid. It does not reduce `F-D-B` or make the column materially steady. A
longer run would only test how the redistributed inventory loss propagates.

The implementation remains opt-in for reproducibility and diagnostics. It must
not be used as an accepted operating recipe.

## Gate Correction

The runtime steady-state detector now includes:

```text
ss_global_inventory_rate_frac_feed = abs(dM_total_dt_lbmolph) / abs(F_lbmolph)
```

The default tolerance is `0.01`, or one percent of feed. Nonpositive tolerance
disables this criterion. Cases without a finite nonzero feed omit the
feed-normalized criterion.

For the audited C3/C4 endpoint:

```text
abs(-530.03) / 7142.98 = 0.0742
score contribution = 0.0742 / 0.01 = 7.42
```

The same endpoint therefore fails instead of receiving a false steady-state
PASS.

## Next Model Step

Do not tune the local phase source further. The remaining model work is a
coupled closure in which:

1. interstage vapor flow and pressure are solved consistently,
2. phase generation satisfies component and energy balances,
3. liquid hydraulics respond to current inventory without retained profile
   ownership,
4. terminal product flows and total column inventory settle so `F-D-B`
   approaches zero.

This is evidence for the broader DAE/simultaneous-solve direction already
identified in `DD-060`.

## Evidence

- `logs/c3c4_transport_balanced_phase_one_step_20260717/`
- `logs/c3c4_composition_exponential_control_one_step_20260717/`
- `logs/c3c4_transport_balanced_phase_60s_20260717/`
