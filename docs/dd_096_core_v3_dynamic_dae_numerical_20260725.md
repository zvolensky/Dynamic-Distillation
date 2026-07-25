# DD-096 Core V3 Dynamic DAE Numerical Result

Date: 2026-07-25

## Decision

DD-096 passes every frozen numerical gate in its single live execution from
contract commit `42975bc`.

The provider-derived storage chain rule and the complete Core V3 leading
implicit system are numerically regular at the exact DD-094 root. This result
authorizes only a separately frozen implicit-solver contract. No dynamic
integration has yet been performed.

## Result

```text
zero-derivative scaled residual     2.462658e-11
zero-derivative component rate     0.0 lbmol/h
zero-derivative storage-energy rate 0.0 BTU/h
storage-gradient step change       8.669536e-10
maximum storage bubble residual    4.662937e-15
leading ranks                      38/38, 38/38
leading conditions                 35.408730, 35.408732
singular-spectrum step change      3.512314e-7
component conservation error       2.578375e-16
energy conservation error          1.021448e-16
provider calls                     6306
provider violations                0
wall clock                         16.133 s
```

Both Jacobians have no zero row, no zero column, and no coupling outside the
DD-095 structural registry above the frozen `1e-7` threshold. All property
calls use declared DWSIM direct fugacity, phase enthalpy, or liquid density;
no provider fallback occurs.

## Interpretation

This is stronger than the DD-095 property-free rank result. It demonstrates
that the actual DWSIM storage derivatives do not make the local implicit
system singular or badly conditioned at the accepted reduced root. The
condition number near `35.4` is comfortably below the frozen `1e8` limit and
is substantially better than the earlier steady-state audit conditions.

It does not establish trajectory stability, disturbance behavior, controller
performance, full-column scalability, or production design-point accuracy.
The DD-094 drum remains compositionally heavier and `15.897 F` warmer than
the frozen source; DD-096 does not change that qualification.

## Next Authorized Increment

DD-097 may draft and precommit one numerical implicit-solver contract. It
should require, in order:

1. exact recovery of the DD-094 zero-rate algebraic solution;
2. a consistent implicit step whose state increment tends to zero as
   `dt -> 0`;
3. one bounded, very small open-loop step from the exact root;
4. conservation, provider, physical-domain, nonlinear-convergence, and step
   refinement gates fixed before execution.

No multi-step trajectory, controller, disturbance, initializer, production
tray count, pressure dynamics, or vapor-holdup extension is authorized by
DD-096.

Primary evidence:

- `logs/dd096_core_v3_dynamic_dae_numerical_contract_20260725.json`
- `logs/dd096_core_v3_dynamic_dae_numerical_20260725.json`
- `src/dynamic_distillation/core_v3/dynamic_dae_numerical_audit_v1.py`
- `tools/audit_core_v3_dynamic_dae_numerical.py`
- `tests/test_core_v3_dynamic_dae_numerical_audit_v1.py`
