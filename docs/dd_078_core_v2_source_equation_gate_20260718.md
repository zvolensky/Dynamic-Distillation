# DD-078 Core V2 Source-Equation Gate

## Purpose

DD-078 implements the first numerical equation assembly in the isolated
`core_v2` namespace. It is deliberately limited to the property-free binary
Skogestad source equations authorized by DD-077.

This increment tests indexing, terminal material balances, composition-rate
reconstruction, feed placement, hydraulic holdup response, and global
material conservation. It does not test energy, rigorous properties,
nonlinear solution, or dynamic integration.

## Result

The residual gate passes.

| Check | Result |
|---|---:|
| Nominal source-assembly parity | `2.22044604925e-16` |
| +1% feed-step assembly parity | `2.22044604925e-16` |
| Perturbed-state assembly parity | `5.56629395354e-16` |
| Published-profile maximum rate | `3.68312544907e-08 /min` |
| Global total-material closure error | `0` |
| Maximum global light-component closure error | `3.47e-16 kmol/min` |

The local Skogestad workbook contains the published tabulated profile. That
profile is not machine-exact under the source equations; its largest rate is
about `3.7e-8 /min`. The gate therefore uses `1e-7 /min` for the tabulated
profile while requiring v2-to-independent-translation parity within `1e-12`.

Evidence:

- `src/dynamic_distillation/core_v2/source_equation_gate_v1.py`
- `tools/audit_core_v2_source_equation_gate.py`
- `tests/test_core_v2_source_equation_gate_v1.py`
- `logs/dd078_core_v2_source_equation_gate_20260718.json`
- `logs/dd078_core_v2_source_equation_gate_20260718.md`

## Smaller-Column Assets

The repository's `sandbox/mini8` case will be used where it provides genuine
leverage:

- compact C3/C4 workbook and loader exercise;
- three-component feed and terminal data;
- pressure, temperature, liquid/vapor-flow, and composition seeds;
- tray geometry, vapor volume, weir dimensions, and hydraulic coefficients;
- UV state-building and terminal liquid-node patterns;
- simultaneous algebraic layout and Jacobian-conditioning audit patterns.

The mini8 workbook was created by sampling selected locations from the old
20-stage model. Its profile and historical trajectories are therefore not
independent validation data. They may seed or perturb a test, but they may not
be the acceptance answer.

The following legacy mechanisms are not authorized for reuse in `core_v2`:

- governing balances or physical ownership from the v1 runtime;
- profile-owned liquid or vapor traffic;
- clipping or projection of accepted states;
- explicit-Euler state advance;
- anchor regularization used to make a solve appear converged;
- historical mini8 run outcomes as proof of the v2 equations.

For Gate B, mini8 may supply one representative inventory volume, geometry,
composition, pressure, and a DWSIM property-provider call pattern. For Gate C,
its workbook may supply a compact case shell and parameter scale, but the
five-volume acceptance state must be independently reproduced under the new
equations.

## Decision

DD-078 passes the property-free residual portion of Gate A.

A separately bounded Gate A dynamic-integration comparison is authorized
next. Live DWSIM properties, a nonlinear five-volume solve, and production
integration remain unauthorized until their respective gates are reached.
