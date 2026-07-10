# External Review Addendum: Top-Boundary Fixed-Duty Sweep

Date: 2026-07-09

## Scope

This addendum covers only the work performed after the previous external-review collection. It focuses on the condenser-duty / top-boundary operating-point probes performed after the geometry-based level-controller run.

The base recipe retained:

- hydraulic runtime mode,
- Clapeyron PR thermo,
- energy enabled,
- feed flashed at stage conditions,
- live product draws from boundary liquid compositions,
- Francis liquid hydraulics with `alpha = 0.25`,
- true-level top drum and bottoms sump controllers,
- no pressure controller for the fixed-duty sweep.

## Question Investigated

The recent successful level-controller run passed the dynamic gate, but the top-boundary behavior remained suspicious:

- top-anchor pressure control created a large split between anchored column-top pressure and raw top-drum pressure,
- condenser-duty pressure control made top pressure and top-drum pressure consistent, but did not reach the target pressure,
- distillate flow remained far below the Excel/ChemSep design flow.

The immediate question was whether a fixed condenser duty closer to the Excel value would recover the intended operating point.

## Pressure-Control Probe Results

Three condenser-duty pressure-control probes were run before the fixed-duty sweep.

1. Default condenser-duty PI with specified-duty mode
   - Run: `logs/c3c4_stage2_productdrawfix_liqhyd_a025_truelevel_condduty_spec_1800s_20260709`
   - Final dynamic gate: pass
   - Final score: about `0.791`
   - Final top/top-drum pressure: about `200.22 / 200.22 psia`
   - Final condenser duty: about `-34.55 MMBtu/h`
   - Final distillate flow: about `801 lbmol/h`
   - Interpretation: dynamically bounded, but too little condenser duty and too little distillate production.

2. Positive-gain/aggressive condenser-duty PI
   - Run: `logs/c3c4_stage2_productdrawfix_liqhyd_a025_truelevel_condduty_spec_kcpos_1800s_20260709`
   - Final dynamic gate: fail
   - Final score: about `469`
   - Final top pressure: near zero
   - Final condenser duty: about `-150 MMBtu/h`
   - Interpretation: the duty lever is powerful, but aggressive PI destabilizes the top boundary.

3. Bounded high-duty condenser-duty PI
   - Run: `logs/c3c4_stage2_productdrawfix_liqhyd_a025_truelevel_condduty_spec_clamp45_1800s_20260709`
   - Final dynamic gate: fail
   - Final score: about `1.73`
   - Final top/top-drum pressure: about `168.62 / 168.62 psia`
   - Final condenser duty: `-45.00 MMBtu/h`
   - Final distillate flow: about `1210 lbmol/h`
   - Interpretation: keeping duty in a higher-cooling band improves the product-rate direction but still does not recover pressure or the design product rate.

## Fixed-Duty Sweep

Pressure control was removed. The condenser was run in specified-duty mode with fixed duties from `34` to `50 MMBtu/h` heat removal in `2 MMBtu/h` increments.

Run folders:

- `logs/c3c4_stage2_truelevel_fixedcond_Q34MM_1800s_20260709`
- `logs/c3c4_stage2_truelevel_fixedcond_Q36MM_1800s_20260709`
- `logs/c3c4_stage2_truelevel_fixedcond_Q38MM_1800s_20260709`
- `logs/c3c4_stage2_truelevel_fixedcond_Q40MM_1800s_20260709`
- `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_1800s_20260709`
- `logs/c3c4_stage2_truelevel_fixedcond_Q44MM_1800s_20260709`
- `logs/c3c4_stage2_truelevel_fixedcond_Q46MM_1800s_20260709`
- `logs/c3c4_stage2_truelevel_fixedcond_Q48MM_1800s_20260709`
- `logs/c3c4_stage2_truelevel_fixedcond_Q50MM_1800s_20260709`

Summary tables:

- `logs/fixed_condenser_duty_sweep_34_50MM_20260709.csv`
- `logs/fixed_condenser_duty_sweep_34_50MM_20260709.md`

Excel references used for comparison:

- condenser duty: `49.988 MMBtu/h` heat removal,
- reboiler duty: `54.844 MMBtu/h`,
- distillate flow: `2386.929 lbmol/h`,
- bottoms flow: `4761.985 lbmol/h`,
- top and bottom level setpoints: `0.5` fraction.

## Main Findings

The fixed-duty sweep did not recover the Excel operating point.

- The `34 MMBtu/h` case passed the final dynamic gate, but produced only about `597 lbmol/h` distillate, far below the Excel value of about `2387 lbmol/h`.
- Increasing duty raised distillate flow only modestly, reaching about `881-885 lbmol/h` near `46-50 MMBtu/h`.
- At `38 MMBtu/h` and above, the final raw top-drum pressure collapsed to approximately zero in the logged final state.
- Bottoms flow remained around `4430-4440 lbmol/h`, still below the Excel value by about `320-330 lbmol/h`.
- Reboiler duty was held at the Excel value throughout, so the observed changes are tied to the condenser/top-boundary side rather than a reboiler-duty change.

## Interpretation

The sweep rules out a simple fixed-condenser-duty explanation. Moving condenser duty toward the Excel value does not move the model toward the Excel operating point. Instead, it exposes an unresolved top-boundary pressure / vapor / condensation closure problem.

This is not a brand-new top-end audit finding. Earlier work already identified that:

- top-anchor pressure control can stabilize the run but hides a raw top-drum pressure deficit,
- top-drum vapor inventory deficit is real,
- condenser-duty pressure control exists but has not yet provided authoritative pressure recovery,
- top vapor-slip/gate behavior was not the direct cause of one earlier transient failure.

The present sweep adds a sharper operating-point result:

> Specified condenser duty near the Excel value causes raw top-drum pressure collapse rather than sustaining the expected overhead vapor, condensate, and distillate traffic.

The next investigation should therefore be targeted to the explicit chain:

```text
specified Qcond
-> condenser energy removal
-> V_condensed / V_to_top_drum
-> top vapor holdup derivative
-> raw P_top_drum from vapor holdup, T, volume, and Z
-> reflux and distillate liquid inventory response
```

The goal should be to determine whether the defect is in condenser mass/energy closure, top vapor inventory pressure calculation, vapor-to-drum traffic ownership, or a missing algebraic pressure/condensation constraint.

## Follow-Up Patch

After external review, the direct pressure-collapse mechanism was confirmed in
`_condenser_mass_split_from_duty()`. In specified-duty mode, excess cooling
capacity beyond the incoming-vapor latent load was being converted into
`V_cond_top`, which condensed the reflux drum's existing vapor inventory. This
could drive the explicit top vapor holdup to its numerical floor and collapse
`P_top_drum_psia` to vacuum.

The local patch changes specified-duty behavior so excess cooling beyond the
incoming vapor latent load is not treated as a material sink on `top_V`. It is
left as unused/subcooling capacity rather than a fictitious withdrawal of reflux
drum vapor.

Regression coverage:

- `tests/test_column_rhs_v1.py::test_specified_condenser_duty_excess_does_not_condense_top_holdup`
- focused mass-split test group: `python -m pytest tests\test_column_rhs_v1.py -k "mass_split"` passed, `5 passed`

Representative rerun:

- Pre-patch Q42 fixed-duty run:
  - final `P_top_drum_psia` about `1.6e-08 psia`
  - final `MV_top_drum_lbmol` about `8.5e-09 lbmol`
  - max `V_condensed_top_lbmolph` about `1398`
  - final score about `1.97`
- Post-patch Q42 fixed-duty rerun:
  - run folder: `logs/c3c4_stage2_truelevel_fixedcond_Q42MM_no_topv_condense_1800s_20260709`
  - final `P_top_drum_psia` about `182.57 psia`
  - final `MV_top_drum_lbmol` about `130.79 lbmol`
  - max `V_condensed_top_lbmolph` exactly `0`
  - final score about `1.19`

This confirms that the vacuum collapse was caused by the specified-duty
`V_cond_top` mechanism. The patch removes that failure mode, but it does not
recover the Excel operating point by itself: the Q42 rerun still fails the final
dynamic gate and still produces too little distillate. The remaining issue is
therefore narrower: pressure no longer collapses to vacuum, but the top boundary
still lacks an operating-point closure that can reconcile condenser duty,
incoming vapor traffic, reflux/drum inventory, and distillate production.
