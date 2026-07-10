# External Review Model State: Feed Flash K=1 Fix and 900 s Run

Date: 2026-07-09

## Purpose

This package summarizes the current state of the C3/C4 dynamic distillation model after correcting the feed-stage flash split edge case. It is intended for external technical review of the model formulation, initialization workflow, and remaining dynamic-consistency concerns.

## Current Bottom Line

The model is materially healthier than it was during the artificial 50/50 feed-split failure. The feed-stage flash bug has been corrected, and a 900 s run with feed-stage flashing enabled now passes the rate-based steady-state gate.

However, the model should not yet be considered fully validated. The main remaining concern is that the run can pass the rate gate while the vapor composition state remains meaningfully inconsistent with thermo equilibrium (`K_state` versus `K_thermo`). This is a level-consistency problem, not a simple mass-balance problem.

## Important Recent Correction

The earlier 300 s feed-stage-flash run appeared to show feed flashing destabilizing the feed region by toggling the effective feed vapor fraction to `0.5`. That conclusion was revised.

The feed stream is specified near its bubble point with workbook vapor fraction `0.0`. The Clapeyron PR provider returned an unresolved/single-phase packet with approximately:

```text
K = [1, 1, 1]
```

For that packet, the Rachford-Rice residual is identically zero. The previous split logic allowed the bisection midpoint to become the effective vapor fraction, creating an artificial `beta = 0.5`. The code now treats `K ~= 1` feed flash packets as indeterminate and falls back to the source stream vapor fraction.

For the C3/C4 feed, the corrected split is:

```text
feed effective vapor fraction = 0.0
feed liquid rate = 1.98416036 lbmol/s
feed vapor rate = 0.0 lbmol/s
```

## Corrected 900 s Run

Run directory:

```text
logs/c3c4_stage2_stagefeedflash_k1fix_900s_20260709/
```

Command shape:

```text
python -m dynamic_distillation.dynamic_run_scaffold_v1
  --excel logs/c3c4_initializer_residual_vapor_state_stage2_20260706.xlsx
  --runtime-mode hydraulic
  --thermo clapeyron
  --clapeyron-model PR
  --include-energy
  --equilibrium-relaxation-mode composition-only
  --equilibrium-tau-sec 0.5
  --equilibrium-component-transfer-max-cancel-multiplier 1.0
  --flash-feed-at-stage-conditions
  --vapor-holdup-relaxation-sec 0
  --vapor-flow-relaxation-sec 0
  --vapor-flow-zero-temperature-target
  --use-excel-vapor-holdup
  --enable-pressure-control
  --pressure-control-mv top-anchor
  --top-pressure-sp 222.62
  --top-pressure-anchor-min 222.62
  --top-pressure-anchor-max 222.62
  --dynamic-vflow-nominal-hi-ratio 1.05
  --init-align-top-liquid-to-condensate
  --init-align-tray-liquid-to-equilibrium
  --init-tray-liquid-equilibrium-scope interior
  --init-tray-liquid-equilibrium-blend 1.0
  --init-align-tray-vapor-to-linear-steady
  --init-tray-vapor-linear-steady-scope interior
  --init-tray-vapor-linear-steady-blend 1.0
  --n-steps 4500
  --dt 0.2
  --log-every 25
```

Outcome:

| Metric | Value |
|---|---:|
| final time | `900 s` |
| final steady-state score | `0.970254` |
| gate status | `PASS` |
| peak score | `23.0505` |
| feed effective vapor fraction | `0.0` throughout logged run |
| max feed vapor-fraction step | `0` |
| feed-stage minimum liquid inventory | `12.9216 lbmol at 900 s` |
| worst feed-stage inventory update fraction | `0.0161337` |
| feed liquid closure residual | `0` |
| feed pressure-basis delta | `0 psi` |

## Comparison to Prior 900 s Run

The corrected feed-flash run is very close to the earlier accepted 900 s rate-gate result:

| Case | Final score | Peak score | Final status |
|---|---:|---:|---|
| prior 900 s recipe | `0.968655` | `14.0042` | rate gate passes |
| corrected feed-flash 900 s recipe | `0.970254` | `23.0505` | rate gate passes |

Interpretation: the feed-flash fix removes a real and unphysical failure mode, but it does not substantially change the long-run rate-gate behavior.

## Remaining Concern: K-State Drift

The corrected 900 s run still shows K-state drift:

| Metric | Value |
|---|---:|
| minimum max `|K_state - K_thermo|` | `0.891203` |
| final max `|K_state - K_thermo|` | `1.6588` |
| peak max `|K_state - K_thermo|` | `2.24065` |
| final max `|ln(K_state / K_thermo)|` | `1.93755` |
| final worst stage, 1-based | `5` |
| final worst component | `n_Pentane` |

This indicates that the model can satisfy a rate-based dynamic gate while a physical consistency metric remains poor. The acceptance gate should therefore include K-state level consistency and trend criteria, not only state-rate criteria.

## What Appears Sound

- Overall material accounting is not the current failure mechanism.
- Feed-stage material accounting closes in the audited runs.
- The corrected feed split no longer invents vapor from an indeterminate `K ~= 1` packet.
- The 900 s run remains bounded and passes the current steady-state score gate.
- The code path remains generic; the fix does not hardcode a tray number.

## What Remains Open

- Why `K_state` and `K_thermo` remain far apart after hundreds of seconds.
- Whether the explicit equilibrium-relaxation and component-transfer guard are creating a persistent under-correction.
- Whether the rate-based gate is too permissive without level-consistency checks.
- Whether the feed-region and upper/interior vapor-equilibrium coupling issues share a common formulation cause.
- Whether longer runs still fail after the feed split correction, especially beyond 900 s.

## Recommended Next Review Questions

1. Is the `K ~= 1` fallback treatment thermodynamically appropriate for all source-preserved feed streams, or should the model use a more explicit feed-quality specification such as enthalpy plus pressure?
2. Should equilibrium relaxation be reformulated as an implicit or exponential update instead of an explicitly integrated rate term with guards?
3. What K-state consistency threshold should be required before a run is considered initialized and usable?
4. Is the current steady-state score missing important level/state consistency signals?
5. Does the slow internal liquid inventory decline under fixed/profile liquid traffic indicate a remaining hydraulic/traffic closure issue?

## Included Artifact Highlights

- Corrected 900 s run metadata, profile CSV, summary CSV, startup trace, restart workbook, and native checkpoint.
- Feed-stage audit for corrected 900 s run.
- K-state drift audit for corrected 900 s run.
- Corrected 300 s feed-stage audit showing the artificial feed-split collapse was removed.
- Prior feed-flash failure audit for comparison.
- Relevant source files and tests:
  - `src/dynamic_distillation/column_rhs_v1.py`
  - `src/dynamic_distillation/dynamic_run_scaffold_v1.py`
  - `tools/audit_feed_stage_equations.py`
  - `tools/audit_k_state_drift.py`
  - `tests/test_column_rhs_v1.py`
