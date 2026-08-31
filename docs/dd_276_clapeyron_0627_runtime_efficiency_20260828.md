# DD-276 Clapeyron 0.6.27 Runtime-Efficiency Study

## Decision

Clapeyron is faster than DWSIM inside the warm thermo kernel, but it does not
improve the accepted Core V3 dynamic runtime in the architecture tested so
far. DWSIM remains the runtime authority. A new persistent single-runtime
batch measurement is sufficiently fast to justify one static residual-level
integration benchmark; repeating the prior four-worker hybrid trajectory
unchanged is not justified.

The Clapeyron 0.6.27 inactive-phase fix does not itself accelerate the current
production path because its new K-value API is diagnostic-only and is not
called by the governing runtime.

## Current Replay

The DD-161 five-volume, 28-call property packet was rerun in a fresh Python
process after Julia package provisioning and compilation completed.

| Measurement | DWSIM | Clapeyron | DWSIM / Clapeyron |
|---|---:|---:|---:|
| 50 warm property packets | `0.544324 s` | `0.070413 s` | `7.730x` |
| Historical DD-161 replay | `1.117091 s` | `0.120901 s` | `9.240x` |

The current parameter-aligned path spent `9.925 s` extracting DWSIM PR data
and another `12.538 s` constructing the Clapeyron model.  Relative to retaining
an already-required DWSIM initialization, the extra Clapeyron construction
cost would be recovered after roughly `1,323` of these packets, or `37,039`
property calls.  This is an arithmetic kernel break-even estimate, not a
dynamic-runtime projection.

The first fresh-process attempt triggered Julia dependency provisioning and
43 seconds of package precompilation.  That one-time environment setup is
excluded from the representative startup comparison.

## Persistent DD-274 Fugacity Batch

The exact accepted DD-274 final profile supplies 20 liquid/vapor volume pairs,
or 40 imposed-phase fugacity rows per residual evaluation. Three trials of
4,000 rows each produced these warm medians in one process:

| Route | Wall | Relative result |
|---|---:|---:|
| DWSIM scalar | `2.979306 s` | baseline |
| Clapeyron scalar | `0.379574 s` | `7.849x` faster |
| Clapeyron, one 40-row Julia call | `0.098790 s` | `30.158x` faster than DWSIM |

Batching is `3.842x` faster than scalar Clapeyron. Batch and scalar Clapeyron
values agree exactly; the maximum Clapeyron/DWSIM fugacity-coefficient
difference is `6.377e-5`, within the existing fugacity qualification.

This changes the performance outlook from negative to promising, but does not
yet establish a dynamic speedup. Only `219,640 / 658,920`, exactly one-third,
of DD-274's logical provider calls are qualified fugacity calls. The current
residual issues them individually, and exact memoization means an unknown
fraction of the logical calls are cache hits that never reach DWSIM. A static
residual integration benchmark must preserve those hits while batching only
the misses before an end-to-end projection is credible.

## 0.6.27 Diagnostic-Flash Timing

The frozen 54-state DD-275 campaign was repeated ten times after warmup.

| Measurement over 540 state calls | Wall | Relative result |
|---|---:|---:|
| DWSIM full flash (`K`, `HL`, `HV`, `Z`) | `0.788674 s` | baseline |
| Clapeyron inactive-K diagnostic (`K`, `Z`) | `0.370186 s` | `2.130x` faster |
| DWSIM full flash (`K`, `HL`, `HV`, `Z`) | `0.782697 s` | baseline |
| Clapeyron diagnostic plus forced `HL`, `HV`, `Z` | `0.461545 s` | `1.696x` faster |

The second pair is the closer property bundle.  It remains timing-only:
Clapeyron classifies 44 of the 54 K vectors as retained inactive-phase
estimates rather than equilibrium values.

## Why Kernel Speed Has Not Become Simulation Speed

The prior bounded studies show the gain collapsing as more of the real solve
is included:

| Scope | Clapeyron/hybrid result versus DWSIM |
|---|---:|
| Warm 28-call thermo packet | `7.7-9.2x` faster |
| Hybrid residual and colored Jacobian (DD-162) | `1.395x` faster |
| Hybrid matrix inside a DWSIM-owned root (DD-164) | `1.101x` faster |
| 30-root hybrid trajectory (DD-166 vs DD-158) | `1.887x` slower |
| Total governed wall (DD-166 vs DD-158) | `2.183x` slower |
| Four-worker pool startup (DD-166 vs DD-158) | `4.553x` slower |

DD-166 took `10.075 s` for the trajectory versus `5.338 s` for memoized
DWSIM.  Its four Julia-backed workers took `28.792 s` to start versus
`6.323 s` for the DWSIM pool.  The hybrid also retained DWSIM for main-process
residuals, line searches, endpoint decisions, enthalpy, density, and vapor Z,
so fugacity acceleration addressed only part of the cost.

## Scientific Boundary

Full backend replacement is still not a performance-only change.  At the
fixed DD-161 states, parameter-aligned Clapeyron differs from DWSIM by as much
as `7.445%` in liquid density and `172.946 BTU/lbmol` in latent enthalpy.  In
the DD-275 54-state campaign, maximum absolute K difference is `0.0416124`
and maximum absolute log-ratio difference is `0.154610`.  Those differences
would alter hydraulics, energy balances, or equilibrium targets.

## Recommended Next Experiment

Before another trajectory, integrate one persistent single Julia runtime into
a captured Core V3 residual/Jacobian benchmark and quantify:

1. batch-aware exact memo hits and misses for every 40-row fugacity group;
2. DWSIM versus batched-Clapeyron residual and Jacobian differences;
3. measured wall improvement after retained enthalpy, density, and vapor-Z
   calls;
4. projected break-even over the accepted 30-second DD-274 call volume.

Only if that static/captured benchmark predicts an end-to-end gain should a
new trajectory contract be considered.

Evidence:

- `logs/dd276_clapeyron_0627_runtime_efficiency_20260828.json`;
- `logs/dd276_clapeyron_0627_runtime_probe_r2_20260828.json`;
- `logs/dd161_core_v3_clapeyron_provider_qualification_20260806.json`;
- `logs/dd162_core_v3_hybrid_fugacity_benchmark_20260806.json`;
- `logs/dd164_core_v3_clapeyron_jacobian_dwsim_root_20260806.json`;
- `logs/dd158_core_v3_memoized_captured_short_trajectory_20260806.json`;
- `logs/dd166_core_v3_hybrid_jacobian_memoized_short_trajectory_20260806.json`.
