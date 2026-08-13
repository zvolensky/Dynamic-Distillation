# DD-180 Seven-Volume Physical-Policy Longer-Trajectory Contract

## Purpose

DD-180 extends the seven-volume open-loop proof to thirty simulated seconds.
It uses the DD-176 physical-refinement policy and DD-179 duration-scaled
response policy from the outset. It does not rerun or reclassify DD-178.

## Frozen Experiment

- initial state: accepted DD-169 seven-volume stationary root;
- disturbance: unchanged `+0.1%` feed component rates and feed enthalpy;
- coarse path: `120 x 0.25 s`;
- refined path: `240 x 0.125 s`;
- shared comparisons: all 120 coarse endpoints against refined endpoints at
  the same physical times;
- controllers, clipping, projection, fallback, retry, alternate grid, and
  continuation: prohibited.

## Gates

All 360 roots must close below `1e-8`, retain rank `54`, condition below
`1e8`, physicality, equilibrium, conservation, and exact kinematics. All
shared times must pass the DD-176 physical inventory limits and `<1e-5`
rate/algebraic refinement. The unfloored component-relative maximum remains
diagnostic only.

Each path's actual total accumulation must match its integrated expected
external flow within `1e-6` relative, remain positive and monotone, and retain
global component identity below `1e-6 lbmol`. Coarse/refined actual totals
must agree within `1e-9 lbmol`. No duration-independent absolute response
ceiling is present.

Logical calls must remain below `2,000,000`; wall time must remain below
`600 s`. Compact evidence retains each root's scalar gate data, complete path
endpoints, total-inventory histories, and all 120 shared comparisons.

## Decision

A complete pass authorizes only structural design of terminal inventory
control. No live controller or longer trajectory is authorized directly.
Failure stops the physical-policy trajectory path.
